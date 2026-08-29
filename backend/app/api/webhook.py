"""Webhook de WAHA: valida firma HMAC y dispara la ingesta."""
import asyncio
import hashlib
import hmac

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request

from app.core.config import settings
from app.db.repository import Repo, get_repo
from app.services import ingest

router = APIRouter()
logger = structlog.get_logger()


# WAHA firma con SHA-512 y lo declara en `X-Webhook-Hmac-Algorithm`. El backend
# validaba con SHA-256 fijo, así que NINGUNA firma podía coincidir — con la clave
# correcta o equivocada. El canal de ofertas no habría funcionado nunca, y el
# síntoma era el peor posible: todo configurado, nada entra, y del lado de URUKU
# ni un error. Se descubrió leyendo los registros de WAHA, que sí lo gritaba:
# "POST request failed: 401 · firma inválida".
#
# Ahora se usa el algoritmo que el emisor declara, con SHA-512 por defecto. La
# lista blanca importa: sin ella, cualquiera podría pedir un algoritmo débil en
# la cabecera y bajarle el piso a la validación.
_ALGORITMOS = {"sha512": hashlib.sha512, "sha256": hashlib.sha256}


def _valid_signature(body: bytes, signature: str | None, algoritmo: str | None = None) -> bool:
    if not settings.webhook_secret:
        # fail-OPEN solo en dev; en producción se rechaza si no hay secreto configurado
        return settings.environment != "production"
    if not signature:
        return False
    hash_fn = _ALGORITMOS.get((algoritmo or "sha512").strip().lower())
    if hash_fn is None:
        logger.warning("webhook.algoritmo_desconocido", algoritmo=algoritmo)
        return False
    expected = hmac.new(settings.webhook_secret.encode(), body, hash_fn).hexdigest()
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def webhook(
    request: Request,
    x_webhook_hmac: str | None = Header(default=None),
    x_webhook_hmac_algorithm: str | None = Header(default=None),
    # Por inyección, como el resto de la app: antes se resolvía adentro de
    # handle_message contra la base real, así que este endpoint no se podía
    # probar ni apuntar a otro repositorio.
    repo: Repo = Depends(get_repo),
) -> dict:
    body = await request.body()
    if not _valid_signature(body, x_webhook_hmac, x_webhook_hmac_algorithm):
        # El detalle NO dice qué falló (algoritmo, clave, cuerpo): a quien tenga
        # que arreglarlo le sobra con los registros, y a quien esté probando
        # firmas no hay que darle pistas.
        logger.warning("webhook.firma_invalida", algoritmo=x_webhook_hmac_algorithm,
                       tiene_firma=bool(x_webhook_hmac))
        raise HTTPException(status_code=401, detail="firma inválida")

    event = await request.json()
    kind = event.get("event")

    if kind in {"message", "message.any"}:
        try:
            result = await asyncio.to_thread(ingest.handle_message, event, repo)
        except ingest.IngestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, **result}

    if kind == "session.status":
        status = (event.get("payload") or {}).get("status")
        logger.info("bridge.status", status=status)
        return {"ok": True, "handled": "session.status"}

    return {"ok": True, "ignored": kind}
