"""Bootstrap del suscriptor: cierra el lazo entrada↔salida.

Pasos (todos idempotentes / find-or-create):
  1. Aprovisiona el catálogo en ODM (un manifiesto por publisher).
  2. Asegura la Application de ckan-jerez y registra su webhook (URL + secreto).
  3. Resuelve los IDs de los recursos del catálogo y suscribe los que falten.

Tras esto, cuando ODM cargue datos de un recurso suscrito, notificará a ckan-jerez
por el webhook, que publicará el dataset homogéneo en el CKAN.
"""
from __future__ import annotations

from typing import Optional

from services.odm_client import OdmClient
from services.provisioning import provision_catalog


def ensure_application(client: OdmClient, *, name: str, webhook_url: Optional[str] = None,
                       consumption_mode: str = "webhook") -> dict:
    """Encuentra la Application por nombre o la crea (find-or-create)."""
    app = next((a for a in client.applications() if a.get("name") == name), None)
    if app is None:
        app = client.create_application(name=name, webhook_url=webhook_url,
                                        consumption_mode=consumption_mode)
    return app


def resolve_resource_ids(client: OdmClient, catalog: dict) -> dict:
    """Mapea {nombre → resourceId} con DOS orígenes:
    1. Lo declarado en el catálogo, casando por (publisher, name) y, en su
       defecto, por name (requiere recursos ya aprovisionados).
    2. ADOPCIÓN: todos los recursos de ODM cuyos publisher figure en
       `subscribe_publishers` (acrónimo o nombre), estén o no declarados —
       así los recursos heredados quedan suscritos sin redeclararlos."""
    publishers = catalog.get("publishers") or {}
    recursos = client.resources()
    by_pub_name = {(r.get("publisher"), r.get("name")): r["id"] for r in recursos}
    by_name: dict[str, str] = {}
    for r in recursos:
        by_name.setdefault(r.get("name"), r["id"])

    ids: dict[str, str] = {}
    for s in (catalog.get("sources") or []):
        pub_nombre = (publishers.get(s.get("publisher")) or {}).get("nombre")
        rid = by_pub_name.get((pub_nombre, s["name"])) or by_name.get(s["name"])
        if rid:
            ids[s["name"]] = rid

    adoptar = set(catalog.get("subscribe_publishers") or [])
    if adoptar:
        alias = set(adoptar)
        for acro in adoptar:                       # acrónimo y nombre valen
            nombre = (publishers.get(acro) or {}).get("nombre")
            if nombre:
                alias.add(nombre)
        for r in recursos:
            if r.get("publisher") in alias and r.get("name") not in ids:
                ids[r["name"]] = r["id"]
    return ids


def ensure_subscriptions(client: OdmClient, application_id: str, resource_ids: dict, *,
                         auto_upgrade: str = "patch") -> list[str]:
    """Suscribe los recursos que aún no lo estén. Devuelve los recién suscritos."""
    ya = {sub.get("resourceId") for sub in client.dataset_subscriptions(application_id=application_id)}
    nuevos = []
    for name, rid in resource_ids.items():
        if rid in ya:
            continue
        client.subscribe_resource(application_id=application_id, resource_id=rid, auto_upgrade=auto_upgrade)
        nuevos.append(name)
    return nuevos


def bootstrap(client: OdmClient, *, catalog: dict, app_name: str, webhook_url: str,
              webhook_secret: str, auto_upgrade: str = "patch", dry_run: bool = False) -> dict:
    """Orquesta el bootstrap completo. dry_run=True solo previsualiza el provisioning
    (no crea Application, ni webhook, ni suscripciones)."""
    prov = provision_catalog(client, catalog, dry_run=dry_run)
    if dry_run:
        return {"dry_run": True, "manifests": prov["manifests"], "applied": False}

    app = ensure_application(client, name=app_name, webhook_url=webhook_url)
    client.set_application_webhook(app["id"], webhook_url, webhook_secret)
    ids = resolve_resource_ids(client, catalog)
    subscribed = ensure_subscriptions(client, app["id"], ids, auto_upgrade=auto_upgrade)
    return {
        "dry_run": False,
        "application_id": app["id"],
        "provisioned": prov.get("results"),
        "resources_resolved": len(ids),
        "subscribed": subscribed,
        "already_subscribed": [n for n in ids if n not in subscribed],
    }
