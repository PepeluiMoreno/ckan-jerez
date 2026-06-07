"""Pilotaje del ciclo Web Tree de Jerez en ODM: discover → política → promote.

ckan-jerez decide la VARIANTE de cada candidato (el "cerebro" del cliente) y la
promueve por la API GraphQL de ODM. Política de Jerez:
  - el path/nombre casa un patrón de receta (PMP, remanente, resultado)
        → Extracción con receta (+ las capturas declarativas a aplicar)
  - formatos tabulares puros (xlsx/xls/csv/tsv/ods, sin prosa)
        → Extracción de datos
  - resto (prosa PDF, mixto, opaco)
        → Censo documental
"""
from __future__ import annotations

import json
import re
from typing import Any

from services.odm_client import (
    VARIANTE_CENSO, VARIANTE_DATOS, VARIANTE_RECETA, OdmClient,
)

TABULAR = {"xlsx", "xls", "csv", "tsv", "ods"}

# Conocimiento de Jerez: token de path → capturas de la receta (motor en ODM).
RECETA_DEFS: dict[str, list[dict]] = {
    "informe_pmp": [
        {"campo": "periodo_medio_pago_global", "etiqueta": "Periodo Medio de Pago Global",
         "tipo": "numero", "posicion": "derecha"},
    ],
    "remanente_de_tesoreria": [
        {"campo": "remanente_tesoreria_total", "etiqueta": "Remanente de Tesorer[ií]a Total",
         "tipo": "numero", "posicion": "derecha"},
        {"campo": "remanente_tesoreria_gastos_generales",
         "etiqueta": "Remanente de Tesorer[ií]a para Gastos Generales",
         "tipo": "numero", "posicion": "derecha"},
    ],
    "resultado_presupuestario": [
        {"campo": "resultado_presupuestario_ajustado", "etiqueta": "Resultado Presupuestario Ajustado",
         "tipo": "numero", "posicion": "ultima"},
    ],
}


def _file_formats(candidate: dict) -> set[str]:
    ft = candidate.get("fileTypes") or {}
    if isinstance(ft, str):
        ft = json.loads(ft or "{}")
    return {str(k).lower() for k in ft}


def _receta_token(candidate: dict) -> str | None:
    blob = f"{candidate.get('pathTemplate') or ''} {candidate.get('suggestedName') or ''}".lower()
    return next((tok for tok in RECETA_DEFS if tok in blob), None)


def decidir_variante(candidate: dict) -> str:
    if _receta_token(candidate):
        return VARIANTE_RECETA
    formats = _file_formats(candidate)
    if formats and formats <= TABULAR:
        return VARIANTE_DATOS
    return VARIANTE_CENSO


def _target_table(candidate: dict) -> str:
    base = candidate.get("suggestedName") or candidate.get("pathTemplate") or "recurso"
    slug = re.sub(r"[^a-z0-9]+", "_", base.lower()).strip("_")[:48] or "recurso"
    return f"jerez_{slug}"


def planificar(candidates: list[dict]) -> list[dict]:
    """Plan de promoción (sin tocar ODM): variante + target_table por candidato.
    Para la variante receta adjunta las capturas a aplicar (RECETA_DEFS)."""
    plan = []
    for c in candidates:
        variante = decidir_variante(c)
        item = {
            "candidate_id": c["id"],
            "suggested_name": c.get("suggestedName"),
            "variante": variante,
            "target_table": _target_table(c),
            "enable_load": variante != VARIANTE_CENSO,
        }
        if variante == VARIANTE_RECETA:
            item["receta"] = RECETA_DEFS[_receta_token(c)]
        plan.append(item)
    return plan


def _promovible(c: dict) -> bool:
    return not c.get("promotedResourceId") and (c.get("status") or "").lower() not in (
        "discarded", "promoted", "merged", "descartado")


def discover_and_promote(client: OdmClient, crawler_resource_id: str, *, dry_run: bool = True) -> dict:
    """discover → política → promote.

    Con dry_run=True (defecto, SEGURO) solo planifica y no escribe en ODM. Con
    dry_run=False promueve cada candidato con su variante. NOTA: aplicar las
    capturas de la variante receta (el param `receta`) requiere `updateResource`
    tras promover — pendiente en el cliente; el plan ya las incluye.
    """
    res = client.discover(crawler_resource_id)
    candidates = [c for c in res["candidates"] if _promovible(c)]
    plan = planificar(candidates)
    if dry_run:
        return {"execution": res["execution"], "plan": plan, "applied": False}
    promoted = []
    for p in plan:
        promoted.append(client.promote_candidate(
            p["candidate_id"], name=p["suggested_name"] or p["target_table"],
            target_table=p["target_table"], variante=p["variante"],
            enable_load=p["enable_load"]))
    return {"execution": res["execution"], "plan": plan, "applied": True, "promoted": promoted}
