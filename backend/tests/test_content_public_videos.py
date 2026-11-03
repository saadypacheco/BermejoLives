"""Los videos de URUKU en la home: `GET /public/videos` y sus archivos (docs/contenido-redes-tecnico.md §15.1)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.services import content_storage
from tests.content_helpers import autorizar, comercio, hoy, pieza

VIDEO = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 40
PORTADA = b"\xff\xd8\xff\xe0cover"


def _sembrar(crepo, n, *, comercio_id="com-1", pilar="comercio_del_dia", ciudad_id="ciu-1", posted=True,
             facts=None, dias=1, **extra):
    """Una pieza publicada con sus archivos en el disco y un posteo en TikTok."""
    base = f"renders/2026-11/{n}"
    content_storage.guardar(f"{base}/video.mp4", VIDEO)
    content_storage.guardar(f"{base}/cover.jpg", PORTADA)
    kw = dict(dia=hoy() - timedelta(days=dias), status="published", pilar=pilar, video_path=f"{base}/video.mp4",
              cover_path=f"{base}/cover.jpg", ciudad_id=ciudad_id, duration_s=17.5,
              published_at=(datetime.now(timezone.utc) - timedelta(hours=10 - n)).isoformat())
    if facts is not None:
        kw["facts"] = facts
    kw.update(extra)
    p = pieza(crepo, comercio_id, **kw)
    crepo.insert_posts([{"piece_id": p["id"], "network": "tiktok", "ref_tag": f"tt-{n}",
                         "status": "posted" if posted else "pending",
                         "post_url": f"https://www.tiktok.com/@uruku/video/{n}"},
                        {"piece_id": p["id"], "network": "instagram", "ref_tag": f"ig-{n}", "status": "posted",
                         "post_url": f"https://www.instagram.com/reel/{n}/"} if posted else
                        {"piece_id": p["id"], "network": "instagram", "ref_tag": f"ig-{n}", "status": "pending"}])
    return p


@pytest.fixture
def una(repo, crepo):
    comercio(repo)
    autorizar(crepo, "com-1")
    return _sembrar(crepo, 1)


def _ids(client, qs=""):
    r = client.get("/public/videos" + qs)
    assert r.status_code == 200, r.text
    return [i["id"] for i in r.json()["items"]]


def test_la_lista_trae_el_contrato_de_la_home(client, una):
    r = client.get("/public/videos?city=bermejo")
    assert r.status_code == 200
    (v,) = r.json()["items"]
    assert v == {
        "id": una["id"], "title": "Local com-1", "comercio": {"nombre": "Local com-1", "slug": "local-com-1"},
        "rubro": None, "city_slug": "bermejo", "published_at": una["published_at"], "duration_s": 17.5,
        "cover_url": f"/public/videos/{una['id']}/cover", "video_url": f"/public/videos/{una['id']}/video",
        "network_links": {"tiktok": "https://www.tiktok.com/@uruku/video/1",
                          "instagram": "https://www.instagram.com/reel/1/"}}
    assert set(r.json()) == {"items"}


def test_no_hace_falta_login_ni_se_filtra_nada_privado(client, una):
    r = client.get("/public/videos")
    assert r.status_code == 200
    texto = r.text
    for privado in ("share_token", "video_path", "cover_path", "recorded_by", "caption", "sig=", "exp="):
        assert privado not in texto


def test_un_compilado_sale_sin_comercio_y_con_titulo_de_ofertas(repo, crepo, client):
    comercio(repo)
    autorizar(crepo, "com-1")
    comercio(repo, "com-2")
    autorizar(crepo, "com-2")
    p = _sembrar(crepo, 2, comercio_id=None, pilar="ofertas",
                 facts={"pillar": "ofertas", "ciudad": "Bermejo", "hashtags_allowed": []})
    crepo.insert_sources([{"piece_id": p["id"], "position": 1, "source_type": "asset", "comercio_id": "com-1"},
                          {"piece_id": p["id"], "position": 2, "source_type": "asset", "comercio_id": "com-2"}])
    (v,) = client.get("/public/videos").json()["items"]
    assert v["id"] == p["id"] and v["comercio"] is None and v["title"] == "Ofertas de la semana"
    assert v["city_slug"] == "bermejo"


def test_una_pieza_no_posteada_no_aparece_ni_se_baja(client, crepo, una):
    nueva = _sembrar(crepo, 2, posted=False, dias=2)
    assert _ids(client) == [una["id"]]
    assert client.get(f"/public/videos/{nueva['id']}/video").status_code == 404
    assert client.get(f"/public/videos/{nueva['id']}/cover").status_code == 404


def test_una_pieza_que_no_esta_publicada_no_aparece(client, crepo, una):
    crepo.pieces[una["id"]]["status"] = "skipped"
    assert _ids(client) == []
    assert client.get(f"/public/videos/{una['id']}/video").status_code == 404


def test_comercio_de_baja_no_aparece_y_su_archivo_es_404(client, repo, una):
    repo.comercios["com-1"]["activo"] = False
    assert _ids(client) == []
    for kind in ("video", "cover"):
        assert client.get(f"/public/videos/{una['id']}/{kind}").status_code == 404


def test_autorizacion_retirada_no_aparece_y_su_archivo_es_404(client, crepo, una):
    autorizar(crepo, "com-1", granted=False)
    assert _ids(client) == []
    assert client.get(f"/public/videos/{una['id']}/video").status_code == 404
    autorizar(crepo, "com-1", granted=True)                      # vuelve a autorizar: vuelve a verse
    assert _ids(client) == [una["id"]]


def test_comercio_sin_autorizacion_nunca_registrada_no_aparece(repo, crepo, client):
    comercio(repo)
    _sembrar(crepo, 1)
    assert _ids(client) == []


def test_en_un_compilado_basta_un_comercio_sin_autorizacion_o_de_baja(repo, crepo, client):
    comercio(repo)
    autorizar(crepo, "com-1")
    comercio(repo, "com-2")
    autorizar(crepo, "com-2")
    p = _sembrar(crepo, 3, comercio_id=None, pilar="ofertas", facts={"pillar": "ofertas", "ciudad": "Bermejo"})
    crepo.insert_sources([{"piece_id": p["id"], "position": 1, "source_type": "asset", "comercio_id": "com-1"},
                          {"piece_id": p["id"], "position": 2, "source_type": "asset", "comercio_id": "com-2"}])
    assert _ids(client) == [p["id"]]
    autorizar(crepo, "com-2", granted=False)
    assert _ids(client) == [] and client.get(f"/public/videos/{p['id']}/video").status_code == 404
    autorizar(crepo, "com-2", granted=True)
    repo.comercios["com-2"]["activo"] = False
    assert _ids(client) == [] and client.get(f"/public/videos/{p['id']}/cover").status_code == 404


def test_video_purgado_o_sin_archivo_no_aparece(client, crepo, una):
    otra = _sembrar(crepo, 2, dias=2)
    crepo.pieces[una["id"]]["files_purged_at"] = datetime.now(timezone.utc).isoformat()
    content_storage.borrar(crepo.pieces[otra["id"]]["video_path"])          # purgado en disco, fila sin marcar
    assert _ids(client) == []
    assert client.get(f"/public/videos/{una['id']}/video").status_code == 404
    assert client.get(f"/public/videos/{otra['id']}/video").status_code == 404
    assert client.get(f"/public/videos/{otra['id']}/cover").status_code == 404


def test_filtra_por_ciudad_y_ciudad_desconocida_es_lista_vacia(repo, crepo, client, una):
    comercio(repo, "com-sc", ciudad_id="ciu-santa-cruz")
    autorizar(crepo, "com-sc")
    sc = _sembrar(crepo, 2, dias=2, comercio_id="com-sc", ciudad_id="ciu-santa-cruz",
                  facts={"pillar": "comercio_del_dia", "nombre": "Local sc", "slug": "local-sc", "ciudad": "Santa Cruz"})
    assert set(_ids(client)) == {una["id"], sc["id"]}
    assert _ids(client, "?city=bermejo") == [una["id"]]
    assert _ids(client, "?city=santa-cruz") == [sc["id"]]
    assert client.get("/public/videos?city=santa-cruz").json()["items"][0]["city_slug"] == "santa-cruz"
    assert _ids(client, "?city=no-existe") == []
    assert client.get("/public/videos?city=Bermejo;drop").status_code == 422


def test_orden_por_fecha_de_publicacion_descendente_y_limit(repo, crepo, client):
    comercio(repo)
    autorizar(crepo, "com-1")
    piezas = [_sembrar(crepo, n, dias=n) for n in range(1, 6)]            # el 5 es el más nuevo (published_at)
    esperado = [p["id"] for p in sorted(piezas, key=lambda p: p["published_at"], reverse=True)]
    assert _ids(client) == esperado
    assert _ids(client, "?limit=2") == esperado[:2]
    assert _ids(client, "?limit=0") == esperado[:1]                      # el mínimo es 1
    assert len(_ids(client, "?limit=999")) == 5                          # el tope es 24, y hay 5
    assert client.get("/public/videos?limit=abc").status_code == 422


def test_limit_tope_24(repo, crepo, client):
    comercio(repo)
    autorizar(crepo, "com-1")
    for n in range(26):
        _sembrar(crepo, n, dias=n + 1)
    assert len(_ids(client, "?limit=100")) == 24
    assert len(_ids(client)) == 12


def test_el_video_sale_con_cabeceras_publicas_y_sin_gzip(client, una):
    r = client.get(f"/public/videos/{una['id']}/video", headers={"Accept-Encoding": "gzip"})
    assert r.status_code == 200 and r.content == VIDEO and r.headers["content-type"] == "video/mp4"
    assert r.headers["cache-control"] == "public, max-age=3600"
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "content-encoding" not in r.headers and "content-disposition" not in r.headers
    c = client.get(f"/public/videos/{una['id']}/cover", headers={"Accept-Encoding": "gzip"})
    assert c.status_code == 200 and c.content == PORTADA and c.headers["content-type"] == "image/jpeg"
    assert c.headers["cache-control"] == "public, max-age=3600" and "content-encoding" not in c.headers


def test_el_video_atiende_rangos_206_y_416(client, una):
    ruta = f"/public/videos/{una['id']}/video"
    r = client.get(ruta, headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and r.content == VIDEO[:100]
    assert r.headers["content-range"] == f"bytes 0-99/{len(VIDEO)}" and r.headers["accept-ranges"] == "bytes"
    assert r.headers["cache-control"] == "public, max-age=3600"
    resto = client.get(ruta, headers={"Range": "bytes=10000-"})
    assert resto.status_code == 206 and resto.content == VIDEO[10000:]
    assert client.get(ruta, headers={"Range": "bytes=99999999-"}).status_code == 416


def test_ids_con_mala_forma_o_desconocidos_son_404(client, una):
    for malo in ("no-es-uuid", "123", "..%2F..%2Fetc%2Fpasswd", "%00", "00000000-0000-0000-0000-000000000000",
                 "{" + una["id"] + "}", "urn:uuid:" + una["id"]):
        for kind in ("video", "cover"):
            assert client.get(f"/public/videos/{malo}/{kind}").status_code == 404, (malo, kind)


def test_una_ruta_adulterada_en_la_base_no_sale_del_directorio(client, crepo, una):
    crepo.pieces[una["id"]]["video_path"] = "../../../../etc/passwd"
    assert client.get(f"/public/videos/{una['id']}/video").status_code == 404
    assert _ids(client) == []


def test_las_redes_sin_link_o_con_link_raro_no_se_devuelven(client, crepo, una):
    posts = [p for p in crepo.posts.values() if p["piece_id"] == una["id"]]
    for p in posts:
        if p["network"] == "instagram":
            p["post_url"] = "javascript:alert(1)"
        else:
            p["post_url"] = None
    (v,) = client.get("/public/videos").json()["items"]
    assert v["network_links"] == {}


# ═══════════════════════════════════════ la tarea «Entregar el video a mano» (sin wa.me, con descarga)

def _tarea_de_entrega(crepo, pieza_, **extra):
    return crepo.insert_task({"comercio_id": "com-1", "kind": "piece_delivery", "due_on": hoy().isoformat(),
                              "piece_id": pieza_["id"], **extra})


def _admin():
    from app.core import auth
    from tests.content_helpers import h
    return h(auth.make_token("ana.perez@uruku.bo", rol="admin"))


def test_la_tarea_de_entrega_no_trae_whatsapp_y_si_el_link_firmado_de_descarga(client, crepo, una):
    crepo.pieces[una["id"]]["share_token"] = "tok_" + "a" * 20 + "bcd"
    _tarea_de_entrega(crepo, una)
    r = client.get("/admin/subscribers/tasks?cuando=hoy", headers=_admin())
    assert r.status_code == 200, r.text
    (t,) = [x for x in r.json()["items"] if x["kind"] == "piece_delivery"]
    assert t["kind_label"] == "Entregar el video a mano"
    assert t["message_text"] is None and t["whatsapp"] is None and t["message_template"] is None
    dl = t["download_url"]
    assert dl.startswith(f"/content/files/piece/{una['id']}/video?") and dl.endswith("&download=1")
    assert "tok_" not in r.text and "/pieza/" not in r.text                  # el link de la página no se arma
    bajado = client.get(dl)                                                  # el link firmado baja el archivo como adjunto
    assert bajado.status_code == 200 and bajado.content == VIDEO
    assert bajado.headers["content-disposition"].startswith("attachment")


def test_la_tarea_de_entrega_sin_video_no_trae_download_url(client, crepo, una):
    crepo.pieces[una["id"]]["files_purged_at"] = datetime.now(timezone.utc).isoformat()
    _tarea_de_entrega(crepo, una)
    (t,) = [x for x in client.get("/admin/subscribers/tasks?cuando=hoy", headers=_admin()).json()["items"]
            if x["kind"] == "piece_delivery"]
    assert t["download_url"] is None and t["message_text"] is None


def test_las_otras_tareas_no_traen_download_url_y_marcar_entregado_anda_sin_texto(client, crepo, una):
    t = _tarea_de_entrega(crepo, una)
    crepo.insert_task({"comercio_id": "com-1", "kind": "photo_refresh", "due_on": hoy().isoformat()})
    items = client.get("/admin/subscribers/tasks?cuando=hoy", headers=_admin()).json()["items"]
    assert [i["download_url"] for i in items if i["kind"] == "photo_refresh"] == [None]
    r = client.post(f"/admin/subscribers/tasks/{t['id']}/done", headers=_admin(), json={"sent": True})
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "done" and crepo.tasks[t["id"]].get("sent_text") is None
