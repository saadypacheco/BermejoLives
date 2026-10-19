"""Comercio GESTIONADO (en el alcance de la integración de marketing) y regresión de la ingesta.

`services/ingest.py` es el corazón del producto: acá se prueba, lado a lado, que
  - un comercio gestionado queda SIEMPRE pendiente, sin difusión, sin auto-aprobación de IA, y que una edición suya
    vuelve a pendiente y aprobarlo desde el panel es un 409 salvo override de admin registrado;
  - y que un comercio NO gestionado se comporta EXACTAMENTE igual que antes (confiable → aprobado directo + difusión;
    no confiable → pendiente; fusión de foto + precio; explorador; idempotencia).
"""
from __future__ import annotations

import pytest

from app.core.config import settings
from app.services import ingest, integracion, revision_ia
from tests.conftest import comercio_token
from tests.test_ingest import GRUPO, _evento, _evento_grupo

NUM = "59170000009"


@pytest.fixture(autouse=True)
def _redes_por_defecto(monkeypatch):
    # El canal de WhatsApp no se encola (WAHA sólo lee); Facebook e Instagram sí, para planes con `redes`.
    monkeypatch.setattr(settings, "wa_solo_lectura", True)


def _gestionar(repo, comercio_id):
    cli = integracion.emitir_clave(repo, "Marketing", None, "test")
    repo.integracion_set_comercio(cli["grupo_id"], comercio_id, True, "test")
    return cli


def _comercio(repo, id_, *, confiable=True, plan="destacado", whatsapp=None, **kw):
    return repo.seed_comercio(id=id_, slug=id_, nombre=id_.upper(), whatsapp=whatsapp or (NUM if id_ == "com-a" else f"5917{abs(hash(id_)) % 10**7:07d}"),
                              wa_jid=None, activo=True, confiable=confiable, plan=plan, **kw)


@pytest.fixture(autouse=True)
def _foto_baja_bien(monkeypatch):
    """La foto de WAHA no se baja en los tests: `guardar_imagen_publicacion` devuelve una URL fija."""
    from app.services import wa_media

    monkeypatch.setattr(wa_media, "guardar_imagen_publicacion", lambda slug, url: f"https://fotos.test/{slug}/x.jpg")


# ═════════════════════════════════════════════════ regresión: los NO gestionados siguen igual
def test_confiable_no_gestionado_publica_directo_y_encola_a_las_redes(repo):
    _comercio(repo, "com-a")
    res = ingest.handle_message(_evento(wamid="r-1", jid=f"{NUM}@c.us"), repo)
    assert res["estado"] == "aprobado"
    pub = repo.publicaciones[0]
    assert pub["estado"] == "aprobado" and pub["moderado_por"] == "auto-confiable"
    assert pub["approved_at"] is not None and pub["moderado_at"] is not None
    assert {f["destino"] for f in repo.difusion} == {"facebook", "instagram"}
    assert all(f["solicitado_por"] is None and f["texto_override"] is None for f in repo.difusion)


def test_no_confiable_no_gestionado_sigue_pendiente_sin_difusion(repo):
    _comercio(repo, "com-a", confiable=False)
    res = ingest.handle_message(_evento(wamid="r-2", jid=f"{NUM}@c.us"), repo)
    assert res["estado"] == "pendiente"
    assert repo.publicaciones[0]["estado"] == "pendiente" and repo.publicaciones[0]["moderado_por"] is None
    assert repo.difusion == []


def test_que_otro_comercio_este_gestionado_no_cambia_a_los_demas(repo):
    """Gestionar a B no toca a A: el alcance es por comercio, no global."""
    _comercio(repo, "com-a")
    b = _comercio(repo, "com-b")
    _gestionar(repo, b["id"])
    res = ingest.handle_message(_evento(wamid="r-3", jid=f"{NUM}@c.us"), repo)
    assert res["estado"] == "aprobado" and repo.publicaciones[0]["moderado_por"] == "auto-confiable"
    assert len(repo.difusion) == 2


def test_un_comercio_que_sale_del_alcance_vuelve_a_su_flujo_de_siempre(repo):
    a = _comercio(repo, "com-a")
    cli = _gestionar(repo, a["id"])
    assert ingest.handle_message(_evento(wamid="r-4", jid=f"{NUM}@c.us"), repo)["estado"] == "pendiente"
    repo.integracion_set_comercio(cli["grupo_id"], a["id"], False, "test")          # el admin lo saca del alcance
    assert ingest.handle_message(_evento(wamid="r-5", jid=f"{NUM}@c.us"), repo)["estado"] == "aprobado"


def test_numero_por_codigo_y_codigo_siguen_a_cola_aunque_el_comercio_sea_confiable(repo):
    _comercio(repo, "com-a")
    res = ingest.handle_message(_evento(wamid="r-6", jid="59170000555@c.us", body="URUKU-" + repo.comercios["com-a"]["codigo"] + " oferta taladro 300"), repo)
    assert res["estado"] == "pendiente"
    assert repo.publicaciones[0]["identidad_origen"] == "codigo"
    assert repo.publicaciones[0]["remitente_rol"] == "third_party"


def test_duplicado_sigue_siendo_idempotente(repo):
    _comercio(repo, "com-a")
    ingest.handle_message(_evento(wamid="r-7", jid=f"{NUM}@c.us"), repo)
    assert ingest.handle_message(_evento(wamid="r-7", jid=f"{NUM}@c.us"), repo).get("duplicate") is True
    assert len(repo.publicaciones) == 1


def test_fusion_de_foto_y_precio_sigue_funcionando_para_un_no_gestionado_aunque_la_previa_este_aprobada(repo):
    """Comportamiento existente (no se toca): la segunda mitad se junta con la anterior aprobada."""
    _comercio(repo, "com-a")
    ingest.handle_message({"event": "message", "session": "s", "payload": {
        "id": "f-1", "from": f"{NUM}@c.us", "fromMe": False, "body": "", "type": "image", "hasMedia": True,
        "mediaUrl": "http://waha/f.jpg", "mimetype": "image/jpeg", "timestamp": 1700000000}}, repo)
    res = ingest.handle_message(_evento(wamid="f-2", body="220 bolivianos", jid=f"{NUM}@c.us"), repo)
    assert res.get("fusionada") is True and len(repo.publicaciones) == 1
    assert repo.publicaciones[0]["estado"] == "aprobado"


# ═════════════════════════════════════════════════ el gestionado
def test_gestionado_confiable_queda_pendiente_sin_difusion(repo):
    a = _comercio(repo, "com-a")
    _gestionar(repo, a["id"])
    res = ingest.handle_message(_evento(wamid="g-1", jid=f"{NUM}@c.us"), repo)
    assert res["estado"] == "pendiente"
    pub = repo.publicaciones[0]
    assert pub["estado"] == "pendiente" and pub["approved_at"] is None
    assert pub["moderado_por"] is None and pub["moderado_at"] is None
    assert repo.difusion == []


def test_gestionado_por_grupo_tambien_y_el_remitente_ajeno_se_marca(repo):
    a = _comercio(repo, "com-g", whatsapp="59170000007")
    repo.vincular_grupo_comercio(GRUPO, "com-g", None, "admin", "test")
    _gestionar(repo, a["id"])
    ingest.handle_message(_evento_grupo(wamid="g-2", participante="59170000007@c.us"), repo)
    ingest.handle_message(_evento_grupo(wamid="g-3", participante="59170001234@c.us", body="Otra cosa 90 Bs"), repo)
    propios = {p["wa_message_id"]: p for p in repo.publicaciones}
    assert propios["g-2"]["remitente_rol"] == "merchant" and propios["g-3"]["remitente_rol"] == "third_party"
    assert all(p["estado"] == "pendiente" for p in repo.publicaciones) and repo.difusion == []


def test_el_remitente_de_un_no_gestionado_tambien_queda_guardado(repo):
    _comercio(repo, "com-a")
    ingest.handle_message(_evento(wamid="g-4", jid=f"{NUM}@c.us"), repo)
    assert repo.publicaciones[0]["remitente_rol"] == "merchant"


def test_gestionado_no_junta_con_una_publicacion_ya_aprobada_pero_si_con_una_pendiente(repo):
    a = _comercio(repo, "com-a")
    _gestionar(repo, a["id"])
    foto = {"event": "message", "session": "s", "payload": {
        "id": "h-1", "from": f"{NUM}@c.us", "fromMe": False, "body": "", "type": "image", "hasMedia": True,
        "mediaUrl": "http://waha/f.jpg", "mimetype": "image/jpeg", "timestamp": 1700000000}}
    ingest.handle_message(foto, repo)
    res = ingest.handle_message(_evento(wamid="h-2", body="220 bolivianos", jid=f"{NUM}@c.us"), repo)
    assert res.get("fusionada") is True and len(repo.publicaciones) == 1                       # pendiente: se junta
    repo.set_estado_publicacion(repo.publicaciones[0]["id"], "aprobado", None, "integracion:marketing:op")
    foto2 = {**foto, "payload": {**foto["payload"], "id": "h-3"}}
    ingest.handle_message(foto2, repo)
    res = ingest.handle_message(_evento(wamid="h-4", body="300 bolivianos", jid=f"{NUM}@c.us"), repo)
    assert len(repo.publicaciones) >= 2                                                        # nada se cambia por debajo de la aprobada
    assert repo.publicaciones[0]["precio"] == 220


def test_si_no_se_puede_saber_si_esta_gestionado_el_confiable_queda_pendiente(repo, monkeypatch):
    """Falla CERRADO: la duda se resuelve en el estado seguro (una persona lo mira)."""
    _comercio(repo, "com-a")
    monkeypatch.setattr(repo, "es_comercio_gestionado", lambda cid: (_ for _ in ()).throw(RuntimeError("la base no contesta")))
    res = ingest.handle_message(_evento(wamid="x-1", jid=f"{NUM}@c.us"), repo)
    assert res["estado"] == "pendiente" and repo.difusion == []


def test_explorador_sigue_siempre_a_cola_y_marca_su_remitente(repo, monkeypatch):
    monkeypatch.setattr(settings, "wa_numeros_explorador", "59170000888")
    a = _comercio(repo, "com-a")
    ev = _evento(wamid="e-1", jid="59170000888@c.us", body=f"URUKU-{repo.comercios['com-a']['codigo']} oferta 100 Bs")
    res = ingest.handle_message(ev, repo)
    assert res["estado"] == "pendiente"
    assert repo.publicaciones[0]["origen"] == "explorador" and repo.publicaciones[0]["remitente_rol"] == "uruku_explorer"


# ═════════════════════════════════════════════════ auto-aprobación de la IA
@pytest.fixture
def ia_aprueba(monkeypatch):
    monkeypatch.setattr(revision_ia, "moderar_publicacion",
                        lambda t, d: {"veredicto": "aprobar", "motivo": "ok", "confianza": 0.95})
    monkeypatch.setattr(settings, "ia_auto_aprobar_desde", 0.8)
    monkeypatch.setattr(settings, "wa_solo_lectura", False)


def _pend(repo, comercio_id, titulo="zapatillas"):
    return repo.insert_publicacion_directa({"comercio_id": comercio_id, "tipo": "oferta", "titulo": titulo, "estado": "pendiente",
                                            "created_at": "2026-09-10T10:00:00+00:00"})


def test_la_ia_sigue_auto_aprobando_a_un_no_gestionado(repo, ia_aprueba):
    c = _comercio(repo, "com-a", confiable=False)
    p = _pend(repo, c["id"])
    r = revision_ia.revisar_pendientes(repo)
    assert r["auto_aprobadas"] == 1 and repo.get_publicacion(p["id"])["moderado_por"] == "ia-auto"
    assert len(repo.difusion) == 3


def test_la_ia_nunca_auto_aprueba_a_un_gestionado(repo, ia_aprueba):
    c = _comercio(repo, "com-a", confiable=False)
    _gestionar(repo, c["id"])
    p = _pend(repo, c["id"])
    r = revision_ia.revisar_pendientes(repo)
    assert r["revisadas"] == 1 and r["auto_aprobadas"] == 0
    assert repo.get_publicacion(p["id"])["estado"] == "pendiente" and repo.difusion == []
    assert repo.get_publicacion(p["id"])["ia_veredicto"] == "aprobar"          # la IA sigue opinando: sólo no decide


# ═════════════════════════════════════════════════ Mi comercio (api/comercio.py)
def _h(token):
    return {"Authorization": f"Bearer {token}"}


def test_editar_siendo_confiable_no_gestionado_sigue_aprobado(client, repo):
    _comercio(repo, "com-c")
    pub = repo.insert_publicacion_directa({"comercio_id": "com-c", "tipo": "oferta", "estado": "aprobado", "precio": 100})
    r = client.patch(f"/comercio/publicaciones/{pub['id']}", headers=_h(comercio_token("com-c")), json={"precio": 90})
    assert r.status_code == 200 and r.json()["estado"] == "aprobado"


def test_editar_siendo_gestionado_vuelve_a_pendiente(client, repo):
    c = _comercio(repo, "com-c")
    _gestionar(repo, c["id"])
    pub = repo.insert_publicacion_directa({"comercio_id": "com-c", "tipo": "oferta", "estado": "aprobado", "precio": 100})
    r = client.patch(f"/comercio/publicaciones/{pub['id']}", headers=_h(comercio_token("com-c")), json={"precio": 90})
    assert r.status_code == 200 and r.json()["estado"] == "pendiente"
    assert repo.get_publicacion(pub["id"])["approved_at"] is None


def test_publicar_desde_mi_comercio_siendo_gestionado_va_a_cola(client, repo):
    c = _comercio(repo, "com-c")
    r = client.post("/comercio/publicar", headers=_h(comercio_token("com-c")), json={"tipo": "novedad", "titulo": "Llegó stock"})
    assert r.json()["estado"] == "aprobado"                                     # antes de gestionarlo
    _gestionar(repo, c["id"])
    r = client.post("/comercio/publicar", headers=_h(comercio_token("com-c")), json={"tipo": "novedad", "titulo": "Otro"})
    assert r.json()["estado"] == "pendiente" and r.json()["publicado_directo"] is False


# ═════════════════════════════════════════════════ el panel de moderación
def _admin(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def test_aprobar_desde_el_panel_a_un_no_gestionado_sigue_igual(client, repo, admin_token):
    c = _comercio(repo, "com-a", confiable=False)
    p = _pend(repo, c["id"])
    r = client.post(f"/moderacion/publicaciones/{p['id']}", headers=_admin(admin_token), json={"estado": "aprobado"})
    assert r.status_code == 200 and repo.get_publicacion(p["id"])["estado"] == "aprobado"


def test_aprobar_desde_el_panel_a_un_gestionado_es_409(client, repo, admin_token):
    c = _comercio(repo, "com-a", confiable=False)
    _gestionar(repo, c["id"])
    p = _pend(repo, c["id"])
    r = client.post(f"/moderacion/publicaciones/{p['id']}", headers=_admin(admin_token), json={"estado": "aprobado"})
    assert r.status_code == 409 and "marketing" in r.json()["detail"]
    assert repo.get_publicacion(p["id"])["estado"] == "pendiente" and repo.difusion == []


def test_rechazar_o_pedir_cambios_desde_el_panel_si_se_puede(client, repo, admin_token):
    c = _comercio(repo, "com-a", confiable=False)
    _gestionar(repo, c["id"])
    p = _pend(repo, c["id"])
    r = client.post(f"/moderacion/publicaciones/{p['id']}", headers=_admin(admin_token), json={"estado": "rechazado", "motivo": "spam"})
    assert r.status_code == 200 and repo.get_publicacion(p["id"])["estado"] == "rechazado"


def test_override_de_admin_aprueba_una_vez_exige_motivo_y_queda_registrado(client, repo, admin_token):
    c = _comercio(repo, "com-a", confiable=False)
    _gestionar(repo, c["id"])
    p = _pend(repo, c["id"])
    corto = client.post(f"/moderacion/publicaciones/{p['id']}", headers=_admin(admin_token),
                        json={"estado": "aprobado", "override_gestionado": True, "motivo": "ok"})
    assert corto.status_code == 422
    r = client.post(f"/moderacion/publicaciones/{p['id']}", headers=_admin(admin_token),
                    json={"estado": "aprobado", "override_gestionado": True, "motivo": "marketing caído y el comercio pide salir hoy"})
    assert r.status_code == 200
    pub = repo.get_publicacion(p["id"])
    assert pub["estado"] == "aprobado" and pub["motivo_moderacion"].startswith("override-gestionado:")
    ev = [e for e in repo.integ_eventos if e["tipo"] == "override_aprobacion"]
    assert len(ev) == 1 and ev[0]["actor"] == "admin@bermejolive.com" and ev[0]["detalle"]["publicacion_id"] == p["id"]


def test_override_sin_ser_admin_es_403(client, repo):
    from app.core import auth

    c = _comercio(repo, "com-a", confiable=False)
    _gestionar(repo, c["id"])
    p = _pend(repo, c["id"])
    moderador = auth.make_token("mod@x.com", rol="moderador")
    r = client.post(f"/moderacion/publicaciones/{p['id']}", headers=_h(moderador),
                    json={"estado": "aprobado", "override_gestionado": True, "motivo": "quiero aprobarla igual ya mismo"})
    assert r.status_code == 403
    assert repo.get_publicacion(p["id"])["estado"] == "pendiente"
