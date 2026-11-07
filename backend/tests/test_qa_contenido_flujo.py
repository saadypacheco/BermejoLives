"""QA: flujo completo del contenido para redes por la API (FakeContentRepo + render REAL con ffmpeg).

subir 4 fotos -> autorización -> plan de la semana -> render real -> aprobar -> reclamar -> publicar
-> pieza pública por token (Range 206) -> tarea de entrega. Más: aislamiento, firma, entradas maliciosas.
"""
import io
import re
import shutil
import time
from datetime import timedelta

import pytest

from app.core import auth
from app.core.config import settings
from app.services import content_render, content_storage
from tests.content_helpers import AGENTE, comercio, h, hoy, jpg

HAY_FFMPEG = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))

ANA = "ana.perez@uruku.bo"
LUIS = "luis@uruku.bo"


@pytest.fixture
def ana():
    return h(auth.make_token(ANA, rol="admin"))


@pytest.fixture
def luis():
    return h(auth.make_token(LUIS, rol="admin"))


def _subir(client, ana, cid, n=4, **form):
    out = []
    for i in range(n):
        r = client.post(f"/admin/content/merchants/{cid}/assets", headers=ana,
                        files={"foto": (f"f{i}.jpg", jpg(1600, 1200, seed=100 + i), "image/jpeg")}, data=form)
        assert r.status_code == 200, r.text
        out.append(r.json())
    return out


def test_ac_subir_foto_es_idempotente_y_avisa_sin_autorizacion(client, repo, ana):
    comercio(repo)
    r = _subir(client, ana, "com-1", 1, source_sha256="a" * 64)[0]
    assert r["duplicate"] is False and r["asset"]["thumb_url"].startswith("/content/files/asset/")
    assert any("autorización" in w for w in r["warnings"])
    r2 = _subir(client, ana, "com-1", 1, source_sha256="a" * 64)[0]
    assert r2["duplicate"] is True and r2["asset"]["id"] == r["asset"]["id"]


def test_ac_personas_sin_confirmar_409_con_codigo(client, repo, ana):
    comercio(repo)
    r = client.post("/admin/content/merchants/com-1/assets", headers=ana,
                    files={"foto": ("f.jpg", jpg(seed=5), "image/jpeg")}, data={"has_people": "true"})
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "people_not_confirmed"


def test_fotos_del_banco_no_van_a_data_fotos(client, repo, ana, tmp_path):
    comercio(repo)
    _subir(client, ana, "com-1", 2)
    assert not list((tmp_path / "fotos").rglob("*.jpg")) if (tmp_path / "fotos").exists() else True
    assert list((tmp_path / "content").rglob("*.jpg"))
    assert not content_storage.safe_path("../fotos/x.jpg")


def test_firma_manipulada_o_vencida_es_403_y_traversal_404(client, repo, ana):
    comercio(repo)
    a = _subir(client, ana, "com-1", 1)[0]["asset"]
    url = a["thumb_url"]
    assert client.get(url).status_code == 200
    assert client.get(re.sub(r"sig=[^&]+", "sig=" + "0" * 43, url)).status_code == 403
    assert client.get(url.replace("/thumb", "/file")).status_code == 403            # la firma es del kind
    assert client.get(re.sub(r"exp=\d+", "exp=1", url)).status_code == 403
    assert client.get("/content/files/asset/..%2F..%2Fetc/thumb?exp=9999999999&sig=x").status_code in (403, 404)


def test_sin_token_admin_y_con_token_de_comerciante_o_agente_es_401_403(client, repo):
    comercio(repo)
    for hdr in ({}, h(auth.make_comercio_token("com-1", "x@y.com")), h(auth.make_agente_token(AGENTE))):
        for m, p in (("get", "/admin/content/merchants"), ("get", "/admin/content/week"),
                     ("post", "/admin/content/week/plan"), ("get", "/admin/subscribers"),
                     ("post", "/admin/content/posts/x/claim"), ("get", "/admin/content/pieces")):
            r = getattr(client, m)(p, headers=hdr)
            assert r.status_code in (401, 403), (m, p, hdr, r.status_code)


def test_comerciante_no_toca_la_autorizacion_de_otro_y_solo_la_suya(client, repo, crepo):
    comercio(repo, "com-1")
    comercio(repo, "com-2")
    t = h(auth.make_comercio_token("com-1", "x@y.com"))
    assert client.put("/comercio/social-consent", headers=t, json={"granted": True}).status_code == 200
    assert crepo.current_consents(["com-1"])["com-1"]["granted"] is True
    assert "com-2" not in crepo.current_consents(["com-2"])


def test_agente_de_otra_ciudad_no_sube_ni_autoriza(client, repo):
    comercio(repo, "com-1", ciudad_id="ciu-OTRA", cargado_por="otro@x.com")
    t = h(auth.make_agente_token(AGENTE))
    r = client.post("/campo/mis-comercios/com-1/content-assets", headers=t, files={"foto": ("f.jpg", jpg(seed=9), "image/jpeg")})
    assert r.status_code in (403, 404), r.text
    assert client.put("/campo/mis-comercios/com-1/social-consent", headers=t, json={"granted": True}).status_code in (403, 404)
    assert client.get("/campo/mis-comercios/com-1/content-assets", headers=t).status_code in (403, 404)


def test_pieza_publica_token_invalido_o_inexistente(client):
    assert client.get("/public/pieces/corto").status_code == 404
    assert client.get("/public/pieces/" + "A" * 22).status_code == 404
    assert client.get("/public/pieces/" + "A" * 22 + "/video").status_code == 404
    assert client.get("/public/pieces/..%2F..%2Fx/video").status_code == 404


@pytest.mark.skipif(not HAY_FFMPEG, reason="sin ffmpeg")
def _congelar_un_martes(monkeypatch):
    """El plan de la semana sólo llena los días que faltan desde hoy: un sábado o un domingo no
    queda ningún lugar y el plan da 0. Estos tests no pueden depender del día en que se corren."""
    from datetime import datetime, timezone
    from app.services import cargas
    fijo = datetime(2026, 11, 3, 14, 0, tzinfo=timezone.utc)   # martes 3/11, 10:00 en Bolivia
    monkeypatch.setattr(cargas, "ahora_utc", lambda: fijo)


def test_flujo_completo_extremo_a_extremo(client, repo, crepo, ana, luis, monkeypatch, capsys):
    _congelar_un_martes(monkeypatch)
    monkeypatch.setattr(settings, "content_render_timeout_seg", 300)
    comercio(repo)
    # 1) 4 fotos al banco
    subidas = _subir(client, ana, "com-1", 4)
    lista = client.get("/admin/content/merchants/com-1/assets", headers=ana).json()
    assert lista["usable_for_video"] == 4 and lista["min_for_video"] == 4 and "social_consent" in lista
    # 2) sin autorización no se arma nada
    p0 = client.post("/admin/content/week/plan", headers=ana, json={})
    assert p0.status_code == 200 and p0.json()["created"] == 0, p0.json()
    # 3) autorización
    c = client.put("/admin/content/merchants/com-1/social-consent", headers=ana,
                   json={"granted": True, "via": "admin", "note": None})
    assert c.status_code == 200 and c.json()["granted"] is True, c.text
    assert client.put("/admin/content/merchants/com-1/social-consent", headers=ana,
                      json={"granted": True, "via": "invalida"}).status_code == 400
    # 4) plan (idempotente)
    pl = client.post("/admin/content/week/plan", headers=ana, json={"week_start": None})
    assert pl.status_code == 200, pl.text
    plan = pl.json()
    print("PLAN", plan)
    assert plan["created"] >= 1
    assert client.post("/admin/content/week/plan", headers=ana, json={}).json()["created"] == 0
    piezas = [p for p in crepo.pieces.values() if p["comercio_id"] == "com-1"]
    assert len(piezas) == 1 and piezas[0]["status"] == "queued"
    pid = piezas[0]["id"]
    # aprobar antes de renderizar no se puede
    assert client.post(f"/admin/content/pieces/{pid}/approve", headers=ana).status_code == 409
    # 5) render real
    t0 = time.monotonic()
    r = content_render.render_tick(crepo)
    seg = time.monotonic() - t0
    print(f"RENDER_SEGUNDOS={seg:.1f}")
    assert r and r["ok"], r
    det = client.get(f"/admin/content/pieces/{pid}", headers=ana).json()
    assert det["status"] == "ready_for_review" and det["video_url"] and det["cover_url"]
    assert det["render"]["ms"] is not None
    v = client.get(det["video_url"])
    assert v.status_code == 200 and v.headers["content-type"] == "video/mp4"
    assert v.headers["cache-control"] == "private, no-store"
    # 6) aprobar
    ap = client.post(f"/admin/content/pieces/{pid}/approve", headers=ana)
    assert ap.status_code == 200, ap.text
    posts = ap.json()["posts"]
    assert {p["network"] for p in posts} == {"tiktok", "instagram", "facebook", "wa_channel"}
    assert client.post(f"/admin/content/pieces/{pid}/approve", headers=ana).status_code == 409
    # editar una pieza aprobada -> 409
    assert client.patch(f"/admin/content/pieces/{pid}", headers=ana, json={"caption_tiktok": "x"}).status_code == 409
    # 7) reclamar: Luis choca con Ana con {codigo, mensaje}
    por_red = {p["network"]: p for p in posts}
    cl = client.post(f"/admin/content/posts/{por_red['tiktok']['id']}/claim", headers=ana)
    assert cl.status_code == 200 and cl.json()["claimed_by"] == ANA and cl.json()["claimed_by_name"]
    ch = client.post(f"/admin/content/posts/{por_red['tiktok']['id']}/claim", headers=luis)
    assert ch.status_code == 409 and ch.json()["detail"]["codigo"] == "claimed"
    assert client.post(f"/admin/content/posts/{por_red['tiktok']['id']}/release", headers=luis).status_code == 409
    # 8) marcar publicada: link inválido, y sin link ni flag
    assert client.post(f"/admin/content/posts/{por_red['tiktok']['id']}/posted", headers=ana,
                       json={"post_url": "https://evil.com/x"}).status_code == 400
    assert client.post(f"/admin/content/posts/{por_red['tiktok']['id']}/posted", headers=ana,
                       json={"post_url": "javascript:alert(1)"}).status_code == 400
    assert client.post(f"/admin/content/posts/{por_red['tiktok']['id']}/posted", headers=ana, json={}).status_code == 400
    ok = client.post(f"/admin/content/posts/{por_red['tiktok']['id']}/posted", headers=ana,
                     json={"post_url": "https://www.tiktok.com/@uruku/video/123"})
    assert ok.status_code == 200 and ok.json()["status"] == "posted"
    assert client.post(f"/admin/content/posts/{por_red['tiktok']['id']}/posted", headers=ana,
                       json={"without_link": True}).status_code == 409
    for red in ("instagram", "facebook", "wa_channel"):
        s = client.post(f"/admin/content/posts/{por_red[red]['id']}/skip", headers=ana, json={"reason": "no hace falta"})
        assert s.status_code == 200, s.text
    fin = client.get(f"/admin/content/pieces/{pid}", headers=ana).json()
    assert fin["status"] == "published", fin["status"]
    pieza = crepo.pieces[pid]
    token = pieza["share_token"]
    assert len(token) >= 22
    # 9) pieza pública por token
    pub = client.get(f"/public/pieces/{token}")
    assert pub.status_code == 200, pub.text
    d = pub.json()
    assert d["video_url"] == f"/public/pieces/{token}/video" and d["comercio_slug"] == "local-com-1"
    assert "?ref=st-" in d["status_text"] and d["posts"][0]["network"] == "tiktok"
    full = client.get(d["video_url"])
    assert full.status_code == 200 and full.headers["accept-ranges"] == "bytes"
    n = len(full.content)
    rg = client.get(d["video_url"], headers={"Range": "bytes=0-99"})
    assert rg.status_code == 206 and len(rg.content) == 100 and rg.headers["content-range"] == f"bytes 0-99/{n}"
    assert "content-encoding" not in rg.headers
    dl = client.get(d["video_download_url"])
    assert dl.status_code == 200 and "attachment" in dl.headers["content-disposition"]
    assert client.get(d["cover_url"]).headers["content-type"] == "image/jpeg"
    assert "noindex" in rg.headers.get("x-robots-tag", "")
    # 10) tarea de entrega para el paquete del día de la pieza
    dia = str(pieza["scheduled_for"])[:10]
    tod = client.get(f"/admin/content/today?date={dia}", headers=ana).json()
    items = tod["items"]
    assert items and items[0]["delivery"], tod
    dv = items[0]["delivery"]
    assert dv["whatsapp"] is None and dv["message_text"] is None and dv["download_url"].endswith("&download=1")
    # 11) vencido -> 410
    crepo.pieces[pid]["share_expires_at"] = (hoy() - timedelta(days=1)).isoformat() + "T00:00:00+00:00"
    assert client.get(f"/public/pieces/{token}").status_code == 410
    assert client.get(f"/public/pieces/{token}/video").status_code == 410
    # 12) retirar autorización después: lo no publicado se saltea y devuelve lo publicado
    rv = client.put("/admin/content/merchants/com-1/social-consent", headers=ana, json={"granted": False, "via": "admin"})
    assert rv.status_code == 200 and "published_posts" in rv.json(), rv.text
    print("PUBLISHED_POSTS", rv.json()["published_posts"])


def test_sin_emojis_en_textos_aunque_el_comercio_los_tenga_en_nombre_y_rubro(client, repo, crepo, ana, monkeypatch):
    _congelar_un_martes(monkeypatch)
    from app.services import content_captions, subscriber_messages as sm
    comercio(repo, nombre="🔥 Vidriería Pacheco 🔥", rubros={"nombre": "👕 Vidriería", "slug": "vidrios"})
    _subir(client, ana, "com-1", 4)
    client.put("/admin/content/merchants/com-1/social-consent", headers=ana, json={"granted": True, "via": "admin"})
    assert client.post("/admin/content/week/plan", headers=ana, json={}).json()["created"] == 1
    p = next(iter(crepo.pieces.values()))
    textos = [p.get("caption_tiktok"), p.get("caption_ig"), p.get("caption_channel"), " ".join(p.get("hashtags") or []),
              str(p.get("facts"))] + [str(s) for s in crepo.sources]
    for t in textos:
        assert not content_captions._EMOJI.search(t or ""), t
    # plantillas M1-M6
    k = dict(persona_="Ana", firmante_="Luis", comercio="Local X", slug="local-x")
    msgs = [sm.m1_bienvenida("Ana", "Luis", "Local X", "local-x"), sm.m2_entrega("Ana", "Local X", ["tiktok"], "https://t.co", "T" * 22),
            sm.m3_reporte("Ana", "Local X", {"visits": 3, "whatsapp": 1, "terms": ["vidrio"]}, "2026-12-01"),
            sm.m3_reporte("Ana", "Local X", {}, None), sm.m4_fotos("Ana", "Local X"), sm.m5_vence_manana("Ana", "2026-12-01"),
            sm.m6_atrasado("Ana")]
    for m in msgs:
        assert not content_captions._EMOJI.search(m), m
        assert not re.search(r"\bBs\b|\$|\bURUKU-\d|CONFIRMAR-", m), m


def test_retirar_autorizacion_con_pieza_aprobada_saltea_sus_redes_y_no_se_puede_reclamar(client, repo, crepo, ana):
    from tests.content_helpers import autorizar, pieza
    comercio(repo)
    autorizar(crepo, "com-1")
    p = pieza(crepo)
    posts = client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana).json()["posts"]
    rv = client.put("/admin/content/merchants/com-1/social-consent", headers=ana, json={"granted": False, "via": "admin"})
    assert rv.status_code == 200 and rv.json()["pieces_skipped"] == 1
    assert crepo.pieces[p["id"]]["status"] == "skipped"
    for po in posts:
        r = client.post(f"/admin/content/posts/{po['id']}/claim", headers=ana)
        assert r.status_code == 409, (po["network"], r.text)
        r = client.post(f"/admin/content/posts/{po['id']}/posted", headers=ana, json={"without_link": True})
        assert r.status_code == 409, (po["network"], r.text)


def test_transiciones_invalidas_de_pieza(client, repo, crepo, ana):
    from tests.content_helpers import autorizar, pieza
    comercio(repo)
    autorizar(crepo, "com-1")
    for st in ("queued", "rendering", "approved", "published", "skipped"):
        p = pieza(crepo, status=st, dia=hoy() + timedelta(days=2 + ("queued rendering approved published skipped".split().index(st))))
        assert client.post(f"/admin/content/pieces/{p['id']}/retry", headers=ana).status_code == 409, st
        assert client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana).status_code == 409, st
    pub = pieza(crepo, status="published", dia=hoy() + timedelta(days=9))
    assert client.post(f"/admin/content/pieces/{pub['id']}/skip", headers=ana, json={"reason": "other"}).status_code == 409
    assert client.put(f"/admin/content/pieces/{pub['id']}/sources", headers=ana, json={"remove_positions": [1]}).status_code == 409
    assert client.patch(f"/admin/content/pieces/{pub['id']}", headers=ana, json={"caption_ig": "x"}).status_code == 409
    # lote: ids duplicados y ajenos no rompen
    r = client.post("/admin/content/pieces/approve-batch", headers=ana, json={"ids": [pub["id"], "no-existe"]})
    assert r.status_code == 200 and r.json()["approved"] == [] and len(r.json()["refused"]) == 2
    assert client.post("/admin/content/pieces/approve-batch", headers=ana, json={"ids": []}).status_code == 422
    assert client.get("/admin/content/pieces?status=inventado", headers=ana).status_code == 400
    assert client.get("/admin/content/week?start=2026-11-03", headers=ana).status_code == 400    # martes
    assert client.get("/admin/content/week?start=basura", headers=ana).status_code == 400


def test_link_de_otra_red_o_http_se_rechaza(client, repo, crepo, ana):
    from tests.content_helpers import autorizar, pieza
    comercio(repo)
    autorizar(crepo, "com-1")
    p = pieza(crepo)
    posts = {x["network"]: x for x in client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana).json()["posts"]}
    malos = {"tiktok": ["http://www.tiktok.com/@a/video/1", "https://tiktok.com.evil.com/x", "https://www.instagram.com/p/x"],
             "instagram": ["https://www.tiktok.com/@a/video/1"], "wa_channel": ["https://whatsapp.com/other"]}
    for red, urls in malos.items():
        for u in urls:
            r = client.post(f"/admin/content/posts/{posts[red]['id']}/posted", headers=ana, json={"post_url": u})
            assert r.status_code == 400, (red, u, r.status_code)
