"""Admin multiciudad, fase 1: el panel deja de dar por hecho que todo es Bermejo.

El selector de ciudad del panel es un FILTRO, no un permiso. Lo que se protege
acá es que un filtro mal escrito no se convierta en un dato equivocado: un slug
que no existe tiene que dar 404 (no el total general ni Bermejo), y los textos
que salen a la IA o a las redes tienen que nombrar la ciudad real del comercio.
"""
from unittest.mock import patch

from app.services import difusion
from app.services.vision import _prompt, analizar_fotos
from tests.test_analisis_tanda import PROPUESTA, _con_key
from tests.test_vision import RUBROS, _respuesta

BERMEJO = {"id": "ciu-1", "slug": "bermejo", "nombre": "Bermejo",
           "es_frontera": True, "pais_vecino": "Argentina"}
TARIJA = {"id": "ciu-tarija", "slug": "tarija", "nombre": "Tarija",
          "es_frontera": False, "pais_vecino": None}


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _sembrar(repo):
    """Dos de Tarija, uno de Bermejo y uno sin ciudad; todos con foto y sin analizar."""
    filas = [("t1", "ciu-tarija"), ("t2", "ciu-tarija"), ("b1", "ciu-1"), ("s1", None)]
    for i, (slug, ciudad_id) in enumerate(filas):
        repo.seed_comercio(slug=slug, nombre=slug.upper(), portada_url=f"http://x/{slug}.jpg",
                           activo=True, ciudad_id=ciudad_id, created_at=f"2026-08-{i + 1:02d}")


# ───────────────────────────────────────── pendientes-analisis por ciudad
def test_pendientes_con_ciudad_cuenta_solo_los_de_esa_ciudad(client, repo, admin_token):
    _sembrar(repo)
    r = client.get("/admin/comercios/pendientes-analisis?ciudad=tarija", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() == {"pendientes": 2}


def test_pendientes_sin_ciudad_cuenta_todas_como_antes(client, repo, admin_token):
    _sembrar(repo)
    r = client.get("/admin/comercios/pendientes-analisis", headers=_h(admin_token))
    assert r.json() == {"pendientes": 4}


def test_pendientes_con_ciudad_desconocida_es_404_y_no_el_total_general(client, repo, admin_token):
    """Devolver el total general ante un slug que no existe haría creer que esa
    ciudad tiene pendientes que en realidad son de otra."""
    _sembrar(repo)
    r = client.get("/admin/comercios/pendientes-analisis?ciudad=no-existe", headers=_h(admin_token))
    assert r.status_code == 404
    assert r.json()["detail"] == "Ciudad no encontrada: no-existe"


# ───────────────────────────────────────── analizar-tanda por ciudad
def test_tanda_con_ciudad_analiza_y_cuenta_restantes_solo_de_esa_ciudad(
        client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _sembrar(repo)

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(PROPUESTA)):
        r = client.post("/admin/comercios/analizar-tanda?limite=1&ciudad=tarija",
                        headers=_h(admin_token))

    body = r.json()
    assert r.status_code == 200, r.text
    assert body["procesados"] == 1
    assert body["restantes"] == 1                       # sólo cuenta el otro de Tarija
    assert [f["slug"] for f in body["resultados"]] == ["t1"]
    # Los de otras ciudades ni se tocaron.
    assert not repo.comercios[next(k for k, c in repo.comercios.items() if c["slug"] == "b1")].get("ia_analizado_at")


def test_tanda_sin_ciudad_procesa_de_todas(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _sembrar(repo)

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(PROPUESTA)):
        r = client.post("/admin/comercios/analizar-tanda?limite=20", headers=_h(admin_token))

    assert r.json()["procesados"] == 4
    assert r.json()["restantes"] == 0


def test_tanda_con_ciudad_desconocida_es_404_y_no_analiza_nada(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _sembrar(repo)

    with patch("app.services.vision.httpx.post") as post:
        r = client.post("/admin/comercios/analizar-tanda?ciudad=no-existe", headers=_h(admin_token))

    assert r.status_code == 404
    assert r.json()["detail"] == "Ciudad no encontrada: no-existe"
    post.assert_not_called()


def test_tanda_le_pasa_a_la_ia_la_ciudad_de_cada_comercio(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _sembrar(repo)
    recibidas = {}

    def falso(urls, rubros, ciudad=None):
        recibidas[urls[0]] = ciudad
        return dict(PROPUESTA)

    with patch("app.api.moderacion.analizar_fotos", falso):
        r = client.post("/admin/comercios/analizar-tanda?limite=20", headers=_h(admin_token))

    assert r.status_code == 200, r.text
    assert recibidas["http://x/t1.jpg"]["nombre"] == "Tarija"
    assert recibidas["http://x/b1.jpg"]["id"] == "ciu-1"
    assert recibidas["http://x/s1.jpg"] is None          # sin ciudad: nunca se asume Bermejo


# ───────────────────────────────────────── lugares y adornos: slug desconocido
def test_lugares_get_con_slug_desconocido_es_404(client, repo, admin_token):
    r = client.get("/admin/lugares?ciudad_slug=no-existe", headers=_h(admin_token))
    assert r.status_code == 404
    assert r.json()["detail"] == "Ciudad no encontrada: no-existe"


def test_lugares_post_con_slug_desconocido_es_404_y_no_crea_nada(client, repo, admin_token):
    r = client.post("/admin/lugares", json={"nombre": "Mercado", "ciudad_slug": "no-existe"},
                    headers=_h(admin_token))
    assert r.status_code == 404
    assert r.json()["detail"] == "Ciudad no encontrada: no-existe"
    assert not repo.lugares


def test_lugares_sin_parametro_sigue_en_bermejo(client, repo, admin_token):
    """Los bundles viejos del panel que quedan en el service worker no mandan la
    ciudad: tienen que seguir viendo y creando en Bermejo."""
    creado = client.post("/admin/lugares", json={"nombre": "Mercado"}, headers=_h(admin_token))
    assert creado.status_code == 200, creado.text
    assert creado.json()["lugar"]["ciudad_id"] == "ciu-1"

    pedidos = []
    original = repo.list_lugares
    repo.list_lugares = lambda ciudad_id=None: pedidos.append(ciudad_id) or original(ciudad_id)
    assert client.get("/admin/lugares", headers=_h(admin_token)).status_code == 200
    assert pedidos == ["ciu-1"]


def test_lugares_con_ciudad_valida_usa_esa_ciudad(client, repo, admin_token):
    r = client.post("/admin/lugares", json={"nombre": "Mercado", "ciudad_slug": "tarija"},
                    headers=_h(admin_token))
    assert r.json()["lugar"]["ciudad_id"] == "ciu-tarija"


def test_adornos_get_con_slug_desconocido_es_404(client, repo, admin_token):
    r = client.get("/admin/adornos?ciudad_slug=no-existe", headers=_h(admin_token))
    assert r.status_code == 404
    assert r.json()["detail"] == "Ciudad no encontrada: no-existe"


def test_adornos_post_con_slug_desconocido_es_404_y_no_crea_nada(client, repo, admin_token):
    r = client.post("/admin/adornos",
                    json={"tipo": "chalana", "lat": -22.7, "lng": -64.3, "ciudad_slug": "no-existe"},
                    headers=_h(admin_token))
    assert r.status_code == 404
    assert r.json()["detail"] == "Ciudad no encontrada: no-existe"
    assert not repo.adornos


def test_adornos_sin_parametro_sigue_en_bermejo(client, repo, admin_token):
    creado = client.post("/admin/adornos", json={"tipo": "chalana", "lat": -22.7, "lng": -64.3},
                         headers=_h(admin_token))
    assert creado.status_code == 200, creado.text
    assert creado.json()["adorno"]["ciudad_id"] == "ciu-1"
    items = client.get("/admin/adornos", headers=_h(admin_token)).json()["items"]
    assert len(items) == 1


# ───────────────────────────────────────── ia_analizado_at en el listado
def test_el_listado_de_comercios_trae_ia_analizado_at(client, repo, admin_token):
    """El panel cuenta «con foto sin clasificar» como portada_url != null y
    ia_analizado_at == null: sin el campo en el item no puede contarlo."""
    repo.seed_comercio(slug="a", nombre="A", portada_url="http://x/a.jpg", activo=True,
                       ia_analizado_at="2026-08-21T10:00:00Z")
    repo.seed_comercio(slug="b", nombre="B", portada_url="http://x/b.jpg", activo=True)
    items = {c["slug"]: c for c in client.get(
        "/moderacion/comercios?todos=true", headers=_h(admin_token)).json()["items"]}
    assert items["a"]["ia_analizado_at"] == "2026-08-21T10:00:00Z"
    assert "ia_analizado_at" in items["b"] and items["b"]["ia_analizado_at"] is None


def test_la_consulta_real_del_listado_pide_ia_analizado_at():
    """El repo falso no ejecuta el SELECT real: se mira la constante."""
    from app.db.repository import _COLS_COMERCIO_ADMIN
    assert "ia_analizado_at" in _COLS_COMERCIO_ADMIN


def test_el_listado_avisa_cuando_llego_al_tope_y_los_totales_quedan_incompletos(
        client, repo, admin_token, monkeypatch):
    """Del listado salen el contador de la pestaña y el resumen por ciudad. Si se
    corta en el tope sin decirlo, esos totales son plausibles y falsos."""
    from app.api import moderacion
    for i in range(3):
        repo.seed_comercio(slug=f"c{i}", nombre=f"C{i}", activo=True)

    completo = client.get("/moderacion/comercios?todos=true", headers=_h(admin_token)).json()
    assert completo["truncado"] is False and completo["total"] == 3

    monkeypatch.setattr(moderacion, "TOPE_LISTADO_COMERCIOS", 2)
    cortado = client.get("/moderacion/comercios?todos=true", headers=_h(admin_token)).json()
    assert cortado["truncado"] is True and cortado["total"] == 2


# ───────────────────────────────────────── prompt del análisis por fotos
def test_el_prompt_nombra_la_ciudad_que_se_le_pasa():
    p = _prompt(RUBROS, TARIJA)
    assert "en Tarija, Bolivia" in p


def test_el_prompt_de_una_ciudad_de_frontera_nombra_la_frontera_y_el_pais_vecino():
    p = _prompt(RUBROS, BERMEJO)
    assert "una ciudad de frontera" in p
    assert "frontera con Argentina" in p


def test_el_prompt_de_una_ciudad_que_no_es_frontera_no_habla_de_frontera_ni_de_pais_vecino():
    """Si no, el modelo inventa «términos argentinos» donde nadie los usa."""
    p = _prompt(RUBROS, TARIJA)
    assert "frontera" not in p.lower()
    assert "Argentina" not in p
    # Pero la regla de sinónimos sigue y sigue exigiendo que nombren LA MISMA COSA.
    assert "`sinonimos`" in p
    assert "LA MISMA COSA" in p


def test_el_prompt_de_frontera_sin_pais_vecino_dice_el_pais_vecino():
    ciudad = {**BERMEJO, "pais_vecino": ""}
    assert "frontera con el país vecino" in _prompt(RUBROS, ciudad)


def test_el_prompt_sin_ciudad_dice_bolivia_y_nunca_asume_bermejo():
    p = _prompt(RUBROS)
    assert "en Bolivia" in p
    assert "Bermejo" not in p
    assert "frontera" not in p.lower()


def test_el_prompt_usa_el_pais_de_la_ciudad_y_no_bolivia_fijo():
    """La tabla `ciudades` tiene ciudades argentinas. «En La Quiaca, Bolivia» es
    el mismo dato supuesto que era «Bermejo» para todos."""
    la_quiaca = {"nombre": "La Quiaca", "pais": "Argentina", "es_frontera": True, "pais_vecino": None}
    p = _prompt(RUBROS, la_quiaca)
    assert "en La Quiaca, Argentina" in p
    assert "La Quiaca, Bolivia" not in p
    assert "de el país" not in p


def test_analizar_fotos_manda_el_prompt_de_la_ciudad_al_modelo(monkeypatch):
    _con_key(monkeypatch)
    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(PROPUESTA)) as post:
        analizar_fotos(["http://x/f.jpg"], RUBROS, TARIJA)
    texto = post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
    assert "en Tarija, Bolivia" in texto and "frontera" not in texto.lower()


# ───────────────────────────────────────── texto de difusión
def test_el_texto_de_difusion_dice_la_ciudad_del_comercio():
    t = difusion.texto_de({"titulo": "Oferta"}, {"nombre": "Casa X", "slug": "x"}, None, TARIJA)
    assert "📍 Casa X, Tarija" in t
    assert "Bermejo" not in t


def test_el_texto_de_difusion_sin_ciudad_no_inventa_una():
    t = difusion.texto_de({"titulo": "Oferta"}, {"nombre": "Casa X", "slug": "x"})
    assert "📍 Casa X" in t
    assert "Bermejo" not in t and "Casa X," not in t


def test_el_texto_de_difusion_usa_la_ciudad_embebida_en_el_comercio():
    t = difusion.texto_de({"titulo": "Oferta"},
                          {"nombre": "Casa X", "slug": "x", "ciudades": {"nombre": "Tarija", "slug": "tarija"}})
    assert "📍 Casa X, Tarija" in t


def test_al_procesar_la_difusion_se_resuelve_la_ciudad_del_comercio(repo, monkeypatch):
    """De punta a punta: el comercio sólo trae `ciudad_id` y el texto que sale a
    las redes dice la ciudad."""
    from app.core.config import settings
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    monkeypatch.setattr(settings, "facebook_page_id", "111")
    monkeypatch.setattr(settings, "facebook_page_token", "tok")
    enviados = []
    monkeypatch.setattr(difusion, "_ENVIOS", {
        d: (lambda texto, img, _d=d: enviados.append(texto) or None) for d in difusion.DESTINOS})

    c = repo.seed_comercio(slug="x", nombre="Casa X", plan="destacado", ciudad_id="ciu-tarija")
    pub = repo.insert_publicacion_directa(
        {"comercio_id": c["id"], "tipo": "oferta", "titulo": "algo", "estado": "aprobado"})
    repo.encolar_difusion(pub["id"], ["facebook"])
    fila = repo.difusion_pendientes(10)[0]

    assert difusion.procesar(repo, fila)["estado"] == "enviado"
    assert "📍 Casa X, Tarija" in enviados[0]
