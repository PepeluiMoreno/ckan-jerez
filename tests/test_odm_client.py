"""Prueba de los servicios que conversan con ODM, sin ODM vivo: valida los
documentos GraphQL y las variables de createResource contra el ESQUEMA REAL de
ODM (volcado en tests/fixtures/odm_schema.graphql)."""
from __future__ import annotations

import json
import pathlib
import sys

from graphql import build_schema, parse, validate
from graphql.utilities import coerce_input_value

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.odm_client import (  # noqa: E402
    M_CREATE_RESOURCE, Q_FETCHERS, build_resource_input,
)

SCHEMA = build_schema((ROOT / "tests/fixtures/odm_schema.graphql").read_text())


def _coerce_errors(value, type_name):
    errs = []
    coerce_input_value(value, SCHEMA.get_type(type_name),
                       lambda path, val, err: errs.append(f"{list(path)}: {err}"))
    return errs


def test_documentos_validos_contra_el_esquema_de_odm():
    for doc in (Q_FETCHERS, M_CREATE_RESOURCE):
        errors = validate(SCHEMA, parse(doc))
        assert not errors, f"documento inválido contra el esquema de ODM: {errors}"


def test_variables_create_resource_conformes_al_input():
    variables = build_resource_input(
        name="X", fetcher_id="fid",
        params={"root_url": "u", "receta": [{"campo": "c", "etiqueta": "C"}]},
        preset_id="pid", publisher="P", target_table="t",
    )
    assert not _coerce_errors(variables["input"], "CreateResourceInput")
    receta = next(p for p in variables["input"]["params"] if p["key"] == "receta")
    assert receta["value"].startswith("["), "la receta debe viajar como JSON string"


def test_jerez_json_genera_inputs_validos_para_las_tres_variantes():
    decls = json.loads((ROOT / "data/odm_resources/jerez.json").read_text())
    assert len(decls) == 3
    for d in decls:
        variables = build_resource_input(
            name=d["name"], fetcher_id="fake", preset_id="fake",
            params=d["params"], publisher=d.get("publisher"),
            target_table=d.get("target_table"), description=d.get("description"),
        )
        errs = _coerce_errors(variables["input"], "CreateResourceInput")
        assert not errs, f"{d['name']}: {errs}"


if __name__ == "__main__":
    test_documentos_validos_contra_el_esquema_de_odm()
    print("[OK] Q_FETCHERS y M_CREATE_RESOURCE validan contra el esquema real de ODM")
    test_variables_create_resource_conformes_al_input()
    print("[OK] variables de createResource conformes a CreateResourceInput")
    test_jerez_json_genera_inputs_validos_para_las_tres_variantes()
    print("[OK] jerez.json genera inputs válidos para censo/datos/receta")
    print("TODO VERDE")
