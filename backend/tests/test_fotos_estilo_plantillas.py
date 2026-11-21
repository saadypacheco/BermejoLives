"""Las plantillas del estilo URUKU (docs/fotos-estilo-uruku.md §1): portada 1600 x 1000 y galería 1080 x 1350. Sólo Pillow, sin red."""
import inspect
from io import BytesIO

import pytest
from PIL import Image

from app.services import fotos_estilo as fe, portada_diseno as pd

LOGO_PORTADA = (1236, 839, 1536, 936)


def _foto(w, h, color) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG", quality=95)
    return buf.getvalue()


def _portada(color="white", nombre="Ferretería El Sur", rubro="Ferretería", ciudad="Bermejo") -> Image.Image:
    jpeg = pd.armar_plantilla(_foto(1600, 1000, color), nombre, rubro, ciudad, None, mejorar=False)
    return Image.open(BytesIO(jpeg))


def _se_cruzan(a, b) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _todas_las_cajas_de_texto(d: dict) -> list[tuple]:
    c = d["cajas"]
    return [*c["nombre"], *(x for x in (c["kick"], c["ciudad"]) if x)]


# ══════════════════════════════════════════ portada

def test_portada_es_jpeg_1600x1000_q85():
    img = _portada()
    assert img.format == "JPEG" and img.size == (1600, 1000)


def test_el_logo_va_abajo_a_la_derecha_con_el_tamano_del_kit():
    d = pd.disponer_portada("Ferretería El Sur", "Ferretería", "Bermejo")
    x0, y0, x1, y1 = d["logo"]
    assert (x0, x1, y1) == (LOGO_PORTADA[0], LOGO_PORTADA[2], LOGO_PORTADA[3])
    assert 96 <= y1 - y0 <= 98                       # 300 de ancho -> ~97 de alto (1738 x 563)
    # y de verdad se dibuja ahí: el logo «color» trae dorado y rojo, que no hay en el resto de la esquina
    img = _portada("black", "Local", None, None).convert("RGB")
    dorados = sum(1 for x in range(x0, x1, 3) for y in range(y0, y1, 3)
                  if (lambda p: p[0] > 180 and p[1] > 120 and p[2] < 110)(img.getpixel((x, y))))
    assert dorados > 100


def test_no_hay_logo_ni_nada_arriba_a_la_derecha():
    img = _portada("white", "Local", None, None).convert("RGB")
    assert all(min(img.getpixel((x, y))) >= 250 for x in range(1250, 1520, 10) for y in range(44, 120, 10))


@pytest.mark.parametrize("nombre", [
    "Distribuidora Mayorista de Productos Importados y Nacionales del Sur Boliviano " * 2,   # > 120: se corta
    "A" * 200, "W" * 120, "Mi Local", "Almacén y Ferretería «El Tornillo Dorado» de Don José María Fernández 123456",
])
def test_la_caja_del_logo_no_se_cruza_con_el_texto_ni_con_120_caracteres(nombre):
    d = pd.disponer_portada(nombre, "Ferretería y herramientas de todo tipo", "Villa Montes del Chaco")
    assert len(d["lineas"]) <= 2 and 56 <= d["nombre_px"] <= 104
    for caja in _todas_las_cajas_de_texto(d):
        assert caja[0] >= 80 and caja[2] <= 1188, caja             # ningún texto pasa de x 1188
        assert not _se_cruzan(caja, d["logo"]), (caja, d["logo"])
        assert caja[3] <= 936                                      # el bloque se ancla abajo en y = 936


def test_el_texto_renderizado_no_pisa_la_columna_del_logo():
    """Con el nombre más largo posible: a la derecha de x 1188 (hasta el logo) no hay ni un píxel de texto blanco."""
    img = _portada("black", "W" * 130, "Rubro larguísimo de más de veintiocho letras", "Ciudad " * 12).convert("RGB")
    for y in range(600, 1000, 4):
        for x in range(1190, 1236, 3):
            assert max(img.getpixel((x, y))) < 200, (x, y)


def test_se_corta_con_puntos_suspensivos_el_nombre_a_120_y_el_kick_a_28():
    d = pd.disponer_portada("N" * 300, "R" * 90, None)
    assert d["kick"].endswith("…") and len(d["kick"]) == 28 and d["kick"] == d["kick"].upper()
    assert d["lineas"][-1].endswith("…") or sum(len(ln) for ln in d["lineas"]) <= 120


def test_el_kick_va_en_mayusculas_y_sin_rubro_no_va_kick():
    d = pd.disponer_portada("Local", "Ferretería", "Bermejo")
    assert d["kick"] == "FERRETERÍA" and d["cajas"]["kick"] is not None
    sin = pd.disponer_portada("Local", None, "Bermejo")
    assert sin["kick"] == "" and sin["cajas"]["kick"] is None


def test_sin_ciudad_no_va_la_ultima_linea_y_el_nombre_baja_al_ancla():
    d = pd.disponer_portada("Local", "Rubro", None)
    assert d["cajas"]["ciudad"] is None
    assert d["cajas"]["nombre"][-1][3] == 936
    con = pd.disponer_portada("Local", "Rubro", "Bermejo")
    assert con["cajas"]["ciudad"][3] == 936 and con["cajas"]["nombre"][-1][3] < 936


def test_la_franja_es_verde_oscura_y_no_negra():
    img = _portada("white", "Local", None, None).convert("RGB")
    r, g, b = img.getpixel((1000, 995))
    assert (r, g, b) != (0, 0, 0) and min(r, g, b) > 8
    assert g > b > r - 1 and g > r + 5             # `#08110C` sobre blanco: verde oscuro, nunca gris ni negro
    assert max(r, g, b) < 60                       # y oscuro
    # arriba de y = 420 la franja no existe: la foto blanca queda blanca
    assert min(img.getpixel((800, 300))) >= 250


def test_el_brillo_verde_detras_del_texto_es_mas_verde_que_lejos_del_texto():
    img = _portada("white", "Local", None, None).convert("RGB")
    cerca, lejos = img.getpixel((380, 960)), img.getpixel((1100, 960))
    assert cerca[1] - cerca[0] > lejos[1] - lejos[0]


def test_ni_la_plantilla_tine_la_foto_arriba():
    """Los colores de la foto no se tocan (el verde lo pone la plantilla): arriba de la franja la foto pasa tal cual."""
    img = _portada((200, 40, 40), "Local", None, None).convert("RGB")
    r, g, b = img.getpixel((800, 200))
    assert abs(r - 200) <= 6 and abs(g - 40) <= 6 and abs(b - 40) <= 6


def test_la_portada_se_arma_en_pocos_segundos():
    import time
    t0 = time.perf_counter()
    _portada()
    assert time.perf_counter() - t0 < 3.0


# ══════════════════════════════════════════ galería

def _tarjeta(color="white") -> Image.Image:
    return Image.new("RGB", (fe.TARJETA_ANCHO, fe.TARJETA_ALTO), color)


def test_galeria_es_1080x1350_y_la_miniatura_480x600():
    g = fe.plantilla_galeria(_tarjeta())
    assert g.size == (1080, 1350)
    jpeg = fe._jpeg(g)
    assert Image.open(BytesIO(jpeg)).format == "JPEG" and Image.open(BytesIO(jpeg)).size == (1080, 1350)
    miniatura = Image.open(BytesIO(fe.miniatura(g)))
    assert miniatura.format == "JPEG" and miniatura.size == (480, 600)


def test_la_tarjeta_de_la_galeria_tiene_que_medir_920x1150():
    with pytest.raises(ValueError):
        fe.plantilla_galeria(Image.new("RGB", (900, 1150)))


def test_el_logo_de_la_galeria_va_abajo_a_la_derecha_en_x_740_a_1000():
    x0, y0, x1, y1 = fe.caja_logo_galeria()
    assert (x0, x1) == (740, 1000) and 1206 <= y0 and y1 <= 1350 and 80 <= y1 - y0 <= 90
    g = fe.plantilla_galeria(_tarjeta("black")).convert("RGB")
    dorados = sum(1 for x in range(x0, x1, 3) for y in range(y0, y1, 3)
                  if (lambda p: p[0] > 180 and p[1] > 120 and p[2] < 110)(g.getpixel((x, y))))
    assert dorados > 100
    # y a la izquierda del logo, el texto `uruku.bo` (blanco)
    blancos = sum(1 for x in range(80, 300, 2) for y in range(1236, 1320, 2) if min(g.getpixel((x, y))) > 230)
    assert blancos > 50


def test_la_galeria_no_lleva_textos_de_la_base():
    """La plantilla no recibe nombre, rubro ni ciudad: lo único que dibuja es `uruku.bo` y el logo, siempre iguales."""
    assert list(inspect.signature(fe.plantilla_galeria).parameters) == ["foto"]
    a = fe.plantilla_galeria(_tarjeta("white")).convert("RGB")
    b = fe.plantilla_galeria(_tarjeta("red")).convert("RGB")
    pie = (0, fe.PIE_Y0, 1080, 1350)
    assert a.crop(pie).tobytes() == b.crop(pie).tobytes() or \
        max(abs(x - y) for x, y in zip(a.crop(pie).tobytes(), b.crop(pie).tobytes())) <= 8     # el halo se asoma apenas


def test_el_fondo_de_la_galeria_es_verde_y_no_negro_puro():
    g = fe.plantilla_galeria(_tarjeta()).convert("RGB")
    for punto in ((3, 3), (1076, 3), (3, 1346), (1076, 1346)):
        r, gg, b = g.getpixel(punto)
        assert (r, gg, b) != (0, 0, 0) and gg > b > r - 1 and gg > r + 3, (punto, (r, gg, b))
    # hay brillo verde alrededor de la tarjeta (más claro que el rincón)
    assert g.getpixel((40, 700))[1] > g.getpixel((3, 3))[1]


def test_la_tarjeta_tiene_esquinas_redondas_y_borde_verde_de_3px():
    g = fe.plantilla_galeria(_tarjeta("white")).convert("RGB")
    esquina = g.getpixel((fe.TARJETA_X + 2, fe.TARJETA_Y + 2))
    assert min(esquina) < 200                       # el vértice no es foto blanca: está recortado
    borde = g.getpixel((fe.TARJETA_X + 1, 700))
    assert borde[1] > 180 and borde[0] < 120        # `#34D27F`
    assert min(g.getpixel((fe.TARJETA_X + 20, 700))) >= 250      # adentro, la foto tal cual
    assert min(g.getpixel((fe.TARJETA_X + fe.TARJETA_ANCHO // 2, fe.TARJETA_Y + 20))) >= 250


def test_la_galeria_se_arma_en_pocos_segundos():
    import time
    t0 = time.perf_counter()
    fe.miniatura(fe.plantilla_galeria(_tarjeta()))
    assert time.perf_counter() - t0 < 3.0


# ══════════════════════════════════════════ recortes

@pytest.mark.parametrize("w,h,aspecto", [(4000, 3000, (3, 2)), (3000, 4000, (3, 2)), (4000, 3000, (4, 5)), (800, 600, (3, 2))])
def test_recortar_respeta_la_proporcion_y_nunca_pasa_de_1536(w, h, aspecto):
    img = Image.new("RGB", (w, h), "gray")
    out = fe.recortar(img, aspecto, 30, fe.GEMINI_LADO_MAX)
    assert max(out.size) <= 1536
    assert abs(out.size[0] / out.size[1] - aspecto[0] / aspecto[1]) < 0.01
    assert out.size[0] <= w and out.size[1] <= h            # nunca agranda


def test_recortar_ve_la_parte_que_dice_pos():
    img = Image.new("RGB", (1000, 3000), (0, 0, 200))
    img.paste(Image.new("RGB", (1000, 2100), (200, 0, 0)), (0, 900))
    # 3:2 sobre 1000 de ancho -> alto de 667; con pos=0 arranca arriba (azul) y con pos=100 abajo (rojo)
    assert fe.recortar(img, (3, 2), 0, 1536).getpixel((10, 10))[2] > 150
    assert fe.recortar(img, (3, 2), 100, 1536).getpixel((10, 10))[0] > 150


def test_recortar_nunca_crea_un_intermedio_enorme(monkeypatch):
    tamanos = []
    original = Image.Image.resize
    monkeypatch.setattr(Image.Image, "resize",
                        lambda self, size, *a, **kw: tamanos.append(tuple(size)) or original(self, size, *a, **kw))
    fe.recortar(Image.new("RGB", (6000, 4000), "gray"), (3, 2), 50, fe.GEMINI_LADO_MAX)
    assert max(t[0] * t[1] for t in tamanos) <= 1536 * 1024


def test_a_gemini_va_un_jpeg_de_a_lo_sumo_1536_px():
    jpeg = fe.jpeg_para_gemini(Image.new("RGB", (4000, 3000), "gray"), "cover", 50)
    img = Image.open(BytesIO(jpeg))
    assert img.format == "JPEG" and max(img.size) <= 1536 and img.size == (1536, 1024)
    g = Image.open(BytesIO(fe.jpeg_para_gemini(Image.new("RGB", (3000, 4000), "gray"), "gallery", None)))
    assert max(g.size) <= 1536 and abs(g.size[0] / g.size[1] - 0.8) < 0.01


def test_la_externa_con_alfa_se_pinta_sobre_blanco_y_pierde_el_exif():
    rgba = Image.new("RGBA", (800, 600), (0, 0, 0, 0))             # todo transparente
    buf = BytesIO()
    rgba.save(buf, format="PNG")
    img = fe._abrir_validada(buf.getvalue(), lado_menor_min=fe.EXTERNA_LADO_MENOR_MIN)
    assert img.mode == "RGB" and img.getpixel((10, 10)) == (255, 255, 255)
    assert not img.info.get("exif")


def test_la_externa_muy_chica_o_angosta_o_rota_se_rechaza():
    def png(w, h):
        buf = BytesIO()
        Image.new("RGB", (w, h)).save(buf, format="PNG")
        return buf.getvalue()
    with pytest.raises(pd.PortadaInadecuada):
        fe._abrir_validada(png(400, 400), lado_menor_min=512)
    with pytest.raises(pd.PortadaInadecuada):
        fe._abrir_validada(png(3000, 600), lado_menor_min=512)      # 5:1
    with pytest.raises(ValueError):
        fe._abrir_validada(b"basura", lado_menor_min=512)
