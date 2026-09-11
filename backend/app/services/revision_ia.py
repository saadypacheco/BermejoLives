"""La IA revisa lo que entra, antes de que lo mire una persona.

LO QUE CAMBIA
=============
Hasta ahora la IA opinaba cuando el moderador apretaba un botón, y la opinión
vivía en el navegador — se perdía al recargar. Primero miraba una persona,
después opinaba la máquina: al revés.

Acá un proceso revisa cada publicación pendiente apenas entra y guarda el
veredicto en la fila. La cola le llega al moderador ordenada: lo rechazable y
lo dudoso arriba, lo limpio abajo. Con tres ofertas por día da igual; con
cincuenta es la diferencia entre revisar y no revisar.

LO QUE NO CAMBIA, Y ES A PROPÓSITO
==================================
La IA **sugiere**. Aprobar sigue siendo de una persona. Hay una perilla para
que lo de confianza alta se apruebe solo (`IA_AUTO_APROBAR_DESDE`), y arranca
en cero — apagada — por una razón concreta: una publicación aprobada va a la
cola de difusión, o sea al canal de WhatsApp y a las redes de la marca. Una
foto que ninguna persona miró, en el muro de URUKU, es un error que no se
deshace con un "rechazar" en el panel.

Y hay un límite honesto que conviene tener presente: la IA lee el TEXTO. Una
oferta que llegó como foto con "250 bs" de epígrafe le da muy poco para
opinar, y va a decir "dudoso" seguido. Eso está bien — dudoso es "que lo mire
alguien", no un error.
"""
from __future__ import annotations

from datetime import datetime, timezone

import structlog

from app.core.config import settings
from app.services import difusion
from app.services.clasificador import moderar_publicacion

logger = structlog.get_logger()

# El orden en que el moderador quiere verlas: primero lo que pide acción.
_PRIORIDAD = {"rechazar": 0, "dudoso": 1, None: 2, "aprobar": 3}


def revisar_pendientes(repo, limite: int = 10) -> dict:
    """Pide veredicto a la IA para lo pendiente que todavía no lo tiene."""
    filas = repo.publicaciones_sin_revision_ia(limite)
    hechos = {"revisadas": 0, "auto_aprobadas": 0, "fallidas": 0}

    for pub in filas:
        try:
            v = moderar_publicacion(pub.get("titulo") or "", pub.get("descripcion"))
        except Exception as exc:  # noqa: BLE001
            # `moderar_publicacion` ya no lanza —devuelve "dudoso"— pero el
            # worker no puede depender de eso: una excepción acá cortaría el
            # loop entero y dejaría la cola sin revisar hasta el próximo reinicio.
            logger.warning("revision_ia.error", pub=pub.get("id"), error=str(exc))
            hechos["fallidas"] += 1
            continue

        repo.guardar_veredicto_ia(pub["id"], v["veredicto"], v.get("motivo"),
                                  float(v.get("confianza") or 0))
        hechos["revisadas"] += 1

        if _auto_aprueba(v):
            repo.set_estado_publicacion(pub["id"], "aprobado", v.get("motivo"), "ia-auto")
            difusion.encolar(repo, pub["id"])
            hechos["auto_aprobadas"] += 1
            logger.info("revision_ia.auto_aprobada", pub=pub["id"],
                        confianza=v.get("confianza"))

    return hechos


def _auto_aprueba(v: dict) -> bool:
    """¿Se aprueba sola? Sólo si la perilla está encendida Y la IA dijo
    "aprobar" con confianza por encima del umbral. Con la perilla en cero —el
    valor por defecto— nunca."""
    umbral = settings.ia_auto_aprobar_desde
    if not umbral or umbral <= 0:
        return False
    return v.get("veredicto") == "aprobar" and float(v.get("confianza") or 0) >= umbral


def ordenar_para_moderar(items: list[dict]) -> list[dict]:
    """La cola como la quiere ver el moderador.

    Rechazable y dudoso arriba —es lo que pide una decisión—; lo que todavía
    no tiene veredicto en el medio; lo que la IA aprobaría, abajo, para
    despachar en tanda. Dentro de cada grupo, lo más nuevo primero.
    """
    return sorted(
        items,
        key=lambda p: (_PRIORIDAD.get(p.get("ia_veredicto"), 2),
                       -_ts(p.get("created_at"))),
    )


def _ts(valor) -> float:
    try:
        return datetime.fromisoformat(str(valor).replace("Z", "+00:00")).timestamp()
    except (TypeError, ValueError):
        return 0.0


def ahora_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
