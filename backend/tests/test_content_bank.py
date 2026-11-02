"""El banco de fotos para redes: subida del panel y de la app de campo, privacidad y URLs firmadas."""
import time
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.core import auth
from app.core.config import settings
from app.services import content_storage
from tests.content_helpers import AGENTE, autorizar, banco, comercio, h, jpg


@pytest.fixture
def token():
    return auth.make_token("ana@uruku.bo", rol="admin")


def _subir(client, token, cid="com-1", datos=None, **form):
    datos = datos if datos is not None else jpg()
    return client.post(f"/admin/content/merchants/{cid}/assets", headers=h(token),
                       files={"foto": ("f.jpg", BytesIO(datos), "image/jpeg")}, data=form)


def _archivos(carpeta):
    return sorted(p for p in Path(carpeta).rglob("*") if p.is_file())


def test_el_admin_sube_una_foto_y_queda_bajo_content_dir_no_bajo_fotos(client, repo, crepo, token):
    comercio(repo)
    r = _subir(client, token)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] and body["duplicate"] is False and body["warnings"]
    a = crepo.assets[body["asset"]["id"]]
    assert a["source"] == "admin_upload" and a["uploaded_by"] == "ana@uruku.bo"
    assert max(a["width"], a["height"]) == 1600 and not body["asset"]["too_small"]
    raiz = Path(settings.content_dir).resolve()
    for rel in (a["file_path"], a["thumb_path"]):
        assert content_storage.safe_path(rel).is_file()
        assert raiz in content_storage.safe_path(rel).parents
    assert not _archivos(settings.fotos_dir)                    # nada bajo /fotos
    assert a["file_path"].startswith("assets/com-1/")


def test_la_foto_guardada_no_lleva_exif(client, repo, crepo, token):
    comercio(repo)
    a = crepo.assets[_subir(client, token, datos=jpg(exif=True)).json()["asset"]["id"]]
    with Image.open(content_storage.safe_path(a["file_path"])) as im:
        assert not dict(im.getexif())
    assert b"CamaraSecreta" not in content_storage.safe_path(a["file_path"]).read_bytes()


def test_se_achica_a_2048_y_la_miniatura_a_400(client, repo, crepo, token):
    comercio(repo)
    a = crepo.assets[_subir(client, token, datos=jpg(3000, 2000)).json()["asset"]["id"]]
    assert (a["width"], a["height"]) == (2048, 1365)
    with Image.open(content_storage.safe_path(a["thumb_path"])) as im:
        assert max(im.size) == 400


def test_una_foto_chica_se_guarda_pero_no_entra_en_los_videos(client, repo, token):
    comercio(repo)
    b = _subir(client, token, datos=jpg(900, 600)).json()
    assert b["asset"]["too_small"] is True
    assert any("chica" in w for w in b["warnings"])
    lista = client.get("/admin/content/merchants/com-1/assets", headers=h(token)).json()
    assert lista["usable_for_video"] == 0 and lista["min_for_video"] == 4


def test_sin_permiso_difusion_es_403_y_sin_token_401(client, repo):
    comercio(repo)
    mod = auth.make_token("m@uruku.bo", rol="moderador")
    assert _subir(client, mod).status_code == 403
    assert client.get("/admin/content/merchants/com-1/assets").status_code == 401


def test_comercio_inexistente_es_404(client, token):
    assert _subir(client, token, cid="no-esta").status_code == 404


def test_una_imagen_invalida_es_400(client, repo, token):
    comercio(repo)
    r = _subir(client, token, datos=b"esto no es una imagen")
    assert r.status_code == 400 and r.json()["detail"] == "El archivo no es una imagen válida"


def test_mas_de_15_mb_es_413(client, repo, token):
    comercio(repo)
    r = _subir(client, token, datos=b"0" * (15 * 1024 * 1024 + 1024))
    assert r.status_code == 413


def test_personas_sin_confirmar_es_409_con_codigo(client, repo, crepo, token):
    comercio(repo)
    r = _subir(client, token, has_people="true")
    assert r.status_code == 409
    assert r.json()["detail"] == {"codigo": "people_not_confirmed",
                                  "mensaje": "Confirmá que las personas de la foto aceptaron aparecer"}
    assert not crepo.assets
    ok = _subir(client, token, has_people="true", people_ok="true")
    assert ok.status_code == 200 and ok.json()["asset"]["people_ok"] is True


def test_un_reintento_con_el_mismo_source_sha256_es_duplicado_y_no_escribe(client, repo, crepo, token):
    comercio(repo)
    sha = "a" * 64
    primero = _subir(client, token, source_sha256=sha).json()
    antes = _archivos(settings.content_dir)
    segundo = _subir(client, token, source_sha256=sha, datos=jpg(seed=99)).json()
    assert segundo["duplicate"] is True and segundo["asset"]["id"] == primero["asset"]["id"]
    assert _archivos(settings.content_dir) == antes and len(crepo.assets) == 1


def test_la_misma_foto_sin_source_sha256_tambien_es_duplicado(client, repo, crepo, token):
    comercio(repo)
    datos = jpg(seed=5)
    a = _subir(client, token, datos=datos).json()
    b = _subir(client, token, datos=datos).json()
    assert b["duplicate"] is True and b["asset"]["id"] == a["asset"]["id"] and len(crepo.assets) == 1


def test_source_sha256_mal_formado_es_400(client, repo, token):
    comercio(repo)
    assert _subir(client, token, source_sha256="xyz").status_code == 400


def test_mostrar_en_la_ficha_copia_a_la_galeria(client, repo, crepo, token):
    comercio(repo)
    r = _subir(client, token, show_in_ficha="true").json()
    assert r["ficha"] == {"requested": True, "added": True, "reason": None}
    assert len(repo.comercio_fotos) == 1
    assert crepo.assets[r["asset"]["id"]]["gallery_photo_id"] == repo.comercio_fotos[0]["id"]


def test_mostrar_en_la_ficha_en_el_tope_guarda_en_el_banco_igual(client, repo, crepo, token):
    comercio(repo)
    repo.planes["publica"]["fotos_max"] = 1
    repo.comercio_fotos.append({"id": "g0", "comercio_id": "com-1", "url": "x", "thumb_url": "x", "orden": 0})
    r = _subir(client, token, show_in_ficha="true")
    assert r.status_code == 200
    assert r.json()["ficha"] == {"requested": True, "added": False, "reason": "tope"}
    assert len(crepo.assets) == 1 and len(repo.comercio_fotos) == 1


def test_tope_de_espacio_del_banco_es_507(client, repo, token, monkeypatch):
    comercio(repo)
    monkeypatch.setattr(settings, "content_dir_max_gb", 0)
    r = _subir(client, token)
    assert r.status_code == 507
    assert r.json()["detail"] == "El banco de contenido llegó a su tope de espacio. Avisale al admin."


def test_poco_disco_libre_tambien_es_507(client, repo, token, monkeypatch):
    comercio(repo)
    monkeypatch.setattr(settings, "content_min_free_gb", 10 ** 9)
    assert _subir(client, token).status_code == 507


def test_content_dir_dentro_de_fotos_dir_apaga_el_banco_con_503(client, repo, token, monkeypatch):
    comercio(repo)
    monkeypatch.setattr(settings, "content_dir", str(Path(settings.fotos_dir) / "privado"))
    r = _subir(client, token)
    assert r.status_code == 503 and r.json()["detail"] == "El banco de contenido no está configurado"


def test_baja_logica_la_fila_queda_y_deja_de_listarse(client, repo, crepo, token):
    comercio(repo)
    aid = _subir(client, token).json()["asset"]["id"]
    assert client.delete(f"/admin/content/assets/{aid}", headers=h(token)).json() == {"ok": True}
    fila = crepo.assets[aid]
    assert fila["activo"] is False and fila["deactivated_by"] == "ana@uruku.bo" and fila["deactivated_at"]
    assert content_storage.safe_path(fila["file_path"]).is_file()         # el archivo se purga a los 30 días
    assert client.get("/admin/content/merchants/com-1/assets", headers=h(token)).json()["items"] == []
    assert client.delete(f"/admin/content/assets/{aid}", headers=h(token)).status_code == 404


def test_patch_de_la_foto(client, repo, crepo, token):
    comercio(repo)
    aid = _subir(client, token).json()["asset"]["id"]
    r = client.patch(f"/admin/content/assets/{aid}", headers=h(token), json={"usable_for_social": False})
    assert r.status_code == 200 and r.json()["usable_for_social"] is False
    assert client.patch(f"/admin/content/assets/{aid}", headers=h(token), json={}).status_code == 400
    assert client.patch("/admin/content/assets/no", headers=h(token), json={"has_people": True}).status_code == 404


# ── la app de campo ──────────────────────────────────────────────────────────

def _subir_campo(client, agente_token, cid, **form):
    return client.post(f"/campo/mis-comercios/{cid}/content-assets", headers=h(agente_token),
                       files={"foto": ("f.jpg", BytesIO(jpg()), "image/jpeg")}, data=form)


def test_el_agente_sube_al_banco_de_su_comercio(client, repo, crepo, agente_token):
    comercio(repo, cargado_por=AGENTE)
    r = _subir_campo(client, agente_token, "com-1")
    assert r.status_code == 200, r.text
    assert crepo.assets[r.json()["asset"]["id"]]["source"] == "agent_upload"


def test_el_agente_no_toca_un_comercio_de_otra_ciudad(client, repo, agente_token):
    comercio(repo, cargado_por="otro@uruku.bo", ciudad_id="ciu-santa-cruz")
    assert _subir_campo(client, agente_token, "com-1").status_code == 404
    assert client.get("/campo/mis-comercios/com-1/content-assets", headers=h(agente_token)).status_code == 404


def test_el_listado_del_agente_trae_la_autorizacion_vigente(client, repo, crepo, agente_token):
    comercio(repo, cargado_por=AGENTE)
    vacio = client.get("/campo/mis-comercios/com-1/content-assets", headers=h(agente_token)).json()
    assert vacio["social_consent"]["granted"] is None and vacio["items"] == []
    autorizar(crepo, "com-1", via="agent_visit")
    lista = client.get("/campo/mis-comercios/com-1/content-assets", headers=h(agente_token)).json()
    assert lista["social_consent"]["granted"] is True and lista["social_consent"]["via"] == "agent_visit"


def test_el_agente_en_el_tope_de_la_galeria_no_reemplaza(client, repo, crepo, agente_token):
    comercio(repo, cargado_por=AGENTE)
    repo.planes["publica"]["fotos_max"] = 1
    repo.comercio_fotos.append({"id": "g0", "comercio_id": "com-1", "url": "x", "thumb_url": "x", "orden": 0})
    r = _subir_campo(client, agente_token, "com-1", show_in_ficha="true").json()
    assert r["ficha"]["reason"] == "tope" and len(repo.comercio_fotos) == 1 and len(crepo.assets) == 1


# ── buscador de comercios ────────────────────────────────────────────────────

def test_buscador_de_comercios_con_conteos_y_recientes(client, repo, crepo, token):
    comercio(repo, "com-1", nombre="Vidriería Pacheco")
    comercio(repo, "com-2", nombre="Kiosco Ana", plan="gratis")
    autorizar(crepo, "com-1")
    banco(crepo, "com-1", 3, uploaded_by="ana@uruku.bo")
    repo.comercio_fotos.append({"id": "g", "comercio_id": "com-1", "url": "x", "thumb_url": "x"})
    r = client.get("/admin/content/merchants?q=vidri", headers=h(token)).json()
    assert [m["nombre"] for m in r["items"]] == ["Vidriería Pacheco"]
    m = r["items"][0]
    assert m["is_subscriber"] is True and m["social_consent"]["granted"] is True
    assert (m["bank_photos"], m["bank_photos_usable"], m["gallery_photos"]) == (3, 3, 1)
    assert [x["id"] for x in r["recent"]] == ["com-1"]
    todos = client.get("/admin/content/merchants", headers=h(token)).json()["items"]
    assert {x["id"]: x["is_subscriber"] for x in todos} == {"com-1": True, "com-2": False}
    assert client.get("/admin/content/merchants?ciudad=no-existe", headers=h(token)).status_code == 400


# ── URLs firmadas ────────────────────────────────────────────────────────────

def test_la_miniatura_se_ve_con_la_url_firmada_y_con_cabeceras_de_privado(client, repo, token):
    comercio(repo)
    asset = _subir(client, token).json()["asset"]
    r = client.get(asset["thumb_url"])
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    assert r.headers["cache-control"] == "private, no-store"
    assert r.headers["x-content-type-options"] == "nosniff" and r.headers["x-robots-tag"] == "noindex"
    assert client.get(asset["file_url"]).status_code == 200


def test_firma_adulterada_o_de_otro_archivo_es_403(client, repo, token):
    comercio(repo)
    a = _subir(client, token).json()["asset"]
    ruta, query = a["thumb_url"].split("?")
    assert client.get(ruta + "?" + query.replace("sig=", "sig=x")).status_code == 403
    assert client.get(ruta.replace("/thumb", "/file") + "?" + query).status_code == 403     # firma de otro `kind`
    assert client.get(ruta.replace(a["id"], "otro-id") + "?" + query).status_code == 403
    assert client.get(ruta + "?exp=999999999999&sig=" + query.split("sig=")[1]).status_code == 403


def test_url_vencida_es_403_con_su_mensaje(client, repo, token):
    comercio(repo)
    a = _subir(client, token).json()["asset"]
    exp = int(time.time()) - 5
    firma = content_storage.firmar("asset", a["id"], "thumb", exp)
    r = client.get(f"/content/files/asset/{a['id']}/thumb?exp={exp}&sig={firma}")
    assert r.status_code == 403 and r.json()["detail"] == "El enlace venció. Volvé a abrir la pantalla."


def test_la_firma_sirve_con_el_ttl_de_15_minutos(repo):
    ruta = content_storage.ruta_firmada("asset", "abc", "thumb", ahora=1000)
    assert "exp=1900" in ruta
    assert content_storage.verificar("asset", "abc", "thumb", 1900, content_storage.firmar("asset", "abc", "thumb", 1900), ahora=1899) == "ok"
    assert content_storage.verificar("asset", "abc", "thumb", 1900, content_storage.firmar("asset", "abc", "thumb", 1900), ahora=1901) == "vencida"
    assert content_storage.verificar("asset", "abc", "video", 1900, "x" * 43) == "invalida"
    assert content_storage.verificar("piece", "abc", "thumb", 1900, "x" * 43) == "invalida"


def test_una_foto_dada_de_baja_ya_no_se_ve(client, repo, token):
    comercio(repo)
    a = _subir(client, token).json()["asset"]
    client.delete(f"/admin/content/assets/{a['id']}", headers=h(token))
    assert client.get(a["thumb_url"]).status_code == 404


def test_safe_path_rechaza_rutas_fuera_del_directorio():
    assert content_storage.safe_path("../../etc/passwd") is None
    assert content_storage.safe_path("assets/../../x") is None
    assert content_storage.safe_path("") is None and content_storage.safe_path(None) is None
    assert content_storage.safe_path("assets/a/b.jpg") is not None


def test_dir_seguro(monkeypatch):
    assert content_storage.dir_seguro()
    monkeypatch.setattr(settings, "content_dir", settings.fotos_dir)
    assert not content_storage.dir_seguro()
    monkeypatch.setattr(settings, "content_dir", str(Path(settings.fotos_dir).parent))
    assert not content_storage.dir_seguro()
