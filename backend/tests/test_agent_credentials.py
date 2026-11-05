"""Credencial de los agentes y página pública de agentes (docs/credencial-agentes.md).

Cubre los criterios de terminado §6 del lado del backend:
  1. token de 22+ caracteres; reemitir revoca la anterior; nunca dos vivas;
  2. las respuestas públicas no traen correo, ids, roles ni (en la lista) el token;
  3. token inexistente -> 404 con el mismo cuerpo siempre;
  4. revocar con corte de acceso -> 401 en /campo/* (con el caché de 60 s);
  5. la lista sólo muestra activos con credencial vigente y foto.
"""
import uuid
from io import BytesIO
from pathlib import Path

import pytest
import structlog
from PIL import Image

from app.core import auth
from app.core.config import settings

NO_ES_DE_URUKU = {"detail": "Esta credencial no es de URUKU"}
PASS = "campo-2026-larga"


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _jpeg(ancho=2000, alto=1500, con_exif=True, comentario=b"") -> bytes:
    img = Image.new("RGB", (ancho, alto), (200, 80, 40))
    kw = {}
    if comentario:
        kw["comment"] = comentario
    if con_exif:
        exif = Image.Exif()
        exif[0x010F] = "CamaraSecreta"       # Make
        exif[0x0110] = "Modelo-X"            # Model
        kw["exif"] = exif
    buf = BytesIO()
    img.save(buf, format="JPEG", **kw)
    return buf.getvalue()


def _png() -> bytes:
    buf = BytesIO()
    Image.new("RGBA", (300, 200), (10, 120, 200, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _alta(client, admin_token, email="ana@uruku.bo", nombre="Ana", apellido="Pérez",
          roles=("agente",), ciudad="bermejo"):
    r = client.post("/admin/equipo", headers=_h(admin_token), json={
        "email": email, "password": PASS, "nombre": nombre, "apellido": apellido,
        "roles": list(roles), "ciudad_slug": ciudad})
    assert r.status_code == 200, r.text
    return r.json()["usuario"]["id"]


def _foto(client, admin_token, uid, data=None, nombre="foto.jpg", tipo="image/jpeg"):
    return client.post(f"/admin/agents/{uid}/photo", headers=_h(admin_token),
                       files={"foto": (nombre, data if data is not None else _jpeg(), tipo)})


def _agente_listo(client, admin_token, **kw):
    """Un agente con nombre, apellido y foto: listo para emitirle la credencial."""
    uid = _alta(client, admin_token, **kw)
    assert _foto(client, admin_token, uid).status_code == 200
    return uid


def _emitir(client, admin_token, uid, consiente=True):
    return client.post(f"/admin/agents/{uid}/credential", headers=_h(admin_token), json={"consiente": consiente})


def _desconocido():
    return str(uuid.uuid4())


# ───────────────────────────────────────── 1. emisión, token, reemisión

def test_emitir_da_un_token_de_22_caracteres_y_la_forma_del_contrato(client, admin_token):
    uid = _agente_listo(client, admin_token)
    r = _emitir(client, admin_token, uid)
    assert r.status_code == 200, r.text
    j = r.json()
    assert set(j) == {"credential", "photo_url", "nombre", "apellido", "ciudad_nombre", "activo", "consentimiento_at"}
    assert j["consentimiento_at"]
    assert set(j["credential"]) == {"token", "issued_at", "scan_count", "last_scan_at"}
    assert len(j["credential"]["token"]) >= 22
    assert j["credential"]["scan_count"] == 0 and j["credential"]["last_scan_at"] is None
    assert (j["nombre"], j["apellido"], j["ciudad_nombre"], j["activo"]) == ("Ana", "Pérez", "Bermejo", True)
    assert j["photo_url"].startswith(settings.fotos_public_base_url + "/agentes/")
    # El GET devuelve lo mismo.
    assert client.get(f"/admin/agents/{uid}/credential", headers=_h(admin_token)).json() == j


def test_sin_credencial_el_get_trae_null_pero_si_la_foto_y_el_nombre(client, admin_token):
    uid = _agente_listo(client, admin_token)
    j = client.get(f"/admin/agents/{uid}/credential", headers=_h(admin_token)).json()
    assert j["credential"] is None and j["photo_url"] and j["nombre"] == "Ana"


def test_los_tokens_son_distintos_cada_vez(client, admin_token):
    a = _emitir(client, admin_token, _agente_listo(client, admin_token)).json()["credential"]["token"]
    b = _emitir(client, admin_token, _agente_listo(client, admin_token, email="beto@uruku.bo")).json()["credential"]["token"]
    assert a != b


def test_reemitir_revoca_la_anterior_y_nunca_quedan_dos_vivas(client, repo, admin_token):
    uid = _agente_listo(client, admin_token)
    vieja = _emitir(client, admin_token, uid).json()["credential"]["token"]
    nueva = _emitir(client, admin_token, uid).json()["credential"]["token"]
    assert vieja != nueva
    vivas = [c for c in repo.credenciales.values() if c["usuario_id"] == uid and c["activo"]]
    assert len(vivas) == 1 and vivas[0]["token"] == nueva
    previa = next(c for c in repo.credenciales.values() if c["token"] == vieja)
    assert previa["revoke_reason"] == "reemitida" and previa["revoked_at"] and previa["activo"] is False
    # La tarjeta impresa vieja ya no vale; la nueva sí.
    assert client.get(f"/public/agents/{vieja}").json()["status"] == "revoked"
    assert client.get(f"/public/agents/{nueva}").json()["status"] == "valid"
    # Nunca se borra: las dos filas siguen.
    assert len(repo.credenciales) == 2


def test_emitir_pide_foto_nombre_apellido_rol_y_cuenta_activa(client, repo, admin_token):
    # sin foto
    sin_foto = _alta(client, admin_token, email="a@uruku.bo")
    r = _emitir(client, admin_token, sin_foto)
    assert r.status_code == 400 and "foto" in r.json()["detail"].lower()
    # sin apellido
    sin_ape = _alta(client, admin_token, email="b@uruku.bo", apellido="")
    _foto(client, admin_token, sin_ape)
    r = _emitir(client, admin_token, sin_ape)
    assert r.status_code == 400 and "apellido" in r.json()["detail"].lower()
    # sin nombre
    sin_nom = _alta(client, admin_token, email="c@uruku.bo", nombre="")
    _foto(client, admin_token, sin_nom)
    r = _emitir(client, admin_token, sin_nom)
    assert r.status_code == 400 and "nombre" in r.json()["detail"].lower()
    # sin rol de agente
    moni = _alta(client, admin_token, email="d@uruku.bo", roles=["moderador"])
    _foto(client, admin_token, moni)
    r = _emitir(client, admin_token, moni)
    assert r.status_code == 400 and "agente" in r.json()["detail"].lower()
    # desactivado
    off = _agente_listo(client, admin_token, email="e@uruku.bo")
    client.put(f"/admin/equipo/{off}", headers=_h(admin_token),
               json={"email": "e@uruku.bo", "activo": False, "roles": ["agente"]})
    r = _emitir(client, admin_token, off)
    assert r.status_code == 400 and "desactivad" in r.json()["detail"].lower()
    assert repo.credenciales == {}
    # No existe
    assert _emitir(client, admin_token, _desconocido()).status_code == 404


def test_un_rol_propio_que_carga_comercios_tambien_puede_tener_credencial(client, admin_token):
    client.put("/admin/roles/cargador-sc", headers=_h(admin_token), json={
        "slug": "cargador-sc", "nombre": "Cargador", "permisos": ["comercios.cargar"]})
    uid = _agente_listo(client, admin_token, email="luis@uruku.bo", roles=["cargador-sc"])
    assert _emitir(client, admin_token, uid).status_code == 200


def test_los_endpoints_de_admin_piden_el_permiso_equipo(client, admin_token, agente_token):
    uid = _agente_listo(client, admin_token)
    rutas = [("get", f"/admin/agents/{uid}/credential", None),
             ("post", f"/admin/agents/{uid}/credential", {}),
             ("post", f"/admin/agents/{uid}/credential/revoke", {"reason": "x"})]
    for metodo, ruta, cuerpo in rutas:
        kw = {"json": cuerpo} if cuerpo is not None else {}
        assert getattr(client, metodo)(ruta, **kw).status_code == 401
        assert getattr(client, metodo)(ruta, headers=_h(agente_token), **kw).status_code == 403
    r = client.post(f"/admin/agents/{uid}/photo", headers=_h(agente_token),
                    files={"foto": ("f.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 403


def test_un_id_que_no_es_uuid_da_422_y_no_500(client, admin_token):
    h = _h(admin_token)
    assert client.get("/admin/agents/no-es-uuid/credential", headers=h).status_code == 422
    assert client.post("/admin/agents/no-es-uuid/credential", headers=h, json={}).status_code == 422
    assert client.post("/admin/agents/no-es-uuid/credential/revoke", headers=h, json={"reason": "x"}).status_code == 422
    assert client.post("/admin/agents/no-es-uuid/photo", headers=h,
                       files={"foto": ("f.jpg", _jpeg(), "image/jpeg")}).status_code == 422


# ───────────────────────────────────────── foto

def test_la_foto_se_recodifica_a_jpeg_de_800px_sin_exif(client, admin_token):
    uid = _alta(client, admin_token)
    r = _foto(client, admin_token, uid, _jpeg(2000, 1500, comentario=b"texto-secreto-del-comentario"))
    assert r.status_code == 200, r.text
    url = r.json()["photo_url"]
    assert set(r.json()) == {"photo_url"}
    assert url.startswith(settings.fotos_public_base_url + "/agentes/") and url.endswith(".jpg")
    nombre = url.rsplit("/", 1)[1]
    assert uid not in nombre and len(nombre) > 16                   # aleatorio, no el id
    archivo = Path(settings.fotos_dir) / "agentes" / nombre
    assert archivo.exists()
    with Image.open(archivo) as img:
        assert img.format == "JPEG"
        assert max(img.size) <= 800 and img.size == (800, 600)
        assert not dict(img.getexif())                              # sin EXIF (ni cámara ni GPS)
        assert "comment" not in img.info                            # ni el marcador COM
    assert b"CamaraSecreta" not in archivo.read_bytes()
    assert b"texto-secreto-del-comentario" not in archivo.read_bytes()


def test_acepta_png_y_la_foto_anterior_no_se_borra_del_disco(client, repo, admin_token):
    uid = _alta(client, admin_token)
    primera = _foto(client, admin_token, uid).json()["photo_url"]
    segunda = _foto(client, admin_token, uid, _png(), "f.png", "image/png").json()["photo_url"]
    assert primera != segunda
    carpeta = Path(settings.fotos_dir) / "agentes"
    assert {p.name for p in carpeta.iterdir()} == {primera.rsplit("/", 1)[1], segunda.rsplit("/", 1)[1]}
    assert repo.agentes[uid]["photo_url"] == segunda
    # Una foto chica no se agranda.
    with Image.open(carpeta / segunda.rsplit("/", 1)[1]) as img:
        assert img.size == (300, 200)


def test_la_foto_rechaza_lo_que_no_es_jpg_png_o_webp(client, repo, admin_token):
    uid = _alta(client, admin_token)
    r = _foto(client, admin_token, uid, b"esto no es una imagen", "nota.jpg", "image/jpeg")
    assert r.status_code == 400 and "imagen" in r.json()["detail"].lower()
    buf = BytesIO()
    Image.new("RGB", (50, 50)).save(buf, format="GIF")
    r = _foto(client, admin_token, uid, buf.getvalue(), "a.gif", "image/gif")
    assert r.status_code == 400
    assert _foto(client, admin_token, uid, b"", "vacia.jpg").status_code == 400
    assert not repo.agentes[uid].get("photo_url")
    assert not (Path(settings.fotos_dir) / "agentes").exists()


def test_la_foto_de_mas_de_8mb_se_rechaza_y_el_usuario_inexistente_es_404(client, admin_token):
    uid = _alta(client, admin_token)
    r = _foto(client, admin_token, uid, b"\xff\xd8\xff" + b"0" * (8 * 1024 * 1024 + 10))
    assert r.status_code == 413
    assert _foto(client, admin_token, _desconocido()).status_code == 404


# ───────────────────────────────────────── 2 y 3. página de una credencial

CLAVES_PUBLICAS = {"status", "nombre", "apellido", "ciudad", "photo_url", "issued_at", "checked_at"}


def test_credencial_vigente_responde_valid_sin_datos_privados(client, admin_token):
    uid = _agente_listo(client, admin_token)
    token = _emitir(client, admin_token, uid).json()["credential"]["token"]
    r = client.get(f"/public/agents/{token}")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "no-store"
    j = r.json()
    assert set(j) == CLAVES_PUBLICAS
    assert (j["status"], j["nombre"], j["apellido"], j["ciudad"]) == ("valid", "Ana", "Pérez", "Bermejo")
    assert j["photo_url"] and j["issued_at"] and j["checked_at"].endswith("Z")
    # Ni correo, ni ids, ni roles, ni permisos, ni el token en ninguna parte.
    texto = r.text
    for prohibido in ("ana@uruku.bo", uid, token, "roles", "permisos", "password", "email"):
        assert prohibido not in texto


def test_cada_consulta_suma_un_escaneo(client, admin_token):
    uid = _agente_listo(client, admin_token)
    token = _emitir(client, admin_token, uid).json()["credential"]["token"]
    for _ in range(3):
        client.get(f"/public/agents/{token}")
    cred = client.get(f"/admin/agents/{uid}/credential", headers=_h(admin_token)).json()["credential"]
    assert cred["scan_count"] == 3 and cred["last_scan_at"]


def test_un_token_que_no_existe_da_siempre_el_mismo_404(client, admin_token):
    uid = _agente_listo(client, admin_token)
    valido = _emitir(client, admin_token, uid).json()["credential"]["token"]
    parecido = valido[:-1] + ("A" if valido[-1] != "A" else "B")
    respuestas = [client.get(f"/public/agents/{t}") for t in
                  (parecido, "a" * 22, "corto", "x" * 200, "%20%20", "no-existe-esta-credencial-para-nada")]
    for r in respuestas:
        assert r.status_code == 404
        assert r.json() == NO_ES_DE_URUKU
        assert r.headers["cache-control"] == "no-store"
    assert len({r.text for r in respuestas}) == 1


def test_credencial_revocada_responde_revoked_y_avisa_en_el_log(client, admin_token):
    uid = _agente_listo(client, admin_token)
    token = _emitir(client, admin_token, uid).json()["credential"]["token"]
    r = client.post(f"/admin/agents/{uid}/credential/revoke", headers=_h(admin_token),
                    json={"reason": "Dejó de trabajar con nosotros"})
    assert r.status_code == 200 and r.json() == {"ok": True}
    with structlog.testing.capture_logs() as logs:
        j = client.get(f"/public/agents/{token}").json()
    assert set(j) == CLAVES_PUBLICAS and j["status"] == "revoked"
    assert j["nombre"] == "Ana" and j["photo_url"]               # para que se lo reconozca
    alerta = [e for e in logs if e["event"] == "credencial.revocada_escaneada"]
    assert alerta and alerta[0]["log_level"] == "warning"
    assert token not in str(logs)
    assert "ip" not in alerta[0]
    # En el panel ya no figura como vigente.
    assert client.get(f"/admin/agents/{uid}/credential", headers=_h(admin_token)).json()["credential"] is None


def test_credencial_viva_de_alguien_desactivado_responde_inactive(client, repo, admin_token):
    uid = _agente_listo(client, admin_token)
    token = _emitir(client, admin_token, uid).json()["credential"]["token"]
    client.put(f"/admin/equipo/{uid}", headers=_h(admin_token),
               json={"email": "ana@uruku.bo", "activo": False, "roles": ["agente"]})
    j = client.get(f"/public/agents/{token}").json()
    assert j["status"] == "inactive" and set(j) == CLAVES_PUBLICAS
    assert repo.credenciales and next(iter(repo.credenciales.values()))["activo"] is True


# ───────────────────────────────────────── revocar

def test_revocar_pide_motivo_y_una_credencial_vigente(client, admin_token):
    uid = _agente_listo(client, admin_token)
    url = f"/admin/agents/{uid}/credential/revoke"
    _emitir(client, admin_token, uid)
    assert client.post(url, headers=_h(admin_token), json={}).status_code == 400
    assert client.post(url, headers=_h(admin_token), json={"reason": "   "}).status_code == 400
    assert client.post(url, headers=_h(admin_token), json={"reason": "motivo"}).status_code == 200
    # Ya no hay vigente: sin corte de acceso no hay qué revocar.
    r = client.post(url, headers=_h(admin_token), json={"reason": "otra vez"})
    assert r.status_code == 400 and "credencial" in r.json()["detail"].lower()
    assert client.post(f"/admin/agents/{_desconocido()}/credential/revoke", headers=_h(admin_token),
                       json={"reason": "x"}).status_code == 404


def test_revocar_guarda_quien_cuando_y_por_que(client, repo, admin_token):
    uid = _agente_listo(client, admin_token)
    _emitir(client, admin_token, uid)
    client.post(f"/admin/agents/{uid}/credential/revoke", headers=_h(admin_token), json={"reason": "Se perdió la tarjeta"})
    c = next(iter(repo.credenciales.values()))
    assert c["activo"] is False and c["revoke_reason"] == "Se perdió la tarjeta"
    assert c["revoked_by"] == "admin@bermejolive.com" and c["revoked_at"]
    assert repo.agentes[uid]["activo"] is True                       # sin cut_access no se toca la cuenta


# ───────────────────────────────────────── 4. corte de acceso

def _entrar_agente(client, email="ana@uruku.bo"):
    r = client.post("/auth/campo/login", json={"email": email, "password": PASS})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def test_revocar_con_corte_de_acceso_deja_al_agente_afuera_de_campo(client, repo, admin_token):
    uid = _agente_listo(client, admin_token)
    _emitir(client, admin_token, uid)
    t = _entrar_agente(client)
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 200      # y queda en el caché
    r = client.post(f"/admin/agents/{uid}/credential/revoke", headers=_h(admin_token),
                    json={"reason": "Robó plata", "cut_access": True})
    assert r.status_code == 200
    assert repo.agentes[uid]["activo"] is False
    r = client.get("/campo/mis-comercios", headers=_h(t))
    assert r.status_code == 401 and r.json()["detail"] == "Tu acceso fue dado de baja"
    # Y no puede volver a entrar.
    assert client.post("/auth/campo/login", json={"email": "ana@uruku.bo", "password": PASS}).status_code == 401


def test_cortar_el_acceso_sin_credencial_emitida_tambien_funciona(client, repo, admin_token):
    uid = _alta(client, admin_token)
    r = client.post(f"/admin/agents/{uid}/credential/revoke", headers=_h(admin_token),
                    json={"reason": "Baja", "cut_access": True})
    assert r.status_code == 200 and repo.agentes[uid]["activo"] is False


def test_el_corte_se_cachea_60_segundos_y_despues_se_aplica(client, repo, admin_token):
    """Si la cuenta se apaga por fuera de este proceso (otro worker, la base), el
    cambio se ve cuando vence el minuto de caché, no antes y no después."""
    uid = _alta(client, admin_token)
    t = _entrar_agente(client)
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 200
    repo.agentes[uid]["activo"] = False                  # directo en la base, sin pasar por la API
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 200      # caché vigente
    assert auth.ACCESO_TTL_SEGUNDOS == 60
    clave = "ana@uruku.bo"
    vence, valor = auth._acceso_cache[clave]
    assert valor["activo"] is True and "comercios.cargar" in valor["permisos"] and vence > 0
    auth._acceso_cache[clave] = (0.0, valor)            # venció
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 401


def test_desactivar_desde_equipo_corta_al_instante_en_este_proceso(client, admin_token):
    uid = _alta(client, admin_token)
    t = _entrar_agente(client)
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 200
    client.put(f"/admin/equipo/{uid}", headers=_h(admin_token),
               json={"email": "ana@uruku.bo", "activo": False, "roles": ["agente"]})
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 401


def test_la_cuenta_del_env_no_tiene_fila_y_pasa_con_aviso(client, agente_token):
    with structlog.testing.capture_logs() as logs:
        r = client.get("/campo/mis-comercios", headers=_h(agente_token))
    assert r.status_code == 200
    assert any(e["event"] == "auth.agente_sin_fila" for e in logs)
    # El segundo pedido sale del caché: no vuelve a avisar.
    with structlog.testing.capture_logs() as logs:
        assert client.get("/campo/mis-comercios", headers=_h(agente_token)).status_code == 200
    assert not any(e["event"] == "auth.agente_sin_fila" for e in logs)


def test_si_la_base_no_contesta_y_no_se_sabe_nada_el_agente_pasa_sin_cachear(client, repo, agente_token, monkeypatch):
    def falla(email):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "get_acceso_usuario_panel", falla)
    assert client.get("/campo/mis-comercios", headers=_h(agente_token)).status_code == 200
    assert "agente@bermejolive.com" not in auth._acceso_cache      # y no se cachea la falla


def test_stale_if_error_una_baja_conocida_no_se_reabre_por_una_caida(client, repo, admin_token, monkeypatch):
    uid = _alta(client, admin_token)
    t = _entrar_agente(client)
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 200
    repo.agentes[uid]["activo"] = False
    auth.reiniciar_cache_acceso()
    # El pedido siguiente se entera de la baja y la cachea...
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 401
    # ...vence el caché y la base se cae: se respeta la baja que ya se conocía.
    clave = "ana@uruku.bo"
    auth._acceso_cache[clave] = (0.0, auth._acceso_cache[clave][1])

    def falla(email):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "get_acceso_usuario_panel", falla)
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 401
    # Con un estado positivo conocido (o ninguno) la caída deja pasar.
    repo.agentes[uid]["activo"] = True
    auth._acceso_cache[clave] = (0.0, {"activo": True, "permisos": ["comercios.cargar"]})
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 200


def test_un_put_sin_activo_no_reactiva_a_quien_se_dio_de_baja(client, repo, admin_token):
    uid = _agente_listo(client, admin_token)
    _emitir(client, admin_token, uid)
    t = _entrar_agente(client)
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 200
    client.post(f"/admin/agents/{uid}/credential/revoke", headers=_h(admin_token),
                json={"reason": "baja", "cut_access": True})
    r = client.put(f"/admin/equipo/{uid}", headers=_h(admin_token),
                   json={"email": "ana@uruku.bo", "apellido": "Gómez", "roles": ["agente"]})
    assert r.status_code == 200 and r.json()["usuario"]["activo"] is False
    assert repo.agentes[uid]["activo"] is False
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 401
    # Y al crear sigue naciendo activo.
    assert repo.agentes[_alta(client, admin_token, email="nuevo@uruku.bo")]["activo"] is True


def test_sacarle_el_rol_de_agente_revoca_la_credencial_y_corta_campo(client, repo, admin_token):
    uid = _agente_listo(client, admin_token)
    token = _emitir(client, admin_token, uid).json()["credential"]["token"]
    t = _entrar_agente(client)
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 200
    r = client.put(f"/admin/equipo/{uid}", headers=_h(admin_token),
                   json={"email": "ana@uruku.bo", "roles": ["moderador"]})
    assert r.status_code == 200
    cred = next(iter(repo.credenciales.values()))
    assert cred["activo"] is False and cred["revoke_reason"] == "sin rol de agente"
    assert client.get(f"/public/agents/{token}").json()["status"] == "revoked"
    assert client.get("/public/agents").json() == {"items": []}
    # El JWT viejo todavía lleva el permiso de campo: el chequeo contra la base lo frena.
    r = client.get("/campo/mis-comercios", headers=_h(t))
    assert r.status_code == 401 and r.json()["detail"] == "Tu acceso fue dado de baja"


def test_si_el_rol_pierde_el_permiso_la_credencial_viva_dice_inactive_y_sale_de_la_lista(client, repo, admin_token):
    """Cambiar los permisos del ROL (no los de la persona) tampoco la deja figurando."""
    client.put("/admin/roles/cargador-sc", headers=_h(admin_token), json={
        "slug": "cargador-sc", "nombre": "Cargador", "permisos": ["comercios.cargar"]})
    uid = _agente_listo(client, admin_token, email="luis@uruku.bo", roles=["cargador-sc"])
    token = _emitir(client, admin_token, uid).json()["credential"]["token"]
    assert len(client.get("/public/agents").json()["items"]) == 1
    client.put("/admin/roles/cargador-sc", headers=_h(admin_token), json={
        "slug": "cargador-sc", "nombre": "Cargador", "permisos": ["lugares"]})
    assert client.get(f"/public/agents/{token}").json()["status"] == "inactive"
    assert client.get("/public/agents").json() == {"items": []}


def test_un_agente_con_token_viejo_pierde_campo_si_la_base_ya_no_le_da_el_permiso(client, repo, admin_token):
    uid = _alta(client, admin_token)
    t = _entrar_agente(client)
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 200
    repo.usuario_roles[uid] = ["moderador"]               # cambió en la base, no en el JWT
    auth.reiniciar_cache_acceso()
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 401


# ───────────────────────────────────────── el corte cubre todo el panel

def test_el_corte_de_acceso_cubre_todo_el_panel_no_solo_campo(client, repo, admin_token):
    uid = _alta(client, admin_token, email="moni@uruku.bo", roles=["moderador"])
    t = client.post("/auth/login", json={"email": "moni@uruku.bo", "password": PASS}).json()["access_token"]
    rutas = ["/moderacion/publicaciones?estado=pendiente",     # require_permiso / require_moderador
             "/admin/planes"]                                  # require_alguno
    for ruta in rutas:
        assert client.get(ruta, headers=_h(t)).status_code == 200, ruta
    client.put(f"/admin/equipo/{uid}", headers=_h(admin_token),
               json={"email": "moni@uruku.bo", "activo": False, "roles": ["moderador"]})
    for ruta in rutas:
        r = client.get(ruta, headers=_h(t))
        assert r.status_code == 401 and r.json()["detail"] == "Tu acceso fue dado de baja", ruta


def test_el_corte_de_require_panel_y_la_cuenta_del_env_que_sigue_pasando(client, repo, admin_token):
    uid = _alta(client, admin_token, email="moni@uruku.bo", roles=["moderador"])
    t = client.post("/auth/login", json={"email": "moni@uruku.bo", "password": PASS}).json()["access_token"]
    assert client.get("/admin/resumen", headers=_h(t)).status_code == 200
    repo.agentes[uid]["activo"] = False
    auth.reiniciar_cache_acceso()
    assert client.get("/admin/resumen", headers=_h(t)).status_code == 401
    # La cuenta del `.env` (sin fila) sigue entrando.
    assert client.get("/admin/resumen", headers=_h(admin_token)).status_code == 200


def test_sin_token_sigue_siendo_401_y_con_otro_permiso_403(client, admin_token):
    assert client.get("/campo/mis-comercios").status_code == 401
    _alta(client, admin_token, email="moni@uruku.bo", roles=["moderador"])
    t = client.post("/auth/login", json={"email": "moni@uruku.bo", "password": PASS}).json()["access_token"]
    assert client.get("/campo/mis-comercios", headers=_h(t)).status_code == 403


# ───────────────────────────────────────── 5. lista pública

def test_la_lista_publica_trae_solo_activos_con_credencial_vigente_y_foto(client, repo, admin_token):
    ok = _agente_listo(client, admin_token, email="ok@uruku.bo", nombre="Carlos", apellido="Soto")
    _emitir(client, admin_token, ok)
    # con credencial pero sin foto (se le sacó la foto después)
    sin_foto = _agente_listo(client, admin_token, email="sf@uruku.bo", nombre="Sin", apellido="Foto")
    _emitir(client, admin_token, sin_foto)
    repo.agentes[sin_foto]["photo_url"] = None
    # con foto pero sin credencial
    _agente_listo(client, admin_token, email="sc@uruku.bo", nombre="Sin", apellido="Credencial")
    # credencial revocada
    rev = _agente_listo(client, admin_token, email="rv@uruku.bo", nombre="Rev", apellido="Ocada")
    _emitir(client, admin_token, rev)
    client.post(f"/admin/agents/{rev}/credential/revoke", headers=_h(admin_token), json={"reason": "x"})
    # credencial viva pero usuario desactivado
    off = _agente_listo(client, admin_token, email="of@uruku.bo", nombre="Off", apellido="Linea")
    _emitir(client, admin_token, off)
    repo.agentes[off]["activo"] = False

    r = client.get("/public/agents")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=60"
    j = r.json()
    assert list(j) == ["items"]                                      # nunca un total
    assert len(j["items"]) == 1
    item = j["items"][0]
    assert set(item) == {"nombre", "apellido", "ciudad_nombre", "ciudad_slug", "photo_url", "desde"}
    assert (item["nombre"], item["apellido"], item["ciudad_nombre"], item["ciudad_slug"]) == (
        "Carlos", "Soto", "Bermejo", "bermejo")
    assert len(item["desde"]) == 10 and item["desde"][4] == "-"      # AAAA-MM-DD


def test_la_lista_publica_no_filtra_datos_privados_ni_tokens(client, repo, admin_token):
    uid = _agente_listo(client, admin_token)
    token = _emitir(client, admin_token, uid).json()["credential"]["token"]
    texto = client.get("/public/agents").text
    for prohibido in ("ana@uruku.bo", uid, token, "token", "roles", "permisos", "password", "email",
                      "telefono", "id\""):
        assert prohibido not in texto
    assert "total" not in texto and "count" not in texto


def test_la_lista_se_ordena_por_ciudad_apellido_y_nombre(client, admin_token):
    datos = [("a@uruku.bo", "Zoe", "Alvarez", "santa-cruz"), ("b@uruku.bo", "Beto", "Soto", "bermejo"),
             ("c@uruku.bo", "Ana", "Soto", "bermejo"), ("d@uruku.bo", "Luis", "Acosta", "bermejo")]
    for email, nom, ape, ciudad in datos:
        uid = _agente_listo(client, admin_token, email=email, nombre=nom, apellido=ape, ciudad=ciudad)
        _emitir(client, admin_token, uid)
    nombres = [(i["ciudad_nombre"], i["apellido"], i["nombre"]) for i in client.get("/public/agents").json()["items"]]
    assert nombres == [("Bermejo", "Acosta", "Luis"), ("Bermejo", "Soto", "Ana"),
                       ("Bermejo", "Soto", "Beto"), ("Santa Cruz", "Alvarez", "Zoe")]


def test_sin_agentes_la_lista_viene_vacia(client):
    r = client.get("/public/agents")
    assert r.status_code == 200 and r.json() == {"items": []}


# ───────────────────────────────────────── equipo: apellido y foto

def test_equipo_maneja_apellido_y_devuelve_la_foto_sin_hash(client, admin_token):
    uid = _alta(client, admin_token, nombre="Ana", apellido="  Pérez ")
    _foto(client, admin_token, uid)
    u = next(x for x in client.get("/admin/equipo", headers=_h(admin_token)).json()["usuarios"] if x["id"] == uid)
    assert u["apellido"] == "Pérez" and u["photo_url"]
    assert "password_hash" not in u
    r = client.put(f"/admin/equipo/{uid}", headers=_h(admin_token),
                   json={"email": "ana@uruku.bo", "apellido": "Gómez", "roles": ["agente"]})
    assert r.status_code == 200 and r.json()["usuario"]["apellido"] == "Gómez"
    assert "password_hash" not in r.json()["usuario"]
    # Editar sin mandar apellido no lo borra.
    client.put(f"/admin/equipo/{uid}", headers=_h(admin_token), json={"email": "ana@uruku.bo", "roles": ["agente"]})
    u = next(x for x in client.get("/admin/equipo", headers=_h(admin_token)).json()["usuarios"] if x["id"] == uid)
    assert u["apellido"] == "Gómez"


# ───────────────────────────────────────── sin limitador por IP

def test_los_get_publicos_de_agentes_no_tienen_tope_por_ip(client):
    """El backend sólo ve la IP del servidor de Next: un tope por IP sería global y
    cualquiera lo agotaría para tirar todas las verificaciones de QR."""
    assert all(client.get("/public/agents").status_code == 200 for _ in range(80))
    assert all(client.get("/public/agents/" + "a" * 22).status_code == 404 for _ in range(80))


# ───────────────────────────────────────── consentimiento

def test_sin_consentimiento_no_se_emite_la_credencial(client, repo, admin_token):
    uid = _agente_listo(client, admin_token)
    for cuerpo in ({}, {"consiente": False}):
        r = client.post(f"/admin/agents/{uid}/credential", headers=_h(admin_token), json=cuerpo)
        assert r.status_code == 400
        assert r.json()["detail"] == "Falta el consentimiento del agente para publicar su foto y su nombre"
    assert repo.credenciales == {} and not repo.agentes[uid].get("publicacion_consentida_at")
    # Sin cuerpo tampoco.
    assert client.post(f"/admin/agents/{uid}/credential", headers=_h(admin_token)).status_code == 400
    assert client.get(f"/admin/agents/{uid}/credential", headers=_h(admin_token)).json()["consentimiento_at"] is None


def test_con_consentimiento_se_guarda_y_la_reemision_no_lo_vuelve_a_pedir(client, repo, admin_token):
    uid = _agente_listo(client, admin_token)
    j = _emitir(client, admin_token, uid, consiente=True).json()
    assert j["consentimiento_at"] and repo.agentes[uid]["publicacion_consentida_at"] == j["consentimiento_at"]
    r = client.post(f"/admin/agents/{uid}/credential", headers=_h(admin_token), json={})
    assert r.status_code == 200 and r.json()["consentimiento_at"] == j["consentimiento_at"]
    assert client.get(f"/admin/agents/{uid}/credential", headers=_h(admin_token)).json()["consentimiento_at"] == j["consentimiento_at"]


def test_una_emision_que_falla_no_guarda_el_consentimiento(client, repo, admin_token):
    uid = _alta(client, admin_token)                         # sin foto: falla antes
    assert client.post(f"/admin/agents/{uid}/credential", headers=_h(admin_token), json={"consiente": True}).status_code == 400
    assert not repo.agentes[uid].get("publicacion_consentida_at")


def test_la_lista_publica_solo_trae_a_quien_consintio(client, repo, admin_token):
    uid = _agente_listo(client, admin_token)
    _emitir(client, admin_token, uid)
    assert len(client.get("/public/agents").json()["items"]) == 1
    repo.agentes[uid]["publicacion_consentida_at"] = None    # retiró el consentimiento
    assert client.get("/public/agents").json() == {"items": []}


def test_las_fotos_de_agentes_no_se_indexan(client):
    """El StaticFiles de main.py se montó con el fotos_dir del import: se escribe ahí y se limpia."""
    montaje = next(x for x in client.app.routes if getattr(x, "name", None) == "fotos")
    raiz = Path(montaje.app.directory)
    creados = [raiz / "agentes" / "prueba-robots.jpg", raiz / "com-x-robots" / "foto.jpg"]
    try:
        for f in creados:
            f.parent.mkdir(parents=True, exist_ok=True)
            f.write_bytes(bytes([0xFF, 0xD8, 0xFF]))
        r = client.get("/fotos/agentes/prueba-robots.jpg")
        assert r.status_code == 200 and r.headers["x-robots-tag"] == "noindex"
        # Las demás fotos no llevan la cabecera.
        assert "x-robots-tag" not in client.get("/fotos/com-x-robots/foto.jpg").headers
    finally:
        for f in creados:
            f.unlink(missing_ok=True)
        (raiz / "com-x-robots").rmdir()
        try:
            (raiz / "agentes").rmdir()
        except OSError:
            pass


# ───────────────────────────────────────── fechas y emisión concurrente

def test_desde_se_calcula_en_hora_de_la_paz():
    from app.api.agent_credentials import _fecha
    # 22:00 del 31/10 en La Paz ya es 1/11 en UTC: «Agente desde» tiene que decir octubre.
    assert _fecha("2026-11-01T02:00:00+00:00") == "2026-10-31"
    assert _fecha("2026-11-01T02:00:00Z") == "2026-10-31"
    assert _fecha("2026-10-30T15:02:37.123456+00:00") == "2026-10-30"
    assert _fecha(None) is None


def test_dos_emisiones_a_la_vez_dan_409(client, repo, admin_token, monkeypatch):
    from app.db.repository import CredencialDuplicada
    uid = _agente_listo(client, admin_token)

    def choca(*a, **k):
        raise CredencialDuplicada(uid)
    monkeypatch.setattr(repo, "emitir_credencial", choca)
    r = _emitir(client, admin_token, uid)
    assert r.status_code == 409
    assert r.json()["detail"] == "Otra persona acaba de emitir esta credencial. Recargá."
    assert not repo.agentes[uid].get("publicacion_consentida_at")


class _Consulta:
    """Un cliente de supabase mínimo para probar `SupabaseRepo.emitir_credencial`."""

    def __init__(self, tabla, falla_insert):
        self.t, self.falla, self.op, self.patch = tabla, falla_insert, None, None

    def update(self, patch):
        self.op, self.patch = "update", patch
        return self

    def insert(self, fila):
        self.op, self.patch = "insert", fila
        return self

    def eq(self, col, val):
        self.filtros = getattr(self, "filtros", []) + [(col, val)]
        return self

    def execute(self):
        class R:
            data = []
        r = R()
        if self.op == "insert":
            if self.falla:
                raise RuntimeError(self.falla)
            self.t.append({"id": "nueva", "activo": True, **self.patch})
            r.data = [self.t[-1]]
        else:
            filtros = dict(getattr(self, "filtros", []))
            for f in self.t:
                if all(f.get(c) == v for c, v in filtros.items() if c != "id") and \
                        ("id" not in filtros or f["id"] == filtros["id"]):
                    f.update(self.patch)
                    r.data.append(f)
        return r


class _Cliente:
    def __init__(self, falla_insert):
        self.filas = [{"id": "vieja", "usuario_id": "u1", "activo": True}]
        self.falla = falla_insert

    def table(self, nombre):
        assert nombre == "agent_credentials"
        return _Consulta(self.filas, self.falla)


def test_si_el_alta_falla_despues_de_revocar_se_reactiva_la_vigente():
    from app.db.repository import SupabaseRepo
    cli = _Cliente("conexión perdida")
    with structlog.testing.capture_logs() as logs:
        with pytest.raises(RuntimeError):
            SupabaseRepo(cli).emitir_credencial("u1", "t" * 22, "admin@x")
    assert cli.filas[0]["activo"] is True and cli.filas[0]["revoke_reason"] is None
    assert any(e["event"] == "credencial.emision_fallida_tras_revocar" for e in logs)


def test_el_indice_unico_se_traduce_a_credencial_duplicada():
    from app.db.repository import CredencialDuplicada, SupabaseRepo
    cli = _Cliente('duplicate key value violates unique constraint "uq_agent_credentials_vigente" (23505)')
    with pytest.raises(CredencialDuplicada):
        SupabaseRepo(cli).emitir_credencial("u1", "t" * 22, "admin@x")


# ───────────────────────────────────────── migración

def test_la_migracion_0163_esta_completa_y_espejada():
    raiz = Path(__file__).resolve().parents[2]
    sql = (raiz / "selfhost" / "postgres-init" / "0163_agent_credentials.sql").read_text(encoding="utf-8")
    assert (raiz / "supabase" / "migrations" / "0163_agent_credentials.sql").read_text(encoding="utf-8") == sql
    for pedazo in ("apellido  text", "photo_url text", "publicacion_consentida_at timestamptz", "length(token) >= 22", "token         text not null unique",
                   "enable row level security", "revoke all on public.agent_credentials",
                   "grant all on public.agent_credentials to service_role",
                   "on public.agent_credentials (usuario_id) where activo"):
        assert pedazo in sql
    assert "delete from" not in sql.lower() and "drop " not in sql.lower()


@pytest.mark.parametrize("ruta", ["/admin/agents/x/photo"])
def test_la_foto_tiene_tope_propio_en_el_middleware(ruta):
    from app.core.limite_cuerpo import TOPE_POR_DEFECTO, tope_para
    assert tope_para(ruta) > TOPE_POR_DEFECTO
