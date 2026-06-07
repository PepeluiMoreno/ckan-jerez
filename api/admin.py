"""API HTTP del panel de operador de ckan-jerez (la consume la SPA).

Consola del SUSCRIPTOR: gestiona lo suyo (sus fuentes, su Application/webhook, su
flujo de datos), hablando con ODM por su API pública. Las acciones de escritura
deben quedar tras autenticación/VPN antes de exponer esto públicamente.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["admin"])

CATALOG_PATH = pathlib.Path(__file__).resolve().parents[1] / "data/odm_resources/jerez.json"
APP_NAME = "ckan-jerez"

_client = None


def _client_or_error():
    global _client
    if _client is None:
        from services.odm_client import OdmClient
        c = OdmClient.from_env()
        c.login()
        _client = c
    return _client


def _odm(fn):
    """Ejecuta una llamada a ODM; 502 legible si falla (incluida auth/red)."""
    try:
        return fn(_client_or_error())
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning("ODM call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"ODM no disponible o error: {e}")


def _catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text())


def _app_id(client) -> Optional[str]:
    app = next((a for a in client.applications() if a.get("name") == APP_NAME), None)
    return app["id"] if app else None


# ── Estado / metadatos ────────────────────────────────────────────────────────
@router.get("/version")
def version() -> dict:
    return {"version": (os.getenv("APP_VERSION") or "dev")[:7]}


@router.get("/system/info")
def system_info() -> dict:
    total = avail = 0
    try:
        with open("/proc/meminfo") as f:
            mem = {l.split(":")[0]: int(l.split()[1]) for l in f if ":" in l}
        total = mem.get("MemTotal", 0) // 1024
        avail = mem.get("MemAvailable", 0) // 1024
    except Exception:  # noqa: BLE001
        pass
    return {"ram_total_mb": total, "ram_available_mb": avail}


@router.get("/status")
def status() -> dict:
    s = get_settings()
    out = {"ckan_configured": s.ckan_configured, "odm": "unknown", "application": None}
    try:
        c = _client_or_error()
        out["odm"] = "online"
        out["application"] = _app_id(c)
    except Exception as e:  # noqa: BLE001
        out["odm"] = "offline"
        out["error"] = str(e)
    return out


@router.get("/catalog")
def catalog() -> dict:
    return _catalog()


# ── Lecturas de ODM ───────────────────────────────────────────────────────────
@router.get("/odm/resources")
def odm_resources() -> Any:
    return _odm(lambda c: c.resources())


@router.get("/odm/fetchers")
def odm_fetchers() -> Any:
    return _odm(lambda c: c.fetchers())


@router.get("/odm/subscriptions")
def odm_subscriptions() -> Any:
    return _odm(lambda c: c.dataset_subscriptions(application_id=_app_id(c)))


@router.get("/odm/executions")
def odm_executions(resource_id: Optional[str] = None) -> Any:
    return _odm(lambda c: c.resource_executions(resource_id))


@router.get("/odm/notifications")
def odm_notifications() -> Any:
    return _odm(lambda c: c.application_notifications(application_id=_app_id(c)))


# ── Acciones (escritura) ──────────────────────────────────────────────────────
@router.post("/odm/manifest-template")
def manifest_template(body: dict = Body(...)) -> Any:
    return _odm(lambda c: c.manifest_template(body["fetcherCode"], body.get("presetCode")))


@router.post("/sources/provision")
def provision(body: dict = Body(default={})) -> Any:
    from services.provisioning import provision_catalog
    dry = bool(body.get("dry_run", True))
    return _odm(lambda c: provision_catalog(c, _catalog(), dry_run=dry))


@router.post("/odm/execute")
def execute(body: dict = Body(...)) -> Any:
    rid = body.get("resource_id")
    if not rid:
        raise HTTPException(status_code=400, detail="falta resource_id")
    return _odm(lambda c: c.execute_resource(rid))


@router.post("/bootstrap")
def do_bootstrap(body: dict = Body(default={})) -> Any:
    from services.bootstrap import bootstrap
    s = get_settings()
    dry = bool(body.get("dry_run", True))
    if not dry and (not s.webhook_url or not s.odm_webhook_secret):
        raise HTTPException(status_code=400, detail="faltan PUBLIC_BASE_URL y/o ODM_WEBHOOK_SECRET")
    return _odm(lambda c: bootstrap(c, catalog=_catalog(), app_name=APP_NAME,
                                    webhook_url=s.webhook_url, webhook_secret=s.odm_webhook_secret, dry_run=dry))
