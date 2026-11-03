"""La página del comerciante (`/public/pieces/{token}`) y las descargas firmadas del panel."""
from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.services import content_storage
from tests.content_helpers import autorizar, comercio, hoy, pieza

TOKEN = "tok_" + "a" * 20 + "bcd"
VIDEO = b"\x00\x00\x00\x18ftypmp42" + bytes(range(256)) * 40          # 10 KB y pico


@pytest.fixture
def publicada(repo, crepo):
    comercio(repo)
    autorizar(crepo, "com-1")
    content_storage.guardar("renders/2026-11/p1/video.mp4", VIDEO)
    content_storage.guardar("renders/2026-11/p1/cover.jpg", b"\xff\xd8\xff\xe0cover")
    ahora = datetime.now(timezone.utc)
    p = pieza(crepo, dia=hoy() - timedelta(days=1), status="published", video_path="renders/2026-11/p1/video.mp4",
              cover_path="renders/2026-11/p1/cover.jpg", share_token=TOKEN, published_at=ahora.isoformat(),
              share_expires_at=(ahora + timedelta(days=60)).isoformat())
    crepo.insert_posts([{"piece_id": p["id"], "network": "tiktok", "ref_tag": "tt-x", "status": "posted",
                         "post_url": "https://www.tiktok.com/@u/video/1"},
                        {"piece_id": p["id"], "network": "instagram", "ref_tag": "ig-x", "status": "pending"}])
    return p


def test_la_pagina_publica_trae_todo_lo_que_el_front_necesita(client, publicada, monkeypatch):
    monkeypatch.setattr(settings, "sitio_url", "https://uruku.bo")
    r = client.get(f"/public/pieces/{TOKEN}")
    assert r.status_code == 200, r.text
    b = r.json()
    assert b["comercio_nombre"] == "Local com-1" and b["comercio_slug"] == "local-com-1" and b["pillar"] == "comercio_del_dia"
    assert b["video_url"] == f"/public/pieces/{TOKEN}/video" and b["video_download_url"].endswith("/video?download=1")
    assert b["cover_url"].endswith("/cover") and b["published_at"] and b["expires_at"]
    assert b["posts"] == [{"network": "tiktok", "network_label": "TikTok", "post_url": "https://www.tiktok.com/@u/video/1"}]
    assert b["status_text"] == "Mire Local com-1 en URUKU: https://uruku.bo/comercios/local-com-1?ref=st-local-com-1"
    assert set(b) == {"comercio_nombre", "comercio_slug", "pillar", "published_at", "expires_at", "video_url",
                      "video_download_url", "cover_url", "posts", "status_text"}


def test_token_desconocido_o_con_mala_forma_es_404(client, publicada):
    assert client.get("/public/pieces/" + "z" * 30).json()["detail"] == "Esta pieza no existe"
    assert client.get("/public/pieces/corto").status_code == 404
    assert client.get("/public/pieces/" + "z" * 30 + "/video").status_code == 404


def test_una_pieza_que_no_esta_publicada_no_se_ve_aunque_tenga_token(client, crepo, publicada):
    crepo.pieces[publicada["id"]]["status"] = "skipped"
    assert client.get(f"/public/pieces/{TOKEN}").status_code == 404


def test_vencido_es_410_con_su_mensaje(client, crepo, publicada):
    crepo.pieces[publicada["id"]]["share_expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat()
    for ruta in ("", "/video", "/cover"):
        r = client.get(f"/public/pieces/{TOKEN}{ruta}")
        assert r.status_code == 410 and r.json()["detail"] == "Este enlace venció. Pedile uno nuevo a URUKU."


def test_purgado_es_410(client, crepo, publicada):
    crepo.pieces[publicada["id"]]["files_purged_at"] = datetime.now(timezone.utc).isoformat()
    assert client.get(f"/public/pieces/{TOKEN}").status_code == 410
    assert client.get(f"/public/pieces/{TOKEN}/video").status_code == 410


def test_el_video_sale_con_cabeceras_de_privado_y_sin_indexar(client, publicada):
    r = client.get(f"/public/pieces/{TOKEN}/video")
    assert r.status_code == 200 and r.content == VIDEO and r.headers["content-type"] == "video/mp4"
    assert r.headers["cache-control"] == "private, no-store"
    assert r.headers["x-robots-tag"] == "noindex" and r.headers["x-content-type-options"] == "nosniff"
    assert "content-disposition" not in r.headers
    c = client.get(f"/public/pieces/{TOKEN}/cover")
    assert c.status_code == 200 and c.headers["content-type"] == "image/jpeg"


def test_download_1_baja_con_content_disposition_y_nombre_seguro(client, publicada):
    r = client.get(f"/public/pieces/{TOKEN}/video?download=1")
    cd = r.headers["content-disposition"]
    assert cd.startswith("attachment") and "uruku-local-com-1-" in cd and cd.endswith('.mp4"')
    assert r.content == VIDEO


def test_soporta_pedidos_por_rango_para_el_video_del_iphone(client, publicada):
    r = client.get(f"/public/pieces/{TOKEN}/video", headers={"Range": "bytes=0-99"})
    assert r.status_code == 206 and r.content == VIDEO[:100]
    assert r.headers["content-range"] == f"bytes 0-99/{len(VIDEO)}" and r.headers["accept-ranges"] == "bytes"
    resto = client.get(f"/public/pieces/{TOKEN}/video", headers={"Range": "bytes=10000-"})
    assert resto.status_code == 206 and resto.content == VIDEO[10000:]
    assert client.get(f"/public/pieces/{TOKEN}/video", headers={"Range": "bytes=99999999-"}).status_code == 416


def test_el_video_no_se_comprime_con_gzip(client, publicada):
    r = client.get(f"/public/pieces/{TOKEN}/video", headers={"Accept-Encoding": "gzip"})
    assert "content-encoding" not in r.headers and r.content == VIDEO


def test_servido_a_otro_origen_lleva_cors_y_nada_que_lo_bloquee(client, publicada):
    r = client.get(f"/public/pieces/{TOKEN}/video", headers={"Origin": "http://localhost:3000"})
    assert r.headers["access-control-allow-origin"] in ("*", "http://localhost:3000")
    assert "cross-origin-resource-policy" not in r.headers and "x-frame-options" not in r.headers


def test_el_video_firmado_del_panel_tambien_acepta_rangos(client, crepo, publicada):
    ruta = content_storage.ruta_firmada("piece", publicada["id"], "video")
    r = client.get(ruta, headers={"Range": "bytes=5-9"})
    assert r.status_code == 206 and r.content == VIDEO[5:10]
    full = client.get(ruta + "&download=1")
    assert full.status_code == 200 and full.headers["content-disposition"].startswith("attachment")


def test_el_archivo_firmado_de_una_pieza_purgada_o_sin_video_no_se_ve(client, crepo, publicada):
    crepo.pieces[publicada["id"]]["files_purged_at"] = "2026-11-02"
    assert client.get(content_storage.ruta_firmada("piece", publicada["id"], "video")).status_code == 410
    crepo.pieces[publicada["id"]].update({"files_purged_at": None, "status": "queued"})
    assert client.get(content_storage.ruta_firmada("piece", publicada["id"], "video")).status_code == 404


def test_si_el_archivo_no_esta_en_el_disco_es_404(client, publicada):
    content_storage.borrar("renders/2026-11/p1/video.mp4")
    assert client.get(f"/public/pieces/{TOKEN}/video").status_code == 404


def test_una_ruta_adulterada_en_la_base_no_sale_del_directorio(client, crepo, publicada):
    crepo.pieces[publicada["id"]]["video_path"] = "../../../../etc/passwd"
    assert client.get(f"/public/pieces/{TOKEN}/video").status_code == 404


def test_la_pagina_publica_de_un_compilado(client, crepo, publicada):
    crepo.pieces[publicada["id"]].update({"comercio_id": None, "pillar": "ofertas",
                                          "facts": {"pillar": "ofertas", "ciudad": "Bermejo"}})
    b = client.get(f"/public/pieces/{TOKEN}").json()
    assert b["comercio_nombre"] is None and "Ofertas de la semana en Bermejo" in b["status_text"]
