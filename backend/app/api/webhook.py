"""Webhook de WhatsApp: valida la firma y dispara la ingesta.

Acepta los dos proveedores. WAHA firma con `X-Webhook-Hmac` (SHA-512 por
defecto) sobre el cuerpo; Meta firma con `X-Hub-Signature-256`, en SHA-256 y
con el prefijo "sha256=". Son claves distintas y cabeceras distintas, así que
se validan por separado: alcanza con que UNA sea válida, porque en un momento
dado sólo entra por un proveedor.
"""
import asyncio
import hashlib
import hmac

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import PlainTextResponse

from app.core.config import settings
from app.db.repository import Repo, get_repo
from app.services import ingest, mensajeria

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


@router.get("/webhook")
async def verificar_webhook(request: Request) -> Response:
    """La verificación que Meta pide UNA vez, al dar de alta la URL.

    Meta manda un GET con un desafío y espera que se le devuelva tal cual, en
    texto plano. Sin esto no se puede ni configurar el webhook de la API
    oficial — y el error que muestra la consola de Meta ("no se pudo validar la
    URL de devolución de llamada") no dice que falta un GET.
    """
    q = request.query_params
    if (q.get("hub.mode") == "subscribe"
            and q.get("hub.verify_token") == (settings.meta_verify_token or "")
            and settings.meta_verify_token):
        return PlainTextResponse(q.get("hub.challenge") or "")
    logger.warning("webhook.verificacion_rechazada", modo=q.get("hub.mode"))
    raise HTTPException(status_code=403, detail="verificación inválida")


def _firma_meta_ok(body: bytes, firma: str | None) -> bool:
    """Meta manda `sha256=<hex>` y firma con el App Secret, no con el secreto
    del webhook de WAHA."""
    secreto = settings.meta_app_secret
    if not secreto or not firma:
        return False
    esperado = "sha256=" + hmac.new(secreto.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperado, firma.strip())


@router.post("/webhook")
async def webhook(
    request: Request,
    x_webhook_hmac: str | None = Header(default=None),
    x_webhook_hmac_algorithm: str | None = Header(default=None),
    x_hub_signature_256: str | None = Header(default=None),
    # Por inyección, como el resto de la app: antes se resolvía adentro de
    # handle_message contra la base real, así que este endpoint no se podía
    # probar ni apuntar a otro repositorio.
    repo: Repo = Depends(get_repo),
) -> dict:
    body = await request.body()
    if not (_valid_signature(body, x_webhook_hmac, x_webhook_hmac_algorithm)
            or _firma_meta_ok(body, x_hub_signature_256)):
        # El detalle NO dice qué falló (algoritmo, clave, cuerpo): a quien tenga
        # que arreglarlo le sobra con los registros, y a quien esté probando
        # firmas no hay que darle pistas.
        logger.warning("webhook.firma_invalida", algoritmo=x_webhook_hmac_algorithm,
                       tiene_firma=bool(x_webhook_hmac))
        raise HTTPException(status_code=401, detail="firma inválida")

    crudo = await request.json()

    # Lo de Meta se traduce a la forma de WAHA acá, en la puerta: la ingesta
    # tiene todas las reglas del negocio y ninguna depende del proveedor.
    event = mensajeria.normalizar_entrante(crudo)
    if event is None:
        # Los avisos de entrega y lectura de Meta llegan por la misma URL. No
        # son mensajes y no tienen que ensuciar la bandeja.
        return {"ok": True, "ignored": "sin mensajes"}

    kind = event.get("event")

    if kind in {"message", "message.any"}:
        try:
            result = await asyncio.to_thread(ingest.handle_message, event, repo)
            # Una tanda de Meta puede traer varios mensajes. Procesarlos de a
            # uno es la diferencia entre atender todo y perder en silencio lo
            # que venga después del primero, los días de mucho movimiento.
            for extra in event.get("_extra") or []:
                await asyncio.to_thread(
                    ingest.handle_message,
                    {"event": "message", "session": event.get("session"), "payload": extra},
                    repo)
        except ingest.IngestError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True, **result}

    if kind == "session.status":
        status = (event.get("payload") or {}).get("status")
        # WAHA avisa cuando la sesión cambia de estado. Que se caiga es lo único
        # que, sin romper nada más, hace que se pierdan ofertas: va como ERROR
        # para que aparezca en cualquier filtro de registros.
        if status == "WORKING":
            logger.info("bridge.status", status=status)
        else:
            logger.error("wa_sesion.CAMBIO", status=status,
                         detalle="no entra ninguna oferta hasta que vuelva a WORKING")
        return {"ok": True, "handled": "session.status"}

    return {"ok": True, "ignored": kind}
