"""Webhook de WAHA: valida firma HMAC y dispara la ingesta."""
import asyncio
import hashlib
import hmac

import structlog
from fastapi import APIRouter, Header, HTTPException, Request

from app.core.config import settings
from app.services import ingest

router = APIRouter()
logger = structlog.get_logger()


def _valid_signature(body: bytes, signature: str | None) -> bool:
    if not settings.webhook_secret:
        return True  # sin secreto en dev
    if not signature:
        return False
    expected = hmac.new(settings.webhook_secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def webhook(request: Request, x_webhook_hmac: str | None = Header(default=None)) -> dict:
    body = await request.body()
    if not _valid_signature(body, x_webhook_hmac):
        raise HTTPException(status_code=401, detail="firma inválida")

    event = await request.json()
    kind = event.get("event")

    if kind in {"message", "message.any"}:
        try:
            result = await asyncio.to_thread(ingest.handle_message, event)
        except ingest.IngestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, **result}

    if kind == "session.status":
        status = (event.get("payload") or {}).get("status")
        logger.info("bridge.status", status=status)
        return {"ok": True, "handled": "session.status"}

    return {"ok": True, "ignored": kind}
