"""La portada «tarjeta» de los carruseles (docs/home-ciudades.md §11, migración 0202): el recorte 4:3 con la regla del
CSS, el puntaje de calidad (funciones puras), la tarjeta sobre un disco temporal, los ganchos (portada nueva,
portada de la galería, encuadre) y el comando de relleno. Sin red y sin IA."""
import math
import random
import re
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image, ImageFilter

from app.core.config import settings
from app.services import fotos_tarjeta as ft, portada, portada_diseno
from app.services.imagenes import guardar_foto_local

BASE = "https://api.test/fotos"


@pytest.fixture(autouse=True)
def _base_publica(monkeypatch):
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)


@pytest.fixture(autouse=True)
def _repo_con_copias(repo, monkeypatch):
    """La base real devuelve filas NUEVAS en cada lectura; el FakeRepo devuelve el mismo dict mutable. Acá se leen
    copias, como en producción: sin esto no se podría ver que «la portada cambió mientras se armaba»."""
    leer, escribir = repo.get_comercio, repo.update_comercio
    monkeypatch.setattr(repo, "get_comercio", lambda cid: (dict(leer(cid)) if leer(cid) else None))
    monkeypatch.setattr(repo, "update_comercio", lambda *a, **k: dict(escribir(*a, **k)))


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _bytes(img: Image.Image) -> bytes:
    buf = BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=92)
    return buf.getvalue()


def _ruido_color(w, h, semilla=1, amplitud=90):
    """Una foto sintética con detalle y color (ruido por canal alrededor de un naranja)."""
    rnd = random.Random(semilla)
    img = Image.new("RGB", (w, h))
    base = (180, 110, 60)
    img.putdata([tuple(max(0, min(255, c + rnd.randint(-amplitud, amplitud))) for c in base) for _ in range(w * h)])
    return img


def _franjas(w, h):
    """Una foto vertical en tres tercios: rojo arriba, verde en el medio y azul abajo."""
    img = Image.new("RGB", (w, h))
    t = h // 3
    img.paste((220, 30, 30), (0, 0, w, t))
    img.paste((30, 200, 30), (0, t, w, 2 * t))
    img.paste((30, 30, 220), (0, 2 * t, w, h))
    return img


def _abrir(b: bytes) -> Image.Image:
    return Image.open(BytesIO(b))


def _comercio(repo, **kw):
    base = dict(id="com-t", slug="local-t", nombre="Ferretería El Tornillo", ciudad_id="ciu-1", activo=True,
                portada_pos=None, portada_url=f"{BASE}/local-t/orig.jpg", portada_thumb_url=f"{BASE}/local-t/orig_t3.jpg")
    base.update(kw)
    guardar_foto_local("local-t/orig.jpg", _bytes(_ruido_color(900, 700)))
    return repo.seed_comercio(**base)


def _ruta(url):
    return Path(settings.fotos_dir) / url[len(BASE) + 1:]


def _en_disco(url):
    return _ruta(url).exists()


# ═══════════════════════════════════════════════ el recorte 4:3 (misma regla que el CSS)

def test_caja_de_una_foto_apaisada_ve_todo_el_alto_y_va_centrada_en_horizontal():
    # 1600 x 600 es más ancha que 4:3: se ve todo el alto (600) y 800 de ancho; sobran 400 a cada lado.
    for pos in (0, 50, 100, None):
        assert ft.caja_recorte(1600, 600, pos) == (400.0, 0.0, 1200.0, 600.0)


@pytest.mark.parametrize("pos,top", [(0, 0), (50, 675), (100, 1350), (None, 675), (25, 337.5), (-5, 0), (150, 1350)])
def test_caja_de_una_foto_vertical_usa_top_igual_pos_sobre_100_por_lo_que_sobra(pos, top):
    # 600 x 1800: se ve todo el ancho (600) y 450 de alto; sobran 1350. CSS: top = pos/100 * (alto - visible).
    x0, y0, x1, y1 = ft.caja_recorte(600, 1800, pos)
    assert (x0, x1) == (0.0, 600.0)
    assert y0 == pytest.approx(top) and y1 - y0 == pytest.approx(450)


def test_caja_de_una_foto_ya_4_a_3_es_la_foto_entera():
    assert ft.caja_recorte(800, 600, 30) == (0.0, 0.0, 800.0, 600.0)
    assert ft.caja_recorte(4000, 3000, 70) == (0.0, 0.0, 4000.0, 3000.0)


def test_la_caja_siempre_es_4_a_3_y_cae_dentro_de_la_foto():
    for w, h in [(1000, 1000), (333, 777), (5000, 700), (801, 600), (600, 799)]:
        for pos in (0, 13, 50, 99, 100):
            x0, y0, x1, y1 = ft.caja_recorte(w, h, pos)
            assert (x1 - x0) / (y1 - y0) == pytest.approx(4 / 3)
            assert -1e-9 <= x0 and x1 <= w + 1e-9 and -1e-9 <= y0 and y1 <= h + 1e-9


def test_recortar_deja_800_por_600_y_el_encuadre_elige_que_parte_se_ve():
    foto = _franjas(600, 1800)                      # 450 de alto visible sobre 1800: rojo, verde o azul
    arriba, medio, abajo = (ft.recortar(foto, p) for p in (0, 50, 100))
    for t in (arriba, medio, abajo):
        assert t.size == (800, 600)
    # centro del recorte: arriba rojo, en el medio verde, abajo azul (pos=0/50/100)
    assert arriba.getpixel((400, 300))[0] > 150 and arriba.getpixel((400, 300))[2] < 80
    assert medio.getpixel((400, 300))[1] > 150
    assert abajo.getpixel((400, 300))[2] > 150 and abajo.getpixel((400, 300))[0] < 80


def test_recortar_no_agranda_antes_de_recortar(monkeypatch):
    """`resize(box=)` sobre la foto original: nunca se arma una imagen intermedia más grande que la salida."""
    vistos = []
    original = Image.Image.resize

    def espia(self, size, *a, **k):
        vistos.append((self.size, size, k.get("box")))
        return original(self, size, *a, **k)

    monkeypatch.setattr(Image.Image, "resize", espia)
    ft.recortar(Image.new("RGB", (300, 1200), "gray"), 40)
    assert len(vistos) == 1 and vistos[0][1] == (800, 600) and vistos[0][2] is not None


# ═══════════════════════════════════════════════ el puntaje (funciones puras)

def test_colorido_de_un_gris_es_cero_y_sigue_la_formula_de_hasler_susstrunk():
    assert ft.colorido(Image.new("RGB", (200, 150), (120, 120, 120))) == 0.0
    # mitad rojo puro, mitad verde puro: rg = +-255 (media 0, varianza 255^2); yb = 127,5 siempre (media 127,5, var 0)
    img = Image.new("RGB", (200, 150), (255, 0, 0))
    img.paste((0, 255, 0), (100, 0, 200, 150))
    esperado = math.sqrt(255 ** 2) + 0.3 * 127.5
    assert ft.colorido(img) == pytest.approx(esperado, rel=1e-6)


def test_una_foto_con_color_puntua_mas_color_que_la_misma_en_gris():
    color = _ruido_color(400, 300)
    assert ft.norm_color(ft.colorido(color)) > ft.norm_color(ft.colorido(color.convert("L").convert("RGB")))


def test_nitidez_una_foto_borrosa_o_lisa_da_menos_que_la_nitida():
    nitida = _ruido_color(500, 375, amplitud=60)
    borrosa = nitida.filter(ImageFilter.GaussianBlur(6))
    lisa = Image.new("RGB", (500, 375), (120, 120, 120))
    v_n, v_b, v_l = (ft.varianza_laplaciano(i) for i in (nitida, borrosa, lisa))
    assert v_n > v_b > v_l
    assert v_l == 0.0
    assert ft.norm_nitidez(v_n) > ft.norm_nitidez(v_b) >= ft.norm_nitidez(v_l) == 0.0


def test_norm_nitidez_es_logaritmica_entre_5_y_500():
    assert ft.norm_nitidez(0) == 0.0 and ft.norm_nitidez(5) == pytest.approx(0.0)
    assert ft.norm_nitidez(50) == pytest.approx(0.5)
    assert ft.norm_nitidez(500) == pytest.approx(1.0) and ft.norm_nitidez(10 ** 6) == 1.0


def test_norm_color_satura_en_60():
    assert ft.norm_color(0) == 0.0 and ft.norm_color(30) == 0.5 and ft.norm_color(60) == 1.0 and ft.norm_color(200) == 1.0


@pytest.mark.parametrize("media,esperado", [(0, 0.0), (20, 0.0), (45, 0.5), (70, 1.0), (125, 1.0), (180, 1.0),
                                            (210, 0.5), (240, 0.0), (255, 0.0)])
def test_norm_luz_penaliza_lo_muy_oscuro_y_lo_quemado(media, esperado):
    assert ft.norm_luz(media) == pytest.approx(esperado)


def test_luz_media_mide_la_luminancia():
    assert ft.luz_media(Image.new("RGB", (100, 80), (0, 0, 0))) == 0.0
    assert ft.luz_media(Image.new("RGB", (100, 80), (255, 255, 255))) == pytest.approx(255.0)


def test_combinar_pesos_y_limites():
    assert ft.combinar(1, 1, 1) == 100
    assert ft.combinar(0, 0, 1) == 0
    assert ft.combinar(1, 1, 0) == 40                      # la luz mala deja como mucho el 40 %
    assert ft.combinar(1, 0, 1) == 45 and ft.combinar(0, 1, 1) == 55      # pesos 0,45 color y 0,55 nitidez
    for c, n, l in [(0.3, 0.9, 0.2), (1, 1, 1), (0, 0, 0), (2, 2, 2), (-1, -1, -1)]:
        assert 0 <= ft.combinar(c, n, l) <= 100


def test_puntaje_una_foto_oscura_vale_menos_que_la_misma_bien_iluminada():
    clara = _ruido_color(400, 300, amplitud=70)
    oscura = clara.point(lambda v: int(v * 0.12))
    p_c, p_o = ft.puntaje(clara), ft.puntaje(oscura)
    assert p_o["luz"] < p_c["luz"] == 1.0
    assert p_o["calidad"] < p_c["calidad"]
    assert set(p_c) == {"color", "nitidez", "luz", "calidad"} and 0 <= p_c["calidad"] <= 100


def test_puntaje_de_una_imagen_lisa_gris_es_cero():
    assert ft.puntaje(Image.new("RGB", (800, 600), (128, 128, 128)))["calidad"] == 0


def test_puntaje_una_foto_nitida_y_colorida_gana_a_una_borrosa_y_deslavada():
    buena = _ruido_color(800, 600, amplitud=80)
    mala = buena.filter(ImageFilter.GaussianBlur(8)).convert("L").convert("RGB")
    assert ft.puntaje(buena)["calidad"] > ft.puntaje(mala)["calidad"] + 20


# ═══════════════════════════════════════════════ la tarjeta (bytes) y el disco

def test_generar_tarjeta_da_jpeg_800x600_y_calidad_entera():
    jpeg, calidad = ft.generar_tarjeta(_bytes(_ruido_color(1200, 700)), 30)
    img = _abrir(jpeg)
    assert img.format == "JPEG" and img.size == (800, 600)
    assert isinstance(calidad, int) and 0 <= calidad <= 100


def test_generar_tarjeta_el_encuadre_cambia_el_resultado():
    foto = _bytes(_franjas(600, 1800))
    arriba, _ = ft.generar_tarjeta(foto, 0)
    abajo, _ = ft.generar_tarjeta(foto, 100)
    pa, pb = _abrir(arriba).getpixel((400, 300)), _abrir(abajo).getpixel((400, 300))
    assert pa[0] > pa[2] and pb[2] > pb[0]


def test_generar_tarjeta_rechaza_lo_que_no_es_imagen_o_es_muy_chico():
    with pytest.raises(ValueError):
        ft.generar_tarjeta(b"no soy una imagen", None)
    with pytest.raises(portada_diseno.PortadaInadecuada):
        ft.generar_tarjeta(_bytes(Image.new("RGB", (150, 150), "red")), None)


def test_guardar_usa_el_prefijo_card_y_un_token_de_64_bits():
    u1, u2 = ft.guardar("local-t", b"x"), ft.guardar("local-t", b"x")
    assert u1 != u2
    for u in (u1, u2):
        assert re.fullmatch(rf"{re.escape(BASE)}/local-t/card-[0-9a-f]{{16}}\.jpg", u) and _en_disco(u)


def test_soltar_archivo_sólo_borra_tarjetas_del_propio_comercio():
    c = {"slug": "local-t"}
    guardar_foto_local("local-t/orig.jpg", b"o")
    guardar_foto_local("local-t/diseno-aaaaaaaaaaaaaaaa.jpg", b"d")
    guardar_foto_local("otro/card-bbbbbbbbbbbbbbbb.jpg", b"c")
    propia = ft.guardar("local-t", b"p")
    for url in (f"{BASE}/local-t/orig.jpg", f"{BASE}/local-t/diseno-aaaaaaaaaaaaaaaa.jpg",
                f"{BASE}/otro/card-bbbbbbbbbbbbbbbb.jpg", "https://otro.sitio/x/card-1.jpg", None, "../../etc/passwd"):
        ft.soltar_archivo(c, url)
    assert _en_disco(f"{BASE}/local-t/orig.jpg") and _en_disco(f"{BASE}/local-t/diseno-aaaaaaaaaaaaaaaa.jpg")
    assert _en_disco(f"{BASE}/otro/card-bbbbbbbbbbbbbbbb.jpg")
    ft.soltar_archivo(c, propia)
    assert not _en_disco(propia)


def test_armar_para_comercio_guarda_la_tarjeta_y_actualiza_la_fila(repo):
    c = _comercio(repo)
    out = ft.armar_para_comercio(repo, c)
    fila = repo.comercios["com-t"]
    assert out == {"portada_card_url": fila["portada_card_url"], "portada_calidad": fila["portada_calidad"]}
    assert "/local-t/card-" in out["portada_card_url"] and _en_disco(out["portada_card_url"])
    assert _abrir(_ruta(out["portada_card_url"]).read_bytes()).size == (800, 600)
    assert 0 <= out["portada_calidad"] <= 100
    assert _en_disco(f"{BASE}/local-t/orig.jpg")                      # la original queda


def test_armar_otra_vez_suelta_la_tarjeta_anterior_y_deja_la_nueva(repo):
    c = _comercio(repo)
    primera = ft.armar_para_comercio(repo, c)["portada_card_url"]
    segunda = ft.armar_para_comercio(repo, repo.comercios["com-t"])["portada_card_url"]
    assert primera != segunda and _en_disco(segunda) and not _en_disco(primera)


def test_armar_sin_portada_o_sin_archivo_no_hace_nada(repo):
    sin = repo.seed_comercio(id="com-s", slug="s", activo=True, portada_url=None)
    assert ft.armar_para_comercio(repo, sin) is None
    roto = repo.seed_comercio(id="com-r", slug="r", activo=True, portada_url=f"{BASE}/r/no-existe.jpg")
    assert ft.armar_para_comercio(repo, roto) is None
    assert not repo.comercios["com-r"].get("portada_card_url")


def test_armar_descarta_la_tarjeta_si_la_portada_cambio_mientras_se_armaba(repo, monkeypatch):
    c = _comercio(repo)
    original = ft.generar_tarjeta

    def generar_y_cambiar(foto, pos):
        r = original(foto, pos)
        repo.comercios["com-t"]["portada_pos"] = 90                 # alguien cambió el encuadre en el medio
        return r

    monkeypatch.setattr(ft, "generar_tarjeta", generar_y_cambiar)
    assert ft.armar_para_comercio(repo, dict(c)) is None
    assert not repo.comercios["com-t"].get("portada_card_url")
    assert not list((Path(settings.fotos_dir) / "local-t").glob("card-*.jpg"))     # no quedó huérfana


def test_armar_si_falla_la_base_no_deja_el_archivo_huerfano(repo, monkeypatch):
    c = _comercio(repo)

    def falla(*a, **k):
        raise RuntimeError("base caída")

    monkeypatch.setattr(repo, "actualizar_portada_card", falla)
    with pytest.raises(RuntimeError):
        ft.armar_para_comercio(repo, c)
    assert not list((Path(settings.fotos_dir) / "local-t").glob("card-*.jpg"))


def test_la_tarjeta_se_escribe_con_un_update_condicional_a_la_portada_y_al_encuadre(repo, monkeypatch):
    c = _comercio(repo, portada_pos=40)
    visto = []
    original = repo.actualizar_portada_card

    def espia(cid, patch, url, pos):
        visto.append((cid, sorted(patch), url, pos))
        return original(cid, patch, url, pos)

    monkeypatch.setattr(repo, "actualizar_portada_card", espia)
    assert ft.armar_para_comercio(repo, dict(c)) is not None
    assert visto == [("com-t", ["portada_calidad", "portada_card_url"], f"{BASE}/local-t/orig.jpg", 40)]


def test_si_el_update_condicional_no_toca_ninguna_fila_se_suelta_el_archivo_nuevo_y_no_se_pisa_nada(repo):
    c = _comercio(repo)
    previa = ft.armar_para_comercio(repo, dict(c))["portada_card_url"]
    repo.comercios["com-t"]["portada_url"] = f"{BASE}/local-t/otra.jpg"     # otro pedido cambió la portada
    antes = dict(repo.comercios["com-t"])
    assert ft.armar_para_comercio(repo, {**antes, "portada_url": f"{BASE}/local-t/orig.jpg"}) is None
    assert repo.comercios["com-t"] == antes and _en_disco(previa)
    assert len(list((Path(settings.fotos_dir) / "local-t").glob("card-*.jpg"))) == 1      # la nueva no quedó huérfana


def test_rellenar_distingue_portada_cambio_de_foto_que_no_esta_en_el_disco(repo, monkeypatch):
    _comercio(repo)
    repo.seed_comercio(id="com-c", slug="c", activo=True, ciudad_id="ciu-1", portada_url=f"{BASE}/c/no-esta.jpg")
    monkeypatch.setattr(repo, "actualizar_portada_card", lambda *a, **k: False)
    r = ft.rellenar(repo, None, dormir=lambda s: None, imprimir=lambda s: None)
    assert r["portada_cambio"] == 1 and r["sin_foto_en_disco"] == 1 and r["armadas"] == 0


def test_armar_seguro_nunca_lanza(repo, monkeypatch):
    c = _comercio(repo)
    monkeypatch.setattr(ft, "generar_tarjeta", lambda *a, **k: (_ for _ in ()).throw(ValueError("rota")))
    assert ft.armar_seguro(repo, c) is None
    assert ft.armar_seguro(repo, {}) is None


# ═══════════════════════════════════════════════ los ganchos

def test_poner_nueva_arma_la_tarjeta_de_la_portada_nueva_y_suelta_la_vieja(repo):
    c = _comercio(repo)
    vieja = ft.armar_para_comercio(repo, c)["portada_card_url"]
    guardar_foto_local("local-t/nueva.jpg", _bytes(_ruido_color(700, 900, semilla=5)))
    out = portada.poner_nueva(repo, repo.comercios["com-t"], f"{BASE}/local-t/nueva.jpg", f"{BASE}/local-t/nueva_t3.jpg")
    nueva = out["portada_card_url"]
    assert nueva and nueva != vieja and "/local-t/card-" in nueva and _en_disco(nueva)
    assert not _en_disco(vieja)
    assert repo.comercios["com-t"]["portada_card_url"] == nueva and out["portada_calidad"] is not None
    assert repo.comercios["com-t"]["portada_pos"] is None


def test_poner_nueva_si_la_tarjeta_falla_el_cambio_de_portada_sigue_y_la_tarjeta_vieja_queda_vacia(repo, monkeypatch):
    c = _comercio(repo)
    vieja = ft.armar_para_comercio(repo, c)["portada_card_url"]
    guardar_foto_local("local-t/nueva.jpg", _bytes(_ruido_color(700, 900, semilla=5)))
    monkeypatch.setattr(ft, "generar_tarjeta", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = portada.poner_nueva(repo, repo.comercios["com-t"], f"{BASE}/local-t/nueva.jpg", None)
    assert out["portada_url"].endswith("/nueva.jpg")
    assert out["portada_card_url"] is None and out["portada_calidad"] is None      # no queda la tarjeta de la foto anterior
    assert not _en_disco(vieja)


def test_usar_de_galeria_arma_la_tarjeta_de_la_foto_elegida(repo):
    c = _comercio(repo)
    guardar_foto_local("local-t/galeria1.jpg", _bytes(_ruido_color(900, 700, semilla=9)))
    fila = repo.add_foto_comercio({"comercio_id": "com-t", "url": f"{BASE}/local-t/galeria1.jpg",
                                   "thumb_url": f"{BASE}/local-t/galeria1_t3.jpg", "orden": 0})
    vieja = ft.armar_para_comercio(repo, c)["portada_card_url"]
    out = portada.usar_de_galeria(repo, repo.comercios["com-t"], fila["id"])
    assert out["portada_url"].endswith("/galeria1.jpg")
    assert out["portada_card_url"] and out["portada_card_url"] != vieja and _en_disco(out["portada_card_url"])
    assert not _en_disco(vieja)


def test_usar_de_galeria_con_tarjeta_rota_sigue(repo, monkeypatch):
    _comercio(repo)
    guardar_foto_local("local-t/galeria1.jpg", _bytes(_ruido_color(900, 700, semilla=9)))
    fila = repo.add_foto_comercio({"comercio_id": "com-t", "url": f"{BASE}/local-t/galeria1.jpg", "thumb_url": None, "orden": 0})
    monkeypatch.setattr(ft, "armar_para_comercio", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    out = portada.usar_de_galeria(repo, repo.comercios["com-t"], fila["id"])
    assert out["portada_url"].endswith("/galeria1.jpg") and out["portada_card_url"] is None


def test_el_endpoint_de_encuadre_rehace_la_tarjeta(client, repo, admin_token):
    c = _comercio(repo)
    vieja = ft.armar_para_comercio(repo, c)["portada_card_url"]
    r = client.put("/admin/comercio/com-t", json={"portada_pos": 80}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    nueva = repo.comercios["com-t"]["portada_card_url"]
    assert nueva != vieja and _en_disco(nueva) and not _en_disco(vieja)
    assert r.json()["comercio"]["portada_card_url"] == nueva
    assert repo.comercios["com-t"]["portada_pos"] == 80


def test_encuadre_igual_o_otro_campo_no_rehace_la_tarjeta(client, repo, admin_token):
    c = _comercio(repo, portada_pos=40)
    vieja = ft.armar_para_comercio(repo, c)["portada_card_url"]
    assert client.put("/admin/comercio/com-t", json={"portada_pos": 40}, headers=_h(admin_token)).status_code == 200
    assert client.put("/admin/comercio/com-t", json={"horario": "9 a 18"}, headers=_h(admin_token)).status_code == 200
    assert repo.comercios["com-t"]["portada_card_url"] == vieja


def test_encuadre_con_tarjeta_rota_igual_guarda(client, repo, admin_token, monkeypatch):
    _comercio(repo)
    monkeypatch.setattr(ft, "generar_tarjeta", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r = client.put("/admin/comercio/com-t", json={"portada_pos": 10}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.comercios["com-t"]["portada_pos"] == 10


def test_subir_portada_por_el_endpoint_del_admin_deja_la_tarjeta(client, repo, admin_token):
    _comercio(repo)
    r = client.post("/admin/comercio/com-t/foto", headers=_h(admin_token),
                    files={"foto": ("p.jpg", _bytes(_ruido_color(900, 700, semilla=3)), "image/jpeg")})
    assert r.status_code == 200, r.text
    fila = repo.comercios["com-t"]
    assert fila["portada_card_url"] and "/card-" in fila["portada_card_url"] and _en_disco(fila["portada_card_url"])
    assert fila["portada_calidad"] is not None


# ═══════════════════════════════════════════════ el comando de relleno

def test_rellenar_arma_las_que_faltan_y_no_borra_ninguna_original(repo):
    a = _comercio(repo)
    guardar_foto_local("b/orig.jpg", _bytes(_ruido_color(800, 600, semilla=2)))
    repo.seed_comercio(id="com-b", slug="b", activo=True, ciudad_id="ciu-1", portada_url=f"{BASE}/b/orig.jpg")
    repo.seed_comercio(id="com-c", slug="c", activo=True, ciudad_id="ciu-1", portada_url=f"{BASE}/c/no-esta.jpg")
    guardar_foto_local("d/orig.jpg", _bytes(Image.new("RGB", (120, 120), "red")))
    repo.seed_comercio(id="com-d", slug="d", activo=True, ciudad_id="ciu-1", portada_url=f"{BASE}/d/orig.jpg")
    repo.seed_comercio(id="com-e", slug="e", activo=True, ciudad_id="ciu-1", portada_url=None)
    repo.seed_comercio(id="com-f", slug="f", activo=False, ciudad_id="ciu-1", portada_url=f"{BASE}/f/orig.jpg")
    previas = ft.armar_para_comercio(repo, a)["portada_card_url"]
    repo.comercios["com-t"]["portada_card_url"] = previas

    r = ft.rellenar(repo, None, dormir=lambda s: None, imprimir=lambda s: None)
    assert r == {"revisados": 4, "armadas": 1, "ya_tenian": 1, "sin_foto_en_disco": 1, "portada_cambio": 0,
                 "inadecuadas": 1, "errores": 0}
    assert repo.comercios["com-b"]["portada_card_url"] and not repo.comercios["com-c"].get("portada_card_url")
    assert repo.comercios["com-t"]["portada_card_url"] == previas and _en_disco(previas)
    for u in (f"{BASE}/local-t/orig.jpg", f"{BASE}/b/orig.jpg", f"{BASE}/d/orig.jpg"):
        assert _en_disco(u)


def test_rellenar_con_rehacer_pisa_las_existentes_y_con_ciudad_filtra(repo):
    a = _comercio(repo)
    guardar_foto_local("b/orig.jpg", _bytes(_ruido_color(800, 600, semilla=2)))
    repo.seed_comercio(id="com-b", slug="b", activo=True, ciudad_id="ciu-2", portada_url=f"{BASE}/b/orig.jpg")
    previa = ft.armar_para_comercio(repo, a)["portada_card_url"]
    r = ft.rellenar(repo, "ciu-1", rehacer=True, dormir=lambda s: None, imprimir=lambda s: None)
    assert r["revisados"] == 1 and r["armadas"] == 1
    assert repo.comercios["com-t"]["portada_card_url"] != previa and not _en_disco(previa)
    assert not repo.comercios["com-b"].get("portada_card_url")          # otra ciudad: no se tocó


def test_rellenar_cuenta_los_errores_y_sigue(repo, monkeypatch):
    _comercio(repo)
    guardar_foto_local("b/orig.jpg", _bytes(_ruido_color(800, 600, semilla=2)))
    repo.seed_comercio(id="com-b", slug="b", activo=True, ciudad_id="ciu-1", portada_url=f"{BASE}/b/orig.jpg")
    original = ft.guardar

    def guardar_roto(slug, jpeg):
        return None if slug == "local-t" else original(slug, jpeg)

    monkeypatch.setattr(ft, "guardar", guardar_roto)
    r = ft.rellenar(repo, None, dormir=lambda s: None, imprimir=lambda s: None)
    assert r["errores"] == 1 and r["armadas"] == 1


def test_el_comando_pide_todas_e_imprime_el_resumen(repo, capsys):
    _comercio(repo)
    assert ft.main([], repo=repo) == 2
    assert ft.main(["--todas", "--ciudad", "no-existe"], repo=type("R", (), {"get_ciudad": lambda s, x: None})()) == 2
    assert ft.main(["--todas", "--pausa", "0"], repo=repo, dormir=lambda s: None) == 0
    out = capsys.readouterr().out
    assert "Tarjetas armadas:           1" in out and "No se borró ninguna portada original" in out


# ═══════════════════════════════════════════════ la migración 0202 (estática)

RAIZ = Path(__file__).resolve().parents[2]
NOMBRE = "0202_fotos_planes_platos.sql"


def _sql(carpeta="supabase/migrations"):
    return (RAIZ / carpeta / NOMBRE).read_text(encoding="utf-8")


def _sin_comentarios(sql):
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


def test_la_0202_es_identica_en_las_dos_carpetas():
    a = (RAIZ / "supabase/migrations" / NOMBRE).read_bytes()
    b = (RAIZ / "selfhost/postgres-init" / NOMBRE).read_bytes()
    assert a == b and a


def test_la_0202_agrega_las_dos_columnas_publicas_por_columna():
    sql = _sin_comentarios(_sql())
    for col, tipo in (("portada_card_url", "text"), ("portada_calidad", "smallint")):
        assert f"add column if not exists {col} {tipo};" in sql
        assert f"grant select ({col}) on public.comercios to anon, authenticated;" in sql
    assert not re.search(r"grant\s+select\s+on\s+(public\.)?comercios\s+to\s+[^;]*anon", sql, re.I)


def test_la_0202_buscar_comercios_devuelve_las_dos_columnas_y_conserva_los_permisos():
    sql = _sin_comentarios(_sql())
    assert "drop function if exists public.buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text);" in sql
    assert "create function public.buscar_comercios(" in sql
    assert "portada_card_url text, portada_calidad smallint" in sql
    assert "c.portada_card_url, c.portada_calidad" in sql
    assert "horario_estimado, portada_card_url, portada_calidad" in sql
    assert "security definer" in sql and "set search_path = public, pg_temp" in sql
    assert "revoke execute on function public.buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text) from public;" in sql
    assert re.search(r"grant\s+execute on function public\.buscar_comercios\([^)]*\)\s+to anon, authenticated, service_role;", sql)
    assert "least(case when coalesce(p_limit, 0) <= 0 then 24 else p_limit end, 500)" in sql      # el tope de la 0186


def test_la_0202_buscar_comercios_es_la_0186_con_las_dos_columnas_nada_mas():
    """El cuerpo de la función es el de la 0186 salvo las líneas de las dos columnas nuevas."""
    def cuerpo(sql):
        m = re.search(r"as \$\$(.*?)\$\$;", sql, re.S)
        assert m
        return [l.rstrip() for l in m.group(1).splitlines()]

    viejo = cuerpo((RAIZ / "supabase/migrations/0186_cierre_lectura_publica.sql").read_text(encoding="utf-8"))
    nuevo = cuerpo(_sql())
    solo_nuevo = [l for l in nuevo if l not in viejo]
    assert solo_nuevo == [
        "      coalesce(c.horario_estimado, false) as horario_estimado,",
        "      c.portada_card_url, c.portada_calidad",
        "         horario_estimado, portada_card_url, portada_calidad"]
    assert [l for l in viejo if l not in nuevo] == [
        "      coalesce(c.horario_estimado, false) as horario_estimado",
        "         horario_estimado"]


def test_la_0202_crea_el_rubro_bodegas_comercial_con_palabras_sin_tildes():
    sql = _sin_comentarios(_sql())
    assert re.search(r"values \('bodegas', 'Bodegas y vinotecas', null, \d+, true\)", sql)
    m = re.search(r"\('bodegas', '(\\m\([^']+\))'\)", sql)
    assert m
    termino = m.group(1)[3:-1].split("|")
    assert termino == ["bodega", "vinoteca", "vinedo", "singani artesanal", "cata de vinos"]
    assert not any(c in m.group(1) for c in "áéíóúñü")


def test_la_0202_pasa_las_bodegas_de_turismo_sin_revisar_al_rubro_nuevo():
    sql = _sin_comentarios(_sql())
    i = sql.index("update public.comercios_importados")
    bloque = sql[i:sql.index(";", i)]
    assert "set rubro_slug = 'bodegas'" in bloque
    assert "fuente = 'turismo'" in bloque and "estado = 'nuevo'" in bloque
    assert "'bodegas-y-vinotecas'" in bloque and "rubro_slug is distinct from 'bodegas'" in bloque     # idempotente


def test_la_0202_platos_tipicos_tiene_las_columnas_el_unico_y_los_checks():
    sql = " ".join(_sin_comentarios(_sql()).split())
    for frag in ("create table if not exists public.platos_tipicos (",
                 "id uuid primary key default gen_random_uuid()",
                 "ciudad_id uuid not null references public.ciudades(id)",
                 "check (tipo in ('plato', 'reposteria', 'bebida'))",
                 "nombre text not null", "descripcion text", "fuente_url text",
                 "estado text not null default 'pendiente' check (estado in ('pendiente', 'aprobado', 'rechazado'))",
                 "activo boolean not null default true",
                 "created_at timestamptz not null default now()", "updated_at timestamptz not null default now()",
                 "unique (ciudad_id, nombre)"):
        assert frag in sql, frag


def test_la_0202_platos_tipicos_rls_y_permisos_sin_delete():
    sql = " ".join(_sin_comentarios(_sql()).split())
    assert "alter table public.platos_tipicos enable row level security;" in sql
    assert ("create policy platos_tipicos_lectura_publica on public.platos_tipicos for select to anon, authenticated "
            "using (estado = 'aprobado' and activo);") in sql
    assert "drop policy if exists platos_tipicos_lectura_publica on public.platos_tipicos;" in sql
    assert "revoke all on public.platos_tipicos from public, anon, authenticated, service_role;" in sql
    assert "grant select on public.platos_tipicos to anon, authenticated;" in sql
    assert "grant select, insert, update on public.platos_tipicos to service_role;" in sql
    assert not re.search(r"grant[^;]*\b(delete|truncate|all)\b[^;]*platos_tipicos", sql)
    # la comprobación final cubre lo mismo
    assert "service_role puede borrar o vaciar platos_tipicos" in sql and "platos_tipicos sin RLS" in sql


def test_la_0202_interruptor_gemini_gastronomia_apagado_y_check_ampliado():
    from app.services.cost_switches import CATALOGO
    sql = " ".join(_sin_comentarios(_sql()).split())
    m = re.search(r"add constraint cost_switches_key_check check \(key in \(([^)]*)\)\)", sql)
    assert m and sorted(re.findall(r"'([a-z_]+)'", m.group(1))) == sorted(CATALOGO)
    assert "insert into public.cost_switches (key, enabled, updated_by) values ('gemini_gastronomia', false," in sql
    assert "on conflict (key) do nothing" in sql
    assert sql.index("drop constraint if exists cost_switches_key_check") < sql.index("add constraint cost_switches_key_check")


def test_la_0202_es_idempotente_y_recarga_postgrest():
    sql = _sin_comentarios(_sql())
    assert sql.lstrip().startswith("begin;") and "commit;" in sql
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    assert "do $chk$" in sql and sql.index("do $chk$") < sql.index("commit;")
    assert not re.search(r"create table(?! if not exists)", sql)
    # sólo se borran palabras del diccionario de rubros (como la 0097); nunca filas de negocio
    assert re.findall(r"delete from (\w+)", sql, re.I) == ["rubro_palabras", "rubro_palabras"]
    assert not re.search(r"\b(truncate table|drop (?:table|column))\b", sql, re.I)
    assert not re.search(r"add column(?! if not exists)", sql)
    assert "on conflict (slug) do update" in sql and "on conflict (rubro_slug, patron) do nothing" in sql


# ═══════════════════════════════════════════════ bodegas contra bebidas: la clasificación con el diccionario final

def _clasificar(texto: str) -> list[str]:
    """Lo que devuelve `rubros_sugeridos(texto)` con el diccionario tal como lo dejan TODAS las migraciones (el mismo
    estado final que arma `test_diccionario_rubros`): `unaccent(lower(texto)) ~ patron`, con `\m` y `\M` de Postgres
    traducidos a sus equivalentes de Python. Ordenado, como el `array_agg(distinct)`."""
    import unicodedata
    from tests.test_diccionario_rubros import _estado_final

    limpio = "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if unicodedata.category(c) != "Mn")
    out = set()
    for slug, patrones in _estado_final().items():
        for p in patrones:
            py = p.replace("\m", r"(?<!\w)(?=\w)").replace("\M", r"(?<=\w)(?!\w)")
            if re.search(py, limpio):
                out.add(slug)
    return sorted(out)


@pytest.mark.parametrize("texto", ["Vinoteca El Parral", "Singani artesanal Don Pedro", "Bodega La Concepción",
                                   "Viñedos de Tarija"])
def test_las_bodegas_se_clasifican_como_bodegas_y_no_como_bebidas(texto):
    assert _clasificar(texto) == ["bodegas"], _clasificar(texto)


def test_una_cata_de_vinos_suma_bodegas_y_no_le_quita_bebidas_porque_vinos_es_una_bebida():
    assert _clasificar("Cata de vinos en la altura") == ["bebidas", "bodegas"]


@pytest.mark.parametrize("texto", ["Licorería Singani", "Singani Casa Real", "Vinos y licores Don José",
                                   "Distribuidora de bebidas"])
def test_las_bebidas_siguen_siendo_bebidas(texto):
    assert "bebidas" in _clasificar(texto) and "bodegas" not in _clasificar(texto), _clasificar(texto)


def test_la_0202_cambia_los_dos_patrones_de_bebidas_sin_dejar_los_viejos():
    from tests.test_diccionario_rubros import _estado_final
    pats = _estado_final()["bebidas"]
    assert r"\m(bebida|gaseosa|cerveza|vinos?\M|jugo|licor|whisky|refresco)" in pats
    assert r"\m(fernet|ron\M|vodka|singani(?! artesanal)|whiskeria|champagne|espumante)" in pats
    assert not any("cerveza|vino|jugo" in p or "vodka|singani|whiskeria" in p for p in pats)
    sql = _sin_comentarios(_sql())
    assert "delete from rubro_palabras where rubro_slug = 'bebidas' and patron like '%cerveza|vino|jugo%';" in sql
    assert "delete from rubro_palabras where rubro_slug = 'bebidas' and patron like '%vodka|singani|whiskeria%';" in sql


def test_la_0202_reserva_de_importados_es_privada_y_nullable():
    sql = _sin_comentarios(_sql())
    assert "alter table public.comercios_importados add column if not exists aprobando_desde timestamptz;" in sql
    assert not re.search(r"grant[^;]*aprobando_desde", sql, re.I)
    assert "puede leer comercios_importados.aprobando_desde" in sql
