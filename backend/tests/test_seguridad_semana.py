"""Lote «Esta semana» de la revisión de seguridad de noviembre (código, lado backend).

Cubre: cliente PostgREST por la red interna, «¿te contestó?» atado a la sesión (A-04), recuperar cuenta con
token de solicitud (M-02), autoregistro oculto hasta confirmar (M-05), comprobantes y fotos del trámite
en disco privado (M-11), bloqueo y hash del panel (M-06) y las bajas (B-02, B-05, B-06, B-12, B-13).
"""
import hashlib
import json
import re
import shutil
import subprocess
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from app.api import campo as campo_mod
from app.core import auth, firmas
from app.core.config import settings

C1 = "00000000-0000-4000-8000-0000000000c1"   # los comercios_id de /lead tienen que ser uuid (0193)
C2 = "00000000-0000-4000-8000-0000000000c2"
C3 = "00000000-0000-4000-8000-0000000000c3"

APP = Path(__file__).resolve().parents[1] / "app"
MIGRACIONES = Path(__file__).resolve().parents[2] / "supabase" / "migrations"


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _jpg():
    buf = BytesIO()
    Image.new("RGB", (20, 20), color="red").save(buf, format="JPEG")
    return buf.getvalue()


# ══════════════════════════════════════════ 1. cliente PostgREST por la red interna
def test_el_cliente_directo_no_lleva_rest_v1_y_manda_la_llave_service_role():
    from postgrest import SyncPostgrestClient

    from app.db.session import crear_cliente_directo

    c = crear_cliente_directo("http://buscadonde-postgrest:3000/", "LLAVE")
    assert isinstance(c, SyncPostgrestClient)
    assert str(c.session.base_url).rstrip("/") == "http://buscadonde-postgrest:3000"
    assert "/rest/v1" not in str(c.session.base_url)
    assert c.session.headers["apikey"] == "LLAVE"
    assert c.session.headers["Authorization"] == "Bearer LLAVE"
    # la API que usa el repositorio
    assert callable(c.from_) and callable(c.rpc)


def test_get_supabase_usa_la_url_interna_si_esta_y_sino_el_cliente_de_siempre(monkeypatch):
    from app.db import session

    monkeypatch.setattr(settings, "supabase_service_role_key", "eyJhbGciOi.eyJyb2xlIjoi.firma")   # forma de JWT
    monkeypatch.setattr(settings, "supabase_url", "https://db.ejemplo.bo")

    session.get_supabase.cache_clear()
    monkeypatch.setattr(settings, "postgrest_internal_url", "http://buscadonde-postgrest:3000")
    interno = session.get_supabase()
    assert str(interno.session.base_url).rstrip("/") == "http://buscadonde-postgrest:3000"

    session.get_supabase.cache_clear()
    monkeypatch.setattr(settings, "postgrest_internal_url", "")
    publico = session.get_supabase()
    # el comportamiento de siempre: supabase-py agrega /rest/v1
    assert str(publico.postgrest.session.base_url).rstrip("/") == "https://db.ejemplo.bo/rest/v1"
    session.get_supabase.cache_clear()


def test_get_supabase_sin_llave_falla_con_un_mensaje_claro(monkeypatch):
    from app.db import session

    session.get_supabase.cache_clear()
    monkeypatch.setattr(settings, "supabase_service_role_key", "")
    with pytest.raises(RuntimeError, match="SUPABASE_SERVICE_ROLE_KEY"):
        session.get_supabase()
    session.get_supabase.cache_clear()


def test_el_backend_solo_usa_table_rpc_y_from_del_cliente():
    """Si algún día algo usa storage/auth/functions/realtime de supabase-py, el cliente directo a
    PostgREST (sin /rest/v1) no lo tiene: este test avisa."""
    prohibidos = re.compile(r"\b(_db|get_supabase\(\)|supabase|client)\.(storage|auth|functions|realtime|channel)\b")
    for ruta in APP.rglob("*.py"):
        assert not prohibidos.search(ruta.read_text(encoding="utf-8")), f"{ruta} usa algo que no es PostgREST"
    for ruta in (APP / "db").glob("*.py"):
        for metodo in set(re.findall(r"self\._db\.([a-z_]+)\(", ruta.read_text(encoding="utf-8"))):
            assert metodo in {"table", "rpc", "from_"}, f"{ruta.name}: self._db.{metodo}"


# ══════════════════════════════════════════ 2. A-04 «¿te contestó?»
def _lead(client, repo, comercio=C1, sesion="sesion-aaaa", minutos=5, tipo="whatsapp"):
    repo.comercios.setdefault(comercio, {"id": comercio, "slug": comercio, "nombre": comercio, "activo": True})
    r = client.post("/lead", json={"comercio_id": comercio, "tipo": tipo, "sesion": sesion}).json()
    for l in repo.leads:
        if l["id"] == r["id"]:
            l["created_at"] = (datetime.now(timezone.utc) - timedelta(minutes=minutos)).isoformat()
    return r


def _votar(client, lead, respondio=False, ip=None, **extra):
    cuerpo = {"respondio": respondio, "token": lead["token"], "sesion": "sesion-aaaa", **extra}
    return client.post(f"/lead/{lead['id']}/respondio", json=cuerpo, headers={"x-forwarded-for": ip} if ip else {})


def test_lead_devuelve_id_y_token_atado_a_la_sesion(client, repo):
    r = _lead(client, repo, sesion="sesion-aaaa")
    assert r["token"] == firmas.token_de_lead(r["id"], "sesion-aaaa")
    assert r["token"] != firmas.token_de_lead(r["id"], "otra-sesion")
    assert len(r["token"]) == 64


def test_el_token_del_lead_usa_su_propia_clave(monkeypatch):
    base = firmas.token_de_lead("L1", "s")
    monkeypatch.setattr(settings, "lead_token_secret", "una-clave-propia-de-los-leads")
    assert firmas.token_de_lead("L1", "s") != base
    # y no es la del JWT: cambiar el JWT no mueve el token cuando hay clave propia
    propio = firmas.token_de_lead("L1", "s")
    monkeypatch.setattr(settings, "jwt_secret", "otro-jwt-distinto-de-32-caracteres-xxx")
    assert firmas.token_de_lead("L1", "s") == propio


def test_voto_con_token_correcto_y_sesion(client, repo):
    lead = _lead(client, repo)
    r = _votar(client, lead)
    assert r.status_code == 200 and r.json()["contacto_no"] == 1


def test_un_token_de_otro_contacto_o_de_otra_sesion_no_sirve(client, repo):
    a, b = _lead(client, repo), _lead(client, repo, sesion="sesion-bbbb")
    # token de b sobre el contacto a
    assert client.post(f"/lead/{a['id']}/respondio", json={"respondio": False, "token": b["token"],
                                                           "sesion": "sesion-aaaa"}).status_code == 403
    # token de a pero otra sesión
    assert client.post(f"/lead/{a['id']}/respondio", json={"respondio": False, "token": a["token"],
                                                           "sesion": "sesion-zzzz"}).status_code == 403
    assert repo.leads[0].get("respondio") is None


def test_sin_token_pasa_en_la_gracia_con_aviso_y_deja_de_pasar_despues(client, repo, monkeypatch):
    lead = _lead(client, repo)
    monkeypatch.setattr(settings, "lead_token_obligatorio_desde", "2999-01-01")
    assert client.post(f"/lead/{lead['id']}/respondio", json={"respondio": False}).status_code == 200
    lead2 = _lead(client, repo, sesion="sesion-bbbb", comercio=C2)
    monkeypatch.setattr(settings, "lead_token_obligatorio_desde", "2020-01-01")
    assert client.post(f"/lead/{lead2['id']}/respondio", json={"respondio": False}).status_code == 403


def test_el_contacto_tiene_que_tener_dos_minutos(client, repo):
    nuevo = _lead(client, repo, minutos=0)
    r = _votar(client, nuevo)
    assert r.status_code == 425
    assert repo.leads[0].get("respondio") is None
    for l in repo.leads:                     # pasan los 2 minutos
        l["created_at"] = (datetime.now(timezone.utc) - timedelta(minutes=3)).isoformat()
    assert _votar(client, nuevo).status_code == 200


def test_un_contacto_de_mas_de_una_semana_ya_no_vota(client, repo):
    viejo = _lead(client, repo, minutos=60 * 24 * 8)
    assert _votar(client, viejo).status_code == 410


def test_un_solo_voto_por_contacto(client, repo):
    lead = _lead(client, repo)
    assert _votar(client, lead, False).json()["contacto_no"] == 1
    otra = _votar(client, lead, True).json()
    assert otra == {"ok": True, "ya": True}
    assert repo.comercios[C1]["contacto_ok"] == 0


def test_un_mismo_votante_vota_una_vez_por_comercio_cada_30_dias(client, repo):
    uno, dos = _lead(client, repo), _lead(client, repo)
    assert _votar(client, uno, False).json()["contacto_no"] == 1
    # el segundo contacto del MISMO votante sobre el mismo comercio no suma
    assert _votar(client, dos, False).json() == {"ok": True, "ya": True}
    assert repo.comercios[C1]["contacto_no"] == 1
    # otro comercio: sí puede
    otro = _lead(client, repo, comercio=C2)
    assert _votar(client, otro, False).status_code == 200 and "ya" not in _votar(client, _lead(client, repo, comercio=C3)).json()


def test_a_lo_sumo_diez_votos_por_dia_desde_una_ip(client, repo):
    estados = []
    for i in range(12):
        lead = _lead(client, repo, comercio=str(uuid.UUID(int=i + 1)))
        estados.append(_votar(client, lead, True).status_code)
    assert estados[:10] == [200] * 10 and estados[10:] == [429, 429]


def test_los_contactos_por_ip_y_comercio_tienen_tope(client, repo):
    repo.comercios[C1] = {"id": C1, "slug": C1, "nombre": "C1", "activo": True}
    ids = [client.post("/lead", json={"comercio_id": C1, "tipo": "whatsapp"}).json()["id"] for _ in range(25)]
    # Sin sesión no hay deduplicación: sólo frena el techo de la IP (10 de cada tipo por comercio y por día).
    assert sum(1 for i in ids if i) == 10 and len(repo.leads) == 10


def test_el_sello_no_responde_exige_tres_votantes_distintos(client, repo):
    """Cinco «no» de antes (sin votante) o de pocos votantes no encienden el sello (contacto_no >= 5)."""
    repo.comercios[C1] = {"id": C1, "slug": C1, "nombre": "C1", "activo": True}
    ahora = datetime.now(timezone.utc).isoformat()
    for i in range(6):                        # 6 «no» heredados: sin `respondio_por`
        repo.leads.append({"id": f"viejo{i}", "comercio_id": C1, "tipo": "whatsapp", "respondio": False,
                           "respondio_en": ahora, "created_at": ahora})
    assert repo.recontar_contactos(C1)["contacto_no"] == 4          # tapado: sin el sello
    # Un votante es una RED (la IP), no una sesión: dos redes nuevas siguen tapadas; la tercera lo destapa.
    for sesion, ip in (("sesion-v001", "203.0.113.1"), ("sesion-v002", "203.0.113.2")):
        lead = _lead(client, repo, sesion=sesion)
        assert _votar(client, lead, sesion=sesion, ip=ip).json()["contacto_no"] == 4
    lead = _lead(client, repo, sesion="sesion-v003")
    assert _votar(client, lead, sesion="sesion-v003", ip="203.0.113.3").json()["contacto_no"] == 9


def test_el_ip_y_la_sesion_no_se_guardan_en_claro(client, repo):
    lead = _lead(client, repo, sesion="sesion-secreta")
    _votar(client, lead, sesion="sesion-secreta")
    voto = next(l for l in repo.leads if l.get("respondio") is not None)
    assert re.fullmatch(r"[0-9a-f]{32}", voto["respondio_por"])
    assert voto["respondio_por"] == firmas.votante_de("testclient", "sesion-secreta")
    assert "sesion-secreta" not in voto["respondio_por"] and "testclient" not in voto["respondio_por"]


# ══════════════════════════════════════════ 3. M-02 recuperar cuenta
def _registrar(client, whatsapp="59170001111", nombre="Mi Tienda"):
    r = client.post("/auth/comercio/registro",
                    data={"nombre": nombre, "whatsapp": whatsapp, "lat": "-22.7361", "lng": "-64.3433"},
                    files={"foto": ("t.jpg", BytesIO(_jpg()), "image/jpeg")})
    assert r.status_code == 200, r.text
    return r.json()


def test_recuperar_devuelve_un_token_de_128_bits_que_cambia_con_cada_codigo(client, repo):
    _registrar(client)
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "59170001111"}).json()
    assert re.fullmatch(r"[0-9a-f]{32}", r["token"])
    cuenta = repo.get_comercio_usuario_por_whatsapp("59170001111")
    esperado = firmas.token_de_recuperacion(cuenta["id"], r["codigo"], cuenta["reset_code_expira"])
    assert r["token"] == esperado
    assert firmas.token_de_recuperacion(cuenta["id"], "000000", cuenta["reset_code_expira"]) != r["token"]


def test_el_token_de_recuperacion_es_el_mismo_con_el_vencimiento_en_otro_formato():
    """La base devuelve el timestamp como `+00:00` con microsegundos o como `Z`: el token no puede cambiar."""
    a = firmas.token_de_recuperacion("u1", "123456", "2026-11-05T12:00:00.123456+00:00")
    assert a == firmas.token_de_recuperacion("u1", "123456", "2026-11-05T12:00:00.123456Z")
    assert a == firmas.token_de_recuperacion("u1", "123456", "2026-11-05T12:00:00+00:00")


def test_estado_exige_el_token_y_con_uno_ajeno_dice_que_no(client, repo):
    client.auto_token = False                 # acá el token se manda (o no) a mano
    _registrar(client)
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "59170001111"}).json()
    base = {"whatsapp": "59170001111", "codigo": r["codigo"]}
    assert client.get("/auth/comercio/recuperar/estado", params=base).status_code == 422        # sin token
    assert client.get("/auth/comercio/recuperar/estado",
                      params={**base, "token": "0" * 32}).json() == {"confirmado": False}
    repo.confirmar_reset_code_comercio("59170001111", r["codigo"])
    # el que sólo sabe el código (el oráculo de antes) ve lo mismo que si no existiera
    assert client.get("/auth/comercio/recuperar/estado",
                      params={**base, "token": "0" * 32}).json() == {"confirmado": False}
    assert client.get("/auth/comercio/recuperar/estado",
                      params={**base, "token": r["token"]}).json() == {"confirmado": True}


def test_confirmar_exige_el_token(client, repo):
    client.auto_token = False
    _registrar(client)
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "59170001111"}).json()
    repo.confirmar_reset_code_comercio("59170001111", r["codigo"])
    cuerpo = {"whatsapp": "59170001111", "codigo": r["codigo"]}
    assert client.post("/auth/comercio/recuperar/confirmar", json=cuerpo).status_code == 422
    malo = client.post("/auth/comercio/recuperar/confirmar", json={**cuerpo, "token": "f" * 32})
    assert malo.status_code == 400 and malo.json()["detail"] == "Código incorrecto"
    ok = client.post("/auth/comercio/recuperar/confirmar", json={**cuerpo, "token": r["token"]})
    assert ok.status_code == 200 and ok.json()["access_token"]


def test_no_se_pisa_un_codigo_vigente(client, repo):
    _registrar(client)
    primero = client.post("/auth/comercio/recuperar", json={"whatsapp": "59170001111"})
    segundo = client.post("/auth/comercio/recuperar", json={"whatsapp": "59170001111"})
    assert primero.status_code == 200 and segundo.status_code == 409
    assert "codigo" not in segundo.json() and "token" not in segundo.json()
    cuenta = repo.get_comercio_usuario_por_whatsapp("59170001111")
    assert cuenta["reset_code"] == primero.json()["codigo"]            # el del primero sigue en pie


def test_vencido_el_codigo_se_puede_pedir_otro(client, repo):
    _registrar(client)
    client.post("/auth/comercio/recuperar", json={"whatsapp": "59170001111"})
    cuenta = repo.get_comercio_usuario_por_whatsapp("59170001111")
    cuenta["reset_code_expira"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    assert client.post("/auth/comercio/recuperar", json={"whatsapp": "59170001111"}).status_code == 200


def test_el_mensaje_precargado_dice_que_es_para_entrar_desde_otro_telefono(client, repo):
    from urllib.parse import parse_qs, urlparse

    _registrar(client)
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "59170001111"}).json()
    texto = parse_qs(urlparse(r["wa_link"]).query)["text"][0]
    assert "Quiero ENTRAR a mi cuenta de URUKU desde otro teléfono" in texto
    assert texto.startswith(f"CONFIRMAR-{r['codigo']}")


# ══════════════════════════════════════════ 4. M-05 autoregistro oculto
def test_el_comercio_que_se_registra_solo_nace_oculto_con_aviso(client, repo):
    data = _registrar(client)
    c = next(iter(repo.comercios.values()))
    assert c["activo"] is False and c["baja_motivo"] == "sin_verificar"
    assert c["confiable"] is False
    assert data["oculto_hasta_confirmar"] is True and "no se ve" in data["aviso"]
    # no sale en ningún listado público (todos filtran activo)
    assert all(not x.get("activo") for x in repo.comercios.values())


def test_el_dueno_oculto_puede_entrar_y_no_se_registra_dos_veces(client, repo):
    data = _registrar(client)
    assert client.get("/comercio/perfil", headers=_h(data["access_token"])).status_code == 200
    # el número sigue ocupado: nadie le cuelga otro negocio
    otra = client.post("/auth/comercio/registro",
                       data={"nombre": "Otro", "whatsapp": "59170001111", "lat": "-22.7", "lng": "-64.3"},
                       files={"foto": ("t.jpg", BytesIO(_jpg()), "image/jpeg")})
    assert otra.status_code == 409


def test_confirmar_el_numero_por_whatsapp_lo_enciende(client, repo):
    _registrar(client)
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "59170001111"}).json()
    c = next(iter(repo.comercios.values()))
    assert c["activo"] is False
    repo.confirmar_reset_code_comercio("59170001111", r["codigo"])
    assert c["activo"] is True and c["baja_motivo"] is None


def test_un_codigo_vencido_no_enciende(client, repo):
    _registrar(client)
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "59170001111"}).json()
    repo.get_comercio_usuario_por_whatsapp("59170001111")["reset_code_expira"] = (
        datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    assert repo.confirmar_reset_code_comercio("59170001111", r["codigo"]) is False
    assert next(iter(repo.comercios.values()))["activo"] is False


def test_confirmar_no_enciende_una_baja_del_admin(client, repo):
    c = repo.seed_comercio(slug="x", nombre="X", whatsapp="59170002222", activo=False)
    c["baja_motivo"] = "admin"
    assert repo.verificar_alta_de_comercio(c["id"]) is False and c["activo"] is False


def test_el_moderador_lo_ve_en_dados_de_baja_y_lo_reactiva(client, repo, admin_token):
    _registrar(client)
    c = next(iter(repo.comercios.values()))
    items = client.get("/admin/comercios/dados-de-baja", headers=_h(admin_token)).json()["items"]
    assert [(i["id"], i["baja_motivo"]) for i in items] == [(c["id"], "sin_verificar")]
    assert client.post(f"/admin/comercio/{c['id']}/reactivar", headers=_h(admin_token)).status_code == 200
    assert c["activo"] is True and c["baja_motivo"] is None


def test_aprobar_una_oferta_no_enciende_un_comercio_sin_verificar(client, repo, admin_token):
    data = _registrar(client)
    r = client.post("/comercio/publicar", headers=_h(data["access_token"]),
                    json={"tipo": "oferta", "titulo": "Remera", "precio": 80, "moneda": "BOB"})
    assert r.status_code == 200, r.text
    pub_id = r.json().get("publicacion_id") or r.json().get("id") or repo.publicaciones[-1]["id"]
    ap = client.post(f"/moderacion/publicaciones/{pub_id}", headers=_h(admin_token), json={"estado": "aprobado"})
    c = next(iter(repo.comercios.values()))
    assert ap.status_code == 200, ap.text
    assert c["activo"] is False and c["baja_motivo"] == "sin_verificar"


# ══════════════════════════════════════════ 5. M-11 archivos privados
def test_el_comprobante_va_al_disco_privado_y_no_a_fotos(client, repo, tmp_path):
    from app.services import archivos_privados

    c = repo.seed_comercio(slug="tienda", nombre="Tienda", whatsapp="59170003333", activo=True)
    tok = auth.make_comercio_token(c["id"], "x@y.com")
    r = client.post("/comercio/pago", headers=_h(tok), data={"monto": "50", "metodo": "transferencia"},
                    files={"comprobante": ("c.jpg", BytesIO(_jpg()), "image/jpeg")})
    assert r.status_code == 200, r.text
    ref = repo.pagos[r.json()["pago_id"]]["comprobante_url"]
    assert archivos_privados.es_referencia(ref) and ref.startswith("privado:comprobantes/")
    destino = archivos_privados.ruta_segura(ref)
    assert destino.is_file()
    assert Path(settings.fotos_dir).resolve() not in destino.resolve().parents      # nunca bajo /fotos
    assert not (Path(settings.fotos_dir) / "comprobantes").exists()


def test_el_comprobante_se_sirve_solo_con_permiso_pagos(client, repo, admin_token):
    c = repo.seed_comercio(slug="tienda", nombre="Tienda", whatsapp="59170003333", activo=True)
    tok = auth.make_comercio_token(c["id"], "x@y.com")
    pago_id = client.post("/comercio/pago", headers=_h(tok), data={"monto": "50"},
                          files={"comprobante": ("c.jpg", BytesIO(_jpg()), "image/jpeg")}).json()["pago_id"]
    url = f"/admin/pagos/{pago_id}/comprobante"
    assert client.get(url).status_code in (401, 403)                         # sin login
    assert client.get(url, headers=_h(tok)).status_code in (401, 403)        # un comercio no
    sin_permiso = auth.make_token("mod@x.bo", rol="moderador", roles=["moderador"], permisos=["moderar"])
    assert client.get(url, headers=_h(sin_permiso)).status_code == 403
    r = client.get(url, headers=_h(admin_token))
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "private, no-store"
    assert Image.open(BytesIO(r.content)).size == (20, 20)
    # el listado apunta al endpoint, no al archivo
    item = client.get("/admin/pagos/pendientes", headers=_h(admin_token)).json()["items"][0]
    assert item["comprobante_url"] == url
    assert client.get("/admin/pagos/no-existe/comprobante", headers=_h(admin_token)).status_code == 404


def test_un_comprobante_viejo_con_url_publica_no_se_sirve_por_el_endpoint(client, repo, admin_token):
    pago = repo.crear_pago_pendiente("c1", {"monto": 1, "comprobante_url": "https://api.x.bo/fotos/comprobantes/c1/a.jpg"})
    assert client.get(f"/admin/pagos/{pago['id']}/comprobante", headers=_h(admin_token)).status_code == 404
    item = client.get("/admin/pagos/pendientes", headers=_h(admin_token)).json()["items"][0]
    assert item["comprobante_url"].endswith("/fotos/comprobantes/c1/a.jpg")        # sigue como estaba hasta migrarlo


def test_la_foto_del_cambio_de_numero_es_privada(client, repo, admin_token):
    c = repo.seed_comercio(slug="casa", nombre="Casa", whatsapp="59170004444", activo=True)
    r = client.post(f"/comercio/{c['id']}/solicitar-cambio-numero",
                    data={"whatsapp_nuevo": "59170005555", "lat": "-22.7", "lng": "-64.3"},
                    files={"foto": ("f.jpg", BytesIO(_jpg()), "image/jpeg")})
    assert r.status_code == 200, r.text
    sol = next(iter(repo.solicitudes_numero.values()))
    assert sol["foto_url"].startswith("privado:cambio_numero/")
    url = f"/admin/solicitudes-cambio-numero/{sol['id']}/foto"
    assert client.get(url).status_code in (401, 403)
    moderador_sin_cuenta = auth.make_token("m@x.bo", rol="moderador", roles=["moderador"], permisos=["panel"])
    assert client.get(url, headers=_h(moderador_sin_cuenta)).status_code == 403          # pide comercios.cuenta
    assert client.get(url, headers=_h(admin_token)).status_code == 200
    item = client.get("/admin/solicitudes-cambio-numero", headers=_h(admin_token)).json()["items"][0]
    assert item["foto_url"] == url


def test_una_referencia_privada_adulterada_no_sale_del_directorio(tmp_path):
    from app.services import archivos_privados

    assert archivos_privados.ruta_segura("privado:../../etc/passwd") is None
    assert archivos_privados.ruta_segura("privado:") is None
    assert archivos_privados.ruta_segura("https://x.bo/fotos/a.jpg") is None
    assert archivos_privados.leer("privado:../x") is None


def test_el_directorio_privado_no_puede_quedar_bajo_fotos(monkeypatch, tmp_path):
    from app.services import archivos_privados

    monkeypatch.setattr(settings, "fotos_dir", str(tmp_path / "fotos"))
    monkeypatch.setattr(settings, "privados_dir", str(tmp_path / "fotos" / "privados"))
    assert archivos_privados.dir_seguro() is False
    assert archivos_privados.guardar("comprobantes", "c1", b"x") is None


def test_el_script_de_migracion_mueve_lo_publico_al_privado(monkeypatch, tmp_path):
    from app.scripts import mover_privados
    from app.services import archivos_privados

    fotos = tmp_path / "fotos"
    (fotos / "comprobantes" / "c1").mkdir(parents=True)
    (fotos / "comprobantes" / "c1" / "a.jpg").write_bytes(b"A")
    (fotos / "cambio-numero-casa").mkdir()
    (fotos / "cambio-numero-casa" / "b.jpg").write_bytes(b"B")
    monkeypatch.setattr(settings, "fotos_dir", str(fotos))
    monkeypatch.setattr(settings, "privados_dir", str(tmp_path / "privados"))

    assert mover_privados.subruta_publica("https://api.x.bo/fotos/comprobantes/c1/a.jpg?v=1") == "comprobantes/c1/a.jpg"
    assert mover_privados.subruta_publica("https://otro.bo/img.jpg") is None
    assert mover_privados.subruta_publica("https://api.x.bo/fotos/../../etc/passwd") is None

    class Tabla:
        def __init__(self, filas, col):
            self.filas, self.col, self._id, self._mod = filas, col, None, None

        def select(self, *_):
            return self

        @property
        def not_(self):
            return self

        def is_(self, *_):
            return self

        def update(self, patch):
            self._mod = patch
            return self

        def eq(self, _c, v):
            self._id = v
            return self

        def execute(self):
            if self._mod is not None:
                for f in self.filas:
                    if f["id"] == self._id:
                        f.update(self._mod)
                self._mod = None
                return type("R", (), {"data": []})()
            return type("R", (), {"data": [dict(f) for f in self.filas]})()

    pagos = [{"id": "p1", "comprobante_url": "https://api.x.bo/fotos/comprobantes/c1/a.jpg"},
             {"id": "p2", "comprobante_url": "privado:comprobantes/c1/ya.jpg"},
             {"id": "p3", "comprobante_url": "https://api.x.bo/fotos/comprobantes/c1/falta.jpg"}]
    sols = [{"id": "s1", "foto_url": "https://api.x.bo/fotos/cambio-numero-casa/b.jpg"}]

    class Db:
        def table(self, nombre):
            return Tabla(pagos if nombre == "pagos" else sols, None)

    seco = mover_privados.mover(Db(), dry_run=True)
    assert seco["pagos"]["movidas"] == 1 and pagos[0]["comprobante_url"].startswith("https")
    assert (fotos / "comprobantes" / "c1" / "a.jpg").exists()

    res = mover_privados.mover(Db())
    assert res["pagos"]["movidas"] == 1 and res["pagos"]["omitidas"] == [("p3", "el archivo ya no está en FOTOS_DIR")]
    assert res["solicitudes_cambio_numero"]["movidas"] == 1
    assert pagos[0]["comprobante_url"] == "privado:comprobantes/c1/a.jpg"
    assert sols[0]["foto_url"] == "privado:cambio_numero/cambio-numero-casa/b.jpg"
    assert archivos_privados.leer(pagos[0]["comprobante_url"]) == b"A"
    assert archivos_privados.leer(sols[0]["foto_url"]) == b"B"
    assert not (fotos / "comprobantes" / "c1" / "a.jpg").exists()      # el original público se borró
    assert mover_privados.mover(Db())["pagos"]["movidas"] == 0         # idempotente


# ══════════════════════════════════════════ 6. M-06 panel
def _alta_panel(client, admin_token, email="ana@uruku.bo", password="una-clave-larga-1", roles=("agente",)):
    return client.post("/admin/equipo", headers=_h(admin_token),
                       json={"email": email, "password": password, "roles": list(roles)})


def test_las_claves_nuevas_del_panel_piden_12_caracteres(client, repo, admin_token):
    assert _alta_panel(client, admin_token, password="corta123").status_code == 400
    assert _alta_panel(client, admin_token, password="a" * 11).status_code == 400
    assert _alta_panel(client, admin_token, password="a" * 12).status_code == 200
    uid = next(iter(repo.agentes))
    r = client.put(f"/admin/equipo/{uid}", headers=_h(admin_token),
                   json={"email": "ana@uruku.bo", "password": "cambiada", "roles": ["agente"]})
    assert r.status_code == 400 and "12" in r.json()["detail"]


def test_el_hash_nuevo_del_panel_es_de_600k_y_los_viejos_siguen_sirviendo():
    nuevo = auth.hash_password_panel("clave-del-panel-1")
    assert nuevo.startswith("pbkdf2_sha256$600000$") and auth.verify_password("clave-del-panel-1", nuevo)
    viejo = auth.hash_password("clave-vieja-1")
    assert viejo.startswith("pbkdf2_sha256$100000$") and auth.verify_password("clave-vieja-1", viejo)
    assert not auth.verify_password("otra", nuevo)
    assert auth.hash_panel_desactualizado(viejo) and not auth.hash_panel_desactualizado(nuevo)
    # el de Mi comercio y el del comprador no cambian (se verifican en cada ingreso)
    from app.core import clave_comercio
    assert clave_comercio.hash_clave("PREFIJO-ABCDEF").split("$")[-3] == "100000"


def test_entrar_con_un_hash_viejo_lo_pasa_a_600k(client, repo, admin_token):
    _alta_panel(client, admin_token)
    uid = next(iter(repo.agentes))
    repo.agentes[uid]["password_hash"] = auth.hash_password("una-clave-larga-1")           # como los de antes
    r = client.post("/auth/campo/login", json={"email": "ana@uruku.bo", "password": "una-clave-larga-1"})
    assert r.status_code == 200
    assert repo.agentes[uid]["password_hash"].startswith("pbkdf2_sha256$600000$")
    assert client.post("/auth/campo/login", json={"email": "ana@uruku.bo", "password": "una-clave-larga-1"}).status_code == 200


@pytest.mark.parametrize("puerta", ["/auth/login", "/auth/campo/login", "/auth/publicador/login"])
def test_cinco_fallos_bloquean_la_cuenta_del_panel_aunque_despues_venga_la_clave_buena(client, repo, admin_token, puerta):
    _alta_panel(client, admin_token, roles=("admin",))
    malo = {"email": "ana@uruku.bo", "password": "no-es-la-clave"}
    assert [client.post(puerta, json=malo).status_code for _ in range(5)] == [401] * 5
    bien = client.post(puerta, json={"email": "ana@uruku.bo", "password": "una-clave-larga-1"})
    assert bien.status_code == 429 and "15 minutos" in bien.json()["detail"]
    # otra cuenta no queda bloqueada
    _alta_panel(client, admin_token, email="beto@uruku.bo", roles=("admin",))
    assert client.post(puerta, json={"email": "beto@uruku.bo", "password": "una-clave-larga-1"}).status_code == 200


def test_el_bloqueo_tambien_cubre_la_llave_del_env_y_correos_que_no_existen(client, repo):
    for _ in range(5):
        client.post("/auth/login", json={"email": settings.admin_email, "password": "mal"})
    assert client.post("/auth/login", json={"email": settings.admin_email,
                                            "password": settings.admin_password}).status_code == 429
    for _ in range(5):
        client.post("/auth/login", json={"email": "nadie@x.bo", "password": "mal"})
    assert client.post("/auth/login", json={"email": "nadie@x.bo", "password": "mal"}).status_code == 429


def test_un_ingreso_correcto_no_borra_los_fallos_pero_pasados_15_minutos_se_libera(client, repo, admin_token):
    _alta_panel(client, admin_token, roles=("admin",))
    for _ in range(4):
        client.post("/auth/login", json={"email": "ana@uruku.bo", "password": "mal"})
    assert client.post("/auth/login", json={"email": "ana@uruku.bo", "password": "una-clave-larga-1"}).status_code == 200
    client.post("/auth/login", json={"email": "ana@uruku.bo", "password": "mal"})          # el quinto fallo
    assert client.post("/auth/login", json={"email": "ana@uruku.bo", "password": "una-clave-larga-1"}).status_code == 429
    for f in repo.clave_fallos:
        f["created_at"] -= timedelta(minutes=16)
    assert client.post("/auth/login", json={"email": "ana@uruku.bo", "password": "una-clave-larga-1"}).status_code == 200


def test_la_cuenta_del_panel_se_identifica_por_un_hash_del_correo_no_por_el_correo(client, repo):
    client.post("/auth/login", json={"email": "Nadie@X.bo", "password": "mal"})
    fila = repo.clave_fallos[-1]
    assert fila["tabla"] == "usuarios_panel" and "nadie" not in fila["numero"].lower()
    assert fila["numero"] == hashlib.sha256(b"nadie@x.bo").hexdigest()[:32]


# ══════════════════════════════════════════ 7. bajas
def test_b02_la_imagen_de_una_publicacion_tiene_que_ser_nuestra(client, repo):
    c = repo.seed_comercio(slug="t", nombre="T", whatsapp="59170006666", activo=True)
    h = _h(auth.make_comercio_token(c["id"], "x@y.com"))
    propia = settings.public_photo_url("t/ofertas/abc.jpg")
    base = {"tipo": "oferta", "titulo": "Remera", "precio": 80}
    ok = client.post("/comercio/publicar", headers=h, json={**base, "imagen_url": propia})
    assert ok.status_code == 200, ok.text
    for malo in ("https://rastreo.evil.com/pixel.gif", "javascript:alert(1)", "http://localhost:9999/x.jpg",
                 propia.replace("/fotos/", "/fotos/../").replace("..//", "../")):
        r = client.post("/comercio/publicar", headers=h, json={**base, "imagen_url": malo})
        assert r.status_code == 422, (malo, r.text)
    # sin imagen también vale
    assert client.post("/comercio/publicar", headers=h, json=base).status_code == 200


def test_b02_el_enlace_de_tiktok_pasa_por_enlaces_py(client, repo):
    c = repo.seed_comercio(slug="t", nombre="T", whatsapp="59170006666", activo=True)
    h = _h(auth.make_comercio_token(c["id"], "x@y.com"))
    base = {"tipo": "video", "titulo": "Video"}
    assert client.post("/comercio/publicar", headers=h,
                       json={**base, "tiktok_url": "javascript:alert(1)"}).status_code == 422
    assert client.post("/comercio/publicar", headers=h,
                       json={**base, "tiktok_url": "https://uruku.bo@evil.com/x"}).status_code == 422
    assert client.post("/comercio/publicar", headers=h,
                       json={**base, "tiktok_url": "https://www.tiktok.com/@t/video/1"}).status_code == 200
    pub = repo.publicaciones[-1]["id"]
    assert client.patch(f"/comercio/publicaciones/{pub}", headers=h,
                        json={"imagen_url": "https://rastreo.evil.com/p.gif"}).status_code == 422
    assert client.patch(f"/comercio/publicaciones/{pub}", headers=h,
                        json={"tiktok_url": "data:text/html,x"}).status_code == 422


def test_b05_nada_se_borra_fisicamente(client, repo, admin_token):
    # producto de la tienda: archivado, ya no sale ni se puede volver a borrar
    ref = repo.crear_producto_ref({"comercio_id": C1, "titulo": "P"})
    repo.delete_producto_ref(ref["id"])
    assert repo.producto_refs[ref["id"]]["estado"] == "archivado"
    assert repo.list_producto_refs("c1") == [] and repo.get_producto_ref(ref["id"]) is None
    # saber de URUKU: pasa a inactivo
    saber = repo.upsert_saber_local({"pregunta": "¿Hora?", "respuesta": "x"})
    assert client.delete(f"/admin/asistente/saber/{saber['id']}", headers=_h(admin_token)).status_code == 200
    assert repo.saber_local[saber["id"]]["activo"] is False
    # video promocional: activo = false, sale de la lista
    video = repo.add_video_promo({"titulo": "v", "url": "u"})
    pub = auth.make_publicador_token("p@x.bo")
    assert client.delete(f"/contenido/videos-promo/{video['id']}", headers=_h(pub)).status_code == 200
    assert repo.videos_promo[0]["activo"] is False
    assert client.get("/contenido/videos-promo", headers=_h(pub)).json()["items"] == []
    assert client.delete(f"/contenido/videos-promo/{video['id']}", headers=_h(pub)).status_code == 404


def test_b05_el_repo_real_no_hace_delete_de_esas_tres_tablas():
    codigo = (APP / "db" / "repository.py").read_text(encoding="utf-8")
    for tabla in ("producto_ref", "saber_local", "videos_promocionales"):
        assert not re.search(rf'table\("{tabla}"\)\.delete\(\)', codigo), tabla


def test_b12_la_descarga_de_waha_es_en_stream_con_tope_y_sin_redirecciones(monkeypatch):
    from app.services import wa_media

    monkeypatch.setattr(settings, "waha_base_url", "http://waha:3000")
    monkeypatch.setattr(settings, "waha_api_key", "CLAVE")
    pedidos = []

    def servidor(request: httpx.Request) -> httpx.Response:
        pedidos.append(request)
        ruta = request.url.path
        if ruta == "/api/files/ok.jpg":
            return httpx.Response(200, content=b"x" * 1000)
        if ruta == "/api/files/redirige.jpg":
            return httpx.Response(302, headers={"location": "http://evil.example/robar"})
        if ruta == "/api/files/enorme.jpg":
            return httpx.Response(200, content=b"x" * (wa_media._MAX_BYTES + 1))
        if ruta == "/api/files/declarado.jpg":
            return httpx.Response(200, headers={"content-length": str(wa_media._MAX_BYTES + 5)}, content=b"x")
        if ruta == "/api/files/roto.jpg":
            return httpx.Response(404)
        return httpx.Response(500)

    monkeypatch.setattr(wa_media, "_cliente",
                        lambda: httpx.Client(transport=httpx.MockTransport(servidor), follow_redirects=False))
    assert wa_media.descargar_media("http://waha:3000/api/files/ok.jpg") == b"x" * 1000
    assert pedidos[0].headers["x-api-key"] == "CLAVE"
    assert wa_media.descargar_media("http://waha:3000/api/files/redirige.jpg") is None
    assert all("evil.example" not in str(p.url) for p in pedidos)          # nunca siguió la redirección
    assert wa_media.descargar_media("http://waha:3000/api/files/enorme.jpg") is None
    assert wa_media.descargar_media("http://waha:3000/api/files/declarado.jpg") is None
    assert wa_media.descargar_media("http://waha:3000/api/files/roto.jpg") is None


def test_b12_el_cliente_real_no_sigue_redirecciones():
    from app.services import wa_media

    assert wa_media._cliente().follow_redirects is False


@pytest.mark.skipif(not shutil.which("ffmpeg") or not shutil.which("ffprobe"), reason="sin ffmpeg")
def test_b13_el_video_sale_sin_metadatos_ni_gps(tmp_path):
    from app.services import imagenes

    origen = tmp_path / "con_gps.mp4"
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=5:duration=1",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-metadata", "location=+22.7361-064.3433/", "-metadata", "title=Mi casa",
                    "-metadata", "com.apple.quicktime.model=iPhone", str(origen)], check=True, capture_output=True)

    def etiquetas(ruta):
        out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format_tags", "-of", "json", str(ruta)],
                             check=True, capture_output=True, text=True).stdout
        return json.loads(out).get("format", {}).get("tags", {})

    assert "location" in etiquetas(origen)                             # el original SÍ la lleva
    limpio = imagenes._limpiar_con_ffmpeg(origen.read_bytes(), "mp4")  # (conftest reemplaza sin_metadatos_video)
    assert limpio
    destino = tmp_path / "limpio.mp4"
    destino.write_bytes(limpio)
    tags = {k.lower(): v for k, v in etiquetas(destino).items()}
    assert "location" not in tags and "title" not in tags and "com.apple.quicktime.model" not in tags


def test_b13_si_ffmpeg_falla_no_se_guarda_el_original(monkeypatch):
    from app.services import imagenes
    monkeypatch.setattr(imagenes, "sin_metadatos_video", imagenes._limpiar_con_ffmpeg)   # sin el reemplazo de conftest
    monkeypatch.setattr(shutil, "which", lambda _n: None)
    assert imagenes.sin_metadatos_video(b"video", "mp4") is None
    assert imagenes.subir_video_comercio("slug", b"video", "video/mp4") is None

    monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 1, stdout=b"", stderr=b"boom"))
    assert imagenes.sin_metadatos_video(b"video", "mp4") is None

    def con_timeout(*a, **k):
        raise subprocess.TimeoutExpired(a, 1)
    monkeypatch.setattr(subprocess, "run", con_timeout)
    assert imagenes.sin_metadatos_video(b"video", "mp4") is None


def test_b13_el_comando_es_el_pedido(monkeypatch):
    from app.services import imagenes
    monkeypatch.setattr(imagenes, "sin_metadatos_video", imagenes._limpiar_con_ffmpeg)
    visto = {}

    def falso(cmd, **k):
        visto["cmd"] = cmd
        Path(cmd[-1]).write_bytes(b"LIMPIO")
        return subprocess.CompletedProcess(cmd, 0, stdout=b"", stderr=b"")

    monkeypatch.setattr(shutil, "which", lambda _n: "/usr/bin/ffmpeg")
    monkeypatch.setattr(subprocess, "run", falso)
    assert imagenes.sin_metadatos_video(b"video", "mov") == b"LIMPIO"
    cmd = visto["cmd"]
    assert cmd[cmd.index("-map_metadata") + 1] == "-1"
    assert cmd[cmd.index("-c") + 1] == "copy"


def test_b13_una_subida_sin_ffmpeg_da_502_y_no_deja_fila(client, repo, monkeypatch, admin_token):
    from app.services import imagenes

    monkeypatch.setattr(imagenes, "sin_metadatos_video", lambda d, e: None)
    pub = auth.make_publicador_token("p@x.bo")
    r = client.post("/contenido/videos-promo", headers=_h(pub),
                    files={"video": ("v.mp4", BytesIO(b"x" * 100), "video/mp4")})
    assert r.status_code == 502 and repo.videos_promo == []


def _sql(nombre):
    return (MIGRACIONES / nombre).read_text(encoding="utf-8")


def test_b06_la_migracion_0187_cierra_lo_pedido_y_tiene_comprobacion():
    sql = _sql("0187_cierre_semana_seguridad.sql")
    assert "'usuarios_panel'" in sql and "respondio_por" in sql and "'sin_verificar'" in sql
    # galería: RLS por comercio activo (no más `using (true)`), lugares con RLS
    assert re.search(r"create policy comercio_fotos_public_read.*?c\.activo", sql, re.S)
    assert re.search(r"create policy comercio_videos_public_read.*?c\.activo", sql, re.S)
    assert "alter table public.lugares enable row level security" in sql
    assert re.search(r"create policy lugares_public_read on public\.lugares\s+for select to anon, authenticated using \(activo\)", sql)
    sin_comentarios = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))
    assert "using (true)" not in sin_comentarios
    # comprobación dentro de la misma transacción, y probada con el rol anon
    assert sql.index("begin;") < sql.index("do $chk$") < sql.index("commit;")
    assert sql.count("set local role anon;") >= 3 and "raise exception" in sql
    # la columna nueva de comercios NO se le da a anon (regla 11)
    assert not re.search(r"grant select \([^)]*baja_motivo", sql)
    assert not re.search(r"grant[^;]*respondio_por[^;]*to anon", sql)


def test_b06_la_0187_es_identica_en_las_dos_carpetas():
    selfhost = Path(__file__).resolve().parents[2] / "selfhost" / "postgres-init" / "0187_cierre_semana_seguridad.sql"
    assert selfhost.read_bytes() == (MIGRACIONES / "0187_cierre_semana_seguridad.sql").read_bytes()
