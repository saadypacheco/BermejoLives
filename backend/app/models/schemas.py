"""Schemas de la API (snake_case, patrón Create/Update/Response — pattern KB)."""
from pydantic import BaseModel, field_validator

from app.services import enlaces


class LoginBody(BaseModel):
    email: str
    password: str


class ModerarBody(BaseModel):
    estado: str               # 'aprobado' | 'rechazado' | 'cambios'
    motivo: str | None = None
    # Corregir el tipo al aprobar: "oferta" | "novedad" | "video".
    #
    # El clasificador acierta el caso común (precio -> oferta, "llegó
    # mercadería" -> novedad) pero no todos, y hasta hoy lo que decidía
    # quedaba fijo: el moderador aprobaba una novedad sabiendo que iba a
    # salir entre las ofertas, y no podía hacer nada.
    tipo: str | None = None


class RegistroBody(BaseModel):
    """Alta self-service de un comercio + su cuenta."""
    nombre: str
    email: str
    password: str
    whatsapp: str                         # E.164 sin '+': '5917xxxxxxx'
    plan: str = "gratis"                  # gratis | pro | premium
    modalidad: str = "mayorista"          # mayorista | minorista | ambos
    rubro_slug: str | None = None         # importadora | gastronomia | gomeria | servicios | ...
    zona_slug: str | None = None
    descripcion: str | None = None


class PublicarBody(BaseModel):
    """Lo que arma el chatbot in-site del comercio logueado."""
    tipo: str = "oferta"                  # oferta | video | novedad
    titulo: str | None = None
    descripcion: str | None = None
    precio: float | None = None
    moneda: str = "BOB"
    imagen_url: str | None = None         # sólo una foto subida a URUKU (B-02): se valida abajo
    tiktok_url: str | None = None         # sólo http(s) (enlaces.validar_red)
    descuento_pct: int | None = None      # 1..99, para el badge "-20%"
    vence_el: str | None = None           # "YYYY-MM-DD"

    @field_validator("imagen_url")
    @classmethod
    def _imagen_propia(cls, v):
        return enlaces.validar_imagen_propia(v, "La imagen de la publicación")

    @field_validator("tiktok_url")
    @classmethod
    def _enlace_tiktok(cls, v):
        return enlaces.validar_red(v, "El enlace de TikTok") or None
