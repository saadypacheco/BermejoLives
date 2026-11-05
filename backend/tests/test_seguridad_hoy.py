"""Lote «Hoy» de la revisión de seguridad de noviembre (código).

Cubre: freno de arranque con secretos de fábrica en producción, la clave de Gemini en
cabecera (nunca en la URL ni en los registros), límites por IP en los endpoints públicos
(también GET) y tope de tamaño en sus cuerpos, el permiso para aprobar un cambio de
número, la API sin /docs en producción, el webhook cerrado por defecto y el health sin
el texto de las excepciones.
"""
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main as main_mod
from app.core import auth, gemini
from app.core.config import (
    Settings, exigir_config_produccion, problemas_config_produccion, settings,
)

APP = Path(__file__).resolve().parents[1] / "app"

FUERTE = "x" * 40
CLAVE_OK = "Abcdefgh1234"


def _cfg(**kw) -> Settings:
    base = dict(environment="production", jwt_secret=FUERTE, admin_password=CLAVE_OK,
                agente_password=CLAVE_OK + "a", publicador_password=CLAVE_OK + "b")
    base.update(kw)
    return Settings(_env_file=None, **base)


# ═════════════════════════════ A-06 · se niega a arrancar con secretos de fábrica

def test_produccion_con_secretos_fuertes_arranca():
    cfg = _cfg()
    assert problemas_config_produccion(cfg) == []
    exigir_config_produccion(cfg)          # no lanza


def test_produccion_con_todo_de_fabrica_no_arranca():
    cfg = Settings(_env_file=None, environment="production")
    problemas = problemas_config_produccion(cfg)
    assert len(problemas) == 4
    with pytest.raises(RuntimeError) as e:
        exigir_config_produccion(cfg)
    msg = str(e.value)
    for nombre in ("JWT_SECRET", "ADMIN_PASSWORD", "AGENTE_PASSWORD", "PUBLICADOR_PASSWORD"):
        assert nombre in msg
    # Nunca imprime los valores.
    for valor in ("bermejo1234", "campo1234", "publicar1234", "bermejo-dev-secret"):
        assert valor not in msg


@pytest.mark.parametrize("campo,valor", [
    ("jwt_secret", "bermejo-dev-secret-change-in-prod"),
    ("jwt_secret", "corto"),
    ("jwt_secret", "CAMBIAR_openssl_rand_hex_32"),
    ("admin_password", "CAMBIAR"),
    ("admin_password", "bermejo1234"),
    ("admin_password", "onceletras1"),              # 11 < 12
    ("agente_password", "campo1234"),
    ("agente_password", "otra-cambiar-123456"),     # trae «cambiar»
    ("publicador_password", "publicar1234"),
    ("publicador_password", ""),
])
def test_cada_secreto_malo_se_detecta(campo, valor):
    assert problemas_config_produccion(_cfg(**{campo: valor}))


def test_fuera_de_produccion_no_frena_nada():
    for amb in ("development", "qa", "staging"):
        exigir_config_produccion(Settings(_env_file=None, environment=amb))


def test_el_arranque_del_backend_falla_en_produccion_con_valores_de_fabrica(monkeypatch):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(settings, "jwt_secret", "bermejo-dev-secret-change-in-prod")
    with pytest.raises(RuntimeError):
        with TestClient(main_mod.app):
            pass


def test_el_ejemplo_de_produccion_tiene_las_claves_del_publicador():
    ejemplo = (Path(__file__).resolve().parents[1] / ".env.prod.example").read_text(encoding="utf-8")
    assert re.search(r"^PUBLICADOR_EMAIL=", ejemplo, re.M)
    assert re.search(r"^PUBLICADOR_PASSWORD=", ejemplo, re.M)


# ═════════════════════════════ M-04 · la clave de Gemini va en la cabecera

LLAVE = "AIzaSyFAKE-clave-de-prueba-123"


class _Resp:
    status_code = 200

    def __init__(self, texto='{"rubro_slugs": ["a"], "descripcion": "d", "rubro_slug": "a", '
                              '"veredicto": "aprobar", "motivo": "m", "confianza": 0.9, "rubros": ["a"]}'):
        self._t = texto
        self.text = texto

    def raise_for_status(self):
        pass

    def json(self):
        return {"candidates": [{"content": {"parts": [{"text": self._t}]}}]}


@pytest.fixture
def capturas(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", LLAVE)
    visto: list[dict] = []

    def post(url, **kw):
        visto.append({"url": url, "headers": kw.get("headers") or {}})
        return _Resp()

    for modulo in ("app.services.clasificador", "app.services.asistente", "app.services.vision"):
        monkeypatch.setattr(f"{modulo}.httpx.post", post)
    return visto


def _sin_clave_en_url(visto):
    assert visto, "no se hizo ninguna llamada"
    for v in visto:
        assert "key=" not in v["url"] and LLAVE not in v["url"]
        assert v["headers"].get("x-goog-api-key") == LLAVE


RUBROS = [{"slug": "a", "nombre": "A"}]


def test_clasificador_manda_la_clave_en_cabecera(capturas):
    from app.services import clasificador as c
    c.clasificar("t", "d", RUBROS)
    c.moderar_publicacion("t", "d")
    c.generar_texto_comercio("n", "q", RUBROS)
    c.sugerir_rubros("algo", RUBROS)
    c.sugerir_rubros_explicado("n", "t", RUBROS)
    assert len(capturas) == 5
    _sin_clave_en_url(capturas)


def test_asistente_manda_la_clave_en_cabecera(capturas):
    from app.services import asistente
    asistente._gemini("hola")
    _sin_clave_en_url(capturas)


def test_vision_sinonimos_y_captions_mandan_la_clave_en_cabecera(capturas, monkeypatch):
    from app.services import content_captions, sinonimos, vision
    monkeypatch.setattr(vision.time, "sleep", lambda s: None)
    sinonimos.gemini_post("p")
    content_captions.llamar_gemini_partes([{"text": "x"}])
    _sin_clave_en_url(capturas)
    assert len(capturas) == 2


def test_ningun_archivo_arma_la_url_de_gemini_con_la_clave():
    for f in APP.rglob("*.py"):
        texto = f.read_text(encoding="utf-8")
        if f.name == "gemini.py":
            continue
        assert "?key=" not in texto, f"{f.relative_to(APP)}: la clave de Gemini va en la cabecera"


def test_sin_secretos_limpia_url_cabecera_y_clave_suelta(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", LLAVE)
    assert LLAVE not in gemini.sin_secretos(f"404 for url https://x/y:generateContent?key={LLAVE}")
    assert LLAVE not in gemini.sin_secretos(f"headers {{'x-goog-api-key': '{LLAVE}'}}")
    assert LLAVE not in gemini.sin_secretos(f"error con {LLAVE} adentro")
    assert gemini.sin_secretos("") == ""


def test_los_errores_del_clasificador_se_registran_sin_la_clave(monkeypatch):
    from app.services import clasificador as c
    monkeypatch.setattr(settings, "gemini_api_key", LLAVE)

    def explota(url, **kw):
        raise RuntimeError(f"fallo en {url}?key={LLAVE} con {LLAVE}")

    monkeypatch.setattr(c.httpx, "post", explota)
    registros: list[str] = []

    class _Log:
        def warning(self, evento, **kw):
            registros.append(repr(kw))

    monkeypatch.setattr(c, "logger", _Log())
    c.clasificar("t", "d", RUBROS)
    c.moderar_publicacion("t", "d")
    c.generar_texto_comercio("n", "q", RUBROS)
    c.sugerir_rubros("algo", RUBROS)
    c.sugerir_rubros_explicado("n", "t", RUBROS)
    assert len(registros) == 5
    assert all(LLAVE not in r for r in registros)


# ═════════════════════════════ M-03 · límites por IP en los endpoints públicos

def test_las_reglas_cubren_los_endpoints_publicos():
    r = main_mod._regla_de_limite
    for ruta in ("/lead", "/visita", "/busquedas/log", "/reclamos", "/comercio/generar-descripcion"):
        assert r("POST", ruta), ruta
    assert r("POST", "/lead/abc/respondio")[0] == "/lead/"          # contador aparte del click
    assert r("POST", "/comercio/abc-123/solicitar-cambio-numero")
    assert r("GET", "/auth/comercio/recuperar/estado")
    # No se limitan por error: otros GET, otros POST.
    assert r("GET", "/comercio/buscar") is None
    assert r("GET", "/lead") is None
    assert r("POST", "/comercio/abc/otra-cosa") is None


def _llamar_hasta_429(monkeypatch, regla, hacer, tope=3):
    """Baja el tope de `regla` y llama hasta que corta. Devuelve los estados vistos."""
    prefijo, tabla = regla
    monkeypatch.setitem(tabla, prefijo, tope)
    return [hacer().status_code for _ in range(tope + 1)]


def test_reclamos_corta_a_la_ip_que_se_pasa(client, monkeypatch):
    estados = _llamar_hasta_429(monkeypatch, ("/reclamos", main_mod._RL_RULES),
                                lambda: client.post("/reclamos", json={"mensaje": "hola"}))
    assert estados == [200, 200, 200, 429]


def test_lead_visita_y_busquedas_cortan(client, monkeypatch):
    assert _llamar_hasta_429(monkeypatch, ("/visita", main_mod._RL_RULES),
                             lambda: client.post("/visita", json={"ruta": "/", "sesion": "abcdef"}))[-1] == 429
    assert _llamar_hasta_429(monkeypatch, ("/busquedas/log", main_mod._RL_RULES),
                             lambda: client.post("/busquedas/log", json={"query": "pan"}))[-1] == 429
    assert _llamar_hasta_429(monkeypatch, ("/lead", main_mod._RL_RULES),
                             lambda: client.post("/lead", json={"comercio_id": "c1"}))[-1] == 429


def test_generar_descripcion_corta(client, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    cuerpo = {"nombre": "n", "que_vende": "pan", "rubros": []}
    estados = _llamar_hasta_429(monkeypatch, ("/comercio/generar-descripcion", main_mod._RL_RULES),
                                lambda: client.post("/comercio/generar-descripcion", json=cuerpo))
    assert estados[-1] == 429 and estados[0] == 200


def test_solicitar_cambio_numero_corta(client, monkeypatch):
    estados = _llamar_hasta_429(
        monkeypatch, (("/comercio/", "/solicitar-cambio-numero"), main_mod._RL_RULES_SUFIJO),
        lambda: client.post("/comercio/no-existe/solicitar-cambio-numero", data={"whatsapp_nuevo": "1"}))
    assert estados[:3] == [422, 422, 422] and estados[-1] == 429


def test_recuperar_estado_get_corta(client, monkeypatch):
    estados = _llamar_hasta_429(
        monkeypatch, ("/auth/comercio/recuperar/estado", main_mod._RL_RULES_GET),
        lambda: client.get("/auth/comercio/recuperar/estado", params={"whatsapp": "70000000", "codigo": "123456"}))
    assert estados[:3] == [200, 200, 200] and estados[-1] == 429


def test_el_polling_normal_de_la_espera_no_se_corta(client):
    # El sitio consulta cada 2,5 s: 24 por minuto, por debajo del tope.
    for _ in range(30):
        r = client.get("/auth/comercio/recuperar/estado", params={"whatsapp": "70000000", "codigo": "123456"})
        assert r.status_code == 200


def test_otra_ip_no_comparte_el_contador(client, monkeypatch):
    monkeypatch.setitem(main_mod._RL_RULES, "/reclamos", 1)
    h1, h2 = {"X-Forwarded-For": "1.1.1.1"}, {"X-Forwarded-For": "2.2.2.2"}
    assert client.post("/reclamos", json={"mensaje": "a"}, headers=h1).status_code == 200
    assert client.post("/reclamos", json={"mensaje": "a"}, headers=h1).status_code == 429
    assert client.post("/reclamos", json={"mensaje": "a"}, headers=h2).status_code == 200


def test_los_topes_por_defecto_son_los_documentados():
    assert main_mod._RL_RULES["/lead"] == 60 and main_mod._RL_RULES["/lead/"] == 20
    assert main_mod._RL_RULES["/visita"] == 120
    assert main_mod._RL_RULES["/busquedas/log"] == 60
    assert main_mod._RL_RULES["/reclamos"] == 5
    assert main_mod._RL_RULES["/comercio/generar-descripcion"] == 10
    assert main_mod._RL_RULES_SUFIJO[("/comercio/", "/solicitar-cambio-numero")] == 5
    assert main_mod._RL_RULES_GET["/auth/comercio/recuperar/estado"] == 60


def test_los_cuerpos_publicos_tienen_tope_de_tamanio(client):
    assert client.post("/busquedas/log", json={"query": "a" * 201}).status_code == 422
    assert client.post("/busquedas/log", json={"query": "ok", "comercios": ["x"] * 101}).status_code == 422
    assert client.post("/reclamos", json={"mensaje": "a" * 2001}).status_code == 422
    assert client.post("/reclamos", json={"mensaje": "ok", "nombre": "n" * 121}).status_code == 422
    assert client.post("/lead", json={"comercio_id": "c" * 65}).status_code == 422
    assert client.post("/visita", json={"ruta": "/", "sesion": "abcdef", "ciudad": "c" * 61}).status_code == 422
    assert client.post("/comercio/generar-descripcion",
                       json={"nombre": "n", "que_vende": "q" * 1501, "rubros": []}).status_code == 422
    assert client.post("/comercio/generar-descripcion",
                       json={"nombre": "n" * 201, "que_vende": "q", "rubros": []}).status_code == 422
    assert client.post("/comercio/generar-descripcion",
                       json={"nombre": "n", "que_vende": "q", "rubros": [{}] * 101}).status_code == 422
    assert client.post("/comercio/x/solicitar-cambio-numero",
                       data={"whatsapp_nuevo": "1" * 41, "lat": "0", "lng": "0"},
                       files={"foto": ("f.jpg", b"x", "image/jpeg")}).status_code == 422
    assert client.get("/auth/comercio/recuperar/estado",
                      params={"whatsapp": "1" * 41, "codigo": "1"}).status_code == 422


# ═════════════════════════════ M-01 · aprobar un cambio de número pide comercios.cuenta

def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _solicitud(repo):
    ciudad = repo.get_ciudad_id("bermejo")
    repo.seed_comercio(id="victima", nombre="Ferreteria", slug="ferr", whatsapp="59170123456",
                       activo=True, ciudad_id=ciudad, cargado_por=None)
    return repo.crear_solicitud_cambio_numero({"comercio_id": "victima", "whatsapp_nuevo": "70004444",
                                               "lat": -22.7, "lng": -64.3})


def test_aprobar_cambio_de_numero_sin_el_permiso_da_403(client, repo):
    sol = _solicitud(repo)
    for permisos in (["moderar", "comercios.editar"], ["panel"], []):
        tok = auth.make_token("poco@uruku.bo", rol="x", permisos=permisos)
        r = client.post(f"/admin/solicitudes-cambio-numero/{sol['id']}/aprobar", headers=_h(tok))
        assert r.status_code == 403, permisos
    assert repo.comercios["victima"]["whatsapp"] == "59170123456"


def test_aprobar_cambio_de_numero_con_el_permiso_anda(client, repo):
    sol = _solicitud(repo)
    tok = auth.make_token("cuentas@uruku.bo", rol="x", permisos=["comercios.cuenta"])
    r = client.post(f"/admin/solicitudes-cambio-numero/{sol['id']}/aprobar", headers=_h(tok))
    assert r.status_code == 200, r.text


def test_el_permiso_comercios_cuenta_existe_en_el_catalogo_y_en_el_moderador():
    from app.core.permisos import ROLES_BASE, TODO
    catalogo = (APP / "core" / "permisos.py").read_text(encoding="utf-8")
    assert '"comercios.cuenta"' in catalogo
    assert "comercios.cuenta" in ROLES_BASE["moderador"]["permisos"]
    assert ROLES_BASE["admin"]["permisos"] == [TODO]
    assert "comercios.cuenta" not in ROLES_BASE["publicador"]["permisos"]


# ═════════════════════════════ B-03 · sin /docs en producción, health sin excepciones

def test_en_produccion_no_se_publica_el_mapa_de_la_api():
    from fastapi import FastAPI

    prod = FastAPI(**main_mod._opciones_docs(True))
    with TestClient(prod) as c:
        for ruta in ("/docs", "/redoc", "/openapi.json"):
            assert c.get(ruta).status_code == 404, ruta
    dev = FastAPI(**main_mod._opciones_docs(False))
    with TestClient(dev) as c:
        assert c.get("/openapi.json").status_code == 200
    # Y la app real lo usa con el ambiente configurado.
    assert 'settings.environment == "production"' in (APP / "main.py").read_text(encoding="utf-8")


def test_en_desarrollo_se_ven_los_docs(client):
    assert client.get("/openapi.json").status_code == 200


def test_el_health_no_devuelve_el_texto_de_la_excepcion(client, monkeypatch):
    from app.api import health

    def explota():
        raise RuntimeError("postgres://usuario:SECRETO@host/db no responde")

    monkeypatch.setattr(health, "get_supabase", explota)
    r = client.get("/health")
    assert r.status_code == 200
    cuerpo = r.text
    assert "SECRETO" not in cuerpo and "postgres://" not in cuerpo
    assert r.json()["status"] == "degraded"
    assert r.json()["base"] == "error: RuntimeError"


# ═════════════════════════════ B-04 · el webhook sin secreto sólo abre en development

@pytest.mark.parametrize("ambiente,abre", [("development", True), ("production", False),
                                           ("qa", False), ("staging", False), ("", False)])
def test_webhook_sin_secreto_abre_solo_en_development(monkeypatch, ambiente, abre):
    from app.api import webhook
    monkeypatch.setattr(settings, "webhook_secret", "")
    monkeypatch.setattr(settings, "environment", ambiente)
    assert webhook._valid_signature(b"{}", None) is abre
    assert webhook._valid_signature(b"{}", "cualquiera") is abre


def test_webhook_sin_secreto_en_qa_rechaza_con_401(client, monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "")
    monkeypatch.setattr(settings, "environment", "qa")
    r = client.post("/ingest/webhook", json={"event": "algo.raro"})
    assert r.status_code == 401
