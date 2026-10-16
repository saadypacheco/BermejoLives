"""Semilla de la DEMO local de URUKU: datos 100 % ficticios para manuales y videos.

No se corre a mano: la llama `demo.py up` (la primera vez) o `demo.py seed`, que le
pasan el entorno de demo (PYTHONPATH=backend, .env de scripts/demo/.run). Si se quiere
correr sola:

    cd scripts/demo/.run && PYTHONPATH=../../../backend python ../seed.py

Es idempotente: cada fila tiene un id fijo (uuid5 de su nombre) y se escribe con
`insert … on conflict do update`. Correrla dos veces deja lo mismo.

Qué siembra (todo inventado salvo las calles y el rol de farmacias, ver abajo):
  - Bermejo (activa) y Yacuiba (se activa) con zonas y dos «lugares».
  - ~30 comercios en Bermejo y 5 en Yacuiba, con GPS dentro del casco de Bermejo,
    portada y galería (imágenes dibujadas acá con Pillow, o fotos de frontend/public/),
    horarios variados, «Lo que suma», planes (estrella al día, uno de cortesía, uno
    vencido, uno suspendido) y pagos.
  - Ofertas y novedades aprobadas, pendientes (con veredicto de IA), en «cambios» y
    rechazadas; bandeja de WhatsApp; difusión; reclamos; mensajes; visitas, contactos
    y búsquedas de los últimos 30 días; cotizaciones y clima.
  - Farmacias de turno: el rol real de backend/data/turnos_farmacia, importado con
    `python -m app.scripts.importar_turnos_farmacia` pero con los TELÉFONOS
    REEMPLAZADOS por números ficticios (el rol trae celulares reales).
  - Calles de Bermejo desde OpenStreetMap (si hay red) o un puñado sembrado a mano,
    con marcas de recorrido.
  - Novedades de URUKU, equipo del panel, una cuenta de comercio y un comprador.

Teléfonos: 5917000NNNN (inventados). Correos: @demo.test (dominio reservado).
"""
from __future__ import annotations

import io
import json
import random
import subprocess
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parents[1]
sys.path.insert(0, str(AQUI))
import demo  # noqa: E402  (psql y constantes de la demo)

from app.core import auth  # noqa: E402
from app.core import clave as clave_usuario  # noqa: E402
from app.core import clave_comercio  # noqa: E402
from app.core.config import settings  # noqa: E402

NS = uuid.UUID("6f1d3c2a-5b8e-4f0a-9c7d-2e4b6a8c0d1e")
RNG = random.Random(20261015)
BOLIVIA = timezone(timedelta(hours=-4))
AHORA = datetime.now(timezone.utc)
HOY = AHORA.astimezone(BOLIVIA).date()
FOTOS = Path(settings.fotos_dir)
PUBLIC = RAIZ / "frontend" / "public"

# ─────────────────────────────────────────────── usuarios y claves de la demo
CLAVE_PANEL = "demo1234"
EQUIPO = [  # email, nombre, roles, ciudad
    ("admin@demo.test", "Valeria Rojas", ["admin"], "bermejo"),
    ("moderador@demo.test", "Martín Flores", ["moderador"], "bermejo"),
    ("publicador@demo.test", "Sofía Vargas", ["publicador"], "bermejo"),
    ("agente@demo.test", "Diego Mamani", ["agente"], "bermejo"),
    ("agente.yacuiba@demo.test", "Carla Gutiérrez", ["agente"], "yacuiba"),
]
AGENTE = "agente@demo.test"
COMERCIO_DEMO_SLUG = "boutique-ejemplo"
COMERCIO_DEMO_WA = "59170000101"
COMERCIO_DEMO_CLAVE = "BOUTIQUE-DEMO26"
COMPRADOR_WA = "59170000201"
COMPRADOR_CLAVE = "246810"


def uid(*partes: str) -> str:
    return str(uuid.uuid5(NS, "/".join(partes)))


# ─────────────────────────────────────────────── SQL
class J:
    """Valor jsonb."""
    def __init__(self, v):
        self.v = v


class A:
    """Valor text[]."""
    def __init__(self, v):
        self.v = list(v)


class S:
    """SQL crudo (una subconsulta, now(), …)."""
    def __init__(self, v):
        self.v = v


def lit(v) -> str:
    if v is None:
        return "null"
    if isinstance(v, S):
        return v.v
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, J):
        return "'" + json.dumps(v.v, ensure_ascii=False).replace("'", "''") + "'::jsonb"
    if isinstance(v, A):
        return "array[" + ",".join(lit(x) for x in v.v) + "]::text[]" if v.v else "'{}'::text[]"
    if isinstance(v, (date, datetime)):
        return "'" + v.isoformat() + "'"
    return "'" + str(v).replace("'", "''") + "'"


SQL: list[str] = []


def upsert(tabla: str, filas: list[dict], clave: str = "id", nada: bool = False) -> None:
    if not filas:
        return
    cols = list(dict.fromkeys(k for f in filas for k in f))
    valores = ",\n  ".join("(" + ", ".join(lit(f[c]) if c in f else "default" for c in cols) + ")" for f in filas)
    sets = ", ".join(f"{c} = excluded.{c}" for c in cols if c not in clave.split(","))
    accion = "do nothing" if nada or not sets else f"do update set {sets}"
    SQL.append(f"insert into {tabla} ({', '.join(cols)}) values\n  {valores}\non conflict ({clave}) {accion};")


def ejecutar(etiqueta: str) -> None:
    if not SQL:
        return
    p = demo.psql("begin;\n" + "\n".join(SQL) + "\ncommit;\nnotify pgrst, 'reload schema';", check=False)
    if p.returncode != 0:
        print(p.stderr[-3000:])
        raise SystemExit(f"Falló el bloque «{etiqueta}»")
    print(f"  ok: {etiqueta} ({len(SQL)} sentencias)")
    SQL.clear()


def valor(sql: str) -> str:
    return demo.psql(sql).stdout.strip()


# ─────────────────────────────────────────────── imágenes (dibujadas acá)
def _fuente(tam: int, negrita: bool = True):
    for nombre in (("arialbd.ttf", "segoeuib.ttf", "DejaVuSans-Bold.ttf") if negrita
                   else ("arial.ttf", "segoeui.ttf", "DejaVuSans.ttf")):
        for base in ("C:/Windows/Fonts/", "/usr/share/fonts/truetype/dejavu/", ""):
            try:
                return ImageFont.truetype(base + nombre, tam)
            except OSError:
                continue
    return ImageFont.load_default(size=tam)


def _mezcla(c1, c2, t):
    return tuple(int(a + (b - a) * t) for a, b in zip(c1, c2))


def _hex(c: str):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def _centrado(d: ImageDraw.ImageDraw, caja, texto, fuente, color):
    x0, y0, x1, y1 = caja
    while True:
        bb = d.textbbox((0, 0), texto, font=fuente)
        if bb[2] - bb[0] <= (x1 - x0) * 0.92 or fuente.size <= 14:
            break
        fuente = _fuente(fuente.size - 4)
    w, h = bb[2] - bb[0], bb[3] - bb[1]
    d.text((x0 + (x1 - x0 - w) / 2 - bb[0], y0 + (y1 - y0 - h) / 2 - bb[1]), texto, font=fuente, fill=color)


def imagen_vidriera(nombre: str, color: str, variante: int = 0, size=(1200, 800)) -> Image.Image:
    """Una fachada de local: cielo, pared, toldo a rayas, cartel con el nombre y vidriera."""
    w, h = size
    rng = random.Random(nombre + str(variante))
    base = _hex(color)
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    cielo_a, cielo_b = (135, 196, 235), (220, 238, 250)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=_mezcla(cielo_a, cielo_b, y / h))
    pared = _mezcla(base, (245, 240, 230), 0.72)
    d.rectangle([0, int(h * .18), w, h], fill=pared)
    d.rectangle([0, int(h * .88), w, h], fill=(150, 150, 150))           # vereda
    # cartel
    d.rounded_rectangle([int(w * .12), int(h * .22), int(w * .88), int(h * .38)], 18, fill=base)
    _centrado(d, (int(w * .12), int(h * .22), int(w * .88), int(h * .38)), nombre.upper(), _fuente(int(h * .09)),
              (255, 255, 255))
    # toldo
    y0, y1 = int(h * .40), int(h * .50)
    franjas = 12
    for i in range(franjas):
        x0 = int(w * .06 + i * (w * .88 / franjas))
        x1 = int(w * .06 + (i + 1) * (w * .88 / franjas))
        d.polygon([(x0, y0), (x1, y0), (x1 + 6, y1), (x0 - 6, y1)], fill=base if i % 2 == 0 else (255, 255, 255))
    # vidriera y puerta
    d.rectangle([int(w * .08), int(h * .52), int(w * .62), int(h * .86)], fill=(60, 70, 80))
    d.rectangle([int(w * .66), int(h * .52), int(w * .90), int(h * .88)], fill=_mezcla(base, (40, 30, 20), .55))
    d.ellipse([int(w * .68), int(h * .70), int(w * .695), int(h * .72)], fill=(230, 200, 90))
    # mercadería en la vidriera
    for _ in range(14 + variante * 3):
        cx = rng.randint(int(w * .1), int(w * .6))
        cy = rng.randint(int(h * .56), int(h * .82))
        r = rng.randint(int(h * .025), int(h * .06))
        col = _mezcla(_hex(rng.choice(["#ff6b6b", "#ffd93d", "#6bcB77", "#4d96ff", "#c77dff", "#ff9f43"])),
                      base, .25)
        if rng.random() < .5:
            d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=col)
        else:
            d.rounded_rectangle([cx - r, cy - r, cx + r, cy + int(r * 1.4)], 6, fill=col)
    d.rectangle([int(w * .08), int(h * .52), int(w * .62), int(h * .55)], fill=(255, 255, 255))
    return img.filter(ImageFilter.SMOOTH)


def imagen_producto(titulo: str, color: str, precio: str | None = None, descuento: int | None = None,
                    size=(1000, 1000)) -> Image.Image:
    """Una foto de producto «de estudio»: fondo suave, el objeto y la etiqueta de precio."""
    w, h = size
    rng = random.Random(titulo)
    base = _hex(color)
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    a, b = _mezcla(base, (255, 255, 255), .82), _mezcla(base, (255, 255, 255), .55)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=_mezcla(a, b, y / h))
    d.ellipse([int(w * .2), int(h * .74), int(w * .8), int(h * .84)], fill=_mezcla(b, (0, 0, 0), .18))
    forma = rng.choice(["caja", "bolsa", "botella", "zapato"])
    if forma == "caja":
        d.rounded_rectangle([int(w * .28), int(h * .28), int(w * .72), int(h * .78)], 28, fill=base)
        d.rectangle([int(w * .28), int(h * .44), int(w * .72), int(h * .5)], fill=(255, 255, 255))
    elif forma == "bolsa":
        d.arc([int(w * .38), int(h * .18), int(w * .62), int(h * .42)], 180, 360, fill=base, width=18)
        d.rounded_rectangle([int(w * .26), int(h * .32), int(w * .74), int(h * .78)], 30, fill=base)
    elif forma == "botella":
        d.rounded_rectangle([int(w * .44), int(h * .16), int(w * .56), int(h * .32)], 12, fill=base)
        d.rounded_rectangle([int(w * .34), int(h * .3), int(w * .66), int(h * .78)], 60, fill=base)
        d.rectangle([int(w * .34), int(h * .46), int(w * .66), int(h * .58)], fill=(255, 255, 255))
    else:
        d.rounded_rectangle([int(w * .2), int(h * .52), int(w * .8), int(h * .76)], 60, fill=base)
        d.rounded_rectangle([int(w * .2), int(h * .38), int(w * .48), int(h * .7)], 50, fill=base)
        d.line([int(w * .22), int(h * .72), int(w * .78), int(h * .72)], fill=(255, 255, 255), width=14)
    d.ellipse([int(w * .32), int(h * .34), int(w * .40), int(h * .40)], fill=_mezcla(base, (255, 255, 255), .5))
    _centrado(d, (int(w * .05), int(h * .04), int(w * .95), int(h * .14)), titulo, _fuente(int(h * .06)),
              _mezcla(base, (0, 0, 0), .55))
    if precio:
        d.rounded_rectangle([int(w * .58), int(h * .82), int(w * .95), int(h * .95)], 24, fill=(20, 20, 20))
        _centrado(d, (int(w * .58), int(h * .82), int(w * .95), int(h * .95)), precio, _fuente(int(h * .06)),
                  (255, 255, 255))
    if descuento:
        d.ellipse([int(w * .05), int(h * .78), int(w * .25), int(h * .98)], fill=(230, 40, 90))
        _centrado(d, (int(w * .05), int(h * .78), int(w * .25), int(h * .98)), f"-{descuento}%",
                  _fuente(int(h * .055)), (255, 255, 255))
    return img.filter(ImageFilter.SMOOTH)


def imagen_cartel(titulo: str, sub: str, color: str, size=(1200, 800)) -> Image.Image:
    """Placa de texto (novedades de URUKU, comprobantes)."""
    w, h = size
    base = _hex(color)
    img = Image.new("RGB", size)
    d = ImageDraw.Draw(img)
    for y in range(h):
        d.line([(0, y), (w, y)], fill=_mezcla(base, _mezcla(base, (0, 0, 0), .45), y / h))
    for i in range(6):
        r = 120 + i * 70
        d.ellipse([w - r, -r // 2, w + r, r * 1.5], outline=_mezcla(base, (255, 255, 255), .2), width=3)
    _centrado(d, (60, int(h * .3), w - 60, int(h * .52)), titulo, _fuente(int(h * .1)), (255, 255, 255))
    _centrado(d, (60, int(h * .56), w - 60, int(h * .68)), sub, _fuente(int(h * .05), False), (235, 235, 235))
    return img


def imagen_comprobante(nombre: str, monto: str) -> Image.Image:
    img = Image.new("RGB", (720, 1100), (250, 250, 250))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 720, 140], fill=(20, 90, 160))
    _centrado(d, (0, 20, 720, 120), "COMPROBANTE DE TRANSFERENCIA", _fuente(34), (255, 255, 255))
    y = 200
    for k, v in (("Banco", "Banco Demo S.A."), ("Destino", "URUKU (cuenta de demo)"), ("Origen", nombre),
                 ("Monto", monto), ("Fecha", HOY.strftime("%d/%m/%Y")), ("Operación", "DEMO-000123")):
        d.text((60, y), k, font=_fuente(28, False), fill=(110, 110, 110))
        d.text((60, y + 38), v, font=_fuente(36), fill=(20, 20, 20))
        y += 130
    d.text((60, 1020), "Documento ficticio — demo", font=_fuente(24, False), fill=(160, 160, 160))
    return img


def foto_publica(nombre: str, variante: int = 0) -> Image.Image:
    """Una foto de frontend/public/ (son del repo), recortada a 3:2."""
    img = Image.open(PUBLIC / nombre).convert("RGB")
    w, h = img.size
    objetivo = 1.5
    if w / h > objetivo:
        nw = int(h * objetivo)
        x = min(w - nw, max(0, (w - nw) // 2 + (variante - 1) * nw // 6))
        img = img.crop((x, 0, x + nw, h))
    else:
        nh = int(w / objetivo)
        y = (h - nh) // 2
        img = img.crop((0, y, w, y + nh))
    if img.width > 1400:
        img = img.resize((1400, int(1400 / objetivo)))
    return img


def guardar(img: Image.Image, rel: str) -> tuple[str, str]:
    """Guarda la foto y su miniatura (_t3, 600 px) como lo hace el backend. Devuelve (url, thumb)."""
    destino = FOTOS / rel
    destino.parent.mkdir(parents=True, exist_ok=True)
    img.save(destino, "JPEG", quality=84)
    chica = img.copy()
    chica.thumbnail((600, 600))
    rel_t = rel[:-4] + "_t3.jpg"
    chica.save(FOTOS / rel_t, "JPEG", quality=80)
    return settings.public_photo_url(rel), settings.public_photo_url(rel_t)


# ─────────────────────────────────────────────── datos
CALLES = ["Avenida Barrientos", "Calle Gualberto Villarroel", "Calle Belgrano", "Calle Mariscal Santa Cruz",
          "Avenida Luis de Fuentes", "Calle Germán Busch", "Calle Virgen de Chaguaya", "Calle Ingavi",
          "Calle Sucre", "Calle Bolívar", "Calle La Paz", "Calle Tarija"]

H_PARTIDO = "Lun-Sáb 8:00-12:00 y 14:30-20:00"
H_CORRIDO = "Lun-Sáb 8:00-20:00"
H_TODOS = "Todos los días 7:00-23:00"
H_24 = "Todos los días 0:00-24:00"
H_OFICINA = "Lun-Vie 9:00-13:00 y 15:00-19:00"
H_NOCHE = "Vie-Sáb 22:00-23:59"
H_DOMINGO = "Dom 10:00-11:00"

# slug, nombre, rubro, color, horario, plan, extras
COMERCIOS = [
    ("boutique-ejemplo", "Boutique Ejemplo", ["ropa", "calzado"], "#d6336c", H_TODOS, "destacado",
     dict(subcategoria="Ropa de mujer y accesorios", modalidad="ambos", pago_dias=4, verificado=True, confiable=True,
          tildes=(1, 1, 1, 1), galeria=8, redes=True, whatsapp=COMERCIO_DEMO_WA, lugar="galeria",
          descripcion="Ropa de mujer, jeans, blusas y accesorios. Llegan novedades todas las semanas.")),
    ("panaderia-el-sol", "Panadería El Sol", ["panaderia"], "#e8590c", H_24, "publica",
     dict(subcategoria="Pan, tortas y masitas", modalidad="minorista", pago_dias=40, verificado=True, confiable=True,
          tildes=(0, 0, 1, 0), galeria=4, descripcion="Pan de batalla, marraquetas, tortas por encargo.")),
    ("zapateria-paso-firme", "Zapatería Paso Firme", ["calzado"], "#5c7cfa", H_PARTIDO, "publica",
     dict(subcategoria="Zapatillas y calzado", modalidad="mayorista", pago_dias=-10, verificado=True,
          tildes=(1, 1, 0, 1), galeria=4, pago_pendiente=True)),
    ("celulares-frontera", "Celulares Frontera", ["celulares", "electronica"], "#1971c2", H_TODOS, "pro",
     dict(subcategoria="Celulares, fundas y cargadores", modalidad="ambos", pago_dias=25, verificado=True,
          confiable=True, tildes=(1, 1, 1, 0), galeria=6, redes=True, catalogo=True)),
    ("ferreteria-el-tornillo", "Ferretería El Tornillo", ["ferreteria"], "#868e96", H_PARTIDO, "gratis",
     dict(subcategoria="Herramientas y construcción", galeria=2, publica=True)),
    ("supermercado-la-canasta", "Supermercado La Canasta", ["alimentos", "bebidas", "limpieza"], "#2f9e44", H_TODOS,
     "destacado", dict(subcategoria="Abarrotes, bebidas y limpieza", modalidad="ambos", pago_dias=18, verificado=True,
                       confiable=True, tildes=(0, 0, 1, 0), galeria=5, redes=True, publica=True)),
    ("casa-de-cambio-el-puente", "Casa de Cambio El Puente", ["cambio"], "#f08c00", H_CORRIDO, "gratis",
     dict(subcategoria="Dólares, pesos y reales", verificado=True, galeria=1)),
    ("restaurante-don-lucho", "Restaurante Don Lucho", ["restaurantes"], "#c92a2a", "Todos los días 11:30-15:30 y 19:00-23:30",
     "destacado", dict(subcategoria="Almuerzo, parrilla y platos típicos", modalidad="minorista", pago_dias=12,
                       verificado=True, galeria=6, redes=True, publica=True)),
    ("heladeria-polo-sur", "Heladería Polo Sur", ["cafeteria"], "#15aabf", "Todos los días 10:00-22:00", "gratis",
     dict(subcategoria="Helados, café y postres", galeria=3)),
    ("perfumeria-aroma", "Perfumería Aroma", ["belleza"], "#be4bdb", H_PARTIDO, "gratis",
     dict(subcategoria="Perfumes y maquillaje", tildes=(1, 1, 0, 0), galeria=3, publica=True)),
    ("bazar-la-economia", "Bazar La Economía", ["bazar", "hogar"], "#fab005", H_CORRIDO, "gratis",
     dict(subcategoria="Bazar, cocina y regalos", modalidad="mayorista", galeria=2)),
    ("electro-hogar-bermejo", "Electro Hogar Bermejo", ["electrodomesticos"], "#364fc7", H_PARTIDO, "destacado",
     dict(subcategoria="Heladeras, cocinas y TV", cortesia=True, verificado=True, galeria=4, tildes=(1, 1, 1, 0))),
    ("tecno-center", "Tecno Center", ["computacion"], "#0b7285", H_OFICINA, "publica",
     dict(subcategoria="Notebooks y accesorios", pago_dias=30, suspendido=True, galeria=2)),
    ("jugueteria-arcoiris", "Juguetería Arcoíris", ["jugueteria"], "#f76707", H_PARTIDO, "gratis",
     dict(subcategoria="Juguetes y útiles escolares", galeria=3)),
    ("deportes-cancha-libre", "Deportes Cancha Libre", ["deportes"], "#37b24d", H_CORRIDO, "gratis",
     dict(subcategoria="Camisetas, pelotas y botines", galeria=2, publica=True)),
    ("optica-vision-clara", "Óptica Visión Clara", ["optica"], "#4263eb", H_OFICINA, "gratis",
     dict(subcategoria="Lentes y anteojos de sol", verificado=True, galeria=2)),
    ("peluqueria-estilo", "Peluquería Estilo", ["peluqueria"], "#e64980", "Mar-Sáb 9:00-19:00", "gratis",
     dict(subcategoria="Corte, color y barbería", galeria=2)),
    ("taller-mecanico-rueda", "Taller Mecánico Rueda", ["taller-mecanico", "repuestos-autos"], "#495057",
     None, "gratis", dict(subcategoria="Celulares, fundas y cargadores", galeria=1)),
    ("motos-del-sur", "Motos del Sur", ["motos"], "#e03131", H_PARTIDO, "gratis",
     dict(subcategoria="Motos, cascos y repuestos", galeria=2)),
    ("licoreria-la-bodega", "Licorería La Bodega", ["bebidas"], "#862e9c", "Todos los días 10:00-23:00", "gratis",
     dict(subcategoria="Vinos, singani y cervezas", galeria=2)),
    ("muebleria-roble", "Mueblería Roble", ["muebles"], "#a0522d", H_PARTIDO, "gratis",
     dict(subcategoria="Roperos, camas y colchones", galeria=2, tildes=(0, 1, 1, 0))),
    ("ropa-americana-toti", "Ropa Americana Toti", ["ropa-americana"], "#1098ad", H_CORRIDO, "gratis",
     dict(subcategoria="Ropa americana por fardo y por prenda", modalidad="mayorista", galeria=2)),
    ("kiosco-la-esquina", "Kiosco La Esquina", ["kiosco"], "#f59f00", None, "gratis",
     dict(subcategoria="Golosinas, bebidas y recargas", galeria=1, sin_foto=True)),
    ("hotel-rio-bermejo", "Hotel Río Bermejo", ["hospedaje"], "#0ca678", H_24, "gratis",
     dict(subcategoria="Habitaciones con baño privado y wifi", verificado=True, galeria=3)),
    ("carniceria-don-pepe", "Carnicería Don Pepe", ["carniceria"], "#c2255c", None, "gratis",
     dict(subcategoria="Carne de res, cerdo y pollo", galeria=1)),
    ("joyeria-brillante", "Joyería Brillante", ["joyeria"], "#ae3ec9", H_PARTIDO, "gratis",
     dict(subcategoria="Oro, plata y relojes", galeria=2, lugar="galeria")),
    ("mascotas-felices", "Mascotas Felices", ["mascotas"], "#74b816", None, "gratis",
     dict(subcategoria="Alimento balanceado y accesorios", galeria=2, lugar="mercado")),
    ("telas-hilo-de-oro", "Telas Hilo de Oro", ["telas"], "#d9480f", None, "gratis",
     dict(subcategoria="Telas, botones y mercería", galeria=1, lugar="mercado")),
    ("boliche-luna", "Boliche Luna", ["nocturna"], "#5f3dc4", H_NOCHE, "gratis",
     dict(subcategoria="Boliche y karaoke", galeria=2)),
    ("lavadero-burbujas", "Lavadero Burbujas", ["lavadero"], "#22b8cf", H_DOMINGO, "gratis",
     dict(subcategoria="Lavado de ropa por kilo", galeria=1, sin_verificar=True)),
    ("regaleria-sorpresa", "Regalería Sorpresa", ["regaleria"], "#f06595", H_PARTIDO, "gratis",
     dict(subcategoria="Regalos, globos y cotillón", galeria=1, borrador=True)),
    # Dos mal clasificados a propósito: aparecen en «Revisar rubros › No cierran».
    ("repuestos-el-rayo", "Repuestos El Rayo", ["kiosco"], "#495057", H_PARTIDO, "gratis",
     dict(subcategoria="Repuestos para autos, baterías, filtros y lubricantes", galeria=1)),
    ("pintureria-color", "Pinturería Color", ["bazar"], "#f76707", H_CORRIDO, "gratis",
     dict(subcategoria="Pinturas, rodillos, herramientas y ferretería", galeria=1)),
    ("libreria-punto-final", "Librería Punto Final", ["jugueteria"], "#495057", H_PARTIDO, "gratis",
     dict(subcategoria="Libros, fotocopias y útiles", galeria=1, baja_admin=True)),
]

COMERCIOS_YACUIBA = [
    ("importadora-chaco", "Importadora Chaco", ["importadora"], "#1c7ed6", H_PARTIDO),
    ("zapatillas-yacuiba", "Zapatillas Yacuiba", ["calzado"], "#7048e8", H_CORRIDO),
    ("restaurante-el-gaucho", "Restaurante El Gaucho", ["restaurantes"], "#e8590c", H_TODOS),
    ("celulares-yacuiba-center", "Celulares Yacuiba Center", ["celulares"], "#1098ad", H_TODOS),
    ("cambios-frontera-sur", "Cambios Frontera Sur", ["cambio"], "#f08c00", H_CORRIDO),
]

PORTADAS_FOTO = {"bazar-la-economia": ("comercios3.png", 0), "ropa-americana-toti": ("comercios2.png", 1),
                 "telas-hilo-de-oro": ("comercios4.png", 1), "jugueteria-arcoiris": ("comercios6.png", 0),
                 "casa-de-cambio-el-puente": ("comercio5.png", 1)}

# Ofertas aprobadas: comercio, título, precio, descuento, color, días de vigencia
OFERTAS = [
    ("boutique-ejemplo", "Jeans tiro alto", 180, 25, "#3b5bdb", 6),
    ("boutique-ejemplo", "Blusas de temporada", 95, 20, "#d6336c", 4),
    ("boutique-ejemplo", "Carteras de cuero sintético", 150, None, "#a0522d", 10),
    ("celulares-frontera", "Auriculares inalámbricos", 120, 30, "#1971c2", 5),
    ("celulares-frontera", "Fundas para celular 3x2", 60, None, "#495057", 7),
    ("supermercado-la-canasta", "Aceite 900 ml", 16, 10, "#f59f00", 3),
    ("supermercado-la-canasta", "Pack de gaseosas", 45, 15, "#c92a2a", 5),
    ("zapateria-paso-firme", "Zapatillas urbanas", 260, 20, "#5c7cfa", 8),
    ("restaurante-don-lucho", "Almuerzo completo", 25, None, "#c92a2a", 2),
    ("panaderia-el-sol", "Torta de cumpleaños", 90, None, "#e8590c", 9),
    ("perfumeria-aroma", "Perfumes importados", 220, 35, "#be4bdb", 6),
    ("electro-hogar-bermejo", "Licuadora 1,5 L", 310, 15, "#364fc7", 12),
    ("deportes-cancha-libre", "Camisetas de fútbol", 85, 20, "#37b24d", 5),
    ("ferreteria-el-tornillo", "Taladro percutor", 420, 10, "#868e96", 14),
    ("licoreria-la-bodega", "Singani 750 ml", 55, None, "#862e9c", 4),
    ("heladeria-polo-sur", "Helado de 1 kg", 40, 20, "#15aabf", 3),
]
NOVEDADES = [
    ("boutique-ejemplo", "Llegó la colección de primavera", "#f783ac"),
    ("celulares-frontera", "Nuevos modelos de celulares", "#1971c2"),
    ("muebleria-roble", "Roperos a medida", "#a0522d"),
    ("hotel-rio-bermejo", "Habitaciones renovadas", "#0ca678"),
    ("restaurante-don-lucho", "Parrillada los domingos", "#c92a2a"),
]
# Pendientes: comercio, tipo, título, precio, origen, veredicto IA
PENDIENTES = [
    ("boutique-ejemplo", "oferta", "Vestidos de fiesta", 240, "panel", ("aprobar", "Foto clara, precio y producto coinciden.", 0.88)),
    ("ferreteria-el-tornillo", "oferta", "Pintura látex 20 L", 380, "whatsapp", ("dudoso", "El precio no se lee en la foto.", 0.52)),
    ("kiosco-la-esquina", "oferta", "Combo golosinas", 15, "explorador", None),
    ("motos-del-sur", "novedad", "Llegaron cascos certificados", None, "whatsapp", None),
    ("boliche-luna", "video", "Noche de karaoke", None, "whatsapp", ("rechazar", "No muestra un producto ni una oferta.", 0.61)),
    ("jugueteria-arcoiris", "oferta", "Mochilas escolares", 70, "whatsapp", ("aprobar", "Oferta clara de un producto del rubro.", 0.81)),
]


def dentro_de_bermejo(i: int) -> tuple[float, float]:
    r = random.Random(f"gps{i}")
    return round(-22.733 + r.uniform(-0.0055, 0.0055), 6), round(-64.338 + r.uniform(-0.0055, 0.0055), 6)


def codigo_de(slug: str) -> str:
    r = random.Random("codigo" + slug)
    return "".join(r.choice("23456789ABCDEFGHJKMNPQRSTUVWXYZ") for _ in range(4))


# ─────────────────────────────────────────────── semilla
def sembrar() -> None:
    print(f"Fotos en {FOTOS} — servidas en {settings.fotos_public_base_url}")
    ciudad = {s: valor(f"select id from ciudades where slug = '{s}'") for s in ("bermejo", "yacuiba")}
    rubro = dict(l.split("|") for l in valor("select slug, id from rubros").splitlines())

    # ── ciudades, zonas, lugares, contenido de la home
    SQL.append("update ciudades set activa = true where slug in ('bermejo', 'yacuiba');")
    # El mapa sale del caché de teselas de la demo (NEXT_PUBLIC_TILES_URL), nunca de uno de producción.
    SQL.append("update ciudades set tiles_url = null, tiles_tipo = 'raster' where tiles_url is not null;")
    zonas = [("centro", "Centro", "#2f9e44"), ("mercado-central", "Mercado Central", "#f08c00"),
             ("zona-puente", "Zona del Puente", "#1971c2"), ("barrio-lapacho", "Barrio Lapacho", "#d6336c")]
    upsert("zonas", [{"id": uid("zona", s), "slug": s, "nombre": n, "color": c, "orden": i, "activo": True,
                      "ciudad_id": ciudad["bermejo"]} for i, (s, n, c) in enumerate(zonas)])
    lugares = {"galeria": ("Galería Comercial Central", "galeria", -22.7318, -64.3392, "Bermejo-plaza.png"),
               "mercado": ("Mercado Central", "mercado", -22.7346, -64.3365, "comercios3.png")}
    filas = []
    for k, (n, t, la, ln, foto) in lugares.items():
        # Sin portada: el mapa del panel dibuja la foto del lugar a tamaño completo y tapa los pines.
        filas.append({"id": uid("lugar", k), "nombre": n, "tipo": t, "ciudad_id": ciudad["bermejo"], "lat": la,
                      "lng": ln, "activo": True, "portada_url": None, "portada_thumb_url": None})
    upsert("lugares", filas)
    for clave, v in (("usd_bob", 6.96), ("usd_ars", 1380), ("ars_bob", 5.2), ("brl_bob", 1.27), ("pen_bob", 1.86)):
        SQL.append(f"update cotizaciones set valor = {v}, actualizado_en = now() where clave = '{clave}';")
    SQL.append("update clima set temp_c = 27, descripcion = 'Parcialmente nublado', icono = '⛅', "
               "fuente = 'demo', override_hasta = now() + interval '365 days', actualizado_en = now();")
    SQL.append("update frontera_estado set puente = 'normal', chalanas = 'operando', rio = 'normal', "
               "nota = 'Paso habilitado (dato de demo)', actualizado_en = now(), actualizado_por = 'publicador@demo.test';")
    ejecutar("ciudades, zonas, lugares, cotizaciones")

    # ── equipo del panel
    filas, roles = [], []
    for email, nombre, rs, ciu in EQUIPO:
        u = uid("panel", email)
        filas.append({"id": u, "email": email, "password_hash": auth.hash_password(CLAVE_PANEL), "nombre": nombre,
                      "ciudad_id": ciudad[ciu], "activo": True, "creado_por": "semilla-demo",
                      "ultimo_acceso": AHORA - timedelta(hours=RNG.randint(1, 60))})
        roles += [{"usuario_id": u, "rol_slug": r} for r in rs]
    upsert("usuarios_panel", filas)
    upsert("usuario_roles", roles, clave="usuario_id,rol_slug", nada=True)
    ejecutar("equipo del panel")

    # ── comercios de Bermejo
    filas, rubros_c, fotos_c, pagos = [], [], [], []
    for i, (slug, nombre, rubs, color, horario, plan, x) in enumerate(COMERCIOS):
        cid = uid("comercio", slug)
        lat, lng = dentro_de_bermejo(i)
        if x.get("lugar"):
            la, ln = lugares[x["lugar"]][2:4]
            lat, lng = round(la + RNG.uniform(-.0002, .0002), 6), round(ln + RNG.uniform(-.0002, .0002), 6)
        if i >= len(COMERCIOS) - 14 and not x.get("lugar"):
            # Las cargas del agente, en el radio que recorre (alrededor de la galería):
            # así «Qué hay acá» muestra locales cargados a menos de 150 m.
            r = random.Random(f"agente{i}")
            lat, lng = round(-22.7318 + r.uniform(-.0011, .0011), 6), round(-64.3392 + r.uniform(-.0011, .0011), 6)
        tild = x.get("tildes", (0, 0, 0, 0))
        portada = thumb = None
        if not x.get("sin_foto"):
            if slug in PORTADAS_FOTO:
                img = foto_publica(*PORTADAS_FOTO[slug])
            else:
                img = imagen_vidriera(nombre, color)
            portada, thumb = guardar(img, f"{slug}/portada.jpg")
        for g in range(x.get("galeria", 0)):
            img = imagen_vidriera(nombre, color, g + 1) if g % 3 == 0 else \
                imagen_producto(f"{nombre.split()[0]} {g + 1}", color)
            u, t = guardar(img, f"{slug}/galeria-{g + 1}.jpg")
            fotos_c.append({"id": uid("foto", slug, str(g)), "comercio_id": cid, "url": u, "thumb_url": t,
                            "orden": g + 1, "created_at": AHORA - timedelta(days=g)})
        pago_dias = x.get("pago_dias")
        paga_hasta = HOY + timedelta(days=pago_dias) if pago_dias is not None else None
        creado = AHORA - timedelta(days=RNG.randint(3, 75), hours=RNG.randint(0, 8))
        # Las últimas 12 son cargas del agente en los últimos días (Cargas, «Qué hay acá»).
        cargado_por = AGENTE if i >= len(COMERCIOS) - 14 else "admin@demo.test"
        if cargado_por == AGENTE:
            dia = (len(COMERCIOS) - i) % 4
            creado = (datetime.combine(HOY - timedelta(days=dia), datetime.min.time(), BOLIVIA)
                      + timedelta(hours=9 + (i % 6), minutes=7 * (i % 8)))
        calle = CALLES[i % len(CALLES)]
        filas.append({
            "id": cid, "slug": slug, "nombre": nombre, "descripcion": x.get("descripcion") or f"{x['subcategoria']}. Atención en {calle}.",
            "portada_url": portada, "portada_thumb_url": thumb, "portada_pos": 50 if portada else None,
            "whatsapp": x.get("whatsapp") or f"5917000{1100 + i:04d}",
            "telefono": f"4{6960000 + i * 37}" if i % 3 == 0 else None,
            "instagram_url": f"https://www.instagram.com/demo.{slug}" if x.get("redes") else None,
            "facebook_url": f"https://www.facebook.com/demo.{slug}" if x.get("redes") else None,
            "tiktok_url": f"https://www.tiktok.com/@demo.{slug}" if x.get("redes") and i % 2 == 0 else None,
            "zona_id": uid("zona", zonas[i % len(zonas)][0]),
            "direccion": f"{calle} {100 + i * 13}", "calle": calle, "lat": lat, "lng": lng,
            "plan": plan, "paga_hasta": paga_hasta, "plan_cortesia": bool(x.get("cortesia")),
            "suspendido": bool(x.get("suspendido")),
            "verificado": bool(x.get("verificado")), "confiable": bool(x.get("confiable")),
            "modalidad": x.get("modalidad", "minorista"), "rubro_id": rubro[rubs[0]], "ciudad_id": ciudad["bermejo"],
            "monedas_aceptadas": A(["BOB", "ARS", "USD"] if i % 2 == 0 else ["BOB", "ARS"]),
            "tiene_pasero": bool(tild[0]), "envios_internacionales": bool(tild[1]), "tiene_factura": bool(tild[2]),
            "talles_especiales": bool(tild[3]), "horario": horario, "horario_estimado": False,
            "subcategoria": x["subcategoria"], "codigo": codigo_de(slug), "fuente": "demo",
            "cargado_por": cargado_por, "capturado_en": creado, "created_at": creado,
            "activo": not (x.get("borrador") or x.get("baja_admin")),
            "baja_motivo": "borrador" if x.get("borrador") else "admin" if x.get("baja_admin") else None,
            "acepta_reservas": i % 4 == 0,
            "lugar_id": uid("lugar", x["lugar"]) if x.get("lugar") else None,
            "puesto": f"Puesto {10 + i}" if x.get("lugar") else None,
            "catalogo_url": f"{settings.fotos_public_base_url}/catalogos/{slug}.pdf" if x.get("catalogo") else None,
            "canal_wa_url": "https://whatsapp.com/channel/DEMO000000000000000" if x.get("redes") else None,
            "pedido_minimo": "Bs 300 por mayor" if x.get("modalidad") == "mayorista" else None,
            "alta_uid": uid("alta", slug),
        })
        rubros_c += [{"comercio_id": cid, "rubro_id": rubro[r]} for r in rubs]
        if paga_hasta and not x.get("cortesia"):
            precio = {"publica": 70, "destacado": 140, "pro": 400}[plan]
            pagos.append({"id": uid("pago", slug), "comercio_id": cid, "monto": precio, "moneda": "BOB",
                          "metodo": "qr", "referencia": f"DEMO-{i:04d}", "periodo_desde": paga_hasta - timedelta(days=30),
                          "periodo_hasta": paga_hasta, "registrado_por": "admin@demo.test", "estado": "confirmado",
                          "created_at": AHORA - timedelta(days=30 - (pago_dias or 0))})
        if x.get("pago_pendiente"):
            u, _ = guardar(imagen_comprobante(nombre, "Bs 70,00"), f"{slug}/comprobante-demo.jpg")
            pagos.append({"id": uid("pago-pend", slug), "comercio_id": cid, "monto": 70, "moneda": "BOB", "metodo": "qr",
                          "referencia": "Comprobante subido desde Mi comercio", "periodo_desde": HOY,
                          "periodo_hasta": HOY + timedelta(days=30), "registrado_por": "comercio", "estado": "pendiente",
                          "comprobante_url": u, "created_at": AHORA - timedelta(hours=5)})

    for i, (slug, nombre, rubs, color, horario) in enumerate(COMERCIOS_YACUIBA):
        cid = uid("comercio", slug)
        r = random.Random(slug)
        portada, thumb = guardar(imagen_vidriera(nombre, color), f"{slug}/portada.jpg")
        filas.append({
            "id": cid, "slug": slug, "nombre": nombre, "descripcion": f"Comercio de demo en Yacuiba ({nombre}).",
            "portada_url": portada, "portada_thumb_url": thumb, "portada_pos": 50,
            "whatsapp": f"5917000{1300 + i:04d}", "direccion": f"Avenida San Martín {200 + i * 40}",
            "calle": "Avenida San Martín", "lat": round(-22.0146 + r.uniform(-.004, .004), 6),
            "lng": round(-63.6775 + r.uniform(-.004, .004), 6), "plan": "gratis", "verificado": i % 2 == 0,
            "modalidad": "ambos", "rubro_id": rubro[rubs[0]], "ciudad_id": ciudad["yacuiba"], "horario": horario,
            "subcategoria": nombre, "codigo": codigo_de(slug), "fuente": "demo", "activo": True,
            "cargado_por": "agente.yacuiba@demo.test", "capturado_en": AHORA - timedelta(days=i + 1),
            "created_at": AHORA - timedelta(days=i + 1), "monedas_aceptadas": A(["BOB", "ARS"]),
            "alta_uid": uid("alta", slug),
        })
        rubros_c += [{"comercio_id": cid, "rubro_id": rubro[x]} for x in rubs]
    upsert("comercios", filas)
    upsert("comercio_rubros", rubros_c, clave="comercio_id,rubro_id", nada=True)
    upsert("comercio_fotos", fotos_c)
    upsert("pagos", pagos)
    ejecutar(f"{len(filas)} comercios, {len(fotos_c)} fotos de galería, {len(pagos)} pagos")

    # ── cuenta del comercio demo y comprador
    cid_demo = uid("comercio", COMERCIO_DEMO_SLUG)
    assert clave_comercio.es_clave(COMERCIO_DEMO_CLAVE)
    upsert("comercio_usuarios", [{"id": uid("cuenta", COMERCIO_DEMO_SLUG), "comercio_id": cid_demo,
                                  "nombre": "Dueña de Boutique Ejemplo", "activo": True,
                                  "clave_hash": clave_comercio.hash_clave(COMERCIO_DEMO_CLAVE),
                                  "credenciales_version": 1}])
    upsert("comercio_numeros", [{"id": uid("numero", COMERCIO_DEMO_SLUG), "comercio_id": cid_demo,
                                 "numero": COMERCIO_DEMO_WA, "etiqueta": "Dueña", "verificado": True, "activo": True,
                                 "created_by": "admin@demo.test"}])
    comprador = uid("comprador", COMPRADOR_WA)
    upsert("usuarios", [{"id": comprador, "whatsapp": COMPRADOR_WA, "activo": True,
                         "clave_hash": clave_usuario.hash_clave(COMPRADOR_CLAVE), "verificado_en": AHORA - timedelta(days=9),
                         "consentimiento_ofertas": True, "consentimiento_en": AHORA - timedelta(days=9),
                         "created_at": AHORA - timedelta(days=9)}])
    upsert("favoritos", [{"id": uid("fav", s), "usuario_id": comprador, "comercio_id": uid("comercio", s),
                          "activo": True} for s in ("boutique-ejemplo", "celulares-frontera", "restaurante-don-lucho")])
    # Otros compradores (para «Compradores» del admin)
    upsert("usuarios", [{"id": uid("comprador", str(n)), "whatsapp": f"5917000{2200 + n:04d}", "activo": True,
                         "verificado_en": AHORA - timedelta(days=n * 2), "created_at": AHORA - timedelta(days=n * 2),
                         "ref": ["volante", "qr-mercado", None][n % 3]} for n in range(1, 9)])
    upsert("comercio_wa_grupos", [{"grupo_jid": "120363000000000001@g.us", "comercio_id": cid_demo,
                                   "nombre": "Boutique Ejemplo × URUKU", "origen": "panel", "created_by": "admin@demo.test"}],
           clave="grupo_jid")
    ejecutar("cuenta de comercio, comprador y favoritos")

    # ── publicaciones
    pubs, cola = [], []
    for n, (slug, titulo, precio, desc, color, vig) in enumerate(OFERTAS):
        pid = uid("oferta", slug, titulo)
        url, _ = guardar(imagen_producto(titulo, color, f"Bs {precio}", desc), f"publicaciones/{pid}.jpg")
        aprobada = AHORA - timedelta(hours=3 + n * 5)
        pubs.append({"id": pid, "comercio_id": uid("comercio", slug), "tipo": "oferta", "titulo": titulo,
                     "descripcion": f"{titulo}. Consultá talles, colores y stock por WhatsApp.", "precio": precio,
                     "moneda": "BOB", "imagen_url": url, "estado": "aprobado", "origen": ["whatsapp", "panel"][n % 2],
                     "activo": True, "created_at": aprobada - timedelta(minutes=40), "approved_at": aprobada,
                     "moderado_por": "moderador@demo.test", "moderado_at": aprobada, "descuento_pct": desc,
                     "vence_el": HOY + timedelta(days=vig), "wa_message_id": f"demo-{pid}"})
        if n < 4:
            cola.append({"id": uid("difusion", pid), "publicacion_id": pid, "destino": "wa_canal",
                         "estado": ["enviado", "pendiente", "omitido", "enviado"][n], "intentos": 1})
    for n, (slug, titulo, color) in enumerate(NOVEDADES):
        pid = uid("novedad", slug, titulo)
        img = imagen_vidriera(titulo, color, 2) if n % 2 else imagen_producto(titulo, color)
        url, _ = guardar(img, f"publicaciones/{pid}.jpg")
        aprobada = AHORA - timedelta(hours=8 + n * 11)
        pubs.append({"id": pid, "comercio_id": uid("comercio", slug), "tipo": "novedad", "titulo": titulo,
                     "descripcion": f"{titulo}. Pasá a conocerlo.", "imagen_url": url, "estado": "aprobado",
                     "origen": "panel", "activo": True, "created_at": aprobada, "approved_at": aprobada,
                     "moderado_por": "moderador@demo.test", "moderado_at": aprobada, "wa_message_id": f"demo-{pid}"})
    for n, (slug, tipo, titulo, precio, origen, ia) in enumerate(PENDIENTES):
        pid = uid("pendiente", slug, titulo)
        url = None
        if tipo != "video":
            url, _ = guardar(imagen_producto(titulo, "#5c7cfa" if n % 2 else "#e8590c",
                                             f"Bs {precio}" if precio else None), f"publicaciones/{pid}.jpg")
        fila = {"id": pid, "comercio_id": uid("comercio", slug), "tipo": tipo, "titulo": titulo,
                "descripcion": f"{titulo} — mandado por {origen}.", "precio": precio, "moneda": "BOB",
                "imagen_url": url, "estado": "pendiente", "origen": origen, "activo": True,
                "created_at": AHORA - timedelta(minutes=25 + n * 47), "wa_message_id": f"demo-{pid}",
                "tiktok_url": "https://www.tiktok.com/@demo.uruku/video/7000000000000000001" if tipo == "video" else None,
                "identidad_origen": "explorador" if origen == "explorador" else None,
                "codigo_recibido": f"URUKU-{codigo_de(slug)}" if origen in ("whatsapp", "explorador") else None}
        if ia:
            fila.update({"ia_veredicto": ia[0], "ia_motivo": ia[1], "ia_confianza": ia[2],
                         "ia_revisado_at": AHORA - timedelta(minutes=10 + n * 40)})
        pubs.append(fila)
    for estado, slug, titulo, motivo in (("cambios", "boutique-ejemplo", "Remeras 2x1", "Falta el precio en la foto."),
                                         ("rechazado", "boutique-ejemplo", "Sorteo en Facebook", "No es una oferta de un producto."),
                                         ("rechazado", "kiosco-la-esquina", "Foto borrosa", "No se ve el producto.")):
        pid = uid(estado, slug, titulo)
        url, _ = guardar(imagen_producto(titulo, "#868e96"), f"publicaciones/{pid}.jpg")
        pubs.append({"id": pid, "comercio_id": uid("comercio", slug), "tipo": "oferta", "titulo": titulo,
                     "imagen_url": url, "estado": estado, "motivo_moderacion": motivo, "origen": "panel", "activo": True,
                     "moderado_por": "moderador@demo.test", "moderado_at": AHORA - timedelta(days=1),
                     "created_at": AHORA - timedelta(days=1, hours=2), "wa_message_id": f"demo-{pid}"})
    upsert("publicaciones", pubs)
    upsert("difusion_cola", cola)
    ejecutar(f"{len(pubs)} publicaciones")

    # ── catálogo de productos (Mi comercio / ficha)
    prods = []
    for slug, items, color in (("boutique-ejemplo", [("Jean mom", 170), ("Blusa lino", 90), ("Campera de jean", 230),
                                                     ("Vestido floreado", 160)], "#d6336c"),
                               ("celulares-frontera", [("Cargador rápido", 45), ("Parlante bluetooth", 140),
                                                       ("Smartwatch", 260)], "#1971c2")):
        for n, (nom, precio) in enumerate(items):
            pid = uid("producto", slug, nom)
            url, _ = guardar(imagen_producto(nom, color, f"Bs {precio}"), f"{slug}/producto-{n + 1}.jpg")
            prods.append({"id": pid, "comercio_id": uid("comercio", slug), "nombre": nom, "precio": precio, "moneda": "BOB",
                          "foto_url": url, "descripcion": f"{nom} — varios talles y colores.", "destacado": n == 0,
                          "activo": True})
    upsert("productos", prods)
    ejecutar(f"{len(prods)} productos")

    # ── novedades de URUKU
    novs = []
    for n, (titulo, texto, foto, color) in enumerate((
            ("URUKU llega a Yacuiba", "Ya podés buscar comercios de Yacuiba desde el mismo sitio.", None, "#1971c2"),
            ("Farmacias de turno, todos los días", "En el inicio ves qué farmacia atiende las 24 horas hoy.", None, "#2f9e44"),
            ("Feria de primavera en la plaza", "Este sábado, comercios de Bermejo con descuentos en la plaza principal.",
             "Bermejo-plaza.png", "#d6336c"))):
        nid = uid("novedad-uruku", titulo)
        img = foto_publica(foto) if foto else imagen_cartel(titulo, "Novedades de URUKU · demo", color)
        url, th = guardar(img, f"uruku/novedades/{nid}/portada.jpg")
        fotos = []
        for k in range(2 if n == 2 else 0):
            u, t = guardar(imagen_cartel(f"Foto {k + 1}", titulo, color), f"uruku/novedades/{nid}/foto-{k + 1}.jpg")
            fotos.append({"url": u, "thumb_url": t})
        novs.append({"id": nid, "ciudad_id": ciudad["bermejo"] if n else None, "titulo": titulo, "texto": texto,
                     "fecha": HOY - timedelta(days=n * 3), "portada_url": url, "portada_thumb_url": th, "fotos": J(fotos),
                     "destacada": n == 0, "activo": True, "created_by": "publicador@demo.test"})
    upsert("novedades_uruku", novs)
    ejecutar("novedades de URUKU")

    # ── bandeja de WhatsApp, reclamos, mensajes, cambio de número
    inbox = []
    for n, (res, body, slug, motivo) in enumerate((
            ("publicada", "URUKU-{c} Jeans tiro alto a Bs 180", "boutique-ejemplo", None),
            ("publicada", "Oferta: aceite 900 ml a Bs 16", "supermercado-la-canasta", None),
            ("sin_comercio", "Hola, quiero publicar mi negocio", None, "No trae código ni viene de un grupo atado"),
            ("ignorada", "Buen día", "boutique-ejemplo", "Mensaje sin foto ni oferta"),
            ("sin_comercio", "Precio de las zapatillas?", None, "Número desconocido"),
            ("error", "[imagen]", "ferreteria-el-tornillo", "No se pudo bajar la foto (demo)"))):
        cod = codigo_de(slug) if slug else ""
        inbox.append({"id": uid("inbox", str(n)), "wa_message_id": f"demo-inbox-{n}",
                      "wa_jid": "120363000000000001@g.us" if n == 0 else f"5917000{3300 + n:04d}@c.us",
                      "phone": f"5917000{3300 + n:04d}", "tipo": "image" if n % 2 == 0 else "text",
                      "body": body.format(c=cod), "raw": J({"demo": True}), "procesado": True, "resultado": res,
                      "motivo": motivo, "comercio_id": uid("comercio", slug) if slug else None,
                      "created_at": AHORA - timedelta(minutes=30 + n * 70), "via": "waha"})
    upsert("wa_inbox", inbox)
    upsert("reclamos", [
        {"id": uid("reclamo", "1"), "nombre": "Lucía (demo)", "contacto": "59170004401", "comercio_id": uid("comercio", "zapateria-paso-firme"),
         "mensaje": "El horario de la ficha no coincide: el sábado a la tarde estaba cerrado.", "estado": "pendiente",
         "created_at": AHORA - timedelta(hours=6)},
        {"id": uid("reclamo", "2"), "nombre": "Jorge (demo)", "contacto": "59170004402", "comercio_id": uid("comercio", "hotel-rio-bermejo"),
         "mensaje": "El número de WhatsApp no contesta.", "estado": "respondido",
         "respuesta": "Gracias, lo verificamos con el hotel y ya está actualizado.", "respondido_por": "moderador@demo.test",
         "respondido_en": AHORA - timedelta(days=1), "created_at": AHORA - timedelta(days=2)}])
    upsert("mensajes", [
        {"id": uid("mensaje", str(n)), "comercio_id": cid_demo, "autor": a, "nombre": nom, "contacto": con, "cuerpo": txt,
         "leido": n > 0, "created_at": AHORA - timedelta(hours=2 + n * 20)}
        for n, (a, nom, con, txt) in enumerate((
            ("cliente", "Mariela", "59170005501", "¿Tienen jeans talle 44?"),
            ("admin", "URUKU", None, "¡Bienvenida a URUKU! Cualquier duda escribinos."),
            ("cliente", "Romina", "59170005502", "¿Hacen envíos a Orán?")))])
    upsert("solicitudes_cambio_numero", [{"id": uid("cambio-numero", "1"), "comercio_id": uid("comercio", "optica-vision-clara"),
                                          "whatsapp_nuevo": "59170006601", "mensaje": "Cambié de celular, este es el nuevo.",
                                          "estado": "pendiente", "created_at": AHORA - timedelta(hours=4),
                                          "lat": -22.7331, "lng": -64.3371}])
    ejecutar("bandeja, reclamos, mensajes, cambio de número")

    # ── métricas: visitas, contactos y búsquedas de los últimos 30 días (SQL, para que sea rápido)
    slugs = [c[0] for c in COMERCIOS[:20]]
    SQL.append(f"""
delete from visitas where sesion like 'demo-%';
insert into visitas (dia, ruta, sesion, origen, ciudad_slug, primera, created_at)
select d::date, r.ruta, 'demo-' || d::date || '-' || g || '-' || r.n, (array['directo','google','whatsapp','qr'])[1 + (g % 4)],
       'bermejo', g % 3 = 0, d + make_interval(hours => (9 + (g % 12))::int)
  from generate_series(current_date - 29, current_date, interval '1 day') d,
       generate_series(1, 18 + (extract(doy from current_date)::int % 7)) g,
       lateral (select n, ruta from unnest(array['/','/buscar','/ofertas','/mapa','/comercios/boutique-ejemplo',
               '/farmacias-de-turno','/cambio','/novedades']) with ordinality as t(ruta, n)) r
 where (g + r.n + extract(day from d)::int) % 3 = 0;
delete from leads where origen = 'demo';
insert into leads (comercio_id, tipo, origen, created_at, respondio)
select c.id, (array['vista','vista','vista','whatsapp','telefono'])[1 + ((g + k) % 5)], 'demo',
       now() - make_interval(days => ((g * 7 + k) % 30)::int, hours => ((g + k) % 10)::int), case when g % 4 = 0 then true end
  from (select id, row_number() over (order by slug) k from comercios where slug = any(array[{",".join(lit(s) for s in slugs)}])) c,
       generate_series(1, 4 + (c.k % 9)::int * 3) g;
""")
    consultas = ["zapatillas", "jeans", "celulares", "farmacia", "cambio dolar", "helado", "almuerzo", "taladro",
                 "colchon", "perfume", "lentes", "hotel", "mochilas", "heladera", "fundas", "pañales", "bicicleta"]
    busq = []
    for n in range(140):
        q = consultas[(n * 7) % len(consultas)]
        busq.append({"id": uid("busqueda", str(n)), "query": q, "resultados": 0 if q in ("pañales", "bicicleta") else 1 + n % 6,
                     "created_at": AHORA - timedelta(hours=n * 5 % 700)})
    upsert("busquedas", busq)
    ejecutar("visitas, contactos y búsquedas")


def importar_farmacias() -> None:
    """El rol real de farmacias, con teléfonos ficticios, por el comando del backend."""
    origen = RAIZ / "backend/data/turnos_farmacia/bermejo-2026-10-04_2026-12-12.json"
    data = json.loads(origen.read_text(encoding="utf-8"))
    for n, f in enumerate(data["farmacias"]):
        f["celular"] = f"7000{4500 + n:04d}"
        f["fijo"] = None
        f["nota_interna"] = None
        f.pop("slug", None)           # en producción apunta a fichas que ya existen; acá se crean
        if f.get("lat") is None:      # las que no traen GPS: un punto ficticio dentro de Bermejo
            f["lat"], f["lng"] = dentro_de_bermejo(500 + n)
            f["ubicacion_aproximada"] = True
    destino = FOTOS.parent / "turnos-farmacia-demo.json"
    destino.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print("  farmacias de turno (teléfonos reemplazados):")
    p = subprocess.run([sys.executable, "-m", "app.scripts.importar_turnos_farmacia", str(destino)],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print("   ", (p.stdout or p.stderr).strip().replace("\n", "\n    "))
    if p.returncode != 0:
        raise SystemExit("Falló la importación de farmacias de turno")
    # Una portada para que la ficha de farmacia no quede vacía.
    for n, slug in enumerate(valor("select slug from comercios where fuente = 'turnos' order by slug").splitlines()):
        url, th = guardar(imagen_vidriera(valor(f"select nombre from comercios where slug = {lit(slug)}"), "#2f9e44", n % 3),
                          f"{slug}/portada.jpg")
        SQL.append(f"update comercios set portada_url = {lit(url)}, portada_thumb_url = {lit(th)}, portada_pos = 50, "
                   f"horario = coalesce(horario, {lit(H_PARTIDO)}) where slug = {lit(slug)};")
    ejecutar("portadas de farmacias")


def calles() -> None:
    """Calles de Bermejo: de OSM por el mismo servicio del endpoint; sin red, un puñado a mano."""
    from app.db.repository import get_repo
    from app.services import calles_mapa
    repo = get_repo()
    cid = valor("select id from ciudades where slug = 'bermejo'")
    hay = int(valor(f"select count(*) from calles_tramos where ciudad_id = '{cid}' and activo"))
    if not hay:
        try:
            r = calles_mapa.importar(repo, cid, repo.get_ciudad("bermejo"), calles_mapa.get_overpass())
            print(f"  calles desde OpenStreetMap: {r}")
        except Exception as exc:  # noqa: BLE001
            print(f"  OSM no respondió ({str(exc)[:120]}); siembro calles a mano")
        hay = int(valor(f"select count(*) from calles_tramos where ciudad_id = '{cid}' and activo"))
    if not hay:
        filas = []
        for n, nombre in enumerate(CALLES[:8]):
            horizontal = n % 2 == 0
            base = -22.7375 + n * 0.0011 if horizontal else -64.3425 + n * 0.0011
            for parte in range(4):
                if horizontal:
                    geom = [[base, -64.344 + parte * .0025], [base, -64.344 + (parte + 1) * .0025]]
                else:
                    geom = [[-22.7385 + parte * .0025, base], [-22.7385 + (parte + 1) * .0025, base]]
                filas.append({"id": uid("tramo", nombre, str(parte)), "ciudad_id": cid, "nombre": nombre,
                              "tipo": "residential", "geom": J(geom), "longitud_m": 260, "activo": True, "parte": parte})
        upsert("calles_tramos", filas)
        ejecutar(f"{len(filas)} tramos de calle a mano")
    # Marcas del recorrido, del centro hacia afuera: lo más cerca del centro ya está recorrido,
    # un anillo intermedio en «pendiente» o «sin comercios», y el resto sin marcar.
    filas = valor(f"select id, geom->0->>0, geom->0->>1 from calles_tramos where ciudad_id = '{cid}' and activo").splitlines()
    tramos = sorted(((float(la) + 22.733) ** 2 + (float(ln) + 64.338) ** 2, tid)
                    for tid, la, ln in (f.split("|") for f in filas))
    SQL.append("delete from calles_marcas where actor in ('agente@demo.test', 'admin@demo.test');")
    marcas = []
    for n, (_, tid) in enumerate(tramos):
        frac = n / max(1, len(tramos))
        if frac < .28:
            estado = "sin_comercios" if n % 9 == 4 else "recorrida"
        elif frac < .38:
            estado = "pendiente" if n % 2 else "recorrida"
        else:
            continue
        marcas.append({"id": uid("marca", tid), "tramo_id": tid, "estado": estado, "actor": AGENTE,
                       "created_at": AHORA - timedelta(days=n % 6, hours=n % 9)})
    ids = tramos
    upsert("calles_marcas", marcas)
    ejecutar(f"{len(marcas)} marcas de recorrido sobre {len(ids)} tramos")


def extras() -> None:
    """Lo que piden las pantallas del panel para no salir vacías."""
    bermejo = valor("select id from ciudades where slug = 'bermejo'")
    boutique = uid("comercio", COMERCIO_DEMO_SLUG)
    # Un rol con «moderar» pero sin «comercios.editar» (pantalla de sólo lectura) y su usuario.
    upsert("roles", [{"slug": "revisor", "nombre": "Revisor (demo)", "descripcion": "Mira y modera; no edita fichas.",
                      "permisos": A(["moderar"]), "del_sistema": False}], clave="slug")
    u = uid("panel", "revisor@demo.test")
    upsert("usuarios_panel", [{"id": u, "email": "revisor@demo.test", "password_hash": auth.hash_password(CLAVE_PANEL),
                               "nombre": "Pablo Revisor", "ciudad_id": bermejo, "activo": True, "creado_por": "semilla-demo"}])
    upsert("usuario_roles", [{"usuario_id": u, "rol_slug": "revisor"}], clave="usuario_id,rol_slug", nada=True)
    # «Le interesa un plan» anotado por el agente (chip «Interesado» en Suscripciones).
    upsert("comercio_eventos", [{"id": uid("evento", "interes", "ferreteria-el-tornillo"),
                                 "comercio_id": uid("comercio", "ferreteria-el-tornillo"), "tipo": "interes_plan",
                                 "actor": AGENTE, "detalle": J({"plan": "destacado", "nota": "Quiere salir primero en la búsqueda"}),
                                 "created_at": AHORA - timedelta(hours=20)}])
    # Importados (OSM) sin revisar.
    imp = []
    for n, (nom, cat, rub) in enumerate((("Ferretería San José", "hardware", "ferreteria"), ("Farmacia Central (OSM)", "pharmacy", "farmacia"),
                                         ("Panadería La Espiga", "bakery", "panaderia"), ("Taller El Chato", "car_repair", "taller-mecanico"),
                                         ("Boutique Ejemplo", "clothes", "ropa"), ("Bar La Esquina", "bar", "nocturna"))):
        la, ln = dentro_de_bermejo(700 + n)
        if nom == "Boutique Ejemplo":
            la, ln = valor(f"select lat || '|' || lng from comercios where id = '{boutique}'").split("|")
        imp.append({"id": uid("importado", nom), "fuente": "osm", "fuente_id": f"node/demo{n}", "ciudad_id": bermejo,
                    "nombre": nom, "categoria": cat, "rubro_slug": rub, "lat": float(la), "lng": float(ln),
                    "direccion": CALLES[n], "tags": J({"shop": cat}), "estado": "nuevo", "importado_at": AHORA - timedelta(days=3)})
    upsert("comercios_importados", imp)
    # Adornos del mapa: lapachos en la plaza y chalanas en el río.
    ad = [{"id": uid("adorno", "lapacho", str(n)), "ciudad_id": bermejo, "tipo": "lapacho", "lat": la, "lng": ln,
           "giro": 0, "escala": 1, "activo": True} for n, (la, ln) in enumerate(
        ((-22.7349, -64.3412), (-22.7352, -64.3405), (-22.7344, -64.3399), (-22.7339, -64.3418)))]
    ad += [{"id": uid("adorno", "chalana", str(n)), "ciudad_id": bermejo, "tipo": "chalana", "lat": la, "lng": ln,
            "giro": 20, "escala": 1, "activo": True} for n, (la, ln) in enumerate(((-22.7428, -64.3335), (-22.7436, -64.3318)))]
    upsert("mapa_adornos", ad)
    upsert("rubros_propuestos", [{"id": uid("propuesto", t), "texto": t, "normalizado": t.lower(),
                                  "comercio_id": uid("comercio", c), "created_at": AHORA - timedelta(days=1)}
                                 for t, c in (("Artículos de pesca", "bazar-la-economia"), ("Fotocopias", "jugueteria-arcoiris"),
                                              ("Cotillón", "regaleria-sorpresa"))])
    # Preguntas a la Ayuda del sitio sin respuesta, y al chatbot de la boutique.
    conv = []
    for n, (preg, com) in enumerate((("¿Dónde puedo cargar gas?", None), ("¿Hasta qué hora atiende migración?", None),
                                     ("¿Se puede pagar con tarjeta en el mercado?", None),
                                     ("¿Tienen jeans talle 46?", boutique), ("¿Hacen envíos a Tarija?", boutique),
                                     ("¿Atienden los domingos a la tarde?", boutique))):
        conv.append({"id": uid("conversacion", str(n)), "sesion": f"demo-sesion-{n}", "canal": "web", "comercio_id": com,
                     "pregunta": preg, "respuesta": "Todavía no tengo ese dato.", "nivel": 0, "sin_respuesta": True,
                     "created_at": AHORA - timedelta(hours=3 + n * 5)})
    upsert("asistente_conversaciones", conv)
    upsert("saber_local", [{"id": uid("saber", "boutique", str(n)), "pregunta": p, "respuesta": r, "comercio_id": boutique,
                            "ciudad_id": bermejo, "activo": True, "creado_por": "comercio", "seccion": "comercio"}
                           for n, (p, r) in enumerate((("¿Tienen talles grandes?", "Sí, hasta el talle 50 en jeans y blusas."),
                                                       ("¿Aceptan pesos?", "Sí: bolivianos, pesos argentinos y dólares.")))])
    upsert("leads", [{"id": uid("lead", "te-contesto"), "comercio_id": boutique, "tipo": "whatsapp", "origen": "demo-fijo",
                      "created_at": AHORA - timedelta(minutes=10)}])
    ejecutar("roles, interés, importados, adornos, propuestas, Ayuda y chatbot")


def datos_para_capturas() -> None:
    """Lo que el script de capturas necesita saber de esta semilla (ids, coordenadas)."""
    farm = valor("select slug || '|' || lat || '|' || lng || '|' || nombre from comercios "
                 "where fuente = 'turnos' and ubicacion_aproximada and activo order by slug limit 1").split("|")
    datos = {
        "comercio_prueba": {"slug": COMERCIO_DEMO_SLUG, "id": uid("comercio", COMERCIO_DEMO_SLUG), "nombre": "Boutique Ejemplo",
                            "whatsapp": COMERCIO_DEMO_WA[3:], "clave": COMERCIO_DEMO_CLAVE},
        "comercio_clave_admin": {"slug": "panaderia-el-sol", "nombre": "Panadería El Sol"},
        "comprador": {"whatsapp": COMPRADOR_WA[3:], "clave": COMPRADOR_CLAVE},
        "panel": {"clave": CLAVE_PANEL, **{rs[0]: email for email, _, rs, _ in EQUIPO if rs[0] != "agente"},
                  "agente": AGENTE, "revisor": "revisor@demo.test"},
        "novedad_uruku_id": uid("novedad-uruku", "Feria de primavera en la plaza"),
        "farmacia_aproximada": {"slug": farm[0], "lat": float(farm[1]), "lng": float(farm[2]), "nombre": farm[3]} if len(farm) == 4 else None,
        "agente_aca": {"lat": -22.7318, "lng": -64.3392},
        "lead_demo_id": uid("lead", "te-contesto"),
    }
    destino = FOTOS.parent / "demo-datos.json"
    destino.write_text(json.dumps(datos, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  datos para las capturas: {destino}")


def main() -> None:
    sembrar()
    importar_farmacias()
    calles()
    extras()
    datos_para_capturas()
    print("\nSemilla lista. Usuarios: scripts/demo/README.md")


if __name__ == "__main__":
    main()
