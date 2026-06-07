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
    M_CREATE_RESOURCE, M_DELETE_RESOURCE, M_EXECUTE_RESOURCE, M_PROMOTE_CANDIDATE,
    Q_FETCHERS, Q_RESOURCE_CANDIDATES, build_resource_input,
    Q_MANIFEST_TEMPLATE, M_IMPORT_MANIFEST, M_CREATE_APPLICATION, M_SET_APP_WEBHOOK,
    M_SUBSCRIBE_RESOURCE, Q_RESOURCE_EXECUTIONS, Q_APP_NOTIFICATIONS,
    Q_APPLICATIONS, Q_RESOURCES, Q_DATASET_SUBSCRIPTIONS, M_UNSUBSCRIBE_RESOURCE,
)

_DOCS_SUSCRIPTOR = (
    Q_MANIFEST_TEMPLATE, M_IMPORT_MANIFEST, M_CREATE_APPLICATION, M_SET_APP_WEBHOOK,
    M_SUBSCRIBE_RESOURCE, Q_RESOURCE_EXECUTIONS, Q_APP_NOTIFICATIONS,
    Q_APPLICATIONS, Q_RESOURCES, Q_DATASET_SUBSCRIPTIONS, M_UNSUBSCRIBE_RESOURCE,
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


def test_documentos_discovery_validos_contra_el_esquema():
    for doc in (M_EXECUTE_RESOURCE, Q_RESOURCE_CANDIDATES, M_PROMOTE_CANDIDATE, M_DELETE_RESOURCE):
        errors = validate(SCHEMA, parse(doc))
        assert not errors, f"documento de discovery inválido contra el esquema de ODM: {errors}"


def test_promote_input_conforme_al_esquema():
    inp = {"name": "Jerez — PMP mensual", "targetTable": "jerez_pmp_mensual",
           "enableLoad": True, "loadMode": "upsert", "variant": "Extracción con receta"}
    assert not _coerce_errors(inp, "PromoteCandidateInput")


def test_documentos_suscriptor_validos_contra_el_esquema():
    for doc in _DOCS_SUSCRIPTOR:
        errors = validate(SCHEMA, parse(doc))
        assert not errors, f"documento de suscriptor inválido contra el esquema de ODM: {errors}"


def test_create_application_input_conforme_al_esquema():
    inp = {"name": "ckan-jerez", "consumptionMode": "webhook",
           "subscribedProjects": [], "webhookUrl": "https://ckan-jerez/webhooks/odmgr"}
    assert not _coerce_errors(inp, "CreateApplicationInput")


if __name__ == "__main__":
    test_documentos_validos_contra_el_esquema_de_odm()
    print("[OK] Q_FETCHERS y M_CREATE_RESOURCE validan contra el esquema real de ODM")
    test_variables_create_resource_conformes_al_input()
    print("[OK] variables de createResource conformes a CreateResourceInput")
    test_documentos_discovery_validos_contra_el_esquema()
    print("[OK] discovery (executeResource, resourceCandidates, promoteCandidate, deleteResource) validan")
    test_promote_input_conforme_al_esquema()
    print("[OK] PromoteCandidateInput con variant conforme al esquema")
    test_documentos_suscriptor_validos_contra_el_esquema()
    print("[OK] documentos de suscriptor (manifiesto, application, suscripción, ejecuciones, entregas) validan")
    test_create_application_input_conforme_al_esquema()
    print("[OK] CreateApplicationInput conforme al esquema")
    print("TODO VERDE")
