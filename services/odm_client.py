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
