"""Mapeo a destino CKAN, por recurso (overrides editables).

Trabajo del CLIENTE: el mapeo automático (services/ckan_publisher.to_ckan_package)
es el suelo; aquí se guardan, por resource_id, los ajustes que un operador quiere
fijar para ESE recurso en SU CKAN: organización real, licencia, título/notas,
tags y grupos. Si un recurso no tiene overrides, se publica con el mapeo
automático (fallback transparente).

Persistencia best-effort en JSON (como app/onboarding.py y app/pub_state.py).
"""
from __future__ import annotations

import json
import os
import pathlib
from datetime import datetime, timezone
from typing import Optional

_PATH = pathlib.Path(os.getenv("MAPPING_STATE_PATH", "/tmp/ckan_jerez_mapping.json"))

# Claves de override admitidas. `name` queda fuera a propósito: es la clave de
# idempotencia del upsert en CKAN y no debe cambiarse desde el mapeo.
SCALAR_KEYS = {
    "title", "notes", "owner_org", "license_id", "author", "author_email",
    "maintainer", "maintainer_email", "url", "private",
}
LIST_KEYS = {"tags", "groups"}      # listas de nombres
DICT_KEYS = {"extras"}              # {clave: valor}
ALLOWED = SCALAR_KEYS | LIST_KEYS | DICT_KEYS


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


def _clean(overrides: dict) -> dict:
    """Filtra a claves admitidas y descarta vacíos."""
    out: dict = {}
    for k, v in (overrides or {}).items():
        if k not in ALLOWED:
            continue
        if k in LIST_KEYS:
            v = [x for x in (v or []) if x]
            if v:
                out[k] = v
        elif k in DICT_KEYS:
            v = {kk: vv for kk, vv in (v or {}).items() if vv not in (None, "")}
            if v:
                out[k] = v
        elif v not in (None, ""):
            out[k] = v
    return out


def get(resource_id: str) -> dict:
    """Overrides de un recurso (vacío si no hay)."""
    return ((_read().get("mappings") or {}).get(resource_id) or {}).get("overrides", {})


def set(resource_id: str, overrides: dict) -> dict:
    data = _read()
    m = data.setdefault("mappings", {})
    clean = _clean(overrides)
    m[resource_id] = {"resource_id": resource_id, "overrides": clean, "updated_at": _now()}
    _write(data)
    return m[resource_id]


def delete(resource_id: str) -> bool:
    data = _read()
    m = data.get("mappings") or {}
    existed = resource_id in m
    m.pop(resource_id, None)
    data["mappings"] = m
    _write(data)
    return existed


def snapshot() -> dict:
    data = _read()
    items = list((data.get("mappings") or {}).values())
    items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return {"mappings": items, "count": len(items)}
