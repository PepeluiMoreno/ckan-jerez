"""API HTTP del panel de operador de ckan-jerez (la consume la SPA).

Consola del SUSCRIPTOR. ckan-jerez NO llama a ODM: el operador gobierna las
suscripciones en ODM y ODM nos las empuja por webhook (firmado HMAC). La consola
solo muestra estado LOCAL: suscripciones recibidas, configuración y últimos
eventos. Las acciones de escritura sobre ODM ya no existen aquí.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any

from fastapi import APIRouter

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["admin"])

CATALOG_PATH = pathlib.Path(__file__).resolve().parents[1] / "data/odm_resources/jerez.json"
APP_NAME = "ckan-jerez"


def _catalog() -> dict:
    try:
        return json.loads(CATALOG_PATH.read_text())
    except Exception:  # noqa: BLE001
        return {}


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
    """Estado LOCAL: no se contacta con ODM. 'operativa' = configuración mínima
    presente para poder recibir (secreto del webhook y URL pública)."""
    from app import subscriptions_store as store
    s = get_settings()
    faltan = [k for k, v in (("PUBLIC_BASE_URL", s.public_base_url),
                             ("ODM_WEBHOOK_SECRET", s.odm_webhook_secret)) if not v]
    return {
        "ckan_configured": s.ckan_configured,
        "config_missing": faltan,
        "operativa": not faltan,
        "webhook_url": s.webhook_url or None,
        "subscriptions_count": len(store.list_all()),
    }


@router.get("/catalog")
def catalog() -> dict:
    return _catalog()


# ── Lecturas LOCALES (lo que ODM nos ha empujado) ─────────────────────────────
@router.get("/odm/subscriptions")
def odm_subscriptions() -> Any:
    """Suscripciones que ODM nos ha comunicado por webhook (estado local)."""
    from app import subscriptions_store as store
    return store.list_all()


@router.get("/odm/resources")
def odm_resources() -> Any:
    """En el modelo push los 'recursos' del consumidor son sus suscripciones."""
    from app import subscriptions_store as store
    return [{"id": s.get("resourceId"),
             "name": s.get("resourceName") or s.get("resourceId"),
             "publisher": s.get("publisher"),
             "subscriptionId": s.get("subscriptionId"),
             "since": s.get("since")} for s in store.list_all()]


@router.get("/odm/notifications")
def odm_notifications() -> Any:
    """Últimos eventos recibidos de ODM por webhook (datasets publicados, altas/bajas
    de suscripción). Telemetría local en memoria."""
    from app import subscriptions_store as store
    return store.list_events()
