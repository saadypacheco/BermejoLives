"""Los endpoints de las fotos con estilo URUKU (docs/fotos-estilo-uruku.md §5 y §6): cada ruta y cada código de error.

Gemini va contra un `httpx.MockTransport`: sin red y sin gastar. Todo lo que se arma queda como PROPUESTA privada.
"""
import base64
import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.core.config import settings
from app.services import cost_switches, fotos_estilo as fe, fotos_estilo_gemini as ge, portada_diseno as pd
from app.services.imagenes import guardar_foto_local

BASE = "https://api.test/fotos"
CLAVE = "AIzaSy-CLAVE-SECRETA-0123456789"
MODELO = "modelo-de-imagen-de-prueba"
COSTO = 0.0336
ADMIN = "admin@bermejolive.com"
NOMBRE = "Ferretería Zeta Reservadísima"


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _jpeg(w=800, h=600, color="green") -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="JPEG")
    return buf.getvalue()


def _png(w=800, h=600, color="blue") -> bytes:
    buf = BytesIO()
    Image.new("RGB", (w, h), color).save(buf, format="PNG")
    return buf.getvalue()


def _en_disco(url) -> bool:
    return (Path(settings.fotos_dir) / url[len(BASE) + 1:]).exists()


def _tamano(url):
    return Image.open(Path(settings.fotos_dir) / url[len(BASE) + 1:]).size


@pytest.fixture(autouse=True)
def _base(monkeypatch):
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", "")


@pytest.fixture
def mundo(repo):
    """Un comercio con portada y dos fotos de galería, todo en el disco."""
    repo.rubros["ferreteria"] = "rub-ferre"
    guardar_foto_local("local-d/orig.jpg", _jpeg(1200, 800))
    guardar_foto_local("local-d/g1.jpg", _jpeg(900, 1100, "red"))
    guardar_foto_local("local-d/g2.jpg", _jpeg(1000, 1000, "yellow"))
    c = repo.seed_comercio(id="com-d", slug="local-d", nombre=NOMBRE, whatsapp="59170000001", ciudad_id="ciu-1",
                           rubro_id="rub-ferre", portada_url=f"{BASE}/local-d/orig.jpg", portada_pos=None)
    for i, n in enumerate(("g1", "g2")):
        repo.comercio_fotos.append({"id": f"f{i + 1}", "comercio_id": "com-d", "url": f"{BASE}/local-d/{n}.jpg",
                                    "thumb_url": f"{BASE}/local-d/{n}_t.jpg", "orden": i,
                                    "created_at": f"2026-01-0{i + 1}T00:00:00+00:00"})
    return c


class Gemini:
    """Un Gemini falso: anota los pedidos y contesta con la imagen o el error que se le pida."""

    def __init__(self, respuesta=None):
        self.pedidos: list[httpx.Request] = []
        self.respuesta = respuesta or self.imagen()

    @staticmethod
    def imagen(datos: bytes | None = None, *, clave="inlineData"):
        datos = datos or _jpeg(1536, 1024, "orange")
        cuerpo = {"candidates": [{"content": {"parts": [{"text": "ok"},
                                                        {clave: {"mimeType": "image/jpeg",
                                                                 "data": base64.b64encode(datos).decode()}}]}}]}
        return lambda req: httpx.Response(200, json=cuerpo)

    def __call__(self, request):
        self.pedidos.append(request)
        return self.respuesta(request)

    @property
    def cuerpo(self) -> dict:
        return json.loads(self.pedidos[-1].content)


@pytest.fixture
def conf(monkeypatch, crepo):
    """Gemini configurado: clave, modelo, costo e interruptor prendido."""
    monkeypatch.setattr(settings, "gemini_api_key", CLAVE)
    monkeypatch.setattr(settings, "gemini_image_model", MODELO)
    monkeypatch.setattr(settings, "gemini_image_cost_usd", COSTO)
    monkeypatch.setattr(settings, "gemini_fotos_tope_diario", 20)
    monkeypatch.setattr(settings, "gemini_image_timeout_seg", 60)
    cost_switches.set(crepo, cost_switches.GEMINI_FOTOS, True, "test@uruku.bo")


@pytest.fixture
def gemini(conf, monkeypatch):
    g = Gemini()
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(g))
    return g


def _con_respuesta(monkeypatch, respuesta) -> Gemini:
    g = Gemini(respuesta)
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(g))
    return g


COVER = "/admin/comercio/com-d/portada-diseno"
GAL = "/admin/comercio/com-d/fotos/f1/diseno"
ESTADO = "/admin/comercio/com-d/fotos-estilo"


# ══════════════════════════════════════════ GET fotos-estilo

def test_get_estado_con_la_ia_apagada_dice_el_motivo(client, repo, mundo, admin_token):
    r = client.get(ESTADO, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    e = r.json()
    assert e["comercio"] == {"id": "com-d", "nombre": NOMBRE, "slug": "local-d"}
    assert e["cover"] == {"photo_url": f"{BASE}/local-d/orig.jpg", "design_url": None, "proposal_url": None,
                          "proposal_method": None}
    assert [g["foto_id"] for g in e["gallery"]] == ["f1", "f2"]
    assert e["gallery"][0] == {"foto_id": "f1", "photo_url": f"{BASE}/local-d/g1.jpg",
                               "thumb_url": f"{BASE}/local-d/g1_t.jpg", "design_url": None, "design_thumb_url": None,
                               "proposal_url": None, "proposal_method": None}
    g = e["gemini"]
    assert g["available"] is False and "apagado" in g["reason"]
    assert set(g) == {"available", "reason", "cost_usd", "used_today", "daily_cap", "merchant_uses", "merchant_cost_usd"}
    assert g["used_today"] == 0 and g["daily_cap"] == 20 and g["merchant_uses"] == 0
    assert e["instructions"]["version"] == "fotos-estilo-v1"
    assert "Do NOT write any text" in e["instructions"]["cover"] and "aspect 4:5" in e["instructions"]["gallery"]
    assert NOMBRE not in e["instructions"]["cover"]


def test_get_estado_con_todo_configurado_esta_disponible(client, repo, mundo, admin_token, conf):
    g = client.get(ESTADO, headers=_h(admin_token)).json()["gemini"]
    assert g["available"] is True and g["reason"] is None and g["cost_usd"] == COSTO


@pytest.mark.parametrize("quitar,motivo", [("api_key", "clave"), ("model", "modelo"), ("cost", "costo")])
def test_get_estado_dice_que_falta(client, repo, mundo, admin_token, conf, monkeypatch, quitar, motivo):
    monkeypatch.setattr(settings, {"api_key": "gemini_api_key", "model": "gemini_image_model",
                                   "cost": "gemini_image_cost_usd"}[quitar], 0.0 if quitar == "cost" else "")
    g = client.get(ESTADO, headers=_h(admin_token)).json()["gemini"]
    assert g["available"] is False and motivo in g["reason"]
    assert CLAVE not in json.dumps(g)


def test_get_estado_cuenta_lo_de_hoy_y_lo_de_este_comercio(client, repo, mundo, admin_token, gemini):
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200
    assert client.post(GAL, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200
    e = client.get(ESTADO, headers=_h(admin_token)).json()
    assert e["gemini"]["used_today"] == 2 and e["gemini"]["merchant_uses"] == 2
    assert e["gemini"]["merchant_cost_usd"] == pytest.approx(2 * COSTO, abs=1e-4)
    assert e["cover"]["proposal_method"] == "gemini" and e["gallery"][0]["proposal_method"] == "gemini"


def test_get_estado_404_y_permisos(client, repo, mundo, agente_token):
    from tests.conftest import comercio_token
    assert client.get("/admin/comercio/nada/fotos-estilo", headers=_h(_admin())).status_code == 404
    assert client.get(ESTADO).status_code in (401, 403)
    assert client.get(ESTADO, headers=_h(agente_token)).status_code in (401, 403)
    assert client.get(ESTADO, headers=_h(comercio_token(comercio_id="com-d"))).status_code in (401, 403)


def _admin():
    from app.core import auth
    return auth.make_token(ADMIN, rol="admin")


# ══════════════════════════════════════════ portada: free / gemini / externa

def test_portada_sin_body_es_free_y_queda_como_propuesta(client, repo, mundo, admin_token):
    r = client.post(COVER, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    c = r.json()
    assert set(c) == {"portada_diseno_url", "portada_diseno_propuesta_url", "proposal_method"}
    assert c["portada_diseno_url"] is None and c["proposal_method"] == "free"
    assert _tamano(c["portada_diseno_propuesta_url"]) == (1600, 1000)
    [uso] = repo.photo_style_uses
    assert (uso["method"], uso["target"], uso["result"], uso["cost_usd"], uso["foto_id"]) == ("free", "cover", "ok", 0, None)
    assert uso["actor"] == ADMIN and uso["result_url"] == c["portada_diseno_propuesta_url"]


def test_portada_con_method_free_explicito(client, repo, mundo, admin_token):
    assert client.post(COVER, headers=_h(admin_token), json={"method": "free"}).json()["proposal_method"] == "free"


def test_portada_method_invalido_es_422(client, repo, mundo, admin_token):
    assert client.post(COVER, headers=_h(admin_token), json={"method": "magia"}).status_code == 422
    assert client.post(COVER, headers=_h(admin_token), json={"method": "external"}).status_code == 422


def test_portada_gemini_feliz_registra_costo_y_modelo(client, repo, mundo, admin_token, gemini):
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["proposal_method"] == "gemini" and _tamano(c["portada_diseno_propuesta_url"]) == (1600, 1000)
    [uso] = repo.photo_style_uses
    assert uso["method"] == "gemini" and uso["result"] == "ok" and uso["cost_usd"] == COSTO
    assert uso["model"] == MODELO and uso["prompt_version"] == "fotos-estilo-v1" and uso["error"] is None
    assert uso["actor"] == ADMIN and uso["target"] == "cover" and uso["result_url"] == c["portada_diseno_propuesta_url"]
    assert repo.comercios["com-d"]["portada_diseno_propuesta_url"] == c["portada_diseno_propuesta_url"]
    assert not repo.comercios["com-d"].get("portada_diseno_url")        # nada se publica solo


def test_el_pedido_a_gemini_no_lleva_datos_del_comercio_y_la_clave_va_en_la_cabecera(client, repo, mundo, admin_token, gemini):
    repo.comercios["com-d"]["descripcion"] = "Vendemos tornillos secretos"
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200
    [pedido] = gemini.pedidos
    crudo = pedido.content.decode()
    for dato in (NOMBRE, "Zeta", "local-d", "com-d", "Ferreteria", "Bermejo", "59170000001", "tornillos"):
        assert dato not in crudo, dato
    assert CLAVE not in str(pedido.url) and "key=" not in str(pedido.url)
    assert pedido.headers["x-goog-api-key"] == CLAVE
    assert str(pedido.url) == f"https://generativelanguage.googleapis.com/v1beta/models/{MODELO}:generateContent"
    cuerpo = gemini.cuerpo
    assert cuerpo["generationConfig"] == {"responseModalities": ["IMAGE"], "imageConfig": {"aspectRatio": "3:2"}}
    partes = cuerpo["contents"][0]["parts"]
    assert partes[0]["text"].startswith("Edit the attached photo") and partes[0]["text"].endswith("aspect 3:2.")
    foto = Image.open(BytesIO(base64.b64decode(partes[1]["inline_data"]["data"])))
    assert partes[1]["inline_data"]["mime_type"] == "image/jpeg" and foto.format == "JPEG"
    assert max(foto.size) <= 1536 and abs(foto.size[0] / foto.size[1] - 1.5) < 0.01     # recortada a 3:2 y achicada


def test_galeria_gemini_pide_4_a_5(client, repo, mundo, admin_token, gemini):
    r = client.post(GAL, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 200, r.text
    assert gemini.cuerpo["generationConfig"]["imageConfig"] == {"aspectRatio": "4:5"}
    assert gemini.cuerpo["contents"][0]["parts"][0]["text"].endswith("aspect 4:5.")
    foto = Image.open(BytesIO(base64.b64decode(gemini.cuerpo["contents"][0]["parts"][1]["inline_data"]["data"])))
    assert abs(foto.size[0] / foto.size[1] - 0.8) < 0.01 and max(foto.size) <= 1536


def test_gemini_responde_con_inline_data_en_snake_case_tambien(client, repo, mundo, admin_token, conf, monkeypatch):
    _con_respuesta(monkeypatch, Gemini.imagen(clave="inline_data"))
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200


def test_portada_externa_feliz(client, repo, mundo, admin_token):
    r = client.post(f"{COVER}/externa", headers=_h(admin_token), files={"foto": ("a.png", _png(1500, 1000), "image/png")})
    assert r.status_code == 200, r.text
    c = r.json()
    assert c["proposal_method"] == "external" and _tamano(c["portada_diseno_propuesta_url"]) == (1600, 1000)
    [uso] = repo.photo_style_uses
    assert (uso["method"], uso["result"], uso["cost_usd"], uso["model"]) == ("external", "ok", 0, None)
    assert uso["prompt_version"] == "fotos-estilo-v1"


def test_portada_externa_errores(client, repo, mundo, admin_token):
    def subir(datos, nombre="a.png"):
        return client.post(f"{COVER}/externa", headers=_h(admin_token), files={"foto": (nombre, datos, "image/png")})
    assert subir(b"").status_code == 400
    r = subir(_png(400, 400))
    assert r.status_code == 400 and "muy chica" in r.json()["detail"]
    assert subir(_png(3000, 600)).status_code == 400                  # 5:1
    r = subir(b"no soy una imagen")
    assert r.status_code == 400 and "no es válida" in r.json()["detail"]
    buf = BytesIO()
    Image.new("RGB", (800, 600)).save(buf, format="GIF")
    assert subir(buf.getvalue()).status_code == 400                   # sólo JPEG, PNG o WEBP
    assert repo.photo_style_uses == []                                # lo que falla no se registra


def test_portada_externa_mas_de_15_mb_es_413(client, repo, mundo, admin_token):
    r = client.post(f"{COVER}/externa", headers=_h(admin_token),
                    files={"foto": ("a.jpg", b"x" * (15 * 1024 * 1024 + 1), "image/jpeg")})
    assert r.status_code == 413


def test_portada_sin_foto_es_400(client, repo, mundo, admin_token):
    repo.comercios["com-d"]["portada_url"] = None
    for ruta in (COVER, f"{COVER}/externa"):
        r = client.post(ruta, headers=_h(admin_token), files={"foto": ("a.png", _png(), "image/png")} if "externa" in ruta else None)
        assert r.status_code == 400 and r.json()["detail"] == "El comercio no tiene foto de portada"


def test_portada_inexistente_es_404_y_pide_permiso(client, repo, mundo, admin_token, agente_token):
    assert client.post("/admin/comercio/nada/portada-diseno", headers=_h(admin_token)).status_code == 404
    assert client.post("/admin/comercio/nada/portada-diseno/externa", headers=_h(admin_token),
                       files={"foto": ("a.png", _png(), "image/png")}).status_code == 404
    for ruta in (COVER, f"{COVER}/externa"):
        assert client.post(ruta).status_code in (401, 403)
        assert client.post(ruta, headers=_h(agente_token)).status_code in (401, 403)


# ══════════════════════════════════════════ galería: proponer, usar, descartar, volver

def test_galeria_free_deja_la_propuesta_con_su_miniatura_y_no_toca_la_ficha(client, repo, mundo, admin_token):
    r = client.post(GAL, headers=_h(admin_token), json={"method": "free"})
    assert r.status_code == 200, r.text
    it = r.json()
    assert set(it) == {"foto_id", "photo_url", "thumb_url", "design_url", "design_thumb_url", "proposal_url",
                       "proposal_method"}
    assert it["foto_id"] == "f1" and it["photo_url"] == f"{BASE}/local-d/g1.jpg" and it["thumb_url"] == f"{BASE}/local-d/g1_t.jpg"
    assert it["design_url"] is None and it["design_thumb_url"] is None and it["proposal_method"] == "free"
    assert it["proposal_url"].startswith(f"{BASE}/local-d/diseno-") and it["proposal_url"].endswith(".jpg")
    assert _tamano(it["proposal_url"]) == (1080, 1350)
    assert _tamano(it["proposal_url"][:-4] + "-t.jpg") == (480, 600)           # la miniatura derivada, junto a la propuesta
    fila = repo.comercio_fotos[0]
    assert fila["diseno_propuesta_url"] == it["proposal_url"] and not fila.get("diseno_url")
    assert fila["url"] == f"{BASE}/local-d/g1.jpg" and _en_disco(fila["url"])  # la original no se toca
    [uso] = repo.photo_style_uses
    assert uso["target"] == "gallery" and uso["foto_id"] == "f1" and uso["method"] == "free"


def test_galeria_sin_body_es_free(client, repo, mundo, admin_token):
    assert client.post(GAL, headers=_h(admin_token)).json()["proposal_method"] == "free"


def test_galeria_gemini_y_externa(client, repo, mundo, admin_token, gemini):
    g = client.post(GAL, headers=_h(admin_token), json={"method": "gemini"}).json()
    assert g["proposal_method"] == "gemini" and _tamano(g["proposal_url"]) == (1080, 1350)
    e = client.post(f"{GAL}/externa", headers=_h(admin_token), files={"foto": ("a.png", _png(900, 1100), "image/png")}).json()
    assert e["proposal_method"] == "external" and e["proposal_url"] != g["proposal_url"]
    assert not _en_disco(g["proposal_url"]) and not _en_disco(g["proposal_url"][:-4] + "-t.jpg")   # la anterior se soltó
    assert _en_disco(e["proposal_url"]) and _en_disco(e["proposal_url"][:-4] + "-t.jpg")


def test_usar_en_la_ficha_copia_la_url_derivada_y_vacia_la_propuesta(client, repo, mundo, admin_token):
    p = client.post(GAL, headers=_h(admin_token)).json()["proposal_url"]
    r = client.put(GAL, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    it = r.json()
    assert it["design_url"] == p and it["design_thumb_url"] == p[:-4] + "-t.jpg"
    assert it["proposal_url"] is None and it["proposal_method"] is None
    fila = repo.comercio_fotos[0]
    assert fila["diseno_url"] == p and fila["diseno_thumb_url"] == p[:-4] + "-t.jpg" and fila["diseno_propuesta_url"] is None
    assert _en_disco(p) and _en_disco(fila["diseno_thumb_url"])


def test_usar_otro_diseno_suelta_el_vigente_anterior(client, repo, mundo, admin_token):
    client.post(GAL, headers=_h(admin_token))
    viejo = client.put(GAL, headers=_h(admin_token)).json()
    client.post(GAL, headers=_h(admin_token))
    nuevo = client.put(GAL, headers=_h(admin_token)).json()
    assert nuevo["design_url"] != viejo["design_url"]
    assert _en_disco(nuevo["design_url"]) and not _en_disco(viejo["design_url"]) and not _en_disco(viejo["design_thumb_url"])


def test_put_sin_propuesta_es_400(client, repo, mundo, admin_token):
    r = client.put(GAL, headers=_h(admin_token))
    assert r.status_code == 400 and "propuesta" in r.json()["detail"]
    r = client.put(COVER, headers=_h(admin_token))
    assert r.status_code == 400


def test_descartar_la_propuesta_no_toca_el_diseno_vigente(client, repo, mundo, admin_token):
    client.post(GAL, headers=_h(admin_token))
    vigente = client.put(GAL, headers=_h(admin_token)).json()["design_url"]
    propuesta = client.post(GAL, headers=_h(admin_token)).json()["proposal_url"]
    r = client.delete(f"{GAL}/propuesta", headers=_h(admin_token))
    assert r.status_code == 200 and r.json()["proposal_url"] is None and r.json()["design_url"] == vigente
    assert _en_disco(vigente) and not _en_disco(propuesta) and not _en_disco(propuesta[:-4] + "-t.jpg")
    assert client.delete(f"{GAL}/propuesta", headers=_h(admin_token)).status_code == 200      # sin propuesta, no es un error


def test_volver_a_la_original_no_borra_la_original_ni_toca_la_propuesta(client, repo, mundo, admin_token):
    client.post(GAL, headers=_h(admin_token))
    vigente = client.put(GAL, headers=_h(admin_token)).json()
    propuesta = client.post(GAL, headers=_h(admin_token)).json()["proposal_url"]
    r = client.delete(GAL, headers=_h(admin_token))
    assert r.status_code == 200
    it = r.json()
    assert it["design_url"] is None and it["design_thumb_url"] is None and it["proposal_url"] == propuesta
    assert not _en_disco(vigente["design_url"]) and not _en_disco(vigente["design_thumb_url"]) and _en_disco(propuesta)
    assert _en_disco(f"{BASE}/local-d/g1.jpg")                              # la original NUNCA se borra
    assert client.delete(GAL, headers=_h(admin_token)).status_code == 200


def test_galeria_404_foto_inexistente_o_de_otro_comercio(client, repo, mundo, admin_token):
    repo.seed_comercio(id="com-x", slug="local-x", nombre="Otro", whatsapp="59170000002", ciudad_id="ciu-1")
    repo.comercio_fotos.append({"id": "fx", "comercio_id": "com-x", "url": f"{BASE}/local-x/z.jpg", "thumb_url": None,
                                "orden": 0, "created_at": "2026-01-01T00:00:00+00:00"})
    for foto in ("nada", "fx"):
        base = f"/admin/comercio/com-d/fotos/{foto}/diseno"
        assert client.post(base, headers=_h(admin_token)).status_code == 404
        assert client.post(f"{base}/externa", headers=_h(admin_token),
                           files={"foto": ("a.png", _png(), "image/png")}).status_code == 404
        assert client.put(base, headers=_h(admin_token)).status_code == 404
        assert client.delete(base, headers=_h(admin_token)).status_code == 404
        assert client.delete(f"{base}/propuesta", headers=_h(admin_token)).status_code == 404
    assert client.post("/admin/comercio/nada/fotos/f1/diseno", headers=_h(admin_token)).status_code == 404
    assert "diseno_propuesta_url" not in repo.comercio_fotos[2] or not repo.comercio_fotos[2]["diseno_propuesta_url"]


def test_galeria_foto_que_no_se_puede_leer_es_400(client, repo, mundo, admin_token):
    (Path(settings.fotos_dir) / "local-d" / "g1.jpg").unlink()
    r = client.post(GAL, headers=_h(admin_token))
    assert r.status_code == 400 and r.json()["detail"] == "No se pudo leer la foto desde el servidor"


def test_galeria_los_permisos(client, repo, mundo, agente_token):
    from tests.conftest import comercio_token
    for metodo, ruta in (("post", GAL), ("post", f"{GAL}/externa"), ("put", GAL), ("delete", GAL), ("delete", f"{GAL}/propuesta")):
        assert getattr(client, metodo)(ruta).status_code in (401, 403)
        assert getattr(client, metodo)(ruta, headers=_h(agente_token)).status_code in (401, 403)
        assert getattr(client, metodo)(ruta, headers=_h(comercio_token(comercio_id="com-d"))).status_code in (401, 403)


def test_galeria_externa_mas_de_15_mb_es_413_y_vacia_es_400(client, repo, mundo, admin_token):
    r = client.post(f"{GAL}/externa", headers=_h(admin_token),
                    files={"foto": ("a.jpg", b"x" * (15 * 1024 * 1024 + 1), "image/jpeg")})
    assert r.status_code == 413
    assert client.post(f"{GAL}/externa", headers=_h(admin_token), files={"foto": ("a.png", b"", "image/png")}).status_code == 400


# ══════════════════════════════════════════ 409

def test_409_si_ya_se_esta_armando_otra_no_llama_a_gemini_ni_registra(client, repo, mundo, admin_token, gemini, monkeypatch):
    monkeypatch.setattr(fe, "ESPERA_TRANSFORMAR", 0.05)
    assert fe._TRANSFORMAR.acquire(timeout=1)
    try:
        rs = [client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}),
              client.post(GAL, headers=_h(admin_token)),
              client.post(f"{GAL}/externa", headers=_h(admin_token), files={"foto": ("a.png", _png(), "image/png")}),
              client.post(f"{COVER}/externa", headers=_h(admin_token), files={"foto": ("a.png", _png(), "image/png")})]
    finally:
        fe._TRANSFORMAR.release()
    assert [r.status_code for r in rs] == [409] * 4
    assert all(r.json()["detail"] == "Ya se está armando otra foto, probá en unos segundos" for r in rs)
    assert gemini.pedidos == [] and repo.photo_style_uses == []
    assert client.post(COVER, headers=_h(admin_token)).status_code == 200          # y se libera


def test_409_si_cambia_la_foto_de_portada_mientras_se_arma_y_no_queda_archivo(client, repo, mundo, admin_token, monkeypatch):
    original = pd.guardar
    nuevas = []

    def guarda_y_cambia(slug, jpeg):
        url = original(slug, jpeg)
        nuevas.append(url)
        repo.comercios["com-d"] = {**repo.comercios["com-d"], "portada_url": f"{BASE}/local-d/otra.jpg"}
        return url

    monkeypatch.setattr(pd, "guardar", guarda_y_cambia)
    r = client.post(COVER, headers=_h(admin_token))
    assert r.status_code == 409 and r.json()["detail"] == "La foto de portada cambió mientras se armaba: armala de nuevo"
    assert nuevas and not _en_disco(nuevas[0]) and not repo.comercios["com-d"].get("portada_diseno_propuesta_url")


def test_409_si_cambia_el_nombre_mientras_se_arma(client, repo, mundo, admin_token, monkeypatch):
    original = pd.guardar

    def guarda_y_renombra(slug, jpeg):
        url = original(slug, jpeg)
        repo.comercios["com-d"] = {**repo.comercios["com-d"], "nombre": "Otro nombre"}
        return url

    monkeypatch.setattr(pd, "guardar", guarda_y_renombra)
    r = client.post(COVER, headers=_h(admin_token))
    assert r.status_code == 409 and "cambiaron" in r.json()["detail"]


def test_409_si_la_foto_de_galeria_cambia_o_se_borra_mientras_se_arma(client, repo, mundo, admin_token, monkeypatch):
    original = fe.guardar_galeria
    creados = []

    def guarda_y_borra(slug, jpeg, thumb):
        r = original(slug, jpeg, thumb)
        creados.append(r)
        repo.comercio_fotos[:] = [f for f in repo.comercio_fotos if f["id"] != "f1"]
        return r

    monkeypatch.setattr(fe, "guardar_galeria", guarda_y_borra)
    r = client.post(GAL, headers=_h(admin_token))
    assert r.status_code == 409 and "cambió o se borró" in r.json()["detail"]
    assert creados and not _en_disco(creados[0][0]) and not _en_disco(creados[0][1])


# ══════════════════════════════════════════ 429, 502, 503, 504 (Gemini)

def test_429_al_llegar_al_tope_del_dia_no_llama_a_gemini(client, repo, mundo, admin_token, gemini, monkeypatch):
    monkeypatch.setattr(settings, "gemini_fotos_tope_diario", 3)
    for _ in range(3):
        assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200
    antes = len(gemini.pedidos)
    for ruta in (COVER, GAL):
        r = client.post(ruta, headers=_h(admin_token), json={"method": "gemini"})
        assert r.status_code == 429 and r.json()["detail"] == "Se llegó al tope de 3 fotos con IA por hoy"
    assert len(gemini.pedidos) == antes == 3
    # las gratis y las de afuera no cuentan
    assert client.post(COVER, headers=_h(admin_token)).status_code == 200
    assert client.post(GAL, headers=_h(admin_token)).status_code == 200


def test_el_tope_se_cuenta_en_la_base_y_cuentan_las_que_fallaron(client, repo, mundo, admin_token, gemini, monkeypatch):
    """Un contador en memoria vuelve a cero al reiniciar; éste sale de `photo_style_uses`, incluyendo errores y timeouts."""
    monkeypatch.setattr(settings, "gemini_fotos_tope_diario", 2)
    for resultado in ("error", "timeout"):
        repo.registrar_uso_foto_estilo({"comercio_id": "com-x", "target": "cover", "method": "gemini", "result": resultado,
                                        "actor": "x@y", "cost_usd": 0})
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 429 and gemini.pedidos == []


def test_el_tope_cuenta_desde_las_00_de_bolivia(client, repo, mundo, admin_token, gemini, monkeypatch):
    from datetime import timedelta
    from app.services import cargas
    monkeypatch.setattr(settings, "gemini_fotos_tope_diario", 1)
    inicio, _ = cargas.limites_dia_utc(cargas.hoy_bolivia())
    repo.registrar_uso_foto_estilo({"comercio_id": "com-x", "target": "cover", "method": "gemini", "result": "ok",
                                    "actor": "x@y", "cost_usd": COSTO,
                                    "created_at": (inicio - timedelta(minutes=1)).isoformat()})     # anoche: no cuenta
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 429


def test_503_con_el_interruptor_apagado_no_llama_ni_registra(client, repo, mundo, admin_token, conf, crepo, monkeypatch):
    g = _con_respuesta(monkeypatch, Gemini.imagen())
    cost_switches.set(crepo, cost_switches.GEMINI_FOTOS, False, "test@uruku.bo")
    for ruta in (COVER, GAL):
        r = client.post(ruta, headers=_h(admin_token), json={"method": "gemini"})
        assert r.status_code == 503 and r.json()["detail"].startswith("Fotos con IA no disponible: ")
        assert "apagado" in r.json()["detail"]
    assert g.pedidos == [] and repo.photo_style_uses == []
    assert client.post(COVER, headers=_h(admin_token)).status_code == 200          # lo gratis sigue andando


def test_503_por_defecto_sin_configurar_nada(client, repo, mundo, admin_token):
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 503 and "apagado" in r.json()["detail"]


@pytest.mark.parametrize("campo,valor,palabra", [("gemini_api_key", "", "clave"), ("gemini_image_model", "", "modelo"),
                                                  ("gemini_image_cost_usd", 0.0, "costo")])
def test_503_si_falta_la_clave_el_modelo_o_el_costo(client, repo, mundo, admin_token, gemini, monkeypatch, campo, valor, palabra):
    monkeypatch.setattr(settings, campo, valor)
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 503 and palabra in r.json()["detail"] and gemini.pedidos == []


def test_504_timeout_se_registra_y_cuenta(client, repo, mundo, admin_token, conf, monkeypatch):
    def tarda(req):
        raise httpx.ReadTimeout("se colgó", request=req)
    g = _con_respuesta(monkeypatch, tarda)
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 504 and "no contestó a tiempo" in r.json()["detail"]
    [uso] = repo.photo_style_uses
    assert (uso["method"], uso["result"], uso["cost_usd"]) == ("gemini", "timeout", COSTO)     # el timeout se cobra
    assert uso["result_url"] is None and uso["actor"] == ADMIN
    assert not repo.comercios["com-d"].get("portada_diseno_propuesta_url")
    assert fe._TRANSFORMAR.acquire(timeout=0.1)
    fe._TRANSFORMAR.release()                                                                    # el lock se soltó
    assert len(g.pedidos) == 1


def test_el_timeout_de_gemini_es_el_del_setting(monkeypatch, conf):
    visto = {}
    original = httpx.Client

    class Espia(original):
        def __init__(self, *a, **kw):
            visto["timeout"] = kw.get("timeout")
            super().__init__(*a, **kw)

    monkeypatch.setattr(settings, "gemini_image_timeout_seg", 7)
    monkeypatch.setattr(ge.httpx, "Client", Espia)
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(Gemini()))
    ge.reestilizar(_jpeg(), "cover")
    assert visto["timeout"].read == 7 and visto["timeout"].connect == 7


def test_502_si_gemini_contesta_con_error_no_se_cobra(client, repo, mundo, admin_token, conf, monkeypatch):
    _con_respuesta(monkeypatch, lambda req: httpx.Response(429, json={"error": {"message": "Resource has been exhausted"}}))
    r = client.post(GAL, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 502 and "429" in r.json()["detail"]
    [uso] = repo.photo_style_uses
    assert (uso["method"], uso["result"], uso["cost_usd"], uso["foto_id"]) == ("gemini", "error", 0, "f1")
    assert "429" in uso["error"]


def test_502_si_no_devuelve_imagen_no_se_cobra(client, repo, mundo, admin_token, conf, monkeypatch):
    _con_respuesta(monkeypatch, lambda req: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "no puedo"}]}}]}))
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 502 and "no devolvió una imagen" in r.json()["detail"]
    assert repo.photo_style_uses[0]["cost_usd"] == 0 and repo.photo_style_uses[0]["result"] == "error"


def test_502_si_bloquean_el_pedido(client, repo, mundo, admin_token, conf, monkeypatch):
    _con_respuesta(monkeypatch, lambda req: httpx.Response(200, json={"promptFeedback": {"blockReason": "SAFETY"}}))
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 502 and "SAFETY" in r.json()["detail"]


def test_502_si_la_imagen_que_vuelve_no_sirve_se_cobra_igual(client, repo, mundo, admin_token, conf, monkeypatch):
    _con_respuesta(monkeypatch, Gemini.imagen(b"esto no es una imagen"))
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 502
    [uso] = repo.photo_style_uses
    assert (uso["result"], uso["cost_usd"]) == ("error", COSTO)          # hubo imagen: se cobra aunque no se pueda usar
    assert not repo.comercios["com-d"].get("portada_diseno_propuesta_url")


def test_502_si_la_imagen_que_vuelve_es_gigante_o_de_otro_formato(client, repo, mundo, admin_token, conf, monkeypatch):
    buf = BytesIO()
    Image.new("RGB", (600, 400)).save(buf, format="GIF")
    _con_respuesta(monkeypatch, Gemini.imagen(buf.getvalue()))
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 502
    enorme = BytesIO()
    Image.new("L", (7000, 7000)).save(enorme, format="PNG")            # 49 MP: pasa los 40 MP, pesa unos pocos KB
    _con_respuesta(monkeypatch, Gemini.imagen(enorme.getvalue()))
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 502
    assert [u["cost_usd"] for u in repo.photo_style_uses] == [COSTO, COSTO]       # las dos volvieron con imagen: se cobran


def test_502_si_no_se_puede_guardar(client, repo, mundo, admin_token, monkeypatch):
    monkeypatch.setattr(pd, "guardar", lambda slug, jpeg: None)
    r = client.post(COVER, headers=_h(admin_token))
    assert r.status_code == 502 and "No se pudo guardar" in r.json()["detail"]
    assert repo.photo_style_uses == []                                    # free sólo se registra si salió bien
    monkeypatch.setattr(fe, "guardar_galeria", lambda *a: None)
    assert client.post(GAL, headers=_h(admin_token)).status_code == 502


def test_si_falla_el_registro_la_foto_igual_se_entrega(client, repo, mundo, admin_token, gemini):
    repo.falla_registro_uso = True
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200


# ══════════════════════════════════════════ la clave nunca sale

def test_la_clave_nunca_aparece_en_detail_ni_en_el_registro(client, repo, mundo, admin_token, conf, monkeypatch):
    peligrosos = [
        lambda req: httpx.Response(400, json={"error": {"message": f"API key not valid ({CLAVE}). {req.url}?key={CLAVE}"}}),
        lambda req: httpx.Response(500, json={"error": {"message": f"x-goog-api-key: {CLAVE} rechazada"}}),
        lambda req: (_ for _ in ()).throw(httpx.ConnectError(f"no conecta a {req.url}?key={CLAVE}", request=req)),
    ]
    for respuesta in peligrosos:
        _con_respuesta(monkeypatch, respuesta)
        for ruta in (COVER, GAL):
            r = client.post(ruta, headers=_h(admin_token), json={"method": "gemini"})
            assert r.status_code == 502
            assert CLAVE not in r.text and CLAVE not in json.dumps(r.json())
    assert repo.photo_style_uses
    for uso in repo.photo_style_uses:
        assert CLAVE not in json.dumps(uso, default=str) and len(uso["error"]) <= 300


def test_el_error_del_registro_se_corta_a_300(client, repo, mundo, admin_token, conf, monkeypatch):
    _con_respuesta(monkeypatch, lambda req: httpx.Response(500, json={"error": {"message": "x" * 5000}}))
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 502
    assert len(repo.photo_style_uses[0]["error"]) == 300


def test_la_clave_no_esta_en_el_estado_ni_en_la_url_de_gemini(client, repo, mundo, admin_token, conf):
    assert CLAVE not in client.get(ESTADO, headers=_h(admin_token)).text
    from app.core import gemini as core
    assert CLAVE not in core.url_generar_imagen() and core.url_generar_imagen().endswith(f"{MODELO}:generateContent")
    assert core.cabeceras() == {"x-goog-api-key": CLAVE}


def test_url_generar_imagen_sin_modelo_no_inventa_uno(monkeypatch):
    from app.core import gemini as core
    monkeypatch.setattr(settings, "gemini_image_model", "")
    assert core.url_generar_imagen() == ""


# ══════════════════════════════════════════ GET /usos

def test_usos_resume_lo_gastado_por_comercio(client, repo, mundo, admin_token):
    repo.seed_comercio(id="com-y", slug="local-y", nombre="Almacén Y", whatsapp="59170000003", ciudad_id="ciu-1")
    for cid, res, costo in (("com-d", "ok", 0.0336), ("com-d", "timeout", 0.0336), ("com-d", "error", 0),
                            ("com-y", "ok", 0.0336)):
        repo.registrar_uso_foto_estilo({"comercio_id": cid, "target": "cover", "method": "gemini", "result": res,
                                        "actor": "a@b", "cost_usd": costo})
    repo.registrar_uso_foto_estilo({"comercio_id": "com-y", "target": "cover", "method": "free", "result": "ok",
                                    "actor": "a@b", "cost_usd": 0})
    from app.services import cargas
    hoy = cargas.hoy_bolivia().isoformat()
    r = client.get(f"/admin/fotos-estilo/usos?desde={hoy}&hasta={hoy}", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["desde"] == hoy and u["hasta"] == hoy and u["images"] == 3 and u["cost_usd"] == pytest.approx(0.1008, abs=1e-4)
    assert [m["comercio_id"] for m in u["by_merchant"]] == ["com-d", "com-y"]
    assert u["by_merchant"][0] == {"comercio_id": "com-d", "nombre": NOMBRE, "images": 2, "cost_usd": pytest.approx(0.0672, abs=1e-4)}
    assert client.get("/admin/fotos-estilo/usos", headers=_h(admin_token)).status_code == 200      # sin fechas: el mes


def test_usos_un_dia_sin_nada_da_ceros_y_las_fechas_se_validan(client, repo, mundo, admin_token):
    u = client.get("/admin/fotos-estilo/usos?desde=2026-01-01&hasta=2026-01-31", headers=_h(admin_token)).json()
    assert u == {"desde": "2026-01-01", "hasta": "2026-01-31", "images": 0, "cost_usd": 0, "by_merchant": []}
    for malo in ("desde=ayer", "desde=2026-13-01", "desde=2026-02-01&hasta=2026-01-01", "desde=2020-01-01&hasta=2026-01-01"):
        assert client.get(f"/admin/fotos-estilo/usos?{malo}", headers=_h(admin_token)).status_code == 400, malo


def test_usos_pide_el_permiso_pagos(client, repo, mundo, agente_token):
    assert client.get("/admin/fotos-estilo/usos").status_code in (401, 403)
    assert client.get("/admin/fotos-estilo/usos", headers=_h(agente_token)).status_code in (401, 403)


def test_las_rutas_nuevas_estan_en_la_tabla_de_topes_de_cuerpo():
    from app.core.limite_cuerpo import TOPE_POR_DEFECTO, tope_para
    for ruta in ("/admin/comercio/abc/portada-diseno/externa", "/admin/comercio/abc/fotos/xyz/diseno/externa"):
        assert tope_para(ruta) > 15 * 1024 * 1024 and tope_para(ruta) > TOPE_POR_DEFECTO
