"""Tests del bootstrap del suscriptor (sin ODM vivo) con un cliente falso que
registra las llamadas."""
from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from services.bootstrap import (  # noqa: E402
    bootstrap, ensure_application, ensure_subscriptions, resolve_resource_ids,
)

CATALOGO = {
    "publishers": {
        "AYTOJEREZ": {"nombre": "Ayuntamiento de Jerez", "nivel": "MUNICIPAL"},
        "DIPUCADIZ": {"nombre": "Diputación de Cádiz", "nivel": "PROVINCIAL"},
    },
    "sources": [
        {"name": "Portal (censo)", "publisher": "AYTOJEREZ", "fetcher": "Web Tree",
         "preset": "Censo documental", "params": {"root_url": "u"}},
        {"name": "Subvenciones", "publisher": "DIPUCADIZ", "fetcher": "File Download",
         "params": {"url": "v"}},
    ],
}


class _FakeClient:
    def __init__(self, *, apps=None, resources=None, subs=None):
        self._apps = list(apps or [])
        self._resources = list(resources or [])
        self._subs = list(subs or [])
        self.calls = {"create_application": 0, "set_webhook": [], "subscribed": [], "imported": 0}

    # provisioning
    def import_manifest(self, manifest):
        self.calls["imported"] += 1
        return {"ok": True, "created": len(manifest["resources"]), "updated": 0}

    # resolución
    def applications(self):
        return self._apps

    def create_application(self, *, name, webhook_url=None, consumption_mode="webhook"):
        self.calls["create_application"] += 1
        app = {"id": f"app-{name}", "name": name, "webhookUrl": webhook_url}
        self._apps.append(app)
        return app

    def set_application_webhook(self, application_id, webhook_url, webhook_secret):
        self.calls["set_webhook"].append((application_id, webhook_url, webhook_secret))
        return {"id": application_id, "webhookUrl": webhook_url}

    def resources(self, active_only=False):
        return self._resources

    def dataset_subscriptions(self, application_id=None, resource_id=None):
        return [s for s in self._subs if application_id in (None, s["applicationId"])]

    def subscribe_resource(self, *, application_id, resource_id, auto_upgrade="patch", pinned_version=None):
        self.calls["subscribed"].append(resource_id)
        sub = {"id": f"sub-{resource_id}", "applicationId": application_id, "resourceId": resource_id}
        self._subs.append(sub)
        return sub


def _resources_para(catalogo):
    out, i = [], 0
    for s in catalogo["sources"]:
        i += 1
        out.append({"id": f"r{i}", "name": s["name"],
                    "publisher": catalogo["publishers"][s["publisher"]]["nombre"]})
    return out


def test_ensure_application_find_or_create():
    cli = _FakeClient(apps=[{"id": "app-ckan-jerez", "name": "ckan-jerez"}])
    app = ensure_application(cli, name="ckan-jerez")
    assert app["id"] == "app-ckan-jerez" and cli.calls["create_application"] == 0   # ya existía
    cli2 = _FakeClient(apps=[])
    app2 = ensure_application(cli2, name="ckan-jerez", webhook_url="https://x/webhooks/odmgr")
    assert cli2.calls["create_application"] == 1 and app2["name"] == "ckan-jerez"


def test_resolve_resource_ids_por_publisher_y_nombre():
    cli = _FakeClient(resources=_resources_para(CATALOGO))
    ids = resolve_resource_ids(cli, CATALOGO)
    assert ids == {"Portal (censo)": "r1", "Subvenciones": "r2"}


def test_ensure_subscriptions_salta_existentes():
    cli = _FakeClient(subs=[{"id": "s1", "applicationId": "app-1", "resourceId": "r1"}])
    nuevos = ensure_subscriptions(cli, "app-1", {"Portal (censo)": "r1", "Subvenciones": "r2"})
    assert nuevos == ["Subvenciones"] and cli.calls["subscribed"] == ["r2"]


def test_bootstrap_dry_run_no_escribe():
    cli = _FakeClient(resources=_resources_para(CATALOGO))
    out = bootstrap(cli, catalog=CATALOGO, app_name="ckan-jerez",
                    webhook_url="https://x/webhooks/odmgr", webhook_secret="s", dry_run=True)
    assert out["dry_run"] is True
    assert cli.calls["create_application"] == 0 and cli.calls["subscribed"] == [] and cli.calls["imported"] == 0
    assert len(out["manifests"]) == 2          # un manifiesto por publisher


def test_bootstrap_completo_cierra_el_lazo():
    cli = _FakeClient(apps=[], resources=_resources_para(CATALOGO), subs=[])
    out = bootstrap(cli, catalog=CATALOGO, app_name="ckan-jerez",
                    webhook_url="https://x/webhooks/odmgr", webhook_secret="s3cr3t")
    assert out["dry_run"] is False
    assert cli.calls["imported"] == 2                      # un import por publisher
    assert cli.calls["create_application"] == 1
    assert cli.calls["set_webhook"] == [("app-ckan-jerez", "https://x/webhooks/odmgr", "s3cr3t")]
    assert set(cli.calls["subscribed"]) == {"r1", "r2"}    # suscribe los dos recursos
    assert out["resources_resolved"] == 2 and sorted(out["subscribed"]) == ["Portal (censo)", "Subvenciones"]


if __name__ == "__main__":
    import pytest as _pytest
    raise SystemExit(_pytest.main([__file__, "-q"]))


def test_adopcion_suscribe_recursos_heredados_del_publisher():
    catalogo = {
        "publishers": {"AJFRA": {"nombre": "Ayuntamiento de Jerez de la Frontera"}},
        "subscribe_publishers": ["AJFRA"],
        "sources": [
            {"name": "Jerez — PMP mensual (receta)", "publisher": "AJFRA",
             "fetcher": "Web Tree", "preset": "Extracción con receta", "params": {}},
        ],
    }
    recursos = [
        {"id": "r1", "name": "Jerez — PMP mensual (receta)", "publisher": "Ayuntamiento de Jerez de la Frontera"},
        {"id": "r2", "name": "Jerez — Deuda anual (heredado)", "publisher": "AJFRA"},       # por acrónimo
        {"id": "r3", "name": "Otro publisher", "publisher": "DIPUCADIZ"},
    ]
    cli = _FakeClient(resources=recursos)
    ids = resolve_resource_ids(cli, catalogo)
    assert ids == {"Jerez — PMP mensual (receta)": "r1",
                   "Jerez — Deuda anual (heredado)": "r2"}      # adopta heredado, ignora ajeno
