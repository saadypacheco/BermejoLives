"""Revisión de seguridad del commit 01b5674 (clave automática): lo que se corrigió.

Qué se prueba, por punto de la revisión:
  1. (ALTO) Los códigos URUKU-XXXX se regeneran (0149) y las publicaciones que entraron con el
     código viejo se pueden aprobar igual; el código viejo ya no identifica a nadie.
  2. (MEDIO) Las sesiones de Mi comercio mueren cuando la clave cambia (`credenciales_version`).
  3. (MEDIO) Pepper: `HMAC-SHA256(CLAVE_PEPPER, clave)` antes de PBKDF2, con formato propio,
     convive con los hashes viejos y se rehashea al primer ingreso correcto.
  4. (MEDIO) Una clave mandada por WhatsApp no se publica ni se guarda: se anula.
  5. (MEDIO) «Generar clave» del admin deja auditoría y valida UUID y `activo`.
  6. (BAJOS) Tiempo parejo en el login, anulación por 10 fallos sólo para la clave de 6 números,
     prefijos que empiezan con URUKU, tracebacks sin variables locales, alta idempotente.
La migración 0149 se prueba además en test_publicaciones_columnas_publicas.py (permisos) y acá
(códigos, versión de credenciales, auditoría, alta_uid) contra un Postgres real si hay Docker.
"""
import json
import re
import sys
import uuid
from io import BytesIO
from pathlib import Path

import pytest
import structlog
from fastapi.testclient import TestClient
from PIL import Image

from app.core import auth, clave as claves, clave_comercio
from app.core.codigo import extraer_codigo, sin_codigo
from app.core.config import settings
from app.db.repository import get_repo
from app.main import app
from app.services import clave_filtrada, ingest, ingreso_clave
from tests.pg_0149 import RAIZ, leer_0149, pg0149, sin_comentarios_sql  # noqa: F401

FORMATO = re.compile(r"^[A-Z0-9]{1,8}-[2-9A-HJKMNP-Z]{6}$")
ID_COMERCIO = "5f0c1b7e-3a2d-4c8e-9b1f-0a6d2e4c7b91"
CLAVE = "BOUTIQUE-K7M2P9"
MSG_SESION = "Tu sesión se cerró porque cambió la clave"


# ═════════════════════════════════════════════════════════ helpers
def _hdr(token):
    return {"Authorization": f"Bearer {token}"}


def _foto():
    buf = BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="JPEG")
    buf.seek(0)
    return {"foto": ("test.jpg", buf, "image/jpeg")}


def _ingresar(client, whatsapp, clave):
    return client.post("/auth/comercio/ingresar", json={"whatsapp": whatsapp, "clave": clave})


def _comercio(repo, con_clave=CLAVE, version=1, **kw):
    """Un comercio activo con cuenta. Con `con_clave`, la cuenta ya tiene esa clave (versión 1:
    toda clave que se genera desde la 0149 sube la versión)."""
    c = repo.seed_comercio(activo=True, **{"id": ID_COMERCIO, "slug": "boutique", "nombre": "Boutique Lucía",
                                          "whatsapp": "59170123456", "codigo": "K7M2", **kw})
    cuenta = repo.crear_comercio_usuario({"comercio_id": c["id"], "nombre": c["nombre"]})
    if con_clave:
        cuenta["clave_hash"] = clave_comercio.hash_clave(con_clave)
        cuenta["credenciales_version"] = version
    return c, cuenta


def _token_de(cuenta, email="x@y.com"):
    """El token que se emitió al entrar con las credenciales de AHORA."""
    return auth.make_comercio_token(cuenta["comercio_id"], email, cuenta["id"], cuenta.get("credenciales_version"))


def _login(client, clave=CLAVE, numero="70123456"):
    r = _ingresar(client, numero, clave)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _msg(phone, body, wamid="wa-1", grupo=None):
    payload = {"id": wamid, "fromMe": False, "body": body, "type": "text", "timestamp": 1700000000,
               "_data": {"body": body, "key": {"remoteJid": f"{phone}@c.us"}}}
    if grupo:
        payload.update({"from": grupo})
        payload["_data"]["key"] = {"remoteJid": grupo, "participant": f"{phone}@c.us"}
    else:
        payload["from"] = f"{phone}@c.us"
    return {"event": "message", "session": "obs@c.us", "payload": payload}


# ═════════════════════════════════════════════════════════ 2. sesiones que mueren con la clave
def test_el_token_del_ingreso_lleva_cuenta_y_version(client, repo):
    c, cuenta = _comercio(repo)
    claims = auth._decode(_login(client))
    assert claims["cuenta_id"] == cuenta["id"] and claims["ver"] == 1 and claims["comercio_id"] == c["id"]


def test_el_admin_que_genera_una_clave_cierra_la_sesion_abierta(client, repo, admin_token):
    c, cuenta = _comercio(repo)
    viejo = _login(client)
    assert client.get("/comercio/perfil", headers=_hdr(viejo)).status_code == 200
    assert client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(admin_token)).status_code == 200
    for metodo, ruta in (("get", "/comercio/perfil"), ("get", "/comercio/mis-publicaciones"),
                         ("get", "/comercio/fotos"), ("get", "/comercio/asistente/preguntas")):
        r = getattr(client, metodo)(ruta, headers=_hdr(viejo))
        assert r.status_code == 401, (ruta, r.status_code)
        assert r.json()["detail"] == MSG_SESION
    # Y las escrituras (con `_comercio_escribe`) también.
    r = client.put("/comercio/perfil", headers=_hdr(viejo), json={"descripcion": "hackeada"})
    assert r.status_code == 401 and r.json()["detail"] == MSG_SESION
    assert c.get("descripcion") != "hackeada"
    # Entrando de nuevo con la clave nueva, vuelve a andar.
    nueva = client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(admin_token)).json()["clave"]
    assert client.get("/comercio/perfil", headers=_hdr(_login(client, nueva))).status_code == 200


def test_pedir_una_clave_nueva_cierra_las_demas_sesiones_y_devuelve_un_token_vigente(client, repo):
    _c, cuenta = _comercio(repo)
    en_el_celular = _login(client)
    en_la_pc = _login(client)
    r = client.post("/comercio/clave", headers=_hdr(en_el_celular))
    assert r.status_code == 200 and FORMATO.match(r.json()["clave"])
    assert r.headers["cache-control"] == "no-store"
    token = r.json()["access_token"]
    assert client.get("/comercio/perfil", headers=_hdr(token)).status_code == 200      # quien la pidió sigue adentro
    for viejo in (en_el_celular, en_la_pc):
        r = client.get("/comercio/perfil", headers=_hdr(viejo))
        assert r.status_code == 401 and r.json()["detail"] == MSG_SESION
    assert auth._decode(token)["ver"] == cuenta["credenciales_version"] == 2


def test_recuperar_por_whatsapp_cierra_las_sesiones_viejas_y_el_token_nuevo_sirve(client, repo):
    _c, cuenta = _comercio(repo)
    viejo = _login(client)
    codigo = client.post("/auth/comercio/recuperar", json={"whatsapp": "70123456"}).json()["codigo"]
    ingest.handle_message(_msg("59170123456", f"CONFIRMAR-{codigo}", "wa-conf"), repo)
    r = client.post("/auth/comercio/recuperar/confirmar", json={"whatsapp": "70123456", "codigo": codigo})
    assert r.status_code == 200, r.text
    nuevo = r.json()["access_token"]
    assert client.get("/comercio/perfil", headers=_hdr(nuevo)).status_code == 200
    r = client.get("/comercio/perfil", headers=_hdr(viejo))
    assert r.status_code == 401 and r.json()["detail"] == MSG_SESION


def test_la_clave_anulada_por_fallos_cierra_la_sesion(client, repo):
    from datetime import timedelta

    _c, cuenta = _comercio(repo, con_clave="123456", version=0)           # clave vieja de 6 números
    viejo = _login(client, "123456")
    for tanda in range(2):
        for _ in range(4):
            assert _ingresar(client, "70123456", "654321").status_code == 401
        for f in repo.clave_fallos:
            f["created_at"] -= timedelta(minutes=16)
    assert _ingresar(client, "70123456", "654321").status_code == 401
    r = _ingresar(client, "70123456", "654321")
    assert r.status_code == 401 and r.json()["detail"] == claves.MENSAJE_ANULADA
    assert cuenta["clave_hash"] is None and cuenta["credenciales_version"] == 1
    r = client.get("/comercio/perfil", headers=_hdr(viejo))
    assert r.status_code == 401 and r.json()["detail"] == MSG_SESION


def test_cambiar_el_whatsapp_del_comercio_cierra_la_sesion(client, repo):
    c, cuenta = _comercio(repo)
    viejo = _login(client)
    repo.anular_claves_de_comercio(c["id"])                  # lo que hace el admin al cambiar el número
    assert client.get("/comercio/perfil", headers=_hdr(viejo)).status_code == 401


def test_un_token_sin_version_vale_como_version_0_hasta_que_la_clave_cambie(client, repo):
    c, cuenta = _comercio(repo, con_clave="123456", version=0)
    sin_ver = auth.make_comercio_token(c["id"], "x@y.com")                          # de antes de la 0149
    con_cuenta_sin_ver = auth.make_comercio_token(c["id"], "x@y.com", cuenta["id"])
    assert "ver" not in auth._decode(sin_ver) and "cuenta_id" not in auth._decode(sin_ver)
    assert auth._decode(con_cuenta_sin_ver)["ver"] == 0
    for t in (sin_ver, con_cuenta_sin_ver):
        assert client.get("/comercio/perfil", headers=_hdr(t)).status_code == 200   # versión 0 = 0
    cuenta["credenciales_version"] = 1                                              # la clave cambió
    for t in (sin_ver, con_cuenta_sin_ver):
        r = client.get("/comercio/perfil", headers=_hdr(t))
        assert r.status_code == 401 and r.json()["detail"] == MSG_SESION


def test_un_token_de_otra_cuenta_o_de_otro_comercio_no_se_confunde(client, repo):
    c, cuenta = _comercio(repo)
    otro = repo.seed_comercio(id="otro", slug="otro", nombre="Otro", whatsapp="59171112222", activo=True)
    otra_cuenta = repo.crear_comercio_usuario({"comercio_id": otro["id"], "nombre": "Otro"})
    otra_cuenta["credenciales_version"] = 7
    assert client.get("/comercio/perfil", headers=_hdr(_token_de(cuenta))).status_code == 200
    assert client.get("/comercio/perfil", headers=_hdr(_token_de(otra_cuenta))).status_code == 200
    # Un `ver` más alto que el de la cuenta (no debería existir) tampoco la cierra.
    futuro = auth.make_comercio_token(c["id"], "x@y.com", cuenta["id"], 99)
    assert client.get("/comercio/perfil", headers=_hdr(futuro)).status_code == 200


def test_el_rehash_con_pepper_no_cierra_la_sesion(client, repo, monkeypatch):
    _c, cuenta = _comercio(repo)
    viejo = _login(client)
    monkeypatch.setattr(settings, "clave_pepper", "pepper-de-prueba")
    _login(client)                                                    # rehashea
    assert cuenta["clave_hash"].startswith("p1$") and cuenta["credenciales_version"] == 1
    assert client.get("/comercio/perfil", headers=_hdr(viejo)).status_code == 200


def test_las_rutas_de_mi_comercio_usan_todas_la_sesion_vigente():
    """Ningún endpoint de /comercio/* ni del asistente de Mi comercio acepta el token sin mirar la versión."""
    for archivo in ("comercio.py", "asistente.py"):
        texto = (RAIZ / "backend/app/api" / archivo).read_text(encoding="utf-8")
        assert "Depends(auth.require_comercio)" not in texto, archivo
    # `require_comercio_vigente` es lo único que usa `require_comercio` por dentro.
    sesion = (RAIZ / "backend/app/core/sesion_comercio.py").read_text(encoding="utf-8")
    assert "Depends(auth.require_comercio)" in sesion


# ═════════════════════════════════════════════════════════ 3. pepper
def test_sin_pepper_el_hash_es_el_de_siempre():
    assert settings.clave_pepper == ""
    h = clave_comercio.hash_clave(CLAVE)
    assert h.startswith("pbkdf2_sha256$") and not h.startswith("p1$")
    assert auth.verify_password(clave_comercio.normalizar(CLAVE), h)
    assert clave_comercio.necesita_rehash(h) is False


def test_con_pepper_el_hash_lleva_su_marca_y_la_clave_sola_no_alcanza(monkeypatch):
    monkeypatch.setattr(settings, "clave_pepper", "pepper-de-prueba")
    h = clave_comercio.hash_clave("boutique k7m2p9")
    assert h.startswith("p1$pbkdf2_sha256$") and CLAVE.replace("-", "").lower() not in h.lower()
    assert clave_comercio.clave_coincide(CLAVE, h) is True
    assert clave_comercio.clave_coincide("boutique-k7m2p9", h) is True
    assert clave_comercio.clave_coincide("BOUTIQUE-K7M2P8", h) is False
    # Sin el pepper, PBKDF2 de la clave pelada NO verifica: la base sola no permite probar claves.
    assert auth.verify_password(clave_comercio.normalizar(CLAVE), h[len("p1$"):]) is False
    # El que entra a PBKDF2 es el HMAC.
    esperado = clave_comercio._con_pepper(clave_comercio.normalizar(CLAVE))
    assert re.fullmatch(r"[0-9a-f]{64}", esperado)
    assert auth.verify_password(esperado, h[len("p1$"):]) is True
    # Con otro pepper (o sin pepper) no coincide.
    monkeypatch.setattr(settings, "clave_pepper", "otro-pepper")
    assert clave_comercio.clave_coincide(CLAVE, h) is False
    monkeypatch.setattr(settings, "clave_pepper", "")
    assert clave_comercio.clave_coincide(CLAVE, h) is False


def test_con_pepper_siguen_entrando_los_hashes_viejos_y_piden_rehash(monkeypatch):
    viejo = auth.hash_password(clave_comercio.normalizar(CLAVE))
    sixes = auth.hash_password("004217")
    monkeypatch.setattr(settings, "clave_pepper", "pepper-de-prueba")
    assert clave_comercio.clave_coincide(CLAVE, viejo) and clave_comercio.clave_coincide("004217", sixes)
    assert clave_comercio.necesita_rehash(viejo) and clave_comercio.necesita_rehash(sixes)
    assert not clave_comercio.necesita_rehash(clave_comercio.hash_clave(CLAVE))
    assert not clave_comercio.necesita_rehash(None)


def test_lo_que_no_tiene_forma_de_clave_no_gasta_pbkdf2_ni_con_pepper(monkeypatch):
    monkeypatch.setattr(settings, "clave_pepper", "pepper-de-prueba")
    h = clave_comercio.hash_clave(CLAVE)
    gastos = []
    monkeypatch.setattr(auth, "verify_password", lambda *a: gastos.append(a) or False)
    for basura in (None, "", "12345", "A" * 25, "boutique!k7m2p9"):
        assert clave_comercio.clave_coincide(basura, h) is False
    assert gastos == []


def test_el_login_rehashea_la_clave_vieja_al_primer_ingreso_correcto(client, repo, monkeypatch):
    c, cuenta = _comercio(repo, con_clave=None)
    cuenta["clave_hash"] = auth.hash_password(clave_comercio.normalizar(CLAVE))          # sin pepper
    cuenta["credenciales_version"] = 1
    monkeypatch.setattr(settings, "clave_pepper", "pepper-de-prueba")
    assert _ingresar(client, "70123456", "BOUTIQUE-K7M2P8").status_code == 401
    assert not cuenta["clave_hash"].startswith("p1$")                                     # un fallo no rehashea
    assert _ingresar(client, "70123456", CLAVE.lower()).status_code == 200
    assert cuenta["clave_hash"].startswith("p1$")
    assert cuenta["credenciales_version"] == 1                                            # la misma clave: misma versión
    hash_con_pepper = cuenta["clave_hash"]
    assert _ingresar(client, "70123456", CLAVE).status_code == 200
    assert cuenta["clave_hash"] == hash_con_pepper                                        # ya está: no se rehashea más


def test_una_clave_nueva_con_pepper_se_guarda_con_pepper(client, repo, monkeypatch):
    c, cuenta = _comercio(repo, con_clave=None)
    monkeypatch.setattr(settings, "clave_pepper", "pepper-de-prueba")
    nueva = client.post("/comercio/clave", headers=_hdr(_token_de(cuenta))).json()["clave"]
    assert cuenta["clave_hash"].startswith("p1$")
    assert _ingresar(client, "70123456", nueva.lower()).status_code == 200


def test_la_clave_distinta_de_la_de_otro_comercio_entiende_los_dos_formatos(monkeypatch):
    ajena_vieja = clave_comercio.hash_clave("PUESTO-K7M2P9")
    monkeypatch.setattr(settings, "clave_pepper", "pepper-de-prueba")
    ajena_nueva = clave_comercio.hash_clave("PUESTO-AAAAAA")
    salidas = iter(["K7M2P9", "AAAAAA", "ZZZZZZ"])
    monkeypatch.setattr(clave_comercio, "generar_azar", lambda: next(salidas))
    assert clave_comercio.clave_distinta_de([ajena_vieja, ajena_nueva], "PUESTO") == "PUESTO-ZZZZZZ"


def test_el_arranque_avisa_si_falta_el_pepper(monkeypatch):
    from structlog.testing import capture_logs

    with capture_logs() as logs:
        with TestClient(app):
            pass
    assert any(l["event"] == "config.clave_pepper_vacio" and l["log_level"] == "warning" for l in logs)
    monkeypatch.setattr(settings, "clave_pepper", "pepper-de-prueba")
    with capture_logs() as logs:
        with TestClient(app):
            pass
    assert not any(l["event"] == "config.clave_pepper_vacio" for l in logs)


def test_el_pepper_esta_en_la_config_en_el_env_de_ejemplo_y_en_los_generadores(capsys, monkeypatch):
    monkeypatch.setattr(sys, "argv", ["generar_secretos.py"])
    assert "clave_pepper" in type(settings).model_fields
    assert re.search(r"^CLAVE_PEPPER=$", (RAIZ / "backend/.env.example").read_text(encoding="utf-8"), re.M)
    assert "CLAVE_PEPPER=" in (RAIZ / "backend/.env.prod.example").read_text(encoding="utf-8")
    assert 'f"CLAVE_PEPPER={clave_pepper}' in (RAIZ / "selfhost/init_prod_env.py").read_text(encoding="utf-8")
    # `generar_secretos.py` imprime un CLAVE_PEPPER distinto en cada corrida, en la sección del backend.
    sys.path.insert(0, str(RAIZ / "selfhost"))
    try:
        import generar_secretos
        salidas = []
        for _ in range(2):
            generar_secretos.main()
            salidas.append(capsys.readouterr().out)
    finally:
        sys.path.remove(str(RAIZ / "selfhost"))
    peppers = [re.search(r"^CLAVE_PEPPER=(\S{40,})$", s, re.M).group(1) for s in salidas]
    assert peppers[0] != peppers[1]
    for s in salidas:
        assert s.index("backend/.env") < s.index("CLAVE_PEPPER=")


# ═════════════════════════════════════════════════════════ 4. la clave mandada por WhatsApp
def test_extraer_codigo_no_toma_un_tramo_de_una_clave():
    assert extraer_codigo("MESA-K7M2P9") is None                  # «MESA» es un código pelado válido: es el prefijo
    assert extraer_codigo("hola, mi clave es mesa k7m2p9 gracias") is None
    assert extraer_codigo("ROPA-ABCDEF") is None
    assert extraer_codigo("K7M2") == "K7M2"                        # el pelado de siempre sigue andando
    assert extraer_codigo("oferta K7M2 zapatillas 200") == "K7M2"
    assert extraer_codigo("URUKU-K7M2 MESA-K7M2P9") == "K7M2"      # con prefijo gana
    assert extraer_codigo("MESA-K7M2P9 y mi código K7M2") == "K7M2"
    assert extraer_codigo(None) is None


def test_una_clave_en_un_mensaje_no_identifica_un_comercio_por_el_prefijo(repo):
    repo.seed_comercio(slug="mesas", nombre="Mesas", codigo="MESA", activo=True)
    antes = len(repo.publicaciones)
    r = ingest.handle_message(_msg("59177777777", "MESA-K7M2P9 hola"), repo)
    assert r.get("publicada") is False and len(repo.publicaciones) == antes


@pytest.mark.parametrize("texto", [
    CLAVE, "boutique-k7m2p9", "boutique k7m2p9", "  Boutique - K7M2P9 ",
    "hola, mi clave es BOUTIQUE-K7M2P9 gracias", "precio 250 Bs BOUTIQUE_K7M2P9",
])
def test_la_clave_mandada_por_whatsapp_no_se_publica_se_guarda_tapada_y_se_anula(repo, texto):
    c, cuenta = _comercio(repo, confiable=True)
    r = ingest.handle_message(_msg("59170123456", texto, "wa-clave"), repo)
    assert r["captured"] is True and r["publicada"] is False and r["clave_anulada"] is True
    assert r["motivo"] == "El comerciante mandó su clave por WhatsApp: se anuló"
    assert repo.publicaciones == []                                # NO se publica
    # La bandeja: sin la clave, ni en el texto ni en el crudo; con el motivo para el admin.
    fila = repo.wa_inbox["wa-clave"]
    assert "K7M2P9" not in json.dumps(fila, ensure_ascii=False).upper().replace("-", "").replace(" ", "").replace("_", "")
    assert "[clave]" in fila["body"] and "[clave]" in fila["raw"]["body"] and "[clave]" in fila["raw"]["_data"]["body"]
    assert fila["resultado"] == "sin_permiso" and fila["comercio_id"] == c["id"]
    assert fila["motivo"] == "El comerciante mandó su clave por WhatsApp: se anuló"
    # La clave quedó anulada: no entra con ella y las sesiones abiertas se cierran.
    assert cuenta["clave_hash"] is None and cuenta["credenciales_version"] == 2
    assert _ingresar_sin_cliente(repo, CLAVE) is False
    # Auditoría.
    assert repo.comercio_eventos == [{"comercio_id": c["id"], "tipo": "clave_anulada_por_whatsapp", "actor": "sistema"}]


def _ingresar_sin_cliente(repo, clave):
    return any(clave_comercio.clave_coincide(clave, u.get("clave_hash")) for u in repo.usuarios.values())


def test_la_sesion_abierta_se_cierra_cuando_la_clave_se_manda_por_whatsapp(client, repo):
    _c, cuenta = _comercio(repo)
    viejo = _login(client)
    ingest.handle_message(_msg("59170123456", CLAVE), repo)
    r = client.get("/comercio/perfil", headers=_hdr(viejo))
    assert r.status_code == 401 and r.json()["detail"] == MSG_SESION
    assert _ingresar(client, "70123456", CLAVE).status_code == 401
    # Recupera por WhatsApp y vuelve a entrar.
    codigo = client.post("/auth/comercio/recuperar", json={"whatsapp": "70123456"}).json()["codigo"]
    ingest.handle_message(_msg("59170123456", f"CONFIRMAR-{codigo}", "wa-conf"), repo)
    nueva = client.post("/auth/comercio/recuperar/confirmar", json={"whatsapp": "70123456", "codigo": codigo}).json()["clave_nueva"]
    assert _ingresar(client, "70123456", nueva).status_code == 200


def test_la_clave_vieja_de_6_numeros_mandada_por_whatsapp_tambien_se_anula(repo):
    _c, cuenta = _comercio(repo, con_clave="004217", version=0)
    r = ingest.handle_message(_msg("59170123456", "mi clave es 004217", "wa-6"), repo)
    assert r.get("clave_anulada") is True and cuenta["clave_hash"] is None
    assert "004217" not in json.dumps(repo.wa_inbox["wa-6"])


def test_la_clave_mandada_en_un_grupo_tambien_se_anula(repo):
    _c, cuenta = _comercio(repo)
    r = ingest.handle_message(_msg("59170123456", CLAVE, "wa-g", grupo="120363111222333@g.us"), repo)
    assert r.get("clave_anulada") is True and cuenta["clave_hash"] is None and repo.publicaciones == []
    assert CLAVE.split("-")[1] not in json.dumps(repo.wa_inbox["wa-g"])


def test_solo_cuenta_la_clave_del_numero_que_la_manda(repo):
    """La clave de OTRO comercio, mandada desde un número que no es el suyo, no se compara (y no
    anula nada): sólo se miran las cuentas del número que escribe."""
    c, cuenta = _comercio(repo)
    repo.seed_comercio(id="otro", slug="otro", nombre="Otro", whatsapp="59171112222", activo=True, confiable=True)
    r = ingest.handle_message(_msg("59171112222", f"oferta {CLAVE} zapatillas 200"), repo)
    assert r.get("clave_anulada") is None
    assert cuenta["clave_hash"] and cuenta["credenciales_version"] == 1 and repo.comercio_eventos == []


def test_un_mensaje_normal_no_toca_la_clave_y_se_publica(repo):
    c, cuenta = _comercio(repo, confiable=True)
    r = ingest.handle_message(_msg("59170123456", "Oferta estampados 250 Bs, mesa 200 Bs, llegaron las camperas"), repo)
    assert r["estado"] == "aprobado" and len(repo.publicaciones) == 1
    assert cuenta["clave_hash"] and cuenta["credenciales_version"] == 1
    assert repo.comercio_eventos == []


def test_el_mismo_mensaje_con_la_clave_no_anula_dos_veces_ni_guarda_la_clave(repo):
    c, cuenta = _comercio(repo)
    ingest.handle_message(_msg("59170123456", CLAVE, "wa-dup"), repo)
    assert ingest.handle_message(_msg("59170123456", CLAVE, "wa-dup"), repo)["duplicate"] is True      # el reintento de WAHA
    assert cuenta["credenciales_version"] == 2 and len(repo.comercio_eventos) == 1
    assert "K7M2P9" not in json.dumps(repo.wa_inbox["wa-dup"])


def test_una_cuenta_sin_clave_no_gasta_pbkdf2_con_un_mensaje_cualquiera(repo, monkeypatch):
    _comercio(repo, con_clave=None, confiable=True)
    gastos = []
    monkeypatch.setattr(auth, "verify_password", lambda *a: gastos.append(a) or False)
    ingest.handle_message(_msg("59170123456", "Oferta estampados 250 Bs, mesa 200 Bs"), repo)
    assert gastos == []


def test_se_prueban_pocos_candidatos_por_mensaje(repo, monkeypatch):
    _comercio(repo, confiable=True)
    gastos = []
    real = auth.verify_password
    monkeypatch.setattr(auth, "verify_password", lambda *a: gastos.append(a) or real(*a))
    texto = " ".join(f"X{n}-STAMPA" for n in range(30))          # 30 tramos con forma de clave
    assert len(clave_filtrada.candidatos(texto)) <= clave_filtrada.MAX_CANDIDATOS
    ingest.handle_message(_msg("59170123456", texto), repo)
    assert 0 < len(gastos) <= clave_filtrada.MAX_CANDIDATOS


def test_los_candidatos_ordenan_primero_lo_mas_parecido_a_una_clave():
    c = clave_filtrada.candidatos("estampa " * 20 + "boutique-k7m2p9")
    assert c[0] == "boutique-k7m2p9"
    assert clave_filtrada.candidatos(None) == [] and clave_filtrada.candidatos("hola") == []
    assert "004217" in clave_filtrada.candidatos("mi clave 004217")


def test_enmascarar_tapa_en_todo_el_crudo():
    crudo = {"body": "mi clave BOUTIQUE-K7M2P9", "_data": {"body": "mi clave boutique-k7m2p9", "lista": ["x BOUTIQUE-K7M2P9", 3]},
             "n": 7}
    tapado = clave_filtrada.enmascarar(crudo, ["BOUTIQUE-K7M2P9"])
    assert "K7M2P9" not in json.dumps(tapado).upper() and tapado["n"] == 7
    assert tapado["body"] == "mi clave [clave]" and crudo["body"].endswith("K7M2P9")          # copia, no toca el original


def test_la_clave_mandada_por_whatsapp_nunca_va_a_un_log(repo, capfd):
    _comercio(repo)
    ingest.handle_message(_msg("59170123456", CLAVE, "wa-log"), repo)
    salida = capfd.readouterr()
    todo = salida.out + salida.err
    assert "ingest.clave_por_whatsapp" in todo
    assert "K7M2P9" not in todo.upper() and "59170123456" not in todo


def test_si_no_se_puede_anular_no_se_sigue_con_la_clave_a_la_vista(repo, monkeypatch):
    _comercio(repo)
    monkeypatch.setattr(repo, "anular_clave_comercio", lambda ids: (_ for _ in ()).throw(RuntimeError("base caída")))
    with pytest.raises(RuntimeError):
        ingest.handle_message(_msg("59170123456", CLAVE, "wa-falla"), repo)
    # El mensaje ya quedó tapado en la bandeja y SIN resultado: WAHA reintenta y se completa.
    assert "K7M2P9" not in json.dumps(repo.wa_inbox["wa-falla"]) and repo.wa_inbox["wa-falla"].get("resultado") is None


# ═════════════════════════════════════════════════════════ 5. auditoría del admin
def test_generar_clave_deja_un_registro_persistente_sin_la_clave(client, repo, admin_token):
    c, _cuenta = _comercio(repo)
    r = client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(admin_token))
    assert r.status_code == 200
    assert repo.comercio_eventos == [{"comercio_id": c["id"], "tipo": "clave_generada_por_admin", "actor": "admin@bermejolive.com"}]
    assert r.json()["clave"].split("-")[1] not in json.dumps(repo.comercio_eventos)
    client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(admin_token))
    assert len(repo.comercio_eventos) == 2


@pytest.mark.parametrize("malo", ["no-existe", "123", "../../etc", "5f0c1b7e", "5f0c1b7e-3a2d-4c8e-9b1f-0a6d2e4c7b9z"])
def test_un_id_que_no_es_uuid_da_404_y_no_toca_nada(client, repo, admin_token, malo):
    c, cuenta = _comercio(repo)
    r = client.post(f"/admin/comercio/{malo}/clave", headers=_hdr(admin_token))
    assert r.status_code == 404
    assert repo.comercio_eventos == [] and cuenta["credenciales_version"] == 1


def test_un_uuid_inexistente_da_404(client, repo, admin_token):
    _comercio(repo)
    assert client.post(f"/admin/comercio/{uuid.uuid4()}/clave", headers=_hdr(admin_token)).status_code == 404
    assert repo.comercio_eventos == []


def test_un_comercio_dado_de_baja_no_recibe_claves(client, repo, admin_token):
    c, cuenta = _comercio(repo)
    c["activo"] = False
    r = client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(admin_token))
    assert r.status_code == 404 and "clave" not in r.json()
    assert cuenta["credenciales_version"] == 1 and repo.comercio_eventos == []
    assert clave_comercio.clave_coincide(CLAVE, cuenta["clave_hash"])                  # intacta


def test_sin_permiso_no_hay_clave_ni_registro(client, repo):
    c, _cuenta = _comercio(repo)
    sin = auth.make_token("m@uruku.bo", rol="moderador", permisos=["comercios.editar"])
    assert client.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(sin)).status_code == 403
    assert repo.comercio_eventos == []


def test_si_no_se_puede_dejar_constancia_no_se_cambia_la_clave(repo, admin_token):
    c, cuenta = _comercio(repo)
    repo.falla_auditoria = True
    app.dependency_overrides[get_repo] = lambda: repo
    try:
        with TestClient(app, raise_server_exceptions=False) as cliente:
            r = cliente.post(f"/admin/comercio/{c['id']}/clave", headers=_hdr(admin_token))
    finally:
        app.dependency_overrides.clear()
    assert r.status_code == 500
    assert cuenta["credenciales_version"] == 1 and clave_comercio.clave_coincide(CLAVE, cuenta["clave_hash"])


# ═════════════════════════════════════════════════════════ 6. bajos
def test_el_login_gasta_el_mismo_tiempo_cuando_la_clave_no_tiene_forma(client, repo, monkeypatch):
    _comercio(repo)
    gastos = []
    real = claves.gastar_tiempo
    monkeypatch.setattr(claves, "gastar_tiempo", lambda c: gastos.append(c) or real(c))
    # Sin forma de clave: no se verifica nada, pero se gasta igual el tiempo de un PBKDF2.
    assert _ingresar(client, "70123456", "x").status_code == 401
    assert _ingresar(client, "70123456", "ñandú!").status_code == 401
    assert len(gastos) == 2
    # Con forma de clave (mala o buena) ya se gasta el PBKDF2 de verdad: no se suma otro.
    assert _ingresar(client, "70123456", "BOUTIQUE-ZZZZZZ").status_code == 401
    assert _ingresar(client, "70123456", CLAVE).status_code == 200
    assert len(gastos) == 2
    # Un número sin cuenta: se gasta (como antes).
    assert _ingresar(client, "70999999", "BOUTIQUE-ZZZZZZ").status_code == 401
    assert len(gastos) == 3


def _fallar(client, repo, tandas, por_tanda=4):
    from datetime import timedelta

    estados = []
    for _ in range(tandas):
        for _ in range(por_tanda):
            estados.append(_ingresar(client, "70123456", "BOUTIQUE-ZZZZZZ"))
        for f in repo.clave_fallos:
            f["created_at"] -= timedelta(minutes=16)
    return estados


def test_la_clave_nueva_no_se_anula_por_10_fallos_en_el_dia(client, repo):
    _c, cuenta = _comercio(repo)
    rs = _fallar(client, repo, tandas=4)                         # 16 fallos en 4 tandas de 4
    assert all(r.status_code == 401 and r.json()["detail"] == claves.MENSAJE_INCORRECTA for r in rs)
    assert cuenta["clave_hash"] and cuenta["credenciales_version"] == 1
    # La del dueño sigue sirviendo (pasado el bloqueo de 15 minutos).
    assert _ingresar(client, "70123456", CLAVE).status_code == 200


def test_la_clave_nueva_sigue_bloqueada_por_5_fallos_en_15_minutos(client, repo):
    _c, cuenta = _comercio(repo)
    for _ in range(5):
        assert _ingresar(client, "70123456", "BOUTIQUE-ZZZZZZ").status_code == 401
    r = _ingresar(client, "70123456", CLAVE)
    assert r.status_code == 429 and r.json()["detail"] == claves.MENSAJE_BLOQUEADO


def test_un_numero_sin_cuenta_contesta_igual_que_uno_con_clave_nueva(client, repo):
    """Pasadas las 10 fallas del día, un número sin cuenta y uno con clave nueva dicen lo mismo
    (nada de «tu clave se anuló», que sólo se vería en las cuentas con clave vieja)."""
    from datetime import timedelta

    _comercio(repo)
    detalles = []
    for numero, ip in (("70123456", "1.1.1.1"), ("70999999", "2.2.2.2")):      # una IP por número: el tope por IP es otro
        def probar():
            return client.post("/auth/comercio/ingresar", headers={"X-Forwarded-For": ip},
                               json={"whatsapp": numero, "clave": "BOUTIQUE-ZZZZZZ"})
        for _ in range(4):
            probar()
        for f in repo.clave_fallos:
            f["created_at"] -= timedelta(minutes=16)
        for _ in range(6):
            r = probar()
        detalles.append((r.status_code, r.json()["detail"]))
    assert detalles[0] == detalles[1] == (429, claves.MENSAJE_BLOQUEADO)


def test_la_clave_vieja_de_6_numeros_si_se_anula_y_la_nueva_del_mismo_numero_no(client, repo):
    """Un número con dos comercios: la cuenta de clave vieja se anula, la de clave nueva no."""
    _c, vieja = _comercio(repo, con_clave="123456", version=0)
    otro = repo.seed_comercio(id="otro", slug="otro", nombre="Puesto", whatsapp="59170123456", activo=True)
    nueva = repo.crear_comercio_usuario({"comercio_id": otro["id"], "nombre": "Puesto"})
    nueva["clave_hash"] = clave_comercio.hash_clave("PUESTO-K7M2P9")
    nueva["credenciales_version"] = 1
    for _ in range(2):
        for _ in range(4):
            _ingresar(client, "70123456", "654321")
        from datetime import timedelta
        for f in repo.clave_fallos:
            f["created_at"] -= timedelta(minutes=16)
    _ingresar(client, "70123456", "654321")
    r = _ingresar(client, "70123456", "654321")
    assert r.json()["detail"] == claves.MENSAJE_ANULADA
    assert vieja["clave_hash"] is None and nueva["clave_hash"]


def test_el_comprador_conserva_la_anulacion_por_10_fallos():
    assert ingreso_clave._se_anula_por_10_fallos("usuarios", None) is True


@pytest.mark.parametrize("nombre,esperado", [
    ("URUKU", "LOCAL"), ("Uruku Bazar", "BAZAR"), ("URUKU123 Bazar", "BAZAR"), ("Uruku1", "LOCAL"),
    ("URUKUXYZ", "LOCAL"), ("urukumart ropa", "ROPA"), ("Bazar Uruku", "BAZAR"), ("Surukuy", "SURUKUY"),
])
def test_ningun_prefijo_empieza_con_URUKU(nombre, esperado):
    assert clave_comercio.prefijo_de(nombre) == esperado
    assert not clave_comercio.generar_clave(nombre).startswith("URUKU")


def test_sin_cartel_tampoco_empieza_con_URUKU():
    assert clave_comercio.prefijo_de(None, sin_cartel=True, subcategoria="Urukunet cables", rubro="Electrónica") == "CABLES"
    assert clave_comercio.prefijo_de(None, sin_cartel=True, subcategoria="URUKU9", rubro="URUKU") == "LOCAL"


def test_los_tracebacks_no_llevan_variables_locales(capfd):
    from app.core.registro import configurar_logging

    configurar_logging()
    log = structlog.get_logger()

    def ingresar_con(la_clave):
        hash_secreto = "pbkdf2_sha256$100000$aa$bb"
        raise ValueError("falló")

    secreta = "BOUTIQUE-" + "K7M2P9"
    try:
        ingresar_con(secreta)
    except ValueError:
        log.error("prueba.fallo", exc_info=True)
    todo = capfd.readouterr()
    todo = todo.out + todo.err
    assert "prueba.fallo" in todo and "Traceback" in todo and "ValueError" in todo
    assert "K7M2P9" not in todo and "pbkdf2_sha256" not in todo and "hash_secreto" not in todo


def test_main_configura_el_registro_sin_locales():
    texto = (RAIZ / "backend/app/main.py").read_text(encoding="utf-8")
    assert "configurar_logging()" in texto
    registro = (RAIZ / "backend/app/core/registro.py").read_text(encoding="utf-8")
    assert "exception_formatter=structlog.dev.plain_traceback" in registro


# ─────────────────────────────────────────────── alta idempotente del agente (alta_uid)
def _login_agente(client, email="agente@bermejolive.com", password="campo1234"):
    return client.post("/auth/campo/login", json={"email": email, "password": password}).json()["access_token"]


def _alta(client, token=None, **extra):
    datos = {"nombre": "Boutique Lucía", "whatsapp": "70002222", "modalidad": "minorista",
             "lat": "-22.7361", "lng": "-64.3433", **extra}
    return client.post("/campo/comercio", headers=_hdr(token or _login_agente(client)), data=datos, files=_foto())


def test_un_alta_sin_alta_uid_se_comporta_como_siempre(client, repo):
    a = _alta(client, whatsapp="70001111")
    b = _alta(client, whatsapp="70001112")
    assert a.status_code == b.status_code == 200 and a.json()["comercio"]["id"] != b.json()["comercio"]["id"]
    assert "repetida" not in a.json() and len(repo.comercios) == 2
    assert all(c.get("alta_uid") is None for c in repo.comercios.values())


def test_un_alta_con_alta_uid_guarda_el_uid_en_el_comercio(client, repo):
    r = _alta(client, alta_uid="2f6c9e0a-7b1d-4c55-8a3e-1f0d9c4b7a21")
    assert r.status_code == 200, r.text
    (c,) = repo.comercios.values()
    assert c["alta_uid"] == "2f6c9e0a-7b1d-4c55-8a3e-1f0d9c4b7a21" and c["cargado_por"] == "agente@bermejolive.com"
    assert "alta_uid" not in json.dumps(r.json())                      # no vuelve al celular


def test_el_reintento_del_mismo_alta_devuelve_el_mismo_comercio_con_una_clave_nueva(client, repo):
    token = _login_agente(client)
    primero = _alta(client, token, alta_uid="alta-001")
    assert primero.status_code == 200
    clave1, cid = primero.json()["clave"], primero.json()["comercio"]["id"]
    assert _ingresar(client, "70002222", clave1).status_code == 200
    segundo = _alta(client, token, alta_uid="alta-001")
    assert segundo.status_code == 200, segundo.text
    assert segundo.json()["comercio"]["id"] == cid and segundo.json()["repetida"] is True
    assert len(repo.comercios) == 1                                    # no se duplicó
    clave2 = segundo.json()["clave"]
    assert FORMATO.match(clave2) and clave2 != clave1 and segundo.json()["clave_inicial"] == clave2
    assert segundo.headers["cache-control"] == "no-store"
    assert _ingresar(client, "70002222", clave1).status_code == 401    # la del primer intento queda invalidada
    assert _ingresar(client, "70002222", clave2).status_code == 200
    assert "alta_uid" not in json.dumps(segundo.json()) and "codigo" not in segundo.json()["comercio"]


def test_el_mismo_alta_uid_de_otro_agente_es_otro_alta(client, repo):
    uno = _alta(client, alta_uid="alta-001")
    otro_token = auth.make_agente_token("otro-agente@uruku.bo")
    dos = _alta(client, otro_token, alta_uid="alta-001", whatsapp="70003333")
    assert uno.status_code == dos.status_code == 200 and len(repo.comercios) == 2
    assert uno.json()["comercio"]["id"] != dos.json()["comercio"]["id"]


@pytest.mark.parametrize("uid", ["x" * 65, "con espacios", "raro;drop", "ñandú", "a/b"])
def test_un_alta_uid_invalido_da_400_y_no_crea_nada(client, repo, uid):
    r = _alta(client, alta_uid=uid)
    assert r.status_code == 400 and repo.comercios == {}


def test_un_alta_uid_de_64_caracteres_o_vacio_es_valido(client, repo):
    assert _alta(client, alta_uid="a" * 64).status_code == 200
    assert _alta(client, alta_uid="   ", whatsapp="70004444").status_code == 200       # vacío = sin alta_uid
    assert len(repo.comercios) == 2


def test_dos_reintentos_en_paralelo_no_duplican_el_comercio(client, repo, monkeypatch):
    """El segundo pasa el chequeo previo antes de que el primero termine; el índice único
    (cargado_por, alta_uid) lo frena al insertar y se devuelve el comercio que ya está."""
    token = _login_agente(client)
    primero = _alta(client, token, alta_uid="carrera-1")
    original = repo.get_comercio_por_alta_uid
    llamadas = []

    def sin_ver_el_primero(cargado_por, alta_uid):
        llamadas.append(1)
        return None if len(llamadas) == 1 else original(cargado_por, alta_uid)

    monkeypatch.setattr(repo, "get_comercio_por_alta_uid", sin_ver_el_primero)
    segundo = _alta(client, token, alta_uid="carrera-1")
    assert segundo.status_code == 200 and segundo.json()["repetida"] is True
    assert segundo.json()["comercio"]["id"] == primero.json()["comercio"]["id"] and len(repo.comercios) == 1


def test_el_reintento_de_un_alta_dada_de_baja_da_409_y_no_da_clave(client, repo):
    token = _login_agente(client)
    primero = _alta(client, token, alta_uid="baja-1")
    repo.comercios[primero.json()["comercio"]["id"]]["activo"] = False
    r = _alta(client, token, alta_uid="baja-1")
    assert r.status_code == 409 and "clave" not in r.json()


def test_las_respuestas_de_campo_y_comercio_no_traen_el_codigo_anterior_ni_el_alta_uid():
    fila = {"id": "x", "nombre": "N", "codigo": "K7M2", "codigo_formateado": "URUKU-K7M2",
            "codigo_anterior": "AAAA", "alta_uid": "alta-001", "slug": "n"}
    assert sin_codigo(fila) == {"id": "x", "nombre": "N", "slug": "n"}
    assert fila["codigo_anterior"] == "AAAA"                               # no toca el original


# ─────────────────────────────────────────────── el código regenerado y la aprobación
def test_aprobar_una_publicacion_que_entro_con_el_codigo_viejo_funciona(client, repo):
    c = repo.seed_comercio(slug="zap", nombre="Zapatería", codigo="N8G7", codigo_anterior="K7M2", activo=True)
    pub = repo.insert_publicacion({"comercio_id": c["id"], "tipo": "oferta", "estado": "pendiente",
                                   "identidad_origen": "codigo", "codigo_recibido": "K7M2", "origen": "whatsapp",
                                   "wa_message_id": "w1"})
    mod = auth.make_token("m@uruku.bo", rol="moderador", permisos=["moderar"])
    r = client.post(f"/moderacion/publicaciones/{pub['id']}", headers=_hdr(mod), json={"estado": "aprobado"})
    assert r.status_code == 200, r.text


def test_sigue_bloqueando_si_el_codigo_recibido_no_es_ni_el_actual_ni_el_anterior(client, repo):
    c = repo.seed_comercio(slug="zap", nombre="Zapatería", codigo="N8G7", codigo_anterior="K7M2", activo=True)
    otra = repo.insert_publicacion({"comercio_id": c["id"], "tipo": "oferta", "estado": "pendiente",
                                    "identidad_origen": "codigo", "codigo_recibido": "ZZZZ", "wa_message_id": "w2"})
    sin_anterior = repo.seed_comercio(slug="otra", nombre="Otra", codigo="BBBB", activo=True)
    vieja = repo.insert_publicacion({"comercio_id": sin_anterior["id"], "tipo": "oferta", "estado": "pendiente",
                                     "identidad_origen": "codigo", "codigo_recibido": "K7M2", "wa_message_id": "w3"})
    mod = auth.make_token("m@uruku.bo", rol="moderador", permisos=["moderar"])
    for pub in (otra, vieja):
        r = client.post(f"/moderacion/publicaciones/{pub['id']}", headers=_hdr(mod), json={"estado": "aprobado"})
        assert r.status_code == 409, r.text
    # Y con el código vigente, bien.
    ok = repo.insert_publicacion({"comercio_id": c["id"], "tipo": "oferta", "estado": "pendiente",
                                  "identidad_origen": "codigo", "codigo_recibido": "N8G7", "wa_message_id": "w4"})
    assert client.post(f"/moderacion/publicaciones/{ok['id']}", headers=_hdr(mod), json={"estado": "aprobado"}).status_code == 200


def test_el_codigo_viejo_ya_no_identifica_a_nadie_en_la_ingesta(repo):
    c = repo.seed_comercio(slug="zap", nombre="Zapatería", codigo="N8G7", codigo_anterior="K7M2", activo=True)
    antes = len(repo.publicaciones)
    r = ingest.handle_message(_msg("59177777777", "URUKU-K7M2 oferta taladro a 300"), repo)
    assert r.get("publicada") is False and len(repo.publicaciones) == antes
    r = ingest.handle_message(_msg("59177777777", "URUKU-N8G7 oferta taladro a 300", "wa-2"), repo)
    assert r.get("comercio") == "zap" and len(repo.publicaciones) == antes + 1


# ═════════════════════════════════════════════════════════ la migración 0149
def _sql():
    return sin_comentarios_sql(leer_0149())


def test_la_0149_regenera_codigos_versiona_credenciales_audita_y_cierra_funciones_del_panel():
    sql = _sql()
    assert "begin;" in sql and sql.rstrip().endswith("notify pgrst, 'reload schema';")
    assert sql.index("begin;") < sql.index("rotar_credenciales_comercio") < sql.index("commit;")
    # Idempotente: nada de create sin if not exists, y los códigos se regeneran sólo la primera vez.
    assert not re.search(r"create table(?! if not exists)", sql)
    assert "uruku.regenerar_codigos_0149" in sql and "add column if not exists codigo_anterior" in sql
    # Columnas nuevas.
    assert "add column if not exists alta_uid" in sql
    assert re.search(r"create unique index if not exists idx_comercios_alta_uid\s+on public\.comercios \(cargado_por, alta_uid\) where alta_uid is not null;", sql)
    assert re.search(r"add column if not exists credenciales_version int not null default 0", sql)
    # Misma longitud y alfabeto que app/core/codigo.py.
    from app.core import codigo
    assert f"'{codigo._ALFABETO}'" in sql and "length(v_nuevo) < 4" in sql and codigo._LARGO == 4
    # Aleatoriedad criptográfica (no random()).
    assert "gen_random_uuid()" in sql and "random()" not in sql.replace("gen_random_uuid()", "")
    # Funciones del panel y de rotación: sólo service_role.
    for firma in ("previsualizar_patron(text, text)", "rubros_a_revisar(text, integer)"):
        assert f"revoke execute on function public.{firma} from public, anon, authenticated;" in sql
        assert f"grant execute on function public.{firma} to service_role;" in sql
    assert "revoke all on function public.rotar_credenciales_comercio(uuid[], text) from public, anon, authenticated;" in sql
    # Auditoría privada.
    assert "alter table public.comercio_eventos enable row level security;" in sql
    assert "revoke all on public.comercio_eventos from public, anon, authenticated;" in sql
    assert re.search(r"actor\s+text not null", sql) and "comercio_id uuid not null references public.comercios(id)" in sql
    assert "do $chk$" in sql


def test_el_repo_real_llama_a_la_funcion_de_la_0149(monkeypatch):
    """El adaptador de PostgREST usa `rotar_credenciales_comercio` y no hace un UPDATE a mano."""
    from app.db.repository import SupabaseRepo

    llamadas = []

    class Res:
        data = [{"id": "u1", "credenciales_version": 4}]

    class Rpc:
        def __init__(self, nombre, params):
            llamadas.append((nombre, params))

        def execute(self):
            return Res()

    class Db:
        def rpc(self, nombre, params):
            return Rpc(nombre, params)

    repo = SupabaseRepo.__new__(SupabaseRepo)
    repo._db = Db()
    assert repo.set_clave_comercio("u1", "hash") == 4
    repo.anular_clave_comercio(["u1", "u2"])
    repo.anular_clave_comercio([])
    assert llamadas == [("rotar_credenciales_comercio", {"p_ids": ["u1"], "p_clave_hash": "hash"}),
                        ("rotar_credenciales_comercio", {"p_ids": ["u1", "u2"], "p_clave_hash": None})]


UUID_A = "11111111-1111-4111-8111-111111111111"
UUID_B = "22222222-2222-4222-8222-222222222222"
ALFABETO = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"


@pytest.fixture(scope="module")
def migrada(pg0149):
    """La base con 40 comercios de códigos viejos (uno sin código, uno dado de baja) y la 0149 aplicada UNA vez."""
    import itertools
    viejos = ["".join(p) for p in itertools.islice(itertools.product("AB2", repeat=4), 40)]
    valores = ", ".join(f"('{viejo}', 'agente{i % 3}@uruku.bo', {'false' if i == 3 else 'true'})"
                        for i, viejo in enumerate(viejos))
    pg0149(f"""
        insert into comercios (codigo, cargado_por, activo) values {valores};
        insert into comercios (id, codigo, activo) values ('{UUID_A}', null, true);
        insert into comercio_usuarios (id, comercio_id, clave_hash) select gen_random_uuid(), id, 'h' from comercios where codigo is not null limit 3;
    """)
    antes = pg0149("select codigo from comercios where codigo is not null order by codigo;").stdout.split()
    assert antes == sorted(viejos)
    pg0149(leer_0149())
    pg0149.viejos = viejos
    return pg0149


def _codigos(psql):
    filas = psql("select coalesce(codigo,'-'), coalesce(codigo_anterior,'-'), id from comercios order by id;").stdout.strip().splitlines()
    return {f.split("|")[2]: (f.split("|")[0], f.split("|")[1]) for f in filas}


def test_0149_en_postgres_regenera_los_codigos_validos_unicos_y_distintos_de_los_viejos(migrada):
    filas = migrada("select codigo, codigo_anterior from comercios where codigo is not null order by id;").stdout.strip().splitlines()
    assert len(filas) == 40
    nuevos = [f.split("|")[0] for f in filas]
    anteriores = [f.split("|")[1] for f in filas]
    assert len(set(nuevos)) == 40                                               # sin colisiones
    assert all(len(c) == 4 and set(c) <= set(ALFABETO) for c in nuevos)         # mismo alfabeto y largo
    assert sorted(anteriores) == sorted(migrada.viejos)                          # guarda el viejo
    assert all(n != a for n, a in zip(nuevos, anteriores))
    assert not set(nuevos) & set(migrada.viejos)                                 # y ninguno repite un código viejo
    # El comercio sin código sigue sin código (no se inventa).
    assert migrada(f"select codigo is null, codigo_anterior is null from comercios where id = '{UUID_A}';").stdout.strip() == "t|t"


def test_0149_en_postgres_los_codigos_solo_se_regeneran_la_primera_vez(migrada):
    despues_de_la_primera = _codigos(migrada)
    # Un comercio que nace DESPUÉS (con su código propio) no se toca al volver a correr la migración.
    migrada(f"insert into comercios (id, codigo, activo) values ('{UUID_B}', 'ZZZ2', true);")
    migrada(leer_0149())
    migrada(leer_0149())
    ahora = _codigos(migrada)
    esperado = dict(despues_de_la_primera)
    esperado[UUID_B] = ("ZZZ2", "-")
    assert ahora == esperado


def test_0149_en_postgres_los_codigos_nuevos_son_aleatorios_y_cubren_el_alfabeto(migrada):
    nuevos = "".join(c[0] for c in _codigos(migrada).values() if c[0] not in ("-", "ZZZ2"))
    assert len(set(nuevos)) >= 15                                                # no es un patrón fijo
    assert not re.fullmatch(r"(.)\1+", nuevos)


def test_0149_en_postgres_columnas_nuevas_privadas_y_funcion_de_rotacion(migrada):
    for rol in ("anon", "authenticated"):
        for col in ("codigo", "codigo_anterior", "alta_uid"):
            r = migrada(f"select {col} from comercios;", rol=rol, check=False)
            assert r.returncode != 0 and "permission denied" in r.stderr, (rol, col)
        r = migrada("select * from comercio_eventos;", rol=rol, check=False)
        assert r.returncode != 0 and "permission denied" in r.stderr
        r = migrada("select credenciales_version from comercio_usuarios;", rol=rol, check=False)
        assert r.returncode != 0 and "permission denied" in r.stderr
        r = migrada(f"select * from rotar_credenciales_comercio(array['{UUID_A}']::uuid[], 'x');", rol=rol, check=False)
        assert r.returncode != 0 and "permission denied for function" in r.stderr
    # service_role: rota, sube la versión y anula con null.
    ids = migrada("select id from comercio_usuarios order by id;").stdout.split()
    assert len(ids) == 3
    arr = "array[" + ",".join(f"'{i}'" for i in ids[:2]) + "]::uuid[]"
    r = migrada(f"select credenciales_version from rotar_credenciales_comercio({arr}, 'hash-nuevo') order by id;", rol="service_role")
    assert r.stdout.split() == ["1", "1"]
    r = migrada(f"select credenciales_version from rotar_credenciales_comercio({arr}, null) order by id;", rol="service_role")
    assert r.stdout.split() == ["2", "2"]
    assert migrada(f"select count(*) from comercio_usuarios where id in ('{ids[0]}','{ids[1]}') and clave_hash is null;").stdout.strip() == "2"
    assert migrada(f"select clave_hash, credenciales_version from comercio_usuarios where id = '{ids[2]}';").stdout.strip() == "h|0"   # la tercera no se tocó
    assert migrada("select * from rotar_credenciales_comercio(array[]::uuid[], 'x');", rol="service_role").stdout.strip() == ""


def test_0149_en_postgres_la_auditoria_es_solo_del_backend_y_exige_comercio(migrada):
    cid = migrada("select id from comercios where codigo is not null limit 1;").stdout.strip()
    migrada(f"insert into comercio_eventos (comercio_id, tipo, actor) values ('{cid}', 'clave_generada_por_admin', 'ana@uruku.bo');",
            rol="service_role")
    assert migrada("select tipo, actor from comercio_eventos;", rol="service_role").stdout.strip() == "clave_generada_por_admin|ana@uruku.bo"
    r = migrada(f"insert into comercio_eventos (comercio_id, tipo, actor) values ('{cid}', 'x', 'y');", rol="anon", check=False)
    assert r.returncode != 0 and "permission denied" in r.stderr
    r = migrada(f"insert into comercio_eventos (comercio_id, tipo, actor) values ('{uuid.uuid4()}', 'x', 'y');", rol="service_role", check=False)
    assert r.returncode != 0 and "violates foreign key" in r.stderr
    r = migrada(f"insert into comercio_eventos (comercio_id, tipo) values ('{cid}', 'x');", rol="service_role", check=False)
    assert r.returncode != 0 and "null value" in r.stderr


def test_0149_en_postgres_alta_uid_es_unico_por_agente(migrada):
    migrada("update comercios set alta_uid = 'alta-1' where codigo = (select codigo from comercios where cargado_por = 'agente0@uruku.bo' order by id limit 1);")
    r = migrada("update comercios set alta_uid = 'alta-1' where id = (select id from comercios where cargado_por = 'agente0@uruku.bo' order by id offset 1 limit 1);", check=False)
    assert r.returncode != 0 and "idx_comercios_alta_uid" in r.stderr
    # Otro agente puede usar el mismo uid, y sin uid (null) no hay límite.
    migrada("update comercios set alta_uid = 'alta-1' where id = (select id from comercios where cargado_por = 'agente1@uruku.bo' order by id limit 1);")
    migrada("select 1 from comercios where alta_uid is null;")
    assert int(migrada("select count(*) from comercios where alta_uid is null;").stdout) >= 30


def test_0149_en_postgres_es_idempotente_con_todo_el_resto(migrada):
    migrada(leer_0149())
    assert migrada("select count(*) from comercios where codigo = codigo_anterior;").stdout.strip() == "0"
    r = migrada("select * from previsualizar_patron('x', null);", rol="anon", check=False)
    assert r.returncode != 0
    r = migrada("select raw from publicaciones;", rol="anon", check=False)
    assert r.returncode != 0 and "permission denied" in r.stderr
