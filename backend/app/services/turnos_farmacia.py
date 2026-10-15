"""Farmacias de turno: importación del rol (docs/farmacias-de-turno.md).

En Bolivia el turno farmacéutico dura 24 horas: de las 08:00 del día indicado a las 08:00 del
día siguiente (DS 25235, art. 74), hora de La Paz (UTC-4, sin horario de verano). El rol viene
como un JSON (`backend/data/turnos_farmacia/*.json`) con las farmacias y, por día, cuáles dos
están de turno.

`importar(repo, data)` es IDEMPOTENTE: correrlo dos veces no duplica fichas ni turnos.

  * Farmacia con `slug`: ya está en URUKU. Se le completa `telefono` y `direccion` SÓLO si están
    vacíos; nada de lo cargado se pisa.
  * Farmacia sin `slug`: se busca la que creó una importación anterior (mismo nombre de ficha,
    misma ciudad, rubro `farmacia`) y, si no está, se crea con `repo.crear_comercio` (código,
    slug, rubro `farmacia`, `fuente='turnos'`, lat/lng, `ubicacion_aproximada`, teléfono,
    dirección y `nota_interna`).
  * Turnos: upsert por `(comercio_id, fecha)`; `inicio` = la fecha a las 08:00 de La Paz y
    `fin` = `inicio` + 24 h.

Antes de escribir nada se valida todo (ciudad, rubro, fichas con `slug`, nombres de los turnos):
si algo no cierra se levanta `ValueError` y la base queda como estaba.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import structlog
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.text import slug_unico, slugify
from app.db.repository import Repo
from app.services import calles_mapa

logger = structlog.get_logger()

#: Bolivia no tiene horario de verano: UTC-4 fijo alcanza (igual que `cargas.BOLIVIA`; no se usa
#: `zoneinfo` porque en Windows falta tzdata).
BOLIVIA = timezone(timedelta(hours=-4))
ZONA = "America/La_Paz"
RUBRO = "farmacia"
FUENTE = "turnos"


class _Turno(BaseModel):
    """Lo que dice el rol sobre cómo es el turno. Si no viene, rige la norma: 08:00 y 24 h."""
    model_config = ConfigDict(extra="ignore")

    hora_inicio: str = "08:00"
    duracion_horas: int = Field(24, ge=1, le=48)
    zona: str = ZONA

    @field_validator("hora_inicio")
    @classmethod
    def _hora(cls, v: str) -> str:
        try:
            datetime.strptime(v.strip(), "%H:%M")
        except ValueError as exc:
            raise ValueError("hora_inicio tiene que ser HH:MM") from exc
        return v.strip()

    @field_validator("zona")
    @classmethod
    def _zona(cls, v: str) -> str:
        if v != ZONA:
            raise ValueError(f"sólo se admite la zona {ZONA}")
        return v


class FarmaciaRol(BaseModel):
    model_config = ConfigDict(extra="ignore")

    nombre: str = Field(min_length=1, max_length=120)             # como figura en el rol
    nombre_ficha: str = Field(min_length=1, max_length=160)       # como se llama la ficha en URUKU
    direccion: str | None = Field(None, max_length=300)
    celular: str | None = Field(None, max_length=40)
    fijo: str | None = Field(None, max_length=40)
    nota_interna: str | None = Field(None, max_length=1000)
    slug: str | None = Field(None, max_length=160)                # ya está en URUKU
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)
    ubicacion_aproximada: bool = False


class DiaDeTurno(BaseModel):
    model_config = ConfigDict(extra="ignore")

    fecha: date
    farmacias: list[str] = Field(min_length=1, max_length=10)     # `nombre` de las farmacias


class RolDeTurnos(BaseModel):
    """El cuerpo de la importación: el JSON del rol."""
    model_config = ConfigDict(extra="ignore")

    ciudad: str = Field("bermejo", min_length=1, max_length=80)
    fuente: str | None = Field(None, max_length=300)
    turno: _Turno = Field(default_factory=_Turno)
    farmacias: list[FarmaciaRol] = Field(max_length=300)
    turnos: list[DiaDeTurno] = Field(max_length=1500)


def _limpio(valor: str | None) -> str | None:
    v = (valor or "").strip()
    return v or None


def telefono_de(f: FarmaciaRol) -> str | None:
    """El teléfono tal como está en la fuente: el celular y, si no hay, el fijo. Sin prefijos
    ni suponer que es WhatsApp."""
    return _limpio(f.celular) or _limpio(f.fijo)


def ventana(fecha: date, turno: _Turno | None = None) -> tuple[str, str]:
    """`(inicio, fin)` en UTC (ISO 8601) del turno que arranca ese día: la fecha a las 08:00 de
    La Paz y 24 horas después. 15/10 → 15/10 12:00Z a 16/10 12:00Z."""
    t = turno or _Turno()
    h, m = (int(x) for x in t.hora_inicio.split(":"))
    inicio = datetime.combine(fecha, time(h, m), tzinfo=BOLIVIA)
    fin = inicio + timedelta(hours=t.duracion_horas)
    return inicio.astimezone(timezone.utc).isoformat(), fin.astimezone(timezone.utc).isoformat()


def _completar(repo: Repo, comercio: dict, f: FarmaciaRol) -> bool:
    """Completa `telefono` y `direccion` SÓLO si están vacíos. True si cambió algo."""
    patch: dict = {}
    if not _limpio(comercio.get("telefono")) and telefono_de(f):
        patch["telefono"] = telefono_de(f)
    if not _limpio(comercio.get("direccion")) and _limpio(f.direccion):
        patch["direccion"] = _limpio(f.direccion)
    if patch:
        repo.update_comercio(comercio["id"], patch, None)
    return bool(patch)


def importar(repo: Repo, data: dict | RolDeTurnos) -> dict:
    """Importa el rol. Devuelve `{creadas, actualizadas, turnos}`:

      * `creadas`: fichas de farmacia nuevas;
      * `actualizadas`: fichas que ya existían (las que traen `slug` y las que creó una
        importación anterior); de ellas, `datos_completados` son a las que se les llenó
        algún dato vacío;
      * `turnos`: turnos del rol guardados (upsert: dos corridas dejan los mismos).

    `ValueError` si el rol no cierra (ciudad inexistente, ficha con `slug` que no está, un
    turno que nombra una farmacia que no está en la lista). No escribe nada en ese caso.
    """
    rol = data if isinstance(data, RolDeTurnos) else RolDeTurnos.model_validate(data)

    ciudad_id = repo.get_ciudad_id(rol.ciudad)
    if not ciudad_id:
        raise ValueError(f"La ciudad «{rol.ciudad}» no existe")
    rubro_id = repo.get_rubro_id(RUBRO)
    if not rubro_id:
        raise ValueError(f"Falta el rubro «{RUBRO}»")

    por_nombre: dict[str, FarmaciaRol] = {}
    for f in rol.farmacias:
        if f.nombre in por_nombre:
            raise ValueError(f"La farmacia «{f.nombre}» está repetida en el rol")
        por_nombre[f.nombre] = f
    for dia in rol.turnos:
        for nombre in dia.farmacias:
            if nombre not in por_nombre:
                raise ValueError(f"El turno del {dia.fecha} nombra a «{nombre}», que no está en la lista de farmacias")

    # ---- 1) Todo lo que hay que BUSCAR, antes de escribir: si falta una ficha, no se toca nada.
    existentes: dict[str, dict] = {}
    faltan_slug: list[str] = []
    for f in rol.farmacias:
        comercio = None
        if f.slug:
            comercio = repo.get_comercio_por_slug(f.slug)
            if not comercio:
                faltan_slug.append(f.slug)
                continue
        else:
            comercio = repo.get_comercio_por_nombre(ciudad_id, f.nombre_ficha.strip(), rubro_id)
            if not comercio and (f.lat is None or f.lng is None):
                raise ValueError(f"«{f.nombre}» no tiene ficha ni coordenadas para crearla")
        if comercio:
            existentes[f.nombre] = comercio
    if faltan_slug:
        raise ValueError("No están en URUKU las fichas: " + ", ".join(faltan_slug))

    # ---- 2) Fichas: completar las que existen, crear las que faltan.
    creadas = actualizadas = completados = 0
    comercio_de: dict[str, str] = {}
    for f in rol.farmacias:
        comercio = existentes.get(f.nombre)
        if comercio:
            actualizadas += 1
            if _completar(repo, comercio, f):
                completados += 1
            comercio_de[f.nombre] = comercio["id"]
            continue
        nombre = f.nombre_ficha.strip()
        fila = {
            "slug": slug_unico(repo, slugify(nombre)),
            "nombre": nombre,
            "rubro_id": rubro_id,
            "ciudad_id": ciudad_id,
            "modalidad": "minorista",
            "direccion": _limpio(f.direccion),
            "telefono": telefono_de(f),
            "lat": f.lat,
            "lng": f.lng,
            "ubicacion_aproximada": bool(f.ubicacion_aproximada),
            "nota_interna": _limpio(f.nota_interna),
            "plan": "gratis",
            "confiable": False,
            "verificado": False,
            "fuente": FUENTE,
        }
        nuevo = repo.crear_comercio(fila)
        repo.set_comercio_rubros(nuevo["id"], [rubro_id])
        comercio_de[f.nombre] = nuevo["id"]
        creadas += 1
    if creadas:
        calles_mapa.invalidar(ciudad_id)      # el mapa de calles cuenta estos comercios

    # ---- 3) Turnos: un upsert por (comercio_id, fecha).
    filas: dict[tuple[str, str], dict] = {}
    for dia in rol.turnos:
        inicio, fin = ventana(dia.fecha, rol.turno)
        for nombre in dia.farmacias:
            cid = comercio_de[nombre]
            filas[(cid, dia.fecha.isoformat())] = {
                "comercio_id": cid, "fecha": dia.fecha.isoformat(),
                "inicio": inicio, "fin": fin, "fuente": FUENTE,
            }
    turnos = repo.upsert_turnos_farmacia(list(filas.values()))

    logger.info("turnos_farmacia.importados", ciudad=rol.ciudad, creadas=creadas,
                actualizadas=actualizadas, datos_completados=completados, turnos=turnos)
    return {"creadas": creadas, "actualizadas": actualizadas,
            "datos_completados": completados, "turnos": turnos}
