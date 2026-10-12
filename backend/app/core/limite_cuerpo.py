"""Tope al tamaño del cuerpo de cada pedido, ANTES de que nadie lo lea.

POR QUÉ EXISTE
==============

FastAPI parsea el multipart de una ruta con `File(...)` antes de correr las
dependencias, o sea ANTES de autenticar, y sin ningún tope: 30 MB a
`/comercio/fotos` sin token se escribían a disco y recién después llegaba el
401. Con `Transfer-Encoding: chunked` ni siquiera hay `Content-Length` que mirar.
Los límites que cada ruta tiene (`len(data) > _MAX_FOTO_BYTES`) corren cuando el
archivo ya se leyó entero: sirven para el mensaje, no para proteger el disco.

QUÉ HACE
========

Un middleware ASGI PURO (no `BaseHTTPMiddleware`, que bufferiza el cuerpo y
rompe justo lo que se quiere evitar) que:

1. Si el pedido declara un `Content-Length` mayor al tope de la ruta, contesta
   413 sin leer nada.
2. Si no lo declara (chunked) o miente, cuenta los bytes REALES que van pasando
   por `receive`. Al pasar el tope le dice a la aplicación que el cliente se fue
   (`http.disconnect`), descarta lo que la aplicación conteste y contesta 413.

Así el parser del multipart se corta en el primer trozo que pasa el tope, y a
disco no llega más que lo que entra en ese trozo.

LOS TOPES
=========

Siguen a los de cada ruta (la constante de cada handler es la que da el mensaje
fino; ésta es la red de seguridad) más 256 KB de holgura multipart. Cualquier
ruta que no esté en la tabla tiene 2 MB: un JSON normal no se acerca. Una ruta
NUEVA que reciba archivos tiene que sumarse acá; el test
`test_toda_ruta_con_archivos_tiene_tope_propio` falla si se olvida.
"""
import json
import re

MB = 1024 * 1024
HOLGURA = 256 * 1024
TOPE_POR_DEFECTO = 2 * MB

MENSAJE = "El archivo es demasiado grande."

#: (patrón de ruta, tope en MB). La primera que coincide gana.
#: Fotos: _MAX_FOTO_BYTES (campo), _GAL_MAX_FOTO_BYTES (comercio),
#: _ADMIN_MAX_FOTO_BYTES (admin): 15 MB. Videos: _MAX_VIDEO_BYTES (campo) y
#: _GAL_MAX_VIDEO_BYTES (comercio): 50 MB; el promo de contenido.py: 100 MB. Las novedades
#: de URUKU (contenido.py): fotos de 15 MB y video de 100 MB.
#: Catálogo en PDF: ficha_catalogo.MAX_BYTES, 8 MB. Audio de «¿qué vende?»: 25 MB
#: (el límite que ya tiene /campo/transcribir). Webhook de WAHA: 25 MB (un
#: mensaje con media inline). `/comercio/productos` lleva hasta 3 fotos de 15 MB.
TABLA_DE_TOPES: tuple[tuple[re.Pattern, int], ...] = tuple(
    (re.compile(p), mb) for p, mb in (
        # Catálogo
        (r"^/comercio/catalogo$", 8),
        (r"^/campo/mis-comercios/[^/]+/catalogo$", 8),
        (r"^/admin/comercio/[^/]+/catalogo$", 8),
        # Webhook de WAHA / Meta
        (r"^/ingest/webhook$", 25),
        # Video promo
        (r"^/contenido/videos-promo$", 100),
        # Novedades de URUKU (0150): video (+ póster) de hasta 100 MB; portada y fotos de 15 MB
        (r"^/contenido/novedades/[^/]+/video$", 100),
        (r"^/contenido/novedades/[^/]+/(portada|fotos)$", 15),
        # Videos
        (r"^/comercio/videos$", 50),
        (r"^/campo/mis-comercios/[^/]+/videos$", 50),
        (r"^/campo/lugares/[^/]+/video$", 50),
        # Audio
        (r"^/campo/transcribir$", 25),
        # Producto con hasta 3 fotos
        (r"^/comercio/productos$", 45),
        # Fotos
        (r"^/campo/comercio$", 15),
        (r"^/auth/comercio/registro$", 15),
        (r"^/comercio/[^/]+/solicitar-cambio-numero$", 15),
        (r"^/comercio/fotos$", 15),
        (r"^/comercio/perfil/foto$", 15),
        (r"^/comercio/pago$", 15),
        (r"^/campo/lugares/[^/]+/portada$", 15),
        (r"^/campo/mis-comercios/[^/]+/fotos?$", 15),
        (r"^/admin/comercio/[^/]+/fotos?$", 15),
        # El Excel de compradores ya leído por el panel: hasta 20.000 filas de JSON.
        (r"^/admin/contactos/importar$", 8),
    )
)


def tope_para(ruta: str) -> int:
    """El tope en bytes del cuerpo para esa ruta (con la holgura multipart)."""
    ruta = ruta.rstrip("/") or "/"
    for patron, mb in TABLA_DE_TOPES:
        if patron.match(ruta):
            return mb * MB + HOLGURA
    return TOPE_POR_DEFECTO


#: El catálogo tiene su propio mensaje: es lo que la pantalla le muestra a quien
#: lo sube, y «el archivo es demasiado grande» no dice cuánto puede pesar.
_RUTA_CATALOGO = re.compile(r"^/(comercio/catalogo|campo/mis-comercios/[^/]+/catalogo|admin/comercio/[^/]+/catalogo)$")
MENSAJE_CATALOGO = "El catálogo puede pesar hasta 8 MB."


def mensaje_para(ruta: str) -> str:
    return MENSAJE_CATALOGO if _RUTA_CATALOGO.match(ruta.rstrip("/") or "/") else MENSAJE


class LimiteCuerpoMiddleware:
    """Middleware ASGI puro: ver el docstring del módulo."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] in ("GET", "HEAD", "OPTIONS"):
            await self.app(scope, receive, send)
            return

        tope = tope_para(scope["path"])
        texto_413 = mensaje_para(scope["path"])
        declarado = None
        for nombre, valor in scope.get("headers", ()):
            if nombre == b"content-length":
                try:
                    declarado = int(valor)
                except ValueError:
                    declarado = None
                break
        if declarado is not None and declarado > tope:
            scope["cuerpo_excedido"] = True
            await _responder_413(send, texto_413)
            return

        total = 0
        excedido = False
        empezada = False      # la aplicación ya empezó a contestar lo suyo
        reemplazada = False   # contestamos nosotros el 413

        async def receive_limitado():
            nonlocal total, excedido
            if excedido:
                return {"type": "http.disconnect"}
            mensaje = await receive()
            if mensaje["type"] == "http.request":
                total += len(mensaje.get("body", b""))
                if total > tope:
                    excedido = True
                    scope["cuerpo_excedido"] = True
                    return {"type": "http.disconnect"}
            return mensaje

        async def send_limitado(mensaje):
            nonlocal empezada, reemplazada
            if reemplazada:
                return
            if mensaje["type"] == "http.response.start":
                if excedido and not empezada:
                    # Lo que la aplicación quería contestar (un 400 de «cuerpo
                    # ilegible», un 500) se reemplaza por el 413.
                    reemplazada = True
                    await _responder_413(send, texto_413)
                    return
                empezada = True
            await send(mensaje)

        try:
            await self.app(scope, receive_limitado, send_limitado)
        except Exception:
            if not excedido:
                raise
            # La aplicación se cayó por un cuerpo cortado: ya se sabe por qué.
        if excedido and not empezada and not reemplazada:
            await _responder_413(send, texto_413)


async def _responder_413(send, mensaje: str = MENSAJE) -> None:
    cuerpo = json.dumps({"detail": mensaje}, ensure_ascii=False).encode("utf-8")
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [
            (b"content-type", b"application/json"),
            (b"content-length", str(len(cuerpo)).encode()),
            # El resto del cuerpo no se lee: la conexión no se reutiliza.
            (b"connection", b"close"),
        ],
    })
    await send({"type": "http.response.body", "body": cuerpo})
