"""«Entrar como este comercio»: lo que pidió la revisión de seguridad y las reglas del dueño (7/11/2026).

  1. Con el token de un admin nada que cueste plata le llega al comercio (foto extra, publicación extra, pago, destacado).
  2. Atribución: el token lleva `jti` = id del evento `entro_como_comercio`; TODA escritura hecha con él se registra
     (`por_admin` + `jti`); lo que publica queda con `identidad_origen = 'admin'`; catálogo: `actor` = el correo del admin.
  3. Lo que publica el equipo NO gasta el plan del comercio (cuota mensual, cobro extra, tope de guardadas).
  4. El aviso al dueño en su bandeja (sin el correo del admin y sin WhatsApp).
  5. Las cuentas de emergencia del `.env` no pueden entrar; la respuesta no se guarda en caché.
  6. Salida del lado del servidor (`POST /comercio/entrada/salir`) e historial (`GET /admin/comercios/{id}/entradas`).
  7. La prueba que clasifica las rutas de Mi comercio también ve las que usan `auth.require_comercio` directo.
"""
import re
import time
from datetime import datetime, timedelta, timezone
from io import BytesIO

import pytest
from fastapi import APIRouter, Depends, FastAPI
from PIL import Image
from structlog.testing import capture_logs

from app.core import auth
from app.core.config import settings
from app.core.sesion_comercio import MSG_NO_COMO_ADMIN
from app.services import planes
from tests.test_entrar_como_comercio import (
    ID_COMERCIO, _admin_con_fila, _comercio, _entrar, _h, _rutas_de_mi_comercio, _token_adm,
)

ADMIN = "admin@bermejolive.com"
BASE = "https://api.test/fotos"


@pytest.fixture
def admin_token(repo):
    return _admin_con_fila(repo, ADMIN)


@pytest.fixture(autouse=True)
def _entradas_cerradas_limpias(monkeypatch):
    """La lista de entradas cerradas es de memoria del proceso: cada test arranca sin ninguna."""
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)
    auth.reiniciar_entradas_revocadas()
    yield
    auth.reiniciar_entradas_revocadas()


def _foto():
    buf = BytesIO()
    Image.new("RGB", (10, 10), "green").save(buf, format="JPEG")
    buf.seek(0)
    return {"foto": ("f.jpg", buf, "image/jpeg")}


def _sembrar_fotos(repo, cid, n):
    for i in range(n):
        repo.comercio_fotos.append({"id": f"f{i}", "comercio_id": cid, "url": f"{BASE}/boutique/s{i}.jpg",
                                    "thumb_url": f"{BASE}/boutique/s{i}_t3.jpg", "orden": i,
                                    "created_at": f"2026-01-01T00:{i // 60:02d}:{i % 60:02d}+00:00"})


# ═══════════════════════════════════════════════ 1. nada que cueste plata le llega al comercio
@pytest.mark.parametrize("extra", ["pagar", "PAGAR", "  pagar "])
def test_foto_extra_pagar_con_el_token_del_admin_es_403_y_no_cobra(client, repo, admin_token, extra):
    c = _comercio(repo)
    _sembrar_fotos(repo, c["id"], 50)                       # el tope del plan gratis
    t = _token_adm(client, admin_token)
    r = client.post("/comercio/fotos", headers=_h(t), files=_foto(), data={"extra": extra})
    assert r.status_code == 403 and r.json()["detail"] == MSG_NO_COMO_ADMIN
    assert repo.cargos_extra == []
    assert len(repo.list_fotos_comercio(c["id"])) == 50
    assert not repo.comercios[c["id"]].get("fotos_extra")


def test_foto_extra_pagar_403_tambien_bajo_el_tope(client, repo, admin_token):
    c = _comercio(repo)
    t = _token_adm(client, admin_token)
    r = client.post("/comercio/fotos", headers=_h(t), files=_foto(), data={"extra": "pagar"})
    assert r.status_code == 403 and repo.cargos_extra == [] and repo.list_fotos_comercio(c["id"]) == []


def test_el_admin_sube_fotos_dentro_del_tope_y_en_el_tope_recibe_el_409_sin_pagar(client, repo, admin_token):
    c = _comercio(repo)
    _sembrar_fotos(repo, c["id"], 49)
    t = _token_adm(client, admin_token)
    assert client.post("/comercio/fotos", headers=_h(t), files=_foto()).status_code == 200
    r = client.post("/comercio/fotos", headers=_h(t), files=_foto())
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["codigo"] == "tope_fotos" and d["limite"] == 50 and d["puede_pagar"] is False
    assert repo.cargos_extra == [] and len(repo.list_fotos_comercio(c["id"])) == 50


def test_el_admin_puede_reemplazar_una_foto_en_el_tope(client, repo, admin_token):
    c = _comercio(repo)
    _sembrar_fotos(repo, c["id"], 50)
    t = _token_adm(client, admin_token)
    r = client.post("/comercio/fotos", headers=_h(t), files=_foto(), data={"reemplazar": "f0"})
    assert r.status_code == 200 and repo.cargos_extra == []
    assert len(repo.list_fotos_comercio(c["id"])) == 50


def test_el_dueno_en_el_tope_sigue_pudiendo_pagar_la_foto_extra(client, repo):
    c = _comercio(repo)
    _sembrar_fotos(repo, c["id"], 50)
    dueno = auth.make_comercio_token(c["id"], "x@y.com")
    r = client.post("/comercio/fotos", headers=_h(dueno), files=_foto(), data={"extra": "pagar"})
    assert r.status_code == 200 and len(repo.cargos_extra) == 1
    sin = client.post("/comercio/fotos", headers=_h(dueno), files=_foto())
    assert sin.status_code == 409 and "puede_pagar" not in sin.json()["detail"]        # el 409 del dueño no cambia


def test_con_el_token_del_admin_no_se_genera_ningun_cargo_ni_pago(client, repo, admin_token):
    """Recorre TODO lo que desde Mi comercio puede terminar en plata y confirma que con `adm` no llega."""
    c = _comercio(repo, plan="publica")
    hoy = datetime.now(timezone.utc).isoformat()
    for i in range(25):                                                       # el tope mensual lleno
        repo.insert_publicacion_directa({"comercio_id": c["id"], "tipo": "oferta", "titulo": f"of {i}",
                                         "estado": "aprobado", "created_at": hoy})
    ref = repo.crear_producto_ref({"comercio_id": c["id"], "titulo": "Remera", "precio": 1, "moneda": "ARS"})
    _sembrar_fotos(repo, c["id"], 100)
    t = _token_adm(client, admin_token)
    intentos = [
        client.post("/comercio/publicar", headers=_h(t), json={"tipo": "oferta", "titulo": "Otra"}),
        client.post("/comercio/fotos", headers=_h(t), files=_foto(), data={"extra": "pagar"}),
        client.post("/comercio/pago", headers=_h(t), data={"monto": "100", "moneda": "ARS", "metodo": "transferencia"}),
        client.post(f"/comercio/productos/{ref['id']}/destacar", headers=_h(t)),
    ]
    assert [r.status_code for r in intentos] == [200, 403, 403, 403]          # publicar sí (sin cargo): ver la regla 3
    assert repo.cargos_extra == [] and repo.pagos == {}
    assert not repo.comercios[c["id"]].get("fotos_extra")
    assert not any(p.get("costo") for p in repo.publicaciones)


# ═══════════════════════════════════════════════ 2. atribución
def test_el_jti_es_el_id_del_evento_de_auditoria(client, repo, admin_token):
    _comercio(repo)
    t = _token_adm(client, admin_token)
    claims = auth._decode(t)
    (evento,) = repo.comercio_eventos
    assert claims["jti"] == evento["id"] and evento["tipo"] == "entro_como_comercio"
    t2 = _token_adm(client, admin_token)
    assert auth._decode(t2)["jti"] == repo.comercio_eventos[1]["id"] != claims["jti"]


def test_un_token_de_admin_sin_jti_no_sirve(client, repo, admin_token):
    import jwt as pyjwt
    _comercio(repo)
    sin_jti = pyjwt.encode({"sub": ADMIN, "email": ADMIN, "rol": "comercio", "comercio_id": ID_COMERCIO, "adm": ADMIN,
                            "exp": int(time.time()) + 600}, settings.jwt_secret, algorithm="HS256")
    assert client.get("/comercio/perfil", headers=_h(sin_jti)).status_code == 401


def _escrituras(ref_id, pub_id, foto_id, video_id, resp_id):
    """(método, ruta, kwargs) de CADA escritura de Mi comercio que el admin puede hacer."""
    return [
        ("POST", "/comercio/publicar", {"json": {"tipo": "oferta", "titulo": "Hola"}}),
        ("PATCH", f"/comercio/publicaciones/{pub_id}", {"json": {"titulo": "Nuevo"}}),
        ("DELETE", f"/comercio/publicaciones/{pub_id}", {}),
        ("POST", "/comercio/productos", {"data": {"titulo": "R", "precio": "1", "moneda": "ARS", "categoria_slug": "ropa"}}),
        ("DELETE", f"/comercio/productos/{ref_id}", {}),
        ("POST", "/comercio/productos/draft", {"json": {"titulo": "Algo"}}),
        ("POST", "/comercio/fotos", {"files": _foto()}),
        ("DELETE", f"/comercio/fotos/{foto_id}", {}),
        ("PUT", "/comercio/portada", {"json": {"foto_id": foto_id}}),
        ("PUT", "/comercio/perfil/foto", {"files": _foto()}),
        ("POST", "/comercio/videos", {"files": {"video": ("v.mp4", b"x", "video/mp4")}}),
        ("DELETE", f"/comercio/videos/{video_id}", {}),
        ("PUT", "/comercio/perfil", {"json": {"descripcion": "Nueva"}}),
        ("POST", "/comercio/catalogo", {"files": {"archivo": ("c.pdf", b"%PDF-1.4", "application/pdf")}}),
        ("DELETE", "/comercio/catalogo", {}),
        ("POST", "/comercio/asistente/respuestas", {"json": {"pregunta": "¿Envían?", "respuesta": "Sí"}}),
        ("PUT", f"/comercio/asistente/respuestas/{resp_id}", {"json": {"respuesta": "No"}}),
        ("DELETE", f"/comercio/asistente/respuestas/{resp_id}", {}),
    ]


def test_toda_escritura_con_el_token_del_admin_deja_por_admin_y_jti_en_el_log(client, repo, admin_token):
    c = _comercio(repo)
    t = _token_adm(client, admin_token)
    jti = auth._decode(t)["jti"]
    ref = repo.crear_producto_ref({"comercio_id": c["id"], "titulo": "Remera", "precio": 1, "moneda": "ARS"})
    for metodo, ruta, kw in _escrituras(ref["id"], "p1", "f1", "v1", "r1"):
        with capture_logs() as logs:
            client.request(metodo, ruta, headers=_h(t), **kw)
        marcas = [e for e in logs if e["event"] == "comercio.escritura_como_admin"]
        assert len(marcas) == 1, (metodo, ruta)
        m = marcas[0]
        assert m["por_admin"] == ADMIN and m["jti"] == jti and m["comercio_id"] == c["id"], (metodo, ruta)
        assert m["metodo"] == metodo and m["ruta"] == ruta.split("?")[0]
        assert t not in repr(logs)


def test_las_lecturas_y_el_dueno_no_dejan_la_marca_de_escritura_como_admin(client, repo, admin_token):
    c = _comercio(repo)
    t = _token_adm(client, admin_token)
    dueno = auth.make_comercio_token(c["id"], "x@y.com")
    with capture_logs() as logs:
        for ruta in ("/comercio/perfil", "/comercio/mis-publicaciones", "/comercio/fotos", "/comercio/mensajes"):
            assert client.get(ruta, headers=_h(t)).status_code == 200
        client.put("/comercio/perfil", headers=_h(dueno), json={"descripcion": "Del dueño"})
        client.post("/comercio/publicar", headers=_h(dueno), json={"tipo": "oferta", "titulo": "Del dueño"})
    assert not [e for e in logs if e["event"] == "comercio.escritura_como_admin"]


def test_lo_que_publica_el_admin_nace_con_identidad_origen_admin_y_lo_del_dueno_no(client, repo, admin_token):
    c = _comercio(repo)
    t = _token_adm(client, admin_token)
    assert client.post("/comercio/publicar", headers=_h(t), json={"tipo": "oferta", "titulo": "Del equipo"}).status_code == 200
    dueno = auth.make_comercio_token(c["id"], "x@y.com")
    assert client.post("/comercio/publicar", headers=_h(dueno), json={"tipo": "oferta", "titulo": "Del dueño"}).status_code == 200
    por_titulo = {p["titulo"]: p for p in repo.publicaciones}
    assert por_titulo["Del equipo"]["identidad_origen"] == "admin" and por_titulo["Del equipo"]["origen"] == "panel"
    assert "identidad_origen" not in por_titulo["Del dueño"]
    # Sin columnas inventadas: el correo del admin NO se guarda en la publicación (queda en el log con el `jti`).
    assert ADMIN not in repr(por_titulo["Del equipo"])


def test_el_publicar_del_admin_respeta_la_moderacion_del_comercio(client, repo, admin_token):
    _comercio(repo, confiable=False)
    t = _token_adm(client, admin_token)
    r = client.post("/comercio/publicar", headers=_h(t), json={"tipo": "oferta", "titulo": "Para revisar"})
    assert r.status_code == 200 and r.json()["estado"] == "pendiente"


def test_catalogo_el_actor_es_el_correo_del_admin_y_para_el_dueno_el_comercio(client, repo, admin_token):
    c = _comercio(repo)
    t = _token_adm(client, admin_token)
    dueno = auth.make_comercio_token(c["id"], "x@y.com")
    with capture_logs() as logs:
        assert client.delete("/comercio/catalogo", headers=_h(t)).status_code == 200
        assert client.delete("/comercio/catalogo", headers=_h(dueno)).status_code == 200
    quitados = [e for e in logs if e["event"] == "comercio.catalogo_quitado"]
    assert [e["actor"] for e in quitados] == [ADMIN, c["id"]]


# ═══════════════════════════════════════════════ 3. el equipo no gasta el plan del comercio
def _admin_pubs(repo, cid, n, **kw):
    hoy = datetime.now(timezone.utc).isoformat()
    for i in range(n):
        repo.insert_publicacion_directa({"comercio_id": cid, "tipo": "oferta", "titulo": f"adm {i}", "estado": "aprobado",
                                         "created_at": hoy, "identidad_origen": "admin", **kw})


def test_las_publicaciones_del_admin_no_cuentan_en_la_cuota_mensual(repo):
    c = _comercio(repo, plan="publica")
    _admin_pubs(repo, c["id"], 40)                                  # muchas más que las 25 del plan
    est = planes.estado(repo, c)
    assert est["usadas"] == 0 and est["excedido"] is False
    antes = planes.revisar_antes_de_publicar(repo, c)
    assert antes["puede"] and antes["consecuencia"] is None          # el dueño publica sin cargo
    hoy = datetime.now(timezone.utc).isoformat()
    for i in range(25):
        repo.insert_publicacion_directa({"comercio_id": c["id"], "tipo": "oferta", "titulo": f"d {i}",
                                         "estado": "aprobado", "created_at": hoy})
    assert planes.estado(repo, c)["usadas"] == 25
    assert planes.revisar_antes_de_publicar(repo, c)["consecuencia"] == "cobrar"     # sus 25 propias sí


def test_las_publicaciones_del_admin_no_ocupan_el_tope_de_guardadas_ni_se_archivan(repo):
    c = _comercio(repo, plan="gratis")
    tope = planes.plan_de(repo, c)["publicaciones_guardadas"]
    assert tope
    _admin_pubs(repo, c["id"], tope + 3)
    assert repo.publicaciones_activas_de(c["id"]) == []
    assert planes.archivar_excedentes(repo, c) == 0
    assert all(p["activo"] for p in repo.publicaciones)             # ninguna del equipo se archivó
    for i in range(tope + 2):                                       # las del dueño sí respetan su tope
        repo.insert_publicacion_directa({"comercio_id": c["id"], "tipo": "oferta", "titulo": f"d {i}",
                                         "estado": "aprobado", "created_at": f"2026-01-{i % 28 + 1:02d}T00:00:00+00:00"})
    assert planes.archivar_excedentes(repo, c) == 2
    assert all(p["activo"] for p in repo.publicaciones if p.get("identidad_origen") == "admin")


def test_publicar_como_admin_no_archiva_las_publicaciones_del_dueno(client, repo, admin_token):
    c = _comercio(repo, plan="gratis")
    tope = planes.plan_de(repo, c)["publicaciones_guardadas"]
    for i in range(tope):
        repo.insert_publicacion_directa({"comercio_id": c["id"], "tipo": "oferta", "titulo": f"d {i}",
                                         "estado": "aprobado", "created_at": f"2026-01-{i % 28 + 1:02d}T00:00:00+00:00"})
    t = _token_adm(client, admin_token)
    assert client.post("/comercio/publicar", headers=_h(t), json={"tipo": "oferta", "titulo": "Del equipo"}).status_code == 200
    assert all(p["activo"] for p in repo.publicaciones)             # el dueño no perdió ninguna por lo del equipo


def test_el_admin_publica_aunque_el_plan_no_admita_extras_o_este_vencido(client, repo, admin_token):
    c = _comercio(repo, plan="gratis")
    repo.upsert_plan("gratis", {"permite_extras": False, "publicaciones_mes": 1})
    hoy = datetime.now(timezone.utc).isoformat()
    repo.insert_publicacion_directa({"comercio_id": c["id"], "tipo": "oferta", "titulo": "única", "estado": "aprobado",
                                     "created_at": hoy})
    dueno = auth.make_comercio_token(c["id"], "x@y.com")
    assert client.post("/comercio/publicar", headers=_h(dueno), json={"tipo": "oferta", "titulo": "x"}).status_code == 402
    t = _token_adm(client, admin_token)
    assert client.post("/comercio/publicar", headers=_h(t), json={"tipo": "oferta", "titulo": "x"}).status_code == 200


# ═══════════════════════════════════════════════ 4. aviso al dueño
def test_el_dueno_recibe_el_aviso_en_su_bandeja_sin_el_correo_del_admin(client, repo, admin_token):
    c = _comercio(repo)
    r = _entrar(client, admin_token, json={"motivo": "Ayudar con las fotos"})
    assert r.status_code == 200
    (m,) = repo.mensajes.values()
    assert m["comercio_id"] == c["id"] and m["autor"] == "admin" and m["nombre"] == "URUKU" and m["leido"] is False
    assert re.fullmatch(r"El equipo de URUKU entró a tu negocio el \d{2}/\d{2}/\d{4} \d{2}:\d{2}\. "
                        r"Motivo: Ayudar con las fotos\.", m["cuerpo"])
    assert ADMIN not in repr(m) and "admin@" not in m["cuerpo"]
    # Lo ve el dueño en su bandeja.
    dueno = auth.make_comercio_token(c["id"], "x@y.com")
    bandeja = client.get("/comercio/mensajes", headers=_h(dueno)).json()
    assert bandeja["no_leidos"] == 1 and bandeja["items"][0]["cuerpo"] == m["cuerpo"]


def test_el_aviso_dice_la_hora_de_bolivia_y_el_motivo_por_defecto():
    from app.api.comercio import _texto_aviso_de_entrada
    ahora = datetime(2026, 11, 7, 16, 5, tzinfo=timezone.utc)                  # Bolivia es UTC-4
    assert _texto_aviso_de_entrada(None, ahora) == (
        "El equipo de URUKU entró a tu negocio el 07/11/2026 12:05. Motivo: sin motivo indicado.")
    assert _texto_aviso_de_entrada("Revisar", datetime(2026, 11, 8, 2, 30, tzinfo=timezone.utc)) == (
        "El equipo de URUKU entró a tu negocio el 07/11/2026 22:30. Motivo: Revisar.")


def test_sin_motivo_el_aviso_dice_sin_motivo_indicado(client, repo, admin_token):
    _comercio(repo)
    _entrar(client, admin_token)
    (m,) = repo.mensajes.values()
    assert m["cuerpo"].endswith("Motivo: sin motivo indicado.")


def test_un_aviso_por_entrada(client, repo, admin_token):
    """Un mensaje en la bandeja por cada entrada. Es sólo la tabla `mensajes`: no hay ningún envío por WhatsApp."""
    _comercio(repo)
    _entrar(client, admin_token)
    _entrar(client, admin_token)
    assert len(repo.mensajes) == 2


def test_si_la_bandeja_falla_la_entrada_igual_se_da_y_queda_auditada(client, repo, admin_token, monkeypatch):
    _comercio(repo)

    def rota(row):
        raise RuntimeError("bandeja caída")
    monkeypatch.setattr(repo, "crear_mensaje", rota)
    r = _entrar(client, admin_token)
    assert r.status_code == 200 and len(repo.comercio_eventos) == 1


def test_si_no_se_puede_auditar_tampoco_se_avisa(client, repo, admin_token):
    _comercio(repo)
    repo.falla_auditoria = True
    assert _entrar(client, admin_token).status_code == 503
    assert repo.mensajes == {}


# ═══════════════════════════════════════════════ 5. cuentas de emergencia y caché
def test_la_cuenta_de_emergencia_del_env_no_entra(client, repo):
    _comercio(repo)
    del_env = auth.make_token("emergencia@bermejolive.com", rol="admin")        # sin fila en usuarios_panel
    r = _entrar(client, del_env)
    assert r.status_code == 403 and "access_token" not in r.json()
    assert repo.comercio_eventos == [] and repo.mensajes == {}


def test_la_respuesta_de_entrar_no_se_guarda_en_cache(client, repo, admin_token):
    _comercio(repo)
    r = _entrar(client, admin_token)
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"


# ═══════════════════════════════════════════════ 6. salir
def test_salir_devuelve_204_y_ese_token_ya_no_sirve(client, repo, admin_token):
    _comercio(repo)
    t = _token_adm(client, admin_token)
    otra = _token_adm(client, admin_token)                                       # otra entrada del mismo admin
    assert client.get("/comercio/perfil", headers=_h(t)).status_code == 200
    r = client.post("/comercio/entrada/salir", headers=_h(t))
    assert r.status_code == 204 and r.content == b""
    for metodo, ruta, kw in (("GET", "/comercio/perfil", {}), ("GET", "/comercio/mensajes", {}),
                             ("PUT", "/comercio/perfil", {"json": {"descripcion": "x"}}),
                             ("POST", "/comercio/publicar", {"json": {"tipo": "oferta", "titulo": "x"}}),
                             ("POST", "/comercio/entrada/salir", {})):
        assert client.request(metodo, ruta, headers=_h(t), **kw).status_code == 401, (metodo, ruta)
    assert repo.comercios[ID_COMERCIO].get("descripcion") != "x" and repo.publicaciones == []
    assert client.get("/comercio/perfil", headers=_h(otra)).status_code == 200  # las otras entradas siguen


def test_salir_solo_con_el_token_de_un_admin(client, repo):
    c = _comercio(repo)
    dueno = auth.make_comercio_token(c["id"], "x@y.com")
    assert client.post("/comercio/entrada/salir", headers=_h(dueno)).status_code == 403
    assert client.post("/comercio/entrada/salir").status_code == 401
    assert client.get("/comercio/perfil", headers=_h(dueno)).status_code == 200


def test_la_entrada_cerrada_se_olvida_cuando_el_token_vence():
    auth.revocar_entrada("evt-vieja", int(time.time()) - 1)                      # ya vencido: ni se anota
    assert auth.entrada_revocada("evt-vieja") is False
    auth.revocar_entrada("evt-viva", int(time.time()) + 600)
    assert auth.entrada_revocada("evt-viva") is True and auth.entrada_revocada(None) is False
    auth._entradas_revocadas["evt-por-vencer"] = int(time.time()) - 5            # el próximo alta limpia las vencidas
    auth.revocar_entrada("evt-otra", int(time.time()) + 600)
    assert "evt-por-vencer" not in auth._entradas_revocadas


def test_un_reinicio_olvida_las_entradas_cerradas_pero_el_token_igual_muere_a_los_30_minutos(client, repo, admin_token):
    """Documentado: la lista es de memoria. Después de un reinicio el token vuelve a servir hasta que vence."""
    _comercio(repo)
    t = _token_adm(client, admin_token)
    client.post("/comercio/entrada/salir", headers=_h(t))
    assert client.get("/comercio/perfil", headers=_h(t)).status_code == 401
    auth.reiniciar_entradas_revocadas()                                         # = reiniciar el proceso
    assert client.get("/comercio/perfil", headers=_h(t)).status_code == 200
    assert auth._decode(t)["exp"] - int(time.time()) <= auth.ENTRADA_ADMIN_TTL_SEGUNDOS


# ═══════════════════════════════════════════════ 7. historial
def test_el_historial_de_entradas_trae_el_contrato_exacto(client, repo, admin_token):
    _comercio(repo)
    _entrar(client, admin_token, json={"motivo": "Primera"})
    _entrar(client, admin_token)
    r = client.get(f"/admin/comercios/{ID_COMERCIO}/entradas", headers=_h(admin_token))
    assert r.status_code == 200
    items = r.json()["items"]
    assert set(r.json()) == {"items"} and len(items) == 2
    assert all(set(i) == {"admin", "motivo", "at", "expira_en"} for i in items)
    assert items[0]["motivo"] is None and items[1]["motivo"] == "Primera"        # la más nueva primero
    assert items[0]["admin"] == ADMIN
    at, expira = datetime.fromisoformat(items[0]["at"]), datetime.fromisoformat(items[0]["expira_en"])
    assert at.tzinfo is not None and expira.tzinfo is not None
    assert timedelta(minutes=29) <= expira - at <= timedelta(minutes=31)


def test_el_historial_tiene_tope_de_50_y_es_de_ese_comercio(client, repo, admin_token):
    otro = "11111111-2222-4333-8444-555555555555"
    _comercio(repo)
    repo.seed_comercio(id=otro, slug="otro", nombre="Otro", whatsapp="59170000009", activo=True)
    for _ in range(55):
        repo.registrar_evento_comercio(ID_COMERCIO, "entro_como_comercio", ADMIN, {"motivo": None, "expira_en": "x"})
    repo.registrar_evento_comercio(ID_COMERCIO, "clave_generada_por_admin", ADMIN)           # otro tipo: no sale
    repo.registrar_evento_comercio(otro, "entro_como_comercio", "otro@uruku.bo", {"motivo": "ajeno", "expira_en": "x"})
    items = client.get(f"/admin/comercios/{ID_COMERCIO}/entradas", headers=_h(admin_token)).json()["items"]
    assert len(items) == 50 and {i["admin"] for i in items} == {ADMIN}
    assert items == sorted(items, key=lambda i: i["at"], reverse=True)
    assert client.get(f"/admin/comercios/{otro}/entradas", headers=_h(admin_token)).json()["items"][0]["motivo"] == "ajeno"


def test_el_historial_pide_equipo_y_el_comercio_tiene_que_existir(client, repo, admin_token):
    _comercio(repo)
    url = f"/admin/comercios/{ID_COMERCIO}/entradas"
    assert client.get(url).status_code == 401
    moderador = _admin_con_fila(repo, "moni@uruku.bo", roles=("moderador",))
    assert client.get(url, headers=_h(moderador)).status_code == 403
    assert client.get(url, headers=_h(auth.make_comercio_token(ID_COMERCIO, "x@y.com"))).status_code == 403
    assert client.get(url, headers=_h(_token_adm(client, admin_token))).status_code == 403      # el token adm no es del panel
    assert client.get("/admin/comercios/no-es-uuid/entradas", headers=_h(admin_token)).status_code == 404
    assert client.get("/admin/comercios/7d1e2f30-4a5b-4c6d-8e7f-000000000000/entradas",
                      headers=_h(admin_token)).status_code == 404


def test_el_historial_sin_entradas_es_una_lista_vacia(client, repo, admin_token):
    _comercio(repo)
    assert client.get(f"/admin/comercios/{ID_COMERCIO}/entradas", headers=_h(admin_token)).json() == {"items": []}


# ═══════════════════════════════════════════════ 8. el clasificador de rutas
def test_el_clasificador_ve_tambien_las_rutas_que_usan_require_comercio_directo():
    chica = FastAPI()
    r = APIRouter()

    @r.get("/comercio/ruta-directa")
    def directa(claims: dict = Depends(auth.require_comercio)):
        return claims

    chica.include_router(r)
    assert ("GET", "/comercio/ruta-directa") in _rutas_de_mi_comercio(chica.routes)
    assert ("GET", "/comercio/perfil") in _rutas_de_mi_comercio()          # y las de siempre, las de la app real
