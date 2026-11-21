"""Ayudas de prueba para las plantillas de las fotos con estilo URUKU (no son código de producción)."""
from app.services import fotos_estilo as fe, portada_diseno as pd


def armar_portada(foto: bytes, nombre: str, rubro: str | None, ciudad: str | None, pos: int | None,
                  *, mejorar: bool = True) -> bytes:
    """La portada de diseño (JPEG 1600 x 1000) del camino GRATIS armada con las funciones vivas: la foto de origen
    recortada (y mejorada, salvo `mejorar=False`, para mirar los colores tal cual) + `fe.plantilla_portada`. Sin lock ni disco."""
    if mejorar:
        img = fe._imagen_base("free", "cover", origen=foto, externa=None, pos=pos, estado={})
    else:
        img = pd.cubrir(pd._abrir(foto), pd.ANCHO, pd.ALTO, pos)
    return fe.plantilla_portada(img, nombre, rubro, ciudad)
