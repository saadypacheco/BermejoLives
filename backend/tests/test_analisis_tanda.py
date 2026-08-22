"""Análisis por fotos en tanda: clasificar 161 comercios sin hacerlo uno por uno.

De a pocos por llamada y no todos de una: cada análisis tarda varios segundos, y
161 seguidos superan cualquier timeout de HTTP y chocan con el límite de
frecuencia de Gemini. El panel llama en bucle, así el avance se ve y el proceso
se puede cortar sin perder lo hecho.
"""
from unittest.mock import patch

from tests.test_vision import _respuesta, _respuesta_error, _CUOTA_AGOTADA


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _con_key(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "gemini_api_key", "test-key")


PROPUESTA = {"productos": "zapatillas, chinelas", "descripcion": "Zapatería",
             "subcategoria": "zapatillas", "rubro_slugs": ["calzado"], "confianza": 0.9}


def _pendientes(repo, n, **kw):
    return [repo.seed_comercio(slug=f"c{i}", nombre=f"Comercio {i}",
                               portada_url=f"http://x/{i}.jpg", activo=True,
                               created_at=f"2026-08-{i + 1:02d}", **kw)
            for i in range(n)]


# ───────────────────────────────────────────────── pendientes
def test_solo_cuenta_los_que_tienen_foto(client, repo, admin_token):
    """Sin foto no hay nada que analizar: no son pendientes, son otro problema."""
    repo.seed_comercio(slug="con", nombre="Con foto", portada_url="http://x/a.jpg", activo=True)
    repo.seed_comercio(slug="sin", nombre="Sin foto", activo=True)

    r = client.get("/admin/comercios/pendientes-analisis", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["pendientes"] == 1


def test_no_cuenta_los_ya_analizados(client, repo, admin_token):
    repo.seed_comercio(slug="ya", nombre="Ya", portada_url="http://x/a.jpg",
                       ia_analizado_at="2026-08-21T10:00:00Z", activo=True)
    assert client.get("/admin/comercios/pendientes-analisis",
                      headers=_h(admin_token)).json()["pendientes"] == 0


# ───────────────────────────────────────────────── la tanda
def test_procesa_hasta_el_limite_y_reporta_el_resto(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _pendientes(repo, 5)

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(PROPUESTA)):
        r = client.post("/admin/comercios/analizar-tanda?limite=2", headers=_h(admin_token))

    body = r.json()
    assert r.status_code == 200, r.text
    assert body["procesados"] == 2
    assert body["restantes"] == 3


def test_el_bucle_termina(client, repo, admin_token, monkeypatch):
    """Sin `sin_mas` el panel llamaría para siempre."""
    _con_key(monkeypatch)
    r = client.post("/admin/comercios/analizar-tanda", headers=_h(admin_token))
    assert r.json() == {"procesados": 0, "restantes": 0, "resultados": [], "sin_mas": True}


def test_lo_analizado_no_se_vuelve_a_procesar(client, repo, admin_token, monkeypatch):
    """Cada tanda avanza: si no, el bucle se quedaría girando sobre los mismos."""
    _con_key(monkeypatch)
    _pendientes(repo, 3)

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(PROPUESTA)):
        primera = client.post("/admin/comercios/analizar-tanda?limite=2", headers=_h(admin_token)).json()
        segunda = client.post("/admin/comercios/analizar-tanda?limite=2", headers=_h(admin_token)).json()

    procesados = {x["slug"] for x in primera["resultados"]} | {x["slug"] for x in segunda["resultados"]}
    assert len(procesados) == 3, "no puede repetir comercios entre tandas"
    assert segunda["restantes"] == 0


def test_aplica_lo_que_detecto(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    c = _pendientes(repo, 1)[0]

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(PROPUESTA)):
        client.post("/admin/comercios/analizar-tanda?limite=1", headers=_h(admin_token))

    guardado = repo.comercios[c["id"]]
    assert guardado["prod_det_ia"] == "zapatillas, chinelas"
    assert guardado["subcategoria"] == "zapatillas"
    assert guardado["ia_analizado_at"]


def test_con_aplicar_false_no_escribe_pero_igual_avanza(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    c = _pendientes(repo, 1)[0]

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(PROPUESTA)):
        r = client.post("/admin/comercios/analizar-tanda?limite=1&aplicar=false",
                        headers=_h(admin_token))

    assert r.json()["resultados"][0]["productos"] == "zapatillas, chinelas"
    assert repo.comercios[c["id"]].get("prod_det_ia") is None


def test_confianza_cero_se_marca_igual(client, repo, admin_token, monkeypatch):
    """El modelo miró y no reconoció nada. Si no se marcara, cada tanda volvería
    a tropezar con los mismos y el proceso no avanzaría nunca."""
    _con_key(monkeypatch)
    c = _pendientes(repo, 1)[0]
    vacia = {"productos": "", "descripcion": "", "subcategoria": "",
             "rubro_slugs": [], "confianza": 0}

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(vacia)):
        r = client.post("/admin/comercios/analizar-tanda?limite=1", headers=_h(admin_token))

    assert r.json()["restantes"] == 0
    assert repo.comercios[c["id"]]["ia_analizado_at"]
    assert repo.comercios[c["id"]].get("prod_det_ia") is None


def test_ante_un_error_corta_y_no_marca(client, repo, admin_token, monkeypatch):
    """Si Gemini falla, el resto de la tanda va a fallar igual: seguir sólo quema
    cuota. Y no se marca como analizado, para reintentarlo después."""
    _con_key(monkeypatch)
    monkeypatch.setattr("app.services.vision.ESPERA_BASE", 0)
    comercios = _pendientes(repo, 4)

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post",
               return_value=_respuesta_error(429, cuerpo=_CUOTA_AGOTADA)):
        r = client.post("/admin/comercios/analizar-tanda?limite=4", headers=_h(admin_token))

    body = r.json()
    assert body["procesados"] == 1, "corta en el primero que falla"
    assert body["resultados"][0]["error"]
    assert body["restantes"] == 4, "ninguno quedó marcado como analizado"
    assert not repo.comercios[comercios[0]["id"]].get("ia_analizado_at")


def test_los_rubros_inventados_se_registran_tambien_en_tanda(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _pendientes(repo, 1)
    prop = {**PROPUESTA, "rubro_slugs": ["calzado", "zapateria de lujo"]}

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(prop)):
        client.post("/admin/comercios/analizar-tanda?limite=1", headers=_h(admin_token))

    assert any(x["texto"] == "zapateria de lujo" for x in repo.rubros_propuestos)


def test_la_tanda_requiere_admin(client, repo):
    assert client.post("/admin/comercios/analizar-tanda").status_code in (401, 403)
    assert client.get("/admin/comercios/pendientes-analisis").status_code in (401, 403)
