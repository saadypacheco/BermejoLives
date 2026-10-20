"""E1 · Recepción (docs/grupos-por-comercio.md §7.2 y §10.1, criterios 6 y 7) + correcciones
de la revisión (S1-S5, S9, E-a).

  GET  /admin/whatsapp/inbox/{wa_message_id}/media    la foto del disco privado
  GET  /admin/whatsapp/unknown?days=30                lo que no tiene dueño (sin teléfonos completos)
  POST /admin/whatsapp/inbox/{wa_message_id}/assign   «Es de…» sobre un mensaje
  POST /admin/whatsapp/groups/{group_jid}/assign      «Es de…» sobre un grupo
"""
from io import BytesIO
from pathlib import Path

import pytest

from app.core import auth
from app.core import config as cfg
from app.core.config import settings
from app.services import ingest

PROPIO = "59175314737"
EXPLORADOR = "59170000555"
NUM = "59171234567"
GRUPO = "120363111222333@g.us"
COM = "11111111-1111-4111-8111-111111111111"
OTRO = "22222222-2222-4222-8222-222222222222"
LID = "160138577080406@lid"


def _jpeg() -> bytes:
    from PIL import Image

    b = BytesIO()
    Image.new("RGB", (60, 40), (10, 90, 200)).save(b, "JPEG")
    return b.getvalue()


@pytest.fixture(autouse=True)
def _waha(monkeypatch):
    """WAHA entrega la foto UNA vez; después ya no tiene nada (la borra)."""
    from app.services import wa_media

    entregas = {"n": 0}

    def descargar(url):
        if not url or "gone" in url:
            return None
        entregas["n"] += 1
        return _jpeg()

    monkeypatch.setattr(wa_media, "descargar_media", descargar)
    monkeypatch.setattr(settings, "wa_numeros_propios", f"{PROPIO},{EXPLORADOR}", raising=False)
    monkeypatch.setattr(settings, "wa_numeros_explorador", EXPLORADOR, raising=False)
    cfg._numeros_propios.cache_clear()
    yield entregas
    cfg._numeros_propios.cache_clear()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _llega(repo, wamid, body="", numero=NUM, media=True, grupo=None, ts=1760880000):
    p = {"id": wamid, "from": grupo or f"{numero}@c.us", "fromMe": False, "body": body,
         "type": "image" if media else "text", "timestamp": ts}
    if grupo:
        p["_data"] = {"key": {"participant": f"{numero}@c.us"}}
    if media:
        p.update({"hasMedia": True, "mediaUrl": "http://waha:3000/api/files/x.jpg",
                  "mimetype": "image/jpeg"})
    return ingest.handle_message({"event": "message", "session": "default", "payload": p}, repo)


def _llega_lid(repo, wamid, body="precio 120", alt=None, media=True, lid=LID):
    p = {"id": wamid, "from": lid, "fromMe": False, "body": body,
         "type": "image" if media else "text", "timestamp": 1760880000}
    if alt:
        p["_data"] = {"key": {"remoteJidAlt": f"{alt}@s.whatsapp.net"}}
    if media:
        p.update({"hasMedia": True, "mediaUrl": "http://waha:3000/api/files/x.jpg",
                  "mimetype": "image/jpeg"})
    return ingest.handle_message({"event": "message", "session": "default", "payload": p}, repo)


def _comercio(repo, **kw):
    kw.setdefault("activo", True)
    return repo.seed_comercio(id=COM, slug="kiosco", nombre="Kiosco Ana", **kw)


# ── 6 · Miniatura ────────────────────────────────────────────────────────────
def test_6_la_miniatura_con_permiso_whatsapp_da_200(client, repo, admin_token):
    _llega(repo, "m1", "precio 120")
    r = client.get("/admin/whatsapp/inbox/m1/media", headers=_auth(admin_token))
    assert r.status_code == 200
    assert r.headers["content-type"] == "image/jpeg"
    assert r.content[:2] == b"\xff\xd8"
    assert "no-store" in r.headers["cache-control"]


def test_6_sin_token_da_401(client, repo):
    _llega(repo, "m1")
    assert client.get("/admin/whatsapp/inbox/m1/media").status_code == 401


def test_6_un_agente_da_403(client, repo, agente_token):
    _llega(repo, "m1")
    assert client.get("/admin/whatsapp/inbox/m1/media", headers=_auth(agente_token)).status_code == 403


def test_6_un_token_de_comercio_o_de_comprador_tampoco(client, repo):
    _llega(repo, "m1")
    for token in (auth.make_comercio_token("com-1", "x@y.com"), auth.make_usuario_token("u-1", NUM)):
        assert client.get("/admin/whatsapp/inbox/m1/media", headers=_auth(token)).status_code == 403


def test_6_purgada_da_404(client, repo, admin_token):
    from app.services import wa_received

    _llega(repo, "m1")
    wa_received.purge_expired(repo, 0)
    r = client.get("/admin/whatsapp/inbox/m1/media", headers=_auth(admin_token))
    assert r.status_code == 404


def test_6_sin_foto_o_inexistente_da_404(client, repo, admin_token):
    _llega(repo, "m2", "solo texto", media=False)
    assert client.get("/admin/whatsapp/inbox/m2/media", headers=_auth(admin_token)).status_code == 404
    assert client.get("/admin/whatsapp/inbox/nadie/media", headers=_auth(admin_token)).status_code == 404


def test_6_un_media_path_adulterado_en_la_base_no_lee_afuera(client, repo, admin_token):
    _llega(repo, "m1")
    repo.wa_inbox["m1"]["media_path"] = "../../../../etc/hostname"
    assert client.get("/admin/whatsapp/inbox/m1/media", headers=_auth(admin_token)).status_code == 404


# ── La lista «sin dueño» ─────────────────────────────────────────────────────
def test_unknown_agrupa_por_numero_y_por_grupo_sin_telefonos_completos(client, repo, admin_token):
    _llega(repo, "a1", "precio 120")
    _llega(repo, "a2", "otra", media=False)
    _llega(repo, "b1", numero="59172222222")
    _llega(repo, "g1", numero="59173333333", grupo=GRUPO)

    r = client.get("/admin/whatsapp/unknown?days=30", headers=_auth(admin_token))
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 3
    # El teléfono completo no viaja NUNCA al panel (S4).
    assert NUM not in r.text and "59172222222" not in r.text and "59173333333" not in r.text

    tel = next(i for i in items if i["kind"] == "phone" and i["count"] == 2)
    assert tel["key"] == "a2"                          # el wa_message_id más reciente: opaco
    assert tel["phone_masked"] == "+591 7•••• 567" and tel["assignable"] is True
    assert "phone" not in tel and "lid" not in tel
    assert tel["at"] and {m["wa_message_id"] for m in tel["messages"]} == {"a1", "a2"}
    msg = {m["wa_message_id"]: m for m in tel["messages"]}
    assert msg["a1"]["has_media"] is True and msg["a1"]["body"] == "precio 120"
    assert msg["a2"]["has_media"] is False

    grupo = next(i for i in items if i["kind"] == "group")
    assert grupo["key"] == GRUPO and grupo["group_jid"] == GRUPO and grupo["count"] == 1
    assert "phone" not in grupo and "group_name" not in grupo and "assignable" not in grupo


def test_unknown_no_lista_lo_que_ya_tiene_dueno(client, repo, admin_token):
    _comercio(repo, whatsapp=NUM)
    _llega(repo, "a1", "precio Bs 120")
    assert client.get("/admin/whatsapp/unknown", headers=_auth(admin_token)).json()["items"] == []


def test_unknown_respeta_la_ventana_de_dias(client, repo, admin_token):
    _llega(repo, "viejo")
    repo.wa_inbox["viejo"]["created_at"] = "2020-01-01T00:00:00+00:00"
    _llega(repo, "nuevo", numero="59172222222")
    items = client.get("/admin/whatsapp/unknown?days=30", headers=_auth(admin_token)).json()["items"]
    assert [i["key"] for i in items] == ["nuevo"]


def test_unknown_un_lid_sin_numero_sale_sin_numero_y_no_asignable(client, repo, admin_token):
    _llega_lid(repo, "lid1", "hola", media=False)
    r = client.get("/admin/whatsapp/unknown", headers=_auth(admin_token))
    item = r.json()["items"][0]
    assert item["phone_masked"] is None and item["assignable"] is False
    assert "160138577080406" not in r.text                    # ni el LID viaja


def test_unknown_un_lid_aprendido_despues_se_resuelve_y_es_asignable(client, repo, admin_token):
    _llega_lid(repo, "lid1", "precio 120")
    repo.upsert_wa_lid(LID, NUM, "event")                      # el par se aprendió DESPUÉS
    item = client.get("/admin/whatsapp/unknown", headers=_auth(admin_token)).json()["items"][0]
    assert item["phone_masked"] == "+591 7•••• 567" and item["assignable"] is True


def test_unknown_los_numeros_de_urukU_y_el_explorador_no_son_asignables(client, repo, admin_token):
    _llega(repo, "ex1", "sin código", numero=EXPLORADOR)       # explorador sin código: queda sin dueño
    item = client.get("/admin/whatsapp/unknown", headers=_auth(admin_token)).json()["items"][0]
    assert item["assignable"] is False


def test_unknown_pide_permiso(client, repo, agente_token):
    assert client.get("/admin/whatsapp/unknown").status_code == 401
    assert client.get("/admin/whatsapp/unknown", headers=_auth(agente_token)).status_code == 403
    assert client.get("/admin/whatsapp/unknown?days=0", headers=_auth(auth.make_token("a@b.c", "admin"))
                      ).status_code == 422


# ── 7 · «Es de…» sobre un mensaje ────────────────────────────────────────────
def _asignar(client, token, wamid="a1", comercio_id=COM, label="Encargado/a"):
    return client.post(f"/admin/whatsapp/inbox/{wamid}/assign", headers=_auth(token),
                       json={"comercio_id": comercio_id, "label": label})


def test_7_asignar_autoriza_y_reprocesa_con_la_foto_local(client, repo, admin_token, _waha):
    _comercio(repo)
    _llega(repo, "a1", "precio 120")                 # foto + precio
    _llega(repo, "a2", "hola, ¿cuánto sale el plan?", media=False)
    assert _waha["n"] == 1
    # WAHA ya no tiene la foto: sólo queda la del disco privado.
    repo.wa_inbox["a1"]["raw"]["mediaUrl"] = "http://waha:3000/api/files/gone.jpg"

    r = _asignar(client, admin_token, "a2")

    assert r.status_code == 200, r.text
    assert r.json() == {"numero_masked": "+591 7•••• 567", "reprocessed": 2, "published": 1, "ignored": 1}
    assert NUM not in r.text                                  # ni de vuelta
    num = repo.comercio_numeros[0]
    assert num["numero"] == NUM and num["comercio_id"] == COM
    assert num["created_by"] == "admin@bermejolive.com" and num["etiqueta"] == "Encargado/a"
    pub = repo.publicaciones[0]
    assert pub["comercio_id"] == COM and pub["imagen_url"]
    nombre = pub["imagen_url"].rsplit("/", 1)[-1]
    assert (Path(settings.fotos_dir) / "kiosco" / "ofertas" / nombre).is_file()
    fila = repo.wa_inbox["a1"]
    assert fila["resultado"] == "publicada" and fila["assigned_by"] == "admin@bermejolive.com"
    assert fila["assigned_at"]
    assert repo.wa_inbox["a2"]["resultado"] == "ignorada"
    assert client.get("/admin/whatsapp/unknown", headers=_auth(admin_token)).json()["items"] == []


def test_s3_un_comercio_confiable_reprocesa_siempre_pendiente_sin_cuota_ni_cobro(client, repo, admin_token):
    _comercio(repo, confiable=True)
    _llega(repo, "a1", "precio 120")
    r = _asignar(client, admin_token)
    assert r.json()["published"] == 1
    assert repo.publicaciones[0]["estado"] == "pendiente"        # aunque el comercio sea confiable
    assert repo.publicaciones[0]["moderado_por"] is None
    assert repo.cargos_extra == []
    assert repo.difusion == []                                    # y no se encola a las redes


def test_s3_no_consume_cuota_ni_cobra_extra(client, repo, admin_token):
    """Un comercio que ya llegó al tope: lo reprocesado entra igual, sin cargo."""
    _comercio(repo)
    repo.planes["gratis"]["publicaciones_mes"] = 0
    repo.planes["gratis"]["permite_extras"] = True
    _llega(repo, "a1", "precio 120")
    r = _asignar(client, admin_token)
    assert r.json()["published"] == 1
    assert repo.cargos_extra == []


def test_7_sin_label_usa_none(client, repo, admin_token):
    _comercio(repo)
    _llega(repo, "a1", "precio 120")
    r = client.post("/admin/whatsapp/inbox/a1/assign", headers=_auth(admin_token), json={"comercio_id": COM})
    assert r.status_code == 200
    assert repo.comercio_numeros[0]["etiqueta"] is None


def test_7_el_numero_de_otro_comercio_da_409_y_no_mueve_nada(client, repo, admin_token):
    _comercio(repo)
    repo.seed_comercio(id=OTRO, slug="otro", nombre="Otro Local", activo=True)
    repo.agregar_numero_comercio(OTRO, NUM, "dueño", "alguien@x.com")
    _llega(repo, "a1", "precio 120")
    repo.comercio_numeros[0]["activo"] = True

    r = _asignar(client, admin_token)

    assert r.status_code == 409
    detalle = r.json()["detail"]
    assert detalle["codigo"] == "phone_owned_by_other"
    assert "Otro Local" in detalle["mensaje"]
    assert detalle["comercio"] == {"nombre": "Otro Local"}           # sin ids del otro comercio
    assert [(n["comercio_id"], n["created_by"]) for n in repo.comercio_numeros] == [(OTRO, "alguien@x.com")]


def test_7_el_whatsapp_cargado_de_otro_comercio_tambien_es_de_otro(client, repo, admin_token):
    _comercio(repo)
    repo.seed_comercio(id=OTRO, slug="otro", nombre="Otro Local", whatsapp=NUM, activo=True)
    repo.insert_wa_inbox({"wa_message_id": "a1", "wa_jid": f"{NUM}@c.us", "phone": NUM, "raw": {}})
    repo.marcar_wa_inbox("a1", "sin_comercio")
    assert _asignar(client, admin_token).status_code == 409
    assert repo.comercio_numeros == []


def test_7_un_numero_propio_da_400_own_number(client, repo, admin_token):
    _comercio(repo)
    repo.insert_wa_inbox({"wa_message_id": "p1", "wa_jid": f"{PROPIO}@c.us", "phone": PROPIO, "raw": {}})
    repo.marcar_wa_inbox("p1", "sin_comercio")
    r = _asignar(client, admin_token, "p1")
    assert r.status_code == 400 and r.json()["detail"]["codigo"] == "own_number"
    assert repo.comercio_numeros == []


def test_7_un_numero_invalido_da_400_invalid_number(client, repo, admin_token):
    _comercio(repo)
    repo.insert_wa_inbox({"wa_message_id": "i1", "wa_jid": "123@c.us", "phone": "123", "raw": {}})
    r = _asignar(client, admin_token, "i1")
    assert r.status_code == 400 and r.json()["detail"]["codigo"] == "invalid_number"


def test_7_un_mensaje_de_grupo_da_400(client, repo, admin_token):
    _comercio(repo)
    _llega(repo, "g1", "precio 120", grupo=GRUPO)
    r = _asignar(client, admin_token, "g1")
    assert r.status_code == 400 and r.json()["detail"]["codigo"] == "invalid_number"
    assert repo.comercio_numeros == []


def test_7_un_comercio_o_mensaje_inexistente_o_de_baja_da_404(client, repo, admin_token):
    _llega(repo, "a1", "precio 120")
    assert _asignar(client, admin_token, comercio_id=OTRO).status_code == 404
    repo.seed_comercio(id=OTRO, slug="baja", nombre="Baja", activo=False)
    assert _asignar(client, admin_token, comercio_id=OTRO).status_code == 404
    _comercio(repo)
    assert _asignar(client, admin_token, wamid="nadie").status_code == 404
    assert repo.comercio_numeros == []


def test_7_pide_permiso_whatsapp(client, repo, agente_token):
    _comercio(repo)
    _llega(repo, "a1", "precio 120")
    assert client.post("/admin/whatsapp/inbox/a1/assign", json={"comercio_id": COM}).status_code == 401
    assert _asignar(client, agente_token).status_code == 403
    assert client.post(f"/admin/whatsapp/groups/{GRUPO}/assign", json={"comercio_id": COM}).status_code == 401
    assert client.post(f"/admin/whatsapp/groups/{GRUPO}/assign", headers=_auth(agente_token),
                       json={"comercio_id": COM}).status_code == 403
    assert repo.comercio_numeros == []


def test_7_asignar_dos_veces_es_inofensivo(client, repo, admin_token):
    _comercio(repo)
    _llega(repo, "a1", "precio 120")
    assert _asignar(client, admin_token).json()["published"] == 1
    r = _asignar(client, admin_token)
    assert r.status_code == 200 and r.json()["reprocessed"] == 0      # nada más sin dueño
    assert len(repo.publicaciones) == 1 and len(repo.comercio_numeros) == 1


def test_7_un_mensaje_de_grupo_del_mismo_numero_no_se_reprocesa(client, repo, admin_token):
    _comercio(repo)
    _llega(repo, "a1", "texto", media=False)
    _llega(repo, "g1", "precio 120", grupo=GRUPO)                    # grupo sin atar
    _asignar(client, admin_token)
    assert repo.wa_inbox["g1"]["resultado"] == "sin_comercio"


def test_7_si_la_foto_se_purgo_igual_reprocesa(client, repo, admin_token):
    from app.services import wa_received

    _comercio(repo)
    _llega(repo, "a1", "precio 120")
    repo.wa_inbox["a1"]["raw"]["mediaUrl"] = "http://waha:3000/api/files/gone.jpg"
    wa_received.purge_expired(repo, 0)
    r = _asignar(client, admin_token)
    assert r.json()["published"] == 1
    assert repo.publicaciones[0]["imagen_url"] is None                # sin foto: ya no existe


def test_7_authorize_pasa_de_por_codigo_a_por_persona(repo):
    """Un número que se autorizó solo (por el código) pasa a ser de una persona."""
    _comercio(repo)
    repo.agregar_numero_comercio(COM, NUM, "se identificó con el código", "ingest-codigo")
    assert repo.authorize_phone_if_free(COM, NUM, "dueño", "admin@x.com") == "ok"
    assert repo.comercio_numeros[0]["created_by"] == "admin@x.com"
    assert repo.authorize_phone_if_free(COM, NUM, "dueño", "otro@x.com") == "already"
    assert repo.comercio_numeros[0]["created_by"] == "admin@x.com"


# ── S9 · comercio_id es un UUID ──────────────────────────────────────────────
def test_s9_un_comercio_id_que_no_es_uuid_da_422_no_500(client, repo, admin_token):
    _comercio(repo)
    _llega(repo, "a1", "precio 120")
    for malo in ("com-k", "no-es-uuid", "1; drop table comercios", " "):
        assert _asignar(client, admin_token, comercio_id=malo).status_code == 422
        assert client.post(f"/admin/whatsapp/groups/{GRUPO}/assign", headers=_auth(admin_token),
                           json={"comercio_id": malo}).status_code == 422
    assert repo.comercio_numeros == []


def test_s9_un_group_jid_raro_da_422(client, repo, admin_token):
    _comercio(repo)
    r = client.post("/admin/whatsapp/groups/no-es-un-grupo/assign", headers=_auth(admin_token),
                    json={"comercio_id": COM})
    assert r.status_code == 422


# ── S1 · LID sin número ──────────────────────────────────────────────────────
def test_s1_un_lid_sin_numero_no_se_asigna_400(client, repo, admin_token):
    _comercio(repo)
    _llega_lid(repo, "lid1", "precio 120")
    r = _asignar(client, admin_token, "lid1")
    assert r.status_code == 400 and r.json()["detail"]["codigo"] == "lid_not_assignable"
    assert repo.comercio_numeros == []


def test_s1_un_lid_aprendido_despues_se_asigna_y_reprocesa(client, repo, admin_token):
    _comercio(repo)
    _llega_lid(repo, "lid1", "precio 120")
    repo.upsert_wa_lid(LID, NUM, "event")
    r = _asignar(client, admin_token, "lid1")
    assert r.status_code == 200 and r.json()["published"] == 1
    assert repo.comercio_numeros[0]["numero"] == NUM
    assert repo.publicaciones[0]["comercio_id"] == COM


def test_s1_un_lid_que_resuelve_a_un_numero_propio_da_own_number(client, repo, admin_token):
    _comercio(repo)
    _llega_lid(repo, "lid1", "hola", media=False)
    repo.upsert_wa_lid(LID, PROPIO, "event")
    r = _asignar(client, admin_token, "lid1")
    assert r.status_code == 400 and r.json()["detail"]["codigo"] == "own_number"


# ── E-a · Explorador ─────────────────────────────────────────────────────────
def test_ea_la_foto_del_explorador_sin_codigo_se_guarda_y_queda_sin_dueno(client, repo, admin_token):
    _llega(repo, "ex1", "zapatillas Bs 200", numero=EXPLORADOR)
    fila = repo.wa_inbox["ex1"]
    assert fila["resultado"] == "sin_comercio" and fila["media_path"]
    assert client.get("/admin/whatsapp/inbox/ex1/media", headers=_auth(admin_token)).status_code == 200
    items = client.get("/admin/whatsapp/unknown", headers=_auth(admin_token)).json()["items"]
    assert [i["key"] for i in items] == ["ex1"]


def test_ea_con_un_codigo_inexistente_tambien_se_guarda(client, repo):
    _llega(repo, "ex2", "URUKU-ZZZ9 zapatillas Bs 200", numero=EXPLORADOR)
    assert repo.wa_inbox["ex2"]["resultado"] == "sin_comercio" and repo.wa_inbox["ex2"]["media_path"]


def test_ea_es_de_sobre_un_mensaje_del_explorador_da_400_explorer_message(client, repo, admin_token):
    _comercio(repo)
    _llega(repo, "ex1", "zapatillas Bs 200", numero=EXPLORADOR)
    r = _asignar(client, admin_token, "ex1")
    assert r.status_code == 400 and r.json()["detail"]["codigo"] == "explorer_message"
    assert repo.comercio_numeros == [] and repo.publicaciones == []


def test_ea_el_explorador_que_llega_como_lid_conocido_publica_por_codigo(repo):
    """Antes se descartaba como "propio 1-a-1"."""
    repo.upsert_wa_lid(LID, EXPLORADOR, "message")
    repo.seed_comercio(id=COM, slug="sol", nombre="Sol", codigo="K7M2", activo=True)
    _llega_lid(repo, "ex3", "URUKU-K7M2 remera Bs 90", media=False)
    pub = repo.publicaciones[0]
    assert pub["comercio_id"] == COM and pub["origen"] == "explorador" and pub["estado"] == "pendiente"
    assert repo.comercio_numeros == []


# ── Grupos ───────────────────────────────────────────────────────────────────
def _asignar_grupo(client, token, grupo=GRUPO, comercio_id=COM):
    return client.post(f"/admin/whatsapp/groups/{grupo}/assign", headers=_auth(token),
                       json={"comercio_id": comercio_id})


def test_grupo_asignar_ata_y_reprocesa_siempre_pendiente(client, repo, admin_token):
    _comercio(repo, confiable=True)
    _llega(repo, "g1", "precio 120", grupo=GRUPO)
    _llega(repo, "g2", "otra cosa sin precio", media=False, grupo=GRUPO)
    r = _asignar_grupo(client, admin_token)
    assert r.status_code == 200, r.text
    assert r.json() == {"reprocessed": 2, "published": 2, "ignored": 0}
    vinculo = repo.wa_grupos[GRUPO]
    assert vinculo["comercio_id"] == COM and vinculo["origen"] == "admin"
    assert vinculo["created_by"] == "admin@bermejolive.com"
    assert [p["estado"] for p in repo.publicaciones] == ["pendiente", "pendiente"]
    assert repo.cargos_extra == []


def test_grupo_atado_a_otro_comercio_activo_da_409_y_no_lo_roba(client, repo, admin_token):
    _comercio(repo)
    repo.seed_comercio(id=OTRO, slug="otro", nombre="Otro Local", activo=True)
    repo.vincular_grupo_comercio(GRUPO, OTRO, None, "codigo", "x")
    r = _asignar_grupo(client, admin_token)
    assert r.status_code == 409
    assert r.json()["detail"]["codigo"] == "group_owned_by_other"
    assert "Otro Local" in r.json()["detail"]["mensaje"]
    assert repo.wa_grupos[GRUPO]["comercio_id"] == OTRO


def test_grupo_atado_a_un_comercio_de_baja_no_se_roba(client, repo, admin_token):
    """Soltar el vínculo viejo sería un DELETE físico (AGENTS.md: nunca). 409 y queda
    como estaba; se suelta a mano desde la ficha del comercio de baja."""
    _comercio(repo)
    repo.seed_comercio(id=OTRO, slug="otro", nombre="Otro", activo=False)
    repo.vincular_grupo_comercio(GRUPO, OTRO, None, "codigo", "x")
    r = _asignar_grupo(client, admin_token)
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "group_owned_by_other"
    assert repo.wa_grupos[GRUPO]["comercio_id"] == OTRO


def test_grupo_ya_atado_al_mismo_comercio_es_idempotente(client, repo, admin_token):
    _comercio(repo)
    repo.vincular_grupo_comercio(GRUPO, COM, None, "codigo", "x")
    r = _asignar_grupo(client, admin_token)
    assert r.status_code == 200 and r.json()["reprocessed"] == 0
    assert repo.wa_grupos[GRUPO]["origen"] == "codigo"             # no se repisó


def test_grupo_comercio_inexistente_404(client, repo, admin_token):
    assert _asignar_grupo(client, admin_token).status_code == 404
    assert GRUPO not in repo.wa_grupos


# ── S5 · authorize_phone_if_free sin carrera (repo real contra un cliente de mentira) ──
class _Resp:
    def __init__(self, data):
        self.data = data


class _Q:
    """Un cliente PostgREST mínimo: sólo lo que usa `authorize_phone_if_free`."""

    def __init__(self, db, tabla):
        self.db, self.tabla, self.op, self.payload, self.filtros = db, tabla, "select", None, {}

    def select(self, *_a, **_k):
        return self

    def insert(self, row):
        self.op, self.payload = "insert", row
        return self

    def update(self, patch):
        self.op, self.payload = "update", patch
        return self

    def eq(self, col, val):
        self.filtros[col] = val
        return self

    def limit(self, *_a):
        return self

    def execute(self):
        filas = self.db.tablas[self.tabla]
        if self.op == "insert":
            if self.db.antes_de_insertar:
                self.db.antes_de_insertar()
                self.db.antes_de_insertar = None
            if any(f["numero"] == self.payload["numero"] for f in filas):
                raise RuntimeError("duplicate key value violates unique constraint (23505)")
            filas.append({"id": f"n{len(filas) + 1}", **self.payload})
            return _Resp([filas[-1]])
        coinciden = [f for f in filas if all(f.get(k) == v for k, v in self.filtros.items())]
        if self.op == "update":
            for f in coinciden:
                f.update(self.payload)
        return _Resp([dict(f) for f in coinciden])


class _Db:
    def __init__(self):
        self.tablas = {"comercio_numeros": []}
        self.antes_de_insertar = None

    def table(self, nombre):
        return _Q(self, nombre)


def _repo_real_sin_dueno(db, monkeypatch, _duenos=None):
    from app.db.repository import SupabaseRepo

    repo = SupabaseRepo(db)
    # `get_comercio_por_numero` mira comercios y números; acá sólo importa quién es el dueño.
    monkeypatch.setattr(repo, "get_comercio_por_numero",
                        lambda numero: _dueno_de(db, numero))
    return repo


def _dueno_de(db, numero):
    for f in db.tablas["comercio_numeros"]:
        if f["numero"] == numero and f.get("activo"):
            return {"id": f["comercio_id"], "nombre": "X"}
    return None


def test_s5_otro_comercio_toma_el_numero_entre_la_lectura_y_el_insert_da_owned_by_other(monkeypatch):
    db = _Db()
    repo = _repo_real_sin_dueno(db, monkeypatch, [])

    def otro_se_adelanta():
        db.tablas["comercio_numeros"].append(
            {"id": "n0", "comercio_id": OTRO, "numero": NUM, "activo": True, "created_by": "otro@x.com"})

    db.antes_de_insertar = otro_se_adelanta
    assert repo.authorize_phone_if_free(COM, NUM, "dueño", "admin@x.com") == "owned_by_other"
    # Nada se movió: sigue siendo del otro.
    assert [(f["comercio_id"], f["created_by"]) for f in db.tablas["comercio_numeros"]] == [(OTRO, "otro@x.com")]


def test_s5_sin_carrera_inserta_y_no_usa_upsert(monkeypatch):
    db = _Db()
    repo = _repo_real_sin_dueno(db, monkeypatch, [])
    assert repo.authorize_phone_if_free(COM, NUM, "dueño", "admin@x.com") == "ok"
    assert db.tablas["comercio_numeros"][0]["comercio_id"] == COM
    assert repo.authorize_phone_if_free(COM, NUM, "dueño", "admin@x.com") == "already"


def test_s5_toma_una_fila_de_baja_con_update_condicional(monkeypatch):
    db = _Db()
    db.tablas["comercio_numeros"].append(
        {"id": "n9", "comercio_id": OTRO, "numero": NUM, "activo": False, "created_by": "viejo@x.com"})
    repo = _repo_real_sin_dueno(db, monkeypatch, [])
    assert repo.authorize_phone_if_free(COM, NUM, None, "admin@x.com") == "ok"
    fila = db.tablas["comercio_numeros"][0]
    assert fila["comercio_id"] == COM and fila["activo"] is True and fila["created_by"] == "admin@x.com"
