"""Estado local del consumidor: suscripciones y bitácora de eventos recibidos.

El operador gobierna las suscripciones en ODM; ODM nos las empuja por webhook
(``suscripcion_activada`` / ``suscripcion_desactivada``). Aquí se persisten para
que la consola las muestre sin tirar de ODM. La bitácora de eventos es telemetría
en memoria (se pierde al reiniciar; no importa). Persistencia de suscripciones
best-effort en JSON; si el volumen no fuese escribible, queda en memoria.
"""
from __future__ import annotations

import json
import logging
import pathlib
import threading
from collections import deque
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

_PATH = pathlib.Path(__file__).resolve().parents[1] / "data" / "subscriptions.json"
_LOCK = threading.Lock()
_CACHE: dict | None = None  # {resourceId: {...}}
_EVENTS: deque = deque(maxlen=200)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load() -> dict:
    global _CACHE
    if _CACHE is None:
        try:
            _CACHE = json.loads(_PATH.read_text())
        except Exception:  # noqa: BLE001
            _CACHE = {}
    return _CACHE


def _save() -> None:
    try:
        _PATH.parent.mkdir(parents=True, exist_ok=True)
        _PATH.write_text(json.dumps(_CACHE, ensure_ascii=False, indent=2))
    except Exception as e:  # noqa: BLE001
        logger.warning("no se pudo persistir subscriptions.json: %s", e)


def upsert(*, resource_id: str, subscription_id=None, resource_name=None,
           publisher=None, pinned_version=None, auto_upgrade=None) -> None:
    if not resource_id:
        return
    with _LOCK:
        d = _load()
        prev = d.get(resource_id, {})
        d[resource_id] = {
            "resourceId": resource_id,
            "subscriptionId": subscription_id or prev.get("subscriptionId"),
            "resourceName": resource_name or prev.get("resourceName"),
            "publisher": publisher if publisher is not None else prev.get("publisher"),
            "pinnedVersion": pinned_version if pinned_version is not None else prev.get("pinnedVersion"),
            "autoUpgrade": auto_upgrade if auto_upgrade is not None else prev.get("autoUpgrade"),
            "since": prev.get("since") or _now(),
        }
        _save()


def remove(*, resource_id=None, subscription_id=None) -> None:
    with _LOCK:
        d = _load()
        if resource_id and resource_id in d:
            d.pop(resource_id, None)
        elif subscription_id:
            for rid, v in list(d.items()):
                if v.get("subscriptionId") == subscription_id:
                    d.pop(rid, None)
        _save()


def clear() -> None:
    global _CACHE
    with _LOCK:
        _CACHE = {}
        _save()


def list_all() -> list:
    with _LOCK:
        vals = list(_load().values())
    return sorted(vals, key=lambda v: ((v.get("publisher") or ""),
                                       (v.get("resourceName") or v.get("resourceId") or "")))


def log_event(kind: str, **detail) -> None:
    _EVENTS.appendleft({"ts": _now(), "kind": kind, **detail})


def list_events() -> list:
    return list(_EVENTS)
