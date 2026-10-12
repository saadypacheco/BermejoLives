"""QA: huecos de test_portada_y_permisos.py (docs/portada-y-permisos.md).

Lo que el archivo del dev no cubre: aislamiento entre ciudades y comercios, tokens
vencidos / falsificados, permisos del publicador con tokens viejos, entradas
maliciosas, el tope del plan con el intercambio, tamaños de subida contra el
middleware, archivos en disco en los bordes y estados de publicaciones.

BUG-3 (la portada nueva queda huérfana en disco si falla guardarla) se arregló en la
ronda 2 (docs/portada-y-permisos.md): ya no tiene `xfail`.
"""
import os
import time
from io import BytesIO
from pathlib import Path

import jwt as pyjwt
import pytest
from PIL import Image

from app.core import auth
from app.core.config import settings
from app.services.imagenes import guardar_foto_local
from tests.conftest import comercio_token

BASE = "https://api.test/fotos"
AGENTE = "agente@bermejolive.com"


@pytest.fixture(autouse=True)
def _base_publica(monkeypatch):
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _jpeg(lado=10, ruido=False):
    buf = BytesIO()
    if ruido:
        Image.frombytes("RGB", (lado, lado), os.urandom(lado * lado * 3)).save(buf, format="JPEG", quality=95)
    else:
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


def _sembrar(repo, cid, nombres, slug="local", thumbs=True):
    for i, n in enumerate(nombres):
        url = _archivo(f"{n}.jpg", slug)
        thumb = _archivo(f"{n}_t3.jpg", slug) if thumbs else None
        repo.comercio_fotos.append({"id": f"f{i}", "comercio_id": cid, "url": url, "thumb_url": thumb,
                                    "orden": i, "created_at": f"2026-01-01T00:0{i}:00+00:00"})


def _vencido(payload):
    return pyjwt.encode({**payload, "exp": int(time.time()) - 60}, settings.jwt_secret, algorithm="HS256")


# ══════════════════════════════ tokens vencidos, falsificados, vacíos (todas las rutas nuevas)

def _rutas_nuevas(cid="com-p"):
    return [
        ("put", f"/admin/comercio/{cid}/portada", {"json": {"foto_id": "f0"}}),
        ("post", f"/admin/comercio/{cid}/foto", {"files": "foto"}),
        ("post", f"/admin/comercio/{cid}/reactivar", {}),
        ("get", "/admin/comercios/dados-de-baja", {}),
        ("put", f"/campo/mis-comercios/{cid}/portada", {"json": {"foto_id": "f0"}}),
        ("post", f"/campo/mis-comercios/{cid}/foto", {"files": "foto"}),
        ("delete", f"/campo/mis-comercios/{cid}/fotos/f0", {}),
        ("put", "/comercio/portada", {"json": {"foto_id": "f0"}}),
        ("put", "/comercio/perfil/foto", {"files": "foto"}),
        ("post", f"/moderacion/comercios/{cid}/rechazar", {}),
    ]


def _llamar(client, metodo, ruta, extra, token):
    kw = {}
    if token is not None:
        kw["headers"] = _h(token)
    if "json" in extra:
        kw["json"] = extra["json"]
    if "files" in extra:
        kw["files"] = _foto()
    return getattr(client, metodo)(ruta, **kw)


@pytest.mark.parametrize("metodo,ruta,extra", _rutas_nuevas())
def test_token_vencido_basura_o_firmado_con_otra_clave_da_401(client, repo, metodo, ruta, extra):
    c = _con_portada(repo)
    _sembrar(repo, c["id"], ["B"])
    vencidos = [
        _vencido({"sub": "a@x.com", "email": "a@x.com", "rol": "admin", "permisos": ["*"]}),
        _vencido({"sub": "a@x.com", "email": AGENTE, "rol": "agente"}),
        _vencido({"sub": "a@x.com", "rol": "comercio", "comercio_id": c["id"]}),
        "esto.no.es.un.jwt",
        pyjwt.encode({"sub": "a@x.com", "rol": "admin", "permisos": ["*"], "exp": int(time.time()) + 600},
                     "otra-clave-que-no-es-la-del-servidor-0123456789", algorithm="HS256"),
    ]
    for tok in vencidos:
        r = _llamar(client, metodo, ruta, extra, tok)
        assert r.status_code == 401, (metodo, ruta, tok[:20], r.status_code, r.text)
    # Sin cabecera.
    assert _llamar(client, metodo, ruta, extra, None).status_code == 401
    assert repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/A.jpg"
    assert repo.comercios[c["id"]].get("activo", True) is True


def test_token_alg_none_no_pasa(client, repo):
    c = _con_portada(repo)
    import base64
    import json

    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b"=").decode()
    falso = f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'rol': 'admin', 'permisos': ['*'], 'exp': int(time.time()) + 600})}."
    r = client.put(f"/admin/comercio/{c['id']}/portada", headers=_h(falso), json={"foto_id": "f0"})
    assert r.status_code == 401


def test_un_rol_vaciado_desde_equipo_no_puede_nada(client, repo):
    """`permisos: []` es una respuesta (no cae en los roles base): 403 en todo lo nuevo."""
    c = _con_portada(repo)
    _sembrar(repo, c["id"], ["B"])
    vacio = auth.make_token("nadie@x.com", rol="publicador", permisos=[])
    for metodo, ruta, extra in _rutas_nuevas(c["id"]):
        if ruta.startswith(("/comercio", "/campo")):
            continue
        r = _llamar(client, metodo, ruta, extra, vacio)
        assert r.status_code == 403, (metodo, ruta, r.status_code)
    assert repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/A.jpg"


# ══════════════════════════════════ el agente: ciudad ajena, ciudad propia, ninguna salida a «borrar»

def test_agente_de_otra_ciudad_no_toca_nada_del_comercio_ajeno(client, repo):
    c = _con_portada(repo, cargado_por="otro-agente@x.com", ciudad_id="ciu-1")   # Bermejo
    _sembrar(repo, c["id"], ["B"])
    sc = auth.make_agente_token("sc@x.com", ciudad_slug="santa-cruz")
    cid = c["id"]
    assert client.put(f"/campo/mis-comercios/{cid}/portada", headers=_h(sc), json={"foto_id": "f0"}).status_code == 404
    assert client.post(f"/campo/mis-comercios/{cid}/foto", headers=_h(sc), files=_foto()).status_code == 404
    assert client.delete(f"/campo/mis-comercios/{cid}/fotos/f0", headers=_h(sc)).status_code == 404
    r = client.post(f"/campo/mis-comercios/{cid}/fotos", headers=_h(sc), files=_foto(), data={"reemplazar": "f0"})
    assert r.status_code == 404
    assert repo.comercios[cid]["portada_url"] == f"{BASE}/local/A.jpg"
    assert repo.comercios[cid]["portada_pos"] == 30
    assert len(repo.list_fotos_comercio(cid)) == 1 and _en_disco("A.jpg") and _en_disco("B.jpg")


def test_agente_de_la_misma_ciudad_que_no_lo_cargo_cambia_portada_pero_no_borra(client, repo):
    c = _con_portada(repo, cargado_por="otro-agente@x.com", ciudad_id="ciu-1")
    _sembrar(repo, c["id"], ["B"])
    mio = auth.make_agente_token("yo@x.com", ciudad_slug="bermejo")
    cid = c["id"]
    r = client.put(f"/campo/mis-comercios/{cid}/portada", headers=_h(mio), json={"foto_id": "f0"})
    assert r.status_code == 200, r.text
    assert r.json()["portada_url"] == f"{BASE}/local/B.jpg"
    assert client.delete(f"/campo/mis-comercios/{cid}/fotos/f0", headers=_h(mio)).status_code == 403
    assert len(repo.list_fotos_comercio(cid)) == 1
    assert _en_disco("A.jpg") and _en_disco("B.jpg")


def test_agente_sin_ciudad_y_que_no_cargo_el_comercio_recibe_404(client, repo):
    c = _con_portada(repo, cargado_por="otro-agente@x.com")
    sin_ciudad = auth.make_agente_token("yo@x.com")
    assert client.put(f"/campo/mis-comercios/{c['id']}/portada", headers=_h(sin_ciudad),
                      json={"foto_id": "f0"}).status_code == 404


def test_agente_no_puede_dar_de_baja_ni_por_el_patch(client, repo, agente_token):
    """Ni la ruta DELETE ni un `activo=false` colado en el PATCH del agente."""
    c = _comercio(repo, descripcion="x")
    r = client.patch(f"/campo/mis-comercios/{c['id']}", headers=_h(agente_token),
                     json={"activo": False, "direccion": "Calle 1"})
    assert r.status_code == 200, r.text
    assert repo.comercios[c["id"]].get("activo", True) is True
    assert repo.comercios[c["id"]]["direccion"] == "Calle 1"


def test_el_comerciante_tampoco_se_da_de_baja_por_el_perfil(client, repo):
    c = _comercio(repo)
    r = client.put("/comercio/perfil", headers=_h(comercio_token(comercio_id=c["id"])),
                   json={"activo": False, "descripcion": "hola"})
    assert r.status_code in (200, 400), r.text
    assert repo.comercios[c["id"]].get("activo", True) is True


def test_el_agente_no_llega_a_ninguna_ruta_de_admin_que_borra_o_da_de_baja(client, repo, agente_token):
    c = _con_portada(repo)
    _sembrar(repo, c["id"], ["B"])
    h = _h(agente_token)
    cid = c["id"]
    assert client.delete(f"/admin/comercio/{cid}/fotos/f0", headers=h).status_code == 403
    assert client.post(f"/moderacion/comercios/{cid}/rechazar", headers=h).status_code == 403
    assert client.post(f"/admin/comercio/{cid}/reactivar", headers=h).status_code == 403
    assert client.put(f"/admin/comercio/{cid}/portada", headers=h, json={"foto_id": "f0"}).status_code == 403
    assert client.post(f"/admin/comercio/{cid}/foto", headers=h, files=_foto()).status_code == 403
    assert client.put(f"/admin/comercio/{cid}", headers=h, json={"descripcion": "x"}).status_code == 403
    assert client.delete(f"/comercio/fotos/f0", headers=h).status_code == 403
    assert len(repo.list_fotos_comercio(cid)) == 1
    assert repo.comercios[cid].get("activo", True) is True


def test_el_comerciante_no_llega_a_la_baja_ni_a_la_moderacion(client, repo):
    c = _comercio(repo)
    t = comercio_token(comercio_id=c["id"])
    assert client.post(f"/moderacion/comercios/{c['id']}/rechazar", headers=_h(t)).status_code == 403
    assert client.delete(f"/admin/comercio/{c['id']}/fotos/f0", headers=_h(t)).status_code == 403
    assert repo.comercios[c["id"]].get("activo", True) is True


def test_comerciante_con_comercio_inexistente_en_el_token_recibe_404(client, repo):
    r = client.put("/comercio/portada", headers=_h(comercio_token(comercio_id="fantasma")), json={"foto_id": "f0"})
    assert r.status_code == 404


def test_comerciante_a_no_usa_fotos_del_comercio_b_en_ninguna_de_las_tres_rutas(client, repo):
    a = _con_portada(repo)
    b = repo.seed_comercio(id="com-b", slug="bb", nombre="B", whatsapp="591")
    repo.comercio_fotos.append({"id": "de-b", "comercio_id": "com-b", "url": _archivo("Zb.jpg", "bb"),
                                "thumb_url": None, "orden": 0, "created_at": "2026-01-01T00:00:00+00:00"})
    t = comercio_token(comercio_id=a["id"])
    assert client.put("/comercio/portada", headers=_h(t), json={"foto_id": "de-b"}).status_code == 404
    assert client.delete("/comercio/fotos/de-b", headers=_h(t)).status_code in (404,)
    assert [f["id"] for f in repo.list_fotos_comercio("com-b")] == ["de-b"]
    assert _en_disco("Zb.jpg", "bb")
    assert repo.comercios[b["id"]].get("portada_url") is None


# ══════════════════════════════════ publicador: con y sin `comercios.editar`

def test_publicador_con_token_viejo_sin_claim_permisos_edita_fichas(client, repo):
    """Token emitido sin `permisos` (sólo `rol`): cae en ROLES_BASE, que ya trae comercios.editar."""
    repo.seed_comercio(id="cm-1", slug="c1", nombre="C1", whatsapp="59170000001")
    viejo = auth.make_publicador_token("pub@uruku.bo")
    assert client.put("/admin/comercio/cm-1", headers=_h(viejo), json={"descripcion": "ok"}).status_code == 200


def test_publicador_con_permisos_explicitos_viejos_no_edita_hasta_que_renueve_el_token(client, repo):
    """Documenta el efecto de 0146 en sesiones vivas: un token de publicador con
    `permisos: [contenido, moderar]` (emitido antes de la migración, TTL 7 días) sigue en 403."""
    c = _con_portada(repo)
    _sembrar(repo, c["id"], ["B"])
    emitido_antes = auth.make_token("pub@uruku.bo", rol="publicador", permisos=["contenido", "moderar"])
    h = _h(emitido_antes)
    assert client.put(f"/admin/comercio/{c['id']}", headers=h, json={"descripcion": "x"}).status_code == 403
    assert client.put(f"/admin/comercio/{c['id']}/portada", headers=h, json={"foto_id": "f0"}).status_code == 403
    assert client.post(f"/moderacion/comercios/{c['id']}/rechazar", headers=h).status_code == 403
    # Lo que ya podía (moderar) sigue: la galería del modal anda en sólo lectura.
    assert client.get(f"/admin/comercio/{c['id']}/fotos", headers=h).status_code == 200
    assert client.delete(f"/admin/comercio/{c['id']}/fotos/f0", headers=h).status_code == 200


def test_publicador_no_hereda_poderes_de_mas(client, repo):
    c = _comercio(repo)
    pub = auth.make_publicador_token("pub@uruku.bo")
    h = _h(pub)
    assert client.put(f"/admin/comercio/{c['id']}/plan", headers=h, json={"plan": "pro"}).status_code == 403
    assert client.put(f"/campo/mis-comercios/{c['id']}/portada", headers=h, json={"foto_id": "f0"}).status_code == 403
    assert client.delete(f"/campo/mis-comercios/{c['id']}/fotos/f0", headers=h).status_code == 403
    assert client.get("/admin/equipo", headers=h).status_code == 403


def test_el_alcance_de_comercios_editar_para_el_publicador_es_la_ficha_y_no_la_cuenta(client, repo):
    """Ronda 2: con 0146 el publicador corrige FICHAS (`comercios.editar`), pero la CUENTA del
    comercio (WhatsApp = llave de ingreso, `confiable` = publicar sin cola, números autorizados,
    grupos, mensajes) pide `comercios.cuenta`, que el publicador no tiene. Este test fija ese
    alcance; si se vuelve a ensanchar `comercios.editar`, avisa."""
    c = _comercio(repo, whatsapp="59170000001", confiable=False)
    cid = c["id"]
    h = _h(auth.make_publicador_token("pub@uruku.bo"))
    # Lo que SÍ puede: corregir la ficha, también mandando el mismo WhatsApp que ya tiene.
    r = client.put(f"/admin/comercio/{cid}", headers=h, json={"direccion": "Calle 1", "whatsapp": "59170000001"})
    assert r.status_code == 200, r.text
    assert repo.comercios[cid]["direccion"] == "Calle 1"
    assert client.get(f"/admin/comercio/{cid}/numeros", headers=h).status_code == 200      # leer, sí
    assert client.get(f"/admin/comercio/{cid}/grupos", headers=h).status_code == 200
    # Lo que NO puede: tocar la cuenta.
    r = client.put(f"/admin/comercio/{cid}", headers=h, json={"whatsapp": "59171111111"})
    assert r.status_code == 403, r.text
    assert repo.comercios[cid]["whatsapp"] == "59170000001"
    cuenta = [
        ("post", f"/admin/comercio/{cid}/confiable", {"json": {"confiable": True}}),
        ("post", f"/admin/comercio/{cid}/numeros", {"json": {"numero": "59172222222"}}),
        ("post", f"/admin/comercio/{cid}/grupos", {"json": {"grupo_jid": "123@g.us"}}),
        ("delete", f"/admin/comercio/{cid}/grupos/123@g.us", {}),
        ("post", f"/admin/comercio/{cid}/grupo", {}),
        ("post", f"/admin/comercio/{cid}/mensaje", {"json": {"cuerpo": "hola"}}),
    ]
    for metodo, ruta, kw in cuenta:
        r = getattr(client, metodo)(ruta, headers=h, **kw)
        assert r.status_code == 403, (metodo, ruta, r.status_code)
    assert repo.comercios[cid]["confiable"] is False
    assert repo.list_numeros_comercio(cid) == [] and repo.list_mensajes_de_comercio(cid) == []
    # El moderador (que trae `comercios.cuenta`) sí.
    mod = _h(auth.make_token("mod@uruku.bo", rol="moderador"))
    assert client.post(f"/admin/comercio/{cid}/confiable", headers=mod, json={"confiable": True}).status_code == 200
    assert client.put(f"/admin/comercio/{cid}", headers=mod, json={"whatsapp": "59171111111"}).status_code == 200
    assert repo.comercios[cid]["confiable"] is True


# ══════════════════════════════════ intercambio: bordes

def test_el_intercambio_funciona_con_la_galeria_llena_en_el_tope_del_plan(client, repo, admin_token):
    c = _con_portada(repo)
    _sembrar(repo, c["id"], ["B", "C"])
    repo.upsert_plan("gratis", {"fotos_max": 2})
    r = client.put(f"/admin/comercio/{c['id']}/portada", headers=_h(admin_token), json={"foto_id": "f1"})
    assert r.status_code == 200, r.text
    assert r.json()["limite"] == 2 and len(r.json()["fotos"]) == 2
    assert [f["url"].rsplit("/", 1)[1] for f in r.json()["fotos"]] == ["B.jpg", "A.jpg"]
    # Y subir una más sigue chocando con el tope (409), el intercambio no abrió lugar.
    r = client.post(f"/admin/comercio/{c['id']}/fotos", headers=_h(admin_token), files=_foto())
    assert r.status_code == 409


def test_intercambio_sin_miniatura_en_la_galeria_usa_la_foto_grande_como_miniatura(client, repo, admin_token):
    c = _con_portada(repo)
    _sembrar(repo, c["id"], ["B"], thumbs=False)
    r = client.put(f"/admin/comercio/{c['id']}/portada", headers=_h(admin_token), json={"foto_id": "f0"})
    assert r.status_code == 200, r.text
    assert r.json()["portada_url"] == f"{BASE}/local/B.jpg"
    assert r.json()["portada_thumb_url"] == f"{BASE}/local/B.jpg"
    # La A vuelve a la galería con sus dos archivos.
    assert r.json()["fotos"][0]["url"] == f"{BASE}/local/A.jpg"
    assert r.json()["fotos"][0]["thumb_url"] == f"{BASE}/local/A_t3.jpg"


def test_intercambio_con_portada_sin_miniatura(client, repo, admin_token):
    c = _comercio(repo, portada_url=_archivo("A.jpg"), portada_thumb_url=None, portada_pos=10)
    _sembrar(repo, c["id"], ["B"])
    r = client.put(f"/admin/comercio/{c['id']}/portada", headers=_h(admin_token), json={"foto_id": "f0"})
    assert r.status_code == 200, r.text
    assert repo.list_fotos_comercio(c["id"])[0]["url"] == f"{BASE}/local/A.jpg"
    assert repo.list_fotos_comercio(c["id"])[0]["thumb_url"] is None


def test_dos_intercambios_seguidos_con_fotos_distintas_no_pierden_ni_duplican(client, repo, admin_token):
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["B", "C"])
    h = _h(admin_token)
    ruta = f"/admin/comercio/{c['id']}/portada"
    assert client.put(ruta, headers=h, json={"foto_id": "f0"}).status_code == 200      # B portada, galería [A, C]
    assert client.put(ruta, headers=h, json={"foto_id": "f1"}).status_code == 200      # C portada, galería [A, B]
    com = repo.comercios[c["id"]]
    assert com["portada_url"].endswith("/C.jpg")
    assert sorted(_u.rsplit("/", 1)[1] for _u in (f["url"] for f in repo.list_fotos_comercio(c["id"]))) == ["A.jpg", "B.jpg"]
    for n in ("A", "B", "C"):
        assert _en_disco(f"{n}.jpg") and _en_disco(f"{n}_t3.jpg")


def test_reusar_el_mismo_foto_id_despues_de_un_intercambio_vuelve_a_intercambiar(client, repo, admin_token):
    """Documenta (no es bug de spec): el id de la fila queda con OTRA imagen después del
    intercambio. Una pestaña con la lista vieja que repite «Usar como portada» sobre f0
    pone de portada la imagen que ANTES era la portada, no la que la persona veía."""
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["B"])
    h = _h(admin_token)
    ruta = f"/admin/comercio/{c['id']}/portada"
    assert client.put(ruta, headers=h, json={"foto_id": "f0"}).json()["portada_url"].endswith("/B.jpg")
    assert client.put(ruta, headers=h, json={"foto_id": "f0"}).json()["portada_url"].endswith("/A.jpg")


def test_intercambio_sobre_un_comercio_dado_de_baja_funciona_para_el_admin(client, repo, admin_token):
    c = _con_portada(repo, "A", activo=False)
    _sembrar(repo, c["id"], ["B"])
    r = client.put(f"/admin/comercio/{c['id']}/portada", headers=_h(admin_token), json={"foto_id": "f0"})
    assert r.status_code == 200, r.text
    assert repo.comercios[c["id"]]["activo"] is False        # no lo reactiva de rebote


def test_si_falla_borrar_la_fila_sin_portada_previa_la_foto_no_se_pierde(client, repo, admin_token, monkeypatch):
    c = _comercio(repo)
    _sembrar(repo, c["id"], ["B"])

    def roto(*a, **k):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "delete_foto_comercio", roto)
    with pytest.raises(RuntimeError):
        client.put(f"/admin/comercio/{c['id']}/portada", headers=_h(admin_token), json={"foto_id": "f0"})
    # La portada ya cambió y la foto sigue en la galería (repetida un rato, nunca perdida).
    assert repo.comercios[c["id"]]["portada_url"].endswith("/B.jpg")
    assert [f["id"] for f in repo.list_fotos_comercio(c["id"])] == ["f0"]
    assert _en_disco("B.jpg")


# ══════════════════════════════════ entradas maliciosas / inválidas

@pytest.mark.parametrize("cuerpo,esperado", [
    ({"foto_id": ""}, 422),
    ({"foto_id": "x" * 65}, 422),
    ({"foto_id": None}, 422),
    ({"foto_id": 5}, 422),
    ({"foto_id": ["f0"]}, 422),
    ({"foto_id": {"$ne": ""}}, 422),
    ({}, 422),
])
def test_foto_id_invalido_es_422_y_no_cambia_nada(client, repo, admin_token, cuerpo, esperado):
    c = _con_portada(repo)
    _sembrar(repo, c["id"], ["B"])
    r = client.put(f"/admin/comercio/{c['id']}/portada", headers=_h(admin_token), json=cuerpo)
    assert r.status_code == esperado, r.text
    assert repo.comercios[c["id"]]["portada_url"].endswith("/A.jpg")
    assert len(repo.list_fotos_comercio(c["id"])) == 1


@pytest.mark.parametrize("fid", ["f0' OR '1'='1", "f0; DROP TABLE comercio_fotos;--", "../../etc/passwd", "f0\x00", "%00", "<script>alert(1)</script>"])
def test_foto_id_malicioso_es_404_sin_efecto(client, repo, admin_token, fid):
    c = _con_portada(repo)
    _sembrar(repo, c["id"], ["B"])
    r = client.put(f"/admin/comercio/{c['id']}/portada", headers=_h(admin_token), json={"foto_id": fid})
    assert r.status_code in (404, 422), r.text
    assert repo.comercios[c["id"]]["portada_url"].endswith("/A.jpg")
    assert len(repo.list_fotos_comercio(c["id"])) == 1


def test_cuerpo_que_no_es_json_es_422(client, repo, admin_token):
    c = _con_portada(repo)
    r = client.put(f"/admin/comercio/{c['id']}/portada", headers={**_h(admin_token), "Content-Type": "application/json"},
                   content=b"{no es json")
    assert r.status_code == 422
    r = client.put(f"/admin/comercio/{c['id']}/portada", headers=_h(admin_token), data={"foto_id": "f0"})
    assert r.status_code == 422                       # form-data en vez de JSON


def test_cuerpo_gigante_a_la_ruta_de_portada_es_413_sin_leerlo(client, repo, admin_token):
    c = _con_portada(repo)
    r = client.put(f"/admin/comercio/{c['id']}/portada", headers={**_h(admin_token), "Content-Type": "application/json"},
                   content=b'{"foto_id": "' + b"a" * (3 * 1024 * 1024) + b'"}')
    assert r.status_code == 413


def test_ids_de_comercio_raros_en_la_ruta(client, repo, admin_token):
    for cid in ("..%2F..%2Fetc", "no-existe", "%27%20OR%201%3D1--", "a" * 300):
        assert client.put(f"/admin/comercio/{cid}/portada", headers=_h(admin_token),
                          json={"foto_id": "f0"}).status_code == 404, cid
        assert client.post(f"/admin/comercio/{cid}/reactivar", headers=_h(admin_token)).status_code == 404, cid
    assert client.post("/moderacion/comercios/no-existe/rechazar", headers=_h(admin_token)).status_code == 404


@pytest.mark.parametrize("nombre,tipo,contenido", [
    ("a.svg", "image/svg+xml", b"<svg xmlns='http://www.w3.org/2000/svg'><script>alert(1)</script></svg>"),
    ("a.html", "text/html", b"<html><script>alert(1)</script></html>"),
    ("a.jpg", "image/jpeg", b"GIF89a esto no es un jpeg"),
    ("a.php", "image/jpeg", b"<?php system($_GET['c']); ?>"),
    ("a.jpg", "image/jpeg", b"\xff\xd8\xff\xe0 truncado"),
])
def test_subir_portada_que_no_es_imagen_se_rechaza_en_las_tres_rutas(client, repo, admin_token, agente_token, nombre, tipo, contenido):
    c = _con_portada(repo)
    antes = {p.name for p in Path(settings.fotos_dir).rglob("*") if p.is_file()}
    casos = [
        ("post", f"/admin/comercio/{c['id']}/foto", admin_token),
        ("post", f"/campo/mis-comercios/{c['id']}/foto", agente_token),
        ("put", "/comercio/perfil/foto", comercio_token(comercio_id=c["id"])),
    ]
    for metodo, ruta, tok in casos:
        r = getattr(client, metodo)(ruta, headers=_h(tok), files={"foto": (nombre, BytesIO(contenido), tipo)})
        assert 400 <= r.status_code < 500, (ruta, r.status_code, r.text)
    assert repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/A.jpg"
    assert repo.comercios[c["id"]]["portada_pos"] == 30
    assert _en_disco("A.jpg")
    assert {p.name for p in Path(settings.fotos_dir).rglob("*") if p.is_file()} == antes


def test_nombre_de_archivo_con_path_traversal_no_escapa_de_la_carpeta_de_fotos(client, repo, admin_token):
    c = _con_portada(repo)
    raiz = Path(settings.fotos_dir).parent
    antes = {p for p in raiz.rglob("*") if p.is_file()}
    r = client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(admin_token),
                    files={"foto": ("../../../evil.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200, r.text
    nuevos = {p for p in raiz.rglob("*") if p.is_file()} - antes
    assert nuevos, "debería haber guardado la portada nueva"
    for p in nuevos:
        assert Path(settings.fotos_dir).resolve() in p.resolve().parents, p
        assert "evil" not in p.name


@pytest.mark.parametrize("ciudad", ["' or 1=1 --", "bermejo;drop table comercios", "%", "../x", "ñandú"])
def test_dados_de_baja_con_ciudad_maliciosa_no_rompe(client, repo, admin_token, ciudad):
    repo.seed_comercio(id="cm-off", slug="off", nombre="Off", whatsapp="591", activo=False, ciudad_id="ciu-1")
    r = client.get("/admin/comercios/dados-de-baja", headers=_h(admin_token), params={"ciudad": ciudad})
    assert r.status_code == 200, r.text
    assert r.json()["items"] == []


def test_dados_de_baja_con_ciudad_demasiado_larga_es_422(client, admin_token):
    assert client.get("/admin/comercios/dados-de-baja", headers=_h(admin_token),
                      params={"ciudad": "a" * 61}).status_code == 422


# ══════════════════════════════════ tamaños de subida contra el middleware

def test_una_portada_real_de_unos_mb_pasa_el_middleware_en_las_tres_rutas(client, repo, admin_token, agente_token):
    c = _con_portada(repo)
    grande = _jpeg(lado=1500, ruido=True).getvalue()
    assert len(grande) > 2 * 1024 * 1024, "la imagen de prueba debe pasar el tope por defecto de 2 MB"
    casos = [
        ("post", f"/admin/comercio/{c['id']}/foto", admin_token),
        ("post", f"/campo/mis-comercios/{c['id']}/foto", agente_token),
        ("put", "/comercio/perfil/foto", comercio_token(comercio_id=c["id"])),
    ]
    for metodo, ruta, tok in casos:
        r = getattr(client, metodo)(ruta, headers=_h(tok), files={"foto": ("g.jpg", BytesIO(grande), "image/jpeg")})
        assert r.status_code == 200, (ruta, r.status_code, r.text[:200])


def test_portada_de_mas_de_15_mb_es_413_en_las_tres_rutas(client, repo, admin_token, agente_token):
    c = _con_portada(repo)
    enorme = b"\xff\xd8\xff" + os.urandom(16 * 1024 * 1024)
    casos = [
        ("post", f"/admin/comercio/{c['id']}/foto", admin_token),
        ("post", f"/campo/mis-comercios/{c['id']}/foto", agente_token),
        ("put", "/comercio/perfil/foto", comercio_token(comercio_id=c["id"])),
    ]
    for metodo, ruta, tok in casos:
        r = getattr(client, metodo)(ruta, headers=_h(tok), files={"foto": ("g.jpg", BytesIO(enorme), "image/jpeg")})
        assert r.status_code == 413, (ruta, r.status_code)
    assert repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/A.jpg"
    assert _en_disco("A.jpg")


def test_subida_fallida_502_deja_la_portada_y_los_archivos_como_estaban(client, repo, admin_token, monkeypatch):
    c = _con_portada(repo)
    from app.api import moderacion
    monkeypatch.setattr(moderacion, "subir_foto_galeria", lambda *a, **k: (None, None))
    r = client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(admin_token), files=_foto())
    assert r.status_code == 502
    assert repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/A.jpg"
    assert repo.comercios[c["id"]]["portada_pos"] == 30
    assert _en_disco("A.jpg") and _en_disco("A_t3.jpg")


# ══════════════════════════════════ archivos en disco: bordes de la portada nueva

def test_portada_nueva_conserva_el_archivo_si_solo_la_miniatura_esta_en_la_galeria(client, repo, admin_token):
    c = _con_portada(repo, "A")
    repo.comercio_fotos.append({"id": "f0", "comercio_id": c["id"], "url": _archivo("X.jpg"),
                                "thumb_url": f"{BASE}/local/A_t3.jpg", "orden": 0, "created_at": "2026-01-01T00:00:00+00:00"})
    r = client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(admin_token), files=_foto())
    assert r.status_code == 200, r.text
    assert _en_disco("A_t3.jpg")            # la galería la muestra
    assert not _en_disco("A.jpg")           # esa nadie la usa


def test_portada_nueva_conserva_el_archivo_si_una_publicacion_usa_solo_la_miniatura(client, repo, admin_token):
    c = _con_portada(repo, "A")
    repo.publicaciones.append({"id": "pub-t", "activo": True, "estado": "aprobado", "comercio_id": c["id"],
                               "imagen_url": f"{BASE}/local/A_t3.jpg"})
    r = client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(admin_token), files=_foto())
    assert r.status_code == 200, r.text
    assert _en_disco("A_t3.jpg") and not _en_disco("A.jpg")


def test_portada_nueva_borra_el_archivo_si_la_unica_publicacion_que_lo_usaba_esta_inactiva(client, repo, admin_token):
    c = _con_portada(repo, "A")
    repo.publicaciones.append({"id": "pub-baja", "activo": False, "estado": "rechazado", "comercio_id": c["id"],
                               "imagen_url": f"{BASE}/local/A.jpg"})
    assert client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(admin_token), files=_foto()).status_code == 200
    assert not _en_disco("A.jpg")


def test_si_la_limpieza_del_disco_falla_la_portada_igual_cambia(client, repo, admin_token, monkeypatch):
    c = _con_portada(repo, "A")

    def roto(*a, **k):
        raise OSError("disco de solo lectura")
    monkeypatch.setattr(repo, "imagen_en_uso", roto)
    r = client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(admin_token), files=_foto())
    assert r.status_code == 200, r.text
    assert repo.comercios[c["id"]]["portada_url"] != f"{BASE}/local/A.jpg"
    assert repo.comercios[c["id"]]["portada_pos"] is None


def test_intercambio_y_despues_portada_nueva_conserva_la_vieja_en_la_galeria_y_borra_la_intercambiada(client, repo, admin_token):
    """A portada, B en la galería. Intercambio: B portada, A en la galería. Subir N: N portada,
    A sigue en la galería (archivos vivos), B ya no la usa nadie (archivos fuera)."""
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["B"])
    h = _h(admin_token)
    assert client.put(f"/admin/comercio/{c['id']}/portada", headers=h, json={"foto_id": "f0"}).status_code == 200
    assert client.post(f"/admin/comercio/{c['id']}/foto", headers=h, files=_foto()).status_code == 200
    assert [f["url"].rsplit("/", 1)[1] for f in repo.list_fotos_comercio(c["id"])] == ["A.jpg"]
    assert _en_disco("A.jpg") and _en_disco("A_t3.jpg")
    assert not _en_disco("B.jpg") and not _en_disco("B_t3.jpg")
    assert repo.comercios[c["id"]]["portada_pos"] is None


def test_borrar_de_la_galeria_la_foto_que_era_portada_vieja_no_toca_la_portada_nueva(client, repo, admin_token):
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["B"])
    h = _h(admin_token)
    client.put(f"/admin/comercio/{c['id']}/portada", headers=h, json={"foto_id": "f0"})   # B portada, A galería
    assert client.delete(f"/admin/comercio/{c['id']}/fotos/f0", headers=h).status_code == 200
    assert not _en_disco("A.jpg")                           # esa sí se borra: ya no es nada
    assert _en_disco("B.jpg") and _en_disco("B_t3.jpg")      # la portada intacta


def test_borrar_de_la_galeria_una_foto_igual_a_la_portada_no_borra_el_archivo(client, repo, admin_token):
    """Portada A y la galería también tiene A (duplicada): borrar la fila no puede borrar el archivo."""
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["A"])
    assert client.delete(f"/admin/comercio/{c['id']}/fotos/f0", headers=_h(admin_token)).status_code == 200
    assert _en_disco("A.jpg") and _en_disco("A_t3.jpg")


def test_si_falla_guardar_la_portada_nueva_no_queda_el_archivo_nuevo_huerfano(client, repo, admin_token, monkeypatch):
    c = _con_portada(repo, "A")
    antes = {p for p in Path(settings.fotos_dir).rglob("*") if p.is_file()}

    def roto(*a, **k):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "update_comercio", roto)
    with pytest.raises(RuntimeError):
        client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(admin_token), files=_foto())
    despues = {p for p in Path(settings.fotos_dir).rglob("*") if p.is_file()}
    assert despues == antes, f"huérfanos: {sorted(p.name for p in despues - antes)}"


# ══════════════════════════════════ baja / reactivación

def test_reactivar_es_idempotente_y_no_toca_otros_comercios(client, repo, admin_token):
    repo.seed_comercio(id="cm-1", slug="c1", nombre="C1", whatsapp="591", activo=False)
    repo.seed_comercio(id="cm-2", slug="c2", nombre="C2", whatsapp="592", activo=False)
    h = _h(admin_token)
    assert client.post("/admin/comercio/cm-1/reactivar", headers=h).status_code == 200
    assert client.post("/admin/comercio/cm-1/reactivar", headers=h).status_code == 200
    assert repo.comercios["cm-1"]["activo"] is True and repo.comercios["cm-2"]["activo"] is False


def test_dar_de_baja_dos_veces_no_rompe_y_lo_deja_en_la_lista_una_sola_vez(client, repo, admin_token):
    repo.seed_comercio(id="cm-1", slug="c1", nombre="C1", whatsapp="591")
    h = _h(admin_token)
    assert client.post("/moderacion/comercios/cm-1/rechazar", headers=h).status_code == 200
    assert client.post("/moderacion/comercios/cm-1/rechazar", headers=h).status_code == 200
    assert [i["id"] for i in client.get("/admin/comercios/dados-de-baja", headers=h).json()["items"]] == ["cm-1"]


def test_dar_de_baja_no_borra_fotos_ni_archivos_ni_publicaciones(client, repo, admin_token):
    c = _con_portada(repo)
    _sembrar(repo, c["id"], ["B"])
    repo.publicaciones.append({"id": "p1", "activo": True, "estado": "aprobado", "comercio_id": c["id"]})
    assert client.post(f"/moderacion/comercios/{c['id']}/rechazar", headers=_h(admin_token)).status_code == 200
    assert len(repo.list_fotos_comercio(c["id"])) == 1
    assert _en_disco("A.jpg") and _en_disco("B.jpg")
    assert repo.publicaciones[0]["estado"] == "aprobado"
    assert client.post(f"/admin/comercio/{c['id']}/reactivar", headers=_h(admin_token)).status_code == 200
    assert repo.comercios[c["id"]]["portada_url"].endswith("/A.jpg")


def test_el_moderador_con_rol_base_da_de_baja_y_reactiva(client, repo):
    repo.seed_comercio(id="cm-1", slug="c1", nombre="C1", whatsapp="591")
    mod = auth.make_token("mod@uruku.bo", rol="moderador")
    assert client.post("/moderacion/comercios/cm-1/rechazar", headers=_h(mod)).status_code == 200
    assert client.get("/admin/comercios/dados-de-baja", headers=_h(mod)).status_code == 200
    assert client.post("/admin/comercio/cm-1/reactivar", headers=_h(mod)).status_code == 200


# ══════════════════════════════════ bajar una publicación ya aprobada

def _pub(repo, pid="pub-ok", estado="aprobado", **kw):
    p = {"id": pid, "activo": True, "estado": estado, "comercio_id": "com-p", "tipo": "oferta", "titulo": "Oferta", **kw}
    repo.publicaciones.append(p)
    return p


def test_bajar_dos_veces_la_misma_publicacion_es_idempotente(client, repo, admin_token):
    _pub(repo)
    h = _h(admin_token)
    for _ in range(2):
        r = client.post("/moderacion/publicaciones/pub-ok", headers=h, json={"estado": "rechazado", "motivo": "x"})
        assert r.status_code == 200, r.text
    assert repo.publicaciones[0]["estado"] == "rechazado"


def test_bajar_con_estado_invalido_o_publicacion_inexistente(client, repo, admin_token):
    _pub(repo)
    h = _h(admin_token)
    assert client.post("/moderacion/publicaciones/pub-ok", headers=h, json={"estado": "borrado"}).status_code == 400
    assert client.post("/moderacion/publicaciones/pub-ok", headers=h, json={"estado": "pendiente"}).status_code in (200, 400)
    assert client.post("/moderacion/publicaciones/no-existe", headers=h, json={"estado": "rechazado"}).status_code == 404
    assert client.post("/moderacion/publicaciones/pub-ok", headers=h, json={}).status_code == 422


def test_bajar_una_publicacion_no_borra_su_imagen_ni_toca_otras(client, repo, admin_token):
    _pub(repo, "pub-ok", imagen_url=_archivo("O.jpg"))
    _pub(repo, "pub-otra", imagen_url=_archivo("P.jpg"))
    assert client.post("/moderacion/publicaciones/pub-ok", headers=_h(admin_token),
                       json={"estado": "rechazado", "motivo": "x"}).status_code == 200
    assert _en_disco("O.jpg")
    assert repo.publicaciones[1]["estado"] == "aprobado"


def test_bajar_no_descarta_la_difusion_de_otras_publicaciones(client, repo, admin_token):
    _pub(repo, "pub-ok")
    _pub(repo, "pub-otra")
    repo.difusion.append({"id": "d1", "publicacion_id": "pub-ok", "estado": "pendiente"})
    repo.difusion.append({"id": "d2", "publicacion_id": "pub-otra", "estado": "pendiente"})
    repo.difusion.append({"id": "d3", "publicacion_id": "pub-ok", "estado": "enviado"})
    assert client.post("/moderacion/publicaciones/pub-ok", headers=_h(admin_token),
                       json={"estado": "rechazado", "motivo": "x"}).status_code == 200
    assert [d["estado"] for d in repo.difusion] == ["omitido", "pendiente", "enviado"]


def test_si_descartar_la_difusion_falla_la_baja_igual_queda_hecha(client, repo, admin_token, monkeypatch):
    _pub(repo)

    def roto(*a, **k):
        raise RuntimeError("cola caída")
    monkeypatch.setattr(repo, "descartar_difusion_de", roto)
    r = client.post("/moderacion/publicaciones/pub-ok", headers=_h(admin_token), json={"estado": "rechazado", "motivo": "x"})
    assert r.status_code == 200
    assert repo.publicaciones[0]["estado"] == "rechazado"


def test_el_agente_y_el_comerciante_no_bajan_publicaciones_ajenas_por_la_moderacion(client, repo, agente_token):
    _pub(repo)
    assert client.post("/moderacion/publicaciones/pub-ok", headers=_h(agente_token), json={"estado": "rechazado"}).status_code == 403
    assert client.get("/moderacion/publicaciones?estado=aprobado", headers=_h(agente_token)).status_code == 403
    assert repo.publicaciones[0]["estado"] == "aprobado"


def test_el_listado_de_aprobadas_exige_login(client, repo):
    assert client.get("/moderacion/publicaciones?estado=aprobado").status_code == 401
