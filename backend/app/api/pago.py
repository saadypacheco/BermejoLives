"""Endpoints públicos del QR de cobro. El QR es un archivo del servidor
(services/pago_qr.py); acá sólo se lee, nunca se escribe."""
import structlog
from fastapi import APIRouter, HTTPException, Request, Response

from app.services import pago_qr

router = APIRouter()
logger = structlog.get_logger()


@router.get("/pago/qr/info")
def qr_info() -> dict:
    return pago_qr.info()


@router.get("/pago/qr/imagen")
def qr_imagen(request: Request) -> Response:
    qr = pago_qr.cargar()
    if qr is None:
        raise HTTPException(status_code=404, detail="No hay un QR de pago disponible")
    cabeceras = {"Cache-Control": "public, max-age=300", "ETag": f'"{qr.huella}"'}
    if request.headers.get("if-none-match", "").strip() in (f'"{qr.huella}"', qr.huella):
        return Response(status_code=304, headers=cabeceras)
    logger.info("pago.qr_servido", huella=qr.huella)
    return Response(content=qr.png, media_type="image/png", headers=cabeceras)
