"""QA: contrato front<->back. Las claves que declara frontend/lib/content.ts, subscribers.ts y pieza.ts tienen
que estar en lo que el backend devuelve de verdad (el sobrante del backend se permite pero se imprime)."""
from datetime import timedelta

import pytest

from app.core import auth
from app.services import content_storage
from tests.content_helpers import autorizar, banco, comercio, h, hoy, pieza

CONSENT = {"granted", "via", "recorded_at", "recorded_by", "note"}
ASSET = {"id", "comercio_id", "width", "height", "bytes", "too_small", "usable_for_social", "has_people", "people_ok",
         "use_count", "last_used_at", "thumb_url", "file_url", "created_at", "uploaded_by"}
MERCHANT = {"id", "nombre", "slug", "rubro", "calle", "ciudad_slug", "ciudad_nombre", "is_subscriber", "social_consent",
            "bank_photos", "bank_photos_usable", "gallery_photos", "last_piece_on"}
SUMMARY = {"id", "scheduled_for", "pillar", "pillar_label", "status", "status_label", "comercio", "ciudad_nombre",
           "counts_for_quota", "cover_url", "duration_s", "skip_reason", "render_error"}
PIECE = SUMMARY | {"facts", "caption_tiktok", "caption_ig", "caption_channel", "hashtags", "hashtags_allowed",
                   "caption_engine", "caption_checks", "caption_edited", "sources", "video_url", "render", "posts",
                   "approved_by", "approved_at"}
POST = {"id", "network", "network_label", "status", "ref_tag", "caption_text", "claimed_by", "claimed_at",
        "claim_expires_at", "posted_by", "posted_at", "post_url", "posted_without_link", "skip_reason"}
SOURCE = {"position", "source_type", "thumb_url", "caption_fact", "comercio_nombre"}
SUBSCRIBER = {"comercio_id", "nombre", "slug", "whatsapp", "ciudad_nombre", "plan", "plan_nombre", "plan_cortesia",
              "paga_hasta", "subscription_state", "in_grace", "social_consent", "pieces", "tasks", "contact_person",
              "onboarding_started_at"}
TASK = {"id", "comercio_id", "comercio_nombre", "kind", "kind_label", "due_on", "status", "overdue", "message_template",
        "message_text", "whatsapp", "call_script", "needs_outcome", "piece_id", "report_id", "outcome", "done_by",
        "done_at", "auto_closed"}

extras = []


def contiene(nombre, datos, esperadas):
    faltan = esperadas - set(datos)
    assert not faltan, f"{nombre}: el front espera {sorted(faltan)} y el backend no lo manda"
    sobran = set(datos) - esperadas
    if sobran:
        extras.append((nombre, sorted(sobran)))


@pytest.fixture
def ana():
    return h(auth.make_token("ana@uruku.bo", rol="admin"))


def test_contrato_banco_consent_y_piezas(client, repo, crepo, ana):
    comercio(repo)
    autorizar(crepo, "com-1")
    banco(crepo, "com-1", 4)
    r = client.get("/admin/content/merchants?q=Local", headers=ana).json()
    assert set(r) == {"items", "recent"}
    contiene("merchant", r["items"][0], MERCHANT)
    contiene("merchant.consent", r["items"][0]["social_consent"], CONSENT)
    lista = client.get("/admin/content/merchants/com-1/assets", headers=ana).json()
    contiene("assets.list", lista, {"items", "usable_for_video", "min_for_video"})
    contiene("asset", lista["items"][0], ASSET)
    # sin ningun consent registrado: el shape tiene que seguir siendo el mismo (granted null)
    comercio(repo, "com-2")
    sin = client.get("/admin/content/merchants/com-2/assets", headers=ana).json()["social_consent"]
    contiene("consent.vacio", sin, CONSENT)
    assert sin["granted"] is None
    # piezas
    p = pieza(crepo, status="ready_for_review")
    crepo.insert_sources([{"piece_id": p["id"], "position": 1, "source_type": "asset", "source_id": lista["items"][0]["id"],
                           "caption_fact": None}])
    d = client.get(f"/admin/content/pieces/{p['id']}", headers=ana).json()
    contiene("piece", d, PIECE)
    contiene("piece.source", d["sources"][0], SOURCE)
    contiene("piece.render", d["render"], {"attempts", "next_at", "started_at", "ms"})
    ap = client.post(f"/admin/content/pieces/{p['id']}/approve", headers=ana).json()
    contiene("post", ap["posts"][0], POST)
    sem = client.get("/admin/content/week", headers=ana).json()
    contiene("week", sem, {"week_start", "days", "queue"})
    contiene("week.day", sem["days"][0], {"date", "weekday_label", "pieces"})
    contiene("week.queue", sem["queue"], {"queued", "rendering", "ready_for_review", "failed"})
    lst = client.get("/admin/content/pieces?status=approved,ready_for_review", headers=ana).json()
    assert set(lst) == {"items"}
    st = client.get("/admin/content/status", headers=ana).json()
    contiene("status", st, {"render_worker", "current_piece_id", "queue", "last_render", "disk", "gemini_configured"})
    contiene("status.disk", st["disk"], {"content_bytes", "free_bytes", "max_bytes"})
    today = client.get(f"/admin/content/today?date={(hoy() + timedelta(days=1)).isoformat()}", headers=ana).json()
    contiene("today", today, {"date", "items", "overdue", "pending_review", "next"})
    contiene("today.item", today["items"][0], {"piece", "posts", "delivery"})
    hist = client.get("/admin/content/merchants/com-1/social-consent/history", headers=ana).json()
    assert "items" in hist
    print("EXTRAS (backend manda y el front no declara):", extras)


def test_contrato_revocar_devuelve_forma_distinta_al_alta(client, repo, crepo, ana):
    comercio(repo)
    alta = client.put("/admin/content/merchants/com-1/social-consent", headers=ana,
                      json={"granted": True, "via": "admin", "note": None}).json()
    contiene("consent.alta", alta, CONSENT)
    baja = client.put("/admin/content/merchants/com-1/social-consent", headers=ana,
                      json={"granted": False, "via": "admin", "note": None}).json()
    contiene("consent.baja", baja, {"consent", "pieces_skipped", "published_posts"})


def test_contrato_descargas(client, repo, crepo, ana):
    comercio(repo)
    autorizar(crepo, "com-1")
    content_storage.guardar("renders/x/p/video.mp4", b"0" * 5000)
    content_storage.guardar("renders/x/p/cover.jpg", b"\xff\xd8\xff\xe0c")
    p = pieza(crepo, status="approved", video_path="renders/x/p/video.mp4", cover_path="renders/x/p/cover.jpg")
    dl = client.get(f"/admin/content/pieces/{p['id']}/download-links", headers=ana).json()
    contiene("download-links", dl, {"video_url", "video_download_url", "cover_url", "expires_at"})
    assert client.get(dl["video_download_url"]).headers["content-disposition"].startswith("attachment")


def test_contrato_suscriptores(client, repo, crepo, ana):
    comercio(repo)
    autorizar(crepo, "com-1")
    crepo.insert_task({"comercio_id": "com-1", "kind": "welcome", "due_on": hoy().isoformat()})
    crepo.insert_task({"comercio_id": "com-1", "kind": "churn_call", "due_on": hoy().isoformat()})
    lst = client.get("/admin/subscribers?filtro=todos", headers=ana).json()
    contiene("subs.list", lst, {"items", "total"})
    contiene("subscriber", lst["items"][0], SUBSCRIBER)
    contiene("subscriber.pieces", lst["items"][0]["pieces"], {"quota", "used", "cycle_start", "cycle_end", "next_scheduled_for"})
    contiene("subscriber.tasks", lst["items"][0]["tasks"], {"due_today", "overdue"})
    ts = client.get("/admin/subscribers/tasks?cuando=hoy", headers=ana).json()
    contiene("tasks.list", ts, {"items", "total"})
    contiene("task", ts["items"][0], TASK)
    det = client.get("/admin/subscribers/com-1", headers=ana).json()
    contiene("subscriber.detail", det, {"summary", "profile_check", "tasks", "pieces", "last_report"})
    if det["profile_check"]:
        contiene("profile_check", det["profile_check"][0], {"key", "label", "ok", "auto"})
    for f in ("tareas", "todos", "por_vencer"):
        assert client.get(f"/admin/subscribers?filtro={f}&ciudad=bermejo", headers=ana).status_code in (200, 400)
    for c in ("hoy", "atrasadas", "semana"):
        assert client.get(f"/admin/subscribers/tasks?cuando={c}", headers=ana).status_code == 200
    pr = client.patch("/admin/subscribers/com-1/profile", headers=ana, json={"contact_person": "Ana"}).json()
    contiene("profile.patch", pr, {"ok", "contact_person", "notes"})
    ob = client.post("/admin/subscribers/com-1/onboarding", headers=ana, json={"force": True}).json()
    contiene("onboarding", ob, {"created", "started_at"})
    ids = [t["id"] for t in ts["items"]]
    done = client.post(f"/admin/subscribers/tasks/{ids[0]}/done", headers=ana, json={"sent": True, "outcome": None})
    assert done.status_code in (200, 400), done.text
    if done.status_code == 200:
        contiene("task.done", done.json(), TASK)
    # el front manda {note} en skip y {sent, outcome} en done: los dos cuerpos validan
    assert client.post(f"/admin/subscribers/tasks/{ids[1]}/skip", headers=ana, json={"note": None}).status_code == 200
