"""Homogeneización / REST-apificación.

Proyecta un dataset de ODM —sea cual sea su fetcher u organismo de origen— sobre
un *package* CKAN con metadatos **DCAT**, y lo publica de forma idempotente en un
CKAN. Esa salida uniforme es la que consumen los portales y cuadros de mando: el
consumidor ve siempre lo mismo, da igual cómo se cosechó el dato.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional, Protocol

import requests

_FORMAT_BY_EXT = {
    "jsonl": "JSONL", "json": "JSON", "csv": "CSV", "tsv": "TSV",
    "xlsx": "XLSX", "xls": "XLS", "ods": "ODS", "pdf": "PDF", "xml": "XML",
}
_MIME_BY_FORMAT = {
    "JSONL": "application/x-ndjson", "JSON": "application/json",
    "CSV": "text/csv", "TSV": "text/tab-separated-values",
    "XLSX": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "PDF": "application/pdf", "XML": "application/xml",
}


def slugify(text: str, *, maxlen: int = 100) -> str:
    # Translitera acentos y ñ a ASCII (á→a, ó→o, ñ→n) antes de slugificar, para
    # no producir slugs rotos como "informaci-n-econ-mica".
    ascii_text = (
        unicodedata.normalize("NFKD", text or "")
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    s = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return s[:maxlen].strip("-") or "dataset"


def _format_from_url(url: str) -> str:
    tail = url.rsplit("/", 1)[-1]
    ext = tail.rsplit(".", 1)[-1].lower() if "." in tail else ""
    return _FORMAT_BY_EXT.get(ext, "")


def apply_overrides(pkg: dict, overrides: Optional[dict]) -> dict:
    """Aplica overrides de mapeo por recurso sobre el package automático.

    El mapeo automático es el suelo; estos ajustes (organización real, licencia,
    título/notas, tags, grupos, extras) lo pisan. `name` NO es override: es la
    clave de idempotencia del upsert.
    """
    if not overrides:
        return pkg
    pkg = {**pkg}
    for k in ("title", "notes", "owner_org", "license_id", "author",
              "author_email", "maintainer", "maintainer_email", "url", "private"):
        if overrides.get(k) not in (None, ""):
            pkg[k] = overrides[k]
    if overrides.get("tags"):
        pkg["tags"] = [{"name": t} for t in overrides["tags"] if t]
    if overrides.get("groups"):
        pkg["groups"] = [{"name": g} for g in overrides["groups"] if g]
    extra_over = overrides.get("extras")
    if isinstance(extra_over, dict) and extra_over:
        merged = {e["key"]: e["value"] for e in pkg.get("extras", [])}
        merged.update(extra_over)
        pkg["extras"] = [{"key": k, "value": v} for k, v in merged.items()]
    return pkg


def to_ckan_package(dataset: dict, download_urls: Optional[dict] = None, *,
                    publisher: Optional[Any] = None,
                    overrides: Optional[dict] = None) -> dict:
    """Mapea un dataset de ODM a un package CKAN (DCAT). Función pura.

    - `dataset`: metadatos (resource_name, id, version, description, …).
    - `download_urls`: {clave: url} de las distribuciones (p. ej. {'data': '…jsonl'}).
    - `publisher`: dict {acronimo, nombre, …} o nombre suelto (DCAT publisher / owner_org).
    - `overrides`: ajustes de mapeo por recurso que pisan el mapeo automático.
    """
    download_urls = download_urls or {}
    title = dataset.get("resource_name") or dataset.get("name") or "Dataset"

    pub = publisher if publisher is not None else dataset.get("publisher")
    pub_nombre = pub.get("nombre") if isinstance(pub, dict) else (pub if isinstance(pub, str) else None)
    pub_acro = pub.get("acronimo") if isinstance(pub, dict) else None

    resources = []
    for clave, url in download_urls.items():
        if not url:
            continue
        fmt = _format_from_url(url) or ("JSONL" if clave == "data" else "")
        res: dict[str, Any] = {"name": clave, "url": url}
        if fmt:
            res["format"] = fmt
            if _MIME_BY_FORMAT.get(fmt):
                res["mimetype"] = _MIME_BY_FORMAT[fmt]
        resources.append(res)

    extras = [{"key": "source", "value": "OpenDataManager"}]
    if dataset.get("id"):
        extras.append({"key": "odm_dataset_id", "value": str(dataset["id"])})
    if dataset.get("version"):
        extras.append({"key": "version", "value": str(dataset["version"])})
    if pub_nombre:
        extras.append({"key": "dcat_publisher_name", "value": pub_nombre})

    pkg: dict[str, Any] = {
        "name": slugify(title),
        "title": title,
        "notes": dataset.get("description") or "",
        "resources": resources,
        "extras": extras,
        "tags": [],
    }
    if pub_acro:
        pkg["owner_org"] = slugify(pub_acro)
    return apply_overrides(pkg, overrides)


class CkanSink(Protocol):
    """Destino de publicación: upsert idempotente por package['name']."""
    def upsert_package(self, package: dict) -> dict: ...


class MemorySink:
    """Sink en memoria (tests / dev sin CKAN). Idempotente por package['name']."""
    def __init__(self) -> None:
        self.packages: dict[str, dict] = {}

    def upsert_package(self, package: dict) -> dict:
        action = "update" if package["name"] in self.packages else "create"
        self.packages[package["name"]] = package
        return {"name": package["name"], "action": action}


class HttpCkanSink:
    """Publica en un CKAN real por su Action API (idempotente por name)."""
    def __init__(self, base_url: str, api_token: str, *, timeout: int = 30) -> None:
        self.base = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers["Authorization"] = api_token

    def _post(self, action: str, payload: dict) -> dict:
        r = self.session.post(f"{self.base}/api/3/action/{action}",
                              json=payload, timeout=self.timeout)
        r.raise_for_status()
        return r.json()["result"]

    def upsert_package(self, package: dict) -> dict:
        show = self.session.get(f"{self.base}/api/3/action/package_show",
                                params={"id": package["name"]}, timeout=self.timeout)
        if show.status_code == 200 and show.json().get("success"):
            self._post("package_update", {**package, "id": package["name"]})
            return {"name": package["name"], "action": "update"}
        self._post("package_create", package)
        return {"name": package["name"], "action": "create"}


def publish_dataset(sink: CkanSink, dataset: dict, download_urls: Optional[dict] = None, *,
                    publisher: Optional[Any] = None, overrides: Optional[dict] = None) -> dict:
    """Homogeneiza y publica un dataset: mapea a CKAN/DCAT y hace upsert en el sink."""
    pkg = to_ckan_package(dataset, download_urls, publisher=publisher, overrides=overrides)
    return {"package": pkg, "result": sink.upsert_package(pkg)}
