"""Sincronización continua con ODM (self-healing).

El bootstrap es idempotente, así que en vez de un botón se converge en bucle:
al arrancar y periódicamente (6 h tras éxito, 5 min tras fallo — p. ej. si ODM
estaba caído al arrancar). El estado queda consultable para la consola.
"""
from __future__ import annotations

import json
import logging
import pathlib
import threading
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

STATE: dict = {"last_ok": None, "last_error": None, "last_attempt": None, "summary": None}
_OK_EVERY = 6 * 3600
_RETRY_EVERY = 300


def _attempt() -> bool:
    from app.config import get_settings
    from services.bootstrap import bootstrap
    from services.odm_client import OdmClient

    s = get_settings()
    STATE["last_attempt"] = datetime.now(timezone.utc).isoformat()
    if not s.webhook_url or not s.odm_webhook_secret:
        STATE["last_error"] = "faltan PUBLIC_BASE_URL y/o ODM_WEBHOOK_SECRET"
        return False
    try:
        catalog = json.loads((pathlib.Path(__file__).resolve().parents[1]
                              / "data/odm_resources/jerez.json").read_text())
        client = OdmClient.from_env()
        client.login()
        out = bootstrap(client, catalog=catalog, app_name="ckan-jerez",
                        webhook_url=s.webhook_url, webhook_secret=s.odm_webhook_secret)
        STATE["last_ok"] = datetime.now(timezone.utc).isoformat()
        STATE["last_error"] = None
        STATE["summary"] = {"subscribed_new": out.get("subscribed"),
                            "resources_resolved": out.get("resources_resolved")}
        logger.info("sync OK: %s", STATE["summary"])
        return True
    except Exception as e:  # noqa: BLE001
        STATE["last_error"] = str(e)
        logger.warning("sync FALLO: %s", e)
        return False


def _loop() -> None:
    time.sleep(5)                      # dejar arrancar al servidor
    while True:
        ok = _attempt()
        time.sleep(_OK_EVERY if ok else _RETRY_EVERY)


def start_background_sync() -> None:
    t = threading.Thread(target=_loop, name="odm-sync", daemon=True)
    t.start()
