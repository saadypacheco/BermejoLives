"""El cableado del contenido para redes: banderas apagadas, topes de cuerpo, gzip, planes y arranque."""
from pathlib import Path

from fastapi.testclient import TestClient

from app.core import auth
from app.core.config import Settings, settings
from app.core.limite_cuerpo import HOLGURA, MB, tope_para
from app.main import _sin_gzip, app
from app.services import content_storage
from tests.content_helpers import h


def test_los_workers_arrancan_apagados_por_defecto():
    s = Settings(_env_file=None)
    assert s.content_planner_worker is False and s.content_render_worker is False
    assert s.content_dir == "/data/content" and s.content_networks_list() == ["tiktok", "instagram", "facebook", "wa_channel"]
    assert (s.content_render_timeout_seg, s.content_render_max_attempts, s.content_render_memory_mb) == (300, 3, 1536)
    assert (s.content_signed_url_ttl_seg, s.content_share_days, s.content_claim_minutes) == (900, 60, 20)
    assert (s.content_planning_weekday, s.content_planning_hour, s.content_care_hour, s.content_grace_days) == (6, 20, 7, 7)


def test_las_subidas_al_banco_tienen_tope_de_15_mb():
    for ruta in ("/admin/content/merchants/abc/assets", "/campo/mis-comercios/abc/content-assets"):
        assert tope_para(ruta) == 15 * MB + HOLGURA


def test_los_videos_y_archivos_firmados_no_se_comprimen():
    assert _sin_gzip("/content/files/piece/x/video") and _sin_gzip("/fotos/a.jpg")
    assert _sin_gzip("/public/pieces/tok/video") and _sin_gzip("/public/pieces/tok/cover")
    assert not _sin_gzip("/public/pieces/tok") and not _sin_gzip("/admin/content/pieces")


def test_el_plan_acepta_las_piezas_por_ciclo(client, repo):
    t = h(auth.make_token("a@u", rol="admin"))
    r = client.put("/admin/planes/publica", headers=t, json={"social_pieces_per_month": 3})
    assert r.status_code == 200 and repo.planes["publica"]["social_pieces_per_month"] == 3
    assert client.put("/admin/planes/publica", headers=t, json={"social_pieces_per_month": 0}).status_code == 200
    assert repo.planes["publica"]["social_pieces_per_month"] == 0
    assert client.put("/admin/planes/publica", headers=t, json={"social_pieces_per_month": 32}).status_code == 422
    assert client.put("/admin/planes/publica", headers=t, json={"social_pieces_per_month": -1}).status_code == 422


def test_null_en_las_piezas_por_ciclo_significa_sin_cambio(client, repo):
    """El campo vacío del formulario manda null: no toca el valor del plan (y con sólo eso no hay nada que cambiar)."""
    t = h(auth.make_token("a@u", rol="admin"))
    repo.planes["publica"]["social_pieces_per_month"] = 2
    r = client.put("/admin/planes/publica", headers=t, json={"nombre": "Publica 2", "social_pieces_per_month": None})
    assert r.status_code == 200 and repo.planes["publica"]["social_pieces_per_month"] == 2 and repo.planes["publica"]["nombre"] == "Publica 2"
    assert client.put("/admin/planes/publica", headers=t, json={"social_pieces_per_month": None}).status_code == 400


def test_al_arrancar_se_limpia_el_tmp_del_render(crepo, repo):
    sobra = content_storage.carpeta_tmp("pieza-vieja")
    sobra.mkdir(parents=True)
    (sobra / "job.json").write_text("{}")
    other = Path(settings.content_dir) / "renders" / "2026-11" / "p"
    other.mkdir(parents=True)
    (other / "video.mp4").write_bytes(b"x")
    with TestClient(app):
        pass
    assert not sobra.exists() and (other / "video.mp4").exists()


def test_con_el_dir_inseguro_el_arranque_no_toca_nada_y_no_cae(monkeypatch, tmp_path):
    inseguro = Path(settings.fotos_dir) / "privado"
    monkeypatch.setattr(settings, "content_dir", str(inseguro))
    monkeypatch.setattr(settings, "content_render_worker", True)
    monkeypatch.setattr(settings, "content_planner_worker", True)
    with TestClient(app) as c:
        assert c.get("/health").status_code in (200, 503)


def test_las_rutas_nuevas_no_chocan_con_las_viejas():
    rutas = {(m.upper(), ruta) for ruta, ops in app.openapi()["paths"].items() for m in ops}
    for esperada in (("GET", "/admin/content/week"), ("POST", "/admin/content/week/plan"), ("GET", "/admin/content/today"),
                     ("GET", "/content/files/{scope}/{item_id}/{kind}"), ("GET", "/public/pieces/{token}"),
                     ("PUT", "/comercio/social-consent"), ("GET", "/admin/subscribers/tasks"),
                     ("POST", "/admin/subscribers/tasks/{task_id}/done"), ("POST", "/admin/content/pieces/approve-batch")):
        assert esperada in rutas, esperada
