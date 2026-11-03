"""Plantilla T1 (carrusel de fotos) del kit de reels, parametrizada.

Lee y valida `job.json` y arma la pagina HTML que despues fotografia `render.py`.
Parte de `docs/reels-kit/referencias/plantillas/reels_build.py` (T1 minorista) con
estos cambios (docs/contenido-redes-tecnico.md, 16.4):

- N fotos (4 a 6) con los tiempos de la tabla "Plantilla T1 v2".
- `.glow` SIN `filter: blur` (16.3: el desenfoque costaba 70 ms por cuadro).
- kick, subtitle, place_chip, close_line y el chip de cada foto son opcionales.
- El ancho del tecleo del buscador y la reduccion de los titulos se miden en el
  navegador (ver FIT_JS), porque la pagina no trae ningun <script>.

Seguridad: todo texto del job pasa por `html.escape`; las fotos se leen solo de la
carpeta del job y los recursos solo de `renderer/assets/`; la pagina lleva una meta
CSP que prohibe todo salvo imagenes y fuentes `file:`.
"""
from __future__ import annotations

import html
import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSETS_DIR = HERE / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
ICONS_DIR = ASSETS_DIR / "iconos"
LOGO_FILE = ASSETS_DIR / "logo.png"

WIDTH, HEIGHT, FPS = 1080, 1920, 30
MIN_SLIDES, MAX_SLIDES = 4, 6
MAX_JOB_BYTES = 64 * 1024
MAX_PHOTO_BYTES = 12 * 1024 * 1024
# Nombres FIJOS de las salidas, dentro de la subcarpeta `out/` (la única que el contenedor puede escribir).
OUT_VIDEO, OUT_COVER = "out/video.mp4", "out/cover.jpg"
COVER_T = 2.6  # segundos: primera foto con el titulo

# Se usan SIEMPRE con `fullmatch` (un `$` deja pasar un salto de línea final).
UUID_RE = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
PHOTO_RE = re.compile(r"s\d{1,2}\.jpg")

# Monedas que existen en renderer/assets/iconos (ic_<nombre>.png).
KNOWN_ICONS = frozenset(p.stem[3:] for p in ICONS_DIR.glob("ic_*.png"))
MAX_ICONS = 3

CSP = "default-src 'none'; img-src file:; style-src 'unsafe-inline'; font-src file:"


class JobError(ValueError):
    """El job.json o su carpeta no sirven. Es un error del pedido: no se reintenta."""


@dataclass(frozen=True)
class Slide:
    file: str
    chip: str | None
    focus_y: float


@dataclass(frozen=True)
class Job:
    piece_id: str
    job_dir: Path
    texts: dict
    icons: tuple
    slides: tuple


@dataclass(frozen=True)
class Timeline:
    n: int
    close_at: float  # C: arranca el cierre
    total: float  # duracion del video

    @property
    def frames(self) -> int:
        return round(self.total * FPS)


def timeline(n: int) -> Timeline:
    """Tiempos de 16.4 para N fotos: carrusel 1,5 s + 2,1 s por foto; cierre desde 1,4 + 2,1 N y dura 4,2 s."""
    close_at = round(1.4 + 2.1 * n, 2)
    return Timeline(n=n, close_at=close_at, total=round(close_at + 4.2, 2))


# ----------------------------------------------------------------------------
# Validacion del job
# ----------------------------------------------------------------------------
def parse_piece_id(value) -> str:
    if not isinstance(value, str) or not UUID_RE.fullmatch(value):
        raise JobError("piece_id inválido: debe ser un UUID")
    return value


def _clean(value: str) -> str:
    """Normaliza (NFKC), saca los caracteres de formato Unicode (categoría Cf: ancho cero, bidi, etc.), los de
    control (saltos, tabs, NUL) y recorta los bordes."""
    value = unicodedata.normalize("NFKC", value)
    value = "".join(ch for ch in value if unicodedata.category(ch) != "Cf")
    return re.sub(r"[\x00-\x1f\x7f]", " ", value).strip()


def _text(texts: dict, key: str, *, required: bool, max_len: int = 120):
    value = texts.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise JobError(f"Falta el texto «{key}»")
        return None
    if not isinstance(value, str):
        raise JobError(f"El texto «{key}» debe ser una cadena")
    value = _clean(value)
    if len(value) > max_len:
        raise JobError(f"El texto «{key}» es demasiado largo (máximo {max_len} caracteres)")
    if not value and required:
        raise JobError(f"Falta el texto «{key}»")
    return value or None


def _resolve_inside(job_dir: Path, name: str) -> Path:
    path = (job_dir / name).resolve()
    if not path.is_relative_to(job_dir.resolve()):
        raise JobError(f"La foto «{name}» está fuera de la carpeta del job")
    return path


def validate_job(data, job_dir: Path, *, check_files: bool = True) -> Job:
    """Valida el contenido de job.json (16.4). Cualquier problema levanta JobError."""
    if not isinstance(data, dict):
        raise JobError("job.json debe ser un objeto")
    piece_id = parse_piece_id(data.get("piece_id"))
    if job_dir.name != piece_id:
        raise JobError("piece_id no coincide con la carpeta del job")
    if data.get("version") != 2:
        raise JobError("version no soportada (se espera 2)")
    if data.get("template") != "t1":
        raise JobError("template no soportada (se espera t1)")
    if data.get("format") != "9x16":
        raise JobError("format no soportado (se espera 9x16)")
    fps = data.get("fps")
    if isinstance(fps, bool) or fps != FPS:
        raise JobError(f"fps no soportado (se espera {FPS})")
    if data.get("out_video") != OUT_VIDEO or data.get("out_cover") != OUT_COVER:
        raise JobError(f"out_video y out_cover deben ser «{OUT_VIDEO}» y «{OUT_COVER}»")

    raw_texts = data.get("texts")
    if not isinstance(raw_texts, dict):
        raise JobError("texts debe ser un objeto")
    texts = {
        "kick": _text(raw_texts, "kick", required=False, max_len=40),
        "title1": _text(raw_texts, "title1", required=True, max_len=40),
        "title2": _text(raw_texts, "title2", required=True, max_len=40),
        "subtitle": _text(raw_texts, "subtitle", required=False, max_len=90),
        "close_title1": _text(raw_texts, "close_title1", required=True, max_len=40),
        "close_title2": _text(raw_texts, "close_title2", required=True, max_len=40),
        "search_term": _text(raw_texts, "search_term", required=True, max_len=24),
        "place_chip": _text(raw_texts, "place_chip", required=False, max_len=60),
        "close_line": _text(raw_texts, "close_line", required=False, max_len=90),
        "url": _text(raw_texts, "url", required=True, max_len=30),
        "lema": _text(raw_texts, "lema", required=True, max_len=60),
    }

    icons = data.get("icons")
    if not isinstance(icons, list) or len(icons) > MAX_ICONS:
        raise JobError(f"icons debe ser una lista de hasta {MAX_ICONS} nombres")
    for name in icons:
        if not isinstance(name, str) or name not in KNOWN_ICONS:
            raise JobError("icons trae un ícono que no está en la lista conocida")
    if len(set(icons)) != len(icons):
        raise JobError("icons no puede repetir íconos")

    raw_slides = data.get("slides")
    if not isinstance(raw_slides, list) or not (MIN_SLIDES <= len(raw_slides) <= MAX_SLIDES):
        raise JobError(f"slides debe traer entre {MIN_SLIDES} y {MAX_SLIDES} fotos")
    slides, seen = [], set()
    for idx, item in enumerate(raw_slides):
        if not isinstance(item, dict):
            raise JobError(f"slides[{idx}] debe ser un objeto")
        name = item.get("file")
        if not isinstance(name, str) or not PHOTO_RE.fullmatch(name):
            raise JobError(f"slides[{idx}].file inválido: debe ser sN.jpg")
        if name in seen:
            raise JobError(f"slides[{idx}].file repetido")
        seen.add(name)
        focus = item.get("focus_y")
        if focus is None:
            focus = 0.4
        elif isinstance(focus, bool) or not isinstance(focus, (int, float)) or not 0 <= focus <= 1:
            raise JobError(f"slides[{idx}].focus_y debe estar entre 0 y 1")
        chip = item.get("chip")
        if chip is not None:
            if not isinstance(chip, str):
                raise JobError(f"slides[{idx}].chip debe ser una cadena")
            chip = _clean(chip)
            if len(chip) > 60:
                raise JobError(f"slides[{idx}].chip es demasiado largo")
            chip = chip or None
        if check_files:
            path = _resolve_inside(job_dir, name)
            if (job_dir / name).is_symlink() or not path.is_file():
                raise JobError(f"Falta la foto {name}")
            size = path.stat().st_size
            if size == 0 or size > MAX_PHOTO_BYTES:
                raise JobError(f"La foto {name} tiene un tamaño inválido")
            with path.open("rb") as fh:
                if fh.read(3) != b"\xff\xd8\xff":
                    raise JobError(f"La foto {name} no es un JPEG")
        slides.append(Slide(file=name, chip=chip, focus_y=float(focus)))

    return Job(piece_id=piece_id, job_dir=job_dir, texts=texts, icons=tuple(icons), slides=tuple(slides))


def load_job(job_dir: Path) -> Job:
    """Lee `job.json` de la carpeta del job y lo valida."""
    job_dir = Path(job_dir)
    if not job_dir.is_dir():
        raise JobError("No existe la carpeta del job")
    path = job_dir / "job.json"
    if path.is_symlink() or not path.is_file():
        raise JobError("No existe job.json en la carpeta del job")
    if path.stat().st_size > MAX_JOB_BYTES:
        raise JobError("job.json es demasiado grande")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise JobError(f"job.json no se puede leer: {exc.__class__.__name__}") from exc
    return validate_job(data, job_dir)


# ----------------------------------------------------------------------------
# HTML
# ----------------------------------------------------------------------------
def esc(value: str) -> str:
    return html.escape(value, quote=True)


def _t(x: float) -> str:
    return f"{x:.2f}s"


def _scene(name: str, t0: float, t1: float, fin: float = 0.4, fout: float = 0.4) -> str:
    dur = t1 - t0
    p1 = fin / dur * 100
    p2 = 100 - fout / dur * 100
    return (
        f"@keyframes io_{name}{{0%{{opacity:0}}{p1:.2f}%{{opacity:1}}{p2:.2f}%{{opacity:1}}100%{{opacity:0}}}}\n"
        f".{name}{{animation:io_{name} {dur:.2f}s {t0:.2f}s linear both}}\n"
    )


# Tokens del kit (prompt.md 6). `.glow` sin filter:blur: el radial-gradient ya es suave.
BASE_CSS = """*{box-sizing:border-box;margin:0;padding:0}
body{width:1080px;height:1920px;overflow:hidden;font-family:Poppins,sans-serif;background:#08110C}
.stage{position:relative;width:1080px;height:1920px;overflow:hidden;background:radial-gradient(110% 75% at 50% 55%,#0F3423 0%,#0B1E15 45%,#08110C 100%)}
.sc{position:absolute;inset:0}
.glow{position:absolute;left:540px;top:1000px;width:1250px;height:1250px;margin:-625px 0 0 -625px;border-radius:50%;
 background:radial-gradient(closest-side,rgba(38,185,105,.55),rgba(29,141,82,.22) 50%,transparent 74%);animation:pulse 4s ease-in-out infinite}
@keyframes pulse{50%{transform:scale(1.07)}}
.title{position:absolute;left:0;right:0;text-align:center;padding:0 60px}
.kick{display:inline-block;font-weight:600;font-size:30px;letter-spacing:3px;color:#04311A;background:#34D27F;border-radius:30px;padding:8px 24px;margin-bottom:22px;white-space:nowrap;animation:rise .6s cubic-bezier(.2,.8,.2,1) both}
.tl1,.tl2{font-weight:600;font-size:88px;line-height:1.05;letter-spacing:-2.5px;color:#fff;white-space:nowrap;animation:rise .6s cubic-bezier(.2,.8,.2,1) both}
.tl2{color:#34D27F}
@keyframes rise{from{opacity:0;transform:translateY(40px)}to{opacity:1;transform:none}}
.sub{position:absolute;left:0;right:0;text-align:center;font-size:38px;line-height:1.35;color:#D2E2D8;padding:0 90px;animation:rise .6s cubic-bezier(.2,.8,.2,1) both}
.pc{position:absolute;border-radius:44px;overflow:hidden;background:#f2f2f0;
 box-shadow:0 50px 100px rgba(0,0,0,.6),0 0 0 3px rgba(80,220,140,.45),0 0 80px rgba(52,210,127,.35)}
.pc img{display:block;width:100%;height:100%;object-fit:cover}
.chip{position:absolute;font-weight:600;font-size:40px;color:#fff;background:#16211B;border:2px solid #2B4A39;border-radius:44px;padding:16px 34px;display:flex;align-items:center;gap:16px;
 box-shadow:0 24px 48px rgba(0,0,0,.5);white-space:nowrap}
.chip i{width:18px;height:18px;border-radius:50%;background:#34D27F;box-shadow:0 0 16px #34D27F;flex:none}
.coin{position:absolute;filter:drop-shadow(0 24px 30px rgba(0,0,0,.6));animation:cpop .9s cubic-bezier(.2,1.35,.3,1) both, bob 3s ease-in-out infinite}
@keyframes cpop{from{opacity:0;transform:scale(.15) rotate(-40deg)}}
@keyframes bob{50%{translate:0 -12px}}
.logoE{position:absolute;width:420px;left:330px;animation:rise .7s cubic-bezier(.2,.8,.2,1) both}
.url{position:absolute;left:0;right:0;text-align:center;font-weight:700;font-size:80px;color:#34D27F;animation:rise .7s cubic-bezier(.2,.8,.2,1) both}
.lema{position:absolute;left:0;right:0;text-align:center;font-size:34px;color:#A8BDB1;animation:rise .7s both}
.car{position:absolute;left:150px;top:560px;width:780px;height:980px}
.slide{position:absolute;inset:0;animation:sin .7s cubic-bezier(.2,.9,.3,1) both, sout .55s cubic-bezier(.6,0,.8,.4) both}
@keyframes sin{from{opacity:0;transform:translateX(700px) rotate(10deg) scale(.85)}}
@keyframes sout{to{opacity:0;transform:translateX(-760px) rotate(-10deg) scale(.85)}}
.slide .pc{left:0;top:0;width:780px;height:980px}
.slide .chip{left:50%;bottom:-40px;transform:translateX(-50%)}
.cnt{position:absolute;left:0;right:0;top:1640px;display:flex;justify-content:center;gap:16px}
.cnt b{width:16px;height:16px;border-radius:50%;background:#2B4A39;animation:on .3s both}
@keyframes on{to{background:#34D27F;box-shadow:0 0 14px #34D27F;width:46px;border-radius:10px}}
.search{position:absolute;left:70px;right:70px;top:640px;height:130px;border-radius:32px;background:#16211B;border:2px solid #2B4A39;
 display:flex;align-items:center;padding-left:36px;gap:24px;box-shadow:0 30px 60px rgba(0,0,0,.55),0 0 50px rgba(52,210,127,.25);animation:rise .6s both}
.mag{width:42px;height:42px;border:5px solid #8FA79A;border-radius:50%;position:relative;flex:none}
.mag:after{content:"";position:absolute;width:5px;height:18px;background:#8FA79A;right:-10px;bottom:-13px;transform:rotate(-45deg);border-radius:2px}
.typed{font-size:48px;color:#fff;font-weight:500;white-space:nowrap;overflow:hidden;width:0}
@keyframes type{to{width:var(--tw,300px)}}
.btn{margin-left:auto;height:100%;padding:0 46px;display:grid;place-items:center;font-weight:700;font-size:40px;color:#fff;background:#1F9D58;border-radius:0 30px 30px 0}
.whw{position:absolute;left:0;right:0;top:880px;display:flex;justify-content:center;animation:rise .6s both}.whw .chip{position:relative}
"""

# Se corre con `page.evaluate` despues de cargar fuentes e imagenes y antes de pausar las
# animaciones. Usa offsetWidth/scrollWidth (layout, no afectado por los transform de entrada).
FIT_JS = """() => {
  document.querySelectorAll('.title').forEach(t => {
    const lines = t.querySelectorAll('.tl1,.tl2');
    if ([...lines].some(l => l.scrollWidth > l.clientWidth + 1)) lines.forEach(l => { l.style.fontSize = '72px'; });
  });
  document.querySelectorAll('.chip').forEach(c => {
    const w = c.offsetWidth;
    if (w > 980) { c.style.fontSize = Math.max(26, Math.floor(40 * 980 / w)) + 'px'; }
  });
  const typed = document.querySelector('.typed');
  if (typed) {
    const tt = typed.querySelector('.tt');
    typed.style.setProperty('--tw', Math.ceil(tt.getBoundingClientRect().width) + 'px');
  }
  return true;
}"""


def _file_url(path: Path) -> str:
    return path.resolve().as_uri()


def _font_faces() -> str:
    faces = []
    for name, weight in (("Poppins-Medium", 400), ("Poppins-Medium", 500), ("Poppins-SemiBold", 600), ("Poppins-Bold", 700)):
        faces.append(
            f'@font-face{{font-family:Poppins;src:url("{_file_url(FONTS_DIR / (name + ".ttf"))}");font-weight:{weight}}}'
        )
    return "".join(faces)


def _title(kick: str | None, l1: str, l2: str, t: float, top: int) -> str:
    kk = f'<div class="kick" style="animation-delay:{_t(t)}">{esc(kick)}</div>' if kick else ""
    return (
        f'<div class="title" style="top:{top}px">{kk}'
        f'<div class="tl1" style="animation-delay:{_t(t + .1)}">{esc(l1)}</div>'
        f'<div class="tl2" style="animation-delay:{_t(t + .25)}">{esc(l2)}</div></div>'
    )


def _coin(name: str, x: int, y: int, t: float, size: int = 170) -> str:
    src = _file_url(ICONS_DIR / f"ic_{name}.png")
    return (
        f'<img class="coin" src="{esc(src)}" style="left:{x - size // 2}px;top:{y - size // 2}px;'
        f'width:{size}px;animation-delay:{_t(t)},{_t(t + .9)}">'
    )


def _split_two_lines(text: str) -> str:
    """Parte una frase larga en dos lineas parejas (queda entre las monedas, como en el kit)."""
    if len(text) <= 24 or " " not in text:
        return esc(text)
    mid = len(text) / 2
    cut = min((m.start() for m in re.finditer(" ", text)), key=lambda i: abs(i - mid))
    return f"{esc(text[:cut])}<br>{esc(text[cut + 1:])}"


def _coin_positions(n: int) -> list[int]:
    return {0: [], 1: [540], 2: [170, 910], 3: [170, 540, 910]}[n]


def build_html(job: Job) -> str:
    """Arma la pagina completa de T1 para el job (todo texto escapado)."""
    tl = timeline(len(job.slides))
    c = tl.close_at
    tx = job.texts

    css = BASE_CSS + _scene("a1", 0, c + 0.2, 0.3, 0.4) + _scene("a2", c - 0.1, tl.total + 0.5, 0.4, 0.01)

    slides = []
    last = len(job.slides) - 1
    for i, s in enumerate(job.slides):
        t_in = 1.5 + i * 2.1
        t_out = c - 0.2 if i == last else t_in + 2.0
        src = esc(_file_url(job.job_dir / s.file))
        chip = f'<div class="chip"><i></i>{esc(s.chip)}</div>' if s.chip else ""
        slides.append(
            f'<div class="slide" style="animation-delay:{_t(t_in)},{_t(t_out)}"><div class="pc">'
            f'<img src="{src}" style="object-position:50% {s.focus_y * 100:.1f}%"></div>{chip}</div>'
        )
    dots = "".join(f'<b style="animation-delay:{_t(1.5 + i * 2.1)}"></b>' for i in range(len(job.slides)))
    subtitle = f'<div class="sub" style="top:1730px;animation-delay:{_t(1.2)}">{esc(tx["subtitle"])}</div>' if tx["subtitle"] else ""

    term = tx["search_term"]
    type_dur = max(0.5, min(1.4, 0.11 * len(term)))
    place = (
        f'<div class="whw" style="animation-delay:{_t(c + 1.5)}"><div class="chip"><i></i>{esc(tx["place_chip"])}</div></div>'
        if tx["place_chip"]
        else ""
    )
    coins = "".join(
        _coin(name, x, 1130, c + 1.8 + 0.3 * k) for k, (name, x) in enumerate(zip(job.icons, _coin_positions(len(job.icons))))
    )
    close_line = (
        f'<div class="sub" style="top:1060px;animation-delay:{_t(c + 2.0)};font-size:36px">{_split_two_lines(tx["close_line"])}</div>'
        if tx["close_line"]
        else ""
    )
    logo = esc(_file_url(LOGO_FILE))

    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8">
<meta http-equiv="Content-Security-Policy" content="{esc(CSP)}">
<style>{_font_faces()}{css}</style></head><body><div class="stage">
<div class="glow"></div>
<div class="sc a1">
 {_title(tx["kick"], tx["title1"], tx["title2"], .2, 130)}
 <div class="car">{"".join(slides)}</div>
 <div class="cnt">{dots}</div>
 {subtitle}
</div>
<div class="sc a2">
 {_title(None, tx["close_title1"], tx["close_title2"], c, 260)}
 <div class="search" style="animation-delay:{_t(c + .2)}"><div class="mag"></div><div class="typed" style="animation:type {type_dur:.2f}s {_t(c + .7)} steps({len(term)}) both"><span class="tt">{esc(term)}</span></div><div class="btn">Buscar</div></div>
 {place}
 {coins}
 {close_line}
 <img class="logoE" src="{logo}" style="top:1360px;animation-delay:{_t(c + 2.4)}">
 <div class="url" style="top:1530px;animation-delay:{_t(c + 2.6)}">{esc(tx["url"])}</div>
 <div class="lema" style="top:1660px;animation-delay:{_t(c + 2.8)}">{esc(tx["lema"])}</div>
</div>
</div></body></html>"""
