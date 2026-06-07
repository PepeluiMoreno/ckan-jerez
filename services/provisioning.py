"""Asistente 'nueva fuente': construye un manifiesto a partir de la plantilla de
ODM (manifestTemplate) + los hechos de Jerez, y lo importa (idempotente).

Reparto motor/cliente: ODM aporta la PLANTILLA (verdad de fetcher+variante);
ckan-jerez aporta los HECHOS (publisher, nombre, params propios como root_url).
"""
from __future__ import annotations

import json
from typing import Any, Optional

from services.odm_client import OdmClient


def _as_value(v: Any) -> str:
    return v if isinstance(v, str) else json.dumps(v, ensure_ascii=False)


def build_source_manifest(template: dict, *, publisher: dict, name: str,
                          params: Optional[dict] = None, schedule: Optional[str] = None,
                          active: bool = True) -> dict:
    """Rellena la plantilla de ODM con los hechos del recurso y la deja importable.

    - `publisher`: dict con al menos 'acronimo' (y nombre/nivel/pais/portal_url).
    - `params`: valores propios del recurso (p. ej. {'root_url': ...}); se fusionan
      con los del preset que trae la plantilla (los del recurso ganan).
    - Quita el bloque de ayuda `_plantilla` y los placeholders sin rellenar.
    """
    manifest = {k: v for k, v in template.items() if k != "_plantilla"}

    pub = dict(manifest.get("publisher") or {})
    pub.update({k: v for k, v in publisher.items() if v is not None})
    if not pub.get("acronimo"):
        raise ValueError("El publisher necesita 'acronimo'.")
    manifest["publisher"] = pub

    resources = manifest.get("resources") or [{}]
    r = dict(resources[0])
    r["name"] = name
    r["active"] = active
    if schedule is not None:
        r["schedule"] = schedule
    elif isinstance(r.get("schedule"), str) and r["schedule"].startswith("<"):
        r.pop("schedule")                      # descartar el placeholder si no se da

    base = {p["key"]: dict(p) for p in (r.get("params") or [])}
    for k, v in (params or {}).items():
        base[k] = {"key": k, "value": _as_value(v),
                   "is_external": base.get(k, {}).get("is_external", False)}
    r["params"] = sorted(base.values(), key=lambda d: d["key"])
    manifest["resources"] = [r]
    return manifest


def provision_source(client: OdmClient, *, fetcher_code: str, preset_code: Optional[str],
                     publisher: dict, name: str, params: Optional[dict] = None,
                     schedule: Optional[str] = None, dry_run: bool = False) -> dict:
    """Flujo completo del asistente: plantilla → relleno → import (idempotente).

    Con dry_run=True devuelve el manifiesto sin importar (previsualización)."""
    template = client.manifest_template(fetcher_code, preset_code)
    manifest = build_source_manifest(template, publisher=publisher, name=name,
                                     params=params, schedule=schedule)
    if dry_run:
        return {"manifest": manifest, "imported": False}
    return {"manifest": manifest, "imported": True, "result": client.import_manifest(manifest)}


def build_manifests(catalog: dict) -> list[dict]:
    """Compila un catálogo declarativo en una LISTA de manifiestos, uno por
    publisher (el formato de manifiesto de ODM es por-publisher).

    El catálogo es HETEROGÉNEO en dos ejes: varios PUBLISHERS y varios FETCHERS.
    ckan-jerez es un homogeneizador: da igual de qué organismo o con qué
    tecnología venga cada fuente; aquí se declara y luego se publica uniforme.

    Forma del catálogo:
      {
        "publishers": { "<ACRONIMO>": {nombre, nivel, pais, portal_url}, ... },
        "sources": [ {name, publisher: "<ACRONIMO>", fetcher, preset?, schedule?, params{}}, ... ]
      }
    """
    publishers = catalog.get("publishers") or {}
    if not isinstance(publishers, dict) or not publishers:
        raise ValueError("El catálogo necesita 'publishers' (acrónimo → datos del organismo).")

    grupos: dict[str, list[dict]] = {}
    for s in (catalog.get("sources") or []):
        acro = s.get("publisher")
        if not acro:
            raise ValueError(f"Cada fuente necesita 'publisher' (acrónimo): {s.get('name')!r}")
        if acro not in publishers:
            raise ValueError(f"La fuente '{s.get('name')}' referencia un publisher desconocido '{acro}'.")
        if not s.get("name") or not s.get("fetcher"):
            raise ValueError(f"Cada fuente necesita 'name' y 'fetcher' (código): {s!r}")
        r: dict[str, Any] = {
            "name": s["name"],
            "fetcher": s["fetcher"],
            "active": bool(s.get("active", True)),
            "params": [
                {"key": k, "value": _as_value(v), "is_external": False}
                for k, v in sorted((s.get("params") or {}).items())
            ],
        }
        if s.get("preset"):
            r["preset"] = s["preset"]
        if s.get("schedule"):
            r["schedule"] = s["schedule"]
        grupos.setdefault(acro, []).append(r)

    manifests = []
    for acro, resources in grupos.items():
        pub = {"acronimo": acro,
               **{k: v for k, v in publishers[acro].items() if v is not None}}
        manifests.append({"odm_manifest_version": 1, "publisher": pub, "resources": resources})
    return manifests


def provision_catalog(client: OdmClient, catalog: dict, *, dry_run: bool = False) -> dict:
    """Aprovisiona TODO el catálogo en ODM: un import idempotente POR PUBLISHER
    (multi-publisher, multi-fetcher). dry_run=True devuelve los manifiestos sin
    importar (previsualización)."""
    manifests = build_manifests(catalog)
    if dry_run:
        return {"manifests": manifests, "imported": False}
    results = [client.import_manifest(m) for m in manifests]
    return {"manifests": manifests, "imported": True, "results": results}
