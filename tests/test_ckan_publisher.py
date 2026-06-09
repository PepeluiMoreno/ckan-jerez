"""Tests de la salida homogénea (sin CKAN ni ODM vivos): mapeo ODM→CKAN/DCAT,
sinks idempotentes y verificación HMAC del webhook."""
from __future__ import annotations

import hashlib
import hmac
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.ckan_publisher import (  # noqa: E402
    MemorySink, publish_dataset, slugify, to_ckan_package,
)
from services.odmgr_sync import handle_notification, verify_hmac  # noqa: E402


# --- mapeo ODM → CKAN/DCAT ----------------------------------------------------

def test_to_ckan_package_dcat():
    dataset = {"resource_name": "Jerez — Ejecución del gasto", "id": "abc-123",
               "version": "3", "description": "Series tabulares."}
    pkg = to_ckan_package(dataset, {"data": "https://odm/d/abc.jsonl"},
                          publisher={"acronimo": "AYTOJEREZ", "nombre": "Ayuntamiento de Jerez"})
    assert pkg["name"] == slugify("Jerez — Ejecución del gasto")
    assert pkg["title"] == "Jerez — Ejecución del gasto"
    assert pkg["owner_org"] == "aytojerez"
    res = pkg["resources"][0]
    assert res["url"].endswith(".jsonl") and res["format"] == "JSONL"
    assert res["mimetype"] == "application/x-ndjson"
    extras = {e["key"]: e["value"] for e in pkg["extras"]}
    assert extras["source"] == "OpenDataManager"
    assert extras["odm_dataset_id"] == "abc-123"
    assert extras["version"] == "3"
    assert extras["dcat_publisher_name"] == "Ayuntamiento de Jerez"


def test_to_ckan_package_detecta_formato_por_extension():
    pkg = to_ckan_package({"resource_name": "X"}, {"data": "https://o/x.csv", "raw": "https://o/y.pdf"})
    fmts = {r["name"]: r.get("format") for r in pkg["resources"]}
    assert fmts == {"data": "CSV", "raw": "PDF"}


# --- sink idempotente ---------------------------------------------------------

def test_memory_sink_idempotente():
    sink = MemorySink()
    pkg = {"name": "jerez-x", "title": "X"}
    assert sink.upsert_package(pkg)["action"] == "create"
    assert sink.upsert_package(pkg)["action"] == "update"
    assert list(sink.packages) == ["jerez-x"]


def test_publish_dataset_homogeneiza_y_upserta():
    sink = MemorySink()
    out = publish_dataset(sink, {"resource_name": "Padrón", "id": "p1"},
                          {"data": "https://o/p.jsonl"})
    assert out["result"]["action"] == "create"
    assert out["package"]["name"] in sink.packages


# --- ingesta del webhook ------------------------------------------------------

def test_verify_hmac_acepta_y_rechaza():
    secret = "s3cr3t"
    body = b'{"dataset":{"id":"1"}}'
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    assert verify_hmac(body, sig, secret) is True
    assert verify_hmac(body, "sha256=" + sig, secret) is True     # tolera prefijo
    assert verify_hmac(body, "deadbeef", secret) is False
    assert verify_hmac(body, sig, "otro-secreto") is False


def test_handle_notification_publica_homogeneo():
    sink = MemorySink()
    payload = {"dataset": {"resource_name": "Jerez — PMP", "id": "pmp-1", "version": "2",
                           "publisher": {"acronimo": "AYTOJEREZ", "nombre": "Ayto"}},
               "download_urls": {"data": "https://odm/pmp.jsonl"}}
    out = handle_notification(payload, sink=sink)
    assert out["action"] == "published" and out["result"] == "create"
    assert out["dataset_id"] == "pmp-1"
    assert out["package"] in sink.packages
    # reentrega del mismo dataset → update (idempotente)
    out2 = handle_notification(payload, sink=sink)
    assert out2["result"] == "update"


if __name__ == "__main__":
    import pytest as _pytest
    raise SystemExit(_pytest.main([__file__, "-q"]))


def test_slugify_translitera_acentos_y_enie():
    # Los acentos y la ñ se transliteran a ASCII (no se borran dejando guiones).
    assert slugify("Información Económica") == "informacion-economica"
    assert slugify("Subvenciones y Ñoño") == "subvenciones-y-nono"
    # Caso real de un recurso de Jerez.
    assert slugify("Jerez — A07-Información Económica — Ejecución del Gasto") \
        == "jerez-a07-informacion-economica-ejecucion-del-gasto"
