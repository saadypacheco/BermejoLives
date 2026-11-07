"""Correcciones de la revisión de seguridad de la API de integración (marketing) y de la ingesta.

  1  `sender_role`: quien sólo sabe el código del local (chat 1-a-1 o grupo) es `third_party`, nunca `merchant`.
  2  E8/E9 sólo tocan las filas que pidió la integración; `broadcast:send` no es un scope por defecto;
     `INTEGRACION_DIFUSION` apagada ⇒ 403 en E7 con destinos, E9 y E10.
  3  La integración no aprueba lo que sólo Uruku puede moderar (409 `requiere_moderacion_uruku`).
  4  E6: tope de 8 MB, cuota diaria por cliente, metadatos fuera sin recomprimir y limpieza de huérfanas.
  5  E10 pide `broadcast:send`; purga diaria de idempotencia; «gestionado» exige una clave activa; la fusión foto +
     texto no junta remitentes distintos y deja el rol menos confiable; E3/E4 sólo activas; teléfonos tapados;
     tope de 401 por IP.
  6  Ingesta: una publicación APROBADA no se modifica por un mensaje que iría a moderación, y un número autorizado
     sólo por el código no publica directo en un grupo.
"""
from __future__ import annotations

import io
import os
import time
import uuid

import pytest
from PIL import Image

from app.core.config import settings
from app.services import difusion, ingest, integracion, wa_media, wa_received
from tests.test_ingest import GRUPO, _evento_grupo
from tests.test_integracion_api import BASE, H, _aprobar, _foto, _pub, aprobada, error, etag, mundo  # noqa: F401

NUM = "59170000009"          # el número del comercio de la ficha
OTRO = "59171111111"


@pytest.fixture(autouse=True)
def _entorno(monkeypatch):
    monkeypatch.setattr(settings, "wa_solo_lectura", True)
    monkeypatch.setattr(wa_media, "guardar_imagen_publicacion",
                        lambda slug, url, media_path=None: f"https://fotos.test/{slug}/x.jpg")


def _comercio(repo, *, confiable=True, **kw):
    return repo.seed_comercio(id="com-a", slug="com-a", nombre="Com A", whatsapp=kw.pop("whatsapp", NUM), wa_jid=None,
                              activo=True, confiable=confiable, plan="destacado", **kw)


def _msg(wamid, body="", numero=NUM, media=False):
    p = {"id": wamid, "from": f"{numero}@c.us", "fromMe": False, "body": body,
         "type": "image" if media else "text", "timestamp": 1700000000}
    if media:
        p.update({"hasMedia": True, "mediaUrl": "http://waha/f.jpg", "mimetype": "image/jpeg"})
    return {"event": "message", "session": "s", "payload": p}


def _msg_grupo(wamid, participante, body="Oferta zapatillas 120 Bs", media=False):
    ev = _evento_grupo(wamid=wamid, body=body, participante=f"{participante}@c.us")
    if media:
        ev["payload"].update({"type": "image", "hasMedia": True, "mediaUrl": "http://waha/f.jpg", "mimetype": "image/jpeg"})
    return ev


def _atar_grupo(repo, comercio):
    repo.vincular_grupo_comercio(GRUPO, comercio["id"], None, "admin", "admin")


# ═══════════════════════════════════════════════════════════════ 1 · sender_role
def test_remitente_de_mapea_codigo_y_numero_por_codigo_a_third_party():
    assert integracion.remitente_de({"identidad_origen": "numero_por_codigo"}) == "third_party"
    assert integracion.remitente_de({"identidad_origen": "codigo"}) == "third_party"
    assert integracion.remitente_de({"identidad_origen": "numero"}) == "merchant"
    assert integracion.remitente_de({"origen": "explorador"}) == "uruku_explorer"
    assert integracion.remitente_de({"origen": "panel"}) == "merchant"
    assert integracion.remitente_de({"identidad_origen": "grupo"}) is None
    assert integracion.remitente_de({"remitente_rol": "merchant", "identidad_origen": "codigo"}) == "merchant"   # lo guardado manda


def test_1a1_numero_conocido_por_el_comercio_es_merchant(repo):
    _comercio(repo)
    ingest.handle_message(_msg("m-1", "zapatillas 120 Bs"), repo)
    assert repo.publicaciones[0]["remitente_rol"] == "merchant"


def test_1a1_numero_autorizado_solo_por_el_codigo_es_third_party_y_va_a_moderacion(repo):
    c = _comercio(repo, whatsapp=None)
    repo.agregar_numero_comercio(c["id"], NUM, "se identificó con el código", ingest.NUMERO_POR_CODIGO)
    ingest.handle_message(_msg("m-2", "zapatillas 120 Bs"), repo)
    pub = repo.publicaciones[0]
    assert pub["identidad_origen"] == "numero_por_codigo"
    assert pub["remitente_rol"] == "third_party" and pub["estado"] == "pendiente"


def test_1a1_con_el_codigo_del_local_es_third_party(repo):
    c = _comercio(repo, whatsapp=None)
    ingest.handle_message(_msg("m-3", f"URUKU-{c['codigo']} zapatillas 120 Bs"), repo)
    pub = repo.publicaciones[0]
    assert pub["identidad_origen"] == "codigo" and pub["remitente_rol"] == "third_party"


def test_numero_autorizado_por_una_persona_del_equipo_es_merchant(repo):
    c = _comercio(repo, whatsapp=None)
    repo.agregar_numero_comercio(c["id"], NUM, None, "admin@bermejolive.com")
    ingest.handle_message(_msg("m-4", "zapatillas 120 Bs"), repo)
    pub = repo.publicaciones[0]
    assert pub["remitente_rol"] == "merchant" and pub["estado"] == "aprobado"


# ═══════════════════════════════════════════════════════════════ 1 + 6b · grupos
def test_grupo_numero_autorizado_solo_por_codigo_no_publica_directo_aunque_el_comercio_sea_confiable(repo):
    c = _comercio(repo, whatsapp=None)
    _atar_grupo(repo, c)
    repo.agregar_numero_comercio(c["id"], OTRO, "se identificó con el código", ingest.NUMERO_POR_CODIGO)
    res = ingest.handle_message(_msg_grupo("g-1", OTRO), repo)
    pub = repo.publicaciones[0]
    assert res["estado"] == "pendiente" and pub["estado"] == "pendiente" and pub["moderado_por"] is None
    assert pub["remitente_rol"] == "third_party"
    assert repo.difusion == []                                  # y sin difusión: nada salió


def test_grupo_dueno_del_comercio_sigue_publicando_directo_como_merchant(repo):
    c = _comercio(repo, whatsapp=OTRO)                         # el número público del comercio
    _atar_grupo(repo, c)
    ingest.handle_message(_msg_grupo("g-2", OTRO), repo)
    pub = repo.publicaciones[0]
    assert pub["estado"] == "aprobado" and pub["remitente_rol"] == "merchant"


def test_grupo_numero_autorizado_por_el_equipo_sigue_publicando_directo(repo):
    c = _comercio(repo, whatsapp=None)
    _atar_grupo(repo, c)
    repo.agregar_numero_comercio(c["id"], OTRO, None, "admin@bermejolive.com")
    ingest.handle_message(_msg_grupo("g-3", OTRO), repo)
    pub = repo.publicaciones[0]
    assert pub["estado"] == "aprobado" and pub["remitente_rol"] == "merchant"


def test_grupo_participante_ajeno_sigue_siendo_third_party_y_pendiente(repo):
    c = _comercio(repo, whatsapp=NUM)
    _atar_grupo(repo, c)
    ingest.handle_message(_msg_grupo("g-4", "59173333333"), repo)
    pub = repo.publicaciones[0]
    assert pub["estado"] == "pendiente" and pub["remitente_rol"] == "third_party"


# ═══════════════════════════════════════════════════════════════ 5 y 6a · fusión
def test_fusion_normal_del_mismo_remitente_confiable_sigue_funcionando(repo):
    _comercio(repo)
    ingest.handle_message(_msg("f-1", "", media=True), repo)
    res = ingest.handle_message(_msg("f-2", "220 bolivianos"), repo)
    assert res.get("fusionada") is True and len(repo.publicaciones) == 1
    assert repo.publicaciones[0]["estado"] == "aprobado" and repo.publicaciones[0]["remitente_rol"] == "merchant"


def test_no_se_juntan_mensajes_de_remitentes_distintos(repo):
    c = _comercio(repo, whatsapp=None)
    _atar_grupo(repo, c)
    repo.agregar_numero_comercio(c["id"], NUM, None, "admin@bermejolive.com")
    repo.agregar_numero_comercio(c["id"], OTRO, None, "admin@bermejolive.com")
    ingest.handle_message(_msg_grupo("d-1", NUM, body="", media=True), repo)            # foto de A
    res = ingest.handle_message(_msg_grupo("d-2", OTRO, body="Zapatillas 220 bolivianos"), repo)   # texto de B
    assert not res.get("fusionada") and len(repo.publicaciones) == 2
    assert repo.publicaciones[0]["descripcion"] is None and repo.publicaciones[0]["imagen_url"]


def test_el_texto_de_otro_remitente_en_1a1_no_es_la_segunda_mitad_de_la_foto(repo):
    c = _comercio(repo)
    repo.agregar_numero_comercio(c["id"], OTRO, None, "admin@bermejolive.com")
    ingest.handle_message(_msg("e-1", "", media=True), repo)
    res = ingest.handle_message(_msg("e-2", "zapatillas urbanas de cuero", numero=OTRO), repo)
    assert res["publicada"] is False and "charla" in repo.wa_inbox["e-2"]["motivo"]
    assert len(repo.publicaciones) == 1 and repo.publicaciones[0]["descripcion"] is None


def test_no_se_junta_con_algo_que_no_vino_de_un_mensaje_conocido(repo):
    """Una publicación del panel / sin bandeja (no se sabe quién la mandó) no se completa por WhatsApp."""
    c = _comercio(repo)
    repo.insert_publicacion({"comercio_id": c["id"], "tipo": "oferta", "estado": "pendiente", "origen": "panel",
                             "imagen_url": "https://fotos.test/p.jpg", "descripcion": None})
    res = ingest.handle_message(_msg("p-1", "220 bolivianos"), repo)
    assert not res.get("fusionada") and len(repo.publicaciones) == 2


def test_la_fusion_deja_el_rol_menos_confiable():
    class R:
        def __init__(self, rol):
            self.rol, self.parches = rol, []

        def integracion_origen_de_publicacion(self, pub_id):
            return {"remitente_rol": self.rol, "identidad_origen": None, "origen": "whatsapp", "phone": "591700"}

        def update_publicacion(self, pub_id, patch):
            self.parches.append(patch)
            return {"id": pub_id, **patch}

    com = {"id": "c", "slug": "c"}
    previa = {"id": "p1", "estado": "pendiente", "imagen_url": "https://f/x.jpg", "descripcion": None}
    # la anterior era third_party y ésta merchant ⇒ queda third_party (el que ya tenía: no se reescribe a merchant)
    r = R("third_party")
    ingest._fusionar_con_la_anterior(r, com, {"descripcion": "220 Bs", "remitente_rol": "merchant"}, "oferta", previa,
                                     phone="591700")
    assert r.parches[0].get("remitente_rol", "third_party") == "third_party"
    # la anterior era merchant y ésta third_party ⇒ baja a third_party
    r = R("merchant")
    ingest._fusionar_con_la_anterior(r, com, {"descripcion": "220 Bs", "remitente_rol": "third_party"}, "oferta", previa,
                                     phone="591700")
    assert r.parches[0]["remitente_rol"] == "third_party"
    # el mismo rol no se reescribe
    r = R("merchant")
    ingest._fusionar_con_la_anterior(r, com, {"descripcion": "220 Bs", "remitente_rol": "merchant"}, "oferta", previa,
                                     phone="591700")
    assert "remitente_rol" not in r.parches[0]


def test_6a_el_mensaje_que_iria_a_moderacion_no_modifica_una_publicacion_ya_aprobada(repo):
    """El comercio NO es confiable; un moderador ya aprobó su foto; el texto del mismo número no la cambia sin
    moderar: se crea una publicación nueva, pendiente."""
    _comercio(repo, confiable=False)
    ingest.handle_message(_msg("a-1", "", media=True), repo)
    repo.publicaciones[0]["estado"] = "aprobado"                 # la aprobó una persona
    res = ingest.handle_message(_msg("a-2", "220 bolivianos"), repo)
    assert not res.get("fusionada") and len(repo.publicaciones) == 2
    assert repo.publicaciones[0]["descripcion"] is None and repo.publicaciones[0]["estado"] == "aprobado"
    assert repo.publicaciones[1]["estado"] == "pendiente" and repo.publicaciones[1]["descripcion"] == "220 bolivianos"


def test_6a_un_numero_por_codigo_no_modifica_lo_aprobado_de_otro(repo):
    c = _comercio(repo)                                          # el dueño verificado publica directo
    ingest.handle_message(_msg("b-1", "", media=True), repo)
    assert repo.publicaciones[0]["estado"] == "aprobado"
    repo.agregar_numero_comercio(c["id"], OTRO, "se identificó con el código", ingest.NUMERO_POR_CODIGO)
    res = ingest.handle_message(_msg("b-2", "precio 1 Bs, comprá en mi web", numero=OTRO), repo)
    assert not res.get("fusionada")
    assert repo.publicaciones[0]["descripcion"] is None and repo.publicaciones[0]["estado"] == "aprobado"
    assert len(repo.publicaciones) == 2 and repo.publicaciones[1]["estado"] == "pendiente"


def test_6a_el_mismo_numero_por_codigo_tampoco_modifica_una_aprobada(repo):
    c = _comercio(repo, whatsapp=None)
    repo.agregar_numero_comercio(c["id"], OTRO, "se identificó con el código", ingest.NUMERO_POR_CODIGO)
    ingest.handle_message(_msg("c-1", "", numero=OTRO, media=True), repo)
    repo.publicaciones[0]["estado"] = "aprobado"                 # un moderador la aprobó
    res = ingest.handle_message(_msg("c-2", "220 bolivianos", numero=OTRO), repo)
    assert not res.get("fusionada") and len(repo.publicaciones) == 2
    assert repo.publicaciones[0]["descripcion"] is None
    assert repo.publicaciones[1]["estado"] == "pendiente"


def test_la_fusion_con_una_pendiente_del_mismo_numero_por_codigo_sigue_andando(repo):
    c = _comercio(repo, whatsapp=None)
    repo.agregar_numero_comercio(c["id"], OTRO, "se identificó con el código", ingest.NUMERO_POR_CODIGO)
    ingest.handle_message(_msg("h-1", "", numero=OTRO, media=True), repo)
    res = ingest.handle_message(_msg("h-2", "220 bolivianos", numero=OTRO), repo)
    assert res.get("fusionada") is True and len(repo.publicaciones) == 1
    assert repo.publicaciones[0]["remitente_rol"] == "third_party" and repo.publicaciones[0]["estado"] == "pendiente"


# ═══════════════════════════════════════════════════════════════ 2 · scopes, difusión y filas propias
def test_emitir_clave_no_da_broadcast_send_por_defecto(repo):
    c = integracion.emitir_clave(repo, "Marketing", None, "test")
    assert set(c["scopes"]) == {"publications:read", "publications:write", "media:write"}
    assert "broadcast:send" not in c["scopes"]
    explicita = integracion.emitir_clave(repo, "Con difusión", ["publications:read", "broadcast:send"], "test")
    assert "broadcast:send" in explicita["scopes"]
    rotada = integracion.rotar_clave(repo, c["key_id"], "test")
    assert "broadcast:send" not in rotada["scopes"]


def test_el_script_de_claves_no_ofrece_broadcast_send_por_defecto(repo, monkeypatch, capsys):
    from scripts import integracion_clave

    monkeypatch.setattr(integracion_clave, "get_repo", lambda: repo)
    assert integracion_clave.main(["emitir", "--nombre", "Marketing"]) == 0
    assert "broadcast:send" not in capsys.readouterr().out
    assert integracion_clave.main(["emitir", "--nombre", "X", "--scopes", "publications:read", "broadcast:send"]) == 0
    assert "broadcast:send" in capsys.readouterr().out


def test_difusion_apagada_e7_con_destinos_es_403_y_no_toca_nada(mundo, monkeypatch):
    monkeypatch.setattr(settings, "integracion_difusion", False)
    p = _pub(mundo.repo, mundo.com["id"])
    r = _aprobar(mundo, p)
    assert r.status_code == 403 and error(r)["code"] == "difusion_deshabilitada"
    assert "deshabilitada" in error(r)["message"]
    assert mundo.repo.get_publicacion(p["id"])["estado"] == "pendiente" and mundo.repo.difusion == []


def test_difusion_apagada_aprobar_sin_destinos_sigue_andando(mundo, monkeypatch):
    monkeypatch.setattr(settings, "integracion_difusion", False)
    p = _pub(mundo.repo, mundo.com["id"])
    r = _aprobar(mundo, p, destinos=())
    assert r.status_code == 200 and r.json()["estado"] == "aprobado" and r.json()["difusion"] == []


def test_difusion_apagada_e9_y_e10_son_403_aun_con_el_scope(mundo, aprobada, monkeypatch):
    monkeypatch.setattr(settings, "integracion_difusion", False)
    r = mundo.client.post(f"{BASE}/publications/{aprobada['id']}/broadcasts/send",
                          headers=H(mundo, idem="x", if_match=etag(mundo, aprobada)), json={})
    assert r.status_code == 403 and error(r)["code"] == "difusion_deshabilitada"
    fila = mundo.repo.difusion_de_publicacion(aprobada["id"])[0]
    r = mundo.client.post(f"{BASE}/broadcasts/{fila['id']}/verify", headers=H(mundo, idem="y"), json={})
    assert r.status_code == 403 and error(r)["code"] == "difusion_deshabilitada"
    # leer sigue permitido
    assert mundo.client.get(f"{BASE}/publications/{aprobada['id']}/broadcasts", headers=H(mundo)).status_code == 200


def test_e9_solo_manda_las_filas_que_pidio_la_integracion_y_e8_solo_las_muestra(mundo, aprobada, monkeypatch):
    mundo.enviados = []
    monkeypatch.setattr(difusion, "_ENVIOS", {
        d: (lambda texto, img, _d=d, **kw: mundo.enviados.append(_d) or difusion.Publicado(None, external_post_id=f"{_d}_1"))
        for d in difusion.DESTINOS})
    # una fila ajena a la integración (la pidió el panel/worker): sin `solicitado_por`
    fila_ajena = next(f for f in mundo.repo.difusion if f["publicacion_id"] == aprobada["id"] and f["destino"] == "instagram")
    fila_ajena["solicitado_por"] = None
    visibles = mundo.client.get(f"{BASE}/publications/{aprobada['id']}/broadcasts", headers=H(mundo)).json()["items"]
    assert [i["destino"] for i in visibles] == ["facebook"]
    r = mundo.client.post(f"{BASE}/publications/{aprobada['id']}/broadcasts/send",
                          headers=H(mundo, idem="s1", if_match=etag(mundo, aprobada)), json={})
    assert r.status_code == 200 and [i["destino"] for i in r.json()["items"]] == ["facebook"]
    assert mundo.enviados == ["facebook"]
    assert fila_ajena["estado"] == "pendiente"                  # la otra quedó donde estaba
    # E10 sobre la fila ajena: 404
    r = mundo.client.post(f"{BASE}/broadcasts/{fila_ajena['id']}/verify", headers=H(mundo, idem="v1"), json={})
    assert r.status_code == 404


def test_e10_exige_broadcast_send(mundo, aprobada):
    lector = integracion.emitir_clave(mundo.repo, "Lector", ["publications:read"], "test")
    mundo.repo.integracion_set_comercio(lector["grupo_id"], mundo.com["id"], True, "test")
    fila = mundo.repo.difusion_de_publicacion(aprobada["id"])[0]
    r = mundo.client.post(f"{BASE}/broadcasts/{fila['id']}/verify", headers=H(mundo, idem="z", key=lector["clave"]), json={})
    assert r.status_code == 403 and error(r)["code"] == "scope_insuficiente"


# ═══════════════════════════════════════════════════════════════ 3 · lo que sólo Uruku modera
@pytest.mark.parametrize("cambio", [
    {"remitente_rol": "third_party"},
    {"remitente_rol": "uruku_explorer", "origen": "explorador", "identidad_origen": "explorador"},
    {"origen": "explorador"},
    {"identidad_origen": "codigo"},
    {"identidad_origen": "numero_por_codigo"},
    {"remitente_rol": None, "identidad_origen": "grupo"},          # sin rol y no deducible: se trata como «no»
    {"ia_veredicto": "rechazar", "ia_confianza": 0.95},
])
def test_la_integracion_no_aprueba_lo_que_solo_uruku_puede_moderar(mundo, cambio):
    p = _pub(mundo.repo, mundo.com["id"], **cambio)
    r = _aprobar(mundo, p, destinos=())
    assert r.status_code == 409 and error(r)["code"] == "requiere_moderacion_uruku", r.text
    assert mundo.repo.get_publicacion(p["id"])["estado"] == "pendiente"
    assert "K7M2" not in r.text and "URUKU-" not in r.text


def test_la_integracion_si_aprueba_lo_del_comercio_y_puede_rechazar_lo_de_terceros(mundo):
    ok = _pub(mundo.repo, mundo.com["id"], remitente_rol="merchant", identidad_origen="numero", ia_veredicto="aprobar")
    assert _aprobar(mundo, ok, destinos=()).status_code == 200
    viejo = _pub(mundo.repo, mundo.com["id"], remitente_rol=None, identidad_origen="numero")     # anterior a la 0191
    assert _aprobar(mundo, viejo, destinos=(), idem="k-viejo").status_code == 200
    tercero = _pub(mundo.repo, mundo.com["id"], remitente_rol="third_party")
    body = {"decision": "reject", "motivo": "no es del comercio", "actor": {"sistema": "marketing", "usuario": "op"}}
    r = mundo.client.post(f"{BASE}/publications/{tercero['id']}/moderation",
                          headers=H(mundo, idem="rj-3", if_match=etag(mundo, tercero)), json=body)
    assert r.status_code == 200 and r.json()["estado"] == "rechazado"


# ═══════════════════════════════════════════════════════════════ 4 · E6
def _jpeg_con_metadatos(lado=64):
    exif = Image.Exif()
    exif[0x010F] = "ACME-CAMARA"                       # fabricante
    exif[0x0132] = "2026:10:15 10:00:00"
    buf = io.BytesIO()
    Image.new("RGB", (lado, lado), (10, 200, 90)).save(buf, "JPEG", quality=80, exif=exif, comment=b"coordenadas-secretas")
    return buf.getvalue()


def _jpeg_limpio(lado=64):
    buf = io.BytesIO()
    Image.new("RGB", (lado, lado), (10, 200, 90)).save(buf, "JPEG", quality=80)
    return buf.getvalue()


def test_quitar_metadatos_saca_exif_y_comentarios_sin_tocar_los_datos_de_la_imagen():
    con = _jpeg_con_metadatos()
    assert b"ACME-CAMARA" in con and b"coordenadas-secretas" in con
    limpio = integracion.quitar_metadatos_jpeg(con)
    assert b"ACME-CAMARA" not in limpio and b"coordenadas-secretas" not in limpio and b"Exif" not in limpio
    assert limpio == _jpeg_limpio()                       # byte a byte lo mismo que sin metadatos: no se recomprimió
    with Image.open(io.BytesIO(limpio)) as im:
        assert im.size == (64, 64)
    assert limpio.startswith(b"\xff\xd8\xff\xe0")        # el JFIF se conserva


@pytest.mark.parametrize("roto", [b"\xff\xd8", b"\xff\xd8\xff\xe1\x00\x02", b"\xff\xd8\xff\xe1\xff\xff\x00", b"\xff\xd8\x00\x00",
                                   b"\xff\xd8\xff\xd9"])
def test_quitar_metadatos_rechaza_estructuras_rotas(roto):
    with pytest.raises(ValueError):
        integracion.quitar_metadatos_jpeg(roto)


def test_e6_guarda_la_imagen_sin_exif_y_el_id_es_el_del_archivo_limpio(mundo):
    r = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="x1"),
                          files={"file": ("a.jpg", _jpeg_con_metadatos(), "image/jpeg")})
    assert r.status_code == 200, r.text
    d = r.json()
    guardado = (settings.fotos_dir and __import__("pathlib").Path(settings.fotos_dir) / "integracion" / f"{d['media_id']}.jpg").read_bytes()
    assert b"ACME-CAMARA" not in guardado and b"coordenadas-secretas" not in guardado
    assert d["sha256"] == __import__("hashlib").sha256(guardado).hexdigest()
    # la misma imagen ya limpia da el mismo media_id (idempotente por contenido)
    r2 = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="x2"), files={"file": ("b.jpg", _jpeg_limpio(), "image/jpeg")})
    assert r2.json()["media_id"] == d["media_id"]


def test_e6_tope_de_8_mb(mundo):
    assert integracion.MAX_MEDIA_BYTES == 8 * 1024 * 1024
    grande = b"\xff\xd8" + b"\0" * (8 * 1024 * 1024)
    r = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="g1"), files={"file": ("a.jpg", grande, "image/jpeg")})
    assert r.status_code == 413 and error(r)["code"] == "media_too_large" and "8 MB" in error(r)["message"]
    from app.core.limite_cuerpo import tope_para
    assert tope_para("/v1/integration/media") < 9 * 1024 * 1024


def test_e6_cuota_diaria_de_archivos_por_cliente(mundo, monkeypatch):
    monkeypatch.setattr(settings, "integracion_media_cuota_archivos_dia", 2)
    for i, lado in enumerate((60, 61)):
        assert mundo.client.post(f"{BASE}/media", headers=H(mundo, idem=f"q{i}"),
                                 files={"file": ("a.jpg", _jpeg_limpio(lado), "image/jpeg")}).status_code == 200
    r = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="q3"), files={"file": ("a.jpg", _jpeg_limpio(62), "image/jpeg")})
    assert r.status_code == 429 and error(r)["code"] == "media_quota_exceeded" and r.headers.get("retry-after")
    # un archivo que ya estaba NO cuenta ni se rechaza
    ya = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="q4"), files={"file": ("a.jpg", _jpeg_limpio(60), "image/jpeg")})
    assert ya.status_code == 200
    # y la cuota es POR CLIENTE: otro cliente tiene la suya
    otro = integracion.emitir_clave(mundo.repo, "Otro", None, "test")
    r = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="q5", key=otro["clave"]),
                          files={"file": ("a.jpg", _jpeg_limpio(63), "image/jpeg")})
    assert r.status_code == 200


def test_e6_cuota_diaria_de_bytes(mundo, monkeypatch):
    monkeypatch.setattr(settings, "integracion_media_cuota_bytes_dia", len(_jpeg_limpio(200)) + 10)
    assert mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="b1"),
                             files={"file": ("a.jpg", _jpeg_limpio(200), "image/jpeg")}).status_code == 200
    r = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="b2"), files={"file": ("a.jpg", _jpeg_limpio(201), "image/jpeg")})
    assert r.status_code == 429 and error(r)["code"] == "media_quota_exceeded"


def test_e6_la_cuota_es_de_ventana_de_24_horas(mundo, monkeypatch):
    monkeypatch.setattr(settings, "integracion_media_cuota_archivos_dia", 1)
    assert mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="w1"),
                             files={"file": ("a.jpg", _jpeg_limpio(70), "image/jpeg")}).status_code == 200
    for e in mundo.repo.integ_eventos:
        if e["tipo"] == "media_subida":
            e["created_at"] = "2020-01-01T00:00:00+00:00"          # pasó más de un día
    assert mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="w2"),
                             files={"file": ("a.jpg", _jpeg_limpio(71), "image/jpeg")}).status_code == 200


def test_e6_si_no_se_puede_medir_la_cuota_no_se_escribe(mundo, monkeypatch):
    def roto(*a, **k):
        raise RuntimeError("la base no contesta")

    monkeypatch.setattr(mundo.repo, "integracion_uso_media", roto)
    r = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="n1"), files={"file": ("a.jpg", _jpeg_limpio(80), "image/jpeg")})
    assert r.status_code == 503 and error(r)["code"] == "cuota_no_verificable"
    assert not (__import__("pathlib").Path(settings.fotos_dir) / "integracion").exists() or \
        not list((__import__("pathlib").Path(settings.fotos_dir) / "integracion").glob("med_*"))


def _plantar(nombre_id: str, dias: float) -> str:
    from pathlib import Path

    carpeta = Path(settings.fotos_dir) / "integracion"
    carpeta.mkdir(parents=True, exist_ok=True)
    f = carpeta / f"{nombre_id}.jpg"
    f.write_bytes(_jpeg_limpio(32))
    antes = time.time() - dias * 86400
    os.utime(f, (antes, antes))
    return settings.public_photo_url(f"integracion/{f.name}")


def test_limpieza_borra_solo_las_huerfanas_viejas(repo):
    from pathlib import Path

    huerfana = "med_" + "a" * 32
    usada = "med_" + "b" * 32
    reciente = "med_" + "c" * 32
    _plantar(huerfana, 30)
    url_usada = _plantar(usada, 30)
    _plantar(reciente, 1)
    carpeta = Path(settings.fotos_dir) / "integracion"
    (carpeta / "otra-cosa.jpg").write_bytes(b"x")                       # no es un med_*: no se toca
    os.utime(carpeta / "otra-cosa.jpg", (0, 0))
    repo.encolar_difusion("pub-1", ["facebook"], {"imagen_url_override": url_usada, "solicitado_por": "integracion:marketing:op"})

    assert integracion.limpiar_media_huerfana(repo, dias=14) == 1
    assert not (carpeta / f"{huerfana}.jpg").exists()
    assert (carpeta / f"{usada}.jpg").exists() and (carpeta / f"{reciente}.jpg").exists()
    assert (carpeta / "otra-cosa.jpg").exists()


def test_limpieza_no_borra_nada_si_no_puede_saber_que_esta_en_uso(repo, monkeypatch):
    from pathlib import Path

    _plantar("med_" + "d" * 32, 60)
    monkeypatch.setattr(repo, "difusion_imagenes_en_uso", lambda: (_ for _ in ()).throw(RuntimeError("sin base")), raising=False)
    assert integracion.limpiar_media_huerfana(repo, dias=14) == 0
    assert (Path(settings.fotos_dir) / "integracion" / f"med_{'d' * 32}.jpg").exists()


def test_el_loop_diario_de_retencion_corre_la_limpieza_y_la_purga_de_idempotencia(repo):
    from pathlib import Path

    _plantar("med_" + "e" * 32, 90)
    repo.integracion_idem_reclamar("g1", "vieja", "h")
    repo._integ()["idem"][("g1", "vieja")]["created_at"] = "2020-01-01T00:00:00+00:00"
    repo.integracion_idem_reclamar("g1", "nueva", "h")
    wa_received.purge_events(repo)                                       # lo que llama el loop diario de main.py
    assert not (Path(settings.fotos_dir) / "integracion" / f"med_{'e' * 32}.jpg").exists()
    assert ("g1", "vieja") not in repo._integ()["idem"] and ("g1", "nueva") in repo._integ()["idem"]


def test_el_mantenimiento_nunca_lanza(repo, monkeypatch):
    monkeypatch.setattr(repo, "integracion_idem_purgar", lambda: (_ for _ in ()).throw(RuntimeError("x")))
    monkeypatch.setattr(integracion, "limpiar_media_huerfana", lambda r: (_ for _ in ()).throw(RuntimeError("y")))
    assert integracion.mantenimiento_diario(repo) == {"idempotencia": 0, "media": 0}


# ═══════════════════════════════════════════════════════════════ 5 · el resto
def test_gestionado_exige_que_el_cliente_siga_teniendo_una_clave_activa(repo):
    c = repo.seed_comercio(id="com-g", slug="g", nombre="G", activo=True, confiable=True)
    cli = integracion.emitir_clave(repo, "Marketing", None, "test")
    repo.integracion_set_comercio(cli["grupo_id"], c["id"], True, "test")
    assert repo.es_comercio_gestionado(c["id"]) is True
    nueva = integracion.rotar_clave(repo, cli["key_id"], "test")
    integracion.revocar_clave(repo, cli["key_id"], "test")
    assert repo.es_comercio_gestionado(c["id"]) is True                    # la rotada sigue activa
    integracion.revocar_clave(repo, nueva["key_id"], "test")
    assert repo.es_comercio_gestionado(c["id"]) is False                   # sin ninguna clave activa: ya no gestiona
    assert integracion.es_confiable(repo, c) is True                       # y vuelve a publicar directo


def test_e3_y_e4_solo_publicaciones_activas_por_defecto(mundo):
    viva = _pub(mundo.repo, mundo.com["id"])
    baja = _pub(mundo.repo, mundo.com["id"], activo=False)
    ids = lambda r: {i["id"] for i in r.json()["items"]}                   # noqa: E731
    assert ids(mundo.client.get(f"{BASE}/publications", headers=H(mundo))) == {viva["id"]}
    assert ids(mundo.client.get(f"{BASE}/publications?activo=all", headers=H(mundo))) == {viva["id"], baja["id"]}
    assert ids(mundo.client.get(f"{BASE}/publications?activo=false", headers=H(mundo))) == {baja["id"]}
    assert mundo.client.get(f"{BASE}/publications?activo=quizas", headers=H(mundo)).status_code == 422
    assert mundo.client.get(f"{BASE}/publications/{viva['id']}", headers=H(mundo)).status_code == 200
    assert mundo.client.get(f"{BASE}/publications/{baja['id']}", headers=H(mundo)).status_code == 404
    assert mundo.client.get(f"{BASE}/publications/{baja['id']}?activo=all", headers=H(mundo)).status_code == 200


def test_la_api_tapa_los_telefonos_escritos_en_titulo_y_descripcion(mundo):
    p = _pub(mundo.repo, mundo.com["id"], titulo="Llamá al 70123456",
             descripcion="Consultas al +591 71234567 o 7-123-4567-8. Bs 12.500.000, vence 15-10-2026, 220 Bs")
    d = mundo.client.get(f"{BASE}/publications/{p['id']}", headers=H(mundo)).json()
    assert d["titulo"] == "Llamá al [teléfono]"
    assert "71234567" not in d["descripcion"] and "7-123-4567-8" not in d["descripcion"]
    assert "[teléfono]" in d["descripcion"]
    # lo que NO es un teléfono queda como estaba
    assert "Bs 12.500.000" in d["descripcion"] and "15-10-2026" in d["descripcion"] and "220 Bs" in d["descripcion"]
    # el original en la base no se toca
    assert mundo.repo.get_publicacion(p["id"])["titulo"] == "Llamá al 70123456"
    assert integracion.enmascarar_telefonos(None) is None and integracion.enmascarar_telefonos("") == ""


def test_tope_de_claves_invalidas_por_ip(mundo, monkeypatch):
    monkeypatch.setattr(settings, "integracion_auth_fallos_por_min", 3)
    integracion.reiniciar_limites()
    mala = {"Authorization": "Bearer uki_abcdef123456.secretoequivocadoxxxxxxxx"}
    assert [mundo.client.get(f"{BASE}/me", headers=mala).status_code for _ in range(3)] == [401, 401, 401]
    r = mundo.client.get(f"{BASE}/me", headers=mala)
    assert r.status_code == 429 and error(r)["code"] == "rate_limited" and r.headers.get("retry-after")
    # los pedidos con clave válida no cuentan como fallo
    integracion.reiniciar_limites()
    for _ in range(10):
        assert mundo.client.get(f"{BASE}/me", headers=H(mundo)).status_code == 200


def test_el_tope_por_ip_no_crece_sin_limite():
    integracion.reiniciar_limites()
    for i in range(integracion._MAX_IPS_RECORDADAS + 5):
        integracion.registrar_fallo_de_ip(f"10.0.{i // 250}.{i % 250}-{i}")
    assert len(integracion._fallos_ip) <= integracion._MAX_IPS_RECORDADAS
    integracion.reiniciar_limites()


def test_agregar_verificados_sin_parametro_solo_simula(client, repo, admin_token):
    cli = integracion.emitir_clave(repo, "Marketing", None, "test")
    v = repo.seed_comercio(id=str(uuid.uuid4()), slug="v", nombre="V", activo=True, verificado=True)
    ruta = f"/admin/integracion/clientes/{cli['grupo_id']}/comercios/verificados"
    r = client.post(ruta, headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200 and r.json()["simulado"] is True
    assert repo.integracion_comercios_de(cli["grupo_id"]) == []
    assert not repo.es_comercio_gestionado(v["id"])
