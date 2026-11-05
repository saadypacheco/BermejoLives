"""El servicio que lee las portadas (services/telefonos_foto.py) y lo que cuelga de él: el interruptor de costo, el
campo `telefonos` del relevamiento por fotos, el lector de Gemini y el worker. El OCR se prueba con un lector
FALSO; los tests con el Tesseract real se saltean si el programa no está instalado."""
import asyncio
import base64
import json
import shutil
from io import BytesIO

import httpx
import pytest
from PIL import Image, ImageDraw, ImageFont

from app.core.config import settings
from app.services import cost_switches, telefonos_foto as svc, vision
from app.services.vision import LectorFallo, LectorTransitorio, VisionNoConfigurada
from tests.content_helpers import gemini_on, h

FOTO = b"foto-de-prueba"


@pytest.fixture(autouse=True)
def _foto_y_aviso(monkeypatch):
    """`_descargar` devuelve bytes sin tocar disco ni red; el aviso de «sin tesseract» vuelve a cero."""
    monkeypatch.setattr(svc, "_descargar", lambda url: FOTO)
    svc.reiniciar_aviso()
    yield
    svc.reiniciar_aviso()


def comercio(repo, cid, portada="auto", **kw):
    base = {"id": cid, "slug": f"local-{cid}", "nombre": f"Local {cid}", "activo": True, "ciudad_id": "ciu-1",
            "whatsapp": None, "telefono": None, "portada_url": f"http://x/fotos/{cid}.jpg" if portada == "auto" else portada}
    base.update(kw)
    return repo.seed_comercio(**base)


def lector(texto_por_url=None, por_defecto=""):
    """Un OCR falso: el texto depende de la foto (acá todas son los mismos bytes, así que se lleva una cola)."""
    cola = list(texto_por_url or [])
    llamadas = []

    def ocr(data):
        llamadas.append(data)
        return cola.pop(0) if cola else por_defecto
    ocr.llamadas = llamadas
    return ocr


# ═════════════════════════════════════════════════════════════ la tanda

def test_una_tanda_lee_las_portadas_y_guarda_propuestas(repo, trepo, crepo):
    comercio(repo, "c1")
    ocr = lector(["Cel: 70123456\nTel (4) 6612345"])
    out = svc.tanda(trepo, crepo, ocr=ocr)
    assert out == {"motor": "tesseract", "tomadas": 1, "leidas": 1, "numeros": 2, "errores": 0,
                   "cortada": False, "sin_lector": False}
    filas = sorted(trepo.detectados.values(), key=lambda d: d["numero"])
    assert [(f["numero"], f["tipo"], f["estado"], f["motor"], f["foto_url"]) for f in filas] == [
        ("+59146612345", "fijo", "pendiente", "tesseract", "http://x/fotos/c1.jpg"),
        ("+59170123456", "celular", "pendiente", "tesseract", "http://x/fotos/c1.jpg")]
    assert trepo.escaneadas[("http://x/fotos/c1.jpg", "tesseract")]["numeros"] == 2


def test_nada_se_escribe_en_la_ficha_del_comercio(repo, trepo, crepo):
    comercio(repo, "c1", whatsapp=None, telefono=None)
    svc.tanda(trepo, crepo, ocr=lector(["Cel: 70123456"]))
    assert repo.comercios["c1"]["whatsapp"] is None and repo.comercios["c1"]["telefono"] is None


def test_una_portada_ya_leida_no_se_vuelve_a_tomar(repo, trepo, crepo):
    comercio(repo, "c1")
    ocr = lector(["70123456"])
    svc.tanda(trepo, crepo, ocr=ocr)
    out = svc.tanda(trepo, crepo, ocr=ocr)
    assert out["tomadas"] == 0 and len(ocr.llamadas) == 1


def test_una_portada_que_cambia_de_url_se_vuelve_a_leer_sola(repo, trepo, crepo):
    comercio(repo, "c1")
    svc.tanda(trepo, crepo, ocr=lector(["70123456"]))
    repo.comercios["c1"]["portada_url"] = "http://x/fotos/c1-nueva.jpg"
    out = svc.tanda(trepo, crepo, ocr=lector(["71234567"]))
    assert out["tomadas"] == 1
    assert {d["numero"] for d in trepo.detectados.values()} == {"+59170123456", "+59171234567"}


def test_primero_los_comercios_sin_whatsapp_y_de_a_20(repo, trepo, crepo):
    for i in range(25):
        comercio(repo, f"con{i}", whatsapp="59170000001")
    comercio(repo, "sin1")
    comercio(repo, "sin2")
    visto = []
    out = svc.tanda(trepo, crepo, limite=20, ocr=lambda d: visto.append(1) or "")
    assert out["tomadas"] == 20
    assert ("http://x/fotos/sin1.jpg", "tesseract") in trepo.escaneadas
    assert ("http://x/fotos/sin2.jpg", "tesseract") in trepo.escaneadas


def test_sin_portada_o_dado_de_baja_no_se_lee(repo, trepo, crepo):
    comercio(repo, "sin-foto", portada=None)
    comercio(repo, "baja", activo=False)
    assert svc.tanda(trepo, crepo, ocr=lector())["tomadas"] == 0


def test_lo_que_ya_es_el_whatsapp_o_el_telefono_entra_como_coincide(repo, trepo, crepo):
    comercio(repo, "c1", whatsapp="59170123456", telefono="+591 4 6612345")
    svc.tanda(trepo, crepo, ocr=lector(["70123456 71234567 4 6612345"]))
    estados = {d["numero"]: d["estado"] for d in trepo.detectados.values()}
    assert estados == {"+59170123456": "coincide", "+59171234567": "pendiente", "+59146612345": "coincide"}


def test_un_numero_en_cuatro_comercios_se_marca_compartido(repo, trepo, crepo):
    for i in range(4):
        comercio(repo, f"c{i}")
    ocr = lector(["Admin 70123456"] * 4)
    svc.tanda(trepo, crepo, ocr=ocr)
    assert len(trepo.detectados) == 4
    assert all(d["compartido"] for d in trepo.detectados.values())


def test_en_tres_comercios_todavia_no_es_compartido(repo, trepo, crepo):
    for i in range(3):
        comercio(repo, f"c{i}")
    svc.tanda(trepo, crepo, ocr=lector(["70123456"] * 3))
    assert not any(d["compartido"] for d in trepo.detectados.values())


def test_un_numero_descartado_no_resucita(repo, trepo, crepo):
    comercio(repo, "c1")
    svc.tanda(trepo, crepo, ocr=lector(["70123456"]))
    fila = next(iter(trepo.detectados.values()))
    fila["estado"] = "descartado"
    repo.comercios["c1"]["portada_url"] = "http://x/otra.jpg"          # otra foto con el mismo número
    svc.tanda(trepo, crepo, ocr=lector(["70123456"]))
    assert len(trepo.detectados) == 1 and next(iter(trepo.detectados.values()))["estado"] == "descartado"


def test_los_numeros_de_uruku_no_se_proponen(repo, trepo, crepo):
    comercio(repo, "c1")
    svc.tanda(trepo, crepo, ocr=lector(["67671888 70123456 67677803"]))
    assert [d["numero"] for d in trepo.detectados.values()] == ["+59170123456"]


# ─── los errores

def test_una_foto_que_no_se_puede_bajar_queda_con_su_error_y_la_tanda_sigue(repo, trepo, crepo, monkeypatch):
    comercio(repo, "c1")
    comercio(repo, "c2")
    monkeypatch.setattr(svc, "_descargar", lambda url: None if url.endswith("c1.jpg") else FOTO)
    out = svc.tanda(trepo, crepo, ocr=lector(["70123456"]))
    assert out["errores"] == 1 and out["leidas"] == 1
    assert trepo.escaneadas[("http://x/fotos/c1.jpg", "tesseract")]["error"] == "No se pudo bajar la foto"


def test_una_foto_ilegible_se_marca_con_error_y_no_frena_a_las_demas(repo, trepo, crepo):
    comercio(repo, "c1")
    comercio(repo, "c2")

    def ocr(data):
        if not ocr.llamado:
            ocr.llamado = True
            raise LectorFallo("La foto no se pudo abrir como imagen")
        return "70123456"
    ocr.llamado = False
    out = svc.tanda(trepo, crepo, ocr=ocr)
    assert out["errores"] == 1 and out["leidas"] == 1 and out["numeros"] == 1
    errores = [v for v in trepo.escaneadas.values() if v["error"]]
    assert len(errores) == 1 and "imagen" in errores[0]["error"]


def test_si_cae_el_servicio_la_tanda_se_corta_y_la_foto_no_se_marca(repo, trepo, crepo):
    comercio(repo, "c1")
    comercio(repo, "c2")

    def ocr(data):
        raise LectorTransitorio("cuota agotada")
    out = svc.tanda(trepo, crepo, ocr=ocr)
    assert out["cortada"] is True and out["leidas"] == 0
    assert trepo.escaneadas == {}                      # la próxima vuelta reintenta las mismas


def test_un_error_inesperado_en_una_portada_se_registra_y_sigue(repo, trepo, crepo):
    comercio(repo, "c1")
    comercio(repo, "c2")

    def ocr(data):
        if not ocr.llamado:
            ocr.llamado = True
            raise ValueError("algo raro")
        return "70123456"
    ocr.llamado = False
    out = svc.tanda(trepo, crepo, ocr=ocr)
    assert out["errores"] == 1 and out["leidas"] == 1
    assert any("ValueError" in (v["error"] or "") for v in trepo.escaneadas.values())


def test_si_ni_el_registro_del_error_anda_la_tanda_se_corta_sin_romper(repo, trepo, crepo):
    comercio(repo, "c1")
    trepo.falla_registro = True
    out = svc.tanda(trepo, crepo, ocr=lambda d: (_ for _ in ()).throw(ValueError("x")))
    assert out["cortada"] is True


def test_sin_tesseract_avisa_una_sola_vez_y_no_toma_trabajos(repo, trepo, crepo, monkeypatch):
    comercio(repo, "c1")
    monkeypatch.setattr(svc.shutil, "which", lambda nombre: None)
    avisos = []
    monkeypatch.setattr(svc.logger, "warning", lambda evento, **k: avisos.append(evento))
    for _ in range(3):
        out = svc.tanda(trepo, crepo)               # el lector real: sin programa instalado
        assert out["sin_lector"] is True and out["tomadas"] == 0
    assert avisos == ["telefonos_foto.sin_tesseract"]
    assert trepo.escaneadas == {}


# ═════════════════════════════════════════════════════════════ el motor y el interruptor de costo

def test_por_defecto_el_motor_es_el_lector_gratis(crepo, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    assert svc.motor_activo(crepo) == "tesseract"            # sin fila = apagado, aunque haya clave


def test_prendido_y_con_clave_el_motor_es_gemini(crepo, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    cost_switches.set(crepo, cost_switches.GEMINI_PHONE_SCAN, True, "dueno@uruku.bo")
    assert svc.motor_activo(crepo) == "gemini"


def test_prendido_pero_sin_clave_sigue_el_lector_gratis(crepo, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    cost_switches.set(crepo, cost_switches.GEMINI_PHONE_SCAN, True, "dueno@uruku.bo")
    assert svc.motor_activo(crepo) == "tesseract"


def test_el_interruptor_de_contenido_no_prende_el_de_telefonos(crepo, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    gemini_on(crepo)                                        # gemini_content
    assert svc.motor_activo(crepo) == "tesseract"


def test_el_catalogo_describe_el_interruptor_nuevo():
    c = cost_switches.CATALOGO["gemini_phone_scan"]
    assert c["label"] == "Leer teléfonos en las fotos con Gemini"
    assert c["cost"] == "Estimado: menos de US$ 5 para todas las portadas (unas 6000); 0 si la clave es del nivel gratis"
    assert c["off_means"] == "Se usa el lector gratis (Tesseract), que se pierde algunos números en carteles chicos o torcidos"


def test_la_api_de_interruptores_lista_y_prende_el_nuevo(client):
    from app.core import auth
    dueno = h(auth.make_token("dueno@uruku.bo", rol="x", roles=["x"], permisos=["equipo"]))
    claves = [i["key"] for i in client.get("/admin/cost-switches", headers=dueno).json()["items"]]
    assert claves == ["gemini_content", "gemini_phone_scan"]
    r = client.put("/admin/cost-switches/gemini_phone_scan", json={"enabled": True}, headers=dueno)
    assert r.status_code == 400 and "costo" in r.json()["detail"]
    r = client.put("/admin/cost-switches/gemini_phone_scan", json={"enabled": True, "confirm_cost": True}, headers=dueno)
    assert r.status_code == 200 and r.json()["enabled"] is True


def test_con_gemini_prendido_la_tanda_usa_gemini_y_no_el_ocr(repo, trepo, crepo, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    cost_switches.set(crepo, cost_switches.GEMINI_PHONE_SCAN, True, "dueno@uruku.bo")
    comercio(repo, "c1")
    ocr = lector(["99999999"])
    out = svc.tanda(trepo, crepo, ocr=ocr, gemini=lambda data: ["70123456", "+591 71234567"])
    assert out["motor"] == "gemini" and out["numeros"] == 2 and ocr.llamadas == []
    assert {d["motor"] for d in trepo.detectados.values()} == {"gemini"}
    assert ("http://x/fotos/c1.jpg", "gemini") in trepo.escaneadas


def test_cambiar_de_motor_vuelve_a_leer_lo_que_leyo_el_otro(repo, trepo, crepo, monkeypatch):
    comercio(repo, "c1")
    svc.tanda(trepo, crepo, ocr=lector(["70123456"]))
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    cost_switches.set(crepo, cost_switches.GEMINI_PHONE_SCAN, True, "dueno@uruku.bo")
    assert svc.tanda(trepo, crepo, gemini=lambda d: [])["tomadas"] == 1


def test_gemini_caido_corta_la_tanda_sin_marcar(repo, trepo, crepo, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    cost_switches.set(crepo, cost_switches.GEMINI_PHONE_SCAN, True, "dueno@uruku.bo")
    comercio(repo, "c1")

    def gemini(data):
        raise LectorTransitorio("429")
    out = svc.tanda(trepo, crepo, gemini=gemini)
    assert out["cortada"] is True and trepo.escaneadas == {}


# ═════════════════════════════════════════════════════════════ el relevamiento por fotos trae `telefonos` gratis

URLS = ["http://x/fotos/c1.jpg", "http://x/fotos/c1-galeria.jpg"]


def test_el_relevamiento_guarda_los_telefonos_con_su_motor(repo, trepo):
    c = comercio(repo, "c1")
    n = svc.guardar_del_relevamiento(trepo, c, URLS, {"telefonos": ["70123456", "(4) 6612345", "Bs 150"],
                                                      "fotos_analizadas": 2, "confianza": 0.8})
    assert n == 2
    assert {(d["numero"], d["motor"], d["foto_url"]) for d in trepo.detectados.values()} == {
        ("+59170123456", "gemini-relevamiento", URLS[0]), ("+59146612345", "gemini-relevamiento", URLS[0])}
    assert trepo.escaneadas[(URLS[0], "gemini-relevamiento")]["numeros"] == 2


def test_una_portada_que_leyo_el_relevamiento_no_se_vuelve_a_leer(repo, trepo, crepo):
    c = comercio(repo, "c1")
    svc.guardar_del_relevamiento(trepo, c, ["http://x/fotos/c1.jpg"], {"telefonos": [], "fotos_analizadas": 1})
    assert svc.tanda(trepo, crepo, ocr=lector())["tomadas"] == 0


def test_el_relevamiento_sin_campo_telefonos_o_con_error_no_hace_nada(repo, trepo):
    c = comercio(repo, "c1")
    assert svc.guardar_del_relevamiento(trepo, c, URLS, {"fotos_analizadas": 2}) == 0
    assert svc.guardar_del_relevamiento(trepo, c, URLS, {"telefonos": ["70123456"], "error": "falló"}) == 0
    assert svc.guardar_del_relevamiento(trepo, c, URLS, {"telefonos": ["70123456"], "fotos_analizadas": 0}) == 0
    assert svc.guardar_del_relevamiento(trepo, c, [], {"telefonos": ["70123456"], "fotos_analizadas": 1}) == 0
    assert trepo.detectados == {} and trepo.escaneadas == {}


def test_el_relevamiento_nunca_rompe_aunque_la_base_falle(repo, trepo):
    c = comercio(repo, "c1")
    trepo.falla_registro = True
    assert svc.guardar_del_relevamiento(trepo, c, URLS, {"telefonos": ["70123456"], "fotos_analizadas": 1}) == 0


def test_analizar_un_comercio_deja_los_telefonos_como_propuestas(client, repo, trepo, admin_token):
    from unittest.mock import patch
    comercio(repo, "c1")
    propuesta = {"productos": "zapatillas", "descripcion": "", "subcategoria": "", "sinonimos": "", "rubro_slugs": [],
                 "confianza": 0.9, "fotos_analizadas": 1, "telefonos": ["Cel: 70123456", "NIT 71234567"]}
    with patch("app.api.moderacion.analizar_fotos", lambda u, r, c=None: dict(propuesta)):
        r = client.post("/admin/comercio/c1/analizar", headers=h(admin_token))
    assert r.status_code == 200
    assert [d["numero"] for d in trepo.detectados.values()] == ["+59170123456"]      # el NIT no es teléfono
    assert repo.comercios["c1"].get("whatsapp") is None                              # y no se aplicó nada


def test_analizar_en_tanda_tambien_los_guarda(client, repo, trepo, admin_token):
    from unittest.mock import patch
    comercio(repo, "c1", ia_analizado_at=None)
    propuesta = {"productos": "zapatillas", "descripcion": "", "subcategoria": "", "sinonimos": "", "rubro_slugs": [],
                 "confianza": 0.0, "fotos_analizadas": 1, "telefonos": ["70123456"]}
    with patch("app.api.moderacion.analizar_fotos", lambda u, r, c=None: dict(propuesta)):
        client.post("/admin/comercios/analizar-tanda?limite=1&aplicar=false", headers=h(admin_token))
    assert [d["numero"] for d in trepo.detectados.values()] == ["+59170123456"]


# ═════════════════════════════════════════════════════════════ el campo `telefonos` del relevamiento (vision.py)

def test_el_prompt_del_relevamiento_pide_telefonos():
    p = vision._prompt([{"slug": "calzado", "nombre": "Calzado"}])
    assert '"telefonos"' in p and "NIT" in p


def _respuesta(payload: dict, status=200):
    class R:
        status_code = status
        text = json.dumps(payload)

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": json.dumps(payload)}]}}],
                    "usageMetadata": {"totalTokenCount": 10}}

        def raise_for_status(self):
            if status >= 400:
                raise httpx.HTTPStatusError("x", request=None, response=self)
    return R()


def test_analizar_fotos_devuelve_los_telefonos_tal_cual(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(vision, "_descargar", lambda url: FOTO)
    monkeypatch.setattr(vision, "_post_con_reintentos",
                        lambda url, payload: _respuesta({"productos": "x", "rubro_slugs": [], "confianza": 0.5,
                                                         "telefonos": ["+591 7012 3456", 70123456, "", None, True]}))
    out = vision.analizar_fotos(["http://x/f.jpg"], [])
    assert out["telefonos"] == ["+591 7012 3456", "70123456"]


@pytest.mark.parametrize("crudo, esperado", [
    (None, []), ("70123456", ["70123456"]), ({"a": 1}, []), ([], []), (["a", "a", "b"], ["a", "b"]),
    (["x" * 100], ["x" * 40]), ([str(i) for i in range(50)], [str(i) for i in range(20)]), (True, []),
])
def test_lista_de_telefonos_se_acomoda_lo_que_venga(crudo, esperado):
    assert vision._lista_de_telefonos(crudo) == esperado


def test_los_resultados_vacios_del_relevamiento_traen_telefonos_vacios(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(vision, "_descargar", lambda url: None)
    assert vision.analizar_fotos(["http://x/f.jpg"], [])["telefonos"] == []


# ═════════════════════════════════════════════════════════════ Gemini, una foto, sólo los números

def foto_grande(w=3000, h_=2000):
    buf = BytesIO()
    Image.new("RGB", (w, h_), "white").save(buf, format="JPEG")
    return buf.getvalue()


def test_leer_telefonos_foto_manda_una_foto_chica_y_un_prompt_que_solo_pide_numeros(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    visto = {}

    def post(url, payload):
        visto["payload"] = payload
        return _respuesta({"telefonos": ["70123456", "(4) 6612345"]})
    monkeypatch.setattr(vision, "_post_con_reintentos", post)
    assert vision.leer_telefonos_foto(foto_grande()) == ["70123456", "(4) 6612345"]
    partes = visto["payload"]["contents"][0]["parts"]
    assert partes[0]["text"] == vision.PROMPT_TELEFONOS and '"telefonos"' in partes[0]["text"]
    imagen = Image.open(BytesIO(base64.b64decode(partes[1]["inline_data"]["data"])))
    assert max(imagen.size) == 1024                                  # la foto va a 1024 px


def test_leer_telefonos_foto_sin_clave(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    with pytest.raises(VisionNoConfigurada):
        vision.leer_telefonos_foto(foto_grande())


@pytest.mark.parametrize("status", [429, 500, 503, 401, 403, 404])
def test_gemini_que_no_puede_contestar_es_transitorio(monkeypatch, status):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(vision, "_post_con_reintentos", lambda u, p: _respuesta({}, status))
    with pytest.raises(LectorTransitorio):
        vision.leer_telefonos_foto(foto_grande())


def test_un_timeout_es_transitorio_y_el_mensaje_no_lleva_la_clave(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "clave-secreta")

    def post(url, payload):
        raise httpx.TimeoutException(f"timeout en {url}")
    monkeypatch.setattr(vision, "_post_con_reintentos", post)
    with pytest.raises(LectorTransitorio) as exc:
        vision.leer_telefonos_foto(foto_grande())
    assert "clave-secreta" not in str(exc.value)


def test_un_400_o_una_respuesta_ilegible_es_un_fallo_de_esa_foto(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(vision, "_post_con_reintentos", lambda u, p: _respuesta({}, 400))
    with pytest.raises(LectorFallo):
        vision.leer_telefonos_foto(foto_grande())

    class Basura:
        status_code = 200

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "no soy json"}]}}]}
    monkeypatch.setattr(vision, "_post_con_reintentos", lambda u, p: Basura())
    with pytest.raises(LectorFallo):
        vision.leer_telefonos_foto(foto_grande())


def test_una_foto_que_no_es_imagen_es_un_fallo(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    with pytest.raises(LectorFallo):
        vision.leer_telefonos_foto(b"esto no es una imagen")


# ═════════════════════════════════════════════════════════════ el preproceso y el OCR

def test_preparar_imagenes_da_gris_a_1600_y_el_negativo():
    buf = BytesIO()
    Image.new("RGB", (800, 400), (200, 30, 30)).save(buf, format="PNG")
    normal, negativo = svc.preparar_imagenes(buf.getvalue())
    assert normal.mode == "L" and max(normal.size) == 1600 and normal.size == (1600, 800)
    assert negativo.size == normal.size and negativo.getpixel((5, 5)) == 255 - normal.getpixel((5, 5))


def test_preparar_imagenes_achica_las_fotos_grandes_y_respeta_el_exif():
    im = Image.new("RGB", (4000, 1000), "white")
    e = Image.Exif()
    e[274] = 6                                       # rotada 90°: el ancho y el alto se intercambian
    buf = BytesIO()
    im.save(buf, format="JPEG", exif=e)
    normal, _neg = svc.preparar_imagenes(buf.getvalue())
    assert normal.size == (400, 1600)


def test_preparar_imagenes_con_basura_es_un_fallo():
    with pytest.raises(LectorFallo):
        svc.preparar_imagenes(b"no es una imagen")


class FalsoPytesseract:
    """Lo que `leer_con_tesseract` necesita del paquete, sin el programa."""
    class TesseractNotFoundError(Exception):
        pass

    def __init__(self, textos=("70123456", ""), error=None):
        self.llamadas = []
        self.textos = list(textos)
        self.error = error

    def image_to_string(self, im, config="", timeout=0):
        self.llamadas.append({"modo": im.mode, "config": config, "timeout": timeout})
        if self.error:
            raise self.error
        return self.textos.pop(0)


def test_tesseract_se_llama_con_psm_11_lista_blanca_y_dos_pasadas(monkeypatch):
    falso = FalsoPytesseract(textos=("Cel 70123456", "71234567"))
    monkeypatch.setitem(__import__("sys").modules, "pytesseract", falso)
    texto = svc.leer_con_tesseract(foto_grande(800, 600))
    assert texto == "Cel 70123456\n71234567"
    assert len(falso.llamadas) == 2 and all(c["modo"] == "L" for c in falso.llamadas)
    assert all("--psm 11" in c["config"] and "tessedit_char_whitelist=0123456789+-.()" in c["config"]
               for c in falso.llamadas)
    assert all(c["timeout"] == 30 for c in falso.llamadas)


def test_tesseract_sin_programa_es_transitorio_y_con_timeout_es_un_fallo_de_la_foto(monkeypatch):
    sys_modules = __import__("sys").modules
    falso = FalsoPytesseract()
    falso.error = falso.TesseractNotFoundError("no está")
    monkeypatch.setitem(sys_modules, "pytesseract", falso)
    with pytest.raises(LectorTransitorio):
        svc.leer_con_tesseract(foto_grande(400, 300))
    falso = FalsoPytesseract(error=RuntimeError("Tesseract process timeout"))
    monkeypatch.setitem(sys_modules, "pytesseract", falso)
    with pytest.raises(LectorFallo):
        svc.leer_con_tesseract(foto_grande(400, 300))


def test_el_texto_del_ocr_pasa_por_la_normalizacion(repo, trepo, crepo, monkeypatch):
    """De punta a punta con un pytesseract falso: el texto sucio del OCR termina en propuestas limpias."""
    monkeypatch.setitem(__import__("sys").modules, "pytesseract",
                        FalsoPytesseract(textos=("20 11 2026\n7012 3456\n8.00 12.00\n+591-4-6612345\n", "")))
    monkeypatch.setattr(svc, "tesseract_disponible", lambda: True)
    monkeypatch.setattr(svc, "_descargar", lambda url: foto_grande(400, 300))
    comercio(repo, "c1")
    svc.tanda(trepo, crepo)
    assert sorted(d["numero"] for d in trepo.detectados.values()) == ["+59146612345", "+59170123456"]


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract no está instalado en esta PC")
def test_tesseract_real_lee_un_cartel_con_un_celular():
    """Sólo con el programa instalado (en el contenedor del backend lo está)."""
    im = Image.new("L", (1200, 400), 255)
    fuente = ImageFont.load_default(size=140)
    ImageDraw.Draw(im).text((40, 100), "70123456", fill=0, font=fuente)
    buf = BytesIO()
    im.save(buf, format="PNG")
    assert [t.numero for t in svc.extraer(svc.leer_con_tesseract(buf.getvalue()))] == ["+59170123456"]


@pytest.mark.skipif(shutil.which("tesseract") is None, reason="tesseract no está instalado en esta PC")
def test_tesseract_real_lee_un_cartel_claro_sobre_fondo_oscuro():
    im = Image.new("L", (1200, 400), 20)
    fuente = ImageFont.load_default(size=140)
    ImageDraw.Draw(im).text((40, 100), "71234567", fill=240, font=fuente)
    buf = BytesIO()
    im.save(buf, format="PNG")
    assert "+59171234567" in [t.numero for t in svc.extraer(svc.leer_con_tesseract(buf.getvalue()))]


# ═════════════════════════════════════════════════════════════ el worker

def test_el_worker_arranca_apagado():
    assert settings.telefonos_foto_worker is False
    assert settings.telefonos_foto_por_tanda == 20 and settings.telefonos_foto_cada_seg == 30


async def test_el_loop_toma_20_portadas_y_duerme_30_s_entre_tandas(monkeypatch):
    from app import main
    pedidos, pausas = [], []

    def tanda(trepo, crepo, limite):
        pedidos.append(limite)
        return {"motor": "tesseract", "tomadas": 20, "leidas": 20, "numeros": 3, "errores": 0,
                "cortada": False, "sin_lector": False}

    async def dormir(seg):
        pausas.append(seg)
        if len(pausas) >= 3:
            raise asyncio.CancelledError

    monkeypatch.setattr(svc, "tanda", tanda)
    monkeypatch.setattr(main.asyncio, "sleep", dormir)
    with pytest.raises(asyncio.CancelledError):
        await main._telefonos_foto_loop()
    assert pedidos == [20, 20] and pausas[1:] == [30, 30]


async def test_el_loop_duerme_mas_cuando_no_hay_nada_o_falta_el_lector_y_nunca_se_corta(monkeypatch):
    from app import main
    respuestas = iter([{"tomadas": 0, "sin_lector": False, "cortada": False},
                       {"tomadas": 0, "sin_lector": True, "cortada": False},
                       RuntimeError("base caída")])
    pausas = []

    def tanda(trepo, crepo, limite):
        r = next(respuestas)
        if isinstance(r, Exception):
            raise r
        return r

    async def dormir(seg):
        pausas.append(seg)
        if len(pausas) >= 4:
            raise asyncio.CancelledError

    monkeypatch.setattr(svc, "tanda", tanda)
    monkeypatch.setattr(main.asyncio, "sleep", dormir)
    with pytest.raises(asyncio.CancelledError):
        await main._telefonos_foto_loop()
    assert pausas[1:] == [settings.telefonos_foto_ocioso_seg] * 3
