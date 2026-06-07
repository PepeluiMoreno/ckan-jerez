"""Cliente GraphQL de OpenDataManager (ODM).

ckan-jerez habla con ODM solo por su frontera pública: se autentica en
`/api/auth/login` (cuenta de servicio → cookie de sesión) y opera contra
`/graphql`. DEFINE recursos (mutaciones) y CONSULTA datos (queries). No toca la BD
ni la red interna de ODM.

Autenticación (opción A): cuenta de servicio con rol de mínimo privilegio
(`recursos.crear`, `recursos.editar`, lectura). El cliente hace login de forma
perezosa y re-autentica ante un error de permiso/sesión. La migración a token de
servicio (Bearer) es opción B, pendiente en ODM.

Para el Portal de Transparencia de Jerez se usa el fetcher **Web Tree** y una de
sus variantes (presets): censo documental, extracción de datos o con receta.
"""
from __future__ import annotations

import json
import os
from typing import Any, Optional

import requests

WEBTREE_FETCHER_NAME = "Web Tree"
# Variantes (presets) del Web Tree, por `code`, tal y como las publica ODM:
VARIANTE_CENSO = "Censo documental"
VARIANTE_DATOS = "Extracción de datos"
VARIANTE_RECETA = "Extracción con receta"

# ── Documentos GraphQL (validados contra el esquema real de ODM) ─────────────
Q_FETCHERS = "query Fetchers { fetchers { id name presets { id code } } }"
M_CREATE_RESOURCE = (
    "mutation CrearRecurso($input: CreateResourceInput!) {"
    "  createResource(input: $input) {"
    "    id name fetcher { name } preset { code }"
    "  }"
    "}"
)

M_EXECUTE_RESOURCE = (
    "mutation Ejecutar($id: String!, $params: JSON) {"
    "  executeResource(id: $id, params: $params) {"
    "    success message resourceId executionId"
    "  }"
    "}"
)
Q_RESOURCE_CANDIDATES = (
    "query Candidatos($crawler: ID, $status: String) {"
    "  resourceCandidates(crawlerResourceId: $crawler, status: $status) {"
    "    id suggestedName pathTemplate fileTypes confidence status promotedResourceId"
    "  }"
    "}"
)
M_PROMOTE_CANDIDATE = (
    "mutation Promover($id: ID!, $input: PromoteCandidateInput!) {"
    "  promoteCandidate(id: $id, input: $input) { id name preset { code } }"
    "}"
)
M_DELETE_RESOURCE = (
    "mutation Borrar($id: String!, $hard: Boolean!) {"
    "  deleteResource(id: $id, hardDelete: $hard)"
    "}"
)

Q_MANIFEST_TEMPLATE = (
    "query Plantilla($fetcherCode: String!, $presetCode: String) {"
    "  manifestTemplate(fetcherCode: $fetcherCode, presetCode: $presetCode)"
    "}"
)
M_IMPORT_MANIFEST = (
    "mutation Importar($manifest: JSON!) { importManifest(manifest: $manifest) }"
)
M_CREATE_APPLICATION = (
    "mutation CrearApp($input: CreateApplicationInput!) {"
    "  createApplication(input: $input) {"
    "    id name active consumptionMode webhookUrl subscribedProjects"
    "  }"
    "}"
)
M_SET_APP_WEBHOOK = (
    "mutation Webhook($id: String!, $url: String!, $secret: String!) {"
    "  setApplicationWebhook(id: $id, webhookUrl: $url, webhookSecret: $secret) {"
    "    id name webhookUrl consumptionMode"
    "  }"
    "}"
)
M_SUBSCRIBE_RESOURCE = (
    "mutation Suscribir($appId: String!, $resourceId: String!, $pinned: String, $auto: String!) {"
    "  subscribeResource(applicationId: $appId, resourceId: $resourceId,"
    "                    pinnedVersion: $pinned, autoUpgrade: $auto) {"
    "    id applicationId resourceId pinnedVersion autoUpgrade currentVersion notifiedAt"
    "  }"
    "}"
)
Q_RESOURCE_EXECUTIONS = (
    "query Ejecuciones($resourceId: String) {"
    "  resourceExecutions(resourceId: $resourceId) {"
    "    id resourceId resourceName status startedAt completedAt"
    "    totalRecords recordsLoaded errorMessage"
    "  }"
    "}"
)
Q_APP_NOTIFICATIONS = (
    "query Entregas($applicationId: String) {"
    "  applicationNotifications(applicationId: $applicationId) {"
    "    id applicationId datasetId sentAt statusCode responseBody errorMessage"
    "  }"
    "}"
)

Q_APPLICATIONS = (
    "query Apps { applications { id name webhookUrl consumptionMode active } }"
)
Q_RESOURCES = (
    "query Recursos($activeOnly: Boolean!) {"
    "  resources(activeOnly: $activeOnly) { id name publisher publisherId }"
    "}"
)
Q_DATASET_SUBSCRIPTIONS = (
    "query Subs($appId: String, $resourceId: String) {"
    "  datasetSubscriptions(applicationId: $appId, resourceId: $resourceId) {"
    "    id applicationId resourceId autoUpgrade pinnedVersion currentVersion"
    "  }"
    "}"
)

_AUTH_HINTS = ("permis", "autoriz", "autenticad", "no autenticado", "sesión",
               "sesion", "forbidden", "unauthorized", "login")


def build_resource_input(
    *,
    name: str,
    fetcher_id: str,
    params: dict[str, Any],
    preset_id: Optional[str] = None,
    description: Optional[str] = None,
    publisher: Optional[str] = None,
    target_table: Optional[str] = None,
    schedule: Optional[str] = None,
    active: bool = True,
) -> dict:
    """Construye las variables de `createResource` (función pura, testeable sin red).

    `params` es {clave: valor}. Como `ResourceParamInput.value` es String, los
    valores no-cadena (listas/objetos, p. ej. el param `receta`) se serializan a JSON.
    """
    param_inputs = []
    for key, value in params.items():
        val = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        param_inputs.append({"key": key, "value": val})
    inp: dict[str, Any] = {"name": name, "fetcherId": fetcher_id,
                           "params": param_inputs, "active": active}
    if preset_id:
        inp["presetId"] = preset_id
    if description:
        inp["description"] = description
    if publisher:
        inp["publisher"] = publisher
    if target_table:
        inp["targetTable"] = target_table
    if schedule:
        inp["schedule"] = schedule
    return {"input": inp}


class OdmClient:
    """Cliente de la API de ODM: login por cuenta de servicio (cookie) + GraphQL."""

    def __init__(self, base_url: str, username: Optional[str] = None,
                 password: Optional[str] = None, graphql_path: str = "/graphql",
                 timeout: int = 30):
        self.base = base_url.rstrip("/")
        self.gql_url = self.base + graphql_path
        self.username = username
        self.password = password
        self.timeout = timeout
        self.session = requests.Session()
        self._authenticated = False

    @classmethod
    def from_env(cls) -> "OdmClient":
        return cls(os.environ["ODM_API_URL"], os.environ.get("ODM_USER"),
                   os.environ.get("ODM_PASSWORD"))

    # ── Auth (opción A) ──────────────────────────────────────────────────────
    def login(self) -> dict:
        if not (self.username and self.password):
            raise RuntimeError("Faltan credenciales del servicio (ODM_USER/ODM_PASSWORD)")
        r = self.session.post(f"{self.base}/api/auth/login",
                              json={"username": self.username, "password": self.password},
                              timeout=self.timeout)
        r.raise_for_status()
        me = r.json()
        self._authenticated = True
        return me

    def _ensure_auth(self) -> None:
        if not self._authenticated and self.username and self.password:
            self.login()

    @staticmethod
    def _looks_like_auth_error(errors: Any) -> bool:
        blob = json.dumps(errors, ensure_ascii=False).lower()
        return any(h in blob for h in _AUTH_HINTS)

    def execute(self, document: str, variables: Optional[dict] = None, _retry: bool = True) -> dict:
        self._ensure_auth()
        r = self.session.post(self.gql_url,
                              json={"query": document, "variables": variables or {}},
                              timeout=self.timeout)
        if r.status_code in (401, 403) and _retry and self.username:
            self._authenticated = False
            self.login()
            return self.execute(document, variables, _retry=False)
        r.raise_for_status()
        body = r.json()
        if body.get("errors"):
            if _retry and self.username and self._looks_like_auth_error(body["errors"]):
                self._authenticated = False
                self.login()
                return self.execute(document, variables, _retry=False)
            raise RuntimeError(f"GraphQL errors: {body['errors']}")
        return body["data"]

    # ── Operaciones ───────────────────────────────────────────────────────────
    def resolve_webtree(self, variante_code: Optional[str] = None) -> tuple[str, Optional[str]]:
        """Resuelve (fetcher_id del Web Tree, preset_id de la variante|None)."""
        data = self.execute(Q_FETCHERS)
        wt = next((f for f in data["fetchers"] if f["name"] == WEBTREE_FETCHER_NAME), None)
        if not wt:
            raise RuntimeError(f"ODM no expone el fetcher '{WEBTREE_FETCHER_NAME}'")
        preset_id = None
        if variante_code:
            preset = next((p for p in (wt.get("presets") or []) if p["code"] == variante_code), None)
            if not preset:
                raise RuntimeError(f"El Web Tree no tiene la variante '{variante_code}'")
            preset_id = preset["id"]
        return wt["id"], preset_id

    def create_webtree_resource(self, *, name: str, params: dict,
                                variante: Optional[str] = None, **kw) -> dict:
        """Crea en ODM un recurso de tipo Web Tree con la variante indicada."""
        fetcher_id, preset_id = self.resolve_webtree(variante)
        variables = build_resource_input(name=name, fetcher_id=fetcher_id,
                                         params=params, preset_id=preset_id, **kw)
        return self.execute(M_CREATE_RESOURCE, variables)["createResource"]

    # ── Pilotaje del discovery (todo el ciclo Web Tree desde ckan-jerez) ──────
    def execute_resource(self, resource_id: str, params: Optional[dict] = None) -> dict:
        """Ejecuta un recurso. En el crawler Web Tree, dispara el DISCOVERY
        (asíncrono en ODM): los candidatos se pueblan tras unos instantes; usa
        `resource_candidates` para leerlos (con reintentos si hace falta)."""
        return self.execute(M_EXECUTE_RESOURCE, {"id": resource_id, "params": params})["executeResource"]

    def resource_candidates(self, crawler_resource_id: Optional[str] = None,
                            status: Optional[str] = None) -> list[dict]:
        """Lista los candidatos descubiertos por un crawler (suggestedName,
        pathTemplate, fileTypes, confidence…) para decidir su variante."""
        data = self.execute(Q_RESOURCE_CANDIDATES,
                            {"crawler": crawler_resource_id, "status": status})
        return data["resourceCandidates"]

    def promote_candidate(self, candidate_id: str, *, name: str, target_table: str,
                          variante: Optional[str] = None, enable_load: bool = False,
                          load_mode: str = "upsert", schedule: Optional[str] = None) -> dict:
        """Promueve un candidato a recurso, eligiendo su VARIANTE (censo/datos/receta)."""
        inp: dict[str, Any] = {"name": name, "targetTable": target_table,
                               "enableLoad": enable_load, "loadMode": load_mode}
        if variante:
            inp["variant"] = variante
        if schedule:
            inp["schedule"] = schedule
        return self.execute(M_PROMOTE_CANDIDATE, {"id": candidate_id, "input": inp})["promoteCandidate"]

    def discard_candidate_resource(self, resource_id: str, hard: bool = False) -> bool:
        """Borra un recurso (p. ej. retirar los recursos Jerez heredados de ODM)."""
        return self.execute(M_DELETE_RESOURCE, {"id": resource_id, "hard": hard})["deleteResource"]

    def discover(self, crawler_resource_id: str, params: Optional[dict] = None) -> dict:
        """Pilota el discovery: ejecuta el crawler y devuelve {execution, candidates}.
        Como el discovery es asíncrono, `candidates` puede llegar vacío en la
        primera lectura; el llamador puede reconsultar `resource_candidates`."""
        execution = self.execute_resource(crawler_resource_id, params)
        candidates = self.resource_candidates(crawler_resource_id=crawler_resource_id)
        return {"execution": execution, "candidates": candidates}

    # ── Manifiestos (aprovisionamiento idempotente) ───────────────────────────
    def manifest_template(self, fetcher_code: str, preset_code: Optional[str] = None) -> dict:
        """Pide a ODM un manifiesto-plantilla (esqueleto) para un fetcher y, si se
        indica, una variante/preset. Es la base del asistente 'nueva fuente'."""
        return self.execute(Q_MANIFEST_TEMPLATE,
                            {"fetcherCode": fetcher_code, "presetCode": preset_code})["manifestTemplate"]

    def import_manifest(self, manifest: dict) -> dict:
        """Importa un manifiesto en ODM (upsert idempotente). Devuelve el resumen
        {ok, created, updated, skipped, conflicts, errors}."""
        return self.execute(M_IMPORT_MANIFEST, {"manifest": manifest})["importManifest"]

    # ── Identidad y suscripciones del suscriptor ──────────────────────────────
    def create_application(self, *, name: str, description: Optional[str] = None,
                           webhook_url: Optional[str] = None,
                           consumption_mode: str = "webhook",
                           subscribed_projects: Optional[list[str]] = None) -> dict:
        """Registra la Application de este suscriptor en ODM."""
        inp: dict[str, Any] = {"name": name, "consumptionMode": consumption_mode,
                               "subscribedProjects": subscribed_projects or []}
        if description is not None:
            inp["description"] = description
        if webhook_url is not None:
            inp["webhookUrl"] = webhook_url
        return self.execute(M_CREATE_APPLICATION, {"input": inp})["createApplication"]

    def set_application_webhook(self, application_id: str, webhook_url: str, webhook_secret: str) -> dict:
        """Registra el endpoint+secreto de webhook de esta Application en ODM."""
        return self.execute(M_SET_APP_WEBHOOK,
                            {"id": application_id, "url": webhook_url, "secret": webhook_secret})["setApplicationWebhook"]

    def subscribe_resource(self, *, application_id: str, resource_id: str,
                           auto_upgrade: str = "patch", pinned_version: Optional[str] = None) -> dict:
        """Suscribe la Application a un recurso (push vía webhook) con política de versión."""
        return self.execute(M_SUBSCRIBE_RESOURCE,
                            {"appId": application_id, "resourceId": resource_id,
                             "pinned": pinned_version, "auto": auto_upgrade})["subscribeResource"]

    # ── Observabilidad (refresco y entregas) ──────────────────────────────────
    def resource_executions(self, resource_id: Optional[str] = None) -> list[dict]:
        """Historial/estado de ejecuciones (refresco) de un recurso (o de todos)."""
        return self.execute(Q_RESOURCE_EXECUTIONS, {"resourceId": resource_id})["resourceExecutions"]

    def application_notifications(self, application_id: Optional[str] = None) -> list[dict]:
        """Auditoría de entregas de webhook a esta Application (sentAt, statusCode, error)."""
        return self.execute(Q_APP_NOTIFICATIONS, {"applicationId": application_id})["applicationNotifications"]

    # ── Resolución (para el bootstrap del suscriptor) ─────────────────────────
    def applications(self) -> list[dict]:
        """Lista las Applications (para encontrar la de este suscriptor por nombre)."""
        return self.execute(Q_APPLICATIONS)["applications"]

    def resources(self, active_only: bool = False) -> list[dict]:
        """Lista recursos (id, name, publisher) para resolver IDs por nombre."""
        return self.execute(Q_RESOURCES, {"activeOnly": active_only})["resources"]

    def dataset_subscriptions(self, application_id: Optional[str] = None,
                              resource_id: Optional[str] = None) -> list[dict]:
        """Lista suscripciones (para no resuscribir lo ya suscrito)."""
        return self.execute(Q_DATASET_SUBSCRIPTIONS,
                            {"appId": application_id, "resourceId": resource_id})["datasetSubscriptions"]

    def fetchers(self) -> list[dict]:
        """Lista fetchers con sus presets (para el asistente 'nueva fuente')."""
        return self.execute(Q_FETCHERS)["fetchers"]
