"""Estar listos para la API oficial de Meta antes de necesitarla.

WAHA sirve para arrancar; a miles de comercios no se llega con automatización no
oficial. Lo que no puede pasar el día de la migración es reescribir la ingesta,
que es la parte más probada del sistema — de ahí que lo de Meta se traduzca en
la puerta a la forma que la ingesta ya entiende.

Estos tests son la red que hace que esa traducción no se pudra sin que nadie se
entere: hoy no entra ni un mensaje por Meta, así que nada más la vigila.
"""
import hashlib
import hmac
import json

import pytest

from app.core.config import settings
from app.services import mensajeria


def _evento_meta(mensajes: list[dict]) -> dict:
    return {"object": "whatsapp_business_account",
            "entry": [{"id": "1", "changes": [{"field": "messages", "value": {
                "messaging_product": "whatsapp",
                "metadata": {"phone_number_id": "111"},
                "messages": mensajes}}]}]}


def _texto(id_="wamid.1", cuerpo="hola", de="59170000001"):
    return {"from": de, "id": id_, "timestamp": "1757500000",
            "type": "text", "text": {"body": cuerpo}}


# ═════════════════════════════════════════════════════ traducción de entrada

def test_un_texto_de_meta_queda_como_uno_de_waha():
    e = mensajeria.normalizar_entrante(_evento_meta([_texto()]))
    p = e["payload"]
    assert e["event"] == "message"
    assert p["id"] == "wamid.1"
    assert p["body"] == "hola"
    assert p["fromMe"] is False


def test_en_la_api_oficial_nunca_es_un_grupo():
    """Meta no soporta grupos y no hay señales de que lo vaya a hacer. Marcar
    uno como grupo haría que la ingesta buscara un vínculo que no existe."""
    from app.models.whatsapp import WahaMessagePayload

    e = mensajeria.normalizar_entrante(_evento_meta([_texto()]))
    payload = WahaMessagePayload.model_validate(e["payload"])
    assert payload.es_grupo is False
    assert payload.from_ == "59170000001@c.us"


def test_una_foto_trae_el_identificador_y_el_epigrafe():
    """En la API oficial la foto no viene con URL: viene con un id que se canjea
    con el token. Guardar eso como si fuera una URL descarga contra una
    dirección inventada y la publicación sale sin imagen."""
    e = mensajeria.normalizar_entrante(_evento_meta([{
        "from": "59170000001", "id": "wamid.2", "timestamp": "1757500000",
        "type": "image", "image": {"id": "media-77", "caption": "zapatillas 250"}}]))
    p = e["payload"]
    assert p["type"] == "image"
    assert p["hasMedia"] is True
    assert p["mediaUrl"] == "cloud-media:media-77"
    assert p["body"] == "zapatillas 250"


def test_una_tanda_con_varios_mensajes_no_pierde_ninguno():
    """Meta agrupa. Quedarse con el primero pierde el resto en silencio, y
    justo los días de mucho movimiento."""
    e = mensajeria.normalizar_entrante(_evento_meta([
        _texto("wamid.1"), _texto("wamid.2"), _texto("wamid.3")]))
    assert e["payload"]["id"] == "wamid.1"
    assert [m["id"] for m in e["_extra"]] == ["wamid.2", "wamid.3"]


def test_los_avisos_de_entrega_no_son_mensajes():
    """Llegan por la misma URL. Si se tomaran como mensajes, la bandeja se
    llenaría de filas vacías."""
    evento = {"object": "whatsapp_business_account", "entry": [{"changes": [
        {"field": "messages", "value": {"statuses": [{"status": "delivered"}]}}]}]}
    assert mensajeria.normalizar_entrante(evento) is None


def test_lo_de_waha_pasa_derecho():
    """La traducción no puede tocar lo que ya viene bien: hoy TODO entra por
    WAHA."""
    e = {"event": "message", "session": "default", "payload": {"id": "x"}}
    assert mensajeria.normalizar_entrante(e) is e


# ════════════════════════════════════════════════════════ salida por proveedor

def test_el_proveedor_decide_por_donde_sale(monkeypatch):
    llamadas = []
    monkeypatch.setattr(mensajeria, "_waha_texto",
                        lambda c, t: llamadas.append(("waha", c)) or True)
    monkeypatch.setattr(mensajeria, "_cloud_texto",
                        lambda c, t: llamadas.append(("cloud", c)) or True)

    monkeypatch.setattr(settings, "whatsapp_provider", "waha")
    mensajeria.enviar_texto("59170000001@c.us", "hola")
    monkeypatch.setattr(settings, "whatsapp_provider", "cloud_api")
    mensajeria.enviar_texto("59170000001@c.us", "hola")

    assert [p for p, _ in llamadas] == ["waha", "cloud"]


def test_la_api_oficial_quiere_el_telefono_pelado():
    """Mandarle el JID a Meta es un 400 por un destinatario que no existe."""
    assert mensajeria._cloud_destino("59170000001@c.us") == "59170000001"
    assert mensajeria._cloud_destino("+59170000001") == "59170000001"


def test_un_envio_que_falla_no_lanza(monkeypatch):
    """Quien avisa no puede romperse por avisar."""
    def _explota(c, t):
        raise RuntimeError("sin red")
    monkeypatch.setattr(mensajeria, "_waha_texto", _explota)
    monkeypatch.setattr(settings, "whatsapp_provider", "waha")
    assert mensajeria.enviar_texto("x@c.us", "hola") is False


# ═══════════════════════════════════════════════════════════ el webhook

def test_meta_verifica_la_url_con_un_get(client, monkeypatch):
    """Sin este GET no se puede ni dar de alta el webhook, y el error de la
    consola de Meta no dice que falta."""
    monkeypatch.setattr(settings, "meta_verify_token", "secreto-de-verificacion")
    r = client.get("/ingest/webhook", params={"hub.mode": "subscribe",
                                       "hub.verify_token": "secreto-de-verificacion",
                                       "hub.challenge": "12345"})
    assert r.status_code == 200
    assert r.text == "12345"


def test_un_token_de_verificacion_equivocado_se_rechaza(client, monkeypatch):
    monkeypatch.setattr(settings, "meta_verify_token", "el-bueno")
    r = client.get("/ingest/webhook", params={"hub.mode": "subscribe",
                                       "hub.verify_token": "el-malo",
                                       "hub.challenge": "12345"})
    assert r.status_code == 403


def test_sin_token_configurado_no_se_verifica_nada(client, monkeypatch):
    """Vacío no puede significar "que pase cualquiera": sería dejar que un
    tercero enganche su cuenta de Meta a nuestro webhook."""
    monkeypatch.setattr(settings, "meta_verify_token", "")
    r = client.get("/ingest/webhook", params={"hub.mode": "subscribe",
                                       "hub.verify_token": "", "hub.challenge": "1"})
    assert r.status_code == 403


def test_un_mensaje_de_meta_entra_con_su_firma(client, repo, monkeypatch):
    """Meta firma distinto que WAHA: otra cabecera, otro algoritmo y otra
    clave. Si sólo se validara la de WAHA, todo lo de Meta rebotaría con 401 y
    del lado de URUKU no habría ni un error — el mismo síntoma que ya tuvo este
    webhook una vez."""
    monkeypatch.setattr(settings, "meta_app_secret", "app-secret")
    cuerpo = json.dumps(_evento_meta([_texto("wamid.entra")])).encode()
    firma = "sha256=" + hmac.new(b"app-secret", cuerpo, hashlib.sha256).hexdigest()

    r = client.post("/ingest/webhook", content=cuerpo,
                    headers={"Content-Type": "application/json",
                             "X-Hub-Signature-256": firma})
    assert r.status_code == 200, r.text
    assert any(f.get("wa_message_id") == "wamid.entra" for f in repo.wa_inbox.values())


def test_una_firma_de_meta_falsa_se_rechaza(client, monkeypatch):
    monkeypatch.setattr(settings, "meta_app_secret", "app-secret")
    monkeypatch.setattr(settings, "webhook_secret", "otra-cosa")
    cuerpo = json.dumps(_evento_meta([_texto()])).encode()
    r = client.post("/ingest/webhook", content=cuerpo,
                    headers={"Content-Type": "application/json",
                             "X-Hub-Signature-256": "sha256=" + "0" * 64})
    assert r.status_code == 401


def test_los_mensajes_extra_de_una_tanda_tambien_se_procesan(client, repo, monkeypatch):
    monkeypatch.setattr(settings, "meta_app_secret", "app-secret")
    cuerpo = json.dumps(_evento_meta([
        _texto("wamid.a", "uno"), _texto("wamid.b", "dos")])).encode()
    firma = "sha256=" + hmac.new(b"app-secret", cuerpo, hashlib.sha256).hexdigest()

    client.post("/ingest/webhook", content=cuerpo,
                headers={"Content-Type": "application/json", "X-Hub-Signature-256": firma})
    ids = {f.get("wa_message_id") for f in repo.wa_inbox.values()}
    assert {"wamid.a", "wamid.b"} <= ids
