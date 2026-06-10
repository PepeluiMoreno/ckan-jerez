"""Receptor del webhook de ODM.

POST /webhooks/odmgr
  - Verifica la firma HMAC-SHA256 (header X-ODM-Signature).
  - Delega en services/odmgr_sync.py, que publica homogéneo en CKAN.
"""
from __future__ import annotations

import json
import logging

from fastapi import APIRouter, Header, HTTPException, Request, status

from app.config import get_settings
from services.ckan_publisher import CkanSink, HttpCkanSink, MemorySink
from services.odmgr_sync import handle_notification, verify_hmac

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/webhooks", tags=["webhooks"])

_SINK: CkanSink | None = None


def get_sink() -> CkanSink:
    """Sink singleton: CKAN real si está configurado; si no, memoria (dev)."""
    global _SINK
    if _SINK is None:
        s = get_settings()
        if s.ckan_configured:
            _SINK = HttpCkanSink(s.ckan_url, s.ckan_api_token)
        else:
            logger.warning("CKAN no configurado: se usa MemorySink (no persiste).")
            _SINK = MemorySink()
    return _SINK


@router.post("/odmgr", status_code=status.HTTP_200_OK)
async def odmgr_webhook(
    request: Request,
    x_odm_signature: str = Header(..., alias="X-ODM-Signature"),
) -> dict:
    settings = get_settings()
    body = await request.body()
    if not settings.odm_webhook_secret or not verify_hmac(body, x_odm_signature, settings.odm_webhook_secret):
        logger.warning("webhook ODM: firma HMAC inválida")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid HMAC signature")
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid JSON: {exc}")
    # Eventos de gobernanza (push de ODM): no son datasets; se registran para el panel.
    evento = payload.get("evento") if isinstance(payload, dict) else None
    if evento in ("solicitud_resuelta", "recurso_resuelto"):
        from app import onboarding
        if evento == "solicitud_resuelta":
            onboarding.record_solicitud_resuelta(payload.get("estado"), payload.get("motivo"), token=payload.get("token"), username=payload.get("username"))
        else:
            onboarding.add_evento(payload)
        return {"ok": True, "evento": evento}
    return handle_notification(payload, sink=get_sink())
