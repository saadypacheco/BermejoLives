"""Credencial de los agentes y página pública de agentes (docs/credencial-agentes.md).

Cubre los criterios de terminado §6 del lado del backend:
  1. token de 22+ caracteres; reemitir revoca la anterior; nunca dos vivas;
  2. las respuestas públicas no traen correo, ids, roles ni (en la lista) el token;
  3. token inexistente -> 404 con el mismo cuerpo siempre;
  4. revocar con corte de acceso -> 401 en /campo/* (con el caché de 60 s);
  5. la lista sólo muestra activos con credencial vigente y foto.
"""
from io import BytesIO
from pathlib import Path

import pytest
import structlog
from PIL import Image

from app.core import auth
from app.core.config import settings

NO_ES_DE_URUKU = {"detail": "Esta credencial no es de URUKU"}
PASS = "campo2026"


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _jpeg(ancho=2000, alto=1500, con_exif=True) -> bytes:
    img = Image.new("RGB", (ancho, alto), (200, 80, 40))
    kw = {}
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


def _emitir(client, admin_token, uid):
    return client.post(f"/admin/agents/{uid}/credential", headers=_h(admin_token), json={})


# ───────────────────────────────────────── 1. emisión, token, reemisión

def test_emitir_da_un_token_de_22_caracteres_y_la_forma_del_contrato(client, admin_token):
    uid = _agente_listo(client, admin_token)
    r = _emitir(client, admin_token, uid)
    assert r.status_code == 200, r.text
    j = r.json()
    assert set(j) == {"credential", "photo_url", "nombre", "apellido", "ciudad_nombre", "activo"}
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
    assert _emitir(client, admin_token, "no-existe").status_code == 404


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


# ───────────────────────────────────────── foto

def test_la_foto_se_recodifica_a_jpeg_de_800px_sin_exif(client, admin_token):
    uid = _alta(client, admin_token)
    r = _foto(client, admin_token, uid, _jpeg(2000, 1500))
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
    assert b"CamaraSecreta" not in archivo.read_bytes()


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
    assert _foto(client, admin_token, "no-existe").status_code == 404


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
    assert client.post("/admin/agents/no-existe/credential/revoke", headers=_h(admin_token),
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
    clave, (vence, valor) = next(iter(auth._acceso_cache.items()))
    assert clave == "ana@uruku.bo" and valor is True and vence > 0
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


def test_si_la_base_no_contesta_el_agente_no_se_queda_afuera(client, repo, agente_token, monkeypatch):
    def falla(email):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "is_usuario_panel_activo", falla, raising=False)
    assert client.get("/campo/mis-comercios", headers=_h(agente_token)).status_code == 200
    assert auth._acceso_cache == {}                       # y no se cachea la falla


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


# ───────────────────────────────────────── limitador

def test_los_get_publicos_de_agentes_se_limitan_a_30_por_minuto_por_ip(client):
    assert all(client.get("/public/agents").status_code == 200 for _ in range(30))
    r = client.get("/public/agents")
    assert r.status_code == 429
    # Comparten tope la lista y la verificación; otra ruta pública no se toca.
    assert client.get("/public/agents/" + "a" * 22).status_code == 429
    assert client.get("/health").status_code == 200


def test_el_limite_de_agentes_no_depende_de_la_ip_de_otro(client):
    for _ in range(30):
        client.get("/public/agents")
    assert client.get("/public/agents", headers={"X-Forwarded-For": "9.9.9.9"}).status_code == 200


# ───────────────────────────────────────── migración

def test_la_migracion_0163_esta_completa_y_espejada():
    raiz = Path(__file__).resolve().parents[2]
    sql = (raiz / "selfhost" / "postgres-init" / "0163_agent_credentials.sql").read_text(encoding="utf-8")
    assert (raiz / "supabase" / "migrations" / "0163_agent_credentials.sql").read_text(encoding="utf-8") == sql
    for pedazo in ("apellido  text", "photo_url text", "length(token) >= 22", "token         text not null unique",
                   "enable row level security", "revoke all on public.agent_credentials",
                   "grant all on public.agent_credentials to service_role",
                   "on public.agent_credentials (usuario_id) where activo"):
        assert pedazo in sql
    assert "delete from" not in sql.lower() and "drop " not in sql.lower()


@pytest.mark.parametrize("ruta", ["/admin/agents/x/photo"])
def test_la_foto_tiene_tope_propio_en_el_middleware(ruta):
    from app.core.limite_cuerpo import TOPE_POR_DEFECTO, tope_para
    assert tope_para(ruta) > TOPE_POR_DEFECTO
