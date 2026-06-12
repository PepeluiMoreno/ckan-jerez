"""Estado del pipeline de publicación, por recurso.

Lo que es trabajo del CLIENTE (no de ODM): qué versión hemos recibido de cada
recurso vs qué versión hemos publicado en CKAN, último error, reintentos
(recepciones fallidas consecutivas) e histórico de versiones. La suscripción en sí
(a qué me suscribo, auto_upgrade, pinned) vive en ODM; esto es "qué hago con el
recurso al llegarme".

Persistencia best-effort en un fichero JSON (como app/onboarding.py): debe
sobrevivir a redespliegues para poder detectar huecos de versión y dar salud del
receptor. Nunca rompe la recepción del webhook si el disco falla.
"""
from __future__ import annotations

import json
import os
import pathlib
from datetime import datetime, timezone
from typing import Optional

_PATH = pathlib.Path(os.getenv("PUB_STATE_PATH", "/tmp/ckan_jerez_pubstate.json"))
_HISTORY_MAX = 20


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read() -> dict:
    try:
        return json.loads(_PATH.read_text())
    except Exception:
        return {}


def _write(data: dict) -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    except Exception:
        pass


def _entry(data: dict, resource_id: str) -> dict:
    res = data.setdefault("resources", {})
    return res.setdefault(resource_id, {"resource_id": resource_id, "history": []})


def _push_history(e: dict, item: dict) -> None:
    h = e.setdefault("history", [])
    h.insert(0, item)
    del h[_HISTORY_MAX:]


def record_received(dataset: dict) -> None:
    """Llamar al entrar el webhook, antes de publicar."""
    rid = dataset.get("resource_id")
    if not rid:
        return
    data = _read()
    e = _entry(data, rid)
    e["resource_name"] = dataset.get("resource_name") or e.get("resource_name")
    e["publisher"] = dataset.get("publisher") or e.get("publisher")
    e["received_version"] = dataset.get("version")
    e["received_at"] = _now()
    e["received_dataset_id"] = dataset.get("id")
    _write(data)


def record_published(resource_id: Optional[str], version: Optional[str],
                     package: Optional[str], action: Optional[str]) -> None:
    """Publicación CKAN OK: limpia error, resetea reintentos, registra histórico."""
    if not resource_id:
        return
    data = _read()
    e = _entry(data, resource_id)
    e["published_version"] = version
    e["published_at"] = _now()
    e["package"] = package
    e["last_error"] = None
    e["retries"] = 0
    _push_history(e, {"at": _now(), "version": version, "action": action, "ok": True})
    _write(data)


def record_error(resource_id: Optional[str], version: Optional[str], error: str) -> None:
    """Publicación CKAN fallida: marca error e incrementa reintentos consecutivos."""
    if not resource_id:
        return
    data = _read()
    e = _entry(data, resource_id)
    e["last_error"] = error
    e["retries"] = int(e.get("retries") or 0) + 1
    _push_history(e, {"at": _now(), "version": version, "ok": False, "error": error})
    _write(data)


def _status(e: dict) -> str:
    if e.get("last_error"):
        return "error"
    rv, pv = e.get("received_version"), e.get("published_version")
    if pv is None:
        return "pendiente"
    if rv is not None and rv != pv:
        return "desfasado"
    return "ok"


def snapshot() -> dict:
    """Vista para el panel: lista de recursos con su estado de pipeline derivado."""
    data = _read()
    items = []
    for e in (data.get("resources") or {}).values():
        items.append({**e, "status": _status(e)})
    items.sort(key=lambda x: x.get("received_at") or "", reverse=True)
    return {"resources": items, "count": len(items)}
