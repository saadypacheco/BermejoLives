"""Interruptores de lo que cuesta plata (docs/contenido-redes-tecnico.md §17.2).

COSTO CERO POR DEFECTO
======================
Todo lo que genera un gasto queda APAGADO hasta que el dueño lo prende, sabiendo que tiene costo. Hoy el único
servicio pago del contenido para redes es Gemini (`gemini_content`: los textos de las redes y del video y las
marcas de las fotos). Apagado, todo sigue funcionando con los textos fijos y la persona los completa en Revisión.

Sin fila en `cost_switches` = apagado. Un error al leer la base = apagado (ante la duda, no se gasta).

CACHÉ
=====
Cada consulta se recuerda 30 segundos en memoria del proceso (un render o el selector preguntan muchas veces).
`set` la limpia, así que quien prende o apaga lo ve al instante en este proceso. Con más de un proceso, el otro
se entera como mucho 30 segundos después. Es global a propósito: el repositorio se crea de nuevo en cada pedido.
"""
from __future__ import annotations

import time

import structlog

logger = structlog.get_logger()

GEMINI_CONTENT = "gemini_content"

#: Lo que se puede prender o apagar. Fijo en el código: lo devuelve la API para que el panel lo muestre.
CATALOGO: dict[str, dict] = {
    GEMINI_CONTENT: {
        "label": "Textos con Gemini",
        "what": "Propone los textos de las redes y del video y marca las fotos donde se ve un precio o un código",
        "cost": "Menos de US$ 0,01 por video con el modelo actual (0 si la clave de Gemini es del nivel gratis)",
        "off_means": "Se usan los textos fijos y los completás a mano en Revisión",
    },
}

CACHE_SEG = 30
#: key -> (valor, instante monotónico en que se leyó)
_cache: dict[str, tuple[bool, float]] = {}


def reiniciar_cache() -> None:
    _cache.clear()


def esta_prendido(crepo, key: str) -> bool:
    """¿El interruptor está prendido? Sin fila, clave desconocida o error de lectura: apagado."""
    if key not in CATALOGO:
        return False
    visto = _cache.get(key)
    if visto and time.monotonic() - visto[1] < CACHE_SEG:
        return visto[0]
    try:
        fila = next((f for f in crepo.list_cost_switches() if f.get("key") == key), None)
        valor = bool(fila and fila.get("enabled"))
    except Exception:  # noqa: BLE001
        logger.warning("cost_switch_lectura_fallo", key=key, exc_info=True)
        return False                         # no se recuerda: el próximo pedido vuelve a intentar
    _cache[key] = (valor, time.monotonic())
    return valor


def set(crepo, key: str, enabled: bool, actor: str) -> dict:  # noqa: A001 - nombre pedido por la spec (§17.2)
    """Prende o apaga un interruptor. `key` tiene que estar en `CATALOGO` (quien llama ya lo validó).
    Devuelve la fila guardada."""
    fila = crepo.upsert_cost_switch(key, bool(enabled), actor)
    _cache.pop(key, None)
    logger.info("cost_switch_changed", key=key, enabled=bool(enabled), actor=actor)
    return fila


def listar(crepo) -> list[dict]:
    """`[{key, label, what, cost, off_means, enabled, updated_by, updated_at}]` de todo el catálogo.
    Lo que no tiene fila sale apagado, sin autor ni fecha."""
    filas = {f["key"]: f for f in (crepo.list_cost_switches() or [])}
    out = []
    for key, info in CATALOGO.items():
        f = filas.get(key) or {}
        out.append({"key": key, **info, "enabled": bool(f.get("enabled")),
                    "updated_by": f.get("updated_by"), "updated_at": f.get("updated_at")})
    return out
