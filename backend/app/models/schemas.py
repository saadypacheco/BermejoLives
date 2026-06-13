"""Schemas de la API (snake_case, patrón Create/Update/Response — pattern KB)."""
from pydantic import BaseModel


class LoginBody(BaseModel):
    email: str
    password: str


class ModerarBody(BaseModel):
    estado: str               # 'aprobado' | 'rechazado' | 'cambios'
    motivo: str | None = None


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
    imagen_url: str | None = None
    tiktok_url: str | None = None
