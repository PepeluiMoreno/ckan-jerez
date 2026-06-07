"""Tests de la política de variantes (el cerebro del piloto), sin ODM vivo."""
from __future__ import annotations
import pathlib, sys
ROOT = pathlib.Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from services.odm_client import VARIANTE_CENSO, VARIANTE_DATOS, VARIANTE_RECETA  # noqa: E402
from services.pilot import decidir_variante, planificar  # noqa: E402


def test_tabular_puro_va_a_datos():
    c = {"id": "1", "pathTemplate": "…/ejecucion/{year}.xlsx",
         "suggestedName": "Ejecución", "fileTypes": {"xlsx": 12}}
    assert decidir_variante(c) == VARIANTE_DATOS


def test_prosa_y_mixto_van_a_censo():
    prosa = {"id": "2", "pathTemplate": "…/resoluciones/{n}.pdf", "fileTypes": {"pdf": 30}}
    mixto = {"id": "3", "pathTemplate": "…/pila/{n}", "fileTypes": {"pdf": 10, "xlsx": 2}}
    assert decidir_variante(prosa) == VARIANTE_CENSO
    assert decidir_variante(mixto) == VARIANTE_CENSO


def test_token_de_receta_va_a_receta():
    pmp = {"id": "4", "pathTemplate": "…/Informe_PMP_{year}_{month}.xlsx",
           "suggestedName": "PMP", "fileTypes": {"xlsx": 12}}
    res = {"id": "5", "pathTemplate": "…/2._resultado_presupuestario….pdf", "fileTypes": {"pdf": 1}}
    assert decidir_variante(pmp) == VARIANTE_RECETA   # gana receta aunque sea xlsx
    assert decidir_variante(res) == VARIANTE_RECETA


def test_plan_adjunta_receta_y_marca_load():
    cands = [
        {"id": "a", "pathTemplate": "…/remanente_de_tesoreria.pdf", "suggestedName": "Remanente", "fileTypes": {"pdf": 1}},
        {"id": "b", "pathTemplate": "…/contratos/{year}.csv", "suggestedName": "Contratos", "fileTypes": {"csv": 3}},
        {"id": "c", "pathTemplate": "…/memorias/{n}.pdf", "suggestedName": "Memorias", "fileTypes": {"pdf": 9}},
    ]
    plan = {p["candidate_id"]: p for p in planificar(cands)}
    assert plan["a"]["variante"] == VARIANTE_RECETA and plan["a"]["receta"]
    assert plan["b"]["variante"] == VARIANTE_DATOS and plan["b"]["enable_load"]
    assert plan["c"]["variante"] == VARIANTE_CENSO and not plan["c"]["enable_load"]


if __name__ == "__main__":
    for fn in (test_tabular_puro_va_a_datos, test_prosa_y_mixto_van_a_censo,
               test_token_de_receta_va_a_receta, test_plan_adjunta_receta_y_marca_load):
        fn(); print(f"[OK] {fn.__name__}")
    print("TODO VERDE")
