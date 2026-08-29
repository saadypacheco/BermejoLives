"""Rutas que quedaban sin ninguna prueba.

Dos grupos, y el segundo es el que más importa: los endpoints que dependen de un
servicio externo (Gemini, Whisper) tienen que degradar en silencio y NO romper el
flujo cuando la key no está. En producción estuvieron meses sin GEMINI_API_KEY y
nadie se enteró — el clasificador devolvía vacío y el alta caía a "Otros".
"""
import hashlib
import hmac

import pytest

from app.core.config import settings


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ═════════════════════════════════════════════ login del comercio
def test_login_de_comercio_con_credenciales_malas(client, repo):
    r = client.post("/auth/comercio/login", json={"email": "x@y.com", "password": "mala"})
    assert r.status_code == 401


def test_login_de_comercio_ok(client, repo):
    from app.core import auth
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True)
    repo.crear_comercio_usuario({
        "comercio_id": c["id"], "email": "duenio@x.com", "nombre": "Pepe",
        "password_hash": auth.hash_password("secreta123"),
    })

    r = client.post("/auth/comercio/login",
                    json={"email": "duenio@x.com", "password": "secreta123"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"]
    assert body["comercio"]["slug"] == "x"


# ═══════════════════════════════════ publicaciones del comercio logueado
def test_mis_publicaciones_solo_devuelve_las_propias(client, repo):
    from tests.conftest import comercio_token
    mio = repo.seed_comercio(id="com-mio", slug="mio", nombre="Mío", activo=True)
    otro = repo.seed_comercio(id="com-otro", slug="otro", nombre="Otro", activo=True)
    repo.publicaciones.append({"id": "p1", "comercio_id": mio["id"], "titulo": "mía", "activo": True})
    repo.publicaciones.append({"id": "p2", "comercio_id": otro["id"], "titulo": "ajena", "activo": True})

    r = client.get("/comercio/mis-publicaciones",
                   headers=_h(comercio_token("com-mio", "duenio@x.com")))
    assert r.status_code == 200, r.text
    titulos = [p["titulo"] for p in r.json()["items"]]
    assert titulos == ["mía"], "un comercio no puede ver publicaciones de otro"


def test_mis_publicaciones_requiere_login(client, repo):
    assert client.get("/comercio/mis-publicaciones").status_code in (401, 403)


# ═══════════════════════════════════════════════ webhook de WhatsApp
def _evento(wamid="wa-x"):
    return {"event": "message", "session": "obs@c.us",
            "payload": {"id": wamid, "from": "59170000009@c.us", "fromMe": False,
                        "body": "Oferta zapatillas", "type": "text", "timestamp": 1700000000}}


def test_webhook_rechaza_firma_invalida(client, repo, monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "s3cr3t")
    r = client.post("/ingest/webhook", json=_evento(), headers={"X-Webhook-Hmac": "mentira"})
    assert r.status_code == 401


def test_webhook_rechaza_sin_firma_si_hay_secreto(client, repo, monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "s3cr3t")
    assert client.post("/ingest/webhook", json=_evento()).status_code == 401


def test_webhook_acepta_la_firma_como_la_manda_waha(client, repo, monkeypatch):
    """WAHA firma con SHA-512, no con SHA-256.

    Este test firmaba con SHA-256 y pasaba, porque el backend validaba con
    SHA-256: el test confirmaba la suposición del código en vez de la realidad.
    Los dos estaban equivocados y ninguno lo decía. En producción, WAHA mandaba
    su firma sha512, el backend la rechazaba con 401 y NINGUNA oferta podía
    entrar — sin un solo error visible del lado de URUKU.
    """
    import json
    monkeypatch.setattr(settings, "webhook_secret", "s3cr3t")
    cuerpo = json.dumps(_evento()).encode()
    firma = hmac.new(b"s3cr3t", cuerpo, hashlib.sha512).hexdigest()

    r = client.post("/ingest/webhook", content=cuerpo,
                    headers={"X-Webhook-Hmac": firma,
                             "X-Webhook-Hmac-Algorithm": "sha512",
                             "Content-Type": "application/json"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


def test_webhook_sin_cabecera_de_algoritmo_asume_sha512(client, repo, monkeypatch):
    """Es lo que manda WAHA. Si algún día deja de declararlo, sigue andando."""
    import json
    monkeypatch.setattr(settings, "webhook_secret", "s3cr3t")
    cuerpo = json.dumps(_evento("wa-sin-alg")).encode()
    firma = hmac.new(b"s3cr3t", cuerpo, hashlib.sha512).hexdigest()

    r = client.post("/ingest/webhook", content=cuerpo,
                    headers={"X-Webhook-Hmac": firma, "Content-Type": "application/json"})
    assert r.status_code == 200, r.text


def test_webhook_acepta_sha256_si_el_emisor_lo_declara(client, repo, monkeypatch):
    """No se rompe con un emisor que use otro algoritmo, mientras lo diga."""
    import json
    monkeypatch.setattr(settings, "webhook_secret", "s3cr3t")
    cuerpo = json.dumps(_evento("wa-256")).encode()
    firma = hmac.new(b"s3cr3t", cuerpo, hashlib.sha256).hexdigest()

    r = client.post("/ingest/webhook", content=cuerpo,
                    headers={"X-Webhook-Hmac": firma,
                             "X-Webhook-Hmac-Algorithm": "sha256",
                             "Content-Type": "application/json"})
    assert r.status_code == 200, r.text


def test_webhook_rechaza_un_algoritmo_que_no_esta_en_la_lista(client, repo, monkeypatch):
    """Sin lista blanca, cualquiera podría pedir un algoritmo débil por cabecera
    y bajarle el piso a la validación."""
    import json
    monkeypatch.setattr(settings, "webhook_secret", "s3cr3t")
    cuerpo = json.dumps(_evento("wa-md5")).encode()

    r = client.post("/ingest/webhook", content=cuerpo,
                    headers={"X-Webhook-Hmac": "loquesea",
                             "X-Webhook-Hmac-Algorithm": "md5",
                             "Content-Type": "application/json"})
    assert r.status_code == 401


def test_webhook_ignora_eventos_que_no_son_mensajes(client, repo, monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "")
    r = client.post("/ingest/webhook", json={"event": "session.status",
                                             "payload": {"status": "WORKING"}})
    assert r.status_code == 200
    assert r.json()["handled"] == "session.status"


def test_webhook_no_falla_con_un_evento_desconocido(client, repo, monkeypatch):
    monkeypatch.setattr(settings, "webhook_secret", "")
    r = client.post("/ingest/webhook", json={"event": "algo.raro"})
    assert r.status_code == 200
    assert r.json()["ignored"] == "algo.raro"


# ═════════════════════ endpoints que dependen de un servicio externo
# Sin key tienen que responder igual, con un resultado vacío: si rompen, rompen
# el alta de campo entera.
def test_sugerir_rubros_sin_key_no_rompe(client, repo, agente_token, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    r = client.post("/campo/sugerir-rubros",
                    json={"descripcion": "zapatillas y chinelas",
                          "rubros": [{"slug": "calzado", "nombre": "Calzado"}]},
                    headers=_h(agente_token))
    assert r.status_code == 200, r.text
    assert r.json()["rubro_slugs"] == []


def test_generar_descripcion_sin_key_devuelve_el_texto_tal_cual(client, repo, monkeypatch):
    """El agente escribió algo: perderlo sería peor que no mejorarlo."""
    monkeypatch.setattr(settings, "gemini_api_key", "")
    r = client.post("/comercio/generar-descripcion",
                    json={"nombre": "Casa Pepe", "que_vende": "zapatillas y mochilas",
                          "rubros": [{"slug": "calzado", "nombre": "Calzado"}]})
    assert r.status_code == 200, r.text
    assert r.json()["descripcion"] == "zapatillas y mochilas"


def test_sugerir_rubros_requiere_agente(client, repo):
    r = client.post("/campo/sugerir-rubros", json={"descripcion": "x", "rubros": []})
    assert r.status_code in (401, 403)


def test_transcribir_sin_audio_da_400(client, repo, agente_token):
    r = client.post("/campo/transcribir", files={"audio": ("v.webm", b"", "audio/webm")},
                    headers=_h(agente_token))
    assert r.status_code == 400


def test_transcribir_requiere_agente(client, repo):
    r = client.post("/campo/transcribir", files={"audio": ("v.webm", b"x", "audio/webm")})
    assert r.status_code in (401, 403)
