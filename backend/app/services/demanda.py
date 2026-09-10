"""Qué está buscando la gente en Bermejo, y qué no encuentra.

POR QUÉ ESTE ES EL PRIMERO DE LOS AGENTES
=========================================
Todos los demás necesitan datos que todavía no existen: catálogo, precios,
stock, horarios. Éste no. Las búsquedas del sitio se registran desde hace meses
con el término y cuántos resultados dio, así que el informe se puede calcular
hoy — **sin modelo de IA, sin Meta y sin catálogo**.

Y es, antes que un producto, el mejor argumento de venta que URUKU puede tener:

    "Veintiséis personas buscaron esto en Bermejo esta semana y no encontraron
     nada. Vos lo vendés."

Eso no lo puede decir ningún competidor, porque nadie más tiene medida la
demanda de la ciudad.

SE AGRUPA EN PYTHON Y NO EN SQL, A PROPÓSITO
============================================
Hacerlo con una función de la base habría obligado a escribir la misma lógica
dos veces —una en SQL y otra en el repositorio falso de los tests— y esas dos
copias divergen. Acá hay una sola, y se prueba de verdad. El volumen lo permite
de sobra: son unos miles de filas por semana en el peor caso.
"""
from __future__ import annotations

import unicodedata
from datetime import datetime, timedelta, timezone

import structlog

logger = structlog.get_logger()

# Menos de esto no es una búsqueda, es alguien tanteando el teclado.
_MIN_LARGO = 3


# La ñ y la ü NO son vocales con tilde: son letras distintas del español, y
# quitarles el signo cambia la palabra. "pañales" se convierte en "panales" y
# "año" en algo que no se le muestra a un comerciante.
#
# Por eso no se borra todo signo combinante: se borra salvo cuando lo que hay
# debajo es una n o una u, que son los dos casos en que el signo forma otra
# letra. Sin marcadores intermedios — un carácter de control metido en el
# medio del texto es invisible al leer el código y lo come cualquier editor.
_CON_SIGNO_PROPIO = {("n", "\u0303"), ("u", "\u0308")}


def normalizar(texto: str) -> str:
    """Sin tildes, sin mayúsculas, sin espacios de más — pero con ñ y ü.

    "Zapatillas", "zapatillas " y "ZAPATILLAS" son la misma demanda. Contarlas
    por separado parte el número en tres y hace que nada parezca importante.
    """
    descompuesto = unicodedata.normalize("NFD", (texto or "").strip().lower())

    salida: list[str] = []
    for c in descompuesto:
        if unicodedata.category(c) != "Mn":
            salida.append(c)
        elif salida and (salida[-1], c) in _CON_SIGNO_PROPIO:
            salida.append(c)          # la ñ y la ü se quedan enteras

    return " ".join(unicodedata.normalize("NFC", "".join(salida)).split())


def _es_tecleo(termino: str, veces: int, todos: dict[str, int]) -> bool:
    """¿Es el término alguien escribiendo, capturado a mitad de camino?

    El buscador registra mientras la persona tipea, así que una sola búsqueda de
    "zapatillas" deja también "zap", "zapa", "zapati"… Sin esto, el informe
    muestra "zap" como la demanda principal de Bermejo — y eso, mostrado a un
    comerciante, no vuelve a abrir la puerta.

    La regla: un término que es el COMIENZO de otro más largo y que no se buscó
    más veces que aquél, es el mismo tecleo.
    """
    return any(otro != termino and otro.startswith(termino) and veces_otro >= veces
               for otro, veces_otro in todos.items())


def informe(repo, dias: int = 7, limite: int = 40) -> dict:
    """Lo que se buscó, lo que no se encontró, y cuánto de cada cosa."""
    desde = (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()
    filas = repo.list_busquedas(desde)

    cuenta: dict[str, int] = {}
    sin_res: dict[str, int] = {}
    for f in filas:
        t = normalizar(f.get("query") or "")
        if len(t) < _MIN_LARGO:
            continue
        cuenta[t] = cuenta.get(t, 0) + 1
        if not (f.get("resultados") or 0):
            sin_res[t] = sin_res.get(t, 0) + 1

    reales = {t: n for t, n in cuenta.items() if not _es_tecleo(t, n, cuenta)}

    def _fila(t: str) -> dict:
        return {"termino": t, "veces": reales[t], "sin_resultado": sin_res.get(t, 0)}

    buscado = sorted((_fila(t) for t in reales), key=lambda x: -x["veces"])

    # Lo que no encontró nada es lo que vale: es demanda que hoy se va sin
    # comprar, y es lo único de este informe que se le puede llevar a un
    # comerciante como oportunidad.
    vacias = sorted((f for f in buscado if f["sin_resultado"]),
                    key=lambda x: -x["sin_resultado"])

    return {
        "dias": dias,
        "busquedas": len(filas),
        "terminos": len(reales),
        "sin_resultado": sum(sin_res.get(f["termino"], 0) for f in buscado),
        "top": buscado[:limite],
        "oportunidades": vacias[:limite],
        # El tecleo descartado se informa en vez de esconderse: si algún día es
        # la mitad de todo, quiere decir que el buscador está registrando de
        # más y hay que arreglarlo allá, no acá.
        "descartados_por_tecleo": len(cuenta) - len(reales),
    }


def frase_de_venta(inf: dict) -> str | None:
    """La línea para decirle a un comerciante. None si todavía no hay con qué.

    Devolver una frase armada con dos búsquedas sería peor que no devolver
    nada: se dice una vez, delante de alguien, y si el número es ridículo se
    pierde la conversación entera.
    """
    if not inf["oportunidades"]:
        return None
    mejor = inf["oportunidades"][0]
    if mejor["sin_resultado"] < 3:
        return None
    return (f"{mejor['sin_resultado']} personas buscaron «{mejor['termino']}» en "
            f"Bermejo en los últimos {inf['dias']} días y no encontraron nada.")
