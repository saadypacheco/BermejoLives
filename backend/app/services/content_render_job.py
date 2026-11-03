"""Lado HIJO del render de las piezas (docs/contenido-redes-tecnico.md §5).

Se corre como un subproceso aparte, lanzado por `content_render.py`:

    python -m app.services.content_render_job --job <tmp>/job.json

POR QUÉ UN SUBPROCESO
=====================
El trabajo es CPU puro y se puede matar entero al vencer el tiempo. Corriendo fuera del
proceso que atiende los pedidos no le pelea el GIL a la API, y un `RLIMIT_AS` propio
(heredado por ffmpeg) le pone techo a la memoria sin tocar al resto del backend.

CÓMO ARMA EL VIDEO
==================
Pillow dibuja cada tramo UNA vez (fondo desenfocado + foto entera + textos) al 106 % y,
por cuadro, recorta y escala la región que toca (`resize` con caja decimal: un zoom suave, que no
tiembla como `zoompan`). Cada cuadro viaja como `rawvideo rgb24` por stdin a ffmpeg, que sólo codifica
(H.264 + una pista AAC muda, para que todas las redes lo acepten). Todo lo que se dibuja sale
de `facts` (la base): nada de lo que está DENTRO del video lo escribe un modelo de IA.

Imprime en stdout un JSON: `{ok, duration_s, video_bytes, render_ms}` o
`{ok: false, error, retryable}`. Sin emojis en ningún texto dibujado (la fuente no los tiene).
"""
from __future__ import annotations

import argparse
import json
import math
import re
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, ImageStat

ASSETS = Path(__file__).resolve().parents[1] / "assets" / "content"

OUT_W, OUT_H, FPS = 1080, 1920, 30
ZOOM = 1.06                                   # el tramo se dibuja al 106 %
BASE_W, BASE_H = round(OUT_W * ZOOM), round(OUT_H * ZOOM)
VERDE = (29, 141, 82)                         # #1D8D52, el verde de marca
BLANCO = (255, 255, 255)

#: Zona segura: lo que la interfaz de TikTok y Reels no tapa. (x0, y0, x1, y1) en el cuadro
#: de 1080x1920. Todo texto dibujado cae acá.
SAFE = (90, 250, 990, 1450)

DUR_TAPA, DUR_FOTO, DUR_CIERRE, FUNDIDO = 2.0, 2.5, 3.0, 0.3
MIN_FOTOS = 4
MAX_FOTOS = {"comercio_del_dia": 7, "ofertas": 6, "rubro": 6}

#: Foto entera (contain) en 1080 de ancho y hasta esta altura.
FOTO_MAX_H = 1500
#: En ofertas la foto deja libre abajo una banda verde de 220 px (dentro de la zona segura): la foto NO se tapa.
OFERTA_FOTO_Y = (230, 1230)
OFERTA_BANDA = (1230, 1450)

_EMOJI = re.compile("[\U0001F000-\U0001FAFF☀-➿️‍←-⇿⬀-⯿]")


class RenderError(Exception):
    """Falla del render. `retryable` dice si vale la pena volver a intentar."""

    def __init__(self, mensaje: str, retryable: bool = True):
        super().__init__(mensaje)
        self.retryable = retryable


# ───────────────────────────────────────────────────────────── texto

_fuentes: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}
_ARCHIVO = {"medium": "Poppins-Medium.ttf", "semibold": "Poppins-SemiBold.ttf", "bold": "Poppins-Bold.ttf"}


def fuente(peso: str, px: int) -> ImageFont.FreeTypeFont:
    """Poppins en el peso y tamaño pedidos (en píxeles del cuadro final, ya con el 106 %)."""
    clave = (peso, px)
    if clave not in _fuentes:
        ruta = ASSETS / _ARCHIVO[peso]
        try:
            _fuentes[clave] = ImageFont.truetype(str(ruta), px)
        except OSError as exc:
            raise RenderError(f"Falta la fuente {ruta.name}", retryable=False) from exc
    return _fuentes[clave]


def sin_emojis(texto: str | None) -> str:
    """El texto sin emojis ni caracteres de relleno (Poppins no los dibuja: saldría un cuadrado)."""
    return re.sub(r"\s+", " ", _EMOJI.sub("", texto or "")).strip()


def _largo(texto: str, peso: str, px: int) -> float:
    return fuente(peso, round(px * ZOOM)).getlength(texto) / ZOOM


def _cortar(texto: str, peso: str, px: int, ancho: int) -> str:
    """Corta con «…» para que entre en `ancho` (diseño)."""
    if _largo(texto, peso, px) <= ancho:
        return texto
    while texto and _largo(texto + "…", peso, px) > ancho:
        texto = texto[:-1]
    return texto.rstrip() + "…"


def _envolver(texto: str, peso: str, px: int, ancho: int) -> list[str]:
    palabras = texto.split()
    lineas: list[str] = []
    actual = ""
    for p in palabras:
        prueba = f"{actual} {p}".strip()
        if actual and _largo(prueba, peso, px) > ancho:
            lineas.append(actual)
            actual = p
        else:
            actual = prueba
    if actual:
        lineas.append(actual)
    return lineas


def ajustar_nombre(texto: str, peso: str = "bold", maximo: int = 96, minimo: int = 48,
                   ancho: int = 900, max_lineas: int = 2) -> tuple[int, list[str]]:
    """El tamaño más grande (hasta `maximo`) con el que el nombre entra en `max_lineas` de
    `ancho` px. Al mínimo, si todavía no entra, corta la última línea con «…»."""
    texto = sin_emojis(texto)
    for px in range(maximo, minimo - 1, -4):
        lineas = _envolver(texto, peso, px, ancho)
        if len(lineas) <= max_lineas and all(_largo(l, peso, px) <= ancho for l in lineas):
            return px, lineas
    lineas = _envolver(texto, peso, minimo, ancho)[:max_lineas] or [texto]
    lineas[-1] = _cortar(lineas[-1], peso, minimo, ancho)
    return minimo, lineas


# ─────────────────────────────────────────────────────────── lienzo

class Lienzo:
    """Un tramo en construcción: una imagen de `BASE_W x BASE_H` donde se dibuja con las
    coordenadas DEL CUADRO FINAL (1080x1920) y se escala solo. Guarda las cajas de los textos
    (en coordenadas del cuadro) para poder comprobar la zona segura."""

    def __init__(self, fondo: Image.Image):
        self.img = fondo
        self.draw = ImageDraw.Draw(self.img)
        self.cajas: list[tuple[str, tuple[float, float, float, float]]] = []

    @staticmethod
    def p(v: float) -> int:
        return round(v * ZOOM)

    def pegar(self, im: Image.Image, x: float, y: float, mascara: Image.Image | None = None) -> None:
        self.img.paste(im, (self.p(x), self.p(y)), mascara)

    def texto(self, x_centro: float, y: float, texto: str, peso: str, px: int, color=BLANCO) -> tuple[float, float]:
        """Dibuja `texto` centrado en `x_centro` con el borde superior en `y`. Devuelve (ancho, alto)."""
        f = fuente(peso, self.p(px))
        ancho = f.getlength(texto) / ZOOM
        izq = x_centro - ancho / 2
        self.draw.text((self.p(izq), self.p(y)), texto, font=f, fill=color)
        bb = f.getbbox(texto)
        alto = (bb[3] - bb[1]) / ZOOM
        top = y + bb[1] / ZOOM
        self.cajas.append((texto, (izq, top, izq + ancho, top + alto)))
        return ancho, f.size / ZOOM * 1.25

    def logo(self, ancho: float, x_centro: float, y: float) -> float:
        """El logo blanco. Devuelve su alto."""
        lg = Image.open(ASSETS / "uruku-horizontal-blanco.png").convert("RGBA")
        w = self.p(ancho)
        h = round(lg.height * w / lg.width)
        lg = lg.resize((w, h), Image.LANCZOS)
        self.img.paste(lg, (self.p(x_centro - ancho / 2), self.p(y)), lg)
        return h / ZOOM


def _fondo_borroso(foto: Image.Image) -> Image.Image:
    """La misma foto cubriendo todo el cuadro, desenfocada (radio 30) y oscurecida 45 %.
    Se desenfoca chica y se estira: lo mismo a la vista y una fracción del costo."""
    chico = ImageOps.fit(foto, (BASE_W // 4, BASE_H // 4), Image.BILINEAR)
    chico = chico.filter(ImageFilter.GaussianBlur(30 / 4))
    grande = chico.resize((BASE_W, BASE_H), Image.BICUBIC)
    return Image.blend(grande, Image.new("RGB", grande.size, (0, 0, 0)), 0.45)


def n1_suave(img: Image.Image) -> Image.Image:
    """Retoque fijo y suave de la foto (docs/analisis-tratamiento-fotos.md §N1): contraste al
    70 %, luz sólo si está oscura, saturación +5 % y nitidez. Se aplica DESPUÉS del resize."""
    img = img.convert("RGB")
    img = Image.blend(img, ImageOps.autocontrast(img, cutoff=0.5, preserve_tone=True), 0.7)
    media = ImageStat.Stat(img.convert("L")).mean[0]
    if media < 95:
        gamma = max(0.70, math.log(115 / 255) / math.log(max(media, 1) / 255))
        tabla = [round(255 * ((v / 255) ** gamma)) for v in range(256)]
        img = img.point(tabla * 3)
    img = ImageEnhance.Color(img).enhance(1.05)
    return img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=3))


def _foto_contain(foto: Image.Image, ancho: int, alto: int) -> Image.Image:
    """La foto ENTERA que entra en `ancho x alto` (diseño), ya en píxeles de la base."""
    esc = min(ancho / foto.width, alto / foto.height)
    w, h = max(1, round(foto.width * esc * ZOOM)), max(1, round(foto.height * esc * ZOOM))
    return n1_suave(foto.resize((w, h), Image.LANCZOS))


# ───────────────────────────────────────────────────────── los tramos

def tramo_tapa(facts: dict, primera: Image.Image) -> Lienzo:
    """Tapa de 2 s: la primera foto desenfocada, el logo y los datos del comercio (o el título del compilado)."""
    lz = Lienzo(_fondo_borroso(primera))
    alto_logo = lz.logo(360, 540, 270)
    if facts.get("pillar") == "rubro":
        rubro, ciudad = sin_emojis(facts.get("rubro")), sin_emojis(facts.get("ciudad"))
        titulo = f"{rubro} en {ciudad}" if rubro and ciudad else rubro or "Comercios de la ciudad"
        px, lineas = ajustar_nombre(titulo, maximo=88)
        y = 270 + alto_logo + 330
        for l in lineas:
            _, h = lz.texto(540, y, l, "bold", px)
            y += h
        return lz
    if facts.get("pillar") == "ofertas":
        ciudad = sin_emojis(facts.get("ciudad"))
        px, lineas = ajustar_nombre(f"Ofertas de la semana en {ciudad}" if ciudad else "Ofertas de la semana",
                                    maximo=88)
        y = 270 + alto_logo + 330
        for l in lineas:
            _, h = lz.texto(540, y, l, "bold", px)
            y += h
        return lz
    px, lineas = ajustar_nombre(facts.get("nombre") or "", "bold", 96, 48, 900, 2)
    rubro = sin_emojis(facts.get("rubro"))
    calle, ciudad = sin_emojis(facts.get("calle")), sin_emojis(facts.get("ciudad"))
    donde = ", ".join(x for x in (calle, ciudad) if x)
    y = 270 + alto_logo + 330
    for l in lineas:
        _, h = lz.texto(540, y, l, "bold", px)
        y += h
    y += 30
    if rubro:
        _, h = lz.texto(540, y, _cortar(rubro, "medium", 54, 900), "medium", 54)
        y += h + 20
    if donde:
        lz.texto(540, y, _cortar(donde, "medium", 44, 900), "medium", 44)
    return lz


def tramo_foto(foto: Image.Image, banda: dict | None = None) -> tuple[Lienzo, tuple[float, float, float, float]]:
    """Un tramo de foto: fondo desenfocado de la MISMA foto y la foto entera encima. Con `banda`
    (ofertas) la foto se achica para dejar libre abajo una franja verde con el comercio y el
    precio: la franja va FUERA de la foto. Devuelve el lienzo y la caja de la foto (diseño)."""
    lz = Lienzo(_fondo_borroso(foto))
    if banda is None:
        fg = _foto_contain(foto, OUT_W, FOTO_MAX_H)
        x = (OUT_W - fg.width / ZOOM) / 2
        y = (OUT_H - fg.height / ZOOM) / 2
    else:
        y0, y1 = OFERTA_FOTO_Y
        fg = _foto_contain(foto, OUT_W, y1 - y0)
        x = (OUT_W - fg.width / ZOOM) / 2
        y = y0 + ((y1 - y0) - fg.height / ZOOM) / 2
    lz.pegar(fg, x, y)
    caja = (x, y, x + fg.width / ZOOM, y + fg.height / ZOOM)
    if banda is not None:
        b0, b1 = OFERTA_BANDA
        lz.draw.rectangle([0, lz.p(b0), BASE_W, lz.p(b1)], fill=VERDE)
        nombre = _cortar(sin_emojis(banda.get("nombre")), "bold", 46, 940)
        titulo = _cortar(sin_emojis(banda.get("titulo_corto")), "medium", 36, 940)
        filas = [(nombre, "bold", 46)]
        # Sin precio (§16.1): ni en el video ni en los textos. La banda lleva el nombre y, si hay, el título corto.
        if titulo:
            filas.append((titulo, "medium", 36))
        alto = sum(round(px * 1.25) for _, _, px in filas)
        y_txt = b0 + ((b1 - b0) - alto) / 2
        for texto, peso, px in filas:
            _, h = lz.texto(540, y_txt, texto, peso, px)
            y_txt += h
    return lz, caja


def tramo_cierre(facts: dict) -> Lienzo:
    """Cierre de 3 s: fondo verde de marca, el logo y la invitación a buscar el comercio en uruku.bo."""
    lz = Lienzo(Image.new("RGB", (BASE_W, BASE_H), VERDE))
    alto = lz.logo(560, 540, 700)
    if facts.get("pillar") == "rubro":
        frase = f'Vea {sin_emojis(facts.get("rubro")).lower() or "los comercios"} en uruku.bo'
    elif facts.get("pillar") == "ofertas":
        frase = "Vea todas las ofertas en uruku.bo"
    else:
        frase = f'Busque "{sin_emojis(facts.get("nombre"))}" en uruku.bo'
    px, lineas = ajustar_nombre(frase, "semibold", 64, 40, 900, 3)
    y = 700 + alto + 80
    for l in lineas:
        _, h = lz.texto(540, y, l, "semibold", px)
        y += h
    return lz


# ───────────────────────────────────────────────────────── el video

class Tramo:
    def __init__(self, lienzo: Lienzo, dur: float, z0: float, z1: float):
        self.lienzo, self.dur, self.z0, self.z1 = lienzo, dur, z0, z1
        self._estatico: Image.Image | None = None

    def cuadro(self, u: float) -> Image.Image:
        """El cuadro en el segundo `u` del tramo: el zoom z va de `z0` a `z1` (entre 1,00 y 1,06)."""
        p = min(max(u / self.dur, 0.0), 1.0)
        z = self.z0 + (self.z1 - self.z0) * p
        if self.z0 == self.z1:
            if self._estatico is None:
                self._estatico = self._transformar(z)
            return self._estatico
        return self._transformar(z)

    def _transformar(self, z: float) -> Image.Image:
        """La región centrada de la base que corresponde a ese zoom, llevada a 1080x1920. Con `z = 1,00`
        se ve toda la base (el diseño tal cual); con `z = 1,06`, el recorte 1:1 del centro.

        `resize(box=)` acepta una caja en coordenadas decimales (zoom sin saltos de píxel) y es unas
        siete veces más rápido que una transformación afín: medido en esta PC, 43 ms contra 302 ms por
        cuadro, que es lo que separa un render de 30 s de uno de 160 s."""
        vw, vh = BASE_W / z, BASE_H / z
        x0, y0 = (BASE_W - vw) / 2, (BASE_H - vh) / 2
        return self.lienzo.img.resize((OUT_W, OUT_H), Image.BICUBIC, box=(x0, y0, x0 + vw, y0 + vh))


def armar_tramos(facts: dict, slides: list[dict]) -> list[Tramo]:
    """Los tramos de la pieza, en orden: tapa, fotos y cierre. Lanza RenderError si no hay fotos suficientes."""
    pillar = facts.get("pillar") or "comercio_del_dia"
    if pillar not in MAX_FOTOS:
        raise RenderError(f"Plantilla desconocida: {pillar}", retryable=False)
    abiertas: list[tuple[Image.Image, dict | None]] = []
    items = facts.get("items") or []
    for s in slides[:MAX_FOTOS[pillar]]:
        try:
            with Image.open(s["path"]) as im:
                foto = ImageOps.exif_transpose(im).convert("RGB")
        except Exception as exc:  # noqa: BLE001
            raise RenderError(f"No se pudo abrir una foto: {exc}", retryable=False) from exc
        banda = None
        if pillar in ("ofertas", "rubro"):
            # Las piezas nuevas no llevan precio (§16.1): la fuente trae sólo el nombre del comercio.
            banda = next((i for i in items if s.get("caption_fact") in (f"{i.get('nombre')} · {i.get('precio')}",
                                                                        i.get("nombre") if not i.get("precio") else None)), None)
            if banda is None:
                partes = (s.get("caption_fact") or "").split(" · ")
                banda = {"nombre": partes[0], "precio": partes[1] if len(partes) > 1 else ""}
        abiertas.append((foto, banda))
    if len(abiertas) < MIN_FOTOS:
        raise RenderError("Faltan fotos para armar el video", retryable=False)

    tramos = [Tramo(tramo_tapa(facts, abiertas[0][0]), DUR_TAPA, 1.0, 1.0)]
    for i, (foto, banda) in enumerate(abiertas):
        lz, _ = tramo_foto(foto, banda)
        # Alterna acercar y alejar: 1,00 -> 1,06 y 1,06 -> 1,00.
        z0, z1 = (1.0, ZOOM) if i % 2 == 0 else (ZOOM, 1.0)
        tramos.append(Tramo(lz, DUR_FOTO, z0, z1))
    tramos.append(Tramo(tramo_cierre(facts), DUR_CIERRE, 1.0, 1.0))
    return tramos


def duracion_total(tramos: list[Tramo]) -> float:
    return sum(t.dur for t in tramos)


def cuadro_en(tramos: list[Tramo], t: float) -> Image.Image:
    """El cuadro del instante `t` (s): con fundido cruzado de 0,3 s centrado en cada unión.
    Los tiempos de cada tramo son los VISIBLES: el fundido no alarga el video."""
    inicios, acum = [], 0.0
    for tr in tramos:
        inicios.append(acum)
        acum += tr.dur
    mitad = FUNDIDO / 2
    for j in range(len(tramos) - 1):
        borde = inicios[j + 1]
        if abs(t - borde) < mitad:
            a = tramos[j].cuadro(t - inicios[j])
            b = tramos[j + 1].cuadro(t - inicios[j + 1])
            return Image.blend(a, b, (t - (borde - mitad)) / FUNDIDO)
    for j in range(len(tramos) - 1, -1, -1):
        if t >= inicios[j]:
            return tramos[j].cuadro(t - inicios[j])
    return tramos[0].cuadro(0)


def comando_ffmpeg(salida: Path) -> list[str]:
    return ["ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{OUT_W}x{OUT_H}", "-r", str(FPS), "-i", "-",
            "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-profile:v", "high",
            "-pix_fmt", "yuv420p", "-threads", "2",
            "-c:a", "aac", "-b:a", "128k", "-movflags", "+faststart", str(salida)]


def codificar(tramos: list[Tramo], salida: Path) -> None:
    """Manda los cuadros a ffmpeg por stdin. Lanza RenderError si ffmpeg falla."""
    total = duracion_total(tramos)
    n = round(total * FPS)
    log = salida.with_suffix(".log")
    with open(log, "wb") as err:
        try:
            proc = subprocess.Popen(comando_ffmpeg(salida), stdin=subprocess.PIPE, stderr=err)
        except FileNotFoundError as exc:
            raise RenderError("ffmpeg no está instalado", retryable=False) from exc
        try:
            for i in range(n):
                proc.stdin.write(cuadro_en(tramos, i / FPS).tobytes())
            proc.stdin.close()
        except BrokenPipeError:
            pass
        except Exception:
            proc.kill()
            raise
        codigo = proc.wait()
    if codigo != 0:
        detalle = log.read_text(errors="replace")[-300:] if log.exists() else ""
        raise RenderError(f"ffmpeg terminó con error {codigo}: {detalle}".strip())


def verificar(salida: Path) -> float:
    """ffprobe: 1080x1920, 15 a 25 s (± 0,5), pista de audio y más de 100 KB. Devuelve la duración."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_type,width,height",
             "-show_entries", "format=duration", "-of", "json", str(salida)],
            capture_output=True, text=True, timeout=30)
        datos = json.loads(r.stdout or "{}")
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        raise RenderError(f"ffprobe falló: {exc}") from exc
    streams = datos.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if not video or (video.get("width"), video.get("height")) != (OUT_W, OUT_H):
        raise RenderError("El video no quedó de 1080x1920")
    if not any(s.get("codec_type") == "audio" for s in streams):
        raise RenderError("El video no tiene pista de audio")
    try:
        dur = float((datos.get("format") or {}).get("duration"))
    except (TypeError, ValueError) as exc:
        raise RenderError("No se pudo medir la duración del video") from exc
    if not (15 - 0.5 <= dur <= 25 + 0.5):
        raise RenderError(f"El video dura {dur:.1f} s (tiene que estar entre 15 y 25)")
    if salida.stat().st_size < 100 * 1024:
        raise RenderError("El video quedó demasiado liviano (menos de 100 KB)")
    return dur


def limitar_memoria(mb: int) -> None:
    """`RLIMIT_AS` en POSIX (ffmpeg lo hereda). En Windows no existe: se saltea."""
    try:
        import resource

        limite = mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (limite, limite))
    except (ImportError, ValueError, OSError):
        pass


def render(job: dict) -> dict:
    """Arma `out_video` y `out_cover` según el job. Devuelve el resultado (sin `ok`)."""
    inicio = time.monotonic()
    tramos = armar_tramos(job["facts"], job["slides"])
    salida = Path(job["out_video"])
    salida.parent.mkdir(parents=True, exist_ok=True)
    # La tapa a t = 1,0 s (ya con el texto a pleno).
    cuadro_en(tramos, 1.0).save(job["out_cover"], format="JPEG", quality=88)
    codificar(tramos, salida)
    dur = verificar(salida)
    return {"duration_s": round(dur, 1), "video_bytes": salida.stat().st_size,
            "render_ms": round((time.monotonic() - inicio) * 1000)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", required=True)
    args = ap.parse_args(argv)
    try:
        job = json.loads(Path(args.job).read_text(encoding="utf-8"))
        limitar_memoria(int(job.get("memory_mb") or 1536))
        r = {"ok": True, **render(job)}
    except RenderError as exc:
        r = {"ok": False, "error": str(exc)[:500], "retryable": exc.retryable}
    except MemoryError:
        r = {"ok": False, "error": "Se acabó la memoria del render", "retryable": True}
    except Exception as exc:  # noqa: BLE001
        r = {"ok": False, "error": f"{type(exc).__name__}: {exc}"[:500], "retryable": True}
    print(json.dumps(r))
    return 0


if __name__ == "__main__":
    sys.exit(main())
