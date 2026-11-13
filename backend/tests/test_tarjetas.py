"""Carga de comercios desde fotos de tarjetas (docs/carga-tarjetas.md): un test por criterio de terminado.

Nada sale a la red: el lector (Tesseract) y Nominatim se reemplazan, y Gemini no se llama nunca salvo que el
test lo pida. Las imágenes son JPEG/PNG/WebP chicos generados con Pillow.
"""
import re
import uuid
from io import BytesIO
from pathlib import Path

import pytest
import structlog
from PIL import Image

from app.core import auth
from app.core.config import settings
from app.services import cost_switches, tarjetas
from app.services import vision
from app.services.vision import LectorFallo, LectorTransitorio

#: Las funciones REALES, guardadas antes de que el autouse las reemplace por una que falla si salen a la red.
NOMINATIM_REAL = tarjetas._pedir_nominatim
GEMINI_REAL = vision.leer_texto_tarjeta

CIUDAD = str(uuid.uuid4())
TEXTO_COMPLETO = """PANADERIA LA ESQUINA
Pan fresco todos los días
Av. Costanera esq. Sucre Nº 440
Cel: 7012 3456  Fijo: (4) 661 2345
ventas@laesquina.com
www.laesquina.com.bo
IG: @panaderialaesquina"""


def h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def datos():
    return h(auth.make_token("datos@uruku.bo", rol="x", roles=["x"], permisos=["datos"]))


@pytest.fixture
def sin_datos():
    return h(auth.make_token("otro@uruku.bo", rol="x", roles=["x"], permisos=["moderar"]))


@pytest.fixture(autouse=True)
def _sin_red_ni_esperas(monkeypatch):
    """Nominatim y Gemini NUNCA se llaman de verdad; el segundo de espera del 1/seg no se duerme."""
    tarjetas.reiniciar_cache()
    cost_switches.reiniciar_cache()
    monkeypatch.setattr(tarjetas, "_dormir", lambda s: None)

    def sin_red(params):
        raise AssertionError("Nominatim: un test salió a la red")

    def sin_gemini(data):
        raise AssertionError("Gemini: un test lo llamó sin prender el interruptor")

    monkeypatch.setattr(tarjetas, "_pedir_nominatim", sin_red)
    monkeypatch.setattr("app.services.vision.leer_texto_tarjeta", sin_gemini)
    monkeypatch.setattr(settings, "gemini_api_key", "")
    yield
    tarjetas.reiniciar_cache()


def imagen(formato="JPEG", color=(200, 30, 30), lado=64) -> bytes:
    buf = BytesIO()
    Image.new("RGB", (lado, lado), color).save(buf, format=formato)
    return buf.getvalue()


def color(i: int) -> tuple:
    return (i * 40 % 256, (i * 70 + 10) % 256, (i * 20 + 100) % 256)


def subir(client, headers, archivos, ciudad=CIUDAD):
    """`archivos`: lista de (nombre, bytes)."""
    return client.post("/admin/importados/tarjetas", headers=headers, data={"ciudad_id": ciudad},
                       files=[("fotos", (n, b, "image/jpeg")) for n, b in archivos])


def lector(monkeypatch, textos):
    """Tesseract falso: devuelve `textos` en orden (el último se repite)."""
    cola = list(textos)

    def falso(data):
        return cola.pop(0) if len(cola) > 1 else cola[0]

    monkeypatch.setattr(tarjetas, "leer_con_tesseract", falso)
    return falso


def nominatim(monkeypatch, filas=None, llamadas=None):
    def falso(params):
        if llamadas is not None:
            llamadas.append(params)
        if isinstance(filas, Exception):
            raise filas
        return filas or []

    monkeypatch.setattr(tarjetas, "_pedir_nominatim", falso)


def ciudad_con_centro(repo, monkeypatch, lat=-22.7361, lng=-64.3433, nombre="Bermejo"):
    fila = {"id": CIUDAD, "slug": "bermejo", "nombre": nombre, "lat": lat, "lng": lng}
    monkeypatch.setattr(repo, "get_ciudad_por_id", lambda cid: fila if cid else None)
    return fila


# ═══════════════════════════════════════════════════════ el archivo: tipo por los bytes

def test_el_tipo_se_decide_por_los_bytes_y_no_por_el_nombre():
    assert tarjetas.tipo_de_imagen(imagen("JPEG")) == "jpeg"
    assert tarjetas.tipo_de_imagen(imagen("PNG")) == "png"
    assert tarjetas.tipo_de_imagen(imagen("WEBP")) == "webp"
    assert tarjetas.tipo_de_imagen(b"GIF89a....") is None
    assert tarjetas.tipo_de_imagen(b"<?php echo 1; ?>") is None
    assert tarjetas.tipo_de_imagen(b"%PDF-1.4") is None
    assert tarjetas.tipo_de_imagen(b"") is None
    assert tarjetas.tipo_de_imagen(b"RIFF\x00\x00\x00\x00WAVE") is None


# ═══════════════════════════════════════════════════════ los campos (sin inventar)

def test_saca_nombre_direccion_telefonos_correo_web_y_red():
    c = tarjetas.extraer_campos(TEXTO_COMPLETO)
    assert c.nombre == "PANADERIA LA ESQUINA"
    assert c.direccion == "Av. Costanera esq. Sucre Nº 440"
    assert [t.numero for t in c.telefonos] == ["+59170123456", "+59146612345"]
    assert c.email == "ventas@laesquina.com"
    assert c.website == "https://www.laesquina.com.bo"
    assert c.redes == {"instagram": "https://instagram.com/panaderialaesquina"}


def test_el_primer_celular_va_a_whatsapp_y_el_resto_a_telefono():
    c = tarjetas.extraer_campos("Ferretería Sur\nTel: 4 661 2345\nCel: 7012 3456\nCel: 6123 4567")
    wa, tel = tarjetas.repartir_telefonos(c.telefonos)
    assert wa == "59170123456"
    assert tel == "+591 4 661 2345 / +591 6123 4567"


def test_un_argentino_sin_9_se_toma_como_celular():
    c = tarjetas.extraer_campos("Kiosco El Paso\nWhatsApp 387 4123456")
    wa, tel = tarjetas.repartir_telefonos(c.telefonos)
    assert wa == "5493874123456" and tel is None


def test_sin_celular_todos_van_a_telefono_y_whatsapp_queda_vacio():
    wa, tel = tarjetas.repartir_telefonos(tarjetas.extraer_campos("Estudio Contable\n(4) 661 2345").telefonos)
    assert wa is None and tel == "+591 4 661 2345"


@pytest.mark.parametrize("texto", ["", "   \n  ", "|| ~~ ..", "x\n--\n12", "!!! ??? ###"])
def test_con_texto_vacio_o_basura_no_inventa_nada(texto):
    c = tarjetas.extraer_campos(texto)
    assert c.nombre is None and c.direccion is None and c.telefonos == []
    assert c.email is None and c.website is None and c.redes == {}


def test_los_numeros_de_uruku_no_son_del_comercio():
    c = tarjetas.extraer_campos("Casa Pérez\nCel 67671888\nCel 7012 3456")
    assert [t.numero for t in c.telefonos] == ["+59170123456"]


def test_una_linea_de_oficio_no_gana_como_nombre():
    c = tarjetas.extraer_campos("Lic. Juan Pérez - Gerente\nELECTRO HOGAR\nCel 7012 3456")
    assert c.nombre == "ELECTRO HOGAR"


def test_la_direccion_se_reconoce_por_las_palabras_de_calle():
    for linea in ("Calle Bolívar 123", "Av. 6 de Agosto s/n", "Barrio Los Pinos, zona norte", "Esq. Sucre y Junín", "Mza 4 Lote 7 #12"):
        assert tarjetas.extraer_campos(f"MI NEGOCIO\n{linea}").direccion, linea
    assert tarjetas.extraer_campos("AVICOLA EL GALPON\nCel 7012 3456").direccion is None     # «av» dentro de una palabra


# ═══════════════════════════════════════════════════════ criterio 1: 5 fotos → 5 importados

def test_cinco_fotos_crean_cinco_importados_con_lo_leido(client, repo, datos, monkeypatch):
    textos = [TEXTO_COMPLETO,
              "Ferretería Sur\nCalle Bolívar 123\nCel: 6123 4567",
              "",                                          # una foto borrosa: no se lee nada
              "Kiosco El Paso\nTel 387 4123456",
              "Taller Mecánico Ruiz\nBarrio Centro\nsoporte@ruiz.com.bo"]
    lector(monkeypatch, textos)
    r = subir(client, datos, [(f"t{i}.jpg", imagen(color=color(i))) for i in range(5)])
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["errores"] == [] and len(cuerpo["items"]) == 5
    assert len(repo.importados) == 5
    a, b, c, d, e = cuerpo["items"]
    assert a["fuente"] == "tarjeta" and a["estado"] == "nuevo" and a["ciudad_id"] == CIUDAD
    assert a["nombre"] == "PANADERIA LA ESQUINA" and a["whatsapp"] == "59170123456"
    assert a["telefono"] == "+591 4 661 2345" and a["email"] == "ventas@laesquina.com"
    assert a["website"] == "https://www.laesquina.com.bo" and a["direccion"].startswith("Av. Costanera")
    assert a["lector"] == "tesseract" and a["tiene_foto"] is True and a["texto_leido"].startswith("PANADERIA")
    assert b["nombre"] == "Ferretería Sur" and b["direccion"] == "Calle Bolívar 123"
    # la vacía existe, con todo vacío: nunca inventado
    assert c["nombre"] is None and c["whatsapp"] is None and c["telefono"] is None and c["direccion"] is None
    assert d["whatsapp"] == "5493874123456"
    assert e["nombre"] == "Taller Mecánico Ruiz" and e["email"] == "soporte@ruiz.com.bo" and e["whatsapp"] is None


def test_la_referencia_de_la_foto_no_sale_por_la_api(client, repo, datos, monkeypatch):
    lector(monkeypatch, [TEXTO_COMPLETO])
    item = subir(client, datos, [("t.jpg", imagen())]).json()["items"][0]
    assert "foto_ref" not in item and item["tiene_foto"] is True
    fila = repo.importados[item["id"]]
    assert fila["foto_ref"].startswith("privado:tarjetas/")
    listado = client.get("/admin/importados?fuente=tarjeta", headers=datos).json()["items"]
    assert "foto_ref" not in listado[0] and listado[0]["tiene_foto"] is True


def test_la_foto_se_guarda_en_el_disco_privado_y_no_bajo_fotos(client, repo, datos, monkeypatch):
    lector(monkeypatch, [TEXTO_COMPLETO])
    item = subir(client, datos, [("t.jpg", imagen())]).json()["items"][0]
    from app.services import archivos_privados
    ruta = archivos_privados.ruta_segura(repo.importados[item["id"]]["foto_ref"])
    assert ruta and ruta.is_file()
    assert Path(settings.fotos_dir).resolve() not in ruta.resolve().parents
    assert not any(Path(settings.fotos_dir).rglob("*.jpg")) if Path(settings.fotos_dir).exists() else True


def test_un_archivo_malo_no_frena_a_los_demas_y_dice_por_que(client, repo, datos, monkeypatch):
    lector(monkeypatch, [TEXTO_COMPLETO])
    grande = b"\xff\xd8\xff" + b"0" * tarjetas.MAX_BYTES        # un byte de más que 10 MB
    r = subir(client, datos, [("ok.jpg", imagen()), ("script.jpg", b"<?php evil(); ?>"), ("vacio.png", b""),
                              ("gif.jpg", b"GIF89a" + b"0" * 50), ("../../etc/enorme.jpg", grande)])
    # De a 5 por pedido (tarjetas.MAX_ARCHIVOS): el panel parte la selección en tandas.
    r2 = subir(client, datos, [("rota.jpg", b"\xff\xd8\xff\xe0 no es un jpeg de verdad")])
    cuerpo = r.json()
    assert r.status_code == 200 and len(cuerpo["items"]) == 1
    assert r2.status_code == 200 and r2.json()["items"] == []
    motivos = {e["archivo"]: e["motivo"] for e in cuerpo["errores"] + r2.json()["errores"]}
    assert motivos["script.jpg"] == "No es una imagen JPEG, PNG o WebP"
    assert motivos["vacio.png"] == "El archivo está vacío"
    assert motivos["gif.jpg"] == "No es una imagen JPEG, PNG o WebP"
    assert motivos["enorme.jpg"] == "La foto pesa más de 10 MB"          # sin la carpeta del nombre
    assert "dañada" in motivos["rota.jpg"]
    assert len(repo.importados) == 1


def test_acepta_png_y_webp(client, datos, monkeypatch):
    lector(monkeypatch, [TEXTO_COMPLETO])
    r = subir(client, datos, [("a.png", imagen("PNG")), ("b.webp", imagen("WEBP", color=(1, 2, 3)))])
    assert len(r.json()["items"]) == 2 and r.json()["errores"] == []


def test_mas_de_20_fotos_o_ninguna_o_ciudad_mala(client, datos, monkeypatch):
    lector(monkeypatch, [""])
    assert subir(client, datos, [(f"{i}.jpg", imagen(color=color(i))) for i in range(tarjetas.MAX_ARCHIVOS + 1)]).status_code == 400
    assert client.post("/admin/importados/tarjetas", headers=datos, data={"ciudad_id": CIUDAD}).status_code == 422
    assert subir(client, datos, [("a.jpg", imagen())], ciudad="no-es-uuid").status_code == 400
    assert subir(client, datos, [("a.jpg", imagen())], ciudad="x'; drop table ciudades;--").status_code == 400
    assert len(subir(client, datos, [(f"{i}.jpg", imagen(color=color(i))) for i in range(tarjetas.MAX_ARCHIVOS)]).json()["items"]) == tarjetas.MAX_ARCHIVOS


def test_una_ciudad_que_no_existe_da_404(client, repo, datos, monkeypatch):
    monkeypatch.setattr(repo, "get_ciudad_por_id", lambda cid: None)
    assert subir(client, datos, [("a.jpg", imagen())]).status_code == 404


# ═══════════════════════════════════════════════════════ criterio 2: idempotente

def test_la_misma_foto_dos_veces_no_crea_dos_filas(client, repo, datos, monkeypatch):
    lector(monkeypatch, [TEXTO_COMPLETO])
    foto = imagen()
    primera = subir(client, datos, [("a.jpg", foto)]).json()
    assert len(primera["items"]) == 1
    segunda = subir(client, datos, [("copia-con-otro-nombre.jpg", foto)]).json()
    assert segunda["items"] == [] and segunda["errores"] == [{"archivo": "copia-con-otro-nombre.jpg",
                                                              "motivo": "Esa foto ya estaba cargada"}]
    assert len(repo.importados) == 1
    fila = next(iter(repo.importados.values()))
    assert fila["fuente_id"] == tarjetas.fuente_id_de(foto) and re.fullmatch(r"tarjeta:[0-9a-f]{64}", fila["fuente_id"])


def test_la_misma_foto_en_el_mismo_lote_se_carga_una_vez(client, repo, datos, monkeypatch):
    lector(monkeypatch, [TEXTO_COMPLETO])
    foto = imagen()
    r = subir(client, datos, [("a.jpg", foto), ("b.jpg", foto)]).json()
    assert len(r["items"]) == 1 and len(r["errores"]) == 1 and len(repo.importados) == 1


def test_la_carrera_de_dos_subidas_simultaneas_no_deja_la_foto_de_mas(repo, crepo, monkeypatch):
    """Otra subida ganó el INSERT: se informa «ya estaba» y la foto guardada de más se borra."""
    from app.services import archivos_privados
    monkeypatch.setattr(tarjetas, "leer_con_tesseract", lambda d: TEXTO_COMPLETO)
    monkeypatch.setattr(repo, "crear_importado", lambda fila: None)
    r = tarjetas.procesar(repo, crepo, imagen(), {"id": CIUDAD, "nombre": "Bermejo"}, {})
    assert r.fila is None and r.motivo == "Esa foto ya estaba cargada"
    raiz = archivos_privados.raiz()
    assert not raiz.exists() or not list(raiz.rglob("*.jpg"))


# ═══════════════════════════════════════════════════════ criterio 3: la ubicación

def test_una_direccion_que_nominatim_encuentra_queda_aproximada_dentro_de_la_ciudad(client, repo, datos, monkeypatch):
    ciudad_con_centro(repo, monkeypatch)
    llamadas = []
    nominatim(monkeypatch, [{"lat": "-22.7400", "lon": "-64.3400", "display_name": "Av. Costanera 440, Bermejo"}], llamadas)
    lector(monkeypatch, [TEXTO_COMPLETO])
    item = subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]
    assert item["ubicacion"] == "aproximada" and item["lat"] == -22.74 and item["lng"] == -64.34
    p = llamadas[0]
    assert p["countrycodes"] == "bo,ar" and p["bounded"] == 1 and p["limit"] == 1 and p["format"] == "jsonv2"
    assert "Bermejo" in p["q"] and "Costanera" in p["q"]
    oeste, norte, este, sur = (float(v) for v in p["viewbox"].split(","))
    assert oeste < -64.3433 < este and sur < -22.7361 < norte
    assert 0.12 < norte - sur < 0.32            # ~15 km de radio: caja de unos 30 km de lado


def test_una_direccion_que_no_se_encuentra_queda_sin_punto(client, repo, datos, monkeypatch):
    ciudad_con_centro(repo, monkeypatch)
    nominatim(monkeypatch, [])
    lector(monkeypatch, [TEXTO_COMPLETO])
    item = subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]
    assert item["lat"] is None and item["lng"] is None and item["ubicacion"] == "no_encontrada"


def test_un_resultado_fuera_de_la_ciudad_no_se_acepta(client, repo, datos, monkeypatch):
    ciudad_con_centro(repo, monkeypatch)
    nominatim(monkeypatch, [{"lat": "-17.78", "lon": "-63.18", "display_name": "Santa Cruz"}])     # otra ciudad
    lector(monkeypatch, [TEXTO_COMPLETO])
    item = subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]
    assert item["lat"] is None and item["ubicacion"] == "no_encontrada"


def test_si_nominatim_se_cae_la_tarjeta_igual_se_carga_sin_punto(client, repo, datos, monkeypatch):
    ciudad_con_centro(repo, monkeypatch)
    nominatim(monkeypatch, TimeoutError("timeout"))
    lector(monkeypatch, [TEXTO_COMPLETO])
    r = subir(client, datos, [("a.jpg", imagen())]).json()
    assert r["errores"] == [] and r["items"][0]["ubicacion"] == "no_encontrada"


def test_sin_direccion_no_se_consulta_nominatim(client, datos, monkeypatch):
    llamadas = []
    nominatim(monkeypatch, [], llamadas)
    lector(monkeypatch, ["Kiosco El Paso\nCel 7012 3456"])
    item = subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]
    assert llamadas == [] and item["ubicacion"] == "no_encontrada"


def test_respuestas_raras_de_nominatim_no_rompen(repo, monkeypatch):
    for filas in ([{"lat": "abc", "lon": "x"}], [{}], [None], [{"lat": "nan", "lon": "1"}], [{"lat": "95", "lon": "0"}]):
        tarjetas.reiniciar_cache()
        assert tarjetas.buscar_direccion("Calle Falsa 123", None, pedir=lambda p, f=filas: f) is None


def test_politica_de_nominatim_user_agent_timeout_cache_y_un_pedido_por_segundo(monkeypatch):
    assert tarjetas.USER_AGENT == "URUKU/1.0 (+https://uruku.bo)"
    assert tarjetas.TIMEOUT_NOMINATIM == 8 and tarjetas.INTERVALO_NOMINATIM == 1.0
    capturado = {}

    class R:
        def raise_for_status(self): pass
        def json(self): return []

    import httpx

    def get(url, **kw):
        capturado.update(url=url, **kw)
        return R()

    monkeypatch.setattr(httpx, "get", get)
    assert NOMINATIM_REAL({"q": "x"}) == []
    assert capturado["url"] == "https://nominatim.openstreetmap.org/search"
    assert capturado["headers"]["User-Agent"] == "URUKU/1.0 (+https://uruku.bo)"
    assert capturado["timeout"] == 8 and capturado["follow_redirects"] is False


def test_dos_consultas_distintas_esperan_un_segundo_entre_si(monkeypatch):
    esperas = []
    monkeypatch.setattr(tarjetas, "_dormir", esperas.append)
    ok = lambda p: [{"lat": "-22.7", "lon": "-64.3", "display_name": "x"}]  # noqa: E731
    tarjetas.buscar_direccion("Calle Uno 111", None, pedir=ok)
    assert esperas == []                                       # la primera no espera
    tarjetas.buscar_direccion("Calle Dos 222", None, pedir=ok)
    assert len(esperas) == 1 and 0.5 < esperas[0] <= 1.0


def test_la_misma_consulta_sale_de_la_cache_y_no_llama_dos_veces(monkeypatch):
    n = []
    def pedir(p):
        n.append(p)
        return [{"lat": "-22.7", "lon": "-64.3", "display_name": "x"}]
    a = tarjetas.buscar_direccion("Calle Uno 111", {"id": "c1", "nombre": "Bermejo"}, pedir=pedir)
    b = tarjetas.buscar_direccion("  calle UNO 111 ", {"id": "c1", "nombre": "Bermejo"}, pedir=pedir)
    assert a == b and len(n) == 1
    tarjetas.buscar_direccion("Calle Uno 111", {"id": "c2", "nombre": "Yacuiba"}, pedir=pedir)   # otra ciudad: otra consulta
    assert len(n) == 2


def test_un_error_de_red_no_se_guarda_en_la_cache(monkeypatch):
    n = []
    def pedir(p):
        n.append(1)
        if len(n) == 1:
            raise TimeoutError("x")
        return [{"lat": "-22.7", "lon": "-64.3", "display_name": "x"}]
    with pytest.raises(tarjetas.UbicacionNoDisponible):
        tarjetas.buscar_direccion("Calle Uno 111", None, pedir=pedir)
    assert tarjetas.buscar_direccion("Calle Uno 111", None, pedir=pedir)["lat"] == -22.7


# ═══════════════════════════════════════════════════════ criterio 4: repetidos

def _comercio(repo, **extra):
    cid = f"com-{len(repo.comercios) + 1}"
    repo.comercios[cid] = {"id": cid, "nombre": "Panadería Vieja", "slug": cid, "activo": True, **extra}
    return cid


def test_un_telefono_que_ya_tiene_un_comercio_marca_el_repetido(client, repo, datos, monkeypatch):
    cid = _comercio(repo, whatsapp="59170123456")
    lector(monkeypatch, [TEXTO_COMPLETO])
    item = subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]
    assert item["duplicado_de"] == cid and item["duplicado_nombre"] == "Panadería Vieja"
    listado = client.get("/admin/importados?fuente=tarjeta", headers=datos).json()["items"][0]
    assert listado["duplicado_de"] == cid and listado["duplicado_nombre"] == "Panadería Vieja"


def test_el_repetido_tambien_se_detecta_por_el_telefono_fijo_y_con_otro_formato(client, repo, datos, monkeypatch):
    cid = _comercio(repo, telefono="4 661-2345")
    lector(monkeypatch, [TEXTO_COMPLETO])
    assert subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]["duplicado_de"] == cid


def test_el_repetido_tambien_se_detecta_por_un_numero_autorizado(client, repo, datos, monkeypatch):
    cid = _comercio(repo)
    repo.comercio_numeros.append({"comercio_id": cid, "numero": "59170123456", "activo": True})
    lector(monkeypatch, [TEXTO_COMPLETO])
    assert subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]["duplicado_de"] == cid


def test_un_comercio_dado_de_baja_no_cuenta_como_repetido(client, repo, datos, monkeypatch):
    _comercio(repo, whatsapp="59170123456", activo=False)
    lector(monkeypatch, [TEXTO_COMPLETO])
    assert subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]["duplicado_de"] is None


def test_sin_coincidencia_no_hay_repetido(client, repo, datos, monkeypatch):
    _comercio(repo, whatsapp="59171111119")
    lector(monkeypatch, [TEXTO_COMPLETO])
    assert subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]["duplicado_de"] is None


# ═══════════════════════════════════════════════════════ criterio 5: la foto sólo con sesión de panel

def _item(client, datos, monkeypatch):
    lector(monkeypatch, [TEXTO_COMPLETO])
    return subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]


def test_la_foto_se_ve_con_sesion_y_sin_cache(client, datos, monkeypatch):
    item = _item(client, datos, monkeypatch)
    r = client.get(f"/admin/importados/{item['id']}/foto", headers=datos)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "no-store" and r.headers["x-content-type-options"] == "nosniff"
    assert r.content[:3] == b"\xff\xd8\xff"


def test_la_foto_no_se_abre_sin_sesion_ni_sin_permiso_ni_con_otro_rol(client, datos, sin_datos, monkeypatch):
    item = _item(client, datos, monkeypatch)
    url = f"/admin/importados/{item['id']}/foto"
    assert client.get(url).status_code in (401, 403)
    assert client.get(url, headers=h("basura")).status_code in (401, 403)
    assert client.get(url, headers=sin_datos).status_code == 403
    comercio = h(auth.make_comercio_token("com-1", "x@y.com"))
    assert client.get(url, headers=comercio).status_code in (401, 403)


def test_la_foto_de_un_importado_que_no_es_tarjeta_o_no_existe_da_404(client, repo, datos):
    osm = str(uuid.uuid4())
    repo.importados[osm] = {"id": osm, "fuente": "osm", "fuente_id": "node/1", "estado": "nuevo",
                            "foto_ref": "privado:otra/cosa.jpg"}
    assert client.get(f"/admin/importados/{osm}/foto", headers=datos).status_code == 404
    assert client.get(f"/admin/importados/{uuid.uuid4()}/foto", headers=datos).status_code == 404
    assert client.get("/admin/importados/no-es-uuid/foto", headers=datos).status_code == 404


def test_una_referencia_adulterada_no_sale_del_directorio_privado(client, repo, datos, monkeypatch):
    item = _item(client, datos, monkeypatch)
    repo.importados[item["id"]]["foto_ref"] = "privado:../../../../etc/passwd"
    assert client.get(f"/admin/importados/{item['id']}/foto", headers=datos).status_code == 404


def test_todas_las_rutas_nuevas_piden_sesion_y_el_permiso_datos(client, repo, sin_datos):
    imp = str(uuid.uuid4())
    repo.importados[imp] = {"id": imp, "fuente": "tarjeta", "fuente_id": "tarjeta:x", "estado": "nuevo"}
    pedidos = [("post", "/admin/importados/tarjetas", {"data": {"ciudad_id": CIUDAD},
                                                       "files": [("fotos", ("a.jpg", imagen(), "image/jpeg"))]}),
               ("get", f"/admin/importados/{imp}/foto", {}),
               ("patch", f"/admin/importados/{imp}", {"json": {"nombre": "x"}}),
               ("post", f"/admin/importados/{imp}/ubicar", {"json": {"direccion": "Calle Falsa 123"}}),
               ("get", "/admin/importados?fuente=tarjeta", {}),
               ("post", f"/admin/importados/{imp}/promover", {"json": {}}),
               ("post", f"/admin/importados/{imp}/descartar", {})]
    for metodo, url, kw in pedidos:
        assert getattr(client, metodo)(url, **kw).status_code in (401, 403), (metodo, url)
        assert getattr(client, metodo)(url, headers=sin_datos, **kw).status_code == 403, (metodo, url)
    assert repo.importados[imp]["estado"] == "nuevo" and "nombre" not in repo.importados[imp]


def test_el_permiso_es_el_vigente_y_no_el_del_token(client, repo, datos, monkeypatch):
    """Un token viejo con `datos` no alcanza si hoy la cuenta ya no lo tiene (como el resto del panel)."""
    lector(monkeypatch, [TEXTO_COMPLETO])
    from app.core import auth as _auth
    monkeypatch.setattr(_auth, "_vigente_tiene", lambda estado, permisos: False)
    assert subir(client, datos, [("a.jpg", imagen())]).status_code == 403
    assert client.get("/admin/importados", headers=datos).status_code == 403


# ═══════════════════════════════════════════════════════ criterio 6: el interruptor de Gemini

def test_con_el_interruptor_apagado_no_se_llama_a_gemini_nunca(client, crepo, datos, monkeypatch):
    # el autouse ya hace que Gemini explote si lo llaman; con clave presente y SIN prender, igual no se llama
    monkeypatch.setattr(settings, "gemini_api_key", "clave-de-prueba")
    lector(monkeypatch, [TEXTO_COMPLETO])
    r = subir(client, datos, [("a.jpg", imagen())]).json()
    assert r["errores"] == [] and r["items"][0]["lector"] == "tesseract"
    assert tarjetas.motor_activo(crepo) == "tesseract"


def test_prendido_pero_sin_clave_tampoco_se_llama(client, crepo, datos, monkeypatch):
    cost_switches.set(crepo, cost_switches.GEMINI_TARJETAS, True, "dueno@uruku.bo")
    lector(monkeypatch, [TEXTO_COMPLETO])
    assert subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]["lector"] == "tesseract"


def test_el_interruptor_de_telefonos_no_prende_el_de_tarjetas(crepo, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    cost_switches.set(crepo, cost_switches.GEMINI_PHONE_SCAN, True, "dueno@uruku.bo")
    cost_switches.set(crepo, cost_switches.GEMINI_CONTENT, True, "dueno@uruku.bo")
    assert tarjetas.motor_activo(crepo) == "tesseract"


def test_prendido_y_con_clave_lee_con_gemini_y_lo_registra(client, crepo, datos, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "clave-de-prueba")
    cost_switches.set(crepo, cost_switches.GEMINI_TARJETAS, True, "dueno@uruku.bo")
    llamadas = []
    monkeypatch.setattr("app.services.vision.leer_texto_tarjeta", lambda d: llamadas.append(1) or TEXTO_COMPLETO)
    monkeypatch.setattr(tarjetas, "leer_con_tesseract", lambda d: pytest.fail("no debía usar Tesseract"))
    item = subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]
    assert llamadas == [1] and item["lector"] == "gemini" and item["nombre"] == "PANADERIA LA ESQUINA"


@pytest.mark.parametrize("falla", [LectorTransitorio("cuota"), LectorFallo("rechazada")])
def test_si_gemini_falla_se_sigue_con_tesseract(client, crepo, datos, monkeypatch, falla):
    monkeypatch.setattr(settings, "gemini_api_key", "clave-de-prueba")
    cost_switches.set(crepo, cost_switches.GEMINI_TARJETAS, True, "dueno@uruku.bo")
    def explota(d):
        raise falla
    monkeypatch.setattr("app.services.vision.leer_texto_tarjeta", explota)
    lector(monkeypatch, [TEXTO_COMPLETO])
    assert subir(client, datos, [("a.jpg", imagen())]).json()["items"][0]["lector"] == "tesseract"


def test_gemini_tarjetas_esta_en_el_catalogo_apagado_y_con_la_confirmacion_de_siempre(client, crepo):
    c = cost_switches.CATALOGO["gemini_tarjetas"]
    assert set(c) == {"label", "what", "cost", "off_means"} and all(c.values())
    assert cost_switches.esta_prendido(crepo, "gemini_tarjetas") is False
    dueno = h(auth.make_token("dueno@uruku.bo", rol="x", roles=["x"], permisos=["equipo"]))
    assert client.put("/admin/cost-switches/gemini_tarjetas", json={"enabled": True}, headers=dueno).status_code == 400
    r = client.put("/admin/cost-switches/gemini_tarjetas", json={"enabled": True, "confirm_cost": True}, headers=dueno)
    assert r.status_code == 200 and r.json()["enabled"] is True
    solo_difusion = h(auth.make_token("d@uruku.bo", rol="x", roles=["x"], permisos=["difusion"]))
    assert client.put("/admin/cost-switches/gemini_tarjetas", json={"enabled": False}, headers=solo_difusion).status_code == 403


def test_el_prompt_de_gemini_transcribe_y_el_modelo_lo_hace_con_una_foto_chica(monkeypatch):
    """`vision.leer_texto_tarjeta` con la red falsa: manda UNA imagen y devuelve las líneas."""
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    enviado = {}

    class R:
        status_code = 200
        text = ""
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": '{"lineas": ["PAN SA", "Cel 7012 3456", "", 5]}'}]}}]}

    def post(url, payload):
        enviado.update(payload=payload)
        return R()

    monkeypatch.setattr(vision, "_post_con_reintentos", post)
    assert GEMINI_REAL(imagen(lado=40)) == "PAN SA\nCel 7012 3456\n5"
    assert len(enviado["payload"]["contents"][0]["parts"]) == 2
    monkeypatch.setattr(vision, "_post_con_reintentos", lambda u, p: type("R", (), {
        "status_code": 200, "text": "", "json": lambda self: {"candidates": [{"content": {"parts": [{"text": "no es json"}]}}]}})())
    with pytest.raises(LectorFallo):
        GEMINI_REAL(imagen(lado=40))
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(vision.VisionNoConfigurada):
        GEMINI_REAL(imagen(lado=40))


# ═══════════════════════════════════════════════════════ el lector gratis

def test_tesseract_sin_instalar_da_un_motivo_claro_y_no_crea_nada(client, repo, datos, monkeypatch):
    def no_hay(data):
        raise LectorTransitorio("Tesseract no está instalado")
    monkeypatch.setattr(tarjetas, "leer_con_tesseract", no_hay)
    r = subir(client, datos, [("a.jpg", imagen()), ("b.jpg", imagen(color=(9, 9, 9)))]).json()
    assert r["items"] == [] and len(r["errores"]) == 2 and "no está disponible" in r["errores"][0]["motivo"]
    assert repo.importados == {}


def test_una_foto_que_el_lector_rechaza_se_informa_y_no_crea_fila(client, repo, datos, monkeypatch):
    def rechaza(data):
        raise LectorFallo("Tesseract no pudo leer la foto: timeout")
    monkeypatch.setattr(tarjetas, "leer_con_tesseract", rechaza)
    r = subir(client, datos, [("a.jpg", imagen())]).json()
    assert r["items"] == [] and r["errores"][0]["motivo"].startswith("Tesseract no pudo leer")
    assert repo.importados == {}


def test_tesseract_usa_el_mismo_preproceso_y_prueba_el_negativo_si_no_lee_nada(monkeypatch):
    pytesseract = pytest.importorskip("pytesseract")
    vistos = []

    def falso(im, lang=None, config=None, timeout=None):
        vistos.append((im.mode, im.size, lang, config, timeout))
        return "" if len(vistos) == 1 else "AGROPECUARIA SUR S.R.L."

    monkeypatch.setattr(pytesseract, "image_to_string", falso)
    monkeypatch.setattr(tarjetas, "_idioma_ocr", "spa+eng")
    assert tarjetas.leer_con_tesseract(imagen(lado=300)) == "AGROPECUARIA SUR S.R.L."
    assert len(vistos) == 2 and vistos[0][0] == "L" and max(vistos[0][1]) == 1600      # gris, lado mayor 1600
    assert vistos[0][2] == "spa+eng" and "--psm 3" in vistos[0][3] and vistos[0][4] == 30
    assert "whitelist" not in vistos[0][3]                                           # acá se leen letras


# ═══════════════════════════════════════════════════════ PATCH: corregir los campos

def _tarjeta(repo, **extra):
    iid = str(uuid.uuid4())
    repo.importados[iid] = {"id": iid, "fuente": "tarjeta", "fuente_id": f"tarjeta:{iid}", "ciudad_id": CIUDAD,
                            "estado": "nuevo", "nombre": "Panaderia La Esqina", "direccion": "Av. Costanera 440",
                            "telefono": None, "whatsapp": "59170123456", "website": None, "email": None,
                            "lat": None, "lng": None, "ubicacion": "no_encontrada", "foto_ref": None,
                            "texto_leido": "crudo", "lector": "tesseract", **extra}
    return iid


def test_patch_corrige_los_campos_y_no_toca_lo_que_no_viene(client, repo, datos):
    iid = _tarjeta(repo)
    r = client.patch(f"/admin/importados/{iid}", headers=datos, json={
        "nombre": "  Panadería   La Esquina ", "email": "VENTAS@Esquina.com", "website": "https://esquina.com.bo",
        "telefono": "(4) 661 2345", "rubro_slug": "gastronomia"})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["nombre"] == "Panadería La Esquina" and c["email"] == "ventas@esquina.com"
    assert c["website"] == "https://esquina.com.bo" and c["telefono"] == "(4) 661 2345"
    assert c["rubro_slug"] == "gastronomia" and c["direccion"] == "Av. Costanera 440" and c["whatsapp"] == "59170123456"


def test_patch_con_null_o_vacio_borra_el_campo(client, repo, datos):
    iid = _tarjeta(repo, email="a@b.co")
    c = client.patch(f"/admin/importados/{iid}", headers=datos, json={"email": None, "whatsapp": "", "direccion": "  "}).json()
    assert c["email"] is None and c["whatsapp"] is None and c["direccion"] is None


def test_patch_guardar_el_punto_lo_pasa_a_confirmada_y_borrarlo_a_no_encontrada(client, repo, datos):
    iid = _tarjeta(repo, lat=-22.7, lng=-64.3, ubicacion="aproximada")
    c = client.patch(f"/admin/importados/{iid}", headers=datos, json={"lat": -22.71, "lng": -64.31}).json()
    assert c["ubicacion"] == "confirmada" and c["lat"] == -22.71 and c["lng"] == -64.31
    c = client.patch(f"/admin/importados/{iid}", headers=datos, json={"lat": None, "lng": None}).json()
    assert c["ubicacion"] == "no_encontrada" and c["lat"] is None


@pytest.mark.parametrize("cuerpo", [
    {"lat": -22.7}, {"lng": -64.3}, {"lat": 91, "lng": 0}, {"lat": 0, "lng": 181},
    {"whatsapp": "123"}, {"website": "javascript:alert(1)"}, {"website": "https://user@evil.com"},
    {"email": "no-es-correo"}, {"rubro_slug": "no-existe"}, {"nombre": "x" * 500}, {"lat": "abc", "lng": 1},
])
def test_patch_rechaza_lo_invalido_y_no_guarda_nada(client, repo, datos, cuerpo):
    iid = _tarjeta(repo)
    antes = dict(repo.importados[iid])
    assert client.patch(f"/admin/importados/{iid}", headers=datos, json=cuerpo).status_code in (400, 422)
    assert repo.importados[iid] == antes


def test_patch_sólo_con_el_importado_sin_revisar_y_existente(client, repo, datos):
    for estado in ("promovido", "descartado"):
        iid = _tarjeta(repo, estado=estado)
        assert client.patch(f"/admin/importados/{iid}", headers=datos, json={"nombre": "x"}).status_code == 409
    assert client.patch(f"/admin/importados/{uuid.uuid4()}", headers=datos, json={"nombre": "x"}).status_code == 404
    assert client.patch("/admin/importados/no-es-uuid", headers=datos, json={"nombre": "x"}).status_code == 404


def test_patch_ignora_campos_que_no_son_suyos(client, repo, datos):
    iid = _tarjeta(repo)
    client.patch(f"/admin/importados/{iid}", headers=datos, json={"estado": "promovido", "foto_ref": "privado:x",
                                                                  "comercio_id": "com-1", "texto_leido": "pisado"})
    f = repo.importados[iid]
    assert f["estado"] == "nuevo" and f["foto_ref"] is None and f["texto_leido"] == "crudo"


# ═══════════════════════════════════════════════════════ ubicar

def test_ubicar_encuentra_y_guarda_el_punto_aproximado(client, repo, datos, monkeypatch):
    ciudad_con_centro(repo, monkeypatch)
    iid = _tarjeta(repo, ubicacion="confirmada", lat=-22.0, lng=-64.0)
    nominatim(monkeypatch, [{"lat": "-22.7390", "lon": "-64.3410", "display_name": "Calle Sucre 100, Bermejo, Bolivia"}])
    r = client.post(f"/admin/importados/{iid}/ubicar", headers=datos, json={"direccion": "Sucre 100"})
    assert r.status_code == 200, r.text
    assert r.json() == {"lat": -22.739, "lng": -64.341, "aproximada": True, "encontrado": True,
                        "display_name": "Calle Sucre 100, Bermejo, Bolivia", "metodo": "calle"}
    f = repo.importados[iid]
    assert f["lat"] == -22.739 and f["ubicacion"] == "aproximada" and f["direccion"] == "Sucre 100"


def test_ubicar_sin_resultado_no_cambia_nada(client, repo, datos, monkeypatch):
    ciudad_con_centro(repo, monkeypatch)
    iid = _tarjeta(repo, lat=-22.7, lng=-64.3, ubicacion="confirmada")
    antes = dict(repo.importados[iid])
    nominatim(monkeypatch, [])
    r = client.post(f"/admin/importados/{iid}/ubicar", headers=datos, json={"direccion": "Calle que no existe 999"})
    assert r.status_code == 200 and r.json()["encontrado"] is False and r.json()["lat"] is None
    assert repo.importados[iid] == antes


def test_ubicar_con_el_servicio_caido_da_503_y_no_cambia_nada(client, repo, datos, monkeypatch):
    iid = _tarjeta(repo)
    antes = dict(repo.importados[iid])
    nominatim(monkeypatch, ConnectionError("sin red"))
    r = client.post(f"/admin/importados/{iid}/ubicar", headers=datos, json={"direccion": "Calle Sucre 100"})
    assert r.status_code == 503 and "mapas" in r.json()["detail"]
    assert repo.importados[iid] == antes


def test_ubicar_valida_la_entrada(client, repo, datos):
    iid = _tarjeta(repo)
    assert client.post(f"/admin/importados/{iid}/ubicar", headers=datos, json={}).status_code == 422
    assert client.post(f"/admin/importados/{iid}/ubicar", headers=datos, json={"direccion": "ab"}).status_code == 400
    assert client.post(f"/admin/importados/{iid}/ubicar", headers=datos, json={"direccion": "x" * 500}).status_code == 422
    assert client.post(f"/admin/importados/{uuid.uuid4()}/ubicar", headers=datos, json={"direccion": "Calle Sucre 1"}).status_code == 404
    hecho = _tarjeta(repo, estado="promovido")
    assert client.post(f"/admin/importados/{hecho}/ubicar", headers=datos, json={"direccion": "Calle Sucre 1"}).status_code == 409


# ═══════════════════════════════════════════════════════ listado: filtro por fuente

def test_el_listado_filtra_por_fuente_y_valida_el_valor(client, repo, datos):
    repo.upsert_importado({"fuente": "osm", "fuente_id": "node/1", "nombre": "De OSM", "lat": -22.7, "lng": -64.3})
    _tarjeta(repo)
    todos = client.get("/admin/importados", headers=datos).json()
    assert todos["total"] == 2
    osm = client.get("/admin/importados?fuente=osm", headers=datos).json()["items"]
    assert [i["nombre"] for i in osm] == ["De OSM"] and osm[0]["tiene_foto"] is False
    tarj = client.get("/admin/importados?fuente=tarjeta", headers=datos).json()["items"]
    assert [i["fuente"] for i in tarj] == ["tarjeta"] and tarj[0]["email"] is None and tarj[0]["lector"] == "tesseract"
    assert client.get("/admin/importados?fuente=otra", headers=datos).status_code == 422


# ═══════════════════════════════════════════════════════ criterio 7: promover

def _lista_para_promover(repo, **extra):
    base = dict(nombre="Panadería La Esquina", telefono="+591 4 661 2345", whatsapp="59170123456",
                website="https://laesquina.com.bo", email="ventas@laesquina.com", lat=-22.7361, lng=-64.3433,
                ubicacion="confirmada", direccion="Av. Costanera 440", rubro_slug="gastronomia")
    return _tarjeta(repo, **{**base, **extra})


def test_promover_crea_el_comercio_con_los_datos_y_sin_verificar_ni_confiable(client, repo, datos):
    iid = _lista_para_promover(repo)
    r = client.post(f"/admin/importados/{iid}/promover", json={}, headers=datos)
    assert r.status_code == 200, r.text
    com = repo.comercios[r.json()["comercio"]["id"]]
    assert com["nombre"] == "Panadería La Esquina" and com["direccion"] == "Av. Costanera 440"
    assert com["whatsapp"] == "59170123456" and com["telefono"] == "+591 4 661 2345"
    assert com["sitio_web"] == "https://laesquina.com.bo" and com["email"] == "ventas@laesquina.com"
    assert com["lat"] == -22.7361 and com["lng"] == -64.3433 and com["ciudad_id"] == CIUDAD
    assert com["verificado"] is False and com["confiable"] is False and com["activo"] is True
    assert com["cargado_por"] == "import:tarjeta"
    assert "foto_ref" not in com and "texto_leido" not in com and "portada_url" not in com
    assert repo.importados[iid]["estado"] == "promovido" and repo.importados[iid]["comercio_id"] == com["id"]
    assert client.post(f"/admin/importados/{iid}/promover", json={}, headers=datos).status_code == 409


def test_promover_sin_punto_o_sin_nombre_no_se_puede(client, repo, datos):
    sin_punto = _tarjeta(repo, lat=None, lng=None)
    assert client.post(f"/admin/importados/{sin_punto}/promover", json={}, headers=datos).status_code == 400
    sin_nombre = _tarjeta(repo, nombre=None, lat=-22.7, lng=-64.3)
    assert client.post(f"/admin/importados/{sin_nombre}/promover", json={}, headers=datos).status_code == 400
    r = client.post(f"/admin/importados/{sin_nombre}/promover", json={"nombre": "Con Nombre"}, headers=datos)
    assert r.status_code == 200 and r.json()["comercio"]["nombre"] == "Con Nombre"


def test_promover_una_tarjeta_sin_celular_no_usa_el_fijo_como_whatsapp(client, repo, datos):
    iid = _lista_para_promover(repo, whatsapp=None)
    com = repo.comercios[client.post(f"/admin/importados/{iid}/promover", json={}, headers=datos).json()["comercio"]["id"]]
    assert com["whatsapp"] is None and com["telefono"] == "+591 4 661 2345"


def test_promover_toma_el_whatsapp_corregido_en_el_pedido_y_un_sitio_malo_se_descarta(client, repo, datos):
    iid = _lista_para_promover(repo, website="javascript:alert(1)")
    com = repo.comercios[client.post(f"/admin/importados/{iid}/promover", json={"whatsapp": "6123 4567"},
                                     headers=datos).json()["comercio"]["id"]]
    assert com["whatsapp"] == "59161234567" and com["sitio_web"] is None


def test_dos_tarjetas_con_el_mismo_nombre_no_chocan_en_el_slug(client, repo, datos):
    a, b = _lista_para_promover(repo), _lista_para_promover(repo)
    sa = client.post(f"/admin/importados/{a}/promover", json={}, headers=datos).json()["comercio"]["slug"]
    sb = client.post(f"/admin/importados/{b}/promover", json={}, headers=datos).json()["comercio"]["slug"]
    assert sa != sb


def test_los_importados_de_osm_se_promueven_como_siempre(client, repo, datos):
    repo.upsert_importado({"fuente": "osm", "fuente_id": "node/1", "nombre": "Panadería OSM", "lat": -22.7, "lng": -64.3,
                           "telefono": "59171234567", "rubro_slug": "gastronomia"})
    imp = next(iter(repo.importados))
    com = repo.comercios[client.post(f"/admin/importados/{imp}/promover", json={}, headers=datos).json()["comercio"]["id"]]
    assert com["cargado_por"] == "import:osm" and com["whatsapp"] == "59171234567"      # el comportamiento de antes
    assert "email" not in com and "telefono" not in com


def test_descartar_no_borra_y_no_muestra_la_foto(client, repo, datos, monkeypatch):
    item = _item(client, datos, monkeypatch)
    r = client.post(f"/admin/importados/{item['id']}/descartar?motivo=ya+lo+tenemos", headers=datos)
    assert r.status_code == 200 and "foto_ref" not in r.json()["importado"]
    assert repo.importados[item["id"]]["estado"] == "descartado" and repo.importados[item["id"]]["foto_ref"]


# ═══════════════════════════════════════════════════════ privacidad en los logs

def test_el_texto_y_los_telefonos_de_la_tarjeta_no_se_loguean(client, datos, monkeypatch):
    lector(monkeypatch, [TEXTO_COMPLETO])
    with structlog.testing.capture_logs() as logs:
        subir(client, datos, [("a.jpg", imagen())])
    volcado = repr(logs)
    assert any(l["event"] == "tarjetas.leida" for l in logs) and any(l["event"] == "tarjetas.lote" for l in logs)
    for secreto in ("7012", "6612345", "laesquina", "PANADERIA", "Costanera", "59170123456"):
        assert secreto not in volcado, secreto


# ═══════════════════════════════════════════════════════ el límite del cuerpo y la migración

def test_la_ruta_esta_en_la_tabla_de_topes_con_20_fotos_de_10_mb():
    from app.core.limite_cuerpo import MB, TOPE_POR_DEFECTO, tope_para
    tope = tope_para("/admin/importados/tarjetas")
    assert tope > TOPE_POR_DEFECTO and tope >= tarjetas.MAX_ARCHIVOS * 10 * MB
    assert tope_para("/admin/importados/abc/ubicar") == TOPE_POR_DEFECTO          # el JSON normal sigue en 2 MB


def test_un_cuerpo_mas_grande_que_el_tope_de_las_tarjetas_da_413(client, datos):
    from app.core.limite_cuerpo import tope_para
    r = client.post("/admin/importados/tarjetas", headers={**datos, "Content-Length": str(tope_para("/admin/importados/tarjetas") + 1)},
                    content=b"x")
    assert r.status_code == 413


RAIZ = Path(__file__).resolve().parents[2]
NOMBRE = "0195_importados_tarjetas.sql"


def _sql(carpeta):
    return (RAIZ / carpeta / NOMBRE).read_text(encoding="utf-8")


def _normal(sql):
    return re.sub(r"\s+", " ", re.sub(r"--[^\n]*", "", sql))


def test_migracion_identica_en_las_dos_carpetas_y_con_numero_unico():
    assert _sql("supabase/migrations").replace("\r\n", "\n") == _sql("selfhost/postgres-init").replace("\r\n", "\n")
    for carpeta in ("supabase/migrations", "selfhost/postgres-init"):
        assert sorted(p.name for p in (RAIZ / carpeta).glob("0195_*.sql")) == [NOMBRE]


def test_migracion_agrega_las_columnas_privadas_con_sus_checks_y_es_idempotente():
    sql = _normal(_sql("supabase/migrations"))
    for col in ("email", "ubicacion", "foto_ref", "texto_leido", "lector"):
        assert f"add column if not exists {col} text" in sql
    assert "check (ubicacion is null or ubicacion in ('aproximada', 'confirmada', 'no_encontrada'))" in sql
    assert "check (lector is null or lector in ('tesseract', 'gemini'))" in sql
    assert sql.count("drop constraint if exists") == 3
    assert not re.search(r"create index(?! if not exists)", sql)
    assert "delete from" not in sql and "drop table" not in sql and "drop column" not in sql
    assert sql.count("begin;") == 1 and sql.count("commit;") == 1 and sql.rstrip().endswith("notify pgrst, 'reload schema';")


def test_migracion_no_abre_nada_a_anon_y_solo_service_role_escribe():
    sql = _normal(_sql("supabase/migrations"))
    assert not re.search(r"grant [^;]*\bto (anon|authenticated|public)\b", sql)
    assert "revoke all on public.comercios_importados from public, anon, authenticated;" in sql
    assert "grant all on public.comercios_importados to service_role;" in sql
    assert "enable row level security" in sql
    assert "grant select (" not in sql                               # ninguna columna nueva pública


def test_migracion_amplia_el_check_de_cost_switches_con_las_tres_claves():
    sql = _normal(_sql("supabase/migrations"))
    assert ("add constraint cost_switches_key_check check (key in ('gemini_content', 'gemini_phone_scan', 'gemini_tarjetas'))"
            in sql)
    assert sql.index("drop constraint if exists cost_switches_key_check") < sql.index("add constraint cost_switches_key_check")


def test_patch_trata_el_texto_vacio_o_en_blanco_como_null_en_todos_los_campos(client, repo, datos):
    """El front manda "" cuando la persona borra un campo (`{"website": ""}`)."""
    iid = _tarjeta(repo, email="a@b.co", website="https://x.com", telefono="123", rubro_slug="gastronomia")
    vacios = {c: v for c, v in zip(("nombre", "direccion", "telefono", "whatsapp", "website", "email", "rubro_slug"),
                                   ("", "   ", "\t", "", "  ", "", "\n"))}
    r = client.patch(f"/admin/importados/{iid}", headers=datos, json=vacios)
    assert r.status_code == 200, r.text
    c = r.json()
    for campo in vacios:
        assert c[campo] is None, campo
    # de a un campo, como lo manda el front
    otra = _tarjeta(repo, website="https://x.com")
    assert client.patch(f"/admin/importados/{otra}", headers=datos, json={"website": ""}).json()["website"] is None


def test_patch_con_punto_devuelve_el_item_actualizado_con_ubicacion_confirmada(client, repo, datos):
    iid = _tarjeta(repo, ubicacion="aproximada", lat=-22.7, lng=-64.3)
    c = client.patch(f"/admin/importados/{iid}", headers=datos, json={"lat": -22.72, "lng": -64.32}).json()
    assert c["id"] == iid and c["ubicacion"] == "confirmada" and c["lat"] == -22.72 and c["lng"] == -64.32
    assert c["tiene_foto"] is False and "foto_ref" not in c
