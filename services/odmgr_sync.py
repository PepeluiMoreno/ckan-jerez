"""Ingesta del webhook de ODM y disparo de la publicación homogénea en CKAN.

A diferencia de un consumidor de dominio (que rutea por resource_name a sus
tablas), ckan-jerez es un homogeneizador: CUALQUIER dataset de ODM se proyecta de
forma uniforme a un package CKAN (DCAT), sin ramas por recurso.
"""
from __future__ import annotations

import hashlib
import hmac
from typing import Optional

from app import pub_state
from app import mapping_state
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
    dataset = payload.get("dataset") or {}
    download_urls = payload.get("download_urls") or {}

    publisher = dataset.get("publisher")
    if publisher is None and publishers:
        acro = dataset.get("publisher_acronimo") or dataset.get("publisher_id")
        publisher = publishers.get(acro) if acro else None

    pub_state.record_received(dataset)
    rid = dataset.get("resource_id")
    version = dataset.get("version")
    overrides = mapping_state.get(rid) if rid else {}
    try:
        out = publish_dataset(sink, dataset, download_urls, publisher=publisher,
                              overrides=overrides)
    except Exception as exc:  # noqa: BLE001
        pub_state.record_error(rid, version, str(exc))
        raise
    pub_state.record_published(rid, version, out["result"]["name"], out["result"]["action"])
    return {
        "action": "published",
        "package": out["result"]["name"],
        "result": out["result"]["action"],
        "dataset_id": dataset.get("id"),
    }
