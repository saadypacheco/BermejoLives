"""Procesamiento de imágenes subidas (validar + reorientar + resize + recomprimir).

Lección KB fotos-resize: reorientar por EXIF, limitar a 1600px y JPEG 70.
Lanza ValueError si el archivo no es una imagen válida.
"""
from io import BytesIO


def procesar_imagen(data: bytes) -> bytes:
    from PIL import Image, ImageOps

    img = Image.open(BytesIO(data))
    img.verify()                       # valida que sea una imagen real
    img = Image.open(BytesIO(data))    # reabrir tras verify()
    img = ImageOps.exif_transpose(img).convert("RGB")
    img.thumbnail((1600, 1600))
    out = BytesIO()
    img.save(out, format="JPEG", quality=70, optimize=True)
    return out.getvalue()
