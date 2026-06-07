"""App del suscriptor ckan-jerez: homogeneizador/REST-apificador sobre ODM.

Sirve el receptor de webhook y un /health para el healthcheck del despliegue.
"""
from __future__ import annotations

import pathlib

from fastapi import FastAPI
from fastapi.responses import FileResponse

from api.admin import router as admin_router
from api.webhooks import router as webhooks_router
from app.config import get_settings

_SPA = pathlib.Path(__file__).resolve().parent / "static" / "index.html"

app = FastAPI(
    title="ckan-jerez",
    description="Homogeneizador/REST-apificador de datos abiertos de Jerez sobre OpenDataManager.",
)
app.include_router(webhooks_router)
app.include_router(admin_router)


@app.on_event("startup")
def _arrancar_sync() -> None:
    """Sincronización continua con ODM (idempotente). AUTO_BOOTSTRAP=0 la apaga."""
    import os
    if os.getenv("AUTO_BOOTSTRAP", "1") == "1":
        from app.sync_state import start_background_sync
        start_background_sync()


@app.get("/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "service": "ckan-jerez", "ckan_configured": s.ckan_configured}


@app.get("/", include_in_schema=False)
def spa() -> FileResponse:
    """Panel de operador (SPA con el look & feel de ODM)."""
    return FileResponse(_SPA)
