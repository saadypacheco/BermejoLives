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


# ---------------- Confirmación de login/recuperación por WhatsApp entrante ----------------
def test_confirmar_no_crea_publicacion_ni_comercio(repo):
    """El mensaje 'CONFIRMAR-XXXXXX' no es una oferta — no debe caer en el
    flujo normal de ingesta (nada de comercio fantasma ni publicación)."""
    res = ingest.handle_message(_evento(wamid="wa-c1", body="CONFIRMAR-123456", jid="59170000001@c.us"), repo)
    assert res == {"captured": True, "confirmacion": True, "confirmado": False}
    assert len(repo.publicaciones) == 0
    assert len(repo.comercios) == 0


def test_confirmar_valida_codigo_de_comprador(repo):
    usuario = repo.crear_usuario("59170000001")
    repo.set_reset_code_usuario(usuario["id"], "654321", "2099-01-01T00:00:00+00:00")

    res = ingest.handle_message(_evento(wamid="wa-c2", body="CONFIRMAR-654321", jid="59170000001@c.us"), repo)
    assert res["confirmado"] is True
    assert repo.compradores[usuario["id"]]["reset_code_confirmado_at"] is not None


def test_confirmar_codigo_no_coincide(repo):
    usuario = repo.crear_usuario("59170000001")
    repo.set_reset_code_usuario(usuario["id"], "654321", "2099-01-01T00:00:00+00:00")

    res = ingest.handle_message(_evento(wamid="wa-c3", body="CONFIRMAR-000000", jid="59170000001@c.us"), repo)
    assert res["confirmado"] is False
    assert repo.compradores[usuario["id"]]["reset_code_confirmado_at"] is None


def test_confirmar_ignora_mayusculas_y_espacios(repo):
    usuario = repo.crear_usuario("59170000001")
    repo.set_reset_code_usuario(usuario["id"], "654321", "2099-01-01T00:00:00+00:00")

    res = ingest.handle_message(_evento(wamid="wa-c4", body="  confirmar-654321  ", jid="59170000001@c.us"), repo)
    assert res["confirmado"] is True


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


# ---------------- Grupos: uno por comerciante ----------------
#
# El modelo: cada comerciante tiene UN grupo con tres participantes — su
# celular, un celular de URUKU y el testigo (el vinculado a WAHA). El grupo es
# lo estable: el comerciante cambia de teléfono y el contenido sigue llegando
# al local correcto.

GRUPO = "120363111222333@g.us"


def _evento_grupo(wamid="wa-g1", body="Oferta 120 Bs", participante="59170000007@c.us",
                  tipo="text", grupo=GRUPO):
    """Un mensaje de grupo: `from` es el GRUPO y el remitente va aparte, en
    `_data.key.participant` (así lo manda el motor NOWEB, el que corre en prod)."""
    return {
        "event": "message",
        "session": "obs@c.us",
        "payload": {
            "id": wamid, "from": grupo, "fromMe": False, "body": body, "type": tipo,
            "timestamp": 1700000000,
            "_data": {"key": {"remoteJid": grupo, "participant": participante}},
        },
    }


def test_grupo_desconocido_no_crea_comercio_fantasma(repo):
    """Un número desconocido en un chat 1-a-1 es un comerciante nuevo y crear
    el borrador tiene sentido. Un grupo desconocido no es nadie: si se creara
    un comercio por grupo, la base se llenaría de fichas que nadie cargó."""
    res = ingest.handle_message(_evento_grupo(), repo)
    assert res["captured"] is True
    assert res["publicada"] is False
    assert len(repo.comercios) == 0
    assert len(repo.publicaciones) == 0
    # El crudo sí queda: cuando el grupo se ate, se puede saber qué llegó antes.
    assert len(repo.wa_inbox) == 1


def test_grupo_se_ata_con_el_codigo_y_publica(repo):
    repo.seed_comercio(id="com-g", slug="mendo", nombre="Mendo", whatsapp="59170000007",
                       codigo="ABCD")
    res = ingest.handle_message(_evento_grupo(body="URUKU-ABCD"), repo)

    assert res["estado"] == "pendiente"
    assert repo.wa_grupos[GRUPO]["comercio_id"] == "com-g"
    assert repo.publicaciones[0]["comercio_id"] == "com-g"


def test_grupo_ya_atado_publica_sin_codigo(repo):
    """Lo que hace útil al modelo: una vez atado, el comerciante manda la foto
    y nada más — no repite el código ni se identifica."""
    repo.seed_comercio(id="com-g", slug="mendo", nombre="Mendo", whatsapp="59170000007")
    repo.vincular_grupo_comercio(GRUPO, "com-g", None, "admin", "test")

    res = ingest.handle_message(_evento_grupo(wamid="wa-g2", body="Llegaron camperas"), repo)
    assert res["estado"] == "pendiente"
    assert repo.publicaciones[0]["comercio_id"] == "com-g"


def test_el_codigo_de_otro_no_le_roba_el_grupo(repo):
    repo.seed_comercio(id="com-a", slug="a", nombre="A", whatsapp="59170000007")
    repo.seed_comercio(id="com-b", slug="b", nombre="B", whatsapp="59170000008", codigo="BBBB")
    repo.vincular_grupo_comercio(GRUPO, "com-a", None, "admin", "test")

    ingest.handle_message(_evento_grupo(wamid="wa-g3", body="URUKU-BBBB"), repo)
    assert repo.wa_grupos[GRUPO]["comercio_id"] == "com-a"
    assert repo.publicaciones[0]["comercio_id"] == "com-a"


def test_mensaje_de_un_numero_de_uruku_no_publica(repo, monkeypatch):
    """El testigo ya está cubierto por fromMe. El celular de URUKU no: es otro
    teléfono y entra como cualquier participante — sin esta regla, cada 'buen
    día' nuestro se publica a nombre del comerciante."""
    from app.core.config import settings

    monkeypatch.setattr(settings, "wa_numeros_propios", "59170000099", raising=False)
    repo.seed_comercio(id="com-g", slug="mendo", nombre="Mendo", whatsapp="59170000007")
    repo.vincular_grupo_comercio(GRUPO, "com-g", None, "admin", "test")

    res = ingest.handle_message(
        _evento_grupo(wamid="wa-g4", participante="59170000099@c.us", body="buen día"), repo)
    assert res["publicada"] is False
    assert len(repo.publicaciones) == 0


def test_el_placeholder_del_env_no_bloquea_a_nadie_y_avisa(repo, monkeypatch):
    """`591XXXXXXXX` sin reemplazar normaliza a `591`: las X se descartan como
    cualquier separador. La variable queda "puesta", la lista tiene un elemento,
    y no coincide con ningún teléfono real — la guarda existe y no protege nada.

    Se acepta que quede apagada (el .env es del operador), pero NO en silencio:
    tiene que avisar, y sobre todo no puede bloquear a un comerciante real por
    haber quedado con un valor de mentira.
    """
    from app.core.config import settings

    monkeypatch.setattr(settings, "wa_numeros_propios", "591XXXXXXXX", raising=False)
    repo.seed_comercio(id="com-g", slug="mendo", nombre="Mendo", whatsapp="59170000007")
    repo.vincular_grupo_comercio(GRUPO, "com-g", None, "admin", "test")

    res = ingest.handle_message(_evento_grupo(wamid="wa-ph"), repo)
    assert res["estado"] == "pendiente"       # el comerciante publica igual
    assert len(repo.publicaciones) == 1


def test_un_cuarto_participante_no_publica_directo(repo):
    """El grupo dice de qué comercio es; el remitente dice si es él. Si aparece
    un número que no es del comercio ni nuestro, alguien sumó a alguien: no se
    descarta (puede ser el mismo dueño con otro celular) pero no sale solo."""
    repo.seed_comercio(id="com-g", slug="mendo", nombre="Mendo", whatsapp="59170000007",
                       confiable=True)
    repo.vincular_grupo_comercio(GRUPO, "com-g", None, "admin", "test")

    res = ingest.handle_message(
        _evento_grupo(wamid="wa-g5", participante="59170000055@c.us"), repo)
    assert res["estado"] == "pendiente"      # confiable, pero no de él -> moderación


def test_el_confiable_del_grupo_publica_directo(repo):
    repo.seed_comercio(id="com-g", slug="mendo", nombre="Mendo", whatsapp="59170000007",
                       confiable=True)
    repo.vincular_grupo_comercio(GRUPO, "com-g", None, "admin", "test")

    res = ingest.handle_message(_evento_grupo(wamid="wa-g6"), repo)
    assert res["estado"] == "aprobado"


# ── El explorador ────────────────────────────────────────────────────────────
# URUKU sale a fotografiar ofertas de locales que todavía no publican. Un mismo
# teléfono publica para cien locales distintos en una tarde, así que acá el
# CÓDIGO tiene que ganarle a todo lo demás — al revés que para un comerciante,
# cuyo celular es siempre el mismo local.

EXPLORADOR = "59170000555"


def _explorador(monkeypatch, contacto="59170000999"):
    from app.core.config import settings

    monkeypatch.setattr(settings, "wa_numeros_explorador", EXPLORADOR, raising=False)
    monkeypatch.setattr(settings, "wa_contacto_explorador", contacto, raising=False)


def _ev_explorador(wamid, body):
    return _evento(wamid=wamid, body=body, jid=f"{EXPLORADOR}@c.us")


def test_explorador_publica_a_nombre_del_comercio_del_codigo(repo, monkeypatch):
    _explorador(monkeypatch)
    repo.seed_comercio(id="com-e1", slug="am-calzados", nombre="A&M", codigo="AQP5")

    res = ingest.handle_message(_ev_explorador("wa-e1", "URUKU-AQP5 zapatilla urbana Bs 180"), repo)

    assert res["comercio"] == "am-calzados"
    assert res["origen"] == "explorador"
    pub = repo.publicaciones[0]
    assert pub["comercio_id"] == "com-e1"
    assert pub["origen"] == "explorador"
    # Siempre a moderación: URUKU está publicando el precio de un local que no
    # lo pidió, y la cola es donde una persona lo mira.
    assert pub["estado"] == "pendiente"


def test_explorador_no_queda_pegado_al_primer_comercio(repo, monkeypatch):
    """La trampa que motivó todo esto.

    Sin la rama del explorador, la primera publicación ata el número al comercio
    y TODAS las siguientes se publican bajo ése — sin ningún error a la vista.
    """
    _explorador(monkeypatch)
    repo.seed_comercio(id="com-a", slug="local-a", nombre="A", codigo="AAA2")
    repo.seed_comercio(id="com-b", slug="local-b", nombre="B", codigo="BBB3")

    ingest.handle_message(_ev_explorador("wa-a", "URUKU-AAA2 remera Bs 90"), repo)
    ingest.handle_message(_ev_explorador("wa-b", "URUKU-BBB3 campera Bs 300"), repo)

    assert [p["comercio_id"] for p in repo.publicaciones] == ["com-a", "com-b"]


def test_explorador_sin_codigo_no_publica_nada(repo, monkeypatch):
    """Adivinar sería poner la foto y el precio de un local en la ficha de otro."""
    _explorador(monkeypatch)
    repo.seed_comercio(id="com-a", slug="local-a", nombre="A", codigo="AAA2")

    res = ingest.handle_message(_ev_explorador("wa-s", "zapatillas lindas Bs 200"), repo)

    assert res["publicada"] is False
    assert repo.publicaciones == []
    assert repo.comercios.get("com-a") and len(repo.comercios) == 1  # tampoco inventa uno


def test_explorador_codigo_de_comercio_inexistente_no_publica(repo, monkeypatch):
    _explorador(monkeypatch)
    res = ingest.handle_message(_ev_explorador("wa-x", "URUKU-ZZZ9 algo Bs 10"), repo)
    assert res["publicada"] is False
    assert repo.publicaciones == []


def test_explorador_el_codigo_no_queda_a_la_vista_del_comprador(repo, monkeypatch):
    _explorador(monkeypatch)
    repo.seed_comercio(id="com-a", slug="local-a", nombre="A", codigo="AAA2")

    ingest.handle_message(_ev_explorador("wa-t", "URUKU-AAA2 zapatilla urbana Bs 180"), repo)

    assert repo.publicaciones[0]["descripcion"] == "zapatilla urbana Bs 180"


def test_explorador_manda_la_consulta_al_numero_de_uruku(repo, monkeypatch):
    _explorador(monkeypatch, contacto="59170000999")
    repo.seed_comercio(id="com-a", slug="local-a", nombre="A", codigo="AAA2")

    ingest.handle_message(_ev_explorador("wa-c", "URUKU-AAA2 remera Bs 90"), repo)

    assert repo.publicaciones[0]["contacto_whatsapp"] == "59170000999"


def test_sin_numero_de_contacto_la_consulta_va_al_comercio(repo, monkeypatch):
    """Nunca mandar al comprador a un número que no está escuchando."""
    _explorador(monkeypatch, contacto="")
    repo.seed_comercio(id="com-a", slug="local-a", nombre="A", codigo="AAA2")

    ingest.handle_message(_ev_explorador("wa-n", "URUKU-AAA2 remera Bs 90"), repo)

    assert repo.publicaciones[0]["contacto_whatsapp"] is None


def test_explorador_gana_al_descarte_por_numero_propio(repo, monkeypatch):
    """El explorador también está en WA_NUMEROS_PROPIOS.

    Es a propósito: así sigue siendo inofensivo el día que alguien lo agregue al
    grupo de un comerciante. Pero si esa comprobación corriera primero, sus
    fotos se tirarían como "mensaje de un número de URUKU".
    """
    from app.core.config import settings

    _explorador(monkeypatch)
    monkeypatch.setattr(settings, "wa_numeros_propios", EXPLORADOR, raising=False)
    repo.seed_comercio(id="com-a", slug="local-a", nombre="A", codigo="AAA2")

    ev = _ev_explorador("wa-g", "URUKU-AAA2 remera Bs 90")
    ev["payload"]["from"] = "12036@g.us"
    ev["payload"]["participant"] = f"{EXPLORADOR}@c.us"

    res = ingest.handle_message(ev, repo)
    assert res.get("origen") == "explorador"
    assert repo.publicaciones[0]["comercio_id"] == "com-a"
