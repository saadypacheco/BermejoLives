"""¿Está abierto ahora? — el parser de horarios en texto libre, del lado del servidor.

Es el mismo de `frontend/lib/horario.ts`, portado línea por línea: el asistente
tiene que contestar "¿está abierto Rústico?" sin un navegador en el medio. Si
se cambia una regla acá, se cambia allá; los tests de los dos lados prueban las
mismas frases.

El horario del comercio NO tiene formato garantizado, así que es CONSERVADOR:
sólo dice "abierto" o "cerrado" cuando pudo interpretar días + horas con
confianza; ante cualquier duda devuelve "desconocido" y el que llama muestra el
texto crudo.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime

# Lunes=1 … Domingo=7 (así los rangos "vie a lun" se expanden bien).
_DIAS = {
    "lun": 1, "lunes": 1, "mar": 2, "martes": 2, "mie": 3, "miercoles": 3,
    "jue": 4, "jueves": 4, "vie": 5, "viernes": 5, "sab": 6, "sabado": 6,
    "dom": 7, "domingo": 7,
}


@dataclass
class EstadoHorario:
    estado: str                       # "abierto" | "cerrado" | "desconocido"
    cierra_en: int | None = None      # minutos hasta el cierre, si está abierto
    abre_en: int | None = None        # minutos hasta la próxima apertura, si está cerrado


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[–—]", "-", s)
    s = re.sub(r"\bhs?\b|\bhoras?\b", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _a_minutos(h: str, m: str | None) -> int | None:
    hh = int(h)
    mm = int(m) if m else 0
    if hh > 24 or mm > 59:
        return None
    return hh * 60 + mm


def _dias_de_texto(txt: str) -> set[int] | None:
    if re.search(r"todos|diario|lun a dom|lunes a domingo", txt):
        return {1, 2, 3, 4, 5, 6, 7}
    ordinales = [_DIAS[t] for t in re.findall(r"[a-z]+", txt) if t in _DIAS]
    if not ordinales:
        return None
    es_rango = len(ordinales) >= 2 and re.search(r"\ba\b|-", txt) is not None
    if es_rango:
        a, b = ordinales[0], ordinales[-1]
        if b < a:
            b += 7
        return {((d - 1) % 7) + 1 for d in range(a, b + 1)}
    return set(ordinales)


def _rangos_horarios(seg: str) -> list[tuple[int, int]]:
    s = re.sub(r"(\d{1,2}(?::\d{2})?)\s*a\s*(\d{1,2}(?::\d{2})?)", r"\1-\2", seg)
    out: list[tuple[int, int]] = []
    for m in re.finditer(r"(\d{1,2})(?:[:.](\d{2}))?\s*-\s*(\d{1,2})(?:[:.](\d{2}))?", s):
        desde = _a_minutos(m.group(1), m.group(2))
        hasta = _a_minutos(m.group(3), m.group(4))
        if desde is None or hasta is None:
            continue
        if hasta == 0:
            hasta = 24 * 60
        out.append((desde, hasta))
    return out


def abierto_ahora(horario: str | None, ahora: datetime) -> EstadoHorario:
    """Interpreta el horario libre y decide si está abierto en `ahora`."""
    if not horario or not horario.strip():
        return EstadoHorario("desconocido")
    texto = _norm(horario)
    segmentos = [x.strip() for x in re.split(r"[·;|\n]+|,(?=\s*[a-z]{3})", texto) if x.strip()]

    rangos: list[tuple[set[int], int, int]] = []
    for seg in segmentos:
        horas = _rangos_horarios(seg)
        if not horas:
            continue
        solo_dias = re.sub(r"\d{1,2}(?:[:.]\d{2})?", " ", seg)
        dias = _dias_de_texto(solo_dias) or {1, 2, 3, 4, 5, 6, 7}
        for desde, hasta in horas:
            if hasta > desde:
                rangos.append((dias, desde, hasta))
                continue
            # Cruza la medianoche ("22-4"): se parte en dos, y la madrugada
            # pertenece al día siguiente.
            rangos.append((dias, desde, 24 * 60))
            rangos.append(({(d % 7) + 1 for d in dias}, 0, hasta))

    if not rangos:
        return EstadoHorario("desconocido")

    ord_hoy = ahora.isoweekday()
    minutos = ahora.hour * 60 + ahora.minute

    cierra_en: int | None = None
    for dias, desde, hasta in rangos:
        if ord_hoy in dias and desde <= minutos < hasta:
            falta = hasta - minutos
            cierra_en = falta if cierra_en is None else min(cierra_en, falta)
    if cierra_en is not None:
        return EstadoHorario("abierto", cierra_en=cierra_en)

    abre_en: int | None = None
    for adelanto in range(7):
        dia = ((ord_hoy - 1 + adelanto) % 7) + 1
        for dias, desde, _hasta in rangos:
            if dia not in dias:
                continue
            falta = adelanto * 24 * 60 - minutos + desde
            if falta > 0:
                abre_en = falta if abre_en is None else min(abre_en, falta)
    return EstadoHorario("cerrado", abre_en=abre_en)


def _hora(ahora: datetime, minutos: int) -> str:
    total = (ahora.hour * 60 + ahora.minute + minutos) % (24 * 60)
    return f"{total // 60}:{total % 60:02d}"


def etiqueta(e: EstadoHorario, ahora: datetime) -> str | None:
    """Texto corto: "Abierto · cierra 19:00" / "Cerrado · abre 9:00"."""
    if e.estado == "desconocido":
        return None
    if e.estado == "abierto":
        if e.cierra_en is not None and e.cierra_en <= 120:
            return f"Abierto · cierra {_hora(ahora, e.cierra_en)}"
        return "Abierto ahora"
    if e.abre_en is not None and e.abre_en <= 24 * 60:
        return f"Cerrado · abre {_hora(ahora, e.abre_en)}"
    return "Cerrado"
