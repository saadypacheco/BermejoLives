"""Ronda 2 de portada y permisos: correcciones de QA y seguridad (docs/portada-y-permisos.md).

  1. El agente no borra archivos (portada anterior -> galería; videos y catálogo -> 403).
  2. Permiso `comercios.cuenta` (WhatsApp, confiable, números, grupos, mensaje).
  3. `comercios.baja_motivo` (admin | vencido | borrador) y todo lo que decide con él.
  4. Una oferta bajada que el comercio edita vuelve a pendiente, aunque sea confiable.
  5. «Publicadas»: `q`, `offset`, máx 100 y `total` real.
  6. Defensas: 0146/0147, `_ruta_en_disco`, `borrar_archivos`, portada huérfana, Pillow.
"""
import asyncio
import re
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.core import auth
from app.core.config import settings
from app.core.permisos import CATALOGO, ROLES_BASE, TODOS, tiene
from app.services import fotos_galeria, imagenes, portada
from app.services.imagenes import guardar_foto_local
from tests.conftest import comercio_token

BASE = "https://api.test/fotos"
AGENTE = "agente@bermejolive.com"
RAIZ = Path(__file__).resolve().parents[2]


@pytest.fixture(autouse=True)
def _base_publica(monkeypatch):
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _jpeg(lado=10):
    buf = BytesIO()
    Image.new("RGB", (lado, lado), "green").save(buf, format="JPEG")
    buf.seek(0)
    return buf


def _foto():
    return {"foto": ("f.jpg", _jpeg(), "image/jpeg")}


def _en_disco(nombre, slug="local"):
    return (Path(settings.fotos_dir) / slug / nombre).exists()


def _archivo(nombre, slug="local"):
    guardar_foto_local(f"{slug}/{nombre}", b"x")
    return f"{BASE}/{slug}/{nombre}"


def _comercio(repo, **kw):
    base = dict(id="com-p", slug="local", nombre="Local", whatsapp="59170000001",
                confiable=True, cargado_por=AGENTE, ciudad_id="ciu-1")
    base.update(kw)
    return repo.seed_comercio(**base)


def _con_portada(repo, nombre="A", **kw):
    url, thumb = _archivo(f"{nombre}.jpg"), _archivo(f"{nombre}_t3.jpg")
    return _comercio(repo, portada_url=url, portada_thumb_url=thumb, portada_pos=30, **kw)


def _sembrar(repo, cid, nombres, slug="local"):
    for i, n in enumerate(nombres):
        repo.comercio_fotos.append({
            "id": f"f{i}", "comercio_id": cid, "url": _archivo(f"{n}.jpg", slug),
            "thumb_url": _archivo(f"{n}_t3.jpg", slug), "orden": i,
            "created_at": f"2026-01-01T00:0{i}:00+00:00"})


def _urls_galeria(repo, cid):
    return [f["url"].rsplit("/", 1)[1] for f in repo.list_fotos_comercio(cid)]


def _archivos_en_disco():
    raiz = Path(settings.fotos_dir)
    return {p for p in raiz.rglob("*") if p.is_file()} if raiz.exists() else set()


@pytest.fixture
def tok_agente(agente_token):
    return agente_token


@pytest.fixture
def tok_pub():
    return auth.make_publicador_token("pub@uruku.bo")


@pytest.fixture
def tok_mod():
    return auth.make_token("mod@uruku.bo", rol="moderador")


# ══════════════════════════════════════════ 1. el agente no borra archivos

def test_agente_portada_nueva_deja_la_anterior_en_la_galeria_y_en_el_disco(client, repo, tok_agente):
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["B"])
    r = client.post(f"/campo/mis-comercios/{c['id']}/foto", headers=_h(tok_agente), files=_foto())
    assert r.status_code == 200, r.text
    nueva = repo.comercios[c["id"]]
    assert nueva["portada_url"] != f"{BASE}/local/A.jpg" and nueva["portada_pos"] is None
    # La portada anterior pasó a la galería, con sus dos archivos, y no se borró nada.
    assert _urls_galeria(repo, c["id"]) == ["B.jpg", "A.jpg"]
    assert repo.list_fotos_comercio(c["id"])[-1]["thumb_url"] == f"{BASE}/local/A_t3.jpg"
    for n in ("A.jpg", "A_t3.jpg", "B.jpg", "B_t3.jpg"):
        assert _en_disco(n), n


def test_agente_portada_nueva_pasa_a_la_galeria_aunque_supere_el_tope(client, repo, tok_agente):
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["B", "C"])
    repo.upsert_plan("gratis", {"fotos_max": 2})           # la galería YA está en el tope
    r = client.post(f"/campo/mis-comercios/{c['id']}/foto", headers=_h(tok_agente), files=_foto())
    assert r.status_code == 200, r.text
    assert _urls_galeria(repo, c["id"]) == ["B.jpg", "C.jpg", "A.jpg"]      # 3 sobre un tope de 2: ya existía
    assert fotos_galeria.listado(repo, repo.comercios[c["id"]])["limite"] == 2
    # Pero subir otra foto de galería sigue chocando con el tope.
    r = client.post(f"/campo/mis-comercios/{c['id']}/fotos", headers=_h(tok_agente), files=_foto())
    assert r.status_code == 409


def test_agente_portada_nueva_no_repite_la_anterior_si_la_galeria_ya_la_tiene(client, repo, tok_agente):
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["A"])
    r = client.post(f"/campo/mis-comercios/{c['id']}/foto", headers=_h(tok_agente), files=_foto())
    assert r.status_code == 200, r.text
    assert _urls_galeria(repo, c["id"]) == ["A.jpg"] and _en_disco("A.jpg")


def test_agente_portada_nueva_sin_portada_anterior_no_inventa_una_foto_de_galeria(client, repo, tok_agente):
    c = _comercio(repo)
    r = client.post(f"/campo/mis-comercios/{c['id']}/foto", headers=_h(tok_agente), files=_foto())
    assert r.status_code == 200, r.text
    assert repo.list_fotos_comercio(c["id"]) == [] and repo.comercios[c["id"]]["portada_url"]


@pytest.mark.parametrize("lado", ["comercio", "admin"])
def test_admin_y_comerciante_si_borran_la_portada_anterior(client, repo, admin_token, lado):
    c = _con_portada(repo, "A")
    if lado == "admin":
        r = client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(admin_token), files=_foto())
    else:
        r = client.put("/comercio/perfil/foto", headers=_h(comercio_token(comercio_id=c["id"])), files=_foto())
    assert r.status_code == 200, r.text
    assert not _en_disco("A.jpg") and not _en_disco("A_t3.jpg")
    assert repo.list_fotos_comercio(c["id"]) == []


def test_agente_no_borra_videos(client, repo, tok_agente):
    c = _comercio(repo)
    repo.comercio_videos.append({"id": "v1", "comercio_id": c["id"], "url": f"{BASE}/local/videos/v.mp4", "orden": 0})
    r = client.delete(f"/campo/mis-comercios/{c['id']}/videos/v1", headers=_h(tok_agente))
    assert r.status_code == 403
    assert r.json()["detail"] == fotos_galeria.MSG_AGENTE_NO_BORRA == "Las fotos las borra URUKU. Avisale al admin."
    assert [v["id"] for v in repo.comercio_videos] == ["v1"]


def test_agente_no_borra_el_catalogo_ni_por_delete_ni_por_patch(client, repo, tok_agente):
    c = _comercio(repo, catalogo_url="https://drive.google.com/file/d/xyz")
    h = _h(tok_agente)
    r = client.delete(f"/campo/mis-comercios/{c['id']}/catalogo", headers=h)
    assert r.status_code == 403 and r.json()["detail"] == fotos_galeria.MSG_AGENTE_NO_BORRA
    for vacio in ("", "   "):
        r = client.patch(f"/campo/mis-comercios/{c['id']}", headers=h, json={"catalogo_url": vacio})
        assert r.status_code == 403, vacio
    assert repo.comercios[c["id"]]["catalogo_url"] == "https://drive.google.com/file/d/xyz"


def test_agente_puede_cambiar_un_enlace_de_catalogo_por_otro_pero_no_un_pdf_nuestro_por_un_enlace(client, repo, tok_agente):
    c = _comercio(repo, catalogo_url="https://drive.google.com/file/d/uno")
    h = _h(tok_agente)
    r = client.patch(f"/campo/mis-comercios/{c['id']}", headers=h, json={"catalogo_url": "https://drive.google.com/file/d/dos"})
    assert r.status_code == 200, r.text
    assert repo.comercios[c["id"]]["catalogo_url"].endswith("/dos")
    # Un PDF nuestro: reemplazarlo por un enlace lo dejaría huérfano (se borraría del disco).
    carpeta = Path(settings.fotos_dir) / "catalogos" / c["id"]
    carpeta.mkdir(parents=True)
    (carpeta / "abcdef0123456789.pdf").write_bytes(b"%PDF-1.4")
    pdf = f"{BASE}/catalogos/{c['id']}/abcdef0123456789.pdf"
    repo.comercios[c["id"]]["catalogo_url"] = pdf
    r = client.patch(f"/campo/mis-comercios/{c['id']}", headers=h, json={"catalogo_url": "https://x.com/otro"})
    assert r.status_code == 403
    assert (carpeta / "abcdef0123456789.pdf").exists() and repo.comercios[c["id"]]["catalogo_url"] == pdf


def test_el_comerciante_y_el_admin_si_borran_videos_y_catalogo_como_antes(client, repo, admin_token):
    c = _comercio(repo)
    repo.comercio_videos.append({"id": "v1", "comercio_id": c["id"], "url": "u", "orden": 0})
    r = client.delete("/comercio/videos/v1", headers=_h(comercio_token(comercio_id=c["id"])))
    assert r.status_code == 200 and repo.comercio_videos == []


# ══════════════════════════════════════════ 2. el permiso comercios.cuenta

def test_comercios_cuenta_esta_en_el_catalogo_y_en_los_roles_del_sistema():
    assert "comercios.cuenta" in TODOS
    assert [g for p, _, g in CATALOGO if p == "comercios.cuenta"] == ["Día a día"]
    assert "comercios.cuenta" in ROLES_BASE["moderador"]["permisos"]
    assert "comercios.cuenta" not in ROLES_BASE["publicador"]["permisos"]
    assert "comercios.editar" in ROLES_BASE["publicador"]["permisos"]
    assert "comercios.cuenta" not in ROLES_BASE["agente"]["permisos"]
    assert tiene({"rol": "admin", "permisos": ["*"]}, "comercios.cuenta")
    assert not tiene(auth._decode(auth.make_publicador_token("p@x.com")), "comercios.cuenta")


def test_equipo_lista_el_permiso_nuevo(client, admin_token):
    r = client.get("/admin/equipo", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert "comercios.cuenta" in str(r.json())


CUENTA = [
    ("post", "/admin/comercio/{cid}/confiable", {"json": {"confiable": True}}),
    ("post", "/admin/comercio/{cid}/numeros", {"json": {"numero": "59172222222"}}),
    ("post", "/admin/comercio/{cid}/grupos", {"json": {"grupo_jid": "123@g.us"}}),
    ("delete", "/admin/comercio/{cid}/grupos/123@g.us", {}),
    ("post", "/admin/comercio/{cid}/grupo", {}),
    ("post", "/admin/comercio/{cid}/mensaje", {"json": {"cuerpo": "hola"}}),
]


@pytest.mark.parametrize("metodo,ruta,kw", CUENTA)
def test_el_publicador_no_toca_la_cuenta_y_un_rol_con_el_permiso_si(client, repo, tok_pub, metodo, ruta, kw):
    c = _comercio(repo, confiable=False)
    ruta = ruta.format(cid=c["id"])
    assert getattr(client, metodo)(ruta, headers=_h(tok_pub), **kw).status_code == 403
    # Sin el permiso de ficha tampoco (solo `comercios.cuenta` abre la cuenta).
    solo_editar = auth.make_token("e@x.com", rol="x", permisos=["comercios.editar"])
    assert getattr(client, metodo)(ruta, headers=_h(solo_editar), **kw).status_code == 403
    con = auth.make_token("c@x.com", rol="x", permisos=["comercios.cuenta"])
    assert getattr(client, metodo)(ruta, headers=_h(con), **kw).status_code != 403


def test_cambiar_el_whatsapp_pide_cuenta_solo_si_el_numero_cambia(client, repo, tok_pub, tok_mod):
    c = _comercio(repo, whatsapp="59170000001")
    cid = c["id"]
    # Mismo número (aunque escrito distinto) + otros campos: es corregir la ficha.
    r = client.put(f"/admin/comercio/{cid}", headers=_h(tok_pub), json={"whatsapp": "+591 70000001", "direccion": "X"})
    assert r.status_code == 200, r.text
    assert repo.comercios[cid]["direccion"] == "X"
    # Número distinto, o vaciarlo: es tocar la llave de ingreso.
    for nuevo in ("59171111111", ""):
        r = client.put(f"/admin/comercio/{cid}", headers=_h(tok_pub), json={"whatsapp": nuevo})
        assert r.status_code == 403, nuevo
    assert repo.comercios[cid]["whatsapp"] == "59170000001"
    # Y sin tocar el whatsapp, nada de cuenta de por medio.
    assert client.put(f"/admin/comercio/{cid}", headers=_h(tok_pub), json={"nombre": "Nuevo"}).status_code == 200
    # El moderador sí.
    r = client.put(f"/admin/comercio/{cid}", headers=_h(tok_mod), json={"whatsapp": "59171111111"})
    assert r.status_code == 200, r.text
    assert repo.comercios[cid]["whatsapp"] != "59170000001"


def test_leer_numeros_y_grupos_sigue_siendo_de_comercios_editar(client, repo, tok_pub):
    c = _comercio(repo)
    assert client.get(f"/admin/comercio/{c['id']}/numeros", headers=_h(tok_pub)).status_code == 200
    assert client.get(f"/admin/comercio/{c['id']}/grupos", headers=_h(tok_pub)).status_code == 200


# ══════════════════════════════════════════ 3. baja_motivo

def test_rechazar_da_de_baja_con_motivo_admin_y_reactivar_lo_borra(client, repo, admin_token):
    c = _comercio(repo)
    h = _h(admin_token)
    assert client.post(f"/moderacion/comercios/{c['id']}/rechazar", headers=h).status_code == 200
    assert repo.comercios[c["id"]]["activo"] is False and repo.comercios[c["id"]]["baja_motivo"] == "admin"
    items = client.get("/admin/comercios/dados-de-baja", headers=h).json()["items"]
    assert [(i["id"], i["baja_motivo"]) for i in items] == [(c["id"], "admin")]
    assert client.post(f"/admin/comercio/{c['id']}/reactivar", headers=h).status_code == 200
    assert repo.comercios[c["id"]]["activo"] is True and repo.comercios[c["id"]]["baja_motivo"] is None


def test_el_job_de_vencimientos_marca_vencido_y_no_sale_en_dados_de_baja(client, repo, admin_token):
    c = _comercio(repo, paga_hasta="2020-01-01")
    assert repo.ocultar_comercios_vencidos(dias=40) == 1
    assert repo.comercios[c["id"]]["activo"] is False and repo.comercios[c["id"]]["baja_motivo"] == "vencido"
    assert client.get("/admin/comercios/dados-de-baja", headers=_h(admin_token)).json()["items"] == []


def test_dados_de_baja_lista_admin_y_viejos_sin_motivo_pero_no_vencido_ni_borrador(client, repo, admin_token):
    repo.seed_comercio(id="a", slug="a", nombre="A", activo=False, baja_motivo="admin")
    repo.seed_comercio(id="n", slug="n", nombre="N", activo=False)                      # baja vieja, sin motivo
    repo.seed_comercio(id="v", slug="v", nombre="V", activo=False, baja_motivo="vencido")
    repo.seed_comercio(id="b", slug="b", nombre="B", activo=False, baja_motivo="borrador")
    items = client.get("/admin/comercios/dados-de-baja", headers=_h(admin_token)).json()["items"]
    assert sorted((i["id"], i["baja_motivo"]) for i in items) == [("a", "admin"), ("n", None)]


def test_reactivar_un_vencido_es_409_y_no_cambia_nada(client, repo, admin_token):
    c = repo.seed_comercio(id="v", slug="v", nombre="V", activo=False, baja_motivo="vencido")
    r = client.post(f"/admin/comercio/{c['id']}/reactivar", headers=_h(admin_token))
    assert r.status_code == 409 and r.json()["detail"] == "Se reactiva al registrar el pago"
    assert repo.comercios["v"]["activo"] is False and repo.comercios["v"]["baja_motivo"] == "vencido"


def test_reactivar_un_activo_o_inexistente(client, repo, admin_token):
    c = _comercio(repo)
    assert client.post(f"/admin/comercio/{c['id']}/reactivar", headers=_h(admin_token)).status_code == 200
    assert client.post("/admin/comercio/no-existe/reactivar", headers=_h(admin_token)).status_code == 404


def test_un_alta_que_nace_inactiva_es_un_borrador(repo):
    assert repo.crear_comercio({"slug": "x", "nombre": "X", "activo": False})["baja_motivo"] == "borrador"
    assert repo.crear_comercio({"slug": "y", "nombre": "Y"}).get("baja_motivo") is None
    assert repo.crear_comercio({"slug": "z", "nombre": "Z", "activo": False, "baja_motivo": "admin"})["baja_motivo"] == "admin"


@pytest.mark.parametrize("motivo,se_enciende", [("borrador", True), ("admin", False), ("vencido", False), (None, False)])
def test_aprobar_una_publicacion_solo_enciende_a_un_borrador(client, repo, admin_token, motivo, se_enciende):
    kw = {"baja_motivo": motivo} if motivo else {}
    c = repo.seed_comercio(id="com-x", slug="x", nombre="X", whatsapp="591", activo=False, **kw)
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "tipo": "oferta", "estado": "pendiente", "titulo": "T"})
    r = client.post(f"/moderacion/publicaciones/{pub['id']}", headers=_h(admin_token), json={"estado": "aprobado"})
    assert r.status_code == 200, r.text
    assert repo.publicaciones[0]["estado"] == "aprobado"              # la oferta se aprueba igual
    assert repo.comercios[c["id"]]["activo"] is se_enciende
    if se_enciende:
        assert repo.comercios[c["id"]]["baja_motivo"] is None and "advertencia" not in r.json()
    else:
        assert repo.comercios[c["id"]].get("baja_motivo") == motivo
        assert "dado de baja" in r.json()["advertencia"]


def test_aprobar_la_publicacion_de_un_comercio_activo_no_agrega_advertencia(client, repo, admin_token):
    c = _comercio(repo)
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "tipo": "oferta", "estado": "pendiente", "titulo": "T"})
    r = client.post(f"/moderacion/publicaciones/{pub['id']}", headers=_h(admin_token), json={"estado": "aprobado"})
    assert r.status_code == 200 and "advertencia" not in r.json()


def test_la_ingesta_por_grupo_ignora_a_un_comercio_inactivo(repo):
    c = repo.seed_comercio(id="g", slug="g", nombre="G", activo=False, baja_motivo="admin")
    activo = _comercio(repo, id="com-ok")
    repo.vincular_grupo_comercio("1@g.us", c["id"], None, "admin", "x")
    repo.vincular_grupo_comercio("2@g.us", activo["id"], None, "admin", "x")
    assert repo.get_comercio_por_grupo("1@g.us") is None
    assert repo.get_comercio_por_grupo("1@g.us", incluir_inactivos=True)["id"] == "g"       # para saber de quién ES
    assert repo.get_comercio_por_grupo("2@g.us")["id"] == "com-ok"


def test_atar_un_grupo_que_es_de_un_comercio_de_baja_avisa_en_vez_de_no_hacer_nada(client, repo, admin_token):
    viejo = repo.seed_comercio(id="g", slug="g", nombre="G", activo=False, baja_motivo="admin")
    nuevo = _comercio(repo)
    repo.vincular_grupo_comercio("1@g.us", viejo["id"], None, "admin", "x")
    r = client.post(f"/admin/comercio/{nuevo['id']}/grupos", headers=_h(admin_token), json={"grupo_jid": "1@g.us"})
    assert r.status_code == 409


def test_activar_por_pagos_no_reactiva_una_baja_del_admin_pero_si_un_vencido(client, repo):
    admin = repo.seed_comercio(id="a", slug="a", nombre="A", activo=False, baja_motivo="admin", suspendido=True)
    viejo = repo.seed_comercio(id="n", slug="n", nombre="N", activo=False, suspendido=True)
    vencido = repo.seed_comercio(id="v", slug="v", nombre="V", activo=False, baja_motivo="vencido", suspendido=True)
    pagos = _h(auth.make_token("p@x.com", rol="x", permisos=["pagos"]))
    for cid in ("a", "n", "v"):
        assert client.post(f"/admin/comercio/{cid}/activar", headers=pagos).status_code == 200
    for c in (admin, viejo):
        assert c["activo"] is False and c["suspendido"] is False         # sólo se levantó la suspensión
    assert admin["baja_motivo"] == "admin"
    assert vencido["activo"] is True and vencido["suspendido"] is False and vencido["baja_motivo"] is None


def test_registrar_un_pago_reactiva_al_vencido_y_no_al_dado_de_baja_por_el_admin(repo):
    v = repo.seed_comercio(id="v", slug="v", nombre="V", activo=False, baja_motivo="vencido")
    a = repo.seed_comercio(id="a", slug="a", nombre="A", activo=False, baja_motivo="admin")
    repo.registrar_pago("v", {"monto": 10, "meses": 1})
    repo.registrar_pago("a", {"monto": 10, "meses": 1})
    assert v["activo"] is True and v["baja_motivo"] is None
    assert a["activo"] is False and a["baja_motivo"] == "admin" and a["paga_hasta"]       # el pago se registra igual


def test_el_comerciante_dado_de_baja_por_el_admin_lee_pero_no_escribe(client, repo):
    c = _comercio(repo, activo=False, baja_motivo="admin")
    h = _h(comercio_token(comercio_id=c["id"]))
    assert client.get("/comercio/perfil", headers=h).status_code == 200            # puede mirar
    assert client.get("/comercio/fotos", headers=h).status_code == 200
    escrituras = [
        ("put", "/comercio/perfil", {"json": {"direccion": "X"}}),
        ("put", "/comercio/perfil/foto", {"files": _foto()}),
        ("post", "/comercio/fotos", {"files": _foto()}),
        ("put", "/comercio/portada", {"json": {"foto_id": "f0"}}),
        ("delete", "/comercio/fotos/f0", {}),
        ("delete", "/comercio/videos/v1", {}),
        ("delete", "/comercio/catalogo", {}),
        ("patch", "/comercio/publicaciones/p1", {"json": {"titulo": "X"}}),
        ("delete", "/comercio/publicaciones/p1", {}),
        ("post", "/comercio/clave", {}),
    ]
    for metodo, ruta, kw in escrituras:
        r = getattr(client, metodo)(ruta, headers=h, **kw)
        assert r.status_code == 403, (metodo, ruta, r.status_code, r.text)
        assert "dado de baja" in r.json()["detail"]
    assert repo.comercios[c["id"]].get("direccion") is None


@pytest.mark.parametrize("motivo", ["vencido", "borrador", None])
def test_el_comerciante_vencido_o_sin_motivo_sigue_pudiendo_escribir(client, repo, motivo):
    kw = {"baja_motivo": motivo} if motivo else {}
    c = _comercio(repo, activo=False, **kw)
    r = client.put("/comercio/perfil", headers=_h(comercio_token(comercio_id=c["id"])), json={"direccion": "X"})
    assert r.status_code == 200, r.text            # un vencido tiene que poder entrar a pagar


def test_el_comerciante_reactivado_vuelve_a_escribir(client, repo, admin_token):
    c = _comercio(repo, activo=False, baja_motivo="admin")
    h = _h(comercio_token(comercio_id=c["id"]))
    assert client.put("/comercio/perfil", headers=h, json={"direccion": "X"}).status_code == 403
    client.post(f"/admin/comercio/{c['id']}/reactivar", headers=_h(admin_token))
    assert client.put("/comercio/perfil", headers=h, json={"direccion": "X"}).status_code == 200


# ══════════════════════════════════════════ 4. una oferta bajada no vuelve sola

def _oferta(repo, cid, estado, **kw):
    return repo.insert_publicacion_directa({"comercio_id": cid, "tipo": "oferta", "estado": estado,
                                            "titulo": "Campera", **kw})


@pytest.mark.parametrize("estado", ["rechazado", "cambios"])
def test_editar_una_oferta_bajada_la_deja_pendiente_aunque_el_comercio_sea_confiable(client, repo, estado):
    c = _comercio(repo, confiable=True)
    pub = _oferta(repo, c["id"], estado, approved_at=None)
    h = _h(comercio_token(comercio_id=c["id"]))
    r = client.patch(f"/comercio/publicaciones/{pub['id']}", headers=h, json={"titulo": "Campera nueva"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "pendiente"
    assert repo.publicaciones[0]["estado"] == "pendiente" and repo.publicaciones[0]["approved_at"] is None


def test_editar_una_oferta_aprobada_de_un_confiable_sigue_aprobada_y_la_de_un_no_confiable_pendiente(client, repo):
    conf = _comercio(repo, confiable=True)
    no_conf = _comercio(repo, id="com-q", slug="q", confiable=False)
    p1 = _oferta(repo, conf["id"], "aprobado")
    p2 = _oferta(repo, no_conf["id"], "aprobado")
    r1 = client.patch(f"/comercio/publicaciones/{p1['id']}", headers=_h(comercio_token(comercio_id=conf["id"])), json={"titulo": "X"})
    r2 = client.patch(f"/comercio/publicaciones/{p2['id']}", headers=_h(comercio_token(comercio_id=no_conf["id"])), json={"titulo": "X"})
    assert r1.json()["estado"] == "aprobado" and r2.json()["estado"] == "pendiente"


def test_una_oferta_pendiente_de_un_confiable_editada_sigue_el_camino_de_siempre(client, repo):
    c = _comercio(repo, confiable=True)
    pub = _oferta(repo, c["id"], "pendiente")
    r = client.patch(f"/comercio/publicaciones/{pub['id']}", headers=_h(comercio_token(comercio_id=c["id"])), json={"titulo": "X"})
    assert r.json()["estado"] == "aprobado"            # no estaba bajada: no cambia lo de antes


def test_editar_la_oferta_bajada_de_otro_comercio_es_404_y_no_la_toca(client, repo):
    mio = _comercio(repo, confiable=True)
    otro = _comercio(repo, id="com-o", slug="o")
    pub = _oferta(repo, otro["id"], "rechazado")
    r = client.patch(f"/comercio/publicaciones/{pub['id']}", headers=_h(comercio_token(comercio_id=mio["id"])), json={"titulo": "X"})
    assert r.status_code == 404 and repo.publicaciones[0]["estado"] == "rechazado"


# ══════════════════════════════════════════ 5. «Publicadas»

def _publicadas(repo, n, comercio="com-p", estado="aprobado", prefijo="Oferta"):
    for i in range(n):
        repo.publicaciones.append({"id": f"{prefijo}-{i:03d}", "activo": True, "estado": estado, "comercio_id": comercio,
                                   "tipo": "oferta", "titulo": f"{prefijo} {i}",
                                   "created_at": f"2026-01-01T00:00:{i % 60:02d}+00:00" if i < 60 else f"2026-01-02T00:{i // 60:02d}:{i % 60:02d}+00:00"})


def test_publicadas_pagina_de_a_100_y_trae_el_total_real(client, repo, tok_pub):
    _comercio(repo)
    _publicadas(repo, 250)
    h = _h(tok_pub)
    r = client.get("/moderacion/publicaciones?estado=aprobado", headers=h).json()
    assert len(r["items"]) == 100 and r["total"] == 250
    r2 = client.get("/moderacion/publicaciones?estado=aprobado&offset=100", headers=h).json()
    r3 = client.get("/moderacion/publicaciones?estado=aprobado&offset=200", headers=h).json()
    assert len(r2["items"]) == 100 and len(r3["items"]) == 50 and r3["total"] == 250
    ids = [p["id"] for p in r["items"] + r2["items"] + r3["items"]]
    assert len(set(ids)) == 250                         # sin repetir ni saltear
    assert client.get("/moderacion/publicaciones?estado=aprobado&offset=900", headers=h).json() == {"items": [], "total": 250}


def test_publicadas_busca_por_titulo_y_por_nombre_del_comercio(client, repo, tok_pub):
    _comercio(repo, nombre="Ferretería Don Pepe")
    repo.seed_comercio(id="com-z", slug="z", nombre="Zapatería Lola")
    _publicadas(repo, 3, "com-p", prefijo="Taladro")
    _publicadas(repo, 2, "com-z", prefijo="Sandalia")
    h = _h(tok_pub)
    titulo = client.get("/moderacion/publicaciones?estado=aprobado&q=taladro", headers=h).json()
    assert titulo["total"] == 3 and all(p["titulo"].startswith("Taladro") for p in titulo["items"])
    comercio = client.get("/moderacion/publicaciones?estado=aprobado&q=LOLA", headers=h).json()
    assert comercio["total"] == 2 and all(p["comercio_id"] == "com-z" for p in comercio["items"])
    assert client.get("/moderacion/publicaciones?estado=aprobado&q=nada-de-esto", headers=h).json() == {"items": [], "total": 0}
    # Los comodines y la sintaxis de PostgREST se buscan como texto, no revientan.
    for raro in ("%", "*", "a,b", "x)", "(", '"', "\\"):
        assert client.get("/moderacion/publicaciones", params={"estado": "aprobado", "q": raro}, headers=h).status_code == 200


def test_publicadas_filtra_por_estado_y_no_mezcla_archivadas(client, repo, tok_pub):
    _comercio(repo)
    _publicadas(repo, 3, estado="aprobado")
    _publicadas(repo, 2, estado="rechazado", prefijo="Baja")
    repo.publicaciones.append({"id": "arch", "activo": False, "estado": "aprobado", "comercio_id": "com-p", "titulo": "Archivada"})
    h = _h(tok_pub)
    assert client.get("/moderacion/publicaciones?estado=aprobado", headers=h).json()["total"] == 3
    assert client.get("/moderacion/publicaciones?estado=rechazado", headers=h).json()["total"] == 2


def test_la_cola_de_pendientes_no_cambia(client, repo, tok_pub):
    _comercio(repo)
    _publicadas(repo, 150, estado="pendiente")
    j = client.get("/moderacion/publicaciones", headers=_h(tok_pub)).json()
    assert len(j["items"]) == 150 and j["total"] == 150                   # sin el tope de 100
    j = client.get("/moderacion/publicaciones?q=zzz&offset=5", headers=_h(tok_pub)).json()
    assert len(j["items"]) == 150                                          # q y offset no aplican a pendientes


def test_publicadas_valida_los_parametros(client, repo, tok_pub):
    h = _h(tok_pub)
    assert client.get("/moderacion/publicaciones?estado=aprobado&offset=-1", headers=h).status_code == 422
    assert client.get("/moderacion/publicaciones?estado=aprobado&q=" + "a" * 81, headers=h).status_code == 422
    assert client.get("/moderacion/publicaciones?estado=aprobado").status_code == 401
    assert client.get("/moderacion/publicaciones?estado=aprobado", headers=_h(comercio_token())).status_code == 403


def test_limpiar_busqueda():
    from app.db.repository import limpiar_busqueda
    assert limpiar_busqueda(None) == "" and limpiar_busqueda("  ") == ""
    assert limpiar_busqueda('a,b(c)"d\\e*f%g') == "a b c  d e f g"
    assert len(limpiar_busqueda("x" * 500)) == 80


# ══════════════════════════════════════════ 6. defensas

def test_0146_no_prende_un_rol_vaciado_ni_pisa_una_descripcion_editada():
    sql = (RAIZ / "supabase/migrations/0146_publicador_edita_fichas.sql").read_text(encoding="utf-8")
    assert sql == (RAIZ / "selfhost/postgres-init/0146_publicador_edita_fichas.sql").read_text(encoding="utf-8")
    codigo = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
    assert "and cardinality(permisos) > 0" in codigo
    assert "and descripcion = 'Carga la cotización, el estado del paso y los videos.'" in codigo
    assert codigo.count("update roles") == 2


def test_0147_es_igual_en_las_dos_carpetas_y_tiene_lo_prometido():
    a = (RAIZ / "supabase/migrations/0147_cuenta_y_baja_motivo.sql").read_bytes()
    b = (RAIZ / "selfhost/postgres-init/0147_cuenta_y_baja_motivo.sql").read_bytes()
    assert a == b and a
    sql = a.decode("utf-8")
    codigo = "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))
    assert "array_append(permisos, 'comercios.cuenta')" in codigo and "slug = 'moderador'" in codigo
    assert "cardinality(permisos) > 0" in codigo and "not ('comercios.cuenta' = any(permisos))" in codigo
    assert "add column if not exists baja_motivo text" in codigo
    assert "check (baja_motivo in ('admin', 'vencido', 'borrador'))" in codigo
    assert "comment on column comercios.baja_motivo is" in codigo
    # Privada para anon: ningún grant.
    assert not re.search(r"\bgrant\b", codigo, re.I)
    # Idempotente y atómica.
    assert "begin;" in codigo and "commit;" in codigo
    assert codigo.count("and baja_motivo is null") == 2           # el backfill no pisa lo ya clasificado
    assert "notify pgrst, 'reload schema';" in codigo


def test_baja_motivo_esta_en_las_privadas_para_anon():
    from tests.test_comercios_columnas_publicas import NO_VAN_EN_LA_LISTA, PRIVADAS_EXTRA, _columnas_dadas
    assert "baja_motivo" in PRIVADAS_EXTRA and "baja_motivo" in NO_VAN_EN_LA_LISTA
    assert "baja_motivo" not in _columnas_dadas()


def test_ruta_en_disco_exige_la_carpeta_del_comercio():
    ok = f"{BASE}/mi-local/foto.jpg"
    assert fotos_galeria._ruta_en_disco(ok, "mi-local") is not None
    assert fotos_galeria._ruta_en_disco(ok, "otro-local") is None
    assert fotos_galeria._ruta_en_disco(ok, "mi") is None and fotos_galeria._ruta_en_disco(ok, "") is None
    assert fotos_galeria._ruta_en_disco(f"{BASE}/otro-local/foto.jpg", "mi-local") is None
    assert fotos_galeria._ruta_en_disco(ok) is not None            # sin slug, como antes (compatibilidad)


def test_borrar_archivos_no_toca_el_archivo_de_otro_comercio(repo):
    otro = _archivo("ajena.jpg", slug="otro-local")
    c = _comercio(repo)
    # Una fila de galería de ESTE comercio con una URL de la carpeta de otro.
    fotos_galeria.borrar_archivos(c, {"url": otro, "thumb_url": None}, repo)
    assert _en_disco("ajena.jpg", slug="otro-local")


def test_borrar_archivos_mira_cualquier_fila_de_galeria_y_cualquier_portada(repo):
    c = _comercio(repo)
    otro = repo.seed_comercio(id="com-o", slug="o", nombre="O")
    url_fila = _archivo("fila.jpg")
    url_portada = _archivo("portada.jpg")
    url_thumb = _archivo("thumb_t3.jpg")
    libre = _archivo("libre.jpg")
    repo.comercio_fotos.append({"id": "x1", "comercio_id": otro["id"], "url": url_fila, "thumb_url": None, "orden": 0})
    otro["portada_url"] = url_portada
    otro["portada_thumb_url"] = url_thumb
    for u in (url_fila, url_portada, url_thumb, libre):
        fotos_galeria.borrar_archivos(c, {"url": u, "thumb_url": None}, repo)
    assert _en_disco("fila.jpg") and _en_disco("portada.jpg") and _en_disco("thumb_t3.jpg")      # alguien las usa
    assert not _en_disco("libre.jpg")                                                                # nadie: se borra


def test_borrar_archivos_si_no_puede_comprobar_no_borra(repo, monkeypatch):
    c = _comercio(repo)
    url = _archivo("dudosa.jpg")

    def roto(_):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "foto_en_uso_por_comercios", roto)
    fotos_galeria.borrar_archivos(c, {"url": url, "thumb_url": None}, repo)        # nunca lanza
    assert _en_disco("dudosa.jpg")


def test_borrar_una_foto_con_un_duplicado_en_otra_fila_deja_el_archivo(client, repo, admin_token):
    c = _comercio(repo)
    _sembrar(repo, c["id"], ["B"])
    # Otra fila (un duplicado) apunta al mismo archivo.
    repo.comercio_fotos.append({"id": "dup", "comercio_id": c["id"], "url": f"{BASE}/local/B.jpg", "thumb_url": None, "orden": 1})
    r = client.delete(f"/admin/comercio/{c['id']}/fotos/f0", headers=_h(admin_token))
    assert r.status_code == 200
    assert _en_disco("B.jpg")                          # lo sigue usando "dup"
    r = client.delete(f"/admin/comercio/{c['id']}/fotos/dup", headers=_h(admin_token))
    assert not _en_disco("B.jpg")                      # ya nadie: ahora sí


# ── si falla guardar la portada nueva, los archivos subidos se borran (QA BUG-3)

def _romper_update(repo, monkeypatch):
    def roto(*a, **k):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "update_comercio", roto)


def test_si_falla_guardar_la_portada_no_quedan_archivos_huerfanos_en_ningun_perfil(client, repo, admin_token, tok_agente, monkeypatch):
    c = _con_portada(repo, "A")
    _romper_update(repo, monkeypatch)
    antes = _archivos_en_disco()
    llamadas = [
        ("post", f"/admin/comercio/{c['id']}/foto", admin_token),
        ("post", f"/campo/mis-comercios/{c['id']}/foto", tok_agente),
        ("put", "/comercio/perfil/foto", comercio_token(comercio_id=c["id"])),
    ]
    for metodo, ruta, token in llamadas:
        with pytest.raises(RuntimeError):
            getattr(client, metodo)(ruta, headers=_h(token), files=_foto())
        assert _archivos_en_disco() == antes, (ruta, sorted(p.name for p in _archivos_en_disco() - antes))
    assert _en_disco("A.jpg") and repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/A.jpg"


def test_si_falla_guardar_la_portada_del_agente_no_queda_la_anterior_duplicada_en_la_galeria(client, repo, tok_agente, monkeypatch):
    c = _con_portada(repo, "A")
    _romper_update(repo, monkeypatch)
    antes = _archivos_en_disco()
    with pytest.raises(RuntimeError):
        client.post(f"/campo/mis-comercios/{c['id']}/foto", headers=_h(tok_agente), files=_foto())
    assert repo.list_fotos_comercio(c["id"]) == []          # el puntero que se había agregado se deshizo
    assert _archivos_en_disco() == antes


def test_poner_nueva_no_borra_la_portada_vigente_si_la_nueva_fallo(repo, monkeypatch):
    c = _con_portada(repo, "A")
    nueva = _archivo("N.jpg")
    _romper_update(repo, monkeypatch)
    with pytest.raises(RuntimeError):
        portada.poner_nueva(repo, c, nueva, None)
    assert _en_disco("A.jpg") and not _en_disco("N.jpg")


# ── Pillow: tope de píxeles y procesado fuera del event loop

def _png_grande(ancho, alto):
    buf = BytesIO()
    Image.new("1", (ancho, alto), 0).save(buf, format="PNG")
    return buf.getvalue()


def test_pillow_tiene_el_tope_de_40_megapixeles():
    assert imagenes.MAX_PIXELES == 40_000_000
    imagenes.procesar_imagen(_jpeg().getvalue())                    # una foto normal pasa y prepara a Pillow
    assert Image.MAX_IMAGE_PIXELS == 40_000_000


def test_una_imagen_de_mas_de_40_megapixeles_se_rechaza_sin_decodificarla():
    # 45 MP: arriba del tope pero abajo del doble (donde Pillow sólo avisaba con un warning).
    png = _png_grande(7500, 6000)
    assert len(png) < 2_000_000
    with pytest.raises((ValueError, Image.DecompressionBombError, Image.DecompressionBombWarning)):
        imagenes.procesar_imagen(png)
    with pytest.raises(ValueError):
        imagenes.subir_foto_galeria("local", png)
    assert not _archivos_en_disco()                                       # no se guardó nada


def test_una_imagen_justo_en_el_tope_pasa():
    out = imagenes.procesar_imagen(_png_grande(8000, 5000))              # exactamente 40.000.000
    assert Image.open(BytesIO(out)).size[0] <= 1600


def test_el_endpoint_de_subida_contesta_400_ante_una_bomba(client, repo, admin_token):
    c = _comercio(repo)
    files = {"foto": ("bomba.png", BytesIO(_png_grande(7500, 6000)), "image/png")}
    r = client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(admin_token), files=files)
    assert r.status_code == 400, r.text


def test_las_rutas_de_subida_procesan_la_imagen_fuera_del_event_loop(client, repo, admin_token, tok_agente, monkeypatch):
    """Pillow es CPU: en una ruta `async def` bloquea a todos. Cada subida tiene que correr
    en un hilo del pool, donde NO hay un event loop en marcha."""
    c = _con_portada(repo, "A")
    visto = []
    real = imagenes.subir_foto_galeria

    def espia(slug, data):
        try:
            asyncio.get_running_loop()
            visto.append("en el loop")
        except RuntimeError:
            visto.append("en un hilo")
        return real(slug, data)

    for modulo in ("app.api.campo", "app.api.comercio", "app.api.moderacion"):
        monkeypatch.setattr(f"{modulo}.subir_foto_galeria", espia)
    token_com = comercio_token(comercio_id=c["id"])
    assert client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(admin_token), files=_foto()).status_code == 200
    assert client.post(f"/admin/comercio/{c['id']}/fotos", headers=_h(admin_token), files=_foto()).status_code == 200
    assert client.post(f"/campo/mis-comercios/{c['id']}/foto", headers=_h(tok_agente), files=_foto()).status_code == 200
    assert client.post(f"/campo/mis-comercios/{c['id']}/fotos", headers=_h(tok_agente), files=_foto()).status_code == 200
    assert client.put("/comercio/perfil/foto", headers=_h(token_com), files=_foto()).status_code == 200
    assert client.post("/comercio/fotos", headers=_h(token_com), files=_foto()).status_code == 200
    assert visto == ["en un hilo"] * 6, visto


def test_el_comentario_del_delete_fisico_de_la_galeria_esta_en_portada_py():
    """El único DELETE físico de `comercio_fotos` en portada.py se explica por qué es seguro."""
    fuente = (Path(__file__).resolve().parents[1] / "app/services/portada.py").read_text(encoding="utf-8")
    i = fuente.index("repo.delete_foto_comercio(foto[\"id\"], cid)")
    assert "DELETE físico" in fuente[max(0, i - 700):i]
