"""Un mensaje cuya ingesta se cortó a mitad de camino no puede morir guardado.

Pasó el 11/9 con el primer código de grupo en producción: el backend llevaba
una hora sin hablar con la base, la conexión estaba muerta, el INSERT en
wa_inbox se ejecutó pero la respuesta nunca volvió, y la ingesta se cortó
ahí. WAHA reintentó dos veces —bien— y las dos veces la ingesta contestó
"duplicado": la fila ya estaba. El mensaje quedó guardado, sin resultado, y
sin procesar para siempre.

"Ya está guardado" no es "ya se procesó". La guarda de duplicados protegía
contra lo que no había que proteger, y rechazó el reintento que habría
arreglado todo.
"""
import httpx
import pytest

from app.core.config import settings
from app.services import ingest


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _evento(texto, de="59170000009", grupo="120999@g.us", mid="m-1"):
    return {"event": "message", "session": "default", "payload": {
        "id": mid, "from": grupo, "participant": f"{de}@c.us",
        "body": texto, "type": "text", "fromMe": False}}


@pytest.fixture
def propio_es_el_samsung(monkeypatch):
    monkeypatch.setattr(settings, "wa_numeros_propios", "59175314737")
    from app.core import config as cfg
    cfg._numeros_propios.cache_clear()


# ═══════════════════════════════ guardado ≠ procesado

def test_un_mensaje_guardado_sin_resultado_se_retoma_en_el_reintento(repo, propio_es_el_samsung):
    """El escenario exacto del 11/9: la fila existe, no tiene resultado, y
    llega el reintento de WAHA. Tiene que procesarse, no descartarse."""
    repo.seed_comercio(slug="calzados", nombre="Calzados", codigo="7K3M")
    # La primera ingesta llegó a guardar y se cortó: fila sin resultado.
    repo.insert_wa_inbox({"wa_message_id": "m-1", "wa_jid": "120999@g.us",
                          "phone": "59175314737", "raw": {}})
    assert repo.wa_inbox["m-1"].get("resultado") is None

    r = ingest.handle_message(_evento("URUKU-7K3M", de="59175314737"), repo)

    assert r.get("duplicate") is not True
    assert r["grupo_atado"] == "calzados"
    assert repo.wa_inbox["m-1"]["resultado"] == "ignorada"


def test_un_mensaje_ya_procesado_sigue_siendo_duplicado(repo, propio_es_el_samsung):
    """La guarda no se fue: lo que SÍ tiene resultado no se procesa dos veces.
    Reprocesar una oferta ya publicada la publicaría de nuevo."""
    repo.seed_comercio(slug="calzados", nombre="Calzados", codigo="7K3M")
    ingest.handle_message(_evento("URUKU-7K3M", de="59175314737"), repo)
    r = ingest.handle_message(_evento("URUKU-7K3M", de="59175314737"), repo)
    assert r == {"captured": True, "duplicate": True}


# ═══════════════════════════ la conexión muerta, en el webhook

def test_el_webhook_reintenta_una_vez_si_la_conexion_estaba_muerta(client, repo, monkeypatch):
    """La primera consulta después de una hora de silencio viaja por una
    conexión que el servidor ya cerró. La segunda abre una nueva y anda."""
    monkeypatch.setattr(settings, "webhook_secret", "")
    monkeypatch.setattr(settings, "environment", "development")
    llamadas = {"n": 0}
    original = ingest.handle_message

    def _primera_vez_explota(evento, repo_):
        llamadas["n"] += 1
        if llamadas["n"] == 1:
            raise httpx.RemoteProtocolError("Server disconnected")
        return original(evento, repo_)
    monkeypatch.setattr(ingest, "handle_message", _primera_vez_explota)

    r = client.post("/ingest/webhook", json=_evento("hola", mid="m-2"))
    assert r.status_code == 200, r.text
    assert llamadas["n"] == 2
    assert "m-2" in repo.wa_inbox


def test_el_webhook_no_reintenta_dos_veces(client, repo, monkeypatch):
    """Una vez. Si la segunda también falla, es otra cosa y tiene que verse."""
    monkeypatch.setattr(settings, "webhook_secret", "")
    monkeypatch.setattr(settings, "environment", "development")

    def _siempre_explota(evento, repo_):
        raise httpx.RemoteProtocolError("Server disconnected")
    monkeypatch.setattr(ingest, "handle_message", _siempre_explota)

    # El TestClient re-lanza lo que el servidor no atrapó: en producción es
    # un 500, acá es la excepción — y lo que importa es que llegue.
    with pytest.raises(httpx.RemoteProtocolError):
        client.post("/ingest/webhook", json=_evento("hola", mid="m-3"))


def test_otro_error_no_se_reintenta(client, repo, monkeypatch):
    """Sólo la conexión muerta. Un error de lógica repetido dos veces es el
    mismo error dos veces, y podría duplicar algo por el camino."""
    monkeypatch.setattr(settings, "webhook_secret", "")
    monkeypatch.setattr(settings, "environment", "development")
    llamadas = {"n": 0}

    def _explota(evento, repo_):
        llamadas["n"] += 1
        raise RuntimeError("otra cosa")
    monkeypatch.setattr(ingest, "handle_message", _explota)

    with pytest.raises(RuntimeError):
        client.post("/ingest/webhook", json=_evento("hola", mid="m-4"))
    assert llamadas["n"] == 1


# ═══════════════════════════════ reprocesar desde el panel

def test_reprocesar_desde_el_panel_termina_el_trabajo(client, repo, admin_token, propio_es_el_samsung):
    """Para cuando WAHA ya no va a reintentar: el crudo está guardado y se
    vuelve a pasar por la ingesta como si acabara de llegar."""
    repo.seed_comercio(slug="calzados", nombre="Calzados", codigo="7K3M")
    crudo = _evento("URUKU-7K3M", de="59175314737")["payload"]
    repo.insert_wa_inbox({"wa_message_id": "m-1", "wa_jid": "120999@g.us",
                          "phone": "59175314737", "raw": crudo, "via": "waha"})

    r = client.post("/admin/whatsapp/entrantes/m-1/reprocesar", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["grupo_atado"] == "calzados"
    assert repo.wa_grupos["120999@g.us"]


def test_no_se_reprocesa_lo_que_ya_tiene_resultado(client, repo, admin_token):
    repo.insert_wa_inbox({"wa_message_id": "m-9", "wa_jid": "x", "raw": {"id": "m-9"}})
    repo.marcar_wa_inbox("m-9", "publicada", "ok")
    r = client.post("/admin/whatsapp/entrantes/m-9/reprocesar", headers=_h(admin_token))
    assert r.status_code == 409


def test_reprocesar_algo_que_no_existe(client, admin_token):
    r = client.post("/admin/whatsapp/entrantes/nada/reprocesar", headers=_h(admin_token))
    assert r.status_code == 404
