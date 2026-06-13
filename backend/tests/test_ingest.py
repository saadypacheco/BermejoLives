"""Ingesta de WhatsApp: idempotencia, clasificación y regla de confiable."""
from app.services import ingest


def _evento(wamid="wa-1", body="Oferta zapatillas 120 Bs", jid="59170000009@c.us", tipo="text"):
    return {
        "event": "message",
        "session": "obs@c.us",
        "payload": {"id": wamid, "from": jid, "fromMe": False, "body": body, "type": tipo, "timestamp": 1700000000},
    }


def test_mensaje_crea_publicacion_pendiente(repo):
    res = ingest.handle_message(_evento(), repo)
    assert res["captured"] is True
    assert res["estado"] == "pendiente"
    assert len(repo.publicaciones) == 1
    assert repo.publicaciones[0]["estado"] == "pendiente"


def test_idempotencia_por_wa_message_id(repo):
    ingest.handle_message(_evento(wamid="dup-1"), repo)
    res = ingest.handle_message(_evento(wamid="dup-1"), repo)
    assert res.get("duplicate") is True
    assert len(repo.publicaciones) == 1  # no se duplica


def test_comercio_confiable_publica_directo(repo):
    # comercio confiable ya existente por su jid
    repo.seed_comercio(id="com-7", slug="abc", nombre="ABC", whatsapp="59170000007",
                       wa_jid="59170000007@c.us", confiable=True)
    res = ingest.handle_message(_evento(wamid="wa-7", jid="59170000007@c.us"), repo)
    assert res["estado"] == "aprobado"
    pub = repo.publicaciones[0]
    assert pub["estado"] == "aprobado"
    assert pub["approved_at"] is not None
    assert pub["moderado_por"] == "auto-confiable"


def test_clasificacion_video_por_link_tiktok(repo):
    res = ingest.handle_message(_evento(wamid="wa-v", body="Miren https://tiktok.com/@x/video/9"), repo)
    assert res["tipo"] == "video"
    assert repo.publicaciones[0]["tiktok_url"] == "https://tiktok.com/@x/video/9"


def test_ubicacion_por_whatsapp_actualiza_comercio(repo):
    """El vendedor comparte su ubicación por WhatsApp -> se guardan lat/lng."""
    repo.seed_comercio(id="com-loc", slug="loc", nombre="Loc", whatsapp="59170000008",
                       wa_jid="59170000008@c.us")
    ev = {
        "event": "message",
        "session": "obs@c.us",
        "payload": {
            "id": "wa-loc", "from": "59170000008@c.us", "fromMe": False, "type": "location",
            "location": {"latitude": -22.7361, "longitude": -64.3433, "address": "Galería Central"},
            "timestamp": 1700000000,
        },
    }
    res = ingest.handle_message(ev, repo)
    assert res["ubicacion_actualizada"] is True
    c = repo.comercios["com-loc"]
    assert c["lat"] == -22.7361 and c["lng"] == -64.3433
    assert c["direccion"] == "Galería Central"
    assert len(repo.publicaciones) == 0  # ubicación no crea publicación


def test_mensaje_propio_se_ignora(repo):
    ev = _evento()
    ev["payload"]["fromMe"] = True
    res = ingest.handle_message(ev, repo)
    assert res["captured"] is False
    assert len(repo.publicaciones) == 0
