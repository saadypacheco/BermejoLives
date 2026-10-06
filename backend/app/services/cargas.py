"""Cargas del día: qué cargó cada agente, cuándo y por dónde (docs/cargas-del-dia.md).

Todo puro: recibe las filas de `comercios` y devuelve diccionarios. No toca la
base ni el reloj, así se prueba sin nada armado.

La hora de una carga es `capturado_en` (la del celular, la que importa cuando se
cargó sin señal) y, si no hay, `created_at` (la de llegada al servidor). El día
es el de Bolivia.
"""
from __future__ import annotations

import math
from datetime import date, datetime, time, timedelta, timezone
from typing import Iterable

# Bolivia es UTC−4 todo el año: no tiene horario de verano, así que un offset
# fijo alcanza. No se usa `zoneinfo` a propósito: en Windows falta tzdata y el
# import fallaría en las máquinas de desarrollo.
BOLIVIA = timezone(timedelta(hours=-4))

# Más de 30 minutos entre dos cargas del mismo agente = otro tramo (paró).
CORTE_TRAMO = timedelta(minutes=30)
# Llegó al servidor más de 10 minutos después de la hora del celular = se cargó
# sin señal.
MARGEN_SUBIDA_TARDE = timedelta(minutes=10)

_RADIO_TIERRA_M = 6_371_000.0


# ───────────────────────────────────────────────────────────── fechas y horas
def parse_ts(valor) -> datetime | None:
    """Un timestamp ISO 8601 de PostgREST (o del celular) a datetime con zona.

    Acepta el sufijo `Z`. Sin zona se toma como UTC. Devuelve None si no es una
    fecha válida: quien llama decide qué hacer con eso.
    """
    if isinstance(valor, datetime):
        dt = valor
    elif isinstance(valor, str) and valor.strip():
        texto = valor.strip()
        if texto.endswith(("Z", "z")):
            texto = texto[:-1] + "+00:00"
        try:
            dt = datetime.fromisoformat(texto)
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def ahora_utc() -> datetime:
    return datetime.now(timezone.utc)


def hoy_bolivia(ahora: datetime | None = None) -> date:
    return (ahora or ahora_utc()).astimezone(BOLIVIA).date()


def dia_bolivia(dt: datetime) -> date:
    """El día (calendario de Bolivia) al que pertenece un instante."""
    return dt.astimezone(BOLIVIA).date()


def parse_fecha(texto: str) -> date:
    """`AAAA-MM-DD` estricto. Lanza ValueError si no es una fecha real."""
    t = (texto or "").strip()
    if len(t) != 10 or t[4] != "-" or t[7] != "-":
        raise ValueError("formato")
    d = date.fromisoformat(t)
    # 9999-12-31 no tiene «día siguiente» y el cálculo de límites desbordaba
    # (500). Nadie carga comercios fuera de este rango.
    if not 2020 <= d.year <= 2100:
        raise ValueError("fuera de rango")
    return d


def limites_dia_utc(fecha: date) -> tuple[datetime, datetime]:
    """[desde, hasta) en UTC de un día de Bolivia: de las 00:00 a las 24:00 (−4)."""
    desde = datetime.combine(fecha, time(0, 0), tzinfo=BOLIVIA).astimezone(timezone.utc)
    return desde, desde + timedelta(days=1)


def iso_z(dt: datetime) -> str:
    """`2026-10-06T04:00:00Z`: UTC sin `+`, que dentro de una URL se rompería."""
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def hhmm(dt: datetime) -> str:
    return dt.astimezone(BOLIVIA).strftime("%H:%M")


def capturado_valido(
    capturado: datetime | None, ahora: datetime | None = None
) -> bool:
    """Sólo se confía en la hora del celular si está entre hace 7 días y dentro
    de 5 minutos: un reloj mal puesto no puede mover una carga a otro mes."""
    if capturado is None:
        return False
    ahora = ahora or ahora_utc()
    return ahora - timedelta(days=7) <= capturado <= ahora + timedelta(minutes=5)


def hora_de_carga(c: dict) -> tuple[datetime | None, bool]:
    """(hora de la carga, si sale del celular). `capturado_en` si existe y se
    entiende; si no, `created_at`. (None, False) si no hay ninguna."""
    cap = parse_ts(c.get("capturado_en"))
    if cap is not None:
        return cap, True
    return parse_ts(c.get("created_at")), False


# ──────────────────────────────────────────────────────────────── distancias
def metros_entre(lat1, lng1, lat2, lng2) -> float | None:
    """Distancia en línea recta (haversine). None si falta algún punto."""
    if None in (lat1, lng1, lat2, lng2):
        return None
    try:
        f1, f2 = math.radians(float(lat1)), math.radians(float(lat2))
        df = f2 - f1
        dl = math.radians(float(lng2) - float(lng1))
    except (TypeError, ValueError):
        return None
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * _RADIO_TIERRA_M * math.asin(math.sqrt(a))


# ──────────────────────────────────────────────────────────────────── helpers
def _nombre_de(embebido) -> str | None:
    """`rubros(nombre)` / `ciudades(nombre)` llegan como dict (a veces lista)."""
    if isinstance(embebido, list):
        embebido = embebido[0] if embebido else None
    if isinstance(embebido, dict):
        return embebido.get("nombre")
    return None


def _minutos(delta: timedelta) -> int:
    return int(round(delta.total_seconds() / 60))


def _cargas_con_hora(comercios: Iterable[dict]) -> list[dict]:
    """Cada comercio con su hora ya resuelta; descarta los sin agente o sin hora."""
    salida = []
    for c in comercios:
        # En minúscula: el login de emergencia aceptaba «Agente@…» y lo guardaba
        # así, y el mismo agente salía partido en dos, cada uno con sus tramos.
        # Agrupar por minúscula arregla también lo que ya está cargado.
        agente = (c.get("cargado_por") or "").strip().lower()
        if not agente:
            continue
        hora, del_celular = hora_de_carga(c)
        if hora is None:
            continue
        salida.append({
            "c": c, "agente": agente, "hora": hora, "del_celular": del_celular,
            "llegada": parse_ts(c.get("created_at")),
        })
    return salida


def _por_agente_y_dia(comercios: Iterable[dict]) -> dict[tuple[date, str], list[dict]]:
    grupos: dict[tuple[date, str], list[dict]] = {}
    for x in _cargas_con_hora(comercios):
        grupos.setdefault((dia_bolivia(x["hora"]), x["agente"]), []).append(x)
    return grupos


def _tramos_de(cargas: list[dict]) -> list[list[dict]]:
    """Parte las cargas (ya ordenadas) en tramos: corte con más de 30 min."""
    tramos: list[list[dict]] = []
    for x in cargas:
        if tramos and x["hora"] - tramos[-1][-1]["hora"] <= CORTE_TRAMO:
            tramos[-1].append(x)
        else:
            tramos.append([x])
    return tramos


def _ordenadas(cargas: list[dict]) -> list[dict]:
    # Desempate estable: dos cargas en el mismo segundo salen siempre igual.
    return sorted(cargas, key=lambda x: (x["hora"], str(x["c"].get("id") or "")))


def _recorrido(tramos: list[list[dict]]) -> tuple[int, list[float | None]]:
    """(metros totales, metros desde el anterior de cada punto, en orden).

    Sólo suman las distancias DENTRO de un tramo: el salto entre tramos
    (almuerzo, otra zona) no es recorrido de trabajo. Por eso el primer punto
    de cada tramo no tiene distancia desde el anterior.
    """
    total = 0.0
    por_punto: list[float | None] = []
    for tramo in tramos:
        for i, x in enumerate(tramo):
            if i == 0:
                por_punto.append(None)
                continue
            a, b = tramo[i - 1]["c"], x["c"]
            m = metros_entre(a.get("lat"), a.get("lng"), b.get("lat"), b.get("lng"))
            por_punto.append(m)
            if m is not None:
                total += m
    return int(round(total)), por_punto


def _resumen(cargas: list[dict]) -> dict:
    """Lo común del día y del historial: comercios, desde/hasta, minutos, metros."""
    cargas = _ordenadas(cargas)
    tramos = _tramos_de(cargas)
    metros, por_punto = _recorrido(tramos)
    return {
        "cargas": cargas, "tramos": tramos, "metros": metros, "metros_por_punto": por_punto,
        "comercios": len(cargas),
        "desde": hhmm(cargas[0]["hora"]), "hasta": hhmm(cargas[-1]["hora"]),
        "minutos_trabajados": sum(_minutos(t[-1]["hora"] - t[0]["hora"]) for t in tramos),
    }


# ───────────────────────────────────────────────────────────────── el día
def detalle_dia(
    comercios: Iterable[dict], fecha: date, nombres: dict[str, str] | None = None
) -> dict:
    """El detalle de un día de Bolivia por agente, con el formato de la spec.

    `comercios` puede traer filas de otros días: sólo cuentan las que caen en
    `fecha` según su hora de carga. `nombres` = {email en minúscula: nombre}.
    """
    nombres = nombres or {}
    agentes = []
    for (dia, agente), cargas in sorted(_por_agente_y_dia(comercios).items(),
                                        key=lambda kv: kv[0][1].lower()):
        if dia != fecha:
            continue
        r = _resumen(cargas)
        puntos = []
        orden = 0
        metros_iter = iter(r["metros_por_punto"])
        for n_tramo, tramo in enumerate(r["tramos"], start=1):
            for x in tramo:
                orden += 1
                c = x["c"]
                m = next(metros_iter)
                previo = r["cargas"][orden - 2] if orden > 1 else None
                llegada = x["llegada"]
                tarde = bool(
                    x["del_celular"] and llegada is not None
                    and llegada - x["hora"] > MARGEN_SUBIDA_TARDE
                )
                puntos.append({
                    "orden": orden, "tramo": n_tramo,
                    "id": c.get("id"), "slug": c.get("slug"), "nombre": c.get("nombre"),
                    "lat": c.get("lat"), "lng": c.get("lng"),
                    "hora": hhmm(x["hora"]),
                    "hora_del_celular": x["del_celular"],
                    "subido_tarde": tarde,
                    "min_desde_anterior": _minutos(x["hora"] - previo["hora"]) if previo else None,
                    "m_desde_anterior": int(round(m)) if m is not None else None,
                    "foto": c.get("portada_thumb_url"),
                    "rubro": _nombre_de(c.get("rubros")),
                    "ciudad": _nombre_de(c.get("ciudades")),
                })
        por_hora: dict[str, int] = {}
        for x in r["cargas"]:
            h = x["hora"].astimezone(BOLIVIA).strftime("%H")
            por_hora[h] = por_hora.get(h, 0) + 1
        agentes.append({
            "agente": agente,
            "agente_nombre": nombres.get(agente.lower()),
            "comercios": r["comercios"],
            "desde": r["desde"], "hasta": r["hasta"],
            "minutos_trabajados": r["minutos_trabajados"],
            "metros": r["metros"],
            "tramos": [
                {
                    "n": n, "desde": hhmm(t[0]["hora"]), "hasta": hhmm(t[-1]["hora"]),
                    "minutos": _minutos(t[-1]["hora"] - t[0]["hora"]), "comercios": len(t),
                }
                for n, t in enumerate(r["tramos"], start=1)
            ],
            "por_hora": [{"hora": h, "comercios": n} for h, n in sorted(por_hora.items())],
            "puntos": puntos,
        })
    return {"fecha": fecha.isoformat(), "agentes": agentes}


# ─────────────────────────────────────────────────────────────── el historial
def historial(comercios: Iterable[dict], nombres: dict[str, str] | None = None) -> list[dict]:
    """Una fila por día y agente. Fecha descendente y, dentro del día, por agente."""
    nombres = nombres or {}
    items = []
    for (dia, agente), cargas in _por_agente_y_dia(comercios).items():
        r = _resumen(cargas)
        items.append({
            "fecha": dia.isoformat(), "agente": agente,
            "agente_nombre": nombres.get(agente.lower()),
            "comercios": r["comercios"], "desde": r["desde"], "hasta": r["hasta"],
            "minutos_trabajados": r["minutos_trabajados"],
            "tramos": len(r["tramos"]), "metros": r["metros"],
        })
    items.sort(key=lambda i: i["agente"].lower())
    items.sort(key=lambda i: i["fecha"], reverse=True)
    return items
