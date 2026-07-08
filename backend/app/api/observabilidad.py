"""Endpoints públicos para que el frontend reporte errores y performance."""
from fastapi import APIRouter
from pydantic import BaseModel

from app.services.observabilidad import registrar_error, registrar_perf

router = APIRouter()


class ErrorBody(BaseModel):
    mensaje: str
    stack: str | None = None
    ruta: str | None = None
    contexto: dict | None = None


class MetricaBody(BaseModel):
    ruta: str
    metrica: str
    valor_ms: float
    repetida: bool | None = None


@router.post("/errores")
def reportar_error(body: ErrorBody) -> dict:
    registrar_error("frontend", body.mensaje, body.stack, body.ruta, None, body.contexto)
    return {"ok": True}


@router.post("/metricas")
def reportar_metrica(body: MetricaBody) -> dict:
    registrar_perf("frontend", body.ruta, body.metrica, body.valor_ms, body.repetida)
    return {"ok": True}
