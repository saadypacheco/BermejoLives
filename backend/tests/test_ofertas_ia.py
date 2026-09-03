"""Analisis de las fotos de las ofertas: lo que se pisa y lo que no."""
import app.api.moderacion as mod


def _h(t):
    return {"Authorization": f"Bearer {t}"}


def _pub(repo, **kw):
    fila = {"id": kw.pop("id", "pub-1"), "comercio_id": "c1", "activo": True,
            "imagen_url": "https://x/f.jpg", "titulo": None, "descripcion": None,
            "precio": None, **kw}
    repo.publicaciones.append(fila)
    return fila


def _mock(monkeypatch, **out):
    base = {"titulo": "Zapatilla urbana", "terminos": "zapatilla, championes",
            "precio": None, "moneda": "BOB", "es_oferta": True, "confianza": 0.9}
    import app.services.vision as v
    monkeypatch.setattr(v, "analizar_oferta", lambda url: {**base, **out})


def test_una_foto_sin_texto_se_vuelve_buscable(client, admin_token, repo, monkeypatch):
    """El motivo de todo esto: el indice sale de titulo+descripcion, y con foto
    el titulo queda en NULL. Una foto sola era una oferta invisible."""
    p = _pub(repo)
    _mock(monkeypatch)

    r = client.post("/admin/publicaciones/analizar-tanda", headers=_h(admin_token))

    assert r.status_code == 200
    assert p["terminos_ia"] == "zapatilla, championes"
    assert p["titulo"] == "Zapatilla urbana"
    assert p["ia_analizado_at"]


def test_no_pisa_el_titulo_que_escribio_el_comerciante(client, admin_token, repo, monkeypatch):
    """Lo que el dijo con sus palabras vale mas que lo que dedujo el modelo."""
    p = _pub(repo, titulo="Zapas re copadas")
    _mock(monkeypatch)

    client.post("/admin/publicaciones/analizar-tanda", headers=_h(admin_token))

    assert p["titulo"] == "Zapas re copadas"
    assert p["terminos_ia"]        # los terminos sí se agregan


def test_no_pisa_un_precio_ya_cargado(client, admin_token, repo, monkeypatch):
    p = _pub(repo, precio=150)
    _mock(monkeypatch, precio=999)

    client.post("/admin/publicaciones/analizar-tanda", headers=_h(admin_token))

    assert p["precio"] == 150


def test_el_precio_leido_de_la_foto_se_carga(client, admin_token, repo, monkeypatch):
    p = _pub(repo)
    _mock(monkeypatch, precio=180.0, moneda="BOB")

    client.post("/admin/publicaciones/analizar-tanda", headers=_h(admin_token))

    assert p["precio"] == 180.0 and p["moneda"] == "BOB"


def test_lo_que_no_es_una_oferta_no_escribe_nada(client, admin_token, repo, monkeypatch):
    """Una selfie o una captura de pantalla. Se marca analizada igual para que
    la cola avance: si no, cada corrida vuelve a tropezar con las mismas."""
    p = _pub(repo)
    _mock(monkeypatch, es_oferta=False, titulo="", terminos="")

    client.post("/admin/publicaciones/analizar-tanda", headers=_h(admin_token))

    assert p.get("terminos_ia") is None
    assert p["ia_analizado_at"]


def test_confianza_cero_no_escribe_pero_marca(client, admin_token, repo, monkeypatch):
    p = _pub(repo)
    _mock(monkeypatch, confianza=0)

    client.post("/admin/publicaciones/analizar-tanda", headers=_h(admin_token))

    assert p.get("terminos_ia") is None
    assert p["ia_analizado_at"]


def test_un_fallo_corta_la_tanda_y_no_marca(client, admin_token, repo, monkeypatch):
    """El fallo puede ser transitorio: marcarla la sacaria de la cola para
    siempre. Y se corta para no gastar la tanda contra lo mismo."""
    p1 = _pub(repo, id="p1")
    _pub(repo, id="p2")
    _mock(monkeypatch, error="429 rate limit")

    r = client.post("/admin/publicaciones/analizar-tanda?limite=2", headers=_h(admin_token))

    assert r.json()["procesados"] == 1     # cortó en la primera
    assert p1.get("ia_analizado_at") is None


def test_solo_las_que_tienen_foto(repo):
    """Una publicacion de solo texto ya es buscable por lo que escribio el
    comerciante: gastarle una llamada al modelo no agrega nada."""
    _pub(repo, id="con", imagen_url="https://x/a.jpg")
    _pub(repo, id="sin", imagen_url=None)

    assert [p["id"] for p in repo.publicaciones_sin_analizar(10)] == ["con"]
