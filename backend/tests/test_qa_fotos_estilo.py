"""QA de aceptación: fotos con estilo URUKU (docs/fotos-estilo-uruku.md §5 códigos de error y §9 «Terminado»).

Independiente de los `test_fotos_estilo_*` del desarrollo: parte de los criterios de la spec y ataca los bordes
(estados inválidos, aislamiento entre comercios, permisos, entradas hostiles, red). Sin red real (`httpx.MockTransport`)
y sin gastar (Gemini falso). No modifica producción: lo que falla acá es un bug a reportar.

Criterio de §9 -> test:
  POST de portada sin body = gratis ............... test_portada_sin_body_*
  method gemini con interruptor apagado -> 503 .... test_503_*
  tope diario -> 429 .............................. test_429_*
  la propuesta nunca se publica sola .............. test_propuesta_nunca_se_publica_sola_*
  PUT / DELETE propuesta / DELETE ficha ........... test_ciclo_*
  /externa PNG/JPG/WEBP, no imagen, >15 MB, chica . test_externa_*
  logo abajo a la derecha ......................... test_logo_*
  lectura remota de QA ............................ test_remoto_*
  vencimiento al reemplazar la foto ............... test_vencimiento_*
  permisos ........................................ test_permiso_*
"""
import base64
import json
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image, ImageChops

from app.core import auth
from app.core.config import settings
from app.services import cost_switches, fotos_estilo as fe, fotos_estilo_gemini as ge, fotos_origen as fo, portada_diseno as pd
from app.services.imagenes import guardar_foto_local
from tests.conftest import comercio_token

BASE = "https://api.qa.test/fotos"
PROD = "https://api.uruku.bo/fotos"
CLAVE = "AIzaSy-QA-CLAVE-SECRETA-987654321"
MODELO = "modelo-qa"
COSTO = 0.0336
ADMIN = "admin@bermejolive.com"

COVER = "/admin/comercio/com-q/portada-diseno"
COVER_EXT = COVER + "/externa"
GAL = "/admin/comercio/com-q/fotos/f1/diseno"
GAL_EXT = GAL + "/externa"
ESTADO = "/admin/comercio/com-q/fotos-estilo"
USOS = "/admin/fotos-estilo/usos"


# ───────────────────────────────────────────────────────────── utilidades

def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _img(formato="JPEG", w=800, h=600, color="green", modo="RGB") -> bytes:
    buf = BytesIO()
    Image.new(modo, (w, h), color).save(buf, format=formato)
    return buf.getvalue()


def _jpeg(w=800, h=600, color="green"):
    return _img("JPEG", w, h, color)


def _subida(datos: bytes, nombre="x.jpg", tipo="image/jpeg"):
    return {"foto": (nombre, datos, tipo)}


def _ruta(url: str) -> Path:
    return Path(settings.fotos_dir) / url[len(BASE) + 1:]


def _en_disco(url) -> bool:
    return _ruta(url).exists()


def _tam(url):
    return Image.open(_ruta(url)).size


def _diseno_en_disco() -> list[str]:
    return sorted(p.name for p in (Path(settings.fotos_dir) / "local-q").glob("diseno-*"))


@pytest.fixture(autouse=True)
def _base(monkeypatch):
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", "")
    # Si algún camino intentara red de verdad en un test que no la espera, que falle fuerte.
    def _sin_red(req):
        raise AssertionError(f"red inesperada: {req.method} {req.url}")
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(_sin_red))
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(_sin_red))


@pytest.fixture
def mundo(repo):
    """Comercio `com-q` con portada y 2 fotos de galería; y `com-otro` con una foto (para aislamiento)."""
    repo.rubros["ferreteria"] = "rub-ferre"
    guardar_foto_local("local-q/orig.jpg", _jpeg(1200, 800))
    guardar_foto_local("local-q/g1.jpg", _jpeg(900, 1100, "red"))
    guardar_foto_local("local-q/g2.jpg", _jpeg(1000, 1000, "yellow"))
    guardar_foto_local("otro/o1.jpg", _jpeg(900, 1100, "blue"))
    c = repo.seed_comercio(id="com-q", slug="local-q", nombre="Ferretería QA", whatsapp="59170000100", ciudad_id="ciu-1",
                           rubro_id="rub-ferre", portada_url=f"{BASE}/local-q/orig.jpg", portada_pos=None)
    repo.seed_comercio(id="com-otro", slug="otro", nombre="Otro Comercio", whatsapp="59170000101", ciudad_id="ciu-1",
                       portada_url=f"{BASE}/otro/o1.jpg")
    for i, n in enumerate(("g1", "g2")):
        repo.comercio_fotos.append({"id": f"f{i + 1}", "comercio_id": "com-q", "url": f"{BASE}/local-q/{n}.jpg",
                                    "thumb_url": f"{BASE}/local-q/{n}_t.jpg", "orden": i,
                                    "created_at": f"2026-01-0{i + 1}T00:00:00+00:00"})
    repo.comercio_fotos.append({"id": "fo1", "comercio_id": "com-otro", "url": f"{BASE}/otro/o1.jpg", "thumb_url": None,
                                "orden": 0, "created_at": "2026-01-01T00:00:00+00:00"})
    return c


class Gemini:
    def __init__(self, respuesta=None):
        self.pedidos: list[httpx.Request] = []
        datos = _jpeg(1536, 1024, "orange")
        cuerpo = {"candidates": [{"content": {"parts": [{"inlineData": {"mimeType": "image/jpeg",
                                                                        "data": base64.b64encode(datos).decode()}}]}}]}
        self.respuesta = respuesta or (lambda req: httpx.Response(200, json=cuerpo))

    def __call__(self, request):
        self.pedidos.append(request)
        return self.respuesta(request)


def _configurar(monkeypatch, crepo, *, interruptor=True, tope=20):
    monkeypatch.setattr(settings, "gemini_api_key", CLAVE)
    monkeypatch.setattr(settings, "gemini_image_model", MODELO)
    monkeypatch.setattr(settings, "gemini_image_cost_usd", COSTO)
    monkeypatch.setattr(settings, "gemini_fotos_tope_diario", tope)
    monkeypatch.setattr(settings, "gemini_image_timeout_seg", 60)
    cost_switches.set(crepo, cost_switches.GEMINI_FOTOS, interruptor, "qa@uruku.bo")


@pytest.fixture
def gemini(monkeypatch, crepo):
    _configurar(monkeypatch, crepo)
    g = Gemini()
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(g))
    return g


def _publico(repo) -> dict:
    """Todo lo que se publicaría hoy en la ficha: la portada de diseño vigente y las columnas públicas de la galería."""
    c = repo.comercios["com-q"]
    return {"portada_diseno_url": c.get("portada_diseno_url"),
            "galeria": [(f["id"], f.get("diseno_url"), f.get("diseno_thumb_url")) for f in repo.list_fotos_comercio("com-q")]}


# ══════════════════════════════════════════════════════════════ §9 portada sin body = gratis

def test_portada_sin_body_es_gratis_no_llama_a_gemini_ni_cobra(client, repo, mundo, admin_token):
    r = client.post(COVER, headers=_h(admin_token))        # sin body (y sin content-type)
    assert r.status_code == 200, r.text
    assert r.json()["proposal_method"] == "free"
    [uso] = repo.photo_style_uses
    assert uso["method"] == "free" and uso["cost_usd"] == 0 and uso["result"] == "ok"
    assert fe.usados_hoy(repo) == 0                       # lo gratis no consume el tope de IA


def test_portada_con_body_vacio_json_o_nulo_tambien_es_gratis(client, repo, mundo, admin_token):
    for body in ({}, None):
        r = client.post(COVER, headers=_h(admin_token), json=body)
        assert r.status_code == 200, (body, r.text)
        assert r.json()["proposal_method"] == "free"
    assert {u["method"] for u in repo.photo_style_uses} == {"free"}


def test_galeria_sin_body_tambien_es_gratis(client, repo, mundo, admin_token):
    r = client.post(GAL, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["proposal_method"] == "free" and r.json()["proposal_url"]
    assert _tam(r.json()["proposal_url"]) == (1080, 1350)


@pytest.mark.parametrize("body", [{"method": "dalle"}, {"method": "external"}, {"method": ["gemini"]}, {"method": 1},
                                  {"method": "GEMINI"}])
def test_method_invalido_es_422_y_no_registra(client, repo, mundo, admin_token, body):
    for ruta in (COVER, GAL):
        r = client.post(ruta, headers=_h(admin_token), json=body)
        assert r.status_code == 422, (ruta, body, r.text)
    assert repo.photo_style_uses == []


# ══════════════════════════════════════════════════════════════ §9 interruptor apagado -> 503

def test_503_gemini_con_el_interruptor_apagado_da_el_motivo_y_no_registra(client, repo, mundo, admin_token, monkeypatch, crepo):
    _configurar(monkeypatch, crepo, interruptor=False)          # clave, modelo y costo OK: sólo el interruptor apagado
    g = Gemini()
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(g))
    for ruta in (COVER, GAL):
        r = client.post(ruta, headers=_h(admin_token), json={"method": "gemini"})
        assert r.status_code == 503, r.text
        detail = r.json()["detail"]
        assert detail.startswith("Fotos con IA no disponible: ") and "apagado" in detail
        assert CLAVE not in detail
    assert g.pedidos == []                                       # no se llamó
    assert repo.photo_style_uses == []                           # ni se registró ni cuenta para el tope
    assert fe.usados_hoy(repo) == 0
    assert not repo.comercios["com-q"].get("portada_diseno_propuesta_url")


def test_503_el_get_estado_lo_anticipa_y_lo_gratis_sigue_andando(client, repo, mundo, admin_token, monkeypatch, crepo):
    _configurar(monkeypatch, crepo, interruptor=False)
    g = client.get(ESTADO, headers=_h(admin_token)).json()["gemini"]
    assert g["available"] is False and "apagado" in g["reason"] and CLAVE not in json.dumps(g)
    assert client.post(COVER, headers=_h(admin_token), json={"method": "free"}).status_code == 200
    assert client.post(GAL_EXT, headers=_h(admin_token), files=_subida(_jpeg(1000, 800))).status_code == 200


@pytest.mark.parametrize("campo,valor,palabra", [("gemini_api_key", "", "clave"), ("gemini_image_model", "", "modelo"),
                                                  ("gemini_image_cost_usd", 0.0, "costo")])
def test_503_falta_clave_modelo_o_costo_aunque_el_interruptor_este_prendido(client, repo, mundo, admin_token, gemini,
                                                                           monkeypatch, campo, valor, palabra):
    monkeypatch.setattr(settings, campo, valor)
    for ruta in (COVER, GAL):
        r = client.post(ruta, headers=_h(admin_token), json={"method": "gemini"})
        assert r.status_code == 503 and palabra in r.json()["detail"], r.text
    assert gemini.pedidos == [] and repo.photo_style_uses == []


def test_503_el_interruptor_se_relee_en_cada_pedido(client, repo, mundo, admin_token, gemini, crepo):
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200
    cost_switches.set(crepo, cost_switches.GEMINI_FOTOS, False, "qa@uruku.bo")
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 503
    assert len(gemini.pedidos) == 1 and len(repo.photo_style_uses) == 1


# ══════════════════════════════════════════════════════════════ §9 tope diario -> 429

def test_429_al_llegar_al_tope_de_n_no_llama_a_gemini_y_dice_el_numero(client, repo, mundo, admin_token, monkeypatch, crepo):
    _configurar(monkeypatch, crepo, tope=2)
    g = Gemini()
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(g))
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200
    assert client.post(GAL, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200
    r = client.post("/admin/comercio/com-q/fotos/f2/diseno", headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 429 and r.json()["detail"] == "Se llegó al tope de 2 fotos con IA por hoy"
    assert len(g.pedidos) == 2 and len(repo.photo_style_uses) == 2          # el 429 no registra ni llama
    # lo que no es IA no está topado
    assert client.post(COVER, headers=_h(admin_token), json={"method": "free"}).status_code == 200
    assert client.post(COVER_EXT, headers=_h(admin_token), files=_subida(_jpeg(1200, 800))).status_code == 200
    assert client.post(GAL, headers=_h(admin_token)).status_code == 200


def test_429_tope_cero_bloquea_toda_la_ia(client, repo, mundo, admin_token, monkeypatch, crepo):
    _configurar(monkeypatch, crepo, tope=0)
    r = client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 429 and "0" in r.json()["detail"]


def test_429_el_tope_es_global_no_por_comercio_ni_por_foto(client, repo, mundo, admin_token, monkeypatch, crepo):
    _configurar(monkeypatch, crepo, tope=1)
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(Gemini()))
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200
    r = client.post("/admin/comercio/com-otro/portada-diseno", headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 429


def test_429_el_fallo_de_gemini_cuenta_para_el_tope(client, repo, mundo, admin_token, monkeypatch, crepo):
    _configurar(monkeypatch, crepo, tope=1)
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(lambda req: httpx.Response(500, json={"error": {"message": "boom"}})))
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 502
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 429


def test_429_el_dia_arranca_a_las_00_de_bolivia_las_de_ayer_no_cuentan(client, repo, mundo, admin_token, monkeypatch, crepo):
    from datetime import datetime, timedelta, timezone
    _configurar(monkeypatch, crepo, tope=1)
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(Gemini()))
    ayer = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    repo.photo_style_uses.append({"id": "viejo", "comercio_id": "com-q", "foto_id": None, "target": "cover",
                                  "method": "gemini", "cost_usd": COSTO, "result": "ok", "created_at": ayer, "actor": "x"})
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 200
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).status_code == 429


# ══════════════════════════════════════════════════════════════ §9 la propuesta nunca se publica sola

@pytest.mark.parametrize("camino", ["free", "gemini", "externa"])
def test_propuesta_nunca_se_publica_sola_en_portada_y_galeria(client, repo, mundo, admin_token, gemini, camino):
    antes = _publico(repo)
    for ruta, ruta_ext in ((COVER, COVER_EXT), (GAL, GAL_EXT)):
        if camino == "externa":
            r = client.post(ruta_ext, headers=_h(admin_token), files=_subida(_jpeg(1400, 1400)))
        else:
            r = client.post(ruta, headers=_h(admin_token), json={"method": camino})
        assert r.status_code == 200, r.text
    # hay propuesta en las dos columnas PRIVADAS...
    assert repo.comercios["com-q"]["portada_diseno_propuesta_url"]
    assert repo.comercio_fotos[0]["diseno_propuesta_url"]
    # ...y las columnas PÚBLICAS no se movieron ni un byte (sin PUT no cambia nada)
    assert _publico(repo) == antes
    assert not repo.comercios["com-q"].get("portada_diseno_url")
    assert repo.comercio_fotos[0].get("diseno_url") is None and repo.comercio_fotos[0].get("diseno_thumb_url") is None
    # no se tocó ninguna otra foto ni el otro comercio
    assert repo.comercio_fotos[1].get("diseno_propuesta_url") is None
    assert not repo.comercios["com-otro"].get("portada_diseno_propuesta_url")


def test_propuesta_regenerar_no_publica_y_suelta_la_anterior(client, repo, mundo, admin_token):
    r1 = client.post(GAL, headers=_h(admin_token)).json()
    r2 = client.post(GAL, headers=_h(admin_token)).json()
    assert r1["proposal_url"] != r2["proposal_url"]
    assert not _en_disco(r1["proposal_url"]) and _en_disco(r2["proposal_url"])     # no quedan huérfanos
    assert repo.comercio_fotos[0].get("diseno_url") is None


def test_propuesta_la_ruta_admin_de_galeria_no_expone_publicas_las_propuestas_de_otros_roles(client, repo, mundo, admin_token):
    """El GET de estado y los POST son del admin: ni un comercio ni un agente ni nadie sin token los ve ni los arma."""
    client.post(GAL, headers=_h(admin_token))
    for token in (comercio_token(comercio_id="com-q"), auth.make_agente_token("a@x.com"), None):
        h = _h(token) if token else {}
        assert client.get(ESTADO, headers=h).status_code in (401, 403)
        assert client.post(GAL, headers=h).status_code in (401, 403)


def test_propuesta_privada_no_se_filtra_a_la_cuenta_del_comercio(client, repo, mundo, admin_token):
    """`GET /comercio/fotos` es lo que ve el comerciante: la columna privada `diseno_propuesta_url` no debería salir
    (spec §4: privada; la 0203 la saca del `select` de anon/authenticated)."""
    client.post(GAL, headers=_h(admin_token))
    assert repo.comercio_fotos[0]["diseno_propuesta_url"]
    r = client.get("/comercio/fotos", headers=_h(comercio_token(comercio_id="com-q")))
    assert r.status_code == 200, r.text
    assert "diseno_propuesta_url" not in json.dumps(r.json()), "la propuesta sin aprobar llega al comerciante"


def test_propuesta_privada_no_se_filtra_al_agente_de_campo(client, repo, mundo, admin_token):
    client.post(GAL, headers=_h(admin_token))
    repo.comercios["com-q"]["cargado_por"] = "agente@bermejolive.com"
    r = client.get("/campo/mis-comercios/com-q/fotos", headers=_h(auth.make_agente_token("agente@bermejolive.com")))
    assert r.status_code == 200, r.text
    assert "diseno_propuesta_url" not in json.dumps(r.json()), "la propuesta sin aprobar llega al agente de campo"


# ══════════════════════════════════════════════════════════════ §9 PUT / DELETE propuesta / DELETE ficha

def test_ciclo_galeria_propuesta_usar_y_volver_a_la_original(client, repo, mundo, admin_token):
    original = repo.comercio_fotos[0]["url"]
    prop = client.post(GAL, headers=_h(admin_token)).json()
    p_url = prop["proposal_url"]
    assert _en_disco(p_url) and _en_disco(fe.miniatura_de(p_url)) and _tam(fe.miniatura_de(p_url)) == (480, 600)

    # PUT: la propuesta pasa a pública, con su miniatura derivada, y la propuesta queda vacía
    r = client.put(GAL, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    it = r.json()
    assert it["design_url"] == p_url and it["design_thumb_url"] == fe.miniatura_de(p_url)
    assert it["proposal_url"] is None and it["proposal_method"] is None
    fila = repo.comercio_fotos[0]
    assert fila["diseno_url"] == p_url and fila["diseno_propuesta_url"] is None and fila["url"] == original

    # PUT otra vez: ya no hay propuesta -> 400 y nada cambia (idempotencia del estado)
    r = client.put(GAL, headers=_h(admin_token))
    assert r.status_code == 400 and r.json()["detail"]
    assert repo.comercio_fotos[0]["diseno_url"] == p_url

    # DELETE de la ficha («volver a la original»): la original no se toca, los archivos de diseño se sueltan
    r = client.delete(GAL, headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json()["design_url"] is None and r.json()["design_thumb_url"] is None
    assert r.json()["photo_url"] == original and _en_disco(original)
    assert not _en_disco(p_url) and not _en_disco(fe.miniatura_de(p_url))
    # idempotente
    assert client.delete(GAL, headers=_h(admin_token)).status_code == 200
    assert _en_disco(original)


def test_ciclo_galeria_descartar_la_propuesta_no_toca_el_diseno_vigente(client, repo, mundo, admin_token):
    client.post(GAL, headers=_h(admin_token))
    client.put(GAL, headers=_h(admin_token))
    vigente = repo.comercio_fotos[0]["diseno_url"]
    nueva = client.post(GAL, headers=_h(admin_token)).json()["proposal_url"]
    r = client.delete(GAL + "/propuesta", headers=_h(admin_token))
    assert r.status_code == 200 and r.json()["proposal_url"] is None and r.json()["design_url"] == vigente
    assert _en_disco(vigente) and not _en_disco(nueva)
    # idempotente: descartar sin propuesta no es error
    assert client.delete(GAL + "/propuesta", headers=_h(admin_token)).status_code == 200


def test_ciclo_galeria_usar_una_propuesta_nueva_suelta_el_diseno_anterior(client, repo, mundo, admin_token):
    p1 = client.post(GAL, headers=_h(admin_token)).json()["proposal_url"]
    client.put(GAL, headers=_h(admin_token))
    p2 = client.post(GAL, headers=_h(admin_token)).json()["proposal_url"]
    client.put(GAL, headers=_h(admin_token))
    assert repo.comercio_fotos[0]["diseno_url"] == p2
    assert not _en_disco(p1) and _en_disco(p2)


def test_ciclo_galeria_volver_a_la_original_no_toca_una_propuesta_pendiente(client, repo, mundo, admin_token):
    client.post(GAL, headers=_h(admin_token))
    client.put(GAL, headers=_h(admin_token))
    pend = client.post(GAL, headers=_h(admin_token)).json()["proposal_url"]
    r = client.delete(GAL, headers=_h(admin_token))
    assert r.json()["design_url"] is None and r.json()["proposal_url"] == pend and _en_disco(pend)


def test_ciclo_portada_propuesta_usar_descartar_y_quitar(client, repo, mundo, admin_token):
    original = repo.comercios["com-q"]["portada_url"]
    # PUT sin propuesta -> 400
    r = client.put(COVER, headers=_h(admin_token))
    assert r.status_code == 400
    p1 = client.post(COVER, headers=_h(admin_token)).json()["portada_diseno_propuesta_url"]
    assert _tam(p1) == (1600, 1000)
    r = client.put(COVER, headers=_h(admin_token))
    assert r.status_code == 200
    assert r.json()["portada_diseno_url"] == p1 and r.json()["portada_diseno_propuesta_url"] is None
    assert repo.comercios["com-q"]["portada_diseno_url"] == p1
    # otra propuesta y descartarla: el vigente queda
    p2 = client.post(COVER, headers=_h(admin_token)).json()["portada_diseno_propuesta_url"]
    r = client.delete(COVER + "/propuesta", headers=_h(admin_token))
    assert r.status_code == 200 and r.json()["portada_diseno_url"] == p1 and r.json()["portada_diseno_propuesta_url"] is None
    assert _en_disco(p1) and not _en_disco(p2)
    assert client.delete(COVER + "/propuesta", headers=_h(admin_token)).status_code == 200     # idempotente
    # quitar el vigente: vuelve a la original, que sigue en el disco
    r = client.delete(COVER, headers=_h(admin_token))
    assert r.status_code == 200 and r.json()["portada_diseno_url"] is None
    assert not _en_disco(p1) and _en_disco(original)
    assert client.delete(COVER, headers=_h(admin_token)).status_code == 200


def test_ciclo_el_proposal_method_viene_del_registro_de_usos(client, repo, mundo, admin_token, gemini):
    assert client.post(COVER, headers=_h(admin_token)).json()["proposal_method"] == "free"
    assert client.post(COVER, headers=_h(admin_token), json={"method": "gemini"}).json()["proposal_method"] == "gemini"
    assert client.post(COVER_EXT, headers=_h(admin_token), files=_subida(_jpeg(1200, 800))).json()["proposal_method"] == "external"
    e = client.get(ESTADO, headers=_h(admin_token)).json()
    assert e["cover"]["proposal_method"] == "external"


# ── 404 y aislamiento entre comercios

RUTAS_FOTO = [("POST", ""), ("POST", "/externa"), ("PUT", ""), ("DELETE", "/propuesta"), ("DELETE", "")]


def _llamar(client, metodo, ruta, token):
    kw = {"headers": _h(token)}
    if ruta.endswith("/externa"):
        kw["files"] = _subida(_jpeg(900, 900))
    return client.request(metodo, ruta, **kw)


@pytest.mark.parametrize("metodo,sufijo", RUTAS_FOTO)
def test_404_la_foto_de_otro_comercio_no_se_toca(client, repo, mundo, admin_token, metodo, sufijo):
    antes = [dict(f) for f in repo.comercio_fotos]
    # fo1 es de com-otro: pedirla bajo com-q tiene que dar 404 y no escribir nada
    r = _llamar(client, metodo, f"/admin/comercio/com-q/fotos/fo1/diseno{sufijo}", admin_token)
    assert r.status_code == 404, r.text
    assert repo.comercio_fotos == antes
    assert repo.photo_style_uses == []
    assert _diseno_en_disco() == [] and not list((Path(settings.fotos_dir) / "otro").glob("diseno-*"))


@pytest.mark.parametrize("metodo,sufijo", RUTAS_FOTO)
@pytest.mark.parametrize("foto_id", ["no-existe", "..", "f1;drop table comercio_fotos", "%2e%2e", "x" * 500, "' OR '1'='1"])
def test_404_foto_inexistente_o_hostil_nunca_es_500(client, repo, mundo, admin_token, metodo, sufijo, foto_id):
    r = _llamar(client, metodo, f"/admin/comercio/com-q/fotos/{foto_id}/diseno{sufijo}", admin_token)
    assert r.status_code in (404, 405), (foto_id, r.status_code, r.text)
    assert repo.photo_style_uses == []


@pytest.mark.parametrize("metodo,sufijo", RUTAS_FOTO)
def test_404_comercio_inexistente(client, repo, mundo, admin_token, metodo, sufijo):
    r = _llamar(client, metodo, f"/admin/comercio/nada/fotos/f1/diseno{sufijo}", admin_token)
    assert r.status_code == 404
    for m, ruta in (("POST", "/admin/comercio/nada/portada-diseno"), ("POST", "/admin/comercio/nada/portada-diseno/externa"),
                    ("PUT", "/admin/comercio/nada/portada-diseno"), ("GET", "/admin/comercio/nada/fotos-estilo")):
        assert _llamar(client, m, ruta, admin_token).status_code == 404


def test_404_comercio_sin_portada_es_400_claro(client, repo, mundo, admin_token):
    repo.comercios["com-q"]["portada_url"] = None
    r = client.post(COVER, headers=_h(admin_token))
    assert r.status_code == 400 and "portada" in r.json()["detail"]


def test_aislamiento_la_propuesta_de_un_comercio_no_cambia_la_del_otro(client, repo, mundo, admin_token):
    client.post("/admin/comercio/com-otro/fotos/fo1/diseno", headers=_h(admin_token))
    client.post(GAL, headers=_h(admin_token))
    assert repo.comercio_fotos[2]["diseno_propuesta_url"] and "/otro/" in repo.comercio_fotos[2]["diseno_propuesta_url"]
    assert "/local-q/" in repo.comercio_fotos[0]["diseno_propuesta_url"]
    # el estado de uno no lista las fotos ni los usos del otro
    e = client.get(ESTADO, headers=_h(admin_token)).json()
    assert [g["foto_id"] for g in e["gallery"]] == ["f1", "f2"]
    assert e["comercio"]["id"] == "com-q"


# ══════════════════════════════════════════════════════════════ §9 /externa

@pytest.mark.parametrize("formato,nombre,tipo", [("PNG", "a.png", "image/png"), ("JPEG", "a.jpg", "image/jpeg"),
                                                  ("WEBP", "a.webp", "image/webp")])
def test_externa_png_jpg_webp_validos_en_portada_y_galeria(client, repo, mundo, admin_token, formato, nombre, tipo):
    datos = _img(formato, 1200, 900, "purple")
    r = client.post(COVER_EXT, headers=_h(admin_token), files=_subida(datos, nombre, tipo))
    assert r.status_code == 200, r.text
    assert r.json()["proposal_method"] == "external" and _tam(r.json()["portada_diseno_propuesta_url"]) == (1600, 1000)
    r = client.post(GAL_EXT, headers=_h(admin_token), files=_subida(datos, nombre, tipo))
    assert r.status_code == 200, r.text
    assert r.json()["proposal_method"] == "external" and _tam(r.json()["proposal_url"]) == (1080, 1350)
    assert not repo.comercios["com-q"].get("portada_diseno_url") and repo.comercio_fotos[0].get("diseno_url") is None
    assert [u["method"] for u in repo.photo_style_uses] == ["external", "external"]
    assert all(u["cost_usd"] == 0 for u in repo.photo_style_uses)


def test_externa_decide_por_el_contenido_no_por_el_nombre_ni_el_content_type(client, repo, mundo, admin_token):
    png_disfrazado = _img("PNG", 1000, 1000)
    r = client.post(GAL_EXT, headers=_h(admin_token), files=_subida(png_disfrazado, "foto.jpg", "text/plain"))
    assert r.status_code == 200, r.text


def test_externa_png_con_transparencia_se_pinta_sobre_blanco_no_negro(client, repo, mundo, admin_token):
    datos = _img("PNG", 1200, 1200, (0, 0, 0, 0), modo="RGBA")           # todo transparente
    r = client.post(GAL_EXT, headers=_h(admin_token), files=_subida(datos, "t.png", "image/png"))
    assert r.status_code == 200, r.text
    img = Image.open(_ruta(r.json()["proposal_url"])).convert("RGB")
    centro = img.getpixel((540, 600))                                      # en medio de la tarjeta
    assert min(centro) > 235, f"lo transparente salió oscuro: {centro}"


def test_externa_no_deja_exif_ni_gps(client, repo, mundo, admin_token):
    im = Image.new("RGB", (1000, 1000), "teal")
    exif = Image.Exif()
    exif[0x010F] = "CamaraSecreta"
    exif[0x8825] = {1: "S", 2: (22.0, 0.0, 0.0)}
    buf = BytesIO()
    im.save(buf, format="JPEG", exif=exif)
    r = client.post(GAL_EXT, headers=_h(admin_token), files=_subida(buf.getvalue()))
    assert r.status_code == 200
    salida = Image.open(_ruta(r.json()["proposal_url"]))
    assert not salida.getexif() and b"CamaraSecreta" not in _ruta(r.json()["proposal_url"]).read_bytes()


@pytest.mark.parametrize("contenido,nombre", [
    (b"esto no es una imagen, es texto plano", "nota.jpg"),
    (b"%PDF-1.7\n1 0 obj<<>>endobj\n", "doc.png"),
    (b"<svg xmlns='http://www.w3.org/2000/svg' width='900' height='900'><script>alert(1)</script></svg>", "x.svg"),
    (b"GIF89a" + b"\x00" * 200, "a.gif"),
    (b"\xff\xd8\xff\xe0" + b"\x00" * 50, "truncado.jpg"),                  # encabezado JPEG sin cuerpo
    (b"MZ\x90\x00" + b"\x00" * 200, "virus.exe.jpg"),
    (_jpeg(900, 900)[:300], "cortado.jpg"),
])
def test_externa_archivo_que_no_es_imagen_es_400_en_español_sin_500(client, repo, mundo, admin_token, contenido, nombre):
    for ruta in (COVER_EXT, GAL_EXT):
        r = client.post(ruta, headers=_h(admin_token), files=_subida(contenido, nombre))
        assert r.status_code == 400, (ruta, r.status_code, r.text)
        d = r.json()["detail"]
        assert isinstance(d, str) and d and "PIL" not in d and "cannot identify" not in d and "Traceback" not in d
    assert repo.photo_style_uses == [] and _diseno_en_disco() == []
    assert not repo.comercios["com-q"].get("portada_diseno_propuesta_url")


def test_externa_gif_animado_o_tiff_no_se_aceptan(client, repo, mundo, admin_token):
    for fmt in ("GIF", "TIFF", "BMP"):
        r = client.post(GAL_EXT, headers=_h(admin_token), files=_subida(_img(fmt, 900, 900)))
        assert r.status_code == 400, (fmt, r.status_code)


def test_externa_mas_de_15_mb_es_413_y_no_escribe_nada(client, repo, mundo, admin_token):
    tope = 15 * 1024 * 1024
    for tam in (tope + 1, tope + 600 * 1024, 20 * 1024 * 1024):
        for ruta in (COVER_EXT, GAL_EXT):
            r = client.post(ruta, headers=_h(admin_token), files=_subida(b"\xff\xd8\xff" + b"0" * tam, "grande.jpg"))
            assert r.status_code == 413, (ruta, tam, r.status_code, r.text[:200])
    assert repo.photo_style_uses == [] and _diseno_en_disco() == []


def test_externa_justo_por_debajo_de_15_mb_llega_al_validador_y_da_400_no_413(client, repo, mundo, admin_token):
    r = client.post(GAL_EXT, headers=_h(admin_token), files=_subida(b"\xff\xd8\xff" + b"0" * (15 * 1024 * 1024 - 4096)))
    assert r.status_code == 400, (r.status_code, r.text[:200])


def test_externa_imagen_muy_chica_o_muy_angosta_es_400(client, repo, mundo, admin_token):
    for w, h in ((100, 100), (511, 900), (900, 511), (3000, 100), (50, 4000)):
        for ruta in (COVER_EXT, GAL_EXT):
            r = client.post(ruta, headers=_h(admin_token), files=_subida(_jpeg(w, h)))
            assert r.status_code == 400, (ruta, w, h, r.status_code, r.text)
            assert "chica" in r.json()["detail"] or "angosta" in r.json()["detail"]
    assert repo.photo_style_uses == []


def test_externa_bordes_exactos_512_y_4_a_1_se_aceptan_y_apenas_mas_no(client, repo, mundo, admin_token):
    assert client.post(GAL_EXT, headers=_h(admin_token), files=_subida(_jpeg(512, 512))).status_code == 200
    assert client.post(GAL_EXT, headers=_h(admin_token), files=_subida(_jpeg(2048, 512))).status_code == 200
    assert client.post(GAL_EXT, headers=_h(admin_token), files=_subida(_jpeg(2049, 512))).status_code == 400
    assert client.post(GAL_EXT, headers=_h(admin_token), files=_subida(_jpeg(511, 511))).status_code == 400


def test_externa_bomba_de_descompresion_es_400_no_500(client, repo, mundo, admin_token):
    bomba = _img("PNG", 8000, 8000, 0, modo="1")          # ~64 MP, unos KB comprimida: pasa los 15 MB, no los 40 MP
    assert len(bomba) < 15 * 1024 * 1024
    for ruta in (COVER_EXT, GAL_EXT):
        r = client.post(ruta, headers=_h(admin_token), files=_subida(bomba, "b.png", "image/png"))
        assert r.status_code == 400, (ruta, r.status_code, r.text[:200])


def test_externa_vacia_o_sin_campo_foto(client, repo, mundo, admin_token):
    r = client.post(GAL_EXT, headers=_h(admin_token), files=_subida(b""))
    assert r.status_code == 400
    r = client.post(GAL_EXT, headers=_h(admin_token), files={"otro": ("x.jpg", _jpeg(900, 900), "image/jpeg")})
    # la spec dice «400 sin foto»; FastAPI da 422 para un campo multipart que falta. Se acepta cualquiera de los dos,
    # lo que no se acepta es un 500 ni guardar algo.
    assert r.status_code in (400, 422), r.status_code
    assert repo.photo_style_uses == [] and _diseno_en_disco() == []


def test_externa_nombre_de_archivo_hostil_no_decide_donde_se_guarda(client, repo, mundo, admin_token):
    r = client.post(GAL_EXT, headers=_h(admin_token), files=_subida(_jpeg(900, 900), "../../../etc/passwd.jpg"))
    assert r.status_code == 200
    url = r.json()["proposal_url"]
    assert url.startswith(f"{BASE}/local-q/diseno-") and ".." not in url
    assert not list(Path(settings.fotos_dir).parent.glob("passwd*"))


def test_externa_no_llama_a_gemini_ni_cuenta_para_el_tope(client, repo, mundo, admin_token):
    for _ in range(3):
        assert client.post(GAL_EXT, headers=_h(admin_token), files=_subida(_jpeg(900, 900))).status_code == 200
    assert fe.usados_hoy(repo) == 0


# ══════════════════════════════════════════════════════════════ §9 el logo abajo a la derecha

def _caja_del_logo(monkeypatch, dibujar) -> tuple[int, int, int, int]:
    """Dónde cae el logo: se dibuja la pieza dos veces, con el logo real y con un logo transparente, y se mira dónde difieren."""
    con = dibujar()
    real = pd.logo_color
    monkeypatch.setattr(pd, "logo_color", lambda ancho: Image.new("RGBA", real(ancho).size, (0, 0, 0, 0)))
    sin = dibujar()
    monkeypatch.setattr(pd, "logo_color", real)
    caja = ImageChops.difference(con.convert("RGB"), sin.convert("RGB")).getbbox()
    assert caja is not None, "el logo no se dibujó"
    return caja


def test_logo_portada_abajo_a_la_derecha_y_ningun_texto_lo_pisa(monkeypatch):
    nombre = "Ferretería y Distribuidora Industrial Los Hermanos Rodríguez de la Frontera Sur " * 2
    dibujar = lambda: pd.dibujar_portada(Image.new("RGB", (1600, 1000), (200, 200, 200)), nombre[:120], "Ferretería", "Bermejo")
    x0, y0, x1, y1 = _caja_del_logo(monkeypatch, dibujar)
    assert x0 >= 800 and y0 >= 500                       # cuadrante inferior derecho, no arriba
    assert 1600 - x1 >= 32 and 1000 - y1 >= 32           # con margen del borde
    assert x1 > 1400 and y1 > 850                        # pegado a la esquina inferior derecha
    assert 250 <= x1 - x0 <= 310                         # ancho ~300 (§1)
    # el texto (nombre 120 caracteres + kick + ciudad) no entra en la caja del logo
    sin_logo_texto = pd.dibujar_portada(Image.new("RGB", (1600, 1000), (200, 200, 200)), "", None, None)
    con_texto = pd.dibujar_portada(Image.new("RGB", (1600, 1000), (200, 200, 200)), nombre[:120], "Ferretería", "Bermejo")
    real = pd.logo_color
    monkeypatch.setattr(pd, "logo_color", lambda ancho: Image.new("RGBA", real(ancho).size, (0, 0, 0, 0)))
    con_texto_sin_logo = pd.dibujar_portada(Image.new("RGB", (1600, 1000), (200, 200, 200)), nombre[:120], "Ferretería", "Bermejo")
    sin_logo = pd.dibujar_portada(Image.new("RGB", (1600, 1000), (200, 200, 200)), "", None, None)
    monkeypatch.setattr(pd, "logo_color", real)
    caja_texto = ImageChops.difference(con_texto_sin_logo.convert("RGB"), sin_logo.convert("RGB")).getbbox()
    assert caja_texto is not None and caja_texto[2] <= 1188 + 2, f"el texto pasa de x=1188: {caja_texto}"
    assert caja_texto[2] <= x0, "el texto invade la zona del logo"
    assert sin_logo_texto.size == con_texto.size == (1600, 1000)


def test_logo_galeria_abajo_a_la_derecha_en_el_pie(monkeypatch):
    dibujar = lambda: fe.plantilla_galeria(Image.new("RGB", (920, 1150), (120, 120, 120)))
    x0, y0, x1, y1 = _caja_del_logo(monkeypatch, dibujar)
    assert y0 >= 1206 and y1 <= 1350                      # dentro del pie
    assert x0 >= 540 and x1 <= 1080 - 40                  # derecha
    assert x1 - x0 == 260 or 250 <= x1 - x0 <= 262
    # la caja esperada sale de las constantes del pie (el logo va centrado en la franja 1206..1350)
    alto_logo = pd.logo_color(fe.PIE_LOGO_ANCHO).height
    y_esperado = (fe.PIE_Y0 + fe.PIE_Y1) // 2 - alto_logo // 2
    assert (x0, y0, x1, y1) == pytest.approx((fe.PIE_LOGO_X, y_esperado, fe.PIE_LOGO_X + fe.PIE_LOGO_ANCHO, y_esperado + alto_logo), abs=3)


def test_logo_el_archivo_guardado_por_el_endpoint_tiene_el_logo_en_la_esquina(client, repo, mundo, admin_token):
    """De punta a punta: el JPEG que queda en el disco tiene el logo (píxeles claros/dorados) abajo a la derecha y no arriba."""
    url = client.post(COVER, headers=_h(admin_token)).json()["portada_diseno_propuesta_url"]
    img = Image.open(_ruta(url)).convert("RGB")
    def contraste(caja):
        extremo = img.crop(caja)
        px = list(extremo.getdata())
        return max(sum(p) for p in px) - min(sum(p) for p in px)
    assert contraste((1236, 839, 1536, 936)) > 300       # el logo tiene colores muy distintos al fondo
    assert max(img.crop((1236, 20, 1536, 117)).resize((1, 1)).getpixel((0, 0))) < 255          # arriba no hay logo blanco


def test_galeria_no_lleva_textos_de_la_base(client, repo, mundo, admin_token):
    """El nombre del comercio no puede estar en la pieza de galería: dos comercios distintos con la misma foto dan la misma imagen."""
    repo.comercios["com-q"]["nombre"] = "AAAAAAAAAAAAAAAAAAAAAA"
    a = Image.open(_ruta(client.post(GAL, headers=_h(admin_token)).json()["proposal_url"])).convert("RGB")
    repo.comercios["com-q"]["nombre"] = "ZZZZ"
    b = Image.open(_ruta(client.post(GAL, headers=_h(admin_token)).json()["proposal_url"])).convert("RGB")
    assert ImageChops.difference(a, b).getbbox() is None


# ══════════════════════════════════════════════════════════════ §9 lectura remota de QA

class Red:
    def __init__(self, respuesta=None):
        self.pedidos: list[httpx.Request] = []
        self.respuesta = respuesta or (lambda req: httpx.Response(200, content=_jpeg(1200, 800)))

    def __call__(self, request):
        self.pedidos.append(request)
        return self.respuesta(request)


@pytest.fixture
def red(monkeypatch):
    r = Red()
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(r))
    return r


@pytest.fixture
def qa(monkeypatch):
    """QA: sirve en su dominio pero la base trae URLs de producción; la lectura remota está habilitada para PROD."""
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", PROD)


def _comercio_de_prod(repo, url_portada):
    repo.seed_comercio(id="com-prod", slug="de-prod", nombre="De Prod", whatsapp="59170000200", ciudad_id="ciu-1",
                       portada_url=url_portada)
    return "/admin/comercio/com-prod/portada-diseno"


def test_remoto_base_listada_se_lee_y_la_propuesta_se_guarda_en_el_disco_local(client, repo, qa, red, admin_token):
    ruta = _comercio_de_prod(repo, f"{PROD}/de-prod/p.jpg")
    r = client.post(ruta, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert [(p.method, str(p.url)) for p in red.pedidos] == [("GET", f"{PROD}/de-prod/p.jpg")]     # sólo lee
    url = r.json()["portada_diseno_propuesta_url"]
    assert url.startswith(BASE + "/de-prod/diseno-") and _en_disco(url)                            # lo armado, local
    assert not (Path(settings.fotos_dir) / "de-prod" / "p.jpg").exists()                           # no se copió el origen


def test_remoto_tambien_en_la_galeria(client, repo, qa, red, admin_token):
    _comercio_de_prod(repo, f"{PROD}/de-prod/p.jpg")
    repo.comercio_fotos.append({"id": "fp", "comercio_id": "com-prod", "url": f"{PROD}/de-prod/g.jpg", "thumb_url": None,
                                "orden": 0, "created_at": "2026-01-01T00:00:00+00:00"})
    r = client.post("/admin/comercio/com-prod/fotos/fp/diseno", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert len(red.pedidos) == 1 and _tam(r.json()["proposal_url"]) == (1080, 1350)


def test_remoto_base_no_listada_no_hace_red_y_da_400(client, repo, qa, red, admin_token):
    ruta = _comercio_de_prod(repo, "https://api.otro-sitio.com/fotos/de-prod/p.jpg")
    r = client.post(ruta, headers=_h(admin_token))
    assert r.status_code == 400 and "No se pudo leer" in r.json()["detail"]
    assert red.pedidos == [] and repo.photo_style_uses == []


@pytest.mark.parametrize("url", [
    f"{PROD}/de-prod/../otro/p.jpg", f"{PROD}/../p.jpg", f"{PROD}/de-prod/%2e%2e/p.jpg", f"{PROD}/de-prod/p.jpg?x=1",
    f"{PROD}/de-prod/p.jpg#frag", f"{PROD}/de-prod\\p.jpg", f"{PROD}/a/b/c.jpg", f"{PROD}/de-prod/p.png",
    f"{PROD}.evil.com/de-prod/p.jpg", f"{PROD}-evil/de-prod/p.jpg", "https://api.uruku.bo@evil.com/fotos/de-prod/p.jpg",
    f"{PROD}/de-prod/p.jpg\n", f"{PROD}/de-prod/\x00p.jpg", "http://api.uruku.bo/fotos/de-prod/p.jpg",
])
def test_remoto_rutas_y_urls_raras_no_salen_a_la_red(client, repo, qa, red, admin_token, url):
    ruta = _comercio_de_prod(repo, url)
    r = client.post(ruta, headers=_h(admin_token))
    assert r.status_code == 400, (url, r.status_code, r.text)
    assert red.pedidos == [], f"salió a la red con {url!r}: {[str(p.url) for p in red.pedidos]}"


def test_remoto_redireccion_no_se_sigue(client, repo, qa, monkeypatch, admin_token):
    r = Red(lambda req: httpx.Response(302, headers={"location": "https://evil.example/x.jpg"}))
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(r))
    ruta = _comercio_de_prod(repo, f"{PROD}/de-prod/p.jpg")
    resp = client.post(ruta, headers=_h(admin_token))
    assert resp.status_code == 400
    assert len(r.pedidos) == 1 and "evil" not in str(r.pedidos[0].url)


@pytest.mark.parametrize("estado", [301, 303, 307, 308, 404, 403, 500, 204])
def test_remoto_cualquier_cosa_que_no_sea_200_da_400(client, repo, qa, monkeypatch, admin_token, estado):
    r = Red(lambda req: httpx.Response(estado, headers={"location": "https://evil.example/x.jpg"}))
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(r))
    resp = client.post(_comercio_de_prod(repo, f"{PROD}/de-prod/p.jpg"), headers=_h(admin_token))
    assert resp.status_code == 400 and len(r.pedidos) == 1


def test_remoto_http_en_el_setting_se_ignora(client, repo, monkeypatch, red, admin_token):
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", "http://api.uruku.bo/fotos")
    assert fo.bases_remotas() == []
    ruta = _comercio_de_prod(repo, "http://api.uruku.bo/fotos/de-prod/p.jpg")
    assert client.post(ruta, headers=_h(admin_token)).status_code == 400
    assert red.pedidos == []


def test_remoto_mezcla_de_bases_solo_vale_la_https(monkeypatch):
    monkeypatch.setattr(settings, "fotos_lectura_remota_bases", "http://a.com/f, https://b.com/f/ ,ftp://c.com/f,https://, https://u:p@d.com/f")
    assert fo.bases_remotas() == ["https://b.com/f/"]


def test_remoto_setting_vacio_nunca_hay_red(client, repo, red, admin_token):
    ruta = _comercio_de_prod(repo, f"{PROD}/de-prod/p.jpg")          # QA sin setting: el comportamiento de producción
    assert client.post(ruta, headers=_h(admin_token)).status_code == 400
    assert red.pedidos == []


def test_remoto_si_esta_en_el_disco_no_hay_red(client, repo, qa, red, admin_token):
    guardar_foto_local("local-q/orig.jpg", _jpeg(1200, 800))
    repo.seed_comercio(id="com-q", slug="local-q", nombre="Q", whatsapp="59170000300", ciudad_id="ciu-1",
                       portada_url=f"{BASE}/local-q/orig.jpg")
    assert client.post(COVER, headers=_h(admin_token)).status_code == 200
    assert red.pedidos == []


def test_remoto_pasa_el_tope_de_bytes_da_none(monkeypatch, qa):
    grande = b"\xff\xd8" + b"0" * (fo.MAX_BYTES_FOTO + 1)
    for resp in (httpx.Response(200, content=grande),
                 httpx.Response(200, content=b"x", headers={"content-length": str(fo.MAX_BYTES_FOTO + 1)})):
        monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(lambda req, resp=resp: resp))
        assert fo.leer_foto_origen(f"{PROD}/de-prod/p.jpg") is None


def test_remoto_200_valido_da_los_bytes_y_vacio_da_none(monkeypatch, qa):
    datos = _jpeg()
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(lambda req: httpx.Response(200, content=datos)))
    assert fo.leer_foto_origen(f"{PROD}/de-prod/p.jpg") == datos
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(lambda req: httpx.Response(200, content=b"")))
    assert fo.leer_foto_origen(f"{PROD}/de-prod/p.jpg") is None


def test_remoto_un_error_de_red_no_tumba_el_pedido(client, repo, qa, monkeypatch, admin_token):
    def cae(req):
        raise httpx.ConnectError("sin conexión", request=req)
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(cae))
    r = client.post(_comercio_de_prod(repo, f"{PROD}/de-prod/p.jpg"), headers=_h(admin_token))
    assert r.status_code == 400, r.text           # sin conexión: 400 claro, nunca 500
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(
        lambda req: (_ for _ in ()).throw(httpx.ReadTimeout("lento", request=req))))
    assert client.post(_comercio_de_prod_2(repo), headers=_h(admin_token)).status_code == 400


def _comercio_de_prod_2(repo):
    repo.seed_comercio(id="com-prod2", slug="de-prod", nombre="De Prod 2", whatsapp="59170000201", ciudad_id="ciu-1",
                       portada_url=f"{PROD}/de-prod/p2.jpg")
    return "/admin/comercio/com-prod2/portada-diseno"


def test_remoto_el_contenido_remoto_que_no_es_imagen_da_400_y_no_se_guarda(client, repo, qa, monkeypatch, admin_token):
    monkeypatch.setattr(fo, "_TRANSPORTE", httpx.MockTransport(lambda req: httpx.Response(200, content=b"<html>hola</html>")))
    r = client.post(_comercio_de_prod(repo, f"{PROD}/de-prod/p.jpg"), headers=_h(admin_token))
    assert r.status_code == 400
    assert not (Path(settings.fotos_dir) / "de-prod").exists() or not list((Path(settings.fotos_dir) / "de-prod").glob("*"))


def test_remoto_sin_red_para_el_gemini_el_origen_remoto_tambien_va_a_gemini(client, repo, qa, monkeypatch, crepo, admin_token, red):
    _configurar(monkeypatch, crepo)
    g = Gemini()
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(g))
    r = client.post(_comercio_de_prod(repo, f"{PROD}/de-prod/p.jpg"), headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 200, r.text
    assert len(red.pedidos) == 1 and len(g.pedidos) == 1


# ══════════════════════════════════════════════════════════════ §9 vencimiento al reemplazar la foto

def _con_diseno_vigente(client, admin_token, repo, foto="f1"):
    ruta = f"/admin/comercio/com-q/fotos/{foto}/diseno"
    client.post(ruta, headers=_h(admin_token))
    client.put(ruta, headers=_h(admin_token))
    client.post(ruta, headers=_h(admin_token))             # y una propuesta nueva pendiente
    fila = next(f for f in repo.comercio_fotos if f["id"] == foto)
    assert fila["diseno_url"] and fila["diseno_propuesta_url"]
    return fila


def test_vencimiento_cambiar_el_url_de_la_foto_vacia_las_tres_columnas(repo, mundo, client, admin_token):
    fila = _con_diseno_vigente(client, admin_token, repo)
    repo.update_foto_comercio("f1", "com-q", {"url": f"{BASE}/local-q/g2.jpg"})
    assert fila["diseno_url"] is None and fila["diseno_thumb_url"] is None and fila["diseno_propuesta_url"] is None


def test_vencimiento_el_mismo_url_u_otros_campos_no_lo_vencen(repo, mundo, client, admin_token):
    fila = _con_diseno_vigente(client, admin_token, repo)
    d, p = fila["diseno_url"], fila["diseno_propuesta_url"]
    repo.update_foto_comercio("f1", "com-q", {"url": fila["url"], "orden": 9})
    repo.update_foto_comercio("f1", "com-q", {"thumb_url": f"{BASE}/local-q/otro_t.jpg"})
    assert fila["diseno_url"] == d and fila["diseno_propuesta_url"] == p


def test_vencimiento_el_intercambio_con_la_portada_suelta_los_archivos_y_respeta_las_originales(client, repo, mundo, admin_token):
    fila = _con_diseno_vigente(client, admin_token, repo)
    archivos = [fila["diseno_url"], fila["diseno_thumb_url"], fila["diseno_propuesta_url"], fe.miniatura_de(fila["diseno_propuesta_url"])]
    assert all(_en_disco(a) for a in archivos)
    orig_galeria, orig_portada = fila["url"], repo.comercios["com-q"]["portada_url"]

    r = client.put("/admin/comercio/com-q/portada", headers=_h(admin_token), json={"foto_id": "f1"})
    assert r.status_code == 200, r.text
    assert fila["url"] == orig_portada                                   # la fila ahora tiene la portada vieja
    assert fila["diseno_url"] is None and fila["diseno_thumb_url"] is None and fila["diseno_propuesta_url"] is None
    assert not any(_en_disco(a) for a in archivos)                       # los diseño-* del disco se soltaron
    assert _en_disco(orig_galeria) and _en_disco(orig_portada)           # las originales NUNCA se borran por un diseño
    assert repo.comercios["com-q"]["portada_url"] == orig_galeria


def test_vencimiento_borrar_la_foto_suelta_sus_disenos_pero_no_las_de_otras_fotos(client, repo, mundo, admin_token):
    f1 = _con_diseno_vigente(client, admin_token, repo, "f1")
    f2 = _con_diseno_vigente(client, admin_token, repo, "f2")
    de_f1 = [f1["diseno_url"], f1["diseno_thumb_url"], f1["diseno_propuesta_url"], fe.miniatura_de(f1["diseno_propuesta_url"])]
    de_f2 = [f2["diseno_url"], f2["diseno_thumb_url"], f2["diseno_propuesta_url"]]
    r = client.delete("/admin/comercio/com-q/fotos/f1", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert not any(_en_disco(a) for a in de_f1)
    assert all(_en_disco(a) for a in de_f2)                              # la otra foto conserva su diseño
    assert [f["id"] for f in repo.comercio_fotos if f["comercio_id"] == "com-q"] == ["f2"]


def test_vencimiento_el_diseno_de_galeria_no_vence_por_cambiar_el_nombre_el_rubro_o_la_ciudad(client, repo, mundo, admin_token):
    fila = _con_diseno_vigente(client, admin_token, repo)
    d = fila["diseno_url"]
    repo.update_comercio("com-q", {"nombre": "Otro Nombre", "ciudad_id": "ciu-2"}, None)
    assert fila["diseno_url"] == d and _en_disco(d)


def test_vencimiento_la_portada_de_diseno_si_vence_al_cambiar_el_nombre(client, repo, mundo, admin_token):
    client.post(COVER, headers=_h(admin_token))
    client.put(COVER, headers=_h(admin_token))
    assert repo.comercios["com-q"]["portada_diseno_url"]
    repo.update_comercio("com-q", {"nombre": "Nombre Nuevo SRL"}, None)
    assert not repo.comercios["com-q"].get("portada_diseno_url")


def test_vencimiento_repo_real_update_foto_comercio_vacia_en_la_misma_escritura():
    """`SupabaseRepo.update_foto_comercio` (lo que corre en producción; el FakeRepo sólo lo espeja): lee la fila previa y
    manda UN update con el patch del usuario + las tres columnas en None."""
    from app.db.repository import SupabaseRepo

    class Q:
        def __init__(self, db, tabla):
            self.db, self.tabla, self.op, self.datos, self.filtros = db, tabla, None, None, []

        def select(self, cols, **kw):
            self.op = "select"
            return self

        def update(self, patch):
            self.op, self.datos = "update", patch
            return self

        def eq(self, c, v):
            self.filtros.append((c, v))
            return self

        def limit(self, n):
            return self

        def execute(self):
            self.db.llamadas.append((self.op, self.tabla, self.datos, list(self.filtros)))
            if self.op == "select":
                return type("R", (), {"data": [self.db.fila]})
            return type("R", (), {"data": [{**self.db.fila, **self.datos}]})

    class Db:
        fila = {"id": "f1", "url": "A", "diseno_url": "d", "diseno_thumb_url": "dt", "diseno_propuesta_url": None}

        def __init__(self):
            self.llamadas = []

        def table(self, t):
            return Q(self, t)

    db = Db()
    repo = SupabaseRepo.__new__(SupabaseRepo)
    repo._db = db
    repo.update_foto_comercio("f1", "c1", {"url": "B", "orden": 3})
    updates = [c for c in db.llamadas if c[0] == "update"]
    assert len(updates) == 1
    assert updates[0][2] == {"diseno_url": None, "diseno_thumb_url": None, "diseno_propuesta_url": None, "url": "B", "orden": 3}
    assert ("comercio_id", "c1") in updates[0][3]                        # sigue acotado al comercio

    db.llamadas.clear()
    repo.update_foto_comercio("f1", "c1", {"url": "A"})                  # el mismo url: no vence
    assert [c[2] for c in db.llamadas if c[0] == "update"] == [{"url": "A"}]
    db.llamadas.clear()
    repo.update_foto_comercio("f1", "c1", {"diseno_propuesta_url": "p"})  # sin url: ni siquiera lee
    assert [c[0] for c in db.llamadas] == ["update"]


# ══════════════════════════════════════════════════════════════ §9 permisos

def _token(*permisos):
    return auth.make_token("equipo@bermejolive.com", rol="moderador", permisos=list(permisos))


TODAS_LAS_RUTAS = [
    ("GET", ESTADO), ("POST", COVER), ("POST", COVER_EXT), ("PUT", COVER), ("DELETE", COVER + "/propuesta"), ("DELETE", COVER),
    ("POST", GAL), ("POST", GAL_EXT), ("PUT", GAL), ("DELETE", GAL + "/propuesta"), ("DELETE", GAL),
]


@pytest.mark.parametrize("metodo,ruta", TODAS_LAS_RUTAS)
def test_permiso_sin_comercios_editar_es_403_y_no_escribe(client, repo, mundo, metodo, ruta):
    antes = (json.dumps(repo.comercio_fotos, sort_keys=True), dict(repo.comercios["com-q"]))
    for permisos in ([], ["moderar"], ["pagos"], ["comercios.cargar", "contenido", "ayuda"]):
        r = _llamar(client, metodo, ruta, _token(*permisos))
        assert r.status_code == 403, (permisos, r.status_code, r.text)
    assert (json.dumps(repo.comercio_fotos, sort_keys=True), dict(repo.comercios["com-q"])) == antes
    assert repo.photo_style_uses == [] and _diseno_en_disco() == []


@pytest.mark.parametrize("metodo,ruta", TODAS_LAS_RUTAS)
def test_permiso_sin_token_o_con_token_de_comercio_o_agente(client, repo, mundo, metodo, ruta):
    for token in (None, "basura", comercio_token(comercio_id="com-q"), auth.make_agente_token("a@x.com")):
        kw = {"files": _subida(_jpeg(900, 900))} if ruta.endswith("/externa") else {}
        if token:
            kw["headers"] = _h(token)
        r = client.request(metodo, ruta, **kw)
        assert r.status_code in (401, 403), (token, r.status_code)
    assert repo.photo_style_uses == [] and _diseno_en_disco() == []


@pytest.mark.parametrize("metodo,ruta", TODAS_LAS_RUTAS)
def test_permiso_comercios_editar_alcanza_para_las_rutas_del_comercio_pero_no_para_pagos(client, repo, mundo, metodo, ruta):
    r = _llamar(client, metodo, ruta, _token("comercios.editar"))
    assert r.status_code not in (401, 403), (metodo, ruta, r.status_code, r.text)


def test_permiso_usos_exige_pagos_y_comercios_editar_no_alcanza(client, repo, mundo):
    assert client.get(USOS).status_code in (401, 403)
    assert client.get(USOS, headers=_h(_token("comercios.editar", "moderar", "contenido"))).status_code == 403
    assert client.get(USOS, headers=_h(_token())).status_code == 403
    assert client.get(USOS, headers=_h(comercio_token(comercio_id="com-q"))).status_code in (401, 403)
    assert client.get(USOS, headers=_h(auth.make_agente_token("a@x.com"))).status_code in (401, 403)
    ok = client.get(USOS, headers=_h(_token("pagos")))
    assert ok.status_code == 200 and set(ok.json()) == {"desde", "hasta", "images", "cost_usd", "by_merchant"}


def test_permiso_pagos_solo_no_abre_las_rutas_de_fotos(client, repo, mundo):
    assert client.get(ESTADO, headers=_h(_token("pagos"))).status_code == 403


def test_permiso_el_admin_tiene_las_dos_cosas(client, repo, mundo, admin_token):
    assert client.get(USOS, headers=_h(admin_token)).status_code == 200
    assert client.get(ESTADO, headers=_h(admin_token)).status_code == 200


def test_permiso_un_token_viejo_o_alterado_no_pasa(client, repo, mundo):
    bueno = _token("comercios.editar")
    alterado = bueno[:-3] + ("AAA" if not bueno.endswith("AAA") else "BBB")
    assert client.get(ESTADO, headers=_h(alterado)).status_code in (401, 403)


# ══════════════════════════════════════════════════════════════ §5 otros códigos y robustez

def test_409_ocupado_responde_el_texto_de_la_spec_no_registra_y_el_lock_no_queda_tomado(client, repo, mundo, admin_token, monkeypatch):
    monkeypatch.setattr(fe, "ESPERA_TRANSFORMAR", 0.2)
    assert fe._TRANSFORMAR.acquire(timeout=1)
    try:
        for ruta in (COVER, GAL):
            r = client.post(ruta, headers=_h(admin_token))
            assert r.status_code == 409 and r.json()["detail"] == "Ya se está armando otra foto, probá en unos segundos"
        r = client.post(GAL_EXT, headers=_h(admin_token), files=_subida(_jpeg(900, 900)))
        assert r.status_code == 409
    finally:
        fe._TRANSFORMAR.release()
    assert repo.photo_style_uses == [] and _diseno_en_disco() == []
    assert client.post(GAL, headers=_h(admin_token)).status_code == 200        # liberado: anda


@pytest.mark.parametrize("falla", ["imagen_invalida", "gemini_500", "gemini_sin_imagen", "gemini_timeout"])
def test_el_lock_se_libera_aunque_el_pedido_falle(client, repo, mundo, admin_token, monkeypatch, crepo, falla):
    _configurar(monkeypatch, crepo)
    def gem(req):
        if falla == "gemini_500":
            return httpx.Response(500, json={"error": {"message": "x"}})
        if falla == "gemini_sin_imagen":
            return httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": "no puedo"}]}}]})
        raise httpx.ReadTimeout("t", request=req)
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(gem))
    if falla == "imagen_invalida":
        assert client.post(GAL_EXT, headers=_h(admin_token), files=_subida(b"no soy imagen")).status_code == 400
    else:
        r = client.post(GAL, headers=_h(admin_token), json={"method": "gemini"})
        assert r.status_code in (502, 504), r.text
    assert fe._TRANSFORMAR.acquire(timeout=0.2)
    fe._TRANSFORMAR.release()


def test_502_y_504_dejan_su_fila_con_el_costo_correcto_y_sin_propuesta(client, repo, mundo, admin_token, monkeypatch, crepo):
    _configurar(monkeypatch, crepo)
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(lambda req: httpx.Response(503, json={"error": {"message": f"key={CLAVE}"}})))
    r = client.post(GAL, headers=_h(admin_token), json={"method": "gemini"})
    assert r.status_code == 502
    assert CLAVE not in r.text and CLAVE not in json.dumps(repo.photo_style_uses)
    [u] = repo.photo_style_uses
    assert u["result"] == "error" and u["cost_usd"] == 0 and u["result_url"] is None
    assert repo.comercio_fotos[0].get("diseno_propuesta_url") is None and _diseno_en_disco() == []

    def lento(req):
        raise httpx.ReadTimeout("lento", request=req)
    monkeypatch.setattr(ge, "_TRANSPORTE", httpx.MockTransport(lento))
    assert client.post(GAL, headers=_h(admin_token), json={"method": "gemini"}).status_code == 504
    assert [x["result"] for x in repo.photo_style_uses] == ["error", "timeout"]
    assert repo.photo_style_uses[1]["cost_usd"] == COSTO


def test_el_pedido_a_gemini_no_lleva_datos_del_comercio_ni_la_clave_en_la_url(client, repo, mundo, admin_token, gemini):
    client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    pedido = gemini.pedidos[-1]
    texto = pedido.content.decode()
    for secreto in ("Ferretería QA", "Ferreter", "59170000100", "ciu-1", "local-q", "com-q"):
        assert secreto not in texto, f"el pedido a Gemini lleva {secreto!r}"
    assert CLAVE not in str(pedido.url) and CLAVE in pedido.headers.get("x-goog-api-key", CLAVE)
    cuerpo = json.loads(pedido.content)
    assert cuerpo["generationConfig"]["imageConfig"]["aspectRatio"] == "3:2"


def test_usos_resumen_cuenta_solo_lo_cobrado_y_valida_las_fechas(client, repo, mundo, admin_token, gemini):
    client.post(COVER, headers=_h(admin_token), json={"method": "gemini"})
    client.post(GAL, headers=_h(admin_token), json={"method": "gemini"})
    client.post(COVER, headers=_h(admin_token))                                  # free: costo 0, no suma
    j = client.get(USOS, headers=_h(admin_token)).json()
    assert j["images"] == 2 and j["cost_usd"] == pytest.approx(2 * COSTO, abs=1e-4)
    assert [m["comercio_id"] for m in j["by_merchant"]] == ["com-q"]
    for q in ("desde=2026-13-45", "desde=hoy", "desde=2026-05-10&hasta=2026-05-01", "desde=2020-01-01&hasta=2026-11-01"):
        r = client.get(f"{USOS}?{q}", headers=_h(admin_token))
        assert r.status_code == 400 and isinstance(r.json()["detail"], str), (q, r.status_code)
    assert client.get(USOS + "?desde=2030-01-01&hasta=2030-01-02", headers=_h(admin_token)).json()["images"] == 0


def test_get_estado_no_filtra_la_clave_ni_el_prompt_con_datos_del_comercio(client, repo, mundo, admin_token, gemini):
    texto = client.get(ESTADO, headers=_h(admin_token)).text
    assert CLAVE not in texto and "x-goog" not in texto.lower()
