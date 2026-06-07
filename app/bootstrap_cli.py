"""CLI del bootstrap del suscriptor.

Uso (en el contenedor):
    bootstrap            # dry-run: previsualiza el provisioning, no escribe
    bootstrap --apply    # aplica: aprovisiona + Application/webhook + suscribe

Lee el catálogo de data/odm_resources/jerez.json y la config del entorno
(ODM_API_URL, ODM_USER/ODM_PASSWORD, ODM_WEBHOOK_SECRET, PUBLIC_BASE_URL).
"""
from __future__ import annotations

import json
import pathlib
import sys

CATALOG_PATH = pathlib.Path(__file__).resolve().parents[1] / "data/odm_resources/jerez.json"
APP_NAME = "ckan-jerez"


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    apply = "--apply" in argv
    catalog = json.loads(CATALOG_PATH.read_text())

    if not apply:
        from services.provisioning import build_manifests
        manifests = build_manifests(catalog)
        recursos = sum(len(m["resources"]) for m in manifests)
        print(f"[dry-run] {len(manifests)} manifiesto(s) por publisher; {recursos} recurso(s). "
              f"Ejecuta con --apply para aprovisionar, registrar el webhook y suscribir.")
        return 0

    from app.config import get_settings
    from services.bootstrap import bootstrap
    from services.odm_client import OdmClient

    s = get_settings()
    if not s.webhook_url:
        print("ERROR: falta PUBLIC_BASE_URL (para construir el webhook_url).", file=sys.stderr)
        return 2
    if not s.odm_webhook_secret:
        print("ERROR: falta ODM_WEBHOOK_SECRET.", file=sys.stderr)
        return 2

    client = OdmClient.from_env()
    client.login()
    out = bootstrap(client, catalog=catalog, app_name=APP_NAME,
                    webhook_url=s.webhook_url, webhook_secret=s.odm_webhook_secret)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
