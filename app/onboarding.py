"""Estado de alta del suscriptor frente a ODM (flujo solicitud → token).

Persistimos en un fichero JSON (ruta configurable) lo mínimo para pilotar el
alta self-service desde el panel: la última solicitud enviada y el token Bearer
emitido por ODM al aprobarla. El token también puede venir fijado por entorno
(ODM_TOKEN) para despliegues; el introducido en runtime tiene prioridad y, para
que sobreviva a redespliegues, conviene moverlo luego al secreto ODM_TOKEN.
"""
from __future__ import annotations

import json
import os
import pathlib
from typing import Optional

_PATH = pathlib.Path(os.getenv("ONBOARDING_STATE_PATH", "/tmp/ckan_jerez_onboarding.json"))


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


def get_token() -> Optional[str]:
    """Token efectivo: el introducido en runtime o, si no, el del entorno."""
    return _read().get("token") or os.getenv("ODM_TOKEN") or None


def set_token(token: str, username: Optional[str] = None) -> None:
    data = _read()
    data["token"] = (token or "").strip()
    if username:
        data["app_username"] = username
    _write(data)


def set_solicitud(solicitud: dict) -> None:
    data = _read()
    data["solicitud"] = solicitud
    _write(data)


def record_solicitud_resuelta(estado: Optional[str], motivo: Optional[str] = None,
                              token: Optional[str] = None, username: Optional[str] = None) -> None:
    data = _read()
    sol = data.get("solicitud") or {}
    if estado is not None:
        sol["estado"] = estado
    if motivo is not None:
        sol["motivo"] = motivo
    data["solicitud"] = sol
    # Si ODM aprueba y entrega el token autogenerado, guardarlo → operativa sin
    # intervención manual (copiar/pegar).
    if estado == "aprobada" and token:
        data["token"] = (token or "").strip()
        if username:
            data["app_username"] = username
        data["token_origen"] = "auto"
    _write(data)


def add_evento(ev: dict) -> None:
    data = _read()
    evs = data.get("eventos") or []
    evs.insert(0, ev)
    data["eventos"] = evs[:20]
    _write(data)


def eventos() -> list:
    return _read().get("eventos") or []


def state() -> dict:
    """Estado para el panel (sin exponer el token en claro)."""
    data = _read()
    tok = get_token()
    return {
        "tiene_token": bool(tok),
        "token_origen": "runtime" if _read().get("token") else ("entorno" if os.getenv("ODM_TOKEN") else None),
        "app_username": data.get("app_username"),
        "solicitud": data.get("solicitud"),
        "eventos": data.get("eventos") or [],
    }
