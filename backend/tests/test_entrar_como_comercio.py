"""Un admin entra a «Mi comercio» de cualquier comercio (`POST /admin/comercios/{id}/entrar`).

Lo que se prueba:
  - El permiso `equipo` se mira HOY en la base (no el que trae el JWT); 404 si el comercio no existe o está de baja.
  - El token (30 min, claim `adm`) pasa las dependencias de Mi comercio SIN cuenta del dueño y sin mirar la
    versión de su clave; pero se corta si al admin lo dan de baja o pierde `equipo`.
  - Lo que cambia quién controla la cuenta o la plata contesta 403 «No disponible entrando como admin», y la
    lista de esas rutas está FIJADA acá: una ruta nueva de Mi comercio no puede quedar sin clasificar.
  - Auditoría (`comercio_eventos` + log sin token), `por_admin` en el perfil, autor = el admin, y nada de lo que
    hace un admin cuenta como actividad del dueño.
"""
import copy
import time
import uuid
from datetime import datetime, timezone

import pytest
import structlog
from fastapi.routing import APIRoute
from structlog.testing import capture_logs

from app.core import auth
from app.core.sesion_comercio import MSG_NO_COMO_ADMIN
from app.main import app

ID_COMERCIO = "7d1e2f30-4a5b-4c6d-8e7f-9a0b1c2d3e4f"
CLAVE_PANEL = "claveDelPanel123"


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _comercio(repo, **kw):
    return repo.seed_comercio(**{"id": ID_COMERCIO, "slug": "boutique", "nombre": "Boutique Lucía",
                                 "whatsapp": "59170123456", "activo": True, **kw})


def _admin_con_fila(repo, email="jefa@uruku.bo", roles=("admin",), activo=True):
    """Alguien del equipo CON fila en `usuarios_panel` (la cuenta del `.env` no tiene: nunca se corta)."""
    repo.crear_usuario_panel({"email": email, "nombre": "Jefa", "activo": activo, "password_hash": "x"}, list(roles))
    return auth.make_token(email, roles=list(roles))


@pytest.fixture
def admin_token(repo):
    """El admin de estos tests: tiene FILA en el panel (las cuentas del `.env` no pueden entrar: ver
    `test_la_cuenta_de_emergencia_del_env_no_entra`)."""
    return _admin_con_fila(repo, "admin@bermejolive.com")


def _entrar(client, token, comercio_id=ID_COMERCIO, **kw):
    return client.post(f"/admin/comercios/{comercio_id}/entrar", headers=_h(token), **kw)


def _token_adm(client, token, comercio_id=ID_COMERCIO):
    r = _entrar(client, token, comercio_id)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


# ═════════════════════════════════════════════════════════ el endpoint
def test_entrar_devuelve_el_contrato(client, repo, admin_token):
    _comercio(repo)
    r = _entrar(client, admin_token, json={"motivo": "Revisar la ficha"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert set(d) == {"access_token", "comercio", "expira_en", "por_admin"}
    assert d["comercio"] == {"id": ID_COMERCIO, "nombre": "Boutique Lucía", "slug": "boutique"}
    assert d["por_admin"] == "admin@bermejolive.com"
    expira = datetime.fromisoformat(d["expira_en"])
    assert expira.tzinfo is not None
    assert 29 * 60 <= (expira - datetime.now(timezone.utc)).total_seconds() <= 30 * 60 + 5


def test_el_token_es_de_comercio_con_adm_y_dura_30_minutos(client, repo, admin_token):
    _comercio(repo)
    claims = auth._decode(_token_adm(client, admin_token))
    assert claims["rol"] == "comercio" and claims["comercio_id"] == ID_COMERCIO
    assert claims["adm"] == "admin@bermejolive.com"
    assert "cuenta_id" not in claims and "ver" not in claims      # no depende de la cuenta ni de la clave del dueño
    assert 29 * 60 <= claims["exp"] - int(time.time()) <= 30 * 60 + 5


def test_el_motivo_es_opcional_y_tiene_tope(client, repo, admin_token):
    _comercio(repo)
    assert _entrar(client, admin_token).status_code == 200                       # sin body
    assert _entrar(client, admin_token, json={}).status_code == 200
    assert _entrar(client, admin_token, json={"motivo": "x" * 201}).status_code == 422
    assert _entrar(client, admin_token, json={"motivo": "x" * 200}).status_code == 200


def test_sin_token_401_y_sin_equipo_403(client, repo, admin_token):
    _comercio(repo)
    assert client.post(f"/admin/comercios/{ID_COMERCIO}/entrar").status_code == 401
    moderador = _admin_con_fila(repo, "moni@uruku.bo", roles=("moderador",))
    assert _entrar(client, moderador).status_code == 403
    assert _entrar(client, auth.make_comercio_token(ID_COMERCIO, "x@y.com")).status_code == 403
    assert _entrar(client, auth.make_agente_token("agente@uruku.bo")).status_code == 403
    assert repo.comercio_eventos == []                                           # ninguno dejó rastro de entrada


def test_el_permiso_se_mira_hoy_en_la_base_no_en_el_jwt(client, repo):
    _comercio(repo)
    token = _admin_con_fila(repo)                                                # el JWT dice admin
    assert _entrar(client, token).status_code == 200
    repo.usuario_roles[next(iter(repo.agentes))] = ["moderador"]                 # en la base ya no
    auth.reiniciar_cache_acceso()
    assert _entrar(client, token).status_code == 403


def test_un_admin_dado_de_baja_no_entra(client, repo):
    _comercio(repo)
    token = _admin_con_fila(repo)
    repo.agentes[next(iter(repo.agentes))]["activo"] = False
    auth.reiniciar_cache_acceso()
    assert _entrar(client, token).status_code == 401


def test_comercio_inexistente_o_dado_de_baja_404(client, repo, admin_token):
    _comercio(repo, activo=False)
    r = _entrar(client, admin_token)
    assert r.status_code == 404 and r.json()["detail"] == "Comercio no encontrado"
    assert _entrar(client, admin_token, str(uuid.uuid4())).status_code == 404
    assert _entrar(client, admin_token, "no-es-un-uuid").status_code == 404
    assert repo.comercio_eventos == []


# ═════════════════════════════════════════════════════════ el token en Mi comercio
def test_sirve_aunque_el_comercio_no_tenga_cuenta(client, repo, admin_token):
    _comercio(repo)
    assert repo.usuarios == {}                                                   # sin comercio_usuarios
    t = _token_adm(client, admin_token)
    for ruta in ("/comercio/perfil", "/comercio/mis-publicaciones", "/comercio/fotos", "/comercio/suscripcion",
                 "/comercio/mensajes", "/comercio/asistente/preguntas"):
        assert client.get(ruta, headers=_h(t)).status_code == 200, ruta
    assert repo.usuarios == {}                                                   # y no le creó una


def test_no_depende_de_la_version_de_la_clave_del_dueno(client, repo, admin_token):
    c = _comercio(repo)
    cuenta = repo.crear_comercio_usuario({"comercio_id": c["id"], "nombre": c["nombre"]})
    cuenta["credenciales_version"] = 7
    # Un token común del dueño con `ver` viejo se corta; el del admin no se compara con la cuenta.
    viejo = auth.make_comercio_token(c["id"], "x@y.com", cuenta["id"], 1)
    assert client.get("/comercio/perfil", headers=_h(viejo)).status_code == 401
    t = _token_adm(client, admin_token)
    assert client.get("/comercio/perfil", headers=_h(t)).status_code == 200
    cuenta["credenciales_version"] = 8                                           # el dueño cambia la clave: sigue
    assert client.get("/comercio/perfil", headers=_h(t)).status_code == 200


def test_el_token_vencido_da_401(client, repo, admin_token):
    _comercio(repo)
    vencido, _ = auth.make_comercio_admin_token(ID_COMERCIO, "admin@bermejolive.com", "evt-1", ttl_segundos=-5)
    assert client.get("/comercio/perfil", headers=_h(vencido)).status_code == 401


def test_el_token_se_corta_si_al_admin_lo_dan_de_baja(client, repo):
    _comercio(repo)
    t = _token_adm(client, _admin_con_fila(repo))
    assert client.get("/comercio/perfil", headers=_h(t)).status_code == 200
    repo.agentes[next(iter(repo.agentes))]["activo"] = False
    auth.reiniciar_cache_acceso()
    r = client.get("/comercio/perfil", headers=_h(t))
    assert r.status_code == 401
    assert client.put("/comercio/perfil", headers=_h(t), json={"descripcion": "x"}).status_code == 401


def test_el_token_se_corta_si_el_admin_pierde_equipo(client, repo):
    _comercio(repo)
    t = _token_adm(client, _admin_con_fila(repo))
    repo.usuario_roles[next(iter(repo.agentes))] = ["moderador"]
    auth.reiniciar_cache_acceso()
    r = client.get("/comercio/mis-publicaciones", headers=_h(t))
    assert r.status_code == 401 and r.json()["detail"] == auth.MSG_ENTRADA_ADMIN_CORTADA


def test_un_adm_vacio_o_falsificado_no_sirve(client, repo):
    _comercio(repo)
    import jwt as pyjwt
    from app.core.config import settings
    for adm in ("", None, "  "):
        t = pyjwt.encode({"sub": "x", "email": "x", "rol": "comercio", "comercio_id": ID_COMERCIO, "adm": adm,
                          "exp": int(time.time()) + 600}, settings.jwt_secret, algorithm="HS256")
        assert client.get("/comercio/perfil", headers=_h(t)).status_code == 401, repr(adm)


def test_el_token_de_adm_no_sirve_en_el_panel(client, repo, admin_token):
    _comercio(repo)
    t = _token_adm(client, admin_token)
    assert client.get("/moderacion/publicaciones?estado=pendiente", headers=_h(t)).status_code == 403
    assert client.post(f"/admin/comercios/{ID_COMERCIO}/entrar", headers=_h(t)).status_code == 403


# ═════════════════════════════════════════════════════════ perfil
def test_el_perfil_trae_por_admin_solo_si_entro_un_admin(client, repo, admin_token):
    _comercio(repo)
    t = _token_adm(client, admin_token)
    assert client.get("/comercio/perfil", headers=_h(t)).json()["por_admin"] == "admin@bermejolive.com"
    normal = client.get("/comercio/perfil", headers=_h(auth.make_comercio_token(ID_COMERCIO, "x@y.com")))
    assert normal.status_code == 200 and "por_admin" not in normal.json()


# ═════════════════════════════════════════════════════════ lo que NO se puede hacer como admin
def _form_pago():
    return {"data": {"monto": "100", "moneda": "ARS", "metodo": "transferencia"}}


#: (método, ruta, kwargs) de CADA ruta con el guarda. Ver `test_cada_ruta_de_mi_comercio_esta_clasificada`.
BLOQUEADAS = {
    ("POST", "/comercio/clave"): {},
    ("POST", "/comercio/pago"): _form_pago(),
    ("POST", "/comercio/productos/{ref_id}/destacar"): {},
    ("POST", "/comercio/mensajes/{mensaje_id}/leido"): {},
    ("PUT", "/comercio/social-consent"): {"json": {"granted": True}},
}

#: Rutas de Mi comercio que SÍ sirven con el token de un admin que entró.
PERMITIDAS = {
    ("GET", "/comercio/mis-publicaciones"), ("PATCH", "/comercio/publicaciones/{pub_id}"),
    ("DELETE", "/comercio/publicaciones/{pub_id}"), ("GET", "/comercio/perfil"), ("PUT", "/comercio/perfil"),
    ("POST", "/comercio/catalogo"), ("DELETE", "/comercio/catalogo"), ("PUT", "/comercio/perfil/foto"),
    ("GET", "/comercio/suscripcion"), ("GET", "/comercio/metricas"), ("POST", "/comercio/publicar"),
    ("POST", "/comercio/productos/draft"), ("GET", "/comercio/productos"), ("POST", "/comercio/productos"),
    ("DELETE", "/comercio/productos/{ref_id}"), ("GET", "/comercio/mensajes"),
    ("GET", "/comercio/fotos"), ("POST", "/comercio/fotos"), ("PUT", "/comercio/portada"),
    ("DELETE", "/comercio/fotos/{foto_id}"), ("GET", "/comercio/videos"), ("POST", "/comercio/videos"),
    ("DELETE", "/comercio/videos/{video_id}"), ("GET", "/comercio/social-consent"),
    ("GET", "/comercio/asistente/preguntas"), ("GET", "/comercio/asistente/respuestas"),
    ("POST", "/comercio/asistente/respuestas"), ("PUT", "/comercio/asistente/respuestas/{respuesta_id}"),
    ("DELETE", "/comercio/asistente/respuestas/{respuesta_id}"),
    ("POST", "/comercio/entrada/salir"),
}


def _llamadas(dependant):
    """Todas las funciones de dependencia de una ruta, hijas incluidas."""
    for d in dependant.dependencies:
        yield d.call
        yield from _llamadas(d)


def _todas_las_rutas(rutas):
    """Las `APIRoute` de la app, entrando en los routers incluidos (FastAPI los anida como `_IncludedRouter`).
    Los routers de Mi comercio se incluyen sin prefijo, así que el `path` es el real."""
    for r in rutas:
        if isinstance(r, APIRoute):
            yield r
        elif hasattr(r, "original_router"):
            yield from _todas_las_rutas(r.original_router.routes)


def _rutas_de_mi_comercio(rutas=None):
    """{(método, ruta): ¿lleva el guarda `_comercio_dueno`?} de TODA ruta que usa la sesión de Mi comercio:
    la que pasa por `auth.require_comercio` (directo o por `require_comercio_vigente`, que lo trae adentro)."""
    from app.api.comercio import _comercio_dueno
    out = {}
    for r in _todas_las_rutas(rutas if rutas is not None else app.routes):
        llamadas = set(_llamadas(r.dependant))
        if auth.require_comercio not in llamadas:
            continue
        for metodo in r.methods - {"HEAD", "OPTIONS"}:
            out[(metodo, r.path)] = _comercio_dueno in llamadas
    return out


def test_cada_ruta_de_mi_comercio_esta_clasificada():
    """Si agregás una ruta con la sesión de Mi comercio, este test falla hasta que decidas: ¿la puede hacer un
    admin que entró (PERMITIDAS) o cambia quién controla la cuenta / mueve plata (BLOQUEADAS, con `_comercio_dueno`)?"""
    rutas = _rutas_de_mi_comercio()
    guardadas = {k for k, v in rutas.items() if v}
    sin_guarda = {k for k, v in rutas.items() if not v}
    assert guardadas == set(BLOQUEADAS), "las rutas con el guarda cambiaron: actualizá BLOQUEADAS a propósito"
    assert sin_guarda == PERMITIDAS, (
        f"ruta nueva de Mi comercio sin clasificar: {sorted(sin_guarda - PERMITIDAS)}; "
        f"o ruta que ya no existe: {sorted(PERMITIDAS - sin_guarda)}")


@pytest.mark.parametrize("metodo,ruta", sorted(BLOQUEADAS))
def test_las_acciones_del_dueno_contestan_403_con_el_token_del_admin(client, repo, admin_token, metodo, ruta):
    _comercio(repo)
    t = _token_adm(client, admin_token)
    url = ruta.replace("{ref_id}", "r1").replace("{mensaje_id}", "m1")
    r = client.request(metodo, url, headers=_h(t), **BLOQUEADAS[(metodo, ruta)])
    assert r.status_code == 403, r.text
    assert r.json()["detail"] == MSG_NO_COMO_ADMIN == "No disponible entrando como admin"


def test_el_bloqueo_no_toca_nada(client, repo, admin_token):
    c = _comercio(repo)
    cuenta = repo.crear_comercio_usuario({"comercio_id": c["id"], "nombre": c["nombre"]})
    cuenta["credenciales_version"] = 3
    t = _token_adm(client, admin_token)
    assert client.post("/comercio/clave", headers=_h(t)).status_code == 403
    assert client.post("/comercio/pago", headers=_h(t), **_form_pago()).status_code == 403
    assert cuenta["credenciales_version"] == 3 and not cuenta.get("clave_hash")
    assert repo.pagos == {}


def test_las_mismas_acciones_siguen_andando_para_el_dueno(client, repo):
    c = _comercio(repo)
    cuenta = repo.crear_comercio_usuario({"comercio_id": c["id"], "nombre": c["nombre"]})
    dueno = auth.make_comercio_token(c["id"], "x@y.com", cuenta["id"], 0)
    assert client.put("/comercio/social-consent", headers=_h(dueno), json={"granted": True}).status_code == 200
    assert client.post("/comercio/clave", headers=_h(dueno)).status_code == 200      # (sube la versión de la clave)


def test_publicar_pasandose_del_tope_cobra_al_dueno_pero_nunca_al_admin(client, repo, admin_token):
    """Regla del dueño (7/11): lo del equipo no gasta el plan. Con el tope lleno el admin publica igual, sin
    cargo; el dueño en la misma situación sí genera el cargo de siempre."""
    c = _comercio(repo, plan="publica")
    hoy = datetime.now(timezone.utc).isoformat()
    for i in range(25):
        repo.insert_publicacion_directa({"comercio_id": c["id"], "tipo": "oferta", "titulo": f"of {i}",
                                         "estado": "aprobado", "created_at": hoy})
    t = _token_adm(client, admin_token)
    r = client.post("/comercio/publicar", headers=_h(t), json={"tipo": "oferta", "titulo": "Una más"})
    assert r.status_code == 200, r.text
    assert r.json()["aviso"] is None
    assert repo.cargos_extra == []                                                # no se cobró nada
    assert next(p for p in repo.publicaciones if p["titulo"] == "Una más")["identidad_origen"] == "admin"
    dueno = auth.make_comercio_token(c["id"], "x@y.com")
    assert client.post("/comercio/publicar", headers=_h(dueno),
                       json={"tipo": "oferta", "titulo": "Del dueño"}).status_code == 200
    assert len(repo.cargos_extra) == 1                                            # el del dueño sí cobra


# ═════════════════════════════════════════════════════════ lo que SÍ se puede
def test_editar_perfil_y_publicar_andan_como_admin(client, repo, admin_token):
    _comercio(repo)
    t = _token_adm(client, admin_token)
    r = client.put("/comercio/perfil", headers=_h(t), json={"descripcion": "Ropa de mujer"})
    assert r.status_code == 200 and r.json()["descripcion"] == "Ropa de mujer"
    assert repo.comercios[ID_COMERCIO]["descripcion"] == "Ropa de mujer"
    r = client.post("/comercio/publicar", headers=_h(t), json={"tipo": "oferta", "titulo": "Liquidación"})
    assert r.status_code == 200, r.text
    assert any(p.get("titulo") == "Liquidación" and p["comercio_id"] == ID_COMERCIO for p in repo.publicaciones)


def test_lo_que_carga_un_admin_queda_a_su_nombre(client, repo, admin_token):
    _comercio(repo)
    t = _token_adm(client, admin_token)
    r = client.post("/comercio/productos", headers=_h(t),
                    data={"titulo": "Remera", "precio": "120", "moneda": "ARS", "categoria_slug": "ropa"})
    assert r.status_code == 200, r.text
    ref = next(iter(repo.producto_refs.values()))
    assert ref["cargado_por"] == "admin@bermejolive.com"
    r = client.post("/comercio/asistente/respuestas", headers=_h(t),
                    json={"pregunta": "¿Hacen envíos?", "respuesta": "Sí, a todo el país"})
    assert r.status_code == 200, r.text
    assert any(s.get("creado_por") == "admin:admin@bermejolive.com" for s in repo.saber_local.values())
    # El dueño sigue quedando como siempre.
    dueno = auth.make_comercio_token(ID_COMERCIO, "dueno@y.com")
    client.post("/comercio/productos", headers=_h(dueno),
                data={"titulo": "Otra", "precio": "1", "moneda": "ARS", "categoria_slug": "ropa"})
    assert [x["cargado_por"] for x in repo.producto_refs.values()] == ["admin@bermejolive.com", "dueno@y.com"]


# ═════════════════════════════════════════════════════════ auditoría
def test_cada_entrada_queda_en_comercio_eventos_y_en_el_log(client, repo, admin_token):
    _comercio(repo)
    with capture_logs() as logs:
        r = _entrar(client, admin_token, json={"motivo": "  Ayuda con las fotos  "})
    assert r.status_code == 200
    (evento,) = repo.comercio_eventos
    assert evento["comercio_id"] == ID_COMERCIO and evento["tipo"] == "entro_como_comercio"
    assert evento["actor"] == "admin@bermejolive.com"
    assert evento["detalle"]["motivo"] == "Ayuda con las fotos"
    entradas = [e for e in logs if e["event"] == "admin.entro_como_comercio"]
    assert len(entradas) == 1
    assert entradas[0]["admin"] == "admin@bermejolive.com" and entradas[0]["comercio_id"] == ID_COMERCIO
    assert entradas[0]["motivo"] == "Ayuda con las fotos"
    token = r.json()["access_token"]
    assert token not in repr(logs) and token not in repr(repo.comercio_eventos)   # el token nunca se registra
    _entrar(client, admin_token)
    assert len(repo.comercio_eventos) == 2 and repo.comercio_eventos[1]["detalle"]["motivo"] is None


def test_sin_poder_auditar_no_se_entra(client, repo, admin_token):
    _comercio(repo)
    repo.falla_auditoria = True
    r = _entrar(client, admin_token)
    assert r.status_code == 503 and "access_token" not in r.json()
    assert repo.comercio_eventos == []


def test_las_acciones_del_admin_quedan_en_el_log_con_por_admin(client, repo, admin_token):
    _comercio(repo)
    t = _token_adm(client, admin_token)
    with capture_logs() as logs:
        client.put("/comercio/perfil", headers=_h(t), json={"descripcion": "Nueva"})
        client.post("/comercio/clave", headers=_h(t))
    assert [e for e in logs if e["event"] == "comercio.perfil_update"][0]["por_admin"] == "admin@bermejolive.com"
    assert any(e["event"] == "comercio.accion_bloqueada_como_admin" for e in logs)


# ═════════════════════════════════════════════════════════ medición
def test_un_admin_adentro_no_cuenta_como_actividad_del_dueno(client, repo, admin_token):
    c = _comercio(repo)
    cuenta = repo.crear_comercio_usuario({"comercio_id": c["id"], "nombre": c["nombre"]})
    antes = copy.deepcopy((repo.usuarios, repo.comercios))
    t = _token_adm(client, admin_token)
    for ruta in ("/comercio/perfil", "/comercio/mis-publicaciones", "/comercio/metricas", "/comercio/suscripcion"):
        assert client.get(ruta, headers=_h(t)).status_code == 200, ruta
    assert (repo.usuarios, repo.comercios) == antes                  # ni cuenta ni comercio se tocaron
    assert "ultimo_acceso" not in cuenta and "ultimo_acceso" not in repo.comercios[ID_COMERCIO]
