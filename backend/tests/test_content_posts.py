"""Aprobar, revisar, reclamar y publicar a mano: el flujo del modo B por la API."""
from datetime import datetime, timedelta, timezone

import pytest

from app.core import auth
from app.core.config import settings
from tests.content_helpers import autorizar, comercio, h, hoy, pieza


@pytest.fixture
def ana():
    return h(auth.make_token("ana.perez@uruku.bo", rol="admin"))


@pytest.fixture
def luis():
    return h(auth.make_token("luis@uruku.bo", rol="admin"))


@pytest.fixture
def base(repo, crepo):
    comercio(repo)
    autorizar(crepo, "com-1")
    return pieza(crepo)


def _aprobar(client, ana, pid):
    r = client.post(f"/admin/content/pieces/{pid}/approve", headers=ana)
    assert r.status_code == 200, r.text
    return r.json()


def _post(crepo, pid, red):
    return next(p for p in crepo.posts.values() if p["piece_id"] == pid and p["network"] == red)


def test_aprobar_crea_una_fila_por_red_con_su_ref_tag(client, crepo, ana, base):
    r = _aprobar(client, ana, base["id"])
    assert r["status"] == "approved" and r["approved_by"] == "ana.perez@uruku.bo" and r["approved_at"]
    redes = {p["network"]: p for p in r["posts"]}
    assert set(redes) == {"tiktok", "instagram", "facebook", "wa_channel"}
    mmdd = (hoy() + timedelta(days=1)).strftime("%m%d")
    assert redes["tiktok"]["ref_tag"] == f"tt-local-com-1-{mmdd}" and redes["facebook"]["ref_tag"] == f"fb-local-com-1-{mmdd}"
    assert redes["instagram"]["ref_tag"].startswith("ig-") and redes["wa_channel"]["ref_tag"].startswith("canal-")
    assert all(p["status"] == "pending" for p in redes.values())
    assert "?ref=fb-local-com-1" in redes["facebook"]["caption_text"] and "?ref" not in redes["tiktok"]["caption_text"]
    assert redes["tiktok"]["network_label"] == "TikTok"


def test_las_redes_salen_de_la_configuracion(client, crepo, ana, base, monkeypatch):
    monkeypatch.setattr(settings, "content_networks", "tiktok, instagram, inventada")
    assert {p["network"] for p in _aprobar(client, ana, base["id"])["posts"]} == {"tiktok", "instagram"}


@pytest.mark.parametrize("estado", ["queued", "rendering", "approved", "published", "skipped", "failed"])
def test_aprobar_fuera_de_ready_for_review_es_409(client, crepo, ana, repo, estado):
    comercio(repo)
    autorizar(crepo, "com-1")
    p = pieza(crepo, status=estado)
    r = client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana)
    assert r.status_code == 409 and r.json()["detail"] == "Sólo se aprueba una pieza lista para revisar"


def test_aprobar_sin_autorizacion_vigente_es_409(client, crepo, ana, repo):
    comercio(repo)
    p = pieza(crepo)
    r = client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana)
    assert r.status_code == 409 and r.json()["detail"] == "El comercio retiró la autorización para redes"
    autorizar(crepo, "com-1", granted=False)
    assert client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana).status_code == 409
    assert crepo.pieces[p["id"]]["status"] == "ready_for_review"


def test_aprobar_pide_el_permiso_difusion(client, base):
    mod = h(auth.make_token("m@u", rol="moderador"))
    assert client.post(f"/admin/content/pieces/{base['id']}/approve", headers=mod).status_code == 403
    assert client.post(f"/admin/content/pieces/{base['id']}/approve").status_code == 401
    assert client.post("/admin/content/pieces/no-existe/approve", headers=h(auth.make_token("a@u", rol="admin"))).status_code == 404


def test_aprobar_en_lote_solo_las_que_estan_en_verde_y_sin_editar(client, crepo, repo, ana):
    comercio(repo)
    autorizar(crepo, "com-1")
    verde = pieza(crepo, dia=hoy() + timedelta(days=1))
    con_objecion = pieza(crepo, dia=hoy() + timedelta(days=2), caption_checks=["TikTok: Tiene un emoji"])
    editada = pieza(crepo, dia=hoy() + timedelta(days=3), caption_edited=True)
    r = client.post("/admin/content/pieces/approve-batch", headers=ana,
                    json={"ids": [verde["id"], con_objecion["id"], editada["id"], "no-existe"]}).json()
    assert r["approved"] == [verde["id"]]
    assert {x["id"] for x in r["refused"]} == {con_objecion["id"], editada["id"], "no-existe"}
    assert all(x["motivo"] for x in r["refused"])
    assert crepo.pieces[con_objecion["id"]]["status"] == "ready_for_review"
    assert client.post("/admin/content/pieces/approve-batch", headers=ana, json={"ids": []}).status_code == 422
    assert client.post("/admin/content/pieces/approve-batch", headers=ana, json={"ids": ["x"] * 21}).status_code == 422


# ── reclamar ─────────────────────────────────────────────────────────────────

def test_reclamar_y_otra_persona_recibe_409_con_el_nombre(client, crepo, ana, luis, base):
    _aprobar(client, ana, base["id"])
    pid = _post(crepo, base["id"], "tiktok")["id"]
    r = client.post(f"/admin/content/posts/{pid}/claim", headers=ana)
    assert r.status_code == 200 and r.json()["status"] == "claimed" and r.json()["claimed_by"] == "ana.perez@uruku.bo"
    assert r.json()["claimed_by_name"] == "Ana Perez" and r.json()["claim_expires_at"]
    otra = client.post(f"/admin/content/posts/{pid}/claim", headers=luis)
    assert otra.status_code == 409
    assert otra.json()["detail"]["codigo"] == "claimed" and otra.json()["detail"]["mensaje"].startswith("La está publicando Ana Perez desde hace ")
    assert client.post(f"/admin/content/posts/{pid}/claim", headers=ana).status_code == 200      # la misma persona sigue


def test_a_los_20_minutos_otra_persona_puede_tomarla(client, crepo, ana, luis, base):
    _aprobar(client, ana, base["id"])
    post = _post(crepo, base["id"], "tiktok")
    client.post(f"/admin/content/posts/{post['id']}/claim", headers=ana)
    post["claimed_at"] = (datetime.now(timezone.utc) - timedelta(minutes=21)).isoformat()
    leida = client.get(f"/admin/content/pieces/{base['id']}", headers=luis).json()
    assert next(p for p in leida["posts"] if p["network"] == "tiktok")["status"] == "pending"     # se resuelve al leer
    r = client.post(f"/admin/content/posts/{post['id']}/claim", headers=luis)
    assert r.status_code == 200 and r.json()["claimed_by"] == "luis@uruku.bo"


def test_soltar_solo_lo_que_reclamaste_vos(client, crepo, ana, luis, base):
    _aprobar(client, ana, base["id"])
    pid = _post(crepo, base["id"], "tiktok")["id"]
    assert client.post(f"/admin/content/posts/{pid}/release", headers=ana).json()["detail"] == "No la tenías reclamada vos"
    client.post(f"/admin/content/posts/{pid}/claim", headers=ana)
    assert client.post(f"/admin/content/posts/{pid}/release", headers=luis).status_code == 409
    r = client.post(f"/admin/content/posts/{pid}/release", headers=ana)
    assert r.status_code == 200 and r.json()["status"] == "pending" and r.json()["claimed_by"] is None


def test_el_job_diario_libera_los_reclamos_vencidos(client, crepo, ana, base):
    _aprobar(client, ana, base["id"])
    post = _post(crepo, base["id"], "tiktok")
    client.post(f"/admin/content/posts/{post['id']}/claim", headers=ana)
    post["claimed_at"] = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat()
    assert crepo.release_expired_claims((datetime.now(timezone.utc) - timedelta(minutes=20)).isoformat()) == 1
    assert post["status"] == "pending"


# ── salió ────────────────────────────────────────────────────────────────────

URL = {"tiktok": "https://www.tiktok.com/@uruku/video/7000", "instagram": "https://www.instagram.com/reel/Cabc/",
       "facebook": "https://www.facebook.com/uruku/videos/123", "wa_channel": "https://whatsapp.com/channel/0029Va"}


@pytest.mark.parametrize("red, link", [
    ("tiktok", "https://www.instagram.com/reel/x"), ("tiktok", "http://www.tiktok.com/@x/video/1"),
    ("tiktok", "https://eltiktok.com/x"), ("instagram", "https://www.tiktok.com/@x"),
    ("facebook", "javascript:alert(1)"), ("wa_channel", "https://whatsapp.com/otra/cosa"),
    ("wa_channel", "https://www.facebook.com/x"), ("instagram", "no es un link"),
])
def test_un_link_de_otra_red_es_400(client, crepo, ana, base, red, link):
    _aprobar(client, ana, base["id"])
    pid = _post(crepo, base["id"], red)["id"]
    r = client.post(f"/admin/content/posts/{pid}/posted", headers=ana, json={"post_url": link})
    assert r.status_code == 400 and r.json()["detail"].startswith("Ese link no es de ")
    assert _post(crepo, base["id"], red)["status"] == "pending"


@pytest.mark.parametrize("red", ["tiktok", "instagram", "facebook", "wa_channel"])
def test_cada_red_acepta_su_link(client, crepo, ana, base, red):
    _aprobar(client, ana, base["id"])
    pid = _post(crepo, base["id"], red)["id"]
    r = client.post(f"/admin/content/posts/{pid}/posted", headers=ana, json={"post_url": URL[red]})
    assert r.status_code == 200 and r.json()["status"] == "posted" and r.json()["post_url"] == URL[red]


def test_sin_link_hace_falta_marcarlo_y_sin_link_es_valido(client, crepo, ana, base):
    _aprobar(client, ana, base["id"])
    pid = _post(crepo, base["id"], "tiktok")["id"]
    r = client.post(f"/admin/content/posts/{pid}/posted", headers=ana, json={})
    assert r.status_code == 400 and r.json()["detail"] == "Pegá el link o marcá que salió sin link"
    ok = client.post(f"/admin/content/posts/{pid}/posted", headers=ana, json={"without_link": True})
    assert ok.status_code == 200 and ok.json()["posted_without_link"] is True and ok.json()["post_url"] is None
    assert client.post(f"/admin/content/posts/{pid}/posted", headers=ana, json={"without_link": True}).status_code == 409


def test_no_se_marca_publicada_una_red_que_reclamo_otro(client, crepo, ana, luis, base):
    _aprobar(client, ana, base["id"])
    pid = _post(crepo, base["id"], "tiktok")["id"]
    client.post(f"/admin/content/posts/{pid}/claim", headers=ana)
    assert client.post(f"/admin/content/posts/{pid}/posted", headers=luis, json={"without_link": True}).status_code == 409


def test_la_ultima_red_publica_la_pieza_con_token_y_tarea_de_entrega(client, crepo, repo, ana, base):
    crepo.insert_task({"comercio_id": "com-1", "kind": "first_piece", "due_on": hoy().isoformat()})
    _aprobar(client, ana, base["id"])
    for red in ("tiktok", "instagram", "facebook"):
        pid = _post(crepo, base["id"], red)["id"]
        client.post(f"/admin/content/posts/{pid}/posted", headers=ana, json={"post_url": URL[red]})
        assert crepo.pieces[base["id"]]["status"] == "approved"
    assert not crepo.pieces[base["id"]].get("share_token")
    # la última red se saltea: alcanza con que haya una publicada
    pid = _post(crepo, base["id"], "wa_channel")["id"]
    r = client.post(f"/admin/content/posts/{pid}/skip", headers=ana, json={"reason": "sin canal todavía"})
    assert r.status_code == 200 and r.json()["status"] == "skipped"
    p = crepo.pieces[base["id"]]
    assert p["status"] == "published" and p["published_at"] and len(p["share_token"]) >= 22
    vence = datetime.fromisoformat(p["share_expires_at"]) - datetime.fromisoformat(p["published_at"])
    assert vence == timedelta(days=60)
    entrega = [t for t in crepo.tasks.values() if t["kind"] == "piece_delivery"]
    assert len(entrega) == 1 and entrega[0]["piece_id"] == base["id"] and entrega[0]["comercio_id"] == "com-1"
    primera = next(t for t in crepo.tasks.values() if t["kind"] == "first_piece")
    assert primera["status"] == "done" and primera["auto_closed"] is True


def test_si_todas_se_saltean_la_pieza_no_se_publica(client, crepo, ana, base):
    _aprobar(client, ana, base["id"])
    for red in ("tiktok", "instagram", "facebook", "wa_channel"):
        client.post(f"/admin/content/posts/{_post(crepo, base['id'], red)['id']}/skip", headers=ana, json={"reason": "x"})
    assert crepo.pieces[base["id"]]["status"] == "approved"


def test_saltear_una_red_publicada_es_409_y_sin_motivo_400(client, crepo, ana, base):
    _aprobar(client, ana, base["id"])
    pid = _post(crepo, base["id"], "tiktok")["id"]
    assert client.post(f"/admin/content/posts/{pid}/skip", headers=ana, json={"reason": ""}).status_code == 400
    client.post(f"/admin/content/posts/{pid}/posted", headers=ana, json={"without_link": True})
    r = client.post(f"/admin/content/posts/{pid}/skip", headers=ana, json={"reason": "x"})
    assert r.status_code == 409 and r.json()["detail"] == "Ya está publicada"
    assert client.post(f"/admin/content/posts/{pid}/claim", headers=ana).json()["detail"] == "Esta red ya está publicada"


def test_una_pieza_de_ofertas_publicada_no_crea_tarea_de_entrega(client, crepo, ana):
    p = pieza(crepo, None, pilar="ofertas")
    client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana)
    for post in list(crepo.posts.values()):
        client.post(f"/admin/content/posts/{post['id']}/posted", headers=ana, json={"without_link": True})
    assert crepo.pieces[p["id"]]["status"] == "published" and not crepo.tasks


# ── revisión: texto, fotos, saltar, reintentar ───────────────────────────────

def test_editar_textos_pasa_por_el_validador_y_marca_editada(client, crepo, ana, base):
    r = client.patch(f"/admin/content/pieces/{base['id']}", headers=ana,
                     json={"caption_tiktok": "Local com-1 abre de 9 a 17. Buscalo en uruku.bo"})
    assert r.status_code == 200, r.text                                      # un número ajeno lo puede querer la persona
    assert r.json()["caption_edited"] is True and r.json()["caption_tiktok"].startswith("Local com-1 abre")
    for malo, frag in (("Local com-1 😀", "emoji"), ("Local com-1 la mejor", "mejor"), ("Hola", "nombre"), ("Local com-1 envío gratis", "envío")):
        r = client.patch(f"/admin/content/pieces/{base['id']}", headers=ana, json={"caption_ig": malo})
        assert r.status_code == 400 and frag in r.json()["detail"], (malo, r.text)
    assert client.patch(f"/admin/content/pieces/{base['id']}", headers=ana, json={"hashtags": ["#URUKU", "#Raro", "#Otro"]}).status_code == 400
    ok = client.patch(f"/admin/content/pieces/{base['id']}", headers=ana, json={"hashtags": ["URUKU", "#Bermejo", "#Tarija", "#Bolivia"]})
    assert ok.status_code == 200 and ok.json()["hashtags"] == ["#URUKU", "#Bermejo", "#Tarija", "#Bolivia"]
    assert client.patch(f"/admin/content/pieces/{base['id']}", headers=ana, json={}).status_code == 400
    assert client.patch(f"/admin/content/pieces/{base['id']}", headers=ana, json={"caption_ig": "  "}).status_code == 400


def test_una_pieza_aprobada_ya_no_se_edita(client, crepo, ana, base):
    _aprobar(client, ana, base["id"])
    r = client.patch(f"/admin/content/pieces/{base['id']}", headers=ana, json={"caption_ig": "Local com-1 en uruku.bo"})
    assert r.status_code == 409 and r.json()["detail"] == "La pieza ya está aprobada"


def test_saltar_una_pieza_con_motivo(client, crepo, ana, base):
    r = client.post(f"/admin/content/pieces/{base['id']}/skip", headers=ana, json={"reason": "bad_photos", "note": "borrosas"})
    assert r.status_code == 200 and r.json()["status"] == "skipped" and r.json()["skip_reason"] == "bad_photos"
    assert crepo.pieces[base["id"]]["skipped_by"] == "ana.perez@uruku.bo" and crepo.pieces[base["id"]]["skip_note"] == "borrosas"
    assert client.post(f"/admin/content/pieces/{base['id']}/skip", headers=ana, json={"reason": "other"}).status_code == 409
    assert client.post(f"/admin/content/pieces/{base['id']}/skip", headers=ana, json={"reason": "consent_revoked"}).status_code == 400


def test_saltar_una_publicada_es_409(client, crepo, ana, repo):
    comercio(repo)
    p = pieza(crepo, status="published")
    r = client.post(f"/admin/content/pieces/{p['id']}/skip", headers=ana, json={"reason": "other"})
    assert r.status_code == 409 and r.json()["detail"] == "Ya está publicada"


def test_reintentar_solo_una_pieza_con_problemas(client, crepo, ana, repo):
    comercio(repo)
    mala = pieza(crepo, status="failed", render_attempts=3, render_error="boom")
    r = client.post(f"/admin/content/pieces/{mala['id']}/retry", headers=ana)
    assert r.status_code == 200 and r.json()["status"] == "queued" and r.json()["render"]["attempts"] == 0
    assert crepo.pieces[mala["id"]]["render_error"] is None
    r = client.post(f"/admin/content/pieces/{mala['id']}/retry", headers=ana)
    assert r.status_code == 409 and r.json()["detail"] == "Sólo se reintenta una pieza con problemas"


def test_cambiar_fotos_vuelve_a_la_cola(client, crepo, repo, ana):
    from tests.content_helpers import banco
    comercio(repo)
    autorizar(crepo, "com-1")
    fotos = banco(crepo, "com-1", 7)
    p = pieza(crepo)
    crepo.insert_sources([{"piece_id": p["id"], "position": i, "source_type": "asset", "source_id": a["id"], "comercio_id": "com-1",
                           "file_ref": a["file_path"]} for i, a in enumerate(fotos)])
    r = client.put(f"/admin/content/pieces/{p['id']}/sources", headers=ana, json={"remove_positions": [0, 1]})
    assert r.status_code == 200 and r.json()["status"] == "queued" and len(r.json()["sources"]) == 5
    p2 = pieza(crepo, dia=hoy() + timedelta(days=2))
    crepo.insert_sources([{"piece_id": p2["id"], "position": i, "source_type": "asset", "source_id": a["id"], "comercio_id": "com-1",
                           "file_ref": a["file_path"]} for i, a in enumerate(fotos[:4])])
    r = client.put(f"/admin/content/pieces/{p2['id']}/sources", headers=ana, json={"remove_positions": [0]})
    assert r.status_code == 409 and r.json()["detail"]["codigo"] == "no_more_photos"
    assert "Pedile fotos" in r.json()["detail"]["mensaje"]
    assert client.put(f"/admin/content/pieces/{p2['id']}/sources", headers=ana, json={"remove_positions": []}).status_code == 422


def test_listar_piezas_y_estados_invalidos(client, crepo, ana, repo):
    comercio(repo)
    pieza(crepo, status="ready_for_review")
    pieza(crepo, dia=hoy() + timedelta(days=2), status="failed", render_error="faltan fotos")
    pieza(crepo, dia=hoy() + timedelta(days=3), status="published")
    r = client.get("/admin/content/pieces", headers=ana).json()["items"]
    assert sorted(p["status"] for p in r) == ["failed", "ready_for_review"]
    assert r[0]["status_label"] and "sources" in r[0] and "posts" in r[0] and r[0]["hashtags_allowed"]
    assert client.get("/admin/content/pieces?status=published", headers=ana).json()["items"][0]["status"] == "published"
    assert client.get("/admin/content/pieces?status=raro", headers=ana).status_code == 400


def test_semana_con_la_cola(client, crepo, ana, repo):
    comercio(repo)
    lunes = hoy() - timedelta(days=hoy().weekday())
    pieza(crepo, dia=lunes + timedelta(days=2), status="queued")
    r = client.get(f"/admin/content/week?start={lunes.isoformat()}", headers=ana).json()
    assert r["week_start"] == lunes.isoformat() and len(r["days"]) == 7 and r["days"][0]["weekday_label"] == "lunes"
    assert len(r["days"][2]["pieces"]) == 1 and r["queue"]["queued"] == 1
    assert client.get("/admin/content/week?start=2026-11-03", headers=ana).json()["detail"] == "La fecha tiene que ser un lunes"
    assert client.get("/admin/content/week", headers=ana).json()["week_start"] == lunes.isoformat()


# ── paquete del día ──────────────────────────────────────────────────────────

def test_paquete_del_dia(client, crepo, repo, ana):
    comercio(repo)
    autorizar(crepo, "com-1")
    hoy_ = pieza(crepo, dia=hoy(), status="ready_for_review")
    aprobada = pieza(crepo, dia=hoy() - timedelta(days=2), pilar="ofertas", status="ready_for_review")
    _aprobar(client, ana, aprobada["id"])
    client.post(f"/admin/content/pieces/{hoy_['id']}/approve", headers=ana)
    proxima = pieza(crepo, dia=hoy() + timedelta(days=4), status="queued")
    sin_aprobar = pieza(crepo, dia=hoy() + timedelta(days=0), pilar="ofertas", status="ready_for_review")
    r = client.get("/admin/content/today", headers=ana).json()
    assert r["date"] == hoy().isoformat()
    assert [i["piece"]["id"] for i in r["items"]] == [hoy_["id"]] and len(r["items"][0]["posts"]) == 4
    assert [i["piece"]["id"] for i in r["overdue"]] == [aprobada["id"]]          # aprobada de un día anterior con redes pendientes
    assert [p["id"] for p in r["pending_review"]] == [sin_aprobar["id"]]
    assert r["next"] == {"date": proxima["scheduled_for"], "pillar_label": "Comercio del día"}
    assert client.get("/admin/content/today?date=2026-13-45", headers=ana).status_code == 400
    assert client.get(f"/admin/content/today?date={(hoy() + timedelta(days=30)).isoformat()}", headers=ana).json()["items"] == []


def test_paquete_del_dia_trae_el_mensaje_de_entrega_con_whatsapp(client, crepo, repo, ana):
    comercio(repo, whatsapp="59170001234")
    autorizar(crepo, "com-1")
    p = pieza(crepo, dia=hoy(), status="ready_for_review")
    _aprobar(client, ana, p["id"])
    for red in ("tiktok", "instagram", "facebook", "wa_channel"):
        client.post(f"/admin/content/posts/{_post(crepo, p['id'], red)['id']}/posted", headers=ana,
                    json={"post_url": URL[red]})
    item = client.get("/admin/content/today", headers=ana).json()["items"][0]
    d = item["delivery"]
    assert d["whatsapp"] == "59170001234" and d["task_id"]
    token = crepo.pieces[p["id"]]["share_token"]
    assert f"/pieza/{token}" in d["message_text"] and URL["tiktok"] in d["message_text"]
    assert "TikTok" in d["message_text"] and "Local" in d["message_text"]


def test_estado_del_render(client, crepo, ana, repo):
    comercio(repo)
    pieza(crepo, status="queued")
    r = client.get("/admin/content/status", headers=ana).json()
    assert r["render_worker"] == "disabled" and r["queue"]["queued"] == 1 and r["current_piece_id"] is None
    assert set(r["disk"]) == {"content_bytes", "free_bytes", "max_bytes"} and r["disk"]["max_bytes"] == 10 * 1024 ** 3
    assert r["gemini_configured"] in (True, False) and r["last_render"] is None
    assert client.get("/admin/content/status", headers=h(auth.make_token("m@u", rol="moderador"))).status_code == 403


def test_links_de_descarga(client, crepo, repo, ana, tmp_path):
    from app.services import content_storage
    comercio(repo)
    p = pieza(crepo, status="ready_for_review", video_path="renders/2026-11/x/video.mp4", cover_path="renders/2026-11/x/cover.jpg")
    r = client.get(f"/admin/content/pieces/{p['id']}/download-links", headers=ana).json()
    assert r["video_download_url"] == r["video_url"] + "&download=1" and "/content/files/piece/" in r["cover_url"] and r["expires_at"]
    crepo.pieces[p["id"]]["files_purged_at"] = "2026-11-01"
    assert client.get(f"/admin/content/pieces/{p['id']}/download-links", headers=ana).status_code == 410
    nueva = pieza(crepo, dia=hoy() + timedelta(days=3), status="queued")
    assert client.get(f"/admin/content/pieces/{nueva['id']}/download-links", headers=ana).status_code == 404
