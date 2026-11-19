"""Portada de diseño de la ficha pública (docs/portada-diseno.md, migración 0200).

Sin IA (decisión del 19/11/2026): todo es Pillow y no hay llamadas a la red.
"""
import random
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from PIL import Image, ImageStat

from app.core.config import settings
from app.services import cost_switches, portada, portada_diseno as pd
from app.services.imagenes import guardar_foto_local

BASE = "https://api.test/fotos"
RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _base_publica(monkeypatch):
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _jpeg(w=800, h=600, color="green"):
    buf = BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG")
    return buf.getvalue()


def _abrir(jpeg: bytes) -> Image.Image:
    return Image.open(BytesIO(jpeg))


def _media(img: Image.Image) -> float:
    return ImageStat.Stat(img.convert("L")).mean[0]


def _ruido(w, h, centro, amplitud, semilla=1):
    """Una foto sintética con detalle: gris `centro` +- `amplitud`."""
    rnd = random.Random(semilla)
    img = Image.new("RGB", (w, h))
    img.putdata([(max(0, min(255, centro + rnd.randint(-amplitud, amplitud))),) * 3 for _ in range(w * h)])
    return img


def _comercio(repo, con_portada=True, **kw):
    base = dict(id="com-d", slug="local-d", nombre="Ferretería El Tornillo", whatsapp="59170000001",
                ciudad_id="ciu-1", rubro_id="rub-ferre", portada_pos=None)
    repo.rubros["ferreteria"] = "rub-ferre"
    if con_portada:
        base["portada_url"] = f"{BASE}/local-d/orig.jpg"
        guardar_foto_local("local-d/orig.jpg", _jpeg())
        base["portada_thumb_url"] = f"{BASE}/local-d/orig_t3.jpg"
    base.update(kw)
    return repo.seed_comercio(**base)


def _en_disco(url):
    return (Path(settings.fotos_dir) / url[len(BASE) + 1:]).exists()


URL = "/admin/comercio/com-d/portada-diseno"


# ══════════════════════════════════════════ la plantilla (Pillow)

@pytest.mark.parametrize("w,h", [(600, 1800), (2400, 800), (120, 90), (1600, 1000)])
def test_plantilla_devuelve_jpeg_1600x1000_con_foto_vertical_apaisada_chica(w, h):
    out = pd.armar_plantilla(_jpeg(w, h), "Ferretería El Tornillo", "Ferretería", "Bermejo", None)
    img = _abrir(out)
    assert img.format == "JPEG" and img.size == (1600, 1000)


def test_nombre_larguisimo_no_rompe_y_no_se_sale_del_cuadro():
    nombre = "Distribuidora Mayorista de Productos Importados y Nacionales del Sur Boliviano " * 4
    out = pd.armar_plantilla(_jpeg(), nombre, "Almacén", "Bermejo", 20)
    assert _abrir(out).size == (1600, 1000)
    px, lineas = pd.ajustar_nombre(pd.limpiar_texto(nombre), 1440)
    assert len(lineas) <= 2 and lineas[-1].endswith("…") and px == 52
    assert all(pd._largo(l, "bold", px) <= 1440 for l in lineas)


def test_nombre_sin_espacios_se_parte_y_no_se_sale():
    px, lineas = pd.ajustar_nombre("A" * 200, 1440)
    assert len(lineas) <= 2 and all(pd._largo(l, "bold", px) <= 1440 for l in lineas)


def test_nombre_corto_usa_letra_grande_en_un_renglon():
    px, lineas = pd.ajustar_nombre("Don Pepe", 1440)
    assert px == 104 and lineas == ["Don Pepe"]


def test_emoji_en_el_nombre_no_rompe_y_se_filtra():
    assert pd.limpiar_texto("Café 😀 Ñandú ★ 🍕") == "Café Ñandú"
    assert pd.limpiar_texto("​Mi\x00 Local ") == "Mi Local"
    out = pd.armar_plantilla(_jpeg(), "😀🍕 Pizzería 🍕", "Comidas 🍴", "Bermejo ★", None)
    assert _abrir(out).size == (1600, 1000)


def test_nombre_vacio_o_solo_emojis_no_rompe():
    assert _abrir(pd.armar_plantilla(_jpeg(), "😀😀", None, None, None)).size == (1600, 1000)
    assert _abrir(pd.armar_plantilla(_jpeg(), "", "", "", 50)).size == (1600, 1000)


def test_la_franja_de_abajo_es_mas_oscura_que_la_foto():
    out = _abrir(pd.armar_plantilla(_jpeg(1600, 1000, "white"), "Local", "Rubro", "Ciudad", None, mejorar=False))
    abajo = _media(out.crop((700, 940, 900, 990)))
    arriba = _media(out.crop((700, 300, 900, 350)))
    assert arriba > 240 and abajo < 120


def test_el_logo_se_dibuja_arriba_a_la_derecha():
    out = _abrir(pd.armar_plantilla(_jpeg(1600, 1000, "white"), "Local", None, None, None, mejorar=False))
    # sobre la foto blanca el velo de arriba oscurece; el logo blanco es lo más claro de esa esquina
    esquina = out.crop((1250, 44, 1520, 120))
    assert max(ImageStat.Stat(esquina.convert("L")).extrema[0]) >= 240
    assert _media(esquina) < 250


def test_pos_mueve_el_centro_vertical_del_recorte():
    foto = Image.new("RGB", (1000, 3000), (200, 0, 0))
    foto.paste(Image.new("RGB", (1000, 1500), (0, 0, 200)), (0, 1500))      # arriba rojo, abajo azul
    buf = BytesIO()
    foto.save(buf, format="JPEG", quality=95)
    arriba = _abrir(pd.armar_plantilla(buf.getvalue(), "X", None, None, 0, mejorar=False)).getpixel((800, 400))
    abajo = _abrir(pd.armar_plantilla(buf.getvalue(), "X", None, None, 100, mejorar=False)).getpixel((800, 400))
    sin = _abrir(pd.armar_plantilla(buf.getvalue(), "X", None, None, None, mejorar=False)).getpixel((800, 400))
    assert arriba[0] > 150 and arriba[2] < 60
    assert abajo[2] > 150 and abajo[0] < 60
    assert sin[0] > 150 or sin[2] > 150       # 50 = el centro: justo la mitad roja y la mitad azul


def test_foto_corrupta_es_value_error():
    with pytest.raises(ValueError):
        pd.armar_plantilla(b"no soy una imagen", "X", None, None, None)


# ══════════════════════════════════════════ la mejora automática gratis

def test_mejorar_gratis_aclara_una_foto_oscura():
    oscura = _ruido(300, 200, 40, 25)
    mejorada = pd.mejorar_gratis(oscura)
    assert _media(mejorada) > _media(oscura) + 8


def test_mejorar_gratis_no_quema_una_foto_clara():
    clara = _ruido(300, 200, 170, 60)
    mejorada = pd.mejorar_gratis(clara)
    assert _media(mejorada) <= _media(clara) + 4
    # y tampoco la aplasta contra el blanco
    assert ImageStat.Stat(mejorada.convert("L")).extrema[0][1] <= 255 and _media(mejorada) < 235


def test_mejorar_gratis_no_rompe_con_foto_lisa():
    for color in ("black", "white", (120, 120, 120)):
        assert pd.mejorar_gratis(Image.new("RGB", (50, 50), color)).size == (50, 50)


def test_la_plantilla_aplica_la_mejora_solo_sin_ia(monkeypatch):
    llamadas = []
    original = pd.mejorar_gratis
    monkeypatch.setattr(pd, "mejorar_gratis", lambda img: llamadas.append(1) or original(img))
    pd.armar_plantilla(_jpeg(), "X", None, None, None)
    assert llamadas == [1]
    pd.armar_plantilla(_jpeg(), "X", None, None, None, mejorar=False)
    assert llamadas == [1]


# ══════════════════════════════════════════ los 4 endpoints

def test_post_feliz_deja_la_propuesta_y_no_publica(client, repo, admin_token):
    c = _comercio(repo)
    r = client.post(URL, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert set(cuerpo) == {"portada_diseno_url", "portada_diseno_propuesta_url"}
    assert cuerpo["portada_diseno_url"] is None
    url = cuerpo["portada_diseno_propuesta_url"]
    assert url.startswith(f"{BASE}/local-d/diseno-") and url.endswith(".jpg") and _en_disco(url)
    guardado = Path(settings.fotos_dir) / url[len(BASE) + 1:]
    assert _abrir(guardado.read_bytes()).size == (1600, 1000)
    assert repo.comercios[c["id"]]["portada_diseno_propuesta_url"] == url
    assert not repo.comercios[c["id"]].get("portada_diseno_url")


def test_post_dos_veces_cambia_la_propuesta_y_borra_el_archivo_anterior(client, repo, admin_token):
    _comercio(repo)
    a = client.post(URL, headers=_h(admin_token)).json()["portada_diseno_propuesta_url"]
    b = client.post(URL, headers=_h(admin_token)).json()["portada_diseno_propuesta_url"]
    assert a != b and _en_disco(b) and not _en_disco(a)


def test_post_sin_foto_de_portada_es_400(client, repo, admin_token):
    _comercio(repo, con_portada=False)
    r = client.post(URL, headers=_h(admin_token))
    assert r.status_code == 400 and r.json()["detail"] == "El comercio no tiene foto de portada"


def test_post_comercio_inexistente_es_404(client, repo, admin_token):
    assert client.post("/admin/comercio/nada/portada-diseno", headers=_h(admin_token)).status_code == 404


def test_post_usa_rubro_y_ciudad_de_la_base(client, repo, admin_token, monkeypatch):
    _comercio(repo, portada_pos=70)
    visto = {}
    original = pd.armar_plantilla

    def espia(foto, nombre, rubro, ciudad, pos, **kw):
        visto.update(nombre=nombre, rubro=rubro, ciudad=ciudad, pos=pos)
        return original(foto, nombre, rubro, ciudad, pos, **kw)

    monkeypatch.setattr(pd, "armar_plantilla", espia)
    assert client.post(URL, headers=_h(admin_token)).status_code == 200
    assert visto == {"nombre": "Ferretería El Tornillo", "rubro": "Ferreteria", "ciudad": "Bermejo",
                     "pos": 70}


def test_put_usa_la_propuesta_y_la_vacia(client, repo, admin_token):
    c = _comercio(repo)
    propuesta = client.post(URL, headers=_h(admin_token)).json()["portada_diseno_propuesta_url"]
    r = client.put(URL, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() == {"portada_diseno_url": propuesta, "portada_diseno_propuesta_url": None}
    assert repo.comercios[c["id"]]["portada_diseno_url"] == propuesta and _en_disco(propuesta)


def test_put_reemplaza_el_diseno_anterior_y_suelta_su_archivo(client, repo, admin_token):
    _comercio(repo)
    client.post(URL, headers=_h(admin_token))
    viejo = client.put(URL, headers=_h(admin_token)).json()["portada_diseno_url"]
    client.post(URL, headers=_h(admin_token))
    nuevo = client.put(URL, headers=_h(admin_token)).json()["portada_diseno_url"]
    assert nuevo != viejo and _en_disco(nuevo) and not _en_disco(viejo)


def test_put_sin_propuesta_es_400(client, repo, admin_token):
    _comercio(repo)
    r = client.put(URL, headers=_h(admin_token))
    assert r.status_code == 400 and "propuesta" in r.json()["detail"]


def test_delete_propuesta_la_descarta_y_no_toca_la_vigente(client, repo, admin_token):
    _comercio(repo)
    client.post(URL, headers=_h(admin_token))
    vigente = client.put(URL, headers=_h(admin_token)).json()["portada_diseno_url"]
    propuesta = client.post(URL, headers=_h(admin_token)).json()["portada_diseno_propuesta_url"]
    r = client.delete(f"{URL}/propuesta", headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json() == {"portada_diseno_url": vigente, "portada_diseno_propuesta_url": None}
    assert _en_disco(vigente) and not _en_disco(propuesta)
    # sin propuesta no hay nada que hacer, y no es un error
    assert client.delete(f"{URL}/propuesta", headers=_h(admin_token)).status_code == 200


def test_delete_diseno_vuelve_a_la_foto_original(client, repo, admin_token):
    c = _comercio(repo)
    client.post(URL, headers=_h(admin_token))
    vigente = client.put(URL, headers=_h(admin_token)).json()["portada_diseno_url"]
    r = client.delete(URL, headers=_h(admin_token))
    assert r.status_code == 200 and r.json() == {"portada_diseno_url": None, "portada_diseno_propuesta_url": None}
    assert not _en_disco(vigente)
    assert _en_disco(c["portada_url"])          # la foto original NUNCA se toca
    assert client.delete(URL, headers=_h(admin_token)).status_code == 200


def test_los_endpoints_piden_permiso_y_login(client, repo, agente_token):
    _comercio(repo)
    for metodo, ruta in (("post", URL), ("put", URL), ("delete", URL), ("delete", f"{URL}/propuesta")):
        assert getattr(client, metodo)(ruta).status_code in (401, 403)
    # un comerciante no puede (token de otro rol)
    from tests.conftest import comercio_token
    for metodo, ruta in (("post", URL), ("put", URL), ("delete", URL), ("delete", f"{URL}/propuesta")):
        assert getattr(client, metodo)(ruta, headers=_h(comercio_token(comercio_id="com-d"))).status_code in (401, 403)


# ══════════════════════════════════════════ sin IA (decisión del 19/11/2026)

def test_no_hay_ia_en_la_portada_de_diseno():
    """«Mejorar con IA» quedó afuera por costo: ni el servicio, ni el interruptor, ni la config la ofrecen."""
    from app.core.config import Settings
    assert not hasattr(pd, "mejorar_con_ia")
    assert "gemini_portada_diseno" not in cost_switches.CATALOGO
    assert "gemini_image_model" not in Settings.model_fields


def test_el_parametro_ia_se_ignora_y_no_llama_a_nadie(client, repo, admin_token, monkeypatch):
    llamadas = MagicMock()
    monkeypatch.setattr("httpx.post", llamadas)
    _comercio(repo)
    r = client.post(f"{URL}?ia=true", headers=_h(admin_token))
    assert r.status_code == 200 and r.json()["portada_diseno_propuesta_url"]
    llamadas.assert_not_called()


# ══════════════════════════════════════════ cambiar la foto de portada limpia el diseño

def _con_diseno(client, repo, admin_token):
    c = _comercio(repo)
    client.post(URL, headers=_h(admin_token))
    vigente = client.put(URL, headers=_h(admin_token)).json()["portada_diseno_url"]
    propuesta = client.post(URL, headers=_h(admin_token)).json()["portada_diseno_propuesta_url"]
    return c, vigente, propuesta


def test_subir_portada_nueva_limpia_las_dos_columnas_y_los_archivos(client, repo, admin_token):
    c, vigente, propuesta = _con_diseno(client, repo, admin_token)
    r = client.post("/admin/comercio/com-d/foto", headers=_h(admin_token),
                    files={"foto": ("f.jpg", BytesIO(_jpeg()), "image/jpeg")})
    assert r.status_code == 200, r.text
    fila = repo.comercios[c["id"]]
    assert fila["portada_diseno_url"] is None and fila["portada_diseno_propuesta_url"] is None
    assert not _en_disco(vigente) and not _en_disco(propuesta)


def test_elegir_otra_de_la_galeria_limpia_las_dos_columnas(client, repo, admin_token):
    c, vigente, propuesta = _con_diseno(client, repo, admin_token)
    guardar_foto_local("local-d/otra.jpg", _jpeg(color="red"))
    repo.comercio_fotos.append({"id": "f1", "comercio_id": "com-d", "url": f"{BASE}/local-d/otra.jpg",
                                "thumb_url": f"{BASE}/local-d/otra_t3.jpg", "orden": 0,
                                "created_at": "2026-01-01T00:00:00+00:00"})
    r = client.put("/admin/comercio/com-d/portada", headers=_h(admin_token), json={"foto_id": "f1"})
    assert r.status_code == 200, r.text
    fila = repo.comercios[c["id"]]
    assert fila["portada_url"].endswith("otra.jpg")
    assert fila["portada_diseno_url"] is None and fila["portada_diseno_propuesta_url"] is None
    assert not _en_disco(vigente) and not _en_disco(propuesta)


def test_poner_nueva_conservando_la_anterior_tambien_limpia(repo):
    """El agente (`conservar_anterior=True`) y cualquier perfil pasan por `portada.poner_nueva`."""
    c = _comercio(repo, portada_diseno_url=f"{BASE}/local-d/diseno-aaa.jpg",
                  portada_diseno_propuesta_url=f"{BASE}/local-d/diseno-bbb.jpg")
    portada.poner_nueva(repo, c, f"{BASE}/local-d/nueva.jpg", None, conservar_anterior=True)
    fila = repo.comercios["com-d"]
    assert fila["portada_diseno_url"] is None and fila["portada_diseno_propuesta_url"] is None


def test_ya_es_la_portada_no_limpia_el_diseno(client, repo, admin_token):
    c, vigente, _ = _con_diseno(client, repo, admin_token)
    repo.comercio_fotos.append({"id": "f2", "comercio_id": "com-d", "url": c["portada_url"],
                                "thumb_url": c["portada_thumb_url"], "orden": 0,
                                "created_at": "2026-01-01T00:00:00+00:00"})
    assert client.put("/admin/comercio/com-d/portada", headers=_h(admin_token), json={"foto_id": "f2"}).status_code == 200
    assert repo.comercios["com-d"]["portada_diseno_url"] == vigente


def test_soltar_archivo_solo_borra_archivos_de_diseno_del_propio_comercio():
    guardar_foto_local("local-d/diseno-ok.jpg", b"x")
    guardar_foto_local("local-d/foto-real.jpg", b"x")
    guardar_foto_local("otro/diseno-ajeno.jpg", b"x")
    c = {"slug": "local-d"}
    pd.soltar_archivo(c, f"{BASE}/local-d/foto-real.jpg")       # no es de diseño
    pd.soltar_archivo(c, f"{BASE}/otro/diseno-ajeno.jpg")       # es de otro comercio
    pd.soltar_archivo(c, "https://otro.sitio/local-d/diseno-ok.jpg")
    pd.soltar_archivo(c, None)
    assert _en_disco(f"{BASE}/local-d/foto-real.jpg") and _en_disco(f"{BASE}/otro/diseno-ajeno.jpg")
    assert _en_disco(f"{BASE}/local-d/diseno-ok.jpg")
    pd.soltar_archivo(c, f"{BASE}/local-d/diseno-ok.jpg")
    assert not _en_disco(f"{BASE}/local-d/diseno-ok.jpg")


def test_admin_lista_las_columnas_de_diseno():
    from app.db.repository import _COLS_COMERCIO_ADMIN
    cols = {c.strip() for c in _COLS_COMERCIO_ADMIN.split(",")}
    assert {"portada_diseno_url", "portada_diseno_propuesta_url"} <= cols


# ══════════════════════════════════════════ migración 0200

SQL = RAIZ / "supabase" / "migrations" / "0200_portada_diseno.sql"
COPIA = RAIZ / "selfhost" / "postgres-init" / "0200_portada_diseno.sql"


def test_0200_copias_identicas():
    assert SQL.read_bytes() == COPIA.read_bytes()


def test_0200_publica_da_grant_por_columna_a_anon_y_authenticated():
    sql = SQL.read_text(encoding="utf-8")
    sin_comentarios = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
    assert "add column if not exists portada_diseno_url text" in sin_comentarios
    assert "grant select (portada_diseno_url) on public.comercios to anon, authenticated;" in sin_comentarios
    assert "grant select on public.comercios" not in sin_comentarios        # nunca la tabla entera


def test_0200_la_propuesta_es_privada_sin_grant():
    sql = SQL.read_text(encoding="utf-8")
    sin_comentarios = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
    assert "add column if not exists portada_diseno_propuesta_url text" in sin_comentarios
    grants = [l for l in sin_comentarios.splitlines() if l.lower().startswith("grant")]
    assert grants and all("portada_diseno_propuesta_url" not in g for g in grants)
    # la comprobación de la migración exige que anon y authenticated NO puedan leerla
    assert "has_column_privilege(v_rol, 'public.comercios', 'portada_diseno_propuesta_url', 'select')" in sin_comentarios


def test_0200_sin_borrado_fisico_y_en_transaccion():
    sql = SQL.read_text(encoding="utf-8").lower()
    assert "delete from" not in sql and "truncate" not in sql and "drop " not in sql
    assert "begin;" in sql and "commit;" in sql
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
