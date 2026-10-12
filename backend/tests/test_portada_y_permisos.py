"""Portada desde la galería, portada nueva, quién borra qué (docs/portada-y-permisos.md).

Criterios que toca el backend:
  1. «Usar como portada» intercambia portada y foto de galería, igual en los tres perfiles.
  2. Subir una portada nueva borra la anterior del disco (si la galería no la usa) y reinicia el recorte.
  3. El admin cambia la portada (POST /admin/comercio/{id}/foto).
  4. El agente no borra fotos, no reemplaza en el tope y no da de baja comercios.
  5. El publicador guarda cambios en una ficha (migración 0146 + ROLES_BASE).
  6. El admin da de baja, ve los dados de baja y reactiva.
  7. El admin baja una oferta ya publicada.
"""
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.core import auth
from app.core.config import settings
from app.core.permisos import ROLES_BASE, tiene
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


def _jpeg():
    buf = BytesIO()
    Image.new("RGB", (10, 10), "green").save(buf, format="JPEG")
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
    return repo.seed_comercio(id="com-p", slug="local", nombre="Local", whatsapp="59170000001",
                              confiable=True, cargado_por=AGENTE, **kw)


def _sembrar(repo, cid, nombres, slug="local"):
    """Fotos de galería con archivos reales: f0, f1... en el orden dado."""
    for i, n in enumerate(nombres):
        url = _archivo(f"{n}.jpg", slug)
        thumb = _archivo(f"{n}_t3.jpg", slug)
        repo.comercio_fotos.append({"id": f"f{i}", "comercio_id": cid, "url": url, "thumb_url": thumb,
                                    "orden": i, "created_at": f"2026-01-01T00:0{i}:00+00:00"})


def _con_portada(repo, nombre="A", **kw):
    url, thumb = _archivo(f"{nombre}.jpg"), _archivo(f"{nombre}_t3.jpg")
    return _comercio(repo, portada_url=url, portada_thumb_url=thumb, portada_pos=30, **kw)


def _urls_galeria(repo, cid):
    return [f["url"].rsplit("/", 1)[1] for f in repo.list_fotos_comercio(cid)]


@pytest.fixture
def lados(agente_token, admin_token):
    return {"comercio": comercio_token(comercio_id="com-p"), "agente": agente_token, "admin": admin_token}


def _rutas(cid):
    return {
        "comercio": ("/comercio/portada", "/comercio/perfil/foto", "put"),
        "agente": (f"/campo/mis-comercios/{cid}/portada", f"/campo/mis-comercios/{cid}/foto", "post"),
        "admin": (f"/admin/comercio/{cid}/portada", f"/admin/comercio/{cid}/foto", "post"),
    }


# ══════════════════════════ 1. «Usar como portada»: intercambio, en los tres perfiles

@pytest.mark.parametrize("lado", ["comercio", "agente", "admin"])
def test_usar_como_portada_intercambia_y_no_borra_archivos(client, repo, lados, lado):
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["B", "C"])
    ruta = _rutas(c["id"])[lado][0]

    r = client.put(ruta, headers=_h(lados[lado]), json={"foto_id": "f0"})

    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["portada_url"] == f"{BASE}/local/B.jpg"
    assert j["portada_thumb_url"] == f"{BASE}/local/B_t3.jpg"
    # La galería: la portada anterior ocupa el lugar de la elegida; misma cantidad.
    assert [f["url"].rsplit("/", 1)[1] for f in j["fotos"]] == ["A.jpg", "C.jpg"]
    assert [f["id"] for f in j["fotos"]] == ["f0", "f1"]
    assert j["limite"] == 50
    # En la base.
    assert repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/B.jpg"
    assert repo.comercios[c["id"]]["portada_pos"] is None
    assert _urls_galeria(repo, c["id"]) == ["A.jpg", "C.jpg"]
    assert len(repo.list_fotos_comercio(c["id"])) == 2
    # Ningún archivo se borró.
    for n in ("A.jpg", "A_t3.jpg", "B.jpg", "B_t3.jpg", "C.jpg", "C_t3.jpg"):
        assert _en_disco(n), n


@pytest.mark.parametrize("lado", ["comercio", "agente", "admin"])
def test_usar_como_portada_una_foto_ajena_o_inexistente_es_404(client, repo, lados, lado):
    c = _con_portada(repo, "A")
    otro = repo.seed_comercio(id="com-otro", slug="otro", nombre="Otro")
    repo.comercio_fotos.append({"id": "ajena", "comercio_id": otro["id"], "url": _archivo("Z.jpg", "otro"),
                                "thumb_url": None, "orden": 0, "created_at": "2026-01-01T00:00:00+00:00"})
    ruta = _rutas(c["id"])[lado][0]
    for fid in ("ajena", "no-existe"):
        r = client.put(ruta, headers=_h(lados[lado]), json={"foto_id": fid})
        assert r.status_code == 404, (lado, fid)
    assert repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/A.jpg"
    assert repo.comercios[c["id"]]["portada_pos"] == 30
    assert "ajena" in [f["id"] for f in repo.list_fotos_comercio(otro["id"])]


def test_usar_como_portada_sin_foto_id_es_422(client, repo, lados):
    c = _con_portada(repo)
    r = client.put(_rutas(c["id"])["admin"][0], headers=_h(lados["admin"]), json={})
    assert r.status_code == 422


def test_sin_portada_anterior_la_galeria_queda_con_una_menos(client, repo, lados):
    c = _comercio(repo)
    _sembrar(repo, c["id"], ["B", "C"])
    r = client.put(_rutas(c["id"])["admin"][0], headers=_h(lados["admin"]), json={"foto_id": "f0"})
    assert r.status_code == 200, r.text
    assert r.json()["portada_url"] == f"{BASE}/local/B.jpg"
    assert _urls_galeria(repo, c["id"]) == ["C.jpg"]
    assert _en_disco("B.jpg") and _en_disco("C.jpg")           # sin borrar archivos


def test_si_la_portada_anterior_ya_esta_en_la_galeria_no_se_repite(client, repo, lados):
    """La portada A también figura en la galería (f1): al elegir B no entra una A repetida."""
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["B", "A"])
    r = client.put(_rutas(c["id"])["admin"][0], headers=_h(lados["admin"]), json={"foto_id": "f0"})
    assert r.status_code == 200, r.text
    assert r.json()["portada_url"] == f"{BASE}/local/B.jpg"
    assert _urls_galeria(repo, c["id"]) == ["A.jpg"]
    assert _en_disco("A.jpg") and _en_disco("B.jpg")


def test_elegir_la_foto_que_ya_es_la_portada_no_cambia_nada(client, repo, lados):
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["A", "C"])
    r = client.put(_rutas(c["id"])["admin"][0], headers=_h(lados["admin"]), json={"foto_id": "f0"})
    assert r.status_code == 200, r.text
    assert r.json()["portada_url"] == f"{BASE}/local/A.jpg"
    assert len(repo.list_fotos_comercio(c["id"])) == 2
    assert repo.comercios[c["id"]]["portada_pos"] == 30


def test_si_falla_cambiar_la_portada_la_galeria_queda_como_estaba(client, repo, lados, monkeypatch):
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["B", "C"])

    def roto(*a, **k):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "update_comercio", roto)
    with pytest.raises(RuntimeError):
        client.put(_rutas(c["id"])["admin"][0], headers=_h(lados["admin"]), json={"foto_id": "f0"})
    assert _urls_galeria(repo, c["id"]) == ["B.jpg", "C.jpg"]            # deshecho
    assert repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/A.jpg"


def test_usar_como_portada_pide_permiso(client, repo, lados):
    c = _con_portada(repo)
    _sembrar(repo, c["id"], ["B"])
    # Admin: sin token 401; con un comercio ajeno al panel 403; un agente de otra ciudad 404.
    ruta = _rutas(c["id"])["admin"][0]
    assert client.put(ruta, json={"foto_id": "f0"}).status_code == 401
    assert client.put(ruta, headers=_h(lados["comercio"]), json={"foto_id": "f0"}).status_code == 403
    sin_editar = auth.make_token("mod@x.com", rol="x", permisos=["moderar"])
    assert client.put(ruta, headers=_h(sin_editar), json={"foto_id": "f0"}).status_code == 403
    otro_agente = auth.make_agente_token("otro@x.com")
    r = client.put(_rutas(c["id"])["agente"][0], headers=_h(otro_agente), json={"foto_id": "f0"})
    assert r.status_code == 404
    assert repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/A.jpg"


# ══════════════════════════════════ 2 y 3. Portada nueva: borra la vieja y reinicia el recorte

def _subir_portada(client, lado, token, cid):
    _, ruta, metodo = _rutas(cid)[lado]
    return getattr(client, metodo)(ruta, headers=_h(token), files=_foto())


# El agente no está acá a propósito: no borra archivos (la anterior pasa a la galería);
# su caso está en test_portada_ronda2.py.
@pytest.mark.parametrize("lado", ["comercio", "admin"])
def test_portada_nueva_borra_la_anterior_y_reinicia_el_recorte(client, repo, lados, lado):
    c = _con_portada(repo, "A")
    r = _subir_portada(client, lado, lados[lado], c["id"])

    assert r.status_code == 200, r.text
    nueva = repo.comercios[c["id"]]
    assert nueva["portada_url"] != f"{BASE}/local/A.jpg"
    assert nueva["portada_pos"] is None
    assert not _en_disco("A.jpg") and not _en_disco("A_t3.jpg")      # la anterior se fue del disco
    assert (Path(settings.fotos_dir) / nueva["portada_url"].split("/fotos/", 1)[1]).exists()
    assert (Path(settings.fotos_dir) / nueva["portada_thumb_url"].split("/fotos/", 1)[1]).exists()


def test_el_admin_cambia_la_portada_y_recibe_el_comercio(client, repo, lados):
    c = _con_portada(repo, "A")
    r = client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(lados["admin"]), files=_foto())
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["ok"] is True
    assert j["comercio"]["id"] == c["id"]
    assert j["comercio"]["portada_url"] == repo.comercios[c["id"]]["portada_url"]
    assert j["comercio"]["portada_pos"] is None


@pytest.mark.parametrize("lado", ["comercio", "agente", "admin"])
def test_portada_nueva_no_borra_la_anterior_si_la_galeria_la_usa(client, repo, lados, lado):
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["A"])               # la galería tiene la misma foto
    r = _subir_portada(client, lado, lados[lado], c["id"])
    assert r.status_code == 200, r.text
    assert _en_disco("A.jpg") and _en_disco("A_t3.jpg")
    assert len(repo.list_fotos_comercio(c["id"])) == 1


def test_portada_nueva_no_toca_la_galeria_ni_sus_archivos(client, repo, lados):
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["B", "C"])
    r = _subir_portada(client, "admin", lados["admin"], c["id"])
    assert r.status_code == 200, r.text
    assert _urls_galeria(repo, c["id"]) == ["B.jpg", "C.jpg"]
    assert _en_disco("B.jpg") and _en_disco("C.jpg")
    assert not _en_disco("A.jpg")


def test_portada_nueva_sin_portada_anterior_funciona(client, repo, lados):
    c = _comercio(repo)
    r = _subir_portada(client, "admin", lados["admin"], c["id"])
    assert r.status_code == 200, r.text
    assert repo.comercios[c["id"]]["portada_url"]


def test_portada_nueva_no_borra_archivos_ajenos_a_la_galeria(client, repo, lados, tmp_path):
    """La portada anterior apunta fuera de nuestra carpeta: no se toca nada."""
    afuera = tmp_path / "secreto.jpg"
    afuera.write_bytes(b"no me toques")
    c = _comercio(repo, portada_url=f"{BASE}/../secreto.jpg", portada_thumb_url="https://otro.com/x.jpg")
    r = _subir_portada(client, "admin", lados["admin"], c["id"])
    assert r.status_code == 200, r.text
    assert afuera.exists()


def test_portada_nueva_no_borra_un_archivo_que_una_publicacion_usa(client, repo, lados):
    c = _con_portada(repo, "A")
    repo.publicaciones.append({"id": "pub-x", "activo": True, "estado": "aprobado", "comercio_id": c["id"],
                               "imagen_url": f"{BASE}/local/A.jpg"})
    r = _subir_portada(client, "admin", lados["admin"], c["id"])
    assert r.status_code == 200, r.text
    assert _en_disco("A.jpg")                        # una oferta la sigue mostrando
    assert not _en_disco("A_t3.jpg")


def test_portada_nueva_valida_la_entrada(client, repo, lados):
    c = _con_portada(repo)
    ruta = f"/admin/comercio/{c['id']}/foto"
    assert client.post(ruta, headers=_h(lados["admin"]),
                       files={"foto": ("f.jpg", BytesIO(b""), "image/jpeg")}).status_code == 400
    assert client.post(ruta, headers=_h(lados["admin"]),
                       files={"foto": ("f.txt", BytesIO(b"no soy una imagen"), "text/plain")}).status_code == 400
    assert client.post("/admin/comercio/no-existe/foto", headers=_h(lados["admin"]), files=_foto()).status_code == 404
    assert repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/A.jpg"       # nada cambió
    assert repo.comercios[c["id"]]["portada_pos"] == 30


def test_portada_nueva_del_admin_pide_comercios_editar(client, repo, lados):
    c = _con_portada(repo)
    ruta = f"/admin/comercio/{c['id']}/foto"
    assert client.post(ruta, files=_foto()).status_code == 401
    assert client.post(ruta, headers=_h(lados["comercio"]), files=_foto()).status_code == 403
    solo_moderar = auth.make_token("mod@x.com", rol="x", permisos=["moderar"])
    assert client.post(ruta, headers=_h(solo_moderar), files=_foto()).status_code == 403
    assert repo.comercios[c["id"]]["portada_url"] == f"{BASE}/local/A.jpg"


# ══════════════════════════════════════════════ 4. El agente sólo sube

def test_el_agente_no_tiene_la_ruta_de_dar_de_baja(client, repo, lados):
    c = _comercio(repo)
    r = client.delete(f"/campo/mis-comercios/{c['id']}", headers=_h(lados["agente"]))
    assert r.status_code in (404, 405)
    assert repo.comercios[c["id"]].get("activo", True) is True
    # La ruta DELETE ya no está registrada en la app.
    from app.main import app
    assert not any(getattr(r, "path", "") == "/campo/mis-comercios/{comercio_id}"
                   and "DELETE" in (getattr(r, "methods", None) or ()) for r in app.routes)


def test_el_agente_no_borra_fotos(client, repo, lados):
    c = _comercio(repo)
    _sembrar(repo, c["id"], ["B"])
    r = client.delete(f"/campo/mis-comercios/{c['id']}/fotos/f0", headers=_h(lados["agente"]))
    assert r.status_code == 403
    assert r.json()["detail"] == "Las fotos las borra URUKU. Avisale al admin."
    assert len(repo.list_fotos_comercio(c["id"])) == 1 and _en_disco("B.jpg")


def test_el_agente_no_reemplaza_pero_el_409_de_tope_sigue_igual(client, repo, lados):
    c = _comercio(repo)
    _sembrar(repo, c["id"], ["B"])
    repo.upsert_plan("gratis", {"fotos_max": 1})
    url = f"/campo/mis-comercios/{c['id']}/fotos"
    r = client.post(url, headers=_h(lados["agente"]), files=_foto(), data={"reemplazar": "f0"})
    assert r.status_code == 403
    assert r.json()["detail"] == "Las fotos las borra URUKU. Avisale al admin."
    r = client.post(url, headers=_h(lados["agente"]), files=_foto())
    assert r.status_code == 409
    assert r.json()["detail"]["codigo"] == "tope_fotos"
    assert len(repo.list_fotos_comercio(c["id"])) == 1 and _en_disco("B.jpg")


def test_el_agente_si_sube_fotos_bajo_el_tope(client, repo, lados):
    c = _comercio(repo)
    r = client.post(f"/campo/mis-comercios/{c['id']}/fotos", headers=_h(lados["agente"]), files=_foto())
    assert r.status_code == 200, r.text
    assert len(repo.list_fotos_comercio(c["id"])) == 1


def test_comerciante_y_admin_siguen_pudiendo_borrar_fotos(client, repo, lados):
    c = _comercio(repo)
    _sembrar(repo, c["id"], ["B", "C"])
    assert client.delete("/comercio/fotos/f0", headers=_h(lados["comercio"])).status_code == 200
    assert client.delete(f"/admin/comercio/{c['id']}/fotos/f1", headers=_h(lados["admin"])).status_code == 200
    assert repo.list_fotos_comercio(c["id"]) == []


# ══════════════════════════════════ 5. Baja y reactivación de comercios (admin)

def test_rechazar_comercio_pide_comercios_editar(client, repo, admin_token):
    repo.seed_comercio(id="cm-1", slug="campo1", nombre="Campo 1", whatsapp="591")
    url = "/moderacion/comercios/cm-1/rechazar"
    # Sólo `moderar` (lo que antes alcanzaba): ya no.
    solo_moderar = auth.make_token("mod@x.com", rol="x", permisos=["moderar"])
    assert client.post(url, headers=_h(solo_moderar)).status_code == 403
    assert repo.comercios["cm-1"].get("activo", True) is True
    # Con `comercios.editar` sí (moderador y admin).
    mod = auth.make_token("mod@x.com", rol="moderador")
    assert client.post(url, headers=_h(mod)).status_code == 200
    assert repo.comercios["cm-1"]["activo"] is False


def test_el_publicador_puede_dar_de_baja_y_reactivar(client, repo):
    repo.seed_comercio(id="cm-1", slug="campo1", nombre="Campo 1", whatsapp="591")
    pub = auth.make_publicador_token("pub@uruku.bo")
    assert client.post("/moderacion/comercios/cm-1/rechazar", headers=_h(pub)).status_code == 200
    assert repo.comercios["cm-1"]["activo"] is False
    assert client.post("/admin/comercio/cm-1/reactivar", headers=_h(pub)).status_code == 200
    assert repo.comercios["cm-1"]["activo"] is True


def test_reactivar_vuelve_a_activo_y_devuelve_ok(client, repo, admin_token):
    repo.seed_comercio(id="cm-1", slug="campo1", nombre="Campo 1", whatsapp="591", activo=False)
    r = client.post("/admin/comercio/cm-1/reactivar", headers=_h(admin_token))
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert repo.comercios["cm-1"]["activo"] is True


def test_reactivar_un_comercio_inexistente_es_404(client, admin_token):
    assert client.post("/admin/comercio/no-existe/reactivar", headers=_h(admin_token)).status_code == 404


def test_reactivar_pide_comercios_editar(client, repo, lados):
    repo.seed_comercio(id="cm-1", slug="campo1", nombre="Campo 1", whatsapp="591", activo=False)
    url = "/admin/comercio/cm-1/reactivar"
    assert client.post(url).status_code == 401
    assert client.post(url, headers=_h(lados["comercio"])).status_code == 403
    assert client.post(url, headers=_h(lados["agente"])).status_code == 403
    solo_moderar = auth.make_token("mod@x.com", rol="x", permisos=["moderar"])
    assert client.post(url, headers=_h(solo_moderar)).status_code == 403
    assert repo.comercios["cm-1"]["activo"] is False


def test_dados_de_baja_lista_solo_los_inactivos_con_la_forma_del_contrato(client, repo, admin_token):
    repo.seed_comercio(id="cm-on", slug="activo", nombre="Activo", whatsapp="591")
    repo.seed_comercio(id="cm-off", slug="caido", nombre="Caído", whatsapp="591", activo=False,
                       rubro_nombre="Ropa", portada_thumb_url=f"{BASE}/caido/t.jpg",
                       updated_at="2026-10-01T10:00:00+00:00")
    r = client.get("/admin/comercios/dados-de-baja", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() == {"items": [{
        "id": "cm-off", "slug": "caido", "nombre": "Caído", "rubro_nombre": "Ropa",
        "portada_thumb_url": f"{BASE}/caido/t.jpg", "updated_at": "2026-10-01T10:00:00+00:00",
        "baja_motivo": None}]}      # una baja vieja, sin motivo: se lista igual


def test_dados_de_baja_filtra_por_ciudad_y_una_ciudad_inexistente_da_vacio(client, repo, admin_token):
    repo.seed_comercio(id="cm-b", slug="b", nombre="B", whatsapp="591", activo=False, ciudad_id="ciu-1")
    repo.seed_comercio(id="cm-s", slug="s", nombre="S", whatsapp="591", activo=False, ciudad_id="ciu-santa-cruz")
    ids = lambda r: sorted(i["id"] for i in r.json()["items"])
    assert ids(client.get("/admin/comercios/dados-de-baja", headers=_h(admin_token))) == ["cm-b", "cm-s"]
    assert ids(client.get("/admin/comercios/dados-de-baja?ciudad=bermejo", headers=_h(admin_token))) == ["cm-b"]
    assert ids(client.get("/admin/comercios/dados-de-baja?ciudad=santa-cruz", headers=_h(admin_token))) == ["cm-s"]


def test_dados_de_baja_pide_comercios_editar(client, repo, lados):
    url = "/admin/comercios/dados-de-baja"
    assert client.get(url).status_code == 401
    assert client.get(url, headers=_h(lados["comercio"])).status_code == 403
    assert client.get(url, headers=_h(lados["agente"])).status_code == 403
    solo_moderar = auth.make_token("mod@x.com", rol="x", permisos=["moderar"])
    assert client.get(url, headers=_h(solo_moderar)).status_code == 403


def test_dar_de_baja_y_reactivar_de_punta_a_punta(client, repo, admin_token):
    repo.seed_comercio(id="cm-1", slug="campo1", nombre="Campo 1", whatsapp="591")
    h = _h(admin_token)
    assert client.get("/admin/comercios/dados-de-baja", headers=h).json()["items"] == []
    assert client.post("/moderacion/comercios/cm-1/rechazar", headers=h).status_code == 200
    assert [i["id"] for i in client.get("/admin/comercios/dados-de-baja", headers=h).json()["items"]] == ["cm-1"]
    assert client.post("/admin/comercio/cm-1/reactivar", headers=h).status_code == 200
    assert client.get("/admin/comercios/dados-de-baja", headers=h).json()["items"] == []


# ═════════════════════════════ 6. Bajar una publicación ya aprobada

def _pub_aprobada(repo, pid="pub-ok", **kw):
    p = {"id": pid, "activo": True, "estado": "aprobado", "comercio_id": "com-p", "tipo": "oferta",
         "titulo": "Oferta", **kw}
    repo.publicaciones.append(p)
    return p


def test_el_listado_de_aprobadas_trae_solo_las_aprobadas(client, repo, admin_token):
    _pub_aprobada(repo, "pub-ok")
    repo.publicaciones.append({"id": "pub-pend", "activo": True, "estado": "pendiente",
                               "comercio_id": "com-p", "tipo": "oferta", "titulo": "X"})
    r = client.get("/moderacion/publicaciones?estado=aprobado", headers=_h(admin_token))
    assert r.status_code == 200
    assert [p["id"] for p in r.json()["items"]] == ["pub-ok"]
    assert r.json()["total"] == 1


def test_bajar_una_aprobada_la_pasa_a_rechazada_y_sale_del_listado(client, repo, admin_token):
    _pub_aprobada(repo)
    h = _h(admin_token)
    r = client.post("/moderacion/publicaciones/pub-ok", headers=h,
                    json={"estado": "rechazado", "motivo": "Ya no hay stock"})
    assert r.status_code == 200, r.text
    assert r.json()["publicacion"]["estado"] == "rechazado"
    assert repo.publicaciones[0]["motivo_moderacion"] == "Ya no hay stock"
    assert client.get("/moderacion/publicaciones?estado=aprobado", headers=h).json()["items"] == []
    assert [p["id"] for p in client.get("/moderacion/publicaciones?estado=rechazado", headers=h).json()["items"]] == ["pub-ok"]


def test_bajar_una_aprobada_descarta_lo_que_esperaba_salir_en_las_redes(client, repo, admin_token):
    _pub_aprobada(repo)
    repo.difusion.append({"id": "d1", "publicacion_id": "pub-ok", "estado": "pendiente"})
    r = client.post("/moderacion/publicaciones/pub-ok", headers=_h(admin_token),
                    json={"estado": "rechazado", "motivo": "Error de precio"})
    assert r.status_code == 200, r.text
    assert repo.difusion[0]["estado"] == "omitido"


def test_el_publicador_tambien_puede_bajar_una_aprobada(client, repo):
    _pub_aprobada(repo)
    pub = auth.make_publicador_token("pub@uruku.bo")
    r = client.post("/moderacion/publicaciones/pub-ok", headers=_h(pub),
                    json={"estado": "rechazado", "motivo": "Vencida"})
    assert r.status_code == 200, r.text
    assert repo.publicaciones[0]["estado"] == "rechazado"
    assert repo.publicaciones[0]["moderado_por"] == "pub@uruku.bo"


def test_un_comercio_no_puede_bajar_publicaciones_por_la_moderacion(client, repo, lados):
    _pub_aprobada(repo)
    r = client.post("/moderacion/publicaciones/pub-ok", headers=_h(lados["comercio"]),
                    json={"estado": "rechazado"})
    assert r.status_code == 403
    assert repo.publicaciones[0]["estado"] == "aprobado"


# ═════════════════════════════════════ 7. El publicador edita fichas (0146)

def test_roles_base_publicador_tiene_comercios_editar_y_la_descripcion_nueva():
    pub = ROLES_BASE["publicador"]
    assert pub["permisos"] == ["contenido", "moderar", "comercios.editar"]
    assert pub["descripcion"] == "Carga la cotización, el estado del paso y los videos, y corrige fichas."


def test_el_token_del_publicador_puede_editar_fichas():
    claims = {"rol": "publicador"}
    assert tiene(claims, "comercios.editar")
    assert tiene(claims, "moderar") and tiene(claims, "contenido")
    assert not tiene(claims, "pagos") and not tiene(claims, "equipo")


def test_el_publicador_guarda_cambios_en_una_ficha(client, repo):
    repo.seed_comercio(id="cm-1", slug="campo1", nombre="Campo 1", whatsapp="59170000001")
    pub = auth.make_publicador_token("pub@uruku.bo")
    r = client.put("/admin/comercio/cm-1", headers=_h(pub), json={"descripcion": "Ropa por mayor"})
    assert r.status_code == 200, r.text
    assert repo.comercios["cm-1"]["descripcion"] == "Ropa por mayor"


def test_el_publicador_cambia_la_portada_de_una_ficha(client, repo):
    c = _con_portada(repo, "A")
    _sembrar(repo, c["id"], ["B"])
    pub = auth.make_publicador_token("pub@uruku.bo")
    r = client.put(f"/admin/comercio/{c['id']}/portada", headers=_h(pub), json={"foto_id": "f0"})
    assert r.status_code == 200, r.text
    assert client.post(f"/admin/comercio/{c['id']}/foto", headers=_h(pub), files=_foto()).status_code == 200


def test_la_migracion_0146_esta_en_las_dos_carpetas_iguales_e_idempotente():
    nombre = "0146_publicador_edita_fichas.sql"
    a = (RAIZ / "supabase" / "migrations" / nombre).read_text(encoding="utf-8")
    b = (RAIZ / "selfhost" / "postgres-init" / nombre).read_text(encoding="utf-8")
    assert a == b
    sql = a.lower()
    assert "'comercios.editar'" in sql and "slug = 'publicador'" in sql
    # Idempotente: sólo suma el permiso si todavía no está.
    assert "not ('comercios.editar' = any(permisos))" in sql
    assert "carga la cotización, el estado del paso y los videos, y corrige fichas." in sql
    assert "delete" not in sql and "drop" not in sql
