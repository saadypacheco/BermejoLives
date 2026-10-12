"""Novedades de URUKU (migración 0150, docs/novedades-uruku.md).

Lo que cuenta URUKU en la sección «Novedades» del inicio: título, texto, fecha, ciudad (o
todas), enlace, portada, hasta 12 fotos y un video con póster. Las carga el publicador
(permiso `contenido`, igual que los videos promo).

Qué se prueba:
- CRUD y permisos: sin token 401; con un token SIN `contenido` (moderador, comercio, agente) 403.
- Validaciones: título vacío o largo, texto largo, enlace que no es http(s), fecha, ciudad.
- Baja lógica (nunca se borra la fila ni los archivos) y reactivación por PATCH.
- Portada, fotos (tope de 12 -> 409, también en paralelo en la base), sacar una foto borra
  sus archivos, video (+ póster) y sus tamaños; los archivos quedan en uruku/novedades/<id>/.
- Los topes del cuerpo (limite_cuerpo) de las rutas nuevas.
- La 0150 es idéntica en las dos carpetas, tiene RLS/grants por columnas, es idempotente y,
  contra un Postgres real de Docker (opcional, `URUKU_PG_TEST_CONTAINER`), anon lee las
  activas y no `created_by` ni las inactivas.
"""
import os
import re
import shutil
import subprocess
import uuid
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.core import auth
from app.core.config import settings
from app.core.limite_cuerpo import HOLGURA, tope_para
from tests.conftest import comercio_token

RAIZ = Path(__file__).resolve().parents[2]
MB = 1024 * 1024
MP4 = b"\x00\x00\x00\x18ftypmp42" + b"0" * 64


def _h(email="publicador@bermejolive.com"):
    return {"Authorization": f"Bearer {auth.make_publicador_token(email)}"}


def _jpg(lado=40, color="red") -> bytes:
    buf = BytesIO()
    Image.new("RGB", (lado, lado), color=color).save(buf, format="JPEG")
    return buf.getvalue()


def _foto(nombre="f.jpg", data=None, tipo="image/jpeg"):
    return {"foto": (nombre, BytesIO(_jpg() if data is None else data), tipo)}


def _crear(client, **campos):
    body = {"titulo": "URUKU auspició el Festival del Lapacho", **campos}
    r = client.post("/contenido/novedades", headers=_h(), json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _ruta(url: str) -> Path:
    return Path(settings.fotos_dir) / url.split("/fotos/", 1)[1]


def _archivos_de(novedad_id: str) -> list[str]:
    carpeta = Path(settings.fotos_dir) / "uruku" / "novedades" / novedad_id
    return sorted(str(p.relative_to(carpeta)).replace("\\", "/") for p in carpeta.rglob("*") if p.is_file()) if carpeta.exists() else []


# ═════════════════════════════════════════════════════════════════════════════
# Permisos
# ═════════════════════════════════════════════════════════════════════════════
def _rutas_de_escritura(nid="x"):
    return [("get", "/contenido/novedades", {}),
            ("post", "/contenido/novedades", {"json": {"titulo": "a"}}),
            ("patch", f"/contenido/novedades/{nid}", {"json": {"titulo": "a"}}),
            ("delete", f"/contenido/novedades/{nid}", {}),
            ("post", f"/contenido/novedades/{nid}/portada", {"files": _foto()}),
            ("post", f"/contenido/novedades/{nid}/fotos", {"files": _foto()}),
            ("delete", f"/contenido/novedades/{nid}/fotos?url=http://x/y.jpg", {}),
            ("post", f"/contenido/novedades/{nid}/video", {"files": {"video": ("v.mp4", BytesIO(MP4), "video/mp4")}})]


def test_sin_token_es_401(client):
    for metodo, ruta, kw in _rutas_de_escritura():
        r = getattr(client, metodo)(ruta, **kw)
        assert r.status_code == 401, (metodo, ruta, r.status_code)


def test_sin_el_permiso_contenido_es_403(client, repo):
    nov = _crear(client)
    tokens = {
        "moderador": auth.make_token("mod@uruku.bo", rol="moderador"),        # tiene moderar, no contenido
        "agente": auth.make_agente_token("agente@bermejolive.com", "bermejo"),
        "comercio": comercio_token(),
        "rol vaciado": auth.make_token("x@uruku.bo", rol="publicador", permisos=["moderar"]),
    }
    for quien, tok in tokens.items():
        for metodo, ruta, kw in _rutas_de_escritura(nov["id"]):
            r = getattr(client, metodo)(ruta, headers={"Authorization": f"Bearer {tok}"}, **kw)
            assert r.status_code == 403, (quien, metodo, ruta, r.status_code, r.text)
    # Y no tocaron nada.
    assert len(repo.novedades_uruku) == 1 and repo.novedades_uruku[nov["id"]]["activo"] is True


def test_el_admin_tambien_puede(client):
    tok = auth.make_token("admin@bermejolive.com", rol="admin")
    r = client.post("/contenido/novedades", headers={"Authorization": f"Bearer {tok}"}, json={"titulo": "Hola"})
    assert r.status_code == 200 and r.json()["created_by"] == "admin@bermejolive.com"


# ═════════════════════════════════════════════════════════════════════════════
# CRUD
# ═════════════════════════════════════════════════════════════════════════════
def test_crear_devuelve_la_novedad_con_sus_valores_por_defecto(client, repo):
    r = _crear(client)
    assert r["ok"] is True and r["novedad"]["id"] == r["id"]           # plana y bajo `novedad`
    assert r["titulo"] == "URUKU auspició el Festival del Lapacho"
    assert r["activo"] is True and r["destacada"] is False
    assert r["ciudad_id"] is None and r["ciudad_slug"] is None          # null = todas
    assert r["fotos"] == [] and r["portada_url"] is None and r["video_url"] is None
    assert r["created_by"] == "publicador@bermejolive.com"
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", r["fecha"])
    assert r["id"] in repo.novedades_uruku


def test_crear_con_todos_los_campos(client):
    r = _crear(client, titulo="  Festival  ", texto="  Fuimos auspiciantes.  ", fecha="2026-10-05",
               ciudad_slug="Bermejo", enlace_url="https://uruku.bo/festival?x=1", destacada=True)
    assert r["titulo"] == "Festival" and r["texto"] == "Fuimos auspiciantes."
    assert r["fecha"] == "2026-10-05" and r["destacada"] is True
    assert r["ciudad_id"] == "ciu-1" and r["ciudad_slug"] == "bermejo"
    assert r["enlace_url"] == "https://uruku.bo/festival?x=1"


def test_listar_trae_tambien_las_inactivas_destacadas_primero_y_fecha_desc(client):
    a = _crear(client, titulo="A", fecha="2026-10-01")
    b = _crear(client, titulo="B", fecha="2026-10-09")
    c = _crear(client, titulo="C", fecha="2026-09-01", destacada=True)
    d = _crear(client, titulo="D", fecha="2026-10-10")
    assert client.delete(f"/contenido/novedades/{d['id']}", headers=_h()).status_code == 200
    items = client.get("/contenido/novedades", headers=_h()).json()["items"]
    assert [i["titulo"] for i in items] == ["C", "D", "B", "A"]
    assert [i["activo"] for i in items] == [True, False, True, True]
    assert {a["id"], b["id"], c["id"], d["id"]} == {i["id"] for i in items}


def test_editar_cambia_solo_lo_que_viene(client):
    n = _crear(client, texto="uno", enlace_url="https://a.com", ciudad_slug="bermejo", destacada=True)
    r = client.patch(f"/contenido/novedades/{n['id']}", headers=_h(), json={"titulo": "Nuevo", "fecha": "2026-01-02"})
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["titulo"] == "Nuevo" and j["fecha"] == "2026-01-02" and j["novedad"]["titulo"] == "Nuevo"
    assert j["texto"] == "uno" and j["enlace_url"] == "https://a.com" and j["ciudad_slug"] == "bermejo"
    assert j["destacada"] is True and j["activo"] is True


def test_editar_puede_borrar_texto_enlace_y_pasar_a_todas_las_ciudades(client):
    n = _crear(client, texto="uno", enlace_url="https://a.com", ciudad_slug="santa-cruz")
    assert n["ciudad_slug"] == "santa-cruz"
    j = client.patch(f"/contenido/novedades/{n['id']}", headers=_h(),
                     json={"texto": "", "enlace_url": None, "ciudad_slug": None}).json()
    assert j["texto"] is None and j["enlace_url"] is None
    assert j["ciudad_id"] is None and j["ciudad_slug"] is None
    j = client.patch(f"/contenido/novedades/{n['id']}", headers=_h(), json={"ciudad_slug": "bermejo"}).json()
    assert j["ciudad_slug"] == "bermejo"
    j = client.patch(f"/contenido/novedades/{n['id']}", headers=_h(), json={"ciudad_slug": ""}).json()
    assert j["ciudad_id"] is None


def test_editar_y_dar_de_baja_algo_que_no_existe_es_404(client):
    assert client.patch("/contenido/novedades/nada", headers=_h(), json={"titulo": "x"}).status_code == 404
    assert client.delete("/contenido/novedades/nada", headers=_h()).status_code == 404
    assert client.post("/contenido/novedades/nada/portada", headers=_h(), files=_foto()).status_code == 404
    assert client.post("/contenido/novedades/nada/fotos", headers=_h(), files=_foto()).status_code == 404
    assert client.delete("/contenido/novedades/nada/fotos?url=x", headers=_h()).status_code == 404
    assert client.post("/contenido/novedades/nada/video", headers=_h(),
                       files={"video": ("v.mp4", BytesIO(MP4), "video/mp4")}).status_code == 404


def test_editar_sin_nada_que_cambiar_es_400(client):
    n = _crear(client)
    assert client.patch(f"/contenido/novedades/{n['id']}", headers=_h(), json={}).status_code == 400


# ═════════════════════════════════════════════════════════════════════════════
# Validaciones
# ═════════════════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("body,fragmento", [
    ({}, "título"),
    ({"titulo": ""}, "título"),
    ({"titulo": "   "}, "título"),
    ({"titulo": "x" * 121}, "120"),
    ({"titulo": "ok", "texto": "y" * 2001}, "2000"),
    ({"titulo": "ok", "enlace_url": "javascript:alert(1)"}, "http"),
    ({"titulo": "ok", "enlace_url": "mitienda.com"}, "http"),
    ({"titulo": "ok", "enlace_url": "ftp://x.com/a"}, "http"),
    ({"titulo": "ok", "enlace_url": "https://uruku.bo@evil.com"}, "usuario"),
    ({"titulo": "ok", "enlace_url": "https://" + "a" * 600 + ".com"}, "http"),
    ({"titulo": "ok", "fecha": "ayer"}, "fecha"),
    ({"titulo": "ok", "fecha": "2026-13-45"}, "fecha"),
    ({"titulo": "ok", "ciudad_slug": "no-existe"}, "ciudad"),
])
def test_crear_con_datos_malos_es_400_en_castellano_y_no_guarda(client, repo, body, fragmento):
    repo.SLUGS_INEXISTENTES = {"no-existe"}
    r = client.post("/contenido/novedades", headers=_h(), json=body)
    assert r.status_code == 400, (body, r.status_code, r.text)
    detalle = r.json()["detail"]
    assert isinstance(detalle, str) and fragmento in detalle, detalle
    assert repo.novedades_uruku == {}


def test_titulo_de_120_justos_y_texto_de_2000_justos_pasan(client):
    r = _crear(client, titulo="x" * 120, texto="y" * 2000)
    assert len(r["titulo"]) == 120 and len(r["texto"]) == 2000


def test_editar_con_datos_malos_es_400_y_no_cambia_nada(client, repo):
    n = _crear(client, enlace_url="https://a.com")
    for body in ({"titulo": ""}, {"titulo": "x" * 121}, {"enlace_url": "javascript:alert(1)"},
                 {"texto": "y" * 2001}, {"fecha": "no"}):
        r = client.patch(f"/contenido/novedades/{n['id']}", headers=_h(), json=body)
        assert r.status_code == 400, (body, r.text)
    fila = repo.novedades_uruku[n["id"]]
    assert fila["titulo"] == "URUKU auspició el Festival del Lapacho" and fila["enlace_url"] == "https://a.com"


# ═════════════════════════════════════════════════════════════════════════════
# Baja lógica
# ═════════════════════════════════════════════════════════════════════════════
def test_dar_de_baja_es_logico_conserva_los_archivos_y_se_puede_reactivar(client, repo):
    n = _crear(client)
    portada = client.post(f"/contenido/novedades/{n['id']}/portada", headers=_h(), files=_foto()).json()
    foto = client.post(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), files=_foto()).json()["foto"]
    antes = _archivos_de(n["id"])
    assert len(antes) == 4

    r = client.delete(f"/contenido/novedades/{n['id']}", headers=_h())
    assert r.status_code == 200 and r.json() == {"ok": True}
    assert n["id"] in repo.novedades_uruku                       # la fila sigue
    assert repo.novedades_uruku[n["id"]]["activo"] is False
    assert _archivos_de(n["id"]) == antes                        # los archivos también
    assert _ruta(portada["portada_url"]).exists() and _ruta(foto["url"]).exists()
    # Dar de baja dos veces no falla.
    assert client.delete(f"/contenido/novedades/{n['id']}", headers=_h()).status_code == 200
    # Reactivar.
    j = client.patch(f"/contenido/novedades/{n['id']}", headers=_h(), json={"activo": True}).json()
    assert j["activo"] is True


# ═════════════════════════════════════════════════════════════════════════════
# Portada
# ═════════════════════════════════════════════════════════════════════════════
def test_subir_portada_guarda_jpg_y_miniatura_en_la_carpeta_de_la_novedad(client, repo):
    n = _crear(client)
    r = client.post(f"/contenido/novedades/{n['id']}/portada", headers=_h(), files=_foto("p.png", _jpg(), "image/png"))
    assert r.status_code == 200, r.text
    j = r.json()
    assert set(j) >= {"portada_url", "portada_thumb_url"}
    assert f"/uruku/novedades/{n['id']}/" in j["portada_url"] and j["portada_url"].endswith(".jpg")
    assert j["portada_thumb_url"].endswith("_t3.jpg")
    assert _ruta(j["portada_url"]).read_bytes()[:2] == b"\xff\xd8" and _ruta(j["portada_thumb_url"]).exists()
    fila = repo.novedades_uruku[n["id"]]
    assert fila["portada_url"] == j["portada_url"] and fila["portada_thumb_url"] == j["portada_thumb_url"]


def test_cambiar_la_portada_borra_los_archivos_de_la_anterior(client):
    n = _crear(client)
    a = client.post(f"/contenido/novedades/{n['id']}/portada", headers=_h(), files=_foto()).json()
    b = client.post(f"/contenido/novedades/{n['id']}/portada", headers=_h(), files=_foto(data=_jpg(60, "blue"))).json()
    assert a["portada_url"] != b["portada_url"]
    assert not _ruta(a["portada_url"]).exists() and not _ruta(a["portada_thumb_url"]).exists()
    assert _ruta(b["portada_url"]).exists() and _ruta(b["portada_thumb_url"]).exists()
    assert len(_archivos_de(n["id"])) == 2


def test_portada_que_no_es_imagen_es_400_y_no_deja_nada(client, repo):
    n = _crear(client)
    r = client.post(f"/contenido/novedades/{n['id']}/portada", headers=_h(), files=_foto("x.jpg", b"no soy una imagen"))
    assert r.status_code == 400 and "imagen" in r.json()["detail"]
    assert repo.novedades_uruku[n["id"]]["portada_url"] is None and _archivos_de(n["id"]) == []


def test_portada_vacia_o_sin_campo_es_400(client):
    n = _crear(client)
    assert client.post(f"/contenido/novedades/{n['id']}/portada", headers=_h(), files=_foto(data=b"")).status_code == 400
    r = client.post(f"/contenido/novedades/{n['id']}/portada", headers=_h(),
                    files={"otro": ("a.jpg", BytesIO(_jpg()), "image/jpeg")})
    assert r.status_code == 400


def test_portada_de_mas_de_15mb_es_413_y_no_deja_nada(client):
    n = _crear(client)
    r = client.post(f"/contenido/novedades/{n['id']}/portada", headers=_h(), files=_foto(data=b"\xff\xd8" + b"0" * (15 * MB)))
    assert r.status_code == 413 and "15 MB" in r.json()["detail"]
    assert _archivos_de(n["id"]) == []


# ═════════════════════════════════════════════════════════════════════════════
# Fotos
# ═════════════════════════════════════════════════════════════════════════════
def test_subir_fotos_las_suma_en_orden_con_url_y_miniatura(client, repo):
    n = _crear(client)
    subidas = []
    for i in range(4):
        r = client.post(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), files=_foto(data=_jpg(30 + i)))
        assert r.status_code == 200, r.text
        j = r.json()
        assert set(j["foto"]) == {"url", "thumb_url"} and j["fotos"][-1] == j["foto"] and len(j["fotos"]) == i + 1
        assert f"/uruku/novedades/{n['id']}/" in j["foto"]["url"]
        subidas.append(j["foto"])
    assert repo.novedades_uruku[n["id"]]["fotos"] == subidas
    assert all(_ruta(f["url"]).exists() and _ruta(f["thumb_url"]).exists() for f in subidas)
    # La portada no cuenta para el tope ni se mezcla con las fotos.
    assert len(_archivos_de(n["id"])) == 8


def test_la_foto_13_es_409_y_no_deja_archivos(client, repo):
    n = _crear(client)
    for _ in range(12):
        assert client.post(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), files=_foto()).status_code == 200
    antes = _archivos_de(n["id"])
    assert len(antes) == 24
    r = client.post(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), files=_foto())
    assert r.status_code == 409 and "12" in r.json()["detail"]
    assert len(repo.novedades_uruku[n["id"]]["fotos"]) == 12 and _archivos_de(n["id"]) == antes


def test_el_tope_lo_decide_la_base_aunque_el_chequeo_previo_pase(client, repo, monkeypatch):
    """Dos subidas a la vez ven «11 fotos» y las dos pasan el chequeo previo: la que pierde
    la carrera recibe 409 de la base y sus archivos se borran."""
    n = _crear(client)
    for _ in range(12):
        client.post(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), files=_foto())
    antes = _archivos_de(n["id"])
    real = repo.get_novedad_uruku
    primera = {"hecho": False}

    def get_con_once_fotos(novedad_id):
        fila = real(novedad_id)
        if fila and not primera["hecho"]:
            primera["hecho"] = True
            fila["fotos"] = fila["fotos"][:11]       # el chequeo previo ve 11
        return fila

    monkeypatch.setattr(repo, "get_novedad_uruku", get_con_once_fotos)
    r = client.post(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), files=_foto())
    assert r.status_code == 409
    assert len(repo.novedades_uruku[n["id"]]["fotos"]) == 12 and _archivos_de(n["id"]) == antes


def test_foto_que_no_es_imagen_es_400_y_de_mas_de_15mb_es_413(client, repo):
    n = _crear(client)
    r = client.post(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), files=_foto(data=b"texto"))
    assert r.status_code == 400
    r = client.post(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), files=_foto(data=b"\xff\xd8" + b"0" * (15 * MB)))
    assert r.status_code == 413
    assert repo.novedades_uruku[n["id"]]["fotos"] == [] and _archivos_de(n["id"]) == []


def test_sacar_una_foto_la_quita_de_la_lista_y_borra_sus_archivos(client, repo):
    n = _crear(client)
    f = [client.post(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), files=_foto(data=_jpg(30 + i))).json()["foto"]
         for i in range(3)]
    portada = client.post(f"/contenido/novedades/{n['id']}/portada", headers=_h(), files=_foto()).json()

    r = client.delete(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), params={"url": f[1]["url"]})
    assert r.status_code == 200, r.text
    assert r.json()["fotos"] == [f[0], f[2]]
    assert repo.novedades_uruku[n["id"]]["fotos"] == [f[0], f[2]]
    assert not _ruta(f[1]["url"]).exists() and not _ruta(f[1]["thumb_url"]).exists()     # archivo borrado
    for quedan in (f[0], f[2]):
        assert _ruta(quedan["url"]).exists() and _ruta(quedan["thumb_url"]).exists()
    assert _ruta(portada["portada_url"]).exists()
    # Ya no está: 404. Y se puede volver a subir (el hueco se reusa).
    assert client.delete(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), params={"url": f[1]["url"]}).status_code == 404
    assert client.post(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), files=_foto()).status_code == 200


def test_sacar_foto_sin_url_es_400_y_con_url_ajena_no_borra_nada(client, repo):
    n = _crear(client)
    otra = _crear(client, titulo="Otra")
    ajena = client.post(f"/contenido/novedades/{otra['id']}/fotos", headers=_h(), files=_foto()).json()["foto"]
    propia = client.post(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), files=_foto()).json()["foto"]
    assert client.delete(f"/contenido/novedades/{n['id']}/fotos", headers=_h()).status_code == 400
    assert client.delete(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), params={"url": " "}).status_code == 400
    # Una foto de OTRA novedad no se saca por ésta.
    r = client.delete(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), params={"url": ajena["url"]})
    assert r.status_code == 404
    assert _ruta(ajena["url"]).exists() and _ruta(propia["url"]).exists()


def test_el_borrado_de_archivos_no_sale_de_la_carpeta_de_la_novedad(client, repo, tmp_path):
    """Aunque la fila apuntara a otro lado (datos viejos, un PATCH directo a la base), sacar la
    foto no borra nada fuera de uruku/novedades/<id>/."""
    n = _crear(client)
    fuera = Path(settings.fotos_dir) / "otro-comercio" / "intocable.jpg"
    fuera.parent.mkdir(parents=True)
    fuera.write_bytes(_jpg())
    sospechosas = [
        settings.public_photo_url("otro-comercio/intocable.jpg"),
        settings.public_photo_url(f"uruku/novedades/{n['id']}/../../../otro-comercio/intocable.jpg"),
        "https://evil.com/fotos/otro-comercio/intocable.jpg",
    ]
    for url in sospechosas:
        repo.novedades_uruku[n["id"]]["fotos"] = [{"url": url, "thumb_url": url}]
        r = client.delete(f"/contenido/novedades/{n['id']}/fotos", headers=_h(), params={"url": url})
        assert r.status_code == 200
        assert fuera.exists(), url


# ═════════════════════════════════════════════════════════════════════════════
# Video y póster
# ═════════════════════════════════════════════════════════════════════════════
def _video(data=MP4, tipo="video/mp4", nombre="v.mp4"):
    return {"video": (nombre, BytesIO(data), tipo)}


def test_subir_video_sin_poster(client, repo):
    n = _crear(client)
    r = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files=_video())
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["video_url"].endswith(".mp4") and f"/uruku/novedades/{n['id']}/videos/" in j["video_url"]
    assert j["video_poster_url"] is None
    assert _ruta(j["video_url"]).read_bytes() == MP4
    assert repo.novedades_uruku[n["id"]]["video_url"] == j["video_url"]


@pytest.mark.parametrize("tipo,ext", [("video/mp4", "mp4"), ("video/webm", "webm"), ("video/quicktime", "mov")])
def test_formatos_de_video_aceptados(client, tipo, ext):
    n = _crear(client)
    r = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files=_video(tipo=tipo, nombre=f"v.{ext}"))
    assert r.status_code == 200 and r.json()["video_url"].endswith(f".{ext}")


def test_subir_video_con_poster(client, repo):
    n = _crear(client)
    files = {**_video(), "poster": ("p.png", BytesIO(_jpg(80)), "image/png")}
    j = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files=files).json()
    assert j["video_url"] and j["video_poster_url"].endswith(".jpg")
    assert f"/uruku/novedades/{n['id']}/" in j["video_poster_url"]
    assert _ruta(j["video_poster_url"]).read_bytes()[:2] == b"\xff\xd8"         # el póster pasó por imagenes.py (JPG)
    fila = repo.novedades_uruku[n["id"]]
    assert (fila["video_url"], fila["video_poster_url"]) == (j["video_url"], j["video_poster_url"])


def test_video_que_no_es_video_es_400(client, repo):
    n = _crear(client)
    for tipo, nombre in (("image/jpeg", "v.jpg"), ("application/pdf", "v.pdf"), ("video/x-matroska", "v.mkv"), ("", "v")):
        r = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files=_video(tipo=tipo, nombre=nombre))
        assert r.status_code == 400, (tipo, r.text)
    assert client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files=_video(data=b"")).status_code == 400
    assert client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), data={"x": "1"}).status_code == 400
    assert repo.novedades_uruku[n["id"]]["video_url"] is None and _archivos_de(n["id"]) == []


def test_video_de_mas_de_100mb_es_413_y_uno_de_100mb_pasa(client):
    n = _crear(client)
    r = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files=_video(data=b"0" * (100 * MB + 1)))
    assert r.status_code == 413 and "100 MB" in r.json()["detail"]
    assert _archivos_de(n["id"]) == []
    assert client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files=_video(data=b"0" * (100 * MB))).status_code == 200


def test_poster_que_no_es_imagen_es_400_y_no_deja_el_video_a_medias(client, repo):
    n = _crear(client)
    files = {**_video(), "poster": ("p.jpg", BytesIO(b"no soy una imagen"), "image/jpeg")}
    r = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files=files)
    assert r.status_code == 400 and "póster" in r.json()["detail"]
    assert repo.novedades_uruku[n["id"]]["video_url"] is None and _archivos_de(n["id"]) == []
    files = {**_video(), "poster": ("p.jpg", BytesIO(b"\xff\xd8" + b"0" * (15 * MB)), "image/jpeg")}
    assert client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files=files).status_code == 413
    assert _archivos_de(n["id"]) == []


def test_reemplazar_el_video_borra_el_anterior_y_su_poster(client, repo):
    n = _crear(client)
    a = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(),
                    files={**_video(), "poster": ("p.jpg", BytesIO(_jpg()), "image/jpeg")}).json()
    b = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files=_video(data=MP4 + b"1", tipo="video/webm", nombre="b.webm")).json()
    assert not _ruta(a["video_url"]).exists() and not _ruta(a["video_poster_url"]).exists()
    assert b["video_poster_url"] is None                       # el póster era del video anterior
    assert repo.novedades_uruku[n["id"]]["video_poster_url"] is None
    assert _archivos_de(n["id"]) == [b["video_url"].split(f"{n['id']}/", 1)[1]]


def test_cambiar_solo_el_poster_conserva_el_video(client, repo):
    n = _crear(client)
    v = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files=_video()).json()
    a = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(),
                    files={"poster": ("p.jpg", BytesIO(_jpg()), "image/jpeg")}).json()
    assert a["video_url"] == v["video_url"] and a["video_poster_url"]
    b = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(),
                    files={"poster": ("p.jpg", BytesIO(_jpg(70)), "image/jpeg")}).json()
    assert b["video_url"] == v["video_url"] and b["video_poster_url"] != a["video_poster_url"]
    assert _ruta(v["video_url"]).exists() and not _ruta(a["video_poster_url"]).exists() and _ruta(b["video_poster_url"]).exists()


def test_poster_solo_sin_video_previo_es_400(client):
    n = _crear(client)
    r = client.post(f"/contenido/novedades/{n['id']}/video", headers=_h(), files={"poster": ("p.jpg", BytesIO(_jpg()), "image/jpeg")})
    assert r.status_code == 400 and "video" in r.json()["detail"]


# ═════════════════════════════════════════════════════════════════════════════
# Topes del cuerpo (core/limite_cuerpo.py)
# ═════════════════════════════════════════════════════════════════════════════
def test_topes_de_las_rutas_nuevas():
    for sufijo, mb in (("portada", 15), ("fotos", 15), ("video", 100)):
        assert tope_para(f"/contenido/novedades/abc/{sufijo}") == mb * MB + HOLGURA
        assert tope_para(f"/contenido/novedades/abc/{sufijo}/") == mb * MB + HOLGURA
    # El JSON normal (crear/editar) queda con el tope por defecto.
    assert tope_para("/contenido/novedades") == 2 * MB
    assert tope_para("/contenido/novedades/abc") == 2 * MB


def test_un_cuerpo_gigante_a_la_portada_se_corta_con_413_antes_de_autenticar(client):
    r = client.post("/contenido/novedades/abc/portada", headers={"Content-Length": str(40 * MB)}, content=b"x")
    assert r.status_code == 413


# ═════════════════════════════════════════════════════════════════════════════
# La migración 0150
# ═════════════════════════════════════════════════════════════════════════════
def _0150(carpeta="supabase/migrations") -> str:
    return (RAIZ / carpeta / "0150_novedades_uruku.sql").read_text(encoding="utf-8")


def _sin_comentarios(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


COLUMNAS_PUBLICAS = ("id", "ciudad_id", "titulo", "texto", "fecha", "portada_url", "portada_thumb_url", "fotos",
                     "video_url", "video_poster_url", "enlace_url", "destacada", "activo", "created_at", "updated_at")


def test_la_0150_esta_igual_en_supabase_y_en_selfhost():
    a = (RAIZ / "supabase/migrations/0150_novedades_uruku.sql").read_bytes()
    b = (RAIZ / "selfhost/postgres-init/0150_novedades_uruku.sql").read_bytes()
    assert a == b and a


def test_la_0150_da_columnas_menos_created_by_tiene_rls_y_es_idempotente():
    sql = _sin_comentarios(_0150())
    m = re.search(r"grant select \((.*?)\) on public\.novedades_uruku to anon, authenticated;", sql, re.S)
    assert m, "falta el grant select (columnas)"
    dadas = [c.strip() for c in m.group(1).split(",") if c.strip()]
    assert sorted(dadas) == sorted(COLUMNAS_PUBLICAS) and "created_by" not in dadas
    # Nunca un grant de tabla entera a anon / authenticated / public.
    assert not re.search(r"grant\s+(select|all|insert|update|delete)\s+on\s+(table\s+)?(public\.)?novedades_uruku\s+to\s+[^;]*(anon|authenticated|public)", sql, re.I)
    assert "revoke all on public.novedades_uruku from public, anon, authenticated;" in sql
    assert sql.index("revoke all on public.novedades_uruku") < sql.index("grant select (")
    assert "grant all on public.novedades_uruku to service_role;" in sql
    assert "alter table public.novedades_uruku enable row level security;" in sql
    assert "using (activo)" in sql
    assert "drop policy if exists novedades_uruku_public_read" in sql
    assert "create table if not exists public.novedades_uruku" in sql and not re.search(r"create table(?! if not exists)", sql)
    assert not re.search(r"delete\s+from|drop\s+table", sql, re.I)                 # soft-delete: nada de borrar
    assert sql.index("begin;") < sql.index("create table") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    # Comentarios en español sobre la tabla y las columnas.
    assert "comment on table public.novedades_uruku" in sql and "comment on column public.novedades_uruku.created_by" in sql
    # Las funciones de las fotos son sólo del backend.
    for f in ("novedad_agregar_foto(uuid, jsonb, int)", "novedad_quitar_foto(uuid, text)"):
        assert f"revoke all on function public.{f} from public, anon, authenticated;" in sql
        assert f"grant execute on function public.{f} to service_role;" in sql


def test_la_tabla_de_la_0150_tiene_las_columnas_de_la_spec():
    sql = _sin_comentarios(_0150())
    cuerpo = re.search(r"create table if not exists public\.novedades_uruku \((.*?)\n\);", sql, re.S).group(1)
    cols = [l.strip().split()[0] for l in cuerpo.splitlines() if l.strip() and not l.strip().startswith(("check", "references"))]
    cols = [c for c in cols if c in COLUMNAS_PUBLICAS + ("created_by",)]
    assert sorted(cols) == sorted(COLUMNAS_PUBLICAS + ("created_by",))
    assert "(now() at time zone 'America/La_Paz')::date" in cuerpo
    assert "jsonb_array_length(fotos) <= 12" in cuerpo


# ── contra un Postgres real (Docker, opcional) ───────────────────────────────
@pytest.fixture(scope="module")
def pg0150():
    """`psql(sql, rol=None, check=True)` contra una base descartable con un `ciudades` mínimo."""
    contenedor = os.environ.get("URUKU_PG_TEST_CONTAINER")
    if not contenedor or not shutil.which("docker"):
        pytest.skip("sin Postgres de Docker (URUKU_PG_TEST_CONTAINER)")
    base = "t0150_" + uuid.uuid4().hex[:8]

    def psql(sql, db=base, check=True, rol=None):
        if rol:
            sql = f"set role {rol};\n{sql}"
        p = subprocess.run(
            ["docker", "exec", "-i", contenedor, "psql", "-U", "postgres", "-d", db,
             "-v", "ON_ERROR_STOP=1", "-At", "-q", "-F", "|", "-f", "-"],
            input=sql, capture_output=True, text=True, encoding="utf-8")
        if check and p.returncode != 0:
            raise AssertionError(p.stderr)
        return p

    psql(f'create database "{base}"', db="postgres")
    try:
        psql("""
            do $$ begin
              begin create role anon nologin; exception when duplicate_object then null; end;
              begin create role authenticated nologin; exception when duplicate_object then null; end;
              begin create role service_role nologin; exception when duplicate_object then null; end;
            end $$;
            alter role service_role bypassrls;
            grant usage on schema public to anon, authenticated, service_role;
            create table ciudades (id uuid primary key default gen_random_uuid(), slug text unique, nombre text);
            grant select on ciudades to anon, authenticated;
            -- Como los default privileges de Supabase: las tablas nuevas nacen abiertas a anon.
            alter default privileges in schema public grant all on tables to anon, authenticated, service_role;
            alter default privileges in schema public grant execute on functions to anon, authenticated, service_role;
            insert into ciudades (id, slug, nombre) values
              ('aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa', 'bermejo', 'Bermejo'),
              ('bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb', 'tarija', 'Tarija');
        """)
        psql(_0150())
        yield psql
    finally:
        psql(f'drop database if exists "{base}" with (force)', db="postgres", check=False)


def test_0150_en_postgres_anon_lee_las_activas_y_no_created_by_ni_las_inactivas(pg0150):
    pg0150("""
        insert into novedades_uruku (id, titulo, activo, created_by, ciudad_id) values
          ('11111111-1111-4111-8111-111111111111', 'Activa de todas', true, 'ana@uruku.bo', null),
          ('22222222-2222-4222-8222-222222222222', 'Inactiva', false, 'ana@uruku.bo', null),
          ('33333333-3333-4333-8333-333333333333', 'Activa de Bermejo', true, 'ana@uruku.bo',
           'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa');
    """)
    cols = ", ".join(COLUMNAS_PUBLICAS)
    for rol in ("anon", "authenticated"):
        r = pg0150(f"select titulo from novedades_uruku order by titulo;", rol=rol)
        assert r.stdout.split() == ["Activa", "de", "Bermejo", "Activa", "de", "todas"], (rol, r.stdout)
        assert pg0150(f"select count(*) from novedades_uruku where titulo = 'Inactiva';", rol=rol).stdout.strip() == "0"
        assert pg0150(f"select {cols} from novedades_uruku;", rol=rol).returncode == 0
        for malo in ("created_by", "*"):
            r = pg0150(f"select {malo} from novedades_uruku;", rol=rol, check=False)
            assert r.returncode != 0 and "permission denied" in r.stderr, (rol, malo, r.stderr)
        r = pg0150("select count(*) from novedades_uruku where created_by = 'ana@uruku.bo';", rol=rol, check=False)
        assert r.returncode != 0 and "permission denied" in r.stderr                       # ni para filtrar
    # El backend lo ve todo.
    assert pg0150("select count(*) from novedades_uruku;", rol="service_role").stdout.strip() == "3"
    assert pg0150("select created_by from novedades_uruku limit 1;", rol="service_role").stdout.strip() == "ana@uruku.bo"


def test_0150_en_postgres_anon_no_escribe_ni_llama_las_funciones(pg0150):
    for rol in ("anon", "authenticated"):
        for sql in ("insert into novedades_uruku (titulo) values ('x');",
                    "update novedades_uruku set activo = false;",
                    "delete from novedades_uruku;",
                    "select novedad_agregar_foto('11111111-1111-4111-8111-111111111111', '{}'::jsonb, 12);",
                    "select novedad_quitar_foto('11111111-1111-4111-8111-111111111111', 'x');"):
            r = pg0150(sql, rol=rol, check=False)
            assert r.returncode != 0 and "permission denied" in r.stderr, (rol, sql, r.stderr)


def test_0150_en_postgres_defaults_y_checks(pg0150):
    r = pg0150("""
        insert into novedades_uruku (id, titulo) values ('44444444-4444-4444-8444-444444444444', 'Defaults');
        select fecha = (now() at time zone 'America/La_Paz')::date, fotos, destacada, activo, ciudad_id is null,
               created_at is not null, updated_at is not null
          from novedades_uruku where id = '44444444-4444-4444-8444-444444444444';
    """, rol="service_role")
    assert r.stdout.strip() == "t|[]|f|t|t|t|t"
    for sql in ("insert into novedades_uruku (titulo) values ('');",
                "insert into novedades_uruku (titulo) values ('   ');",
                f"insert into novedades_uruku (titulo) values ('{'x' * 121}');",
                f"insert into novedades_uruku (titulo, texto) values ('ok', '{'y' * 2001}');",
                "insert into novedades_uruku (titulo, fotos) values ('ok', '{}'::jsonb);",
                "insert into novedades_uruku (titulo, ciudad_id) values ('ok', 'cccccccc-cccc-4ccc-8ccc-cccccccccccc');"):
        r = pg0150(sql, rol="service_role", check=False)
        assert r.returncode != 0, sql


def test_0150_en_postgres_las_fotos_se_agregan_hasta_12_y_se_sacan_de_a_una(pg0150):
    nid = "55555555-5555-4555-8555-555555555555"
    pg0150(f"insert into novedades_uruku (id, titulo) values ('{nid}', 'Fotos');")
    for i in range(12):
        r = pg0150(f"""select jsonb_array_length(novedad_agregar_foto('{nid}',
                          '{{"url":"u{i}","thumb_url":"t{i}"}}'::jsonb, 12));""", rol="service_role")
        assert r.stdout.strip() == str(i + 1)
    # La 13: la base la rechaza (null) y la lista sigue en 12.
    assert pg0150(f"select novedad_agregar_foto('{nid}', '{{\"url\":\"u13\"}}'::jsonb, 12) is null;", rol="service_role").stdout.strip() == "t"
    assert pg0150(f"select jsonb_array_length(fotos) from novedades_uruku where id = '{nid}';").stdout.strip() == "12"
    # Una novedad que no existe: null.
    assert pg0150("select novedad_agregar_foto('99999999-9999-4999-8999-999999999999', '{}'::jsonb, 12) is null;",
                  rol="service_role").stdout.strip() == "t"
    # Sacar: devuelve la foto sacada, conserva el orden de las demás; una que no está da null.
    assert pg0150(f"select novedad_quitar_foto('{nid}', 'u3');", rol="service_role").stdout.strip() == '{"url": "u3", "thumb_url": "t3"}'
    assert pg0150(f"select novedad_quitar_foto('{nid}', 'u3') is null;", rol="service_role").stdout.strip() == "t"
    assert pg0150(f"select string_agg(e->>'url', ',') from novedades_uruku, jsonb_array_elements(fotos) e where id = '{nid}';"
                  ).stdout.strip() == "u0,u1,u2,u4,u5,u6,u7,u8,u9,u10,u11"
    # Ahora hay lugar para una más.
    assert pg0150(f"select jsonb_array_length(novedad_agregar_foto('{nid}', '{{\"url\":\"nueva\"}}'::jsonb, 12));",
                  rol="service_role").stdout.strip() == "12"


def test_0150_en_postgres_es_idempotente_y_conserva_los_datos(pg0150):
    antes = pg0150("select count(*) from novedades_uruku;").stdout.strip()
    pg0150(_0150())
    pg0150(_0150())
    assert pg0150("select count(*) from novedades_uruku;").stdout.strip() == antes
    # Los permisos siguen como antes de correrla de nuevo.
    r = pg0150("select created_by from novedades_uruku;", rol="anon", check=False)
    assert r.returncode != 0 and "permission denied" in r.stderr
    assert pg0150("select count(*) from novedades_uruku where activo;", rol="anon").returncode == 0
    assert pg0150("select count(*) from pg_policies where tablename = 'novedades_uruku';").stdout.strip() == "1"
