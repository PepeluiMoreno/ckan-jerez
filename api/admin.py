"""API HTTP del panel de operador de ckan-jerez (la consume la SPA).

Consola del SUSCRIPTOR: gestiona lo suyo (sus fuentes, su Application/webhook, su
flujo de datos), hablando con ODM por su API pública. Las acciones de escritura
deben quedar tras autenticación/VPN antes de exponer esto públicamente.
"""
from __future__ import annotations

import json
import logging
import os
import pathlib
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException

from app.config import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["admin"])

CATALOG_PATH = pathlib.Path(__file__).resolve().parents[1] / "data/odm_resources/jerez.json"
APP_NAME = "ckan-jerez"

_client = None


def _client_or_error():
    global _client
    if _client is None:
        from services.odm_client import OdmClient
        from app import onboarding
        s = get_settings()
        tok = onboarding.get_token()
        if tok:                       # opción B: token Bearer (alta aprobada)
            c = OdmClient(s.odm_api_url, token=tok)
        else:                         # opción A (legado): cuenta de servicio
            c = OdmClient.from_env()
            c.login()
        _client = c
    return _client


def _reset_client() -> None:
    global _client
    _client = None


def _odm(fn):
    """Ejecuta una llamada a ODM; 502 legible si falla (incluida auth/red)."""
    try:
        return fn(_client_or_error())
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning("ODM call failed: %s", e)
        raise HTTPException(status_code=502, detail=f"ODM no disponible o error: {e}")


def _catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text())


def _app_id(client) -> Optional[str]:
    app = next((a for a in client.applications() if a.get("name") == APP_NAME), None)
    return app["id"] if app else None


# ── Estado / metadatos ────────────────────────────────────────────────────────
@router.get("/version")
def version() -> dict:
    return {"version": (os.getenv("APP_VERSION") or "dev")[:7]}


@router.get("/system/info")
def system_info() -> dict:
    total = avail = 0
    try:
        with open("/proc/meminfo") as f:
            mem = {l.split(":")[0]: int(l.split()[1]) for l in f if ":" in l}
        total = mem.get("MemTotal", 0) // 1024
        avail = mem.get("MemAvailable", 0) // 1024
    except Exception:  # noqa: BLE001
        pass
    return {"ram_total_mb": total, "ram_available_mb": avail}


@router.get("/status")
def status() -> dict:
    s = get_settings()
    faltan = [k for k, v in (("PUBLIC_BASE_URL", s.public_base_url),
                             ("ODM_WEBHOOK_SECRET", s.odm_webhook_secret)) if not v]
    from app.sync_state import STATE as sync_state
    out = {"ckan_configured": s.ckan_configured, "odm": "unknown",
           "application": None, "application_name": None, "webhook_url": None,
           "config_missing": faltan, "sync": dict(sync_state)}
    try:
        c = _client_or_error()
        out["odm"] = "online"
        app = next((a for a in c.applications() if a.get("name") == APP_NAME), None)
        if app:
            out["application"] = app["id"]
            out["application_name"] = app.get("name")
            out["webhook_url"] = app.get("webhookUrl")
    except Exception as e:  # noqa: BLE001
        out["odm"] = "offline"
        out["error"] = str(e)
    return out


@router.get("/catalog")
def catalog() -> dict:
    return _catalog()


# ── Lecturas de ODM ───────────────────────────────────────────────────────────
@router.get("/odm/resources")
def odm_resources() -> Any:
    def _con_publisher(c):
        rs = c.resources()
        try:
            ents = {p["id"]: (p.get("nombre") or p.get("acronimo")) for p in c.publishers()}
        except Exception:  # noqa: BLE001
            ents = {}
        for r in rs:
            if not r.get("publisher") and r.get("publisherId"):
                r["publisher"] = ents.get(r["publisherId"]) or None
        return rs
    return _odm(_con_publisher)


@router.get("/odm/publishers")
def odm_publishers() -> Any:
    return _odm(lambda c: c.publishers())


@router.get("/odm/resource/manifest")
def odm_resource_manifest(resource_id: str) -> Any:
    """Export de un recurso (para pre-rellenar el asistente al clonar)."""
    return _odm(lambda c: c.resource_manifest(resource_id))


@router.get("/odm/fetchers")
def odm_fetchers() -> Any:
    return _odm(lambda c: c.fetchers())


@router.get("/odm/subscriptions")
def odm_subscriptions() -> Any:
    def _con_nombres(c):
        app_id = _app_id(c)
        if not app_id:
            return []                       # sin Application aún: nada nuestro que listar
        subs = c.dataset_subscriptions(application_id=app_id)
        nombres = {r["id"]: r.get("name") for r in c.resources()}
        for s in subs:
            s["resourceName"] = nombres.get(s.get("resourceId")) or s.get("resourceId")
        return subs
    return _odm(_con_nombres)


@router.get("/odm/executions")
def odm_executions(resource_id: Optional[str] = None) -> Any:
    return _odm(lambda c: c.resource_executions(resource_id))


@router.get("/odm/notifications")
def odm_notifications() -> Any:
    def _solo_nuestras(c):
        app_id = _app_id(c)
        return c.application_notifications(application_id=app_id) if app_id else []
    return _odm(_solo_nuestras)


@router.post("/odm/subscribe")
def subscribe(body: dict = Body(...)) -> Any:
    rid = body.get("resource_id")
    if not rid:
        raise HTTPException(status_code=400, detail="falta resource_id")
    def _sub(c):
        app_id = _app_id(c)
        if not app_id:
            raise HTTPException(status_code=400, detail=(
                "ckan-mgr aún no está registrada como Application en ODM. Completa la "
                "configuración (PUBLIC_BASE_URL, ODM_WEBHOOK_SECRET) y pulsa Sincronizar."))
        return c.subscribe_resource(application_id=app_id, resource_id=rid)
    return _odm(_sub)


@router.post("/odm/unsubscribe")
def unsubscribe(body: dict = Body(...)) -> Any:
    sid = body.get("subscription_id")
    if not sid:
        raise HTTPException(status_code=400, detail="falta subscription_id")
    return _odm(lambda c: {"ok": c.unsubscribe_resource(sid)})


@router.post("/odm/resource/delete")
def resource_delete(body: dict = Body(...)) -> Any:
    rid = body.get("resource_id")
    if not rid:
        raise HTTPException(status_code=400, detail="falta resource_id")
    hard = bool(body.get("hard", False))
    return _odm(lambda c: {"ok": c.delete_resource(rid, hard=hard)})


# ── Acciones (escritura) ──────────────────────────────────────────────────────
@router.post("/odm/manifest-template")
def manifest_template(body: dict = Body(...)) -> Any:
    return _odm(lambda c: c.manifest_template(body["fetcherCode"], body.get("presetCode")))


@router.post("/sources/new")
def new_source(body: dict = Body(...)) -> Any:
    """Asistente 'nueva fuente': recibe CAMPOS (no un manifiesto editado a pelo) y
    deja que provision_source componga el manifiesto: plantilla de ODM (fetcher+
    preset) + hechos del formulario. dry_run=true (defecto) devuelve el manifiesto
    para previsualizar; false lo importa (idempotente)."""
    from services.provisioning import provision_source
    fetcher = body.get("fetcher_code")
    name = (body.get("name") or "").strip()
    publisher = body.get("publisher") or {}
    if not fetcher or not name or not publisher.get("acronimo"):
        raise HTTPException(status_code=400, detail="faltan fetcher_code, name o publisher.acronimo")
    return _odm(lambda c: provision_source(
        c, fetcher_code=fetcher, preset_code=body.get("preset_code") or None,
        publisher=publisher, name=name, params=body.get("params") or {},
        schedule=(body.get("schedule") or "").strip() or None,
        dry_run=bool(body.get("dry_run", True))))


@router.post("/sources/provision")
def provision(body: dict = Body(default={})) -> Any:
    from services.provisioning import provision_catalog
    dry = bool(body.get("dry_run", True))
    return _odm(lambda c: provision_catalog(c, _catalog(), dry_run=dry))


@router.post("/odm/execute")
def execute(body: dict = Body(...)) -> Any:
    rid = body.get("resource_id")
    if not rid:
        raise HTTPException(status_code=400, detail="falta resource_id")
    return _odm(lambda c: c.execute_resource(rid))


@router.post("/bootstrap")
def do_bootstrap(body: dict = Body(default={})) -> Any:
    from services.bootstrap import bootstrap
    s = get_settings()
    dry = bool(body.get("dry_run", True))
    if not dry and (not s.webhook_url or not s.odm_webhook_secret):
        raise HTTPException(status_code=400, detail="faltan PUBLIC_BASE_URL y/o ODM_WEBHOOK_SECRET")
    return _odm(lambda c: bootstrap(c, catalog=_catalog(), app_name=APP_NAME,
                                    webhook_url=s.webhook_url, webhook_secret=s.odm_webhook_secret, dry_run=dry))


# ── Alta self-service como aplicación consumidora (flujo solicitud → token) ───

@router.get("/onboarding")
def onboarding_state() -> Any:
    """Estado del alta para el panel: valida contra ODM si la app sigue dada de
    alta (token vivo). Si ODM responde que no, des-registra; si no hay contacto,
    marca 'sin contacto' SIN des-registrar."""
    global _client
    from app import onboarding
    st = onboarding.state()
    if st["tiene_token"]:
        try:
            who = _client_or_error().whoami()   # username si el token sigue vivo
            if who:
                st["operativa"] = True
            else:
                onboarding.desregistrar()       # ODM dice que ya no estamos dados de alta
                _client = None
                st = onboarding.state()
                st["operativa"] = False
                st["desregistrada"] = True
        except Exception as e:  # noqa: BLE001 — ODM inaccesible: NO des-registrar
            st["operativa"] = False
            st["sin_contacto"] = True
            st["token_error"] = str(e)
    else:
        st["operativa"] = False
    st["app_name"] = APP_NAME
    return st


@router.post("/onboarding/solicitar")
def onboarding_solicitar(body: dict = Body(...)) -> Any:
    """Envía a ODM la solicitud de alta (mutación pública, sin token). Queda
    pendiente hasta que un admin de ODM la apruebe y emita el token."""
    from services.odm_client import OdmClient
    from app import onboarding
    s = get_settings()
    nombre = (body.get("nombre") or APP_NAME).strip()
    contacto = (body.get("contacto") or "").strip() or None
    proposito = (body.get("proposito") or "").strip() or None
    descripcion = (body.get("descripcion") or "").strip() or None
    persona_contacto = (body.get("persona_contacto") or body.get("personaContacto") or "").strip() or None
    email = (body.get("email") or "").strip() or None
    telefono = (body.get("telefono") or "").strip() or None
    github_url = (body.get("github_url") or body.get("githubUrl") or "").strip() or None
    faltan = [k for k, v in {"nombre": nombre, "descripcion": descripcion,
                             "persona_contacto": persona_contacto, "email": email,
                             "github_url": github_url}.items() if not v]
    if faltan:
        raise HTTPException(status_code=400, detail="Faltan campos obligatorios: " + ", ".join(faltan))
    try:
        sol = OdmClient(s.odm_api_url).crear_solicitud_ingreso(
            nombre=nombre, contacto=contacto, proposito=proposito,
            descripcion=descripcion, persona_contacto=persona_contacto, email=email,
            telefono=telefono, github_url=github_url,
            callback_url=(s.webhook_url or None), callback_secret=(s.odm_webhook_secret or None))
        onboarding.set_solicitud(sol)
        return sol
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"No se pudo enviar la solicitud: {e}")


@router.post("/onboarding/token")
def onboarding_token(body: dict = Body(...)) -> Any:
    """Guarda el token Bearer emitido por ODM al aprobar el alta, tras verificarlo."""
    from services.odm_client import OdmClient
    from app import onboarding
    s = get_settings()
    token = (body.get("token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Falta el token")
    try:
        OdmClient(s.odm_api_url, token=token).applications()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Token no válido o ODM no responde: {e}")
    onboarding.set_token(token)
    _reset_client()
    return {"ok": True, "operativa": True}


@router.post("/odm/propose")
def odm_propose(body: dict = Body(...)) -> Any:
    """Propone un recurso Web Tree a ODM. Como la petición va autenticada como
    aplicación, ODM lo crea en estado 'pendiente' de aprobación (gobernanza §11)."""
    name = (body.get("name") or "").strip()
    root_url = (body.get("root_url") or "").strip()
    variante = body.get("variante") or None
    descripcion = (body.get("descripcion") or "").strip() or None
    if not name or not root_url:
        raise HTTPException(status_code=400, detail="faltan name y root_url")
    params = {"root_url": root_url}
    return _odm(lambda c: c.create_webtree_resource(
        name=name, params=params, variante=variante, description=descripcion))
