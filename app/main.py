"""App del suscriptor ckan-jerez: homogeneizador/REST-apificador sobre ODM.

Sirve el receptor de webhook y un /health para el healthcheck del despliegue.
"""
from __future__ import annotations

from fastapi import FastAPI

from api.webhooks import router as webhooks_router
from app.config import get_settings

app = FastAPI(
    title="ckan-jerez",
    description="Homogeneizador/REST-apificador de datos abiertos de Jerez sobre OpenDataManager.",
)
app.include_router(webhooks_router)


@app.get("/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "service": "ckan-jerez", "ckan_configured": s.ckan_configured}
