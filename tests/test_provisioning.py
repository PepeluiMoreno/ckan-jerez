"""Tests del aprovisionamiento (sin ODM vivo): el catálogo heterogéneo
(multi-publisher, multi-fetcher) se compila a manifiestos por publisher, y el
asistente 'nueva fuente' rellena la plantilla de ODM."""
from __future__ import annotations

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.provisioning import (  # noqa: E402
    build_manifests, build_source_manifest, provision_catalog, provision_source,
)


class _FakeClient:
    """Cliente falso: registra llamadas, no toca red."""
    def __init__(self, template=None):
        self._template = template or {
            "odm_manifest_version": 1,
            "_plantilla": {"como_rellenar": ["..."]},
            "publisher": {"acronimo": "", "nombre": "", "nivel": "MUNICIPAL"},
            "resources": [{"name": "<x>", "fetcher": "Web Tree", "preset": "Censo documental",
                           "schedule": "<cron opcional>", "active": True,
                           "params": [{"key": "extract_mode", "value": "censo", "is_external": False}]}],
        }
        self.imported = []
    def manifest_template(self, fetcher_code, preset_code=None):
        return self._template
    def import_manifest(self, manifest):
        self.imported.append(manifest)
        return {"ok": True, "created": len(manifest["resources"]), "updated": 0}


# --- catálogo heterogéneo → manifiestos por publisher -------------------------

def test_build_manifests_agrupa_por_publisher_y_admite_varios_fetchers():
    catalogo = {
        "publishers": {
            "AYTOJEREZ": {"nombre": "Ayto. de Jerez", "nivel": "MUNICIPAL"},
            "DIPUCADIZ": {"nombre": "Diputación de Cádiz", "nivel": "PROVINCIAL"},
        },
        "sources": [
            {"name": "Portal (censo)", "publisher": "AYTOJEREZ", "fetcher": "Web Tree",
             "preset": "Censo documental", "params": {"root_url": "https://j/eco"}},
            {"name": "Padrón (API)", "publisher": "AYTOJEREZ", "fetcher": "API REST",
             "params": {"url": "https://j/api/padron"}},
            {"name": "Subvenciones Cádiz", "publisher": "DIPUCADIZ", "fetcher": "File Download",
             "params": {"url": "https://dipucadiz/subv.csv"}},
        ],
    }
    manifests = build_manifests(catalogo)
    by_pub = {m["publisher"]["acronimo"]: m for m in manifests}
    assert set(by_pub) == {"AYTOJEREZ", "DIPUCADIZ"}            # un manifiesto por publisher
    assert len(by_pub["AYTOJEREZ"]["resources"]) == 2          # dos recursos, dos fetchers
    fetchers = {r["fetcher"] for r in by_pub["AYTOJEREZ"]["resources"]}
    assert fetchers == {"Web Tree", "API REST"}
    assert by_pub["DIPUCADIZ"]["resources"][0]["fetcher"] == "File Download"
    # params como lista {key,value,is_external}; preset solo donde se declara
    censo = next(r for r in by_pub["AYTOJEREZ"]["resources"] if r["name"] == "Portal (censo)")
    assert censo["preset"] == "Censo documental"
    assert {p["key"] for p in censo["params"]} == {"root_url"}
    padron = next(r for r in by_pub["AYTOJEREZ"]["resources"] if r["name"] == "Padrón (API)")
    assert "preset" not in padron


def test_build_manifests_rechaza_publisher_desconocido_o_sin_fetcher():
    import pytest
    with pytest.raises(ValueError):
        build_manifests({"publishers": {"A": {}}, "sources": [
            {"name": "x", "publisher": "Z", "fetcher": "API REST"}]})
    with pytest.raises(ValueError):
        build_manifests({"publishers": {"A": {}}, "sources": [
            {"name": "x", "publisher": "A"}]})


def test_jerez_json_compila_a_manifiesto_por_publisher():
    catalogo = json.loads((ROOT / "data/odm_resources/jerez.json").read_text())
    manifests = build_manifests(catalogo)
    assert len(manifests) == 1
    m = manifests[0]
    assert m["odm_manifest_version"] == 1
    assert m["publisher"]["acronimo"] == "AYTOJEREZ"
    assert len(m["resources"]) == 3
    for r in m["resources"]:
        assert r["fetcher"] == "Web Tree" and isinstance(r["params"], list)
        assert "preset" in r


def test_provision_catalog_dry_run_no_importa():
    cli = _FakeClient()
    cat = {"publishers": {"A": {"nombre": "A"}},
           "sources": [{"name": "x", "publisher": "A", "fetcher": "API REST", "params": {"url": "u"}}]}
    out = provision_catalog(cli, cat, dry_run=True)
    assert out["imported"] is False and cli.imported == []
    assert out["manifests"][0]["publisher"]["acronimo"] == "A"


def test_provision_catalog_importa_un_manifiesto_por_publisher():
    cli = _FakeClient()
    cat = {"publishers": {"A": {"nombre": "A"}, "B": {"nombre": "B"}},
           "sources": [
               {"name": "x", "publisher": "A", "fetcher": "API REST", "params": {"url": "u"}},
               {"name": "y", "publisher": "B", "fetcher": "File Download", "params": {"url": "v"}},
           ]}
    out = provision_catalog(cli, cat)
    assert out["imported"] is True and len(cli.imported) == 2     # un import por publisher


# --- asistente 'nueva fuente' (plantilla de ODM + hechos) ---------------------

def test_build_source_manifest_rellena_limpia_y_funde_params():
    cli = _FakeClient()
    tpl = cli.manifest_template("Web Tree", "Censo documental")
    m = build_source_manifest(tpl, publisher={"acronimo": "AYTOJEREZ", "nombre": "Ayto"},
                              name="Mi fuente", params={"root_url": "https://j/eco"})
    assert "_plantilla" not in m                                  # se quita la ayuda
    assert m["publisher"]["acronimo"] == "AYTOJEREZ"
    r = m["resources"][0]
    assert r["name"] == "Mi fuente" and "schedule" not in r       # placeholder de cron descartado
    keys = {p["key"] for p in r["params"]}
    assert keys == {"extract_mode", "root_url"}                   # preset + propio del recurso


def test_provision_source_dry_run():
    cli = _FakeClient()
    out = provision_source(cli, fetcher_code="Web Tree", preset_code="Censo documental",
                           publisher={"acronimo": "AYTOJEREZ"}, name="X",
                           params={"root_url": "u"}, dry_run=True)
    assert out["imported"] is False and cli.imported == []


if __name__ == "__main__":
    import pytest as _pytest
    raise SystemExit(_pytest.main([__file__, "-q"]))
