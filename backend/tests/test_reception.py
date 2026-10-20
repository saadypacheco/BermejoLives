"""E1 · Recepción (docs/grupos-por-comercio.md §7.2 y §10.1, criterios 6 y 7).

  GET  /admin/whatsapp/inbox/{wa_message_id}/media   la foto del disco privado
  GET  /admin/whatsapp/unknown?days=30               lo que no tiene dueño
  POST /admin/whatsapp/numbers/{phone}/assign        «Es de…»
"""
from io import BytesIO
from pathlib import Path

import pytest

from app.core import auth
from app.core import config as cfg
from app.core.config import settings
from app.services import ingest

PROPIO = "59175314737"
NUM = "59171234567"
GRUPO = "120363111222333@g.us"


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
    monkeypatch.setattr(settings, "wa_numeros_propios", PROPIO, raising=False)
    monkeypatch.setattr(settings, "wa_numeros_explorador", "", raising=False)
    cfg._numeros_propios.cache_clear()
    yield entregas
    cfg._numeros_propios.cache_clear()


def _auth(token):
    return {"Authorization": f"Bearer {token}"}


def _llega(repo, wamid, body="", numero=NUM, media=True, grupo=None):
    p = {"id": wamid, "from": grupo or f"{numero}@c.us", "fromMe": False, "body": body,
         "type": "image" if media else "text", "timestamp": 1760880000}
    if grupo:
        p["_data"] = {"key": {"participant": f"{numero}@c.us"}}
    if media:
        p.update({"hasMedia": True, "mediaUrl": "http://waha:3000/api/files/x.jpg",
                  "mimetype": "image/jpeg"})
    return ingest.handle_message({"event": "message", "session": "default", "payload": p}, repo)


def _comercio(repo, **kw):
    kw.setdefault("activo", True)
    return repo.seed_comercio(id="com-k", slug="kiosco", nombre="Kiosco Ana", **kw)


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
def test_unknown_agrupa_por_numero_y_por_grupo(client, repo, admin_token):
    _llega(repo, "a1", "precio 120")
    _llega(repo, "a2", "otra", media=False)
    _llega(repo, "b1", numero="59172222222")
    _llega(repo, "g1", numero="59173333333", grupo=GRUPO)

    r = client.get("/admin/whatsapp/unknown?days=30", headers=_auth(admin_token))
    assert r.status_code == 200
    items = r.json()["items"]
    por_clave = {(i["kind"], i["key"]): i for i in items}

    tel = por_clave[("phone", NUM)]
    assert tel["phone"] == NUM and tel["phone_masked"] == "+591 7•••• 567"
    assert tel["count"] == 2 and tel["at"]
    assert {m["wa_message_id"] for m in tel["messages"]} == {"a1", "a2"}
    msg = {m["wa_message_id"]: m for m in tel["messages"]}
    assert msg["a1"]["has_media"] is True and msg["a1"]["body"] == "precio 120"
    assert msg["a2"]["has_media"] is False
    assert por_clave[("phone", "59172222222")]["count"] == 1

    grupo = por_clave[("group", GRUPO)]
    assert grupo["group_jid"] == GRUPO and grupo["count"] == 1
    assert "phone" not in grupo
    assert len(items) == 3


def test_unknown_no_lista_lo_que_ya_tiene_dueno(client, repo, admin_token):
    _comercio(repo, whatsapp=NUM)
    _llega(repo, "a1", "precio Bs 120")
    assert client.get("/admin/whatsapp/unknown", headers=_auth(admin_token)).json()["items"] == []


def test_unknown_respeta_la_ventana_de_dias(client, repo, admin_token):
    _llega(repo, "viejo")
    repo.wa_inbox["viejo"]["created_at"] = "2020-01-01T00:00:00+00:00"
    _llega(repo, "nuevo", numero="59172222222")
    items = client.get("/admin/whatsapp/unknown?days=30", headers=_auth(admin_token)).json()["items"]
    assert [i["key"] for i in items] == ["59172222222"]


def test_unknown_un_lid_sin_numero_sale_sin_phone(client, repo, admin_token):
    ev = {"event": "message", "session": "default", "payload": {
        "id": "lid1", "from": "160138577080406@lid", "fromMe": False, "body": "hola",
        "type": "text", "timestamp": 1760880000}}
    ingest.handle_message(ev, repo)
    items = client.get("/admin/whatsapp/unknown", headers=_auth(admin_token)).json()["items"]
    assert items[0]["phone"] is None and items[0]["lid"] == "160138577080406@lid"


def test_unknown_pide_permiso(client, repo, agente_token):
    assert client.get("/admin/whatsapp/unknown").status_code == 401
    assert client.get("/admin/whatsapp/unknown", headers=_auth(agente_token)).status_code == 403
    assert client.get("/admin/whatsapp/unknown?days=0", headers=_auth(auth.make_token("a@b.c", "admin"))
                      ).status_code == 422


# ── 7 · «Es de…» ─────────────────────────────────────────────────────────────
def _asignar(client, token, comercio_id="com-k", phone=NUM, label="Encargado/a"):
    return client.post(f"/admin/whatsapp/numbers/{phone}/assign", headers=_auth(token),
                       json={"comercio_id": comercio_id, "label": label})


def test_7_asignar_autoriza_y_reprocesa_con_la_foto_local(client, repo, admin_token, _waha):
    _comercio(repo)
    _llega(repo, "a1", "precio 120")                 # foto + precio
    _llega(repo, "a2", "hola, ¿cuánto sale el plan?", media=False)
    assert _waha["n"] == 1
    # WAHA ya no tiene la foto: sólo queda la del disco privado.
    repo.wa_inbox["a1"]["raw"]["mediaUrl"] = "http://waha:3000/api/files/gone.jpg"

    r = _asignar(client, admin_token)

    assert r.status_code == 200, r.text
    assert r.json() == {"numero": NUM, "reprocessed": 2, "published": 1, "ignored": 1}
    # El número quedó autorizado por QUIEN lo asignó.
    num = repo.comercio_numeros[0]
    assert num["numero"] == NUM and num["comercio_id"] == "com-k"
    assert num["created_by"] == "admin@bermejolive.com" and num["etiqueta"] == "Encargado/a"
    # La publicación salió con la foto copiada del disco privado.
    pub = repo.publicaciones[0]
    assert pub["comercio_id"] == "com-k" and pub["imagen_url"]
    assert Path(settings.fotos_dir).name in pub["imagen_url"] or "/fotos/" in pub["imagen_url"]
    nombre = pub["imagen_url"].rsplit("/", 1)[-1]
    assert (Path(settings.fotos_dir) / "kiosco" / "ofertas" / nombre).is_file()
    # La fila queda con quién y cuándo.
    fila = repo.wa_inbox["a1"]
    assert fila["resultado"] == "publicada" and fila["assigned_by"] == "admin@bermejolive.com"
    assert fila["assigned_at"]
    assert repo.wa_inbox["a2"]["resultado"] == "ignorada"
    # Ya no figura sin dueño.
    assert client.get("/admin/whatsapp/unknown", headers=_auth(admin_token)).json()["items"] == []


def test_7_un_comercio_confiable_con_numero_asignado_por_el_admin_publica_directo(client, repo, admin_token):
    _comercio(repo, confiable=True)
    _llega(repo, "a1", "precio 120")
    r = _asignar(client, admin_token)
    assert r.json()["published"] == 1
    assert repo.publicaciones[0]["estado"] == "aprobado"


def test_7_sin_label_usa_none(client, repo, admin_token):
    _comercio(repo)
    r = client.post(f"/admin/whatsapp/numbers/{NUM}/assign", headers=_auth(admin_token),
                    json={"comercio_id": "com-k"})
    assert r.status_code == 200
    assert repo.comercio_numeros[0]["etiqueta"] is None


def test_7_el_numero_de_otro_comercio_da_409_y_no_mueve_nada(client, repo, admin_token):
    _comercio(repo)
    repo.seed_comercio(id="com-o", slug="otro", nombre="Otro Local", activo=True)
    repo.agregar_numero_comercio("com-o", NUM, "dueño", "alguien@x.com")
    _llega(repo, "a1", "precio 120", numero="59172222222")        # otra cosa sin dueño

    r = _asignar(client, admin_token)

    assert r.status_code == 409
    detalle = r.json()["detail"]
    assert detalle["codigo"] == "phone_owned_by_other"
    assert "Otro Local" in detalle["mensaje"]
    assert [(n["comercio_id"], n["created_by"]) for n in repo.comercio_numeros] == [("com-o", "alguien@x.com")]
    assert repo.publicaciones == []


def test_7_el_whatsapp_cargado_de_otro_comercio_tambien_es_de_otro(client, repo, admin_token):
    _comercio(repo)
    repo.seed_comercio(id="com-o", slug="otro", nombre="Otro Local", whatsapp=NUM, activo=True)
    assert _asignar(client, admin_token).status_code == 409
    assert repo.comercio_numeros == []


def test_7_un_numero_propio_da_400(client, repo, admin_token):
    _comercio(repo)
    r = _asignar(client, admin_token, phone=PROPIO)
    assert r.status_code == 400 and "URUKU" in r.json()["detail"]
    assert repo.comercio_numeros == []


def test_7_un_numero_invalido_da_400(client, repo, admin_token):
    _comercio(repo)
    assert _asignar(client, admin_token, phone="123").status_code == 400


def test_7_un_comercio_inexistente_o_de_baja_da_404(client, repo, admin_token):
    assert _asignar(client, admin_token, comercio_id="nadie").status_code == 404
    repo.seed_comercio(id="com-b", slug="baja", nombre="Baja", activo=False)
    assert _asignar(client, admin_token, comercio_id="com-b").status_code == 404
    assert repo.comercio_numeros == []


def test_7_pide_permiso_whatsapp(client, repo, agente_token):
    _comercio(repo)
    assert client.post(f"/admin/whatsapp/numbers/{NUM}/assign", json={"comercio_id": "com-k"}).status_code == 401
    assert _asignar(client, agente_token).status_code == 403
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
    _llega(repo, "g1", "precio 120", grupo=GRUPO)                    # grupo sin atar
    r = _asignar(client, admin_token)
    assert r.json()["reprocessed"] == 0
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
    repo.agregar_numero_comercio("com-k", NUM, "se identificó con el código", "ingest-codigo")
    assert repo.authorize_phone_if_free("com-k", NUM, "dueño", "admin@x.com") == "ok"
    assert repo.comercio_numeros[0]["created_by"] == "admin@x.com"
    assert repo.authorize_phone_if_free("com-k", NUM, "dueño", "otro@x.com") == "already"
    assert repo.comercio_numeros[0]["created_by"] == "admin@x.com"
