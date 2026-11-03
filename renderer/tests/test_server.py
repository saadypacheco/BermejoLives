"""Contrato HTTP del servidor: auth, 400, 409, health y plazo."""
import http.client
import json
import threading
import uuid

import pytest

import server as srv

TOKEN = "token-de-prueba-0123456789"


@pytest.fixture
def api(tmp_path):
    """Levanta el servidor en un puerto libre. Devuelve (call, renderer)."""
    renderer = srv.Renderer(token=TOKEN, content_dir=tmp_path, deadline_seg=30)
    httpd = srv.make_server("127.0.0.1", 0, renderer)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]

    def call(method, path, body=None, token=TOKEN, raw=None, headers=None):
        conn = http.client.HTTPConnection("127.0.0.1", port, timeout=60)
        hdrs = dict(headers or {})
        if token is not None:
            hdrs["Authorization"] = f"Bearer {token}"
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        if data is not None:
            hdrs["Content-Type"] = "application/json"
        conn.request(method, path, body=data, headers=hdrs)
        resp = conn.getresponse()
        payload = json.loads(resp.read() or b"null")
        conn.close()
        return resp.status, payload

    yield call, renderer
    httpd.shutdown()
    httpd.server_close()


def post(call, piece_id, **kw):
    return call("POST", "/render", {"piece_id": piece_id}, **kw)


# ---------------------------------------------------------------- auth
def test_sin_token_es_401(api):
    call, _ = api
    status, body = post(call, str(uuid.uuid4()), token=None)
    assert status == 401
    assert body == {"ok": False, "error": "No autorizado", "retryable": False}


def test_token_distinto_es_401(api):
    call, _ = api
    assert post(call, str(uuid.uuid4()), token="otro-token")[0] == 401
    assert post(call, str(uuid.uuid4()), token=TOKEN + "x")[0] == 401
    assert post(call, str(uuid.uuid4()), token="")[0] == 401


def test_esquema_distinto_de_bearer_es_401(api):
    call, _ = api
    status, _ = post(call, str(uuid.uuid4()), token=None, headers={"Authorization": f"Basic {TOKEN}"})
    assert status == 401
    status, _ = post(call, str(uuid.uuid4()), token=None, headers={"Authorization": TOKEN})
    assert status == 401


def test_servidor_sin_token_configurado_rechaza_todo(tmp_path):
    renderer = srv.Renderer(token="", content_dir=tmp_path)
    assert renderer.authorized("Bearer ") is False
    assert renderer.authorized("Bearer algo") is False
    assert renderer.authorized(None) is False


def test_el_handler_tiene_timeout_de_socket():
    assert srv.Handler.timeout == 30


@pytest.mark.parametrize("token", ["", "corto", "x" * 31])
def test_main_no_arranca_con_token_corto(monkeypatch, token):
    monkeypatch.setenv("RENDERER_TOKEN", token)
    with pytest.raises(SystemExit) as exc:
        srv.main()
    assert exc.value.code == 1


def test_kill_strays_no_toca_nada_fuera_de_linux(monkeypatch):
    llamadas = []
    monkeypatch.setattr(srv.sys, "platform", "win32")
    monkeypatch.setattr(srv.os, "kill", lambda *a: llamadas.append(a))
    srv.kill_strays()
    assert llamadas == []


def test_kill_strays_salta_el_pid_1_y_el_propio(monkeypatch):
    matados = []
    monkeypatch.setattr(srv.sys, "platform", "linux")
    monkeypatch.setattr(srv.os, "listdir", lambda p: ["1", str(srv.os.getpid()), "4242", "self", "9999"])
    monkeypatch.setattr(srv.os, "kill", lambda pid, sig: matados.append(pid))
    srv.kill_strays()
    assert matados == [4242, 9999]


def test_la_comparacion_es_en_tiempo_constante():
    import inspect

    assert "hmac.compare_digest" in inspect.getsource(srv.Renderer.authorized)


# ---------------------------------------------------------------- 400
@pytest.mark.parametrize("piece_id", ["", "abc", "../../etc", "1234", None, 5, str(uuid.uuid4()) + "x"])
def test_piece_id_invalido_es_400(api, piece_id):
    call, _ = api
    status, body = post(call, piece_id)
    assert status == 400
    assert body["ok"] is False and body["retryable"] is False


def test_cuerpo_que_no_es_json_es_400(api):
    call, _ = api
    assert call("POST", "/render", raw=b"no es json")[0] == 400
    assert call("POST", "/render", raw=b"[1,2]")[0] == 400
    assert call("POST", "/render", raw=b"x" * 5000)[0] == 400


def test_sin_carpeta_del_job_es_400_no_reintentable(api):
    call, _ = api
    status, body = post(call, str(uuid.uuid4()))
    assert status == 400
    assert body["retryable"] is False
    assert "carpeta" in body["error"]


def test_job_invalido_en_disco_es_400(api, make_job):
    call, renderer = api
    content, piece_id, _ = make_job(3)  # 3 fotos: fuera de 4–6
    renderer.content_dir = content
    status, body = post(call, piece_id)
    assert status == 400
    assert body == {"ok": False, "error": "slides debe traer entre 4 y 6 fotos", "retryable": False}


def test_el_piece_id_no_puede_salirse_de_tmp(api, make_job):
    call, renderer = api
    content, _, _ = make_job(4)
    renderer.content_dir = content
    status, _ = post(call, "..%2F..%2Fx")
    assert status == 400


# ---------------------------------------------------------------- 409 y health
def test_ocupado_es_409_reintentable(api):
    call, renderer = api
    assert renderer.lock.acquire(blocking=False)
    try:
        status, body = post(call, str(uuid.uuid4()))
        assert status == 409
        assert body == {"ok": False, "error": "Ocupado", "retryable": True}
        assert call("GET", "/health", token=None)[1]["busy"] is True
    finally:
        renderer.lock.release()


def test_health_sin_token(api, monkeypatch):
    call, renderer = api
    monkeypatch.setattr(renderer, "chromium_ok", lambda: True)
    status, body = call("GET", "/health", token=None)
    assert status == 200
    assert body["ok"] is True and body["chromium"] is True and body["busy"] is False
    assert isinstance(body["ffmpeg"], bool)


def test_ruta_desconocida_es_404(api):
    call, _ = api
    assert call("GET", "/otra", token=None)[0] == 404
    assert call("POST", "/otra", {"piece_id": str(uuid.uuid4())})[0] == 404


# ---------------------------------------------------------------- plazo
def test_al_vencer_el_plazo_mata_el_render_y_es_reintentable(api, make_job):
    call, renderer = api
    content, piece_id, job_dir = make_job(4)
    renderer.content_dir = content
    renderer.deadline_seg = 0.3  # ni alcanza a arrancar el proceso
    (job_dir / "out").mkdir()
    (job_dir / "out" / "video.mp4").write_bytes(b"parcial")
    status, body = post(call, piece_id)
    assert status == 200
    assert body == {"ok": False, "error": "Se venció el plazo del render", "retryable": True}
    assert not (job_dir / "out" / "video.mp4").exists()  # no quedan salidas a medias
    assert renderer.lock.locked() is False
    assert renderer.current is None
