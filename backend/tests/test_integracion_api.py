"""API de integración (`/v1/integration`, E1–E10): contrato, auth, alcance, idempotencia, ETag y difusión.

Se prueba contra el FakeRepo en memoria con el TestClient. El comportamiento que el cliente de marketing da por
hecho (y que su doble `uruku_fake.py` implementa) está cubierto acá: la búsqueda de idempotencia va ANTES del
`If-Match`; misma clave + otro cuerpo ⇒ 422 `idempotency_key_reused`; 404 (no 403) fuera del alcance.
"""
from __future__ import annotations

import io
import json
import uuid
from types import SimpleNamespace

import pytest
from PIL import Image

from app.core.config import settings
from app.services import difusion, integracion

BASE = "/v1/integration"


# ───────────────────────────────────────────────────────────────────────────── fixtures y helpers
def _foto(lado=1080) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (lado, lado), (120, 160, 190)).save(buf, "JPEG", quality=85)
    return buf.getvalue()


def _pub(repo, comercio_id, **kw):
    row = {"id": str(uuid.uuid4()), "comercio_id": comercio_id, "tipo": "oferta", "estado": "pendiente",
           "titulo": None, "descripcion": "Espejo 60x90 220 bolivianos", "precio": 220, "moneda": "BOB",
           "origen": "whatsapp", "identidad_origen": "grupo", "remitente_rol": "merchant",
           "created_at": "2026-10-15T14:02:11+00:00", "wa_message_id": f"wa-{uuid.uuid4()}",
           "contacto_whatsapp": "59170000009", "raw": {"from": "59170000009@c.us"}, **kw}
    pub = repo.insert_publicacion(row)
    repo._integ_bump(pub)
    return pub


@pytest.fixture
def mundo(repo, client, monkeypatch):
    """Un cliente de integración con todos los scopes, un comercio gestionado (plan con redes) y otro fuera del alcance."""
    monkeypatch.setattr(settings, "facebook_page_id", "111")
    monkeypatch.setattr(settings, "facebook_page_token", "tok")
    monkeypatch.setattr(settings, "instagram_user_id", "222")
    integracion.reiniciar_limites()
    clave = integracion.emitir_clave(repo, "Marketing", None, "test")
    com = repo.seed_comercio(id=str(uuid.uuid4()), slug="vidrieria-pacheco", nombre="Vidriería Pacheco", plan="destacado",
                             activo=True, confiable=True, verificado=True, codigo="K7M2", whatsapp="59170000009",
                             wa_jid="59170000009@c.us")
    com["_grupo_atado"] = True
    ajeno = repo.seed_comercio(id=str(uuid.uuid4()), slug="ferreteria-ajena", nombre="Ferretería ajena", plan="destacado",
                               activo=True, verificado=True)
    repo.integracion_set_comercio(clave["grupo_id"], com["id"], True, "test")
    return SimpleNamespace(repo=repo, client=client, clave=clave, key=clave["clave"], com=com, ajeno=ajeno)


def H(m, *, idem=None, if_match=None, key=None):
    h = {"Authorization": f"Bearer {key or m.key}"}
    if idem:
        h["Idempotency-Key"] = idem
    if if_match:
        h["If-Match"] = if_match
    return h


def etag(m, pub):
    return integracion.etag_de(m.repo.get_publicacion(pub["id"]))


def error(r):
    assert "error" in r.json(), r.text
    return r.json()["error"]


# ───────────────────────────────────────────────────────────────────────────── E1 · auth y alcance
def test_sin_clave_o_con_clave_mala_es_401_con_el_formato_del_contrato(mundo):
    c = mundo.client
    for h in ({}, {"Authorization": "Bearer nada"}, {"Authorization": "Bearer uki_abcdef123456.secretoequivocadoxxxxxxxx"},
              {"Authorization": f"Bearer uki_{mundo.clave['key_id']}.secretoequivocadoxxxxxxxx"}):
        r = c.get(f"{BASE}/me", headers=h)
        assert r.status_code == 401
        assert error(r)["code"] == "unauthorized"
        assert set(error(r)) == {"code", "message", "details"}


def test_me_dice_scopes_y_solo_los_comercios_del_alcance(mundo):
    r = mundo.client.get(f"{BASE}/me", headers=H(mundo))
    assert r.status_code == 200
    d = r.json()
    assert d["comercios"] == [mundo.com["id"]]
    assert mundo.ajeno["id"] not in json.dumps(d)
    assert set(d["scopes"]) == set(integracion.SCOPES)
    assert d["key_id"] == mundo.clave["key_id"] and d["version"]


def test_una_clave_revocada_da_401_y_una_sin_scope_da_403(mundo):
    solo_lectura = integracion.emitir_clave(mundo.repo, "Lector", ["publications:read"], "test")
    r = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="k1", key=solo_lectura["clave"]),
                          files={"file": ("a.jpg", _foto(), "image/jpeg")})
    assert r.status_code == 403 and error(r)["code"] == "scope_insuficiente"
    integracion.revocar_clave(mundo.repo, mundo.clave["key_id"], "test")
    r = mundo.client.get(f"{BASE}/me", headers=H(mundo))
    assert r.status_code == 401


def test_rate_limit_de_60_por_minuto_por_clave(mundo):
    integracion.reiniciar_limites()
    codigos = [mundo.client.get(f"{BASE}/me", headers=H(mundo)).status_code for _ in range(61)]
    assert codigos[:60] == [200] * 60 and codigos[60] == 429
    r = mundo.client.get(f"{BASE}/me", headers=H(mundo))
    assert r.status_code == 429 and r.headers["Retry-After"].isdigit() and error(r)["code"] == "rate_limited"
    otra = integracion.emitir_clave(mundo.repo, "Otra", None, "test")      # el límite es por clave
    assert mundo.client.get(f"{BASE}/me", headers=H(mundo, key=otra["clave"])).status_code == 200


def test_el_secreto_no_se_guarda_solo_su_sha256(mundo):
    secreto = mundo.key.split(".", 1)[1]
    guardado = mundo.repo.integracion_cliente_por_key_id(mundo.clave["key_id"])
    assert guardado["key_hash"] == integracion.hash_secreto(secreto)
    assert secreto not in json.dumps(guardado)


# ───────────────────────────────────────────────────────────────────────────── E2
def test_merchants_solo_del_alcance_sin_verificado_ni_codigo_ni_telefonos(mundo):
    r = mundo.client.get(f"{BASE}/merchants", headers=H(mundo))
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["slug"] for i in items] == ["vidrieria-pacheco"]
    m = items[0]
    assert set(m) == {"id", "slug", "nombre", "ciudad", "plan", "plan_tiene_redes", "grupo_atado", "activo", "public_url",
                      "broadcast_footer"}
    assert m["plan_tiene_redes"] is True and m["grupo_atado"] is True
    assert m["public_url"].endswith("/comercios/vidrieria-pacheco")
    assert "ref=fb" in m["broadcast_footer"]["facebook"] and "ref=ig" in m["broadcast_footer"]["instagram"]
    crudo = r.text
    for prohibido in ("verificado", "K7M2", "59170000009", "whatsapp", "wa_jid", "Ferretería"):
        assert prohibido not in crudo, prohibido


# ───────────────────────────────────────────────────────────────────────────── E3 / E4
def test_publicaciones_pagina_con_cursor_y_solo_del_alcance(mundo):
    a, b, c = (_pub(mundo.repo, mundo.com["id"], descripcion=f"Oferta {i}") for i in range(3))
    _pub(mundo.repo, mundo.ajeno["id"], descripcion="De otro comercio")
    r1 = mundo.client.get(f"{BASE}/publications?limit=2", headers=H(mundo)).json()
    assert [i["id"] for i in r1["items"]] == [a["id"], b["id"]]
    r2 = mundo.client.get(f"{BASE}/publications?limit=2&cursor={r1['next_cursor']}", headers=H(mundo)).json()
    assert [i["id"] for i in r2["items"]] == [c["id"]]
    r3 = mundo.client.get(f"{BASE}/publications?cursor={r2['next_cursor']}", headers=H(mundo)).json()
    assert r3["items"] == [] and r3["next_cursor"] == r2["next_cursor"]
    # un cambio posterior reaparece desde el cursor
    mundo.repo.update_publicacion(a["id"], {"descripcion": "Cambió"})
    r4 = mundo.client.get(f"{BASE}/publications?cursor={r3['next_cursor']}", headers=H(mundo)).json()
    assert [i["id"] for i in r4["items"]] == [a["id"]]


def test_publicaciones_filtra_por_estado_y_valida_parametros(mundo):
    _pub(mundo.repo, mundo.com["id"])
    _pub(mundo.repo, mundo.com["id"], estado="aprobado")
    r = mundo.client.get(f"{BASE}/publications?estado=aprobado", headers=H(mundo)).json()
    assert [i["estado"] for i in r["items"]] == ["aprobado"]
    for q in ("estado=inventado", "limit=0", "limit=101", "limit=abc", "cursor=%%%"):
        resp = mundo.client.get(f"{BASE}/publications?{q}", headers=H(mundo))
        assert resp.status_code == 422 and error(resp)["code"] == "validation", q


def test_la_publicacion_nunca_trae_telefono_crudo_ni_codigo(mundo):
    p = _pub(mundo.repo, mundo.com["id"], imagen_url=None, ia_veredicto="aprobar", ia_confianza=0.82, terminos_ia="espejo")
    r = mundo.client.get(f"{BASE}/publications/{p['id']}", headers=H(mundo))
    assert r.status_code == 200
    d = r.json()
    assert d["sender_role"] == "merchant" and d["ia"] == {"veredicto": "aprobar", "confianza": 0.82, "terminos": "espejo"}
    assert d["etag"] == r.headers["etag"] == etag(mundo, p)
    assert d["comercio_slug"] == "vidrieria-pacheco" and d["public_url"].endswith("/comercios/vidrieria-pacheco")
    for prohibido in ("59170000009", "wa_message_id", "raw", "wa_jid", "contacto_whatsapp", "K7M2", "moderado"):
        assert prohibido not in r.text, prohibido


def test_detalle_fuera_del_alcance_o_con_id_raro_es_404(mundo):
    ajena = _pub(mundo.repo, mundo.ajeno["id"])
    for pid in (ajena["id"], str(uuid.uuid4()), "no-es-un-uuid", "1;drop"):
        r = mundo.client.get(f"{BASE}/publications/{pid}", headers=H(mundo))
        assert r.status_code == 404 and error(r)["code"] == "not_found", pid


def test_el_remitente_se_deduce_para_publicaciones_viejas():
    assert integracion.remitente_de({"remitente_rol": "third_party"}) == "third_party"
    assert integracion.remitente_de({"origen": "explorador"}) == "uruku_explorer"
    assert integracion.remitente_de({"origen": "panel"}) == "merchant"
    assert integracion.remitente_de({"origen": "whatsapp", "identidad_origen": "numero"}) == "merchant"
    assert integracion.remitente_de({"origen": "whatsapp", "identidad_origen": "grupo"}) is None     # no se sabe: se ignora


def test_media_trae_sha_y_tamano_de_la_foto_propia(mundo, tmp_path):
    destino = tmp_path / "fotos" / "vidrieria"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.mkdir(exist_ok=True)
    (destino / "a.jpg").write_bytes(_foto(300))
    url = settings.public_photo_url("vidrieria/a.jpg")
    p = _pub(mundo.repo, mundo.com["id"], imagen_url=url)
    media = mundo.client.get(f"{BASE}/publications/{p['id']}", headers=H(mundo)).json()["media"]
    assert media[0]["width"] == 300 and media[0]["height"] == 300 and len(media[0]["sha256"]) == 64
    assert media[0]["mime"] == "image/jpeg"


# ───────────────────────────────────────────────────────────────────────────── E5
def _patch(m, p, body, *, idem="k-enrich", if_match=None, raw=None):
    return m.client.patch(f"{BASE}/publications/{p['id']}", headers=H(m, idem=idem, if_match=if_match or etag(m, p)),
                          content=raw if raw is not None else json.dumps(body), )


def test_enriquecer_cambia_el_contenido_pero_no_el_estado(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    antes = etag(mundo, p)
    r = _patch(mundo, p, {"titulo": "Espejo 60×90 cm", "descripcion": "Espejo de pared", "precio": 220, "moneda": "BOB",
                          "descuento_pct": None, "vence_el": "2026-10-22", "tipo": "oferta"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["titulo"] == "Espejo 60×90 cm" and d["vence_el"] == "2026-10-22" and d["estado"] == "pendiente"
    assert d["etag"] != antes and r.headers["etag"] == d["etag"]


@pytest.mark.parametrize("body", [
    {"moneda": "EUR"}, {"precio": 0}, {"precio": -3}, {"precio": "220"}, {"precio": 1.234}, {"vence_el": "22/10"},
    {"descuento_pct": 100}, {"tipo": "otra"}, {"titulo": "x" * 121}, {"no_existe": 1}, {},
])
def test_enriquecer_valida_con_422(mundo, body):
    p = _pub(mundo.repo, mundo.com["id"])
    r = _patch(mundo, p, body)
    assert r.status_code == 422 and error(r)["code"] == "validation"
    assert mundo.repo.get_publicacion(p["id"])["descripcion"] == "Espejo 60x90 220 bolivianos"


def test_escribir_exige_idempotency_key_y_if_match(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    sin_idem = mundo.client.patch(f"{BASE}/publications/{p['id']}", headers=H(mundo, if_match=etag(mundo, p)),
                                  json={"titulo": "a"})
    assert sin_idem.status_code == 422 and error(sin_idem)["code"] == "idempotency_key_required"
    larga = _patch(mundo, p, {"titulo": "a"}, idem="k" * 129)
    assert larga.status_code == 422 and error(larga)["code"] == "idempotency_key_required"
    sin_match = mundo.client.patch(f"{BASE}/publications/{p['id']}", headers=H(mundo, idem="k-1"), json={"titulo": "a"})
    assert sin_match.status_code == 428 and error(sin_match)["code"] == "if_match_required"


def test_if_match_viejo_es_412_si_el_comercio_edito(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    leido = etag(mundo, p)
    mundo.repo.update_publicacion_de_comercio(p["id"], mundo.com["id"], {"descripcion": "Lo cambió el comercio"})
    r = _patch(mundo, p, {"titulo": "Mío"}, if_match=leido)
    assert r.status_code == 412 and error(r)["code"] == "etag_mismatch"
    assert mundo.repo.get_publicacion(p["id"])["titulo"] is None


def test_enriquecer_una_ya_moderada_es_409_not_pending(mundo):
    p = _pub(mundo.repo, mundo.com["id"], estado="aprobado")
    r = _patch(mundo, p, {"titulo": "x"})
    assert r.status_code == 409 and error(r)["code"] == "not_pending"


def test_idempotencia_misma_clave_y_cuerpo_misma_respuesta_sin_reaplicar(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    viejo = etag(mundo, p)
    primera = _patch(mundo, p, {"titulo": "Uno"}, idem="mk:v1:uruku_offer:enrich", if_match=viejo)
    pub_tras = dict(mundo.repo.get_publicacion(p["id"]))
    # reintento tras un timeout: el ETag ya cambió, pero la búsqueda de idempotencia va ANTES del If-Match
    repetida = _patch(mundo, p, {"titulo": "Uno"}, idem="mk:v1:uruku_offer:enrich", if_match=viejo)
    assert repetida.status_code == 200 and repetida.json() == primera.json()
    assert dict(mundo.repo.get_publicacion(p["id"])) == pub_tras             # no se volvió a escribir


def test_misma_clave_y_otro_cuerpo_es_422_idempotency_key_reused(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    _patch(mundo, p, {"titulo": "Uno"}, idem="clave-x")
    r = _patch(mundo, p, {"titulo": "Dos"}, idem="clave-x")
    assert r.status_code == 422 and error(r)["code"] == "idempotency_key_reused"


def test_un_error_no_gasta_la_clave(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    mal = _patch(mundo, p, {"moneda": "EUR"}, idem="clave-y")
    assert mal.status_code == 422
    ok = _patch(mundo, p, {"moneda": "USD"}, idem="clave-y")              # misma clave, otro cuerpo: ya no hay nada guardado
    assert ok.status_code == 200 and ok.json()["moneda"] == "USD"


def test_escribir_fuera_del_alcance_es_404(mundo):
    ajena = _pub(mundo.repo, mundo.ajeno["id"])
    r = mundo.client.patch(f"{BASE}/publications/{ajena['id']}", headers=H(mundo, idem="k", if_match='"x"'), json={"titulo": "a"})
    assert r.status_code == 404
    assert mundo.repo.get_publicacion(ajena["id"])["titulo"] is None


# ───────────────────────────────────────────────────────────────────────────── E6
def test_media_se_sube_idempotente_por_sha256(mundo, tmp_path):
    foto = _foto()
    r1 = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="m1"), files={"file": ("a.jpg", foto, "image/jpeg")})
    assert r1.status_code == 200, r1.text
    d = r1.json()
    assert d["width"] == 1080 and d["height"] == 1080 and d["media_id"].startswith("med_") and len(d["sha256"]) == 64
    r2 = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="m2"), files={"file": ("otro-nombre.jpg", foto, "image/jpeg")})
    assert r2.json() == d                                                 # mismo contenido ⇒ mismo media_id (otra clave)
    assert integracion.resolver_media(d["media_id"]) == d["url"]
    r3 = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="m1"), files={"file": ("a.jpg", foto, "image/jpeg")})
    assert r3.json() == d                                                 # replay de la misma clave
    r4 = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="m1"), files={"file": ("b.jpg", _foto(500), "image/jpeg")})
    assert r4.status_code == 422 and error(r4)["code"] == "idempotency_key_reused"


def test_media_rechaza_lo_que_no_es_jpeg(mundo):
    png = io.BytesIO()
    Image.new("RGB", (10, 10)).save(png, "PNG")
    for contenido in (b"", b"texto plano", png.getvalue(), b"\xff\xd8basura que no es una imagen"):
        r = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem=f"m-{len(contenido)}"),
                              files={"file": ("a.jpg", contenido, "image/jpeg")})
        assert r.status_code == 422 and error(r)["code"] == "validation", contenido[:10]
    sin_archivo = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="m-x"), data={"otro": "x"})
    assert sin_archivo.status_code == 422


def test_resolver_media_no_acepta_ids_raros():
    for malo in (None, "", "med_../../etc/passwd", "med_xyz", "../x", "med_" + "g" * 32):
        assert integracion.resolver_media(malo) is None


# ───────────────────────────────────────────────────────────────────────────── E7
def _aprobar(m, p, *, destinos=("facebook",), texto="Espejo 60×90 cm · Bs 220", media_id=None, idem="k-ap", if_match=None,
             usuario="operador@agencia"):
    dif = {"destinos": list(destinos), "texto": texto}
    if media_id:
        dif["media_id"] = media_id
    body = {"decision": "approve", "actor": {"sistema": "marketing", "usuario": usuario, "approval_id": "ap-1",
                                             "content_hash": "h"}, "difusion": dif}
    return m.client.post(f"{BASE}/publications/{p['id']}/moderation", headers=H(m, idem=idem, if_match=if_match or etag(m, p)),
                         json=body)


def test_aprobar_encola_con_texto_y_pie_de_uruku(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    subida = mundo.client.post(f"{BASE}/media", headers=H(mundo, idem="m"), files={"file": ("a.jpg", _foto(), "image/jpeg")}).json()
    r = _aprobar(mundo, p, destinos=("facebook", "instagram"), media_id=subida["media_id"])
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["estado"] == "aprobado" and d["approved_at"] and d["etag"] == r.headers["etag"]
    assert d["public_url"].endswith("/comercios/vidrieria-pacheco")
    por_destino = {f["destino"]: f for f in d["difusion"]}
    assert set(por_destino) == {"facebook", "instagram"} and all(f["estado"] == "pendiente" for f in d["difusion"])
    fb = por_destino["facebook"]["texto_final"]
    assert fb.startswith("Espejo 60×90 cm · Bs 220") and "Vidriería Pacheco" in fb and "/comercios/vidrieria-pacheco?ref=fb" in fb
    assert "?ref=ig" in por_destino["instagram"]["texto_final"]
    pub = mundo.repo.get_publicacion(p["id"])
    assert pub["estado"] == "aprobado" and pub["moderado_por"] == "integracion:marketing:operador@agencia"
    filas = mundo.repo.difusion_de_publicacion(p["id"])
    assert {f["solicitado_por"] for f in filas} == {"integracion:marketing:operador@agencia"}
    assert {f["texto_override"] for f in filas} == {"Espejo 60×90 cm · Bs 220"}
    assert {f["imagen_url_override"] for f in filas} == {subida["url"]}


def test_aprobar_sin_difusion_solo_aprueba(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    body = {"decision": "approve", "actor": {"usuario": "op"}}
    r = mundo.client.post(f"{BASE}/publications/{p['id']}/moderation", headers=H(mundo, idem="k", if_match=etag(mundo, p)), json=body)
    assert r.status_code == 200 and r.json()["difusion"] == []
    assert mundo.repo.difusion == []


def test_aprobar_dos_veces_es_409_not_pending_y_con_etag_viejo_412(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    viejo = etag(mundo, p)
    assert _aprobar(mundo, p, idem="a1").status_code == 200
    ya = _aprobar(mundo, p, idem="a2", if_match=etag(mundo, p))
    assert ya.status_code == 409 and error(ya)["code"] == "not_pending"
    stale = _aprobar(mundo, p, idem="a3", if_match=viejo)
    assert stale.status_code == 412 and error(stale)["code"] == "etag_mismatch"


def test_reintentar_la_misma_aprobacion_devuelve_lo_mismo_y_no_duplica(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    viejo = etag(mundo, p)
    r1 = _aprobar(mundo, p, idem="mk:v1:uruku_offer:approve", if_match=viejo)
    r2 = _aprobar(mundo, p, idem="mk:v1:uruku_offer:approve", if_match=viejo)      # timeout simulado: reintento con el ETag viejo
    assert r2.status_code == 200 and r2.json() == r1.json()
    assert len(mundo.repo.difusion_de_publicacion(p["id"])) == 1


def test_aprobar_si_el_comercio_edito_mientras_tanto_no_aprueba(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    leido = etag(mundo, p)
    mundo.repo.update_publicacion_de_comercio(p["id"], mundo.com["id"], {"precio": 999})
    r = _aprobar(mundo, p, if_match=leido)
    assert r.status_code == 412
    assert mundo.repo.get_publicacion(p["id"])["estado"] == "pendiente"


def test_condicion_de_carrera_se_detecta_en_el_update_condicional(mundo, monkeypatch):
    """El ETag coincide al leer, pero alguien toca la fila antes del UPDATE: no se aprueba (412)."""
    p = _pub(mundo.repo, mundo.com["id"])
    original = mundo.repo.integracion_get_publicacion

    def leer_y_que_alguien_toque(pub_id):
        pub = original(pub_id)
        mundo.repo.update_publicacion(pub_id, {"descripcion": "alguien la tocó justo ahora"})   # mueve updated_at
        return pub

    monkeypatch.setattr(mundo.repo, "integracion_get_publicacion", leer_y_que_alguien_toque)
    r = _aprobar(mundo, p, destinos=())
    assert r.status_code == 412
    assert mundo.repo.get_publicacion(p["id"])["estado"] == "pendiente"


@pytest.mark.parametrize("cambio,codigo,estado", [
    ({"plan": "gratis"}, "destino_no_habilitado_por_plan", 422),
    ({"activo": False}, "comercio_de_baja", 409),
])
def test_aprobar_valida_plan_y_baja(mundo, cambio, codigo, estado):
    mundo.com.update(cambio)
    p = _pub(mundo.repo, mundo.com["id"])
    r = _aprobar(mundo, p)
    assert r.status_code == estado and error(r)["code"] == codigo
    assert mundo.repo.get_publicacion(p["id"])["estado"] == "pendiente" and mundo.repo.difusion == []


def test_aprobar_valida_destinos_media_y_configuracion(mundo, monkeypatch):
    p = _pub(mundo.repo, mundo.com["id"])
    assert _aprobar(mundo, p, destinos=("tiktok",), idem="v1").status_code == 422
    assert _aprobar(mundo, p, destinos=("facebook",), texto="  ", idem="v2").status_code == 422
    r = _aprobar(mundo, p, media_id="med_" + "0" * 32, idem="v3")
    assert r.status_code == 422 and error(r)["code"] == "media_not_found"
    monkeypatch.setattr(settings, "instagram_user_id", "")
    r = _aprobar(mundo, p, destinos=("instagram",), idem="v4")
    assert r.status_code == 422 and error(r)["code"] == "destino_no_configurado"
    r = mundo.client.post(f"{BASE}/publications/{p['id']}/moderation", headers=H(mundo, idem="v5", if_match=etag(mundo, p)),
                          json={"decision": "approve"})
    assert r.status_code == 422                                          # falta actor.usuario
    assert mundo.repo.get_publicacion(p["id"])["estado"] == "pendiente"


def test_instagram_sin_imagen_no_se_aprueba(mundo):
    p = _pub(mundo.repo, mundo.com["id"], imagen_url=None)
    r = _aprobar(mundo, p, destinos=("instagram",))
    assert r.status_code == 422 and "imagen" in error(r)["message"]


def test_el_codigo_que_ya_no_coincide_es_409_sin_filtrar_los_codigos(mundo):
    p = _pub(mundo.repo, mundo.com["id"], identidad_origen="codigo", codigo_recibido="ZZZZ")
    r = _aprobar(mundo, p)
    assert r.status_code == 409 and error(r)["code"] == "codigo_no_coincide"
    assert "ZZZZ" not in r.text and "K7M2" not in r.text and "URUKU-" not in r.text


def test_rechazar_baja_la_publicacion_con_motivo(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    body = {"decision": "reject", "motivo": "complemento_de:123", "actor": {"sistema": "marketing", "usuario": "op"}}
    r = mundo.client.post(f"{BASE}/publications/{p['id']}/moderation", headers=H(mundo, idem="rj", if_match=etag(mundo, p)), json=body)
    assert r.status_code == 200 and r.json()["estado"] == "rechazado"
    pub = mundo.repo.get_publicacion(p["id"])
    assert pub["estado"] == "rechazado" and pub["motivo_moderacion"] == "complemento_de:123"
    assert pub["moderado_por"] == "integracion:marketing:op"


def test_decision_invalida_es_422(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    r = mundo.client.post(f"{BASE}/publications/{p['id']}/moderation", headers=H(mundo, idem="d", if_match=etag(mundo, p)),
                          json={"decision": "cambios", "actor": {"usuario": "x"}})
    assert r.status_code == 422


# ───────────────────────────────────────────────────────────────────────────── E8 / E9 / E10
@pytest.fixture
def aprobada(mundo):
    """Una publicación aprobada por la integración con filas a Facebook e Instagram, y el envío a Meta capturado."""
    p = _pub(mundo.repo, mundo.com["id"], imagen_url=settings.public_photo_url("x/y.jpg"))
    assert _aprobar(mundo, p, destinos=("facebook", "instagram")).status_code == 200
    enviados: list[tuple] = []
    resultados = {"facebook": difusion.Publicado("https://www.facebook.com/111_9", external_post_id="111_9"),
                  "instagram": difusion.Publicado(None, external_post_id="ig_9", ig_container_id="cont_9")}
    mundo.enviados, mundo.resultados = enviados, resultados
    return p


def _stub_envios(monkeypatch, mundo):
    monkeypatch.setattr(difusion, "_ENVIOS", {
        d: (lambda texto, img, _d=d, **kw: mundo.enviados.append((_d, texto, img, kw)) or mundo.resultados.get(_d))
        for d in difusion.DESTINOS})


def _enviar(m, p, idem="k-send", if_match=None):
    return m.client.post(f"{BASE}/publications/{p['id']}/broadcasts/send", headers=H(m, idem=idem, if_match=if_match or etag(m, p)),
                         json={})


def test_e8_lista_las_filas_de_la_publicacion(mundo, aprobada):
    r = mundo.client.get(f"{BASE}/publications/{aprobada['id']}/broadcasts", headers=H(mundo))
    assert r.status_code == 200
    items = r.json()["items"]
    assert {i["destino"] for i in items} == {"facebook", "instagram"}
    assert set(items[0]) == {"fila_id", "destino", "estado", "intentos", "motivo", "external_post_id", "permalink",
                             "enviado_at", "verificado_at"}
    assert mundo.client.get(f"{BASE}/publications/{uuid.uuid4()}/broadcasts", headers=H(mundo)).status_code == 404


def test_e9_envia_con_el_texto_aprobado_y_guarda_los_ids_y_no_reenvia(mundo, aprobada, monkeypatch):
    _stub_envios(monkeypatch, mundo)
    r = _enviar(mundo, aprobada)
    assert r.status_code == 200, r.text
    filas = {i["destino"]: i for i in r.json()["items"]}
    assert {f["estado"] for f in filas.values()} == {"enviado"}
    assert filas["facebook"]["external_post_id"] == "111_9" and filas["instagram"]["external_post_id"] == "ig_9"
    destino, texto, img, _ = next(e for e in mundo.enviados if e[0] == "facebook")
    assert texto.startswith("Espejo 60×90 cm · Bs 220") and "?ref=fb" in texto
    ig = next(f for f in mundo.repo.difusion_de_publicacion(aprobada["id"]) if f["destino"] == "instagram")
    assert ig["ig_container_id"] == "cont_9" and ig["external_post_id"] == "ig_9"
    # otra clave: las filas ya enviadas NO se reenvían
    n = len(mundo.enviados)
    r2 = _enviar(mundo, aprobada, idem="k-send-2")
    assert r2.status_code == 200 and len(mundo.enviados) == n
    # misma clave: replay sin tocar nada
    assert _enviar(mundo, aprobada, idem="k-send").json() == r.json()


def test_e9_exige_aprobada_y_if_match(mundo):
    p = _pub(mundo.repo, mundo.com["id"])
    r = _enviar(mundo, p)
    assert r.status_code == 409 and error(r)["code"] == "not_approved"
    sin = mundo.client.post(f"{BASE}/publications/{p['id']}/broadcasts/send", headers=H(mundo, idem="x"), json={})
    assert sin.status_code == 428


def test_las_filas_de_la_integracion_no_las_manda_el_worker_ni_el_boton_de_enviar_todo(mundo, aprobada, monkeypatch):
    _stub_envios(monkeypatch, mundo)
    monkeypatch.setattr(settings, "difusion_auto", "wa_canal,facebook,instagram")
    r = difusion.enviar_pendientes(mundo.repo, 10, solo_auto=True, pausa=0)
    assert r["procesados"] == 0 and mundo.enviados == []
    r = difusion.enviar_pendientes(mundo.repo, 10, solo_auto=False, pausa=0)
    assert r["procesados"] == 0 and mundo.enviados == []


def test_e9_dos_pedidos_a_la_vez_no_mandan_la_misma_fila_dos_veces(mundo, aprobada, monkeypatch):
    """La fila se reclama (pendiente → incierto) con un UPDATE condicional ANTES de llamar a Meta."""
    _stub_envios(monkeypatch, mundo)
    fila = mundo.repo.difusion_de_publicacion(aprobada["id"])[0]
    assert mundo.repo.reclamar_difusion(fila["id"]) is True
    r = difusion.procesar(mundo.repo, fila, reclamar=True)                # otro proceso ya la tomó
    assert r["estado"] == "omitido" and mundo.enviados == []


def test_e9_un_timeout_deja_la_fila_incierta_y_el_reintento_consulta_antes(mundo, aprobada, monkeypatch):
    llamadas = []

    def fb(texto, img, **kw):
        raise difusion.DifusionIncierta("sin respuesta de Meta (ReadTimeout): puede haber salido")

    monkeypatch.setattr(difusion, "_ENVIOS", {"facebook": fb, "instagram": lambda t, i, **kw: llamadas.append("ig") or difusion.Publicado(None, external_post_id="ig_1"),
                                              "wa_canal": lambda t, i: None})
    r = _enviar(mundo, aprobada, idem="t1")
    estados = {i["destino"]: i["estado"] for i in r.json()["items"]}
    assert estados == {"facebook": "incierto", "instagram": "enviado"}
    # Meta SÍ lo había publicado: el reintento lo encuentra y NO lo vuelve a mandar
    monkeypatch.setattr(difusion, "_buscar_en_facebook",
                        lambda texto: difusion.Publicado("https://www.facebook.com/111_7", external_post_id="111_7"))
    mandados = []
    monkeypatch.setattr(difusion, "_ENVIOS", {"facebook": lambda t, i, **kw: mandados.append(1), "instagram": lambda *a, **k: None,
                                              "wa_canal": lambda t, i: None})
    r2 = _enviar(mundo, aprobada, idem="t2")
    fb_fila = next(i for i in r2.json()["items"] if i["destino"] == "facebook")
    assert fb_fila["estado"] == "enviado" and fb_fila["external_post_id"] == "111_7" and mandados == []


def test_e9_incierta_que_no_aparece_en_meta_se_reintenta(mundo, aprobada, monkeypatch):
    def fb(texto, img, **kw):
        raise difusion.DifusionIncierta("timeout")

    monkeypatch.setattr(difusion, "_ENVIOS", {"facebook": fb, "instagram": lambda *a, **k: difusion.Publicado(None, external_post_id="i"),
                                              "wa_canal": lambda t, i: None})
    _enviar(mundo, aprobada, idem="u1")
    monkeypatch.setattr(difusion, "_buscar_en_facebook", lambda texto: None)         # Meta contesta y no hay rastro
    monkeypatch.setattr(difusion, "_ENVIOS", {"facebook": lambda t, i, **kw: difusion.Publicado(None, external_post_id="111_5"),
                                              "instagram": lambda *a, **k: None, "wa_canal": lambda t, i: None})
    r = _enviar(mundo, aprobada, idem="u2")
    assert next(i for i in r.json()["items"] if i["destino"] == "facebook")["estado"] == "enviado"


def test_e10_verifica_en_graph_y_guarda_permalink_y_verificado_at(mundo, aprobada, monkeypatch):
    _stub_envios(monkeypatch, mundo)
    _enviar(mundo, aprobada)
    fila = next(f for f in mundo.repo.difusion_de_publicacion(aprobada["id"]) if f["destino"] == "facebook")
    pedidos = []

    def graph(metodo, ruta, *, datos=None, campos=None):
        pedidos.append((metodo, ruta, campos))
        return {"id": ruta, "permalink_url": f"https://www.facebook.com/{ruta}"}

    monkeypatch.setattr(difusion, "_a_meta", graph)
    r = mundo.client.post(f"{BASE}/broadcasts/{fila['id']}/verify", headers=H(mundo, idem="v1"), json={})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["permalink"] == "https://www.facebook.com/111_9" and d["verificado_at"]
    assert pedidos == [("GET", "111_9", "id,permalink_url")]                 # sólo pide lo que necesita


def test_e10_errores(mundo, aprobada, monkeypatch):
    filas = {f["destino"]: f for f in mundo.repo.difusion_de_publicacion(aprobada["id"])}
    r = mundo.client.post(f"{BASE}/broadcasts/{filas['facebook']['id']}/verify", headers=H(mundo, idem="e1"), json={})
    assert r.status_code == 409 and error(r)["code"] == "not_sent"
    assert mundo.client.post(f"{BASE}/broadcasts/{uuid.uuid4()}/verify", headers=H(mundo, idem="e2"), json={}).status_code == 404
    assert mundo.client.post(f"{BASE}/broadcasts/xyz/verify", headers=H(mundo, idem="e3"), json={}).status_code == 404
    # una fila de un comercio fuera del alcance es 404
    ajena = _pub(mundo.repo, mundo.ajeno["id"], estado="aprobado")
    mundo.repo.encolar_difusion(ajena["id"], ["facebook"])
    fa = mundo.repo.difusion_de_publicacion(ajena["id"])[0]
    assert mundo.client.post(f"{BASE}/broadcasts/{fa['id']}/verify", headers=H(mundo, idem="e4"), json={}).status_code == 404
    # Graph no encuentra el posteo ⇒ 409 verification_failed; Graph caído ⇒ 502
    _stub_envios(monkeypatch, mundo)
    _enviar(mundo, aprobada)
    monkeypatch.setattr(difusion, "_a_meta", lambda *a, **k: (_ for _ in ()).throw(difusion.DifusionError("Meta respondió HTTP 404")))
    r = mundo.client.post(f"{BASE}/broadcasts/{filas['facebook']['id']}/verify", headers=H(mundo, idem="e5"), json={})
    assert r.status_code == 409 and error(r)["code"] == "verification_failed"
    monkeypatch.setattr(difusion, "_a_meta", lambda *a, **k: (_ for _ in ()).throw(difusion.DifusionIncierta("timeout")))
    r = mundo.client.post(f"{BASE}/broadcasts/{filas['facebook']['id']}/verify", headers=H(mundo, idem="e6"), json={})
    assert r.status_code == 502


# ───────────────────────────────────────────────────────────────────────────── el ciclo completo, como lo usa marketing
def test_ciclo_completo_leer_enriquecer_subir_aprobar_enviar_verificar(mundo, monkeypatch):
    _stub_envios(monkeypatch, mundo)
    mundo.resultados = {"facebook": difusion.Publicado("https://www.facebook.com/111_1", external_post_id="111_1"),
                        "instagram": None}
    mundo.enviados = []
    p = _pub(mundo.repo, mundo.com["id"])
    c, h = mundo.client, lambda **k: H(mundo, **k)
    item = c.get(f"{BASE}/publications", headers=h()).json()["items"][0]
    assert item["id"] == p["id"]
    enr = c.patch(f"{BASE}/publications/{p['id']}", headers=h(idem="mk:1:uruku_offer:enrich", if_match=item["etag"]),
                  json={"titulo": "Espejo 60×90 cm", "vence_el": "2026-10-22"}).json()
    med = c.post(f"{BASE}/media", headers=h(idem="mk:1:uruku_offer:media"), files={"file": ("c.jpg", _foto(), "image/jpeg")}).json()
    ap = c.post(f"{BASE}/publications/{p['id']}/moderation", headers=h(idem="mk:1:uruku_offer:approve", if_match=enr["etag"]),
                json={"decision": "approve", "actor": {"sistema": "marketing", "usuario": "op"},
                      "difusion": {"destinos": ["facebook"], "texto": "Espejo · Bs 220", "media_id": med["media_id"]}}).json()
    sent = c.post(f"{BASE}/publications/{p['id']}/broadcasts/send", headers=h(idem="mk:1:uruku_facebook:broadcast_send", if_match=ap["etag"]),
                  json={}).json()
    assert sent["items"][0]["estado"] == "enviado"
    monkeypatch.setattr(difusion, "_a_meta", lambda m, r, **k: {"id": r, "permalink_url": f"https://fb/{r}"})
    ver = c.post(f"{BASE}/broadcasts/{sent['items'][0]['fila_id']}/verify", headers=h(idem="verify-1"), json={}).json()
    assert ver["verificado_at"] and ver["permalink"] == "https://fb/111_1"
    assert mundo.enviados[0][2] == med["url"]                                # salió con la imagen de marketing
