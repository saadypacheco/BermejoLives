"""Medición del sitio: `POST /collect`, `POST /csp-report` y `GET /public/measurement-config`.

Spec: docs/estadisticas-v2.md §4.2. La lógica (límites, bots, validación, buffer) vive en
`services/site_metrics.py`; acá sólo está el HTTP. Los alias endurecidos (`/visita`, `/lead`,
`/busquedas/log`, `/lead/{id}/respondio`) siguen en `api/campo.py`.

`/collect` y `/csp-report` contestan 204 SIEMPRE que el pedido sea procesable (también si lo descartan: no se
le da a un bot un oráculo de qué se acepta), 413 si el cuerpo es demasiado grande y 429 si la IP pasa el
límite. Nunca 500: un fallo se loguea y se contesta 204.
"""
from __future__ import annotations

import structlog
from fastapi import APIRouter, HTTPException, Request, Response

from app.core.config import settings
from app.core.ip import ip_cliente
from app.services import site_metrics

router = APIRouter()
logger = structlog.get_logger()

SIN_CONTENIDO = {"Cache-Control": "no-store"}
MENSAJE_GRANDE = "El pedido es demasiado grande."
MENSAJE_LIMITE = "Demasiados pedidos."


async def _leer_cuerpo(request: Request, tope: int) -> bytes:
    """El cuerpo crudo (el beacon llega como `text/plain`), cortando apenas pasa del tope."""
    declarado = request.headers.get("content-length", "")
    if declarado.isdigit() and int(declarado) > tope:
        raise HTTPException(status_code=413, detail=MENSAJE_GRANDE)
    trozos: list[bytes] = []
    total = 0
    async for trozo in request.stream():
        total += len(trozo)
        if total > tope:
            raise HTTPException(status_code=413, detail=MENSAJE_GRANDE)
        trozos.append(trozo)
    return b"".join(trozos)


@router.post("/collect", status_code=204, response_class=Response)
async def collect(request: Request) -> Response:
    """Página vista o evento del sitio (lo manda `lib/medicion.ts` con `sendBeacon`, `text/plain`).

    Cuerpo (JSON, hasta 2 KB):
    `{t: 'pv'|'ev', path, session, device?, standalone?, first?, ref?, referrer?, city?, event?, detail?}`.
    - `pv` (página vista) → `visitas`. `ref` es el `?ref=`/`utm_source`; `referrer` es el host (o la URL) de
      donde vino, sólo en la primera página de la carga; `first` es true en la primera página de la sesión.
    - `ev` (evento) → `site_events`: `event` y `detail` tienen que estar en el catálogo cerrado.
    Se descarta sin decir por qué (204): User-Agent vacío o de bot, `Origin` ajeno o `Sec-Fetch-Site: cross-site`,
    ruta interna, evento fuera del catálogo, sesión mal formada."""
    try:
        estado = site_metrics.medidor.limitar("collect", ip_cliente(request))
        if estado == site_metrics.LIMITADO:
            raise HTTPException(status_code=429, detail=MENSAJE_LIMITE)
        if estado == site_metrics.LLENO or not site_metrics.pedido_de_request(request):
            return Response(status_code=204, headers=SIN_CONTENIDO)
        crudo = await _leer_cuerpo(request, site_metrics.MAX_BODY_BYTES)
        site_metrics.procesar_collect(crudo)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — medir no puede romper la página: nunca 500
        logger.warning("collect_failed", error=str(exc)[:200])
    return Response(status_code=204, headers=SIN_CONTENIDO)


@router.post("/csp-report", status_code=204, response_class=Response)
async def csp_report(request: Request) -> Response:
    """Reporte de violación de la CSP (`report-uri`). Se loguea `csp_violation` con la directiva y el host bloqueado;
    no se guarda la IP, ni la página, ni su query. 30 por minuto por IP (429). Se apaga con `CSP_REPORT_ENABLED=false`
    al pasar la CSP de Report-Only a enforce."""
    if not settings.csp_report_enabled:
        return Response(status_code=204, headers=SIN_CONTENIDO)
    try:
        estado = site_metrics.medidor.limitar("csp", ip_cliente(request))
        if estado == site_metrics.LIMITADO:
            raise HTTPException(status_code=429, detail=MENSAJE_LIMITE)
        if estado == site_metrics.LLENO:
            return Response(status_code=204, headers=SIN_CONTENIDO)
        crudo = await _leer_cuerpo(request, site_metrics.MAX_BODY_CSP)
        resumen = site_metrics.resumir_csp(crudo)
        if resumen:
            logger.warning("csp_violation", **resumen)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        logger.warning("csp_report_failed", error=str(exc)[:200])
    return Response(status_code=204, headers=SIN_CONTENIDO)


@router.get("/public/measurement-config")
def measurement_config(response: Response) -> dict:
    """Config pública de la medición: `{internal: true, umami: {script_url, website_id} | null}`.
    `umami` va siempre `null` en esta ronda (Umami no está desplegado). `Cache-Control: public, max-age=300`."""
    response.headers["Cache-Control"] = "public, max-age=300"
    return site_metrics.configuracion_publica()
