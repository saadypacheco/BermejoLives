"""La autorización para redes: bitácora, vigente, retiro con efectos, comerciante y alta de campo."""
import pytest

from app.core import auth
from app.services import content_consent
from tests.conftest import comercio_token
from tests.content_helpers import AGENTE, comercio, h, pieza


@pytest.fixture
def token():
    return auth.make_token("ana@uruku.bo", rol="admin")


def _put(client, token, cid="com-1", **body):
    return client.put(f"/admin/content/merchants/{cid}/social-consent", headers=h(token),
                      json={"granted": True, "via": "admin", **body})


def test_sin_registros_todo_es_null(crepo, repo):
    assert content_consent.respuesta(content_consent.vigente(crepo, "com-1")) == {
        "granted": None, "via": None, "recorded_at": None, "recorded_by": None, "note": None}
    assert not content_consent.esta_autorizado(crepo, "com-1")


def test_la_bitacora_guarda_cada_cambio_y_la_vigente_es_la_ultima(client, repo, crepo, token):
    comercio(repo)
    assert _put(client, token, via="whatsapp_reply", note="me lo dijo por WhatsApp").json()["via"] == "whatsapp_reply"
    r = _put(client, token, granted=False, via="admin")
    assert "consent" in r.json()
    _put(client, token, via="subscription")
    hist = client.get("/admin/content/merchants/com-1/social-consent/history", headers=h(token)).json()["items"]
    assert [(i["granted"], i["via"]) for i in hist] == [(True, "subscription"), (False, "admin"), (True, "whatsapp_reply")]
    assert hist[2]["note"] == "me lo dijo por WhatsApp" and hist[0]["recorded_by"] == "ana@uruku.bo"
    assert content_consent.esta_autorizado(crepo, "com-1")


def test_via_invalida_es_400_y_comercio_inexistente_404(client, repo, token):
    comercio(repo)
    assert _put(client, token, via="agent_signup").json()["detail"] == "Vía no válida"
    assert _put(client, token, cid="nada").status_code == 404
    assert _put(client, token, note="x" * 301).status_code == 400


def test_quien_tiene_pagos_tambien_la_registra_y_un_moderador_no(client, repo):
    comercio(repo)
    assert _put(client, auth.make_token("c@u", roles=["x"], permisos=["pagos"])).status_code == 200
    assert _put(client, auth.make_token("m@u", rol="moderador")).status_code == 403


def test_retirar_saltea_las_piezas_vivas_y_lista_lo_publicado(client, repo, crepo, token):
    comercio(repo)
    content_consent.registrar(crepo, "com-1", True, "admin", "x")
    en_cola = pieza(crepo, status="queued")
    aprobada = pieza(crepo, status="approved", dia=en_cola_dia(1))
    crepo.insert_posts([{"piece_id": aprobada["id"], "network": n, "ref_tag": f"{n}-x"} for n in ("tiktok", "instagram")])
    publicada = pieza(crepo, status="published", dia=en_cola_dia(-5))
    crepo.insert_posts([{"piece_id": publicada["id"], "network": "tiktok", "ref_tag": "tt-x"}])
    p2 = [x for x in crepo.posts.values() if x["piece_id"] == publicada["id"]][0]
    p2.update({"status": "posted", "post_url": "https://www.tiktok.com/@x/video/1", "posted_at": "2026-01-01"})
    r = _put(client, token, granted=False).json()
    assert r["consent"]["granted"] is False and r["pieces_skipped"] == 2
    assert r["published_posts"] == [{"network": "tiktok", "post_url": "https://www.tiktok.com/@x/video/1"}]
    assert crepo.pieces[en_cola["id"]]["status"] == "skipped" and crepo.pieces[en_cola["id"]]["skip_reason"] == "consent_revoked"
    assert crepo.pieces[aprobada["id"]]["status"] == "skipped"
    assert crepo.pieces[publicada["id"]]["status"] == "published"
    assert {x["status"] for x in crepo.posts.values() if x["piece_id"] == aprobada["id"]} == {"skipped"}


def en_cola_dia(n):
    from datetime import timedelta
    from tests.content_helpers import hoy
    return hoy() + timedelta(days=n + 1)


def test_el_agente_registra_la_visita(client, repo, crepo, agente_token):
    comercio(repo, cargado_por=AGENTE)
    r = client.put("/campo/mis-comercios/com-1/social-consent", headers=h(agente_token), json={"granted": True, "note": "en la puerta"})
    assert r.status_code == 200 and r.json()["via"] == "agent_visit" and r.json()["recorded_by"] == AGENTE
    ajeno = comercio(repo, "com-2", cargado_por="otro@uruku.bo", ciudad_id="ciu-santa-cruz")
    assert client.put(f"/campo/mis-comercios/{ajeno['id']}/social-consent", headers=h(agente_token), json={"granted": True}).status_code == 404


def test_el_comerciante_lee_y_cambia_su_autorizacion(client, repo, crepo):
    comercio(repo)
    t = comercio_token("com-1")
    assert client.get("/comercio/social-consent", headers=h(t)).json()["granted"] is None
    r = client.put("/comercio/social-consent", headers=h(t), json={"granted": True})
    assert r.status_code == 200 and r.json()["via"] == "merchant_panel" and r.json()["recorded_by"].startswith("comercio:")
    assert client.put("/comercio/social-consent", headers=h(t), json={"granted": False}).json()["granted"] is False
    assert client.get("/comercio/social-consent").status_code == 401


def test_un_comercio_dado_de_baja_por_el_admin_no_puede_cambiarla(client, repo, crepo):
    comercio(repo, activo=False, baja_motivo="admin")
    t = comercio_token("com-1")
    r = client.put("/comercio/social-consent", headers=h(t), json={"granted": True})
    assert r.status_code == 403 and "dado de baja" in r.json()["detail"]
    assert client.get("/comercio/social-consent", headers=h(t)).status_code == 200      # leer sí


def _alta(client, agente_token, **extra):
    return client.post("/campo/comercio", headers=h(agente_token), data={
        "nombre": "Boutique Sol", "whatsapp": "59170002222", "rubro_slugs": ["gomeria"], "lat": "-22.7", "lng": "-64.3", **extra})


def test_el_alta_de_campo_con_la_casilla_de_redes_queda_en_la_bitacora(client, repo, crepo, agente_token):
    r = _alta(client, agente_token, social_consent="true")
    assert r.status_code == 200, r.text
    cid = r.json()["comercio"]["id"]
    fila = content_consent.vigente(crepo, cid)
    assert fila["granted"] is True and fila["via"] == "agent_signup" and fila["recorded_by"] == AGENTE


def test_el_alta_de_campo_sin_la_casilla_no_registra_nada(client, repo, crepo, agente_token):
    assert _alta(client, agente_token).status_code == 200
    assert crepo.consents == []


def test_si_falla_la_bitacora_el_alta_no_se_cae(client, repo, crepo, agente_token, monkeypatch):
    def roto(row):
        raise RuntimeError("base caída")
    monkeypatch.setattr(crepo, "add_consent", roto)
    assert _alta(client, agente_token, social_consent="true").status_code == 200
