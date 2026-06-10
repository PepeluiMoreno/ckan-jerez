"""Ingesta del webhook de ODM y disparo de la publicación homogénea en CKAN.

A diferencia de un consumidor de dominio (que rutea por resource_name a sus
tablas), ckan-jerez es un homogeneizador: CUALQUIER dataset de ODM se proyecta de
forma uniforme a un package CKAN (DCAT), sin ramas por recurso.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from services.ckan_publisher import CkanSink, publish_dataset


def verify_hmac(payload_bytes: bytes, signature: str, secret: str) -> bool:
    """Verifica la firma HMAC-SHA256 del webhook de ODM (header X-ODM-Signature)."""
    expected = hmac.new(secret.encode(), payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, (signature or "").removeprefix("sha256="))


def handle_notification(payload: dict, *, sink: CkanSink,
                        publishers: Optional[dict] = None) -> dict:
    """Webhook genérico: dataset de ODM → package CKAN (DCAT), sea cual sea su
    fetcher u organismo. `publishers` (opcional) resuelve el organismo por acrónimo
    si el payload no trae el bloque publisher."""
    evento = payload.get("evento")
    if evento in ("suscripcion_activada", "suscripcion_desactivada"):
        from app import subscriptions_store as store
        if evento == "suscripcion_activada":
            store.upsert(resource_id=payload.get("resourceId"),
                         subscription_id=payload.get("subscriptionId"),
                         resource_name=payload.get("resourceName"),
                         publisher=payload.get("publisher"),
                         pinned_version=payload.get("pinnedVersion"),
                         auto_upgrade=payload.get("autoUpgrade"))
            store.log_event("suscripcion_activada", resourceId=payload.get("resourceId"),
                            resourceName=payload.get("resourceName"), publisher=payload.get("publisher"))
            return {"action": "subscription_added", "resourceId": payload.get("resourceId")}
        store.remove(resource_id=payload.get("resourceId"),
                     subscription_id=payload.get("subscriptionId"))
        store.log_event("suscripcion_desactivada", resourceId=payload.get("resourceId"))
        return {"action": "subscription_removed", "resourceId": payload.get("resourceId")}
    if evento in ("anulada", "aplicacion_anulada"):
        from app import subscriptions_store as store
        store.clear()
        store.log_event("anulada")
        return {"action": "deregistered"}
    if evento and evento not in ("notificacion", "dataset"):
        # otros eventos de gobernanza (solicitud_resuelta, recurso_resuelto, …): ignorar
        return {"action": "ignored", "evento": evento}

    dataset = payload.get("dataset") or {}
    if not dataset:
        return {"action": "ignored", "reason": "payload sin dataset"}
    download_urls = payload.get("download_urls") or {}

    publisher = dataset.get("publisher")
    if publisher is None and publishers:
        acro = dataset.get("publisher_acronimo") or dataset.get("publisher_id")
        publisher = publishers.get(acro) if acro else None

    out = publish_dataset(sink, dataset, download_urls, publisher=publisher)
    from app import subscriptions_store as store
    store.log_event("publicado", package=out["result"]["name"],
                    result=out["result"]["action"], datasetId=dataset.get("id"))
    return {
        "action": "published",
        "package": out["result"]["name"],
        "result": out["result"]["action"],
        "dataset_id": dataset.get("id"),
    }
