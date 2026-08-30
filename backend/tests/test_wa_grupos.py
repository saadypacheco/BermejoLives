"""Crear el grupo de WhatsApp de un comercio desde el sistema.

Lo que se prueba acá NO es que WhatsApp funcione —eso no se puede desde un
test— sino las decisiones que se toman alrededor: qué se manda, qué se
rechaza antes de molestar a WhatsApp, y qué pasa cuando la respuesta no es la
esperada. Un grupo creado y sin atar es el peor resultado posible: el
comerciante lo ve aparecer en su teléfono y manda ofertas al vacío.
"""
import pytest

from app.services import wa_grupos


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ─────────────────────────────── el identificador del grupo
def test_encuentra_el_id_en_las_formas_que_devuelve_waha():
    """WAHA cambió la forma entre versiones. Si mañana cambia otra vez, esto
    sigue encontrándolo en vez de dejar el grupo creado y sin atar."""
    assert wa_grupos.id_del_grupo({"id": "12036@g.us"}) == "12036@g.us"
    assert wa_grupos.id_del_grupo({"id": {"_serialized": "12036@g.us"}}) == "12036@g.us"
    assert wa_grupos.id_del_grupo({"gid": "12036@g.us"}) == "12036@g.us"
    assert wa_grupos.id_del_grupo({"chatId": "12036@g.us"}) == "12036@g.us"


def test_no_confunde_un_chat_de_persona_con_un_grupo():
    """Los grupos terminan en @g.us; las personas en @c.us. Atar un chat 1-a-1
    haría que el comercio reciba como propio todo lo que le escriban."""
    assert wa_grupos.id_del_grupo({"id": "59170000007@c.us"}) is None
    assert wa_grupos.id_del_grupo({}) is None


# ─────────────────────────────── antes de molestar a WhatsApp
def test_sin_waha_configurado_no_intenta(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "waha_api_key", "", raising=False)
    with pytest.raises(wa_grupos.GrupoError, match="no está configurado"):
        wa_grupos.crear_grupo("X", ["59170000007"])


def test_sin_numeros_validos_no_crea_un_grupo_vacio(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "waha_api_key", "k", raising=False)
    monkeypatch.setattr(settings, "waha_base_url", "http://waha:3000", raising=False)
    with pytest.raises(wa_grupos.GrupoError, match="Ningún número válido"):
        wa_grupos.crear_grupo("X", ["no-es-un-numero"])


# ─────────────────────────────── el endpoint
def test_crear_grupo_ata_el_comercio(client, repo, admin_token, monkeypatch):
    c = repo.seed_comercio(slug="mendo", nombre="Mendo", whatsapp="59170000007")
    monkeypatch.setattr(wa_grupos, "crear_grupo", lambda n, p: {"id": "120363@g.us"})
    monkeypatch.setattr(wa_grupos, "numeros_de_grupo", lambda: ["59170000099"])

    r = client.post(f"/admin/comercio/{c['id']}/grupo", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["grupo_jid"] == "120363@g.us"
    # Atado en el mismo acto: no hay ventana en la que el grupo exista sin
    # saberse de quién es.
    assert repo.wa_grupos["120363@g.us"]["comercio_id"] == c["id"]


def test_sin_whatsapp_no_se_crea_el_grupo(client, repo, admin_token):
    """Un grupo sin el comerciante es URUKU hablando sola."""
    c = repo.seed_comercio(slug="x", nombre="X", whatsapp=None)
    r = client.post(f"/admin/comercio/{c['id']}/grupo", headers=_h(admin_token))
    assert r.status_code == 400


def test_no_crea_un_segundo_grupo_para_el_mismo_comercio(client, repo, admin_token, monkeypatch):
    c = repo.seed_comercio(slug="mendo", nombre="Mendo", whatsapp="59170000007")
    repo.vincular_grupo_comercio("120363@g.us", c["id"], None, "auto", "yo")
    monkeypatch.setattr(wa_grupos, "crear_grupo", lambda n, p: {"id": "otro@g.us"})

    r = client.post(f"/admin/comercio/{c['id']}/grupo", headers=_h(admin_token))
    assert r.status_code == 409


def test_si_waha_no_devuelve_el_id_se_avisa_fuerte(client, repo, admin_token, monkeypatch):
    """El grupo QUEDÓ creado en WhatsApp. Devolver 200 acá dejaría un grupo
    huérfano donde el comerciante manda ofertas que no llegan a ningún lado."""
    c = repo.seed_comercio(slug="mendo", nombre="Mendo", whatsapp="59170000007")
    monkeypatch.setattr(wa_grupos, "crear_grupo", lambda n, p: {"raro": True})
    monkeypatch.setattr(wa_grupos, "numeros_de_grupo", lambda: [])

    r = client.post(f"/admin/comercio/{c['id']}/grupo", headers=_h(admin_token))
    assert r.status_code == 502
    assert "atalo a mano" in r.json()["detail"]


def test_si_whatsapp_rechaza_no_se_ata_nada(client, repo, admin_token, monkeypatch):
    c = repo.seed_comercio(slug="mendo", nombre="Mendo", whatsapp="59170000007")

    def explota(n, p):
        raise wa_grupos.GrupoError("sesión caída")
    monkeypatch.setattr(wa_grupos, "crear_grupo", explota)
    monkeypatch.setattr(wa_grupos, "numeros_de_grupo", lambda: [])

    r = client.post(f"/admin/comercio/{c['id']}/grupo", headers=_h(admin_token))
    assert r.status_code == 502
    assert repo.wa_grupos == {}
