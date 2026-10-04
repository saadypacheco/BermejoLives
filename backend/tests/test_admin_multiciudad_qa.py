"""QA de «Admin multiciudad», fase 1: casos borde y adversariales.

Complementa `test_admin_multiciudad.py` (del dev) sin repetirlo. Se ataca lo que
ese archivo no toca: filtro vacío, ciudad válida sin pendientes, tanda con dos
ciudades y filtro, comercios sin `ciudad_id`, frontera sin `pais_vecino`, slugs
maliciosos que no deben crear nada, aislamiento real de adornos entre ciudades,
permisos antes que 404 (no filtrar qué ciudades existen) y el texto de difusión
con la ciudad embebida vs. resuelta por id.

El `FakeRepo` es permisivo con los slugs (inventa `ciu-<slug>`), así que donde
importa el 404 se usa `_repo_estricto`, que se comporta como el repo real.
"""
from unittest.mock import patch

import pytest

from app.core import auth
from app.services import difusion
from app.services.vision import _prompt, analizar_fotos
from tests.test_analisis_tanda import PROPUESTA, _con_key
from tests.test_vision import RUBROS, _respuesta

BERMEJO = {"id": "ciu-1", "slug": "bermejo", "nombre": "Bermejo",
           "es_frontera": True, "pais_vecino": "Argentina"}
TARIJA = {"id": "ciu-tarija", "slug": "tarija", "nombre": "Tarija",
          "es_frontera": False, "pais_vecino": None}
SANTA_CRUZ = {"id": "ciu-santa-cruz", "slug": "santa-cruz", "nombre": "Santa Cruz",
              "es_frontera": False, "pais_vecino": None}

CIUDADES = {c["id"]: c for c in (BERMEJO, TARIJA, SANTA_CRUZ)}
SLUGS = {c["slug"]: c["id"] for c in CIUDADES.values()}


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _repo_estricto(repo):
    """Hace que el repo falso conteste como el real: slug desconocido -> None."""
    repo.get_ciudad_id = lambda slug: SLUGS.get(slug)
    repo.get_ciudad_por_id = lambda cid: CIUDADES.get(cid) if cid else None
    return repo


def _sembrar(repo, filas):
    for i, (slug, ciudad_id) in enumerate(filas):
        repo.seed_comercio(slug=slug, nombre=slug.upper(), portada_url=f"http://x/{slug}.jpg",
                           activo=True, ciudad_id=ciudad_id, created_at=f"2026-08-{i + 1:02d}")


def _por_slug(repo, slug):
    return next(c for c in repo.comercios.values() if c["slug"] == slug)


# ───────────────────────────────────── pendientes-analisis: bordes
def test_pendientes_con_ciudad_vacia_cuenta_todas_y_no_falla(client, repo, admin_token):
    """`?ciudad=` (vacío) se trata como «sin filtro». Se documenta: el panel
    nunca lo manda, pero si un bundle lo manda no debe dar 404 ni 500."""
    _sembrar(repo, [("t1", "ciu-tarija"), ("b1", "ciu-1")])
    r = client.get("/admin/comercios/pendientes-analisis?ciudad=", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() == {"pendientes": 2}


def test_pendientes_ciudad_valida_sin_pendientes_da_cero_y_no_404(client, repo, admin_token):
    _repo_estricto(repo)
    _sembrar(repo, [("t1", "ciu-tarija")])
    r = client.get("/admin/comercios/pendientes-analisis?ciudad=santa-cruz", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() == {"pendientes": 0}


def test_pendientes_no_cuenta_comercios_sin_ciudad_cuando_hay_filtro(client, repo, admin_token):
    _repo_estricto(repo)
    _sembrar(repo, [("t1", "ciu-tarija"), ("s1", None)])
    con = client.get("/admin/comercios/pendientes-analisis?ciudad=tarija", headers=_h(admin_token))
    sin = client.get("/admin/comercios/pendientes-analisis", headers=_h(admin_token))
    assert con.json() == {"pendientes": 1}
    assert sin.json() == {"pendientes": 2}          # sin filtro entran los sin ciudad


def test_pendientes_ignora_inactivos_y_ya_analizados_tambien_con_filtro(client, repo, admin_token):
    _repo_estricto(repo)
    repo.seed_comercio(slug="a", nombre="A", portada_url="http://x/a.jpg", activo=False, ciudad_id="ciu-tarija")
    repo.seed_comercio(slug="b", nombre="B", portada_url="http://x/b.jpg", activo=True, ciudad_id="ciu-tarija",
                       ia_analizado_at="2026-08-21T10:00:00Z")
    repo.seed_comercio(slug="c", nombre="C", activo=True, ciudad_id="ciu-tarija")      # sin foto
    r = client.get("/admin/comercios/pendientes-analisis?ciudad=tarija", headers=_h(admin_token))
    assert r.json() == {"pendientes": 0}


@pytest.mark.parametrize("slug", ["TARIJA", "Tarija ", "tarija%27%20OR%201%3D1--", "..%2F..%2Fbermejo",
                                  "%00", "a" * 500])
def test_pendientes_con_slug_raro_es_404_y_nunca_el_total(client, repo, admin_token, slug):
    """Mayúsculas, espacios, inyección y basura: el slug es exacto o es 404."""
    _repo_estricto(repo)
    _sembrar(repo, [("t1", "ciu-tarija"), ("b1", "ciu-1")])
    r = client.get(f"/admin/comercios/pendientes-analisis?ciudad={slug}", headers=_h(admin_token))
    assert r.status_code == 404, r.text
    assert "pendientes" not in r.json()


# ───────────────────────────────────── permisos antes que 404
def test_sin_token_no_se_puede_consultar_ni_saber_si_la_ciudad_existe(client, repo):
    _repo_estricto(repo)
    for slug in ("tarija", "no-existe"):
        r = client.get(f"/admin/comercios/pendientes-analisis?ciudad={slug}")
        assert r.status_code in (401, 403), (slug, r.status_code)
    r = client.post("/admin/comercios/analizar-tanda?ciudad=tarija")
    assert r.status_code in (401, 403)


def test_sin_permiso_comercios_editar_da_403_aunque_la_ciudad_no_exista(client, repo):
    """Si primero resolviera la ciudad, un usuario sin permiso podría averiguar
    qué ciudades existen mirando 404 vs 403."""
    _repo_estricto(repo)
    tok = auth.make_token("poco@y.com", rol="publicador", permisos=["moderar"])
    for slug in ("tarija", "no-existe"):
        r = client.get(f"/admin/comercios/pendientes-analisis?ciudad={slug}", headers=_h(tok))
        assert r.status_code == 403, (slug, r.text)
        r = client.post(f"/admin/comercios/analizar-tanda?ciudad={slug}", headers=_h(tok))
        assert r.status_code == 403, (slug, r.text)


def test_token_de_comercio_no_entra_a_los_endpoints_de_ciudad(client, repo):
    from tests.conftest import comercio_token
    _repo_estricto(repo)
    r = client.get("/admin/comercios/pendientes-analisis?ciudad=tarija", headers=_h(comercio_token()))
    assert r.status_code in (401, 403)


# ───────────────────────────────────── analizar-tanda: dos ciudades + filtro
def test_tanda_con_filtro_y_comercios_de_dos_ciudades_solo_toca_la_elegida(
        client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _repo_estricto(repo)
    _sembrar(repo, [("b1", "ciu-1"), ("t1", "ciu-tarija"), ("b2", "ciu-1"),
                    ("t2", "ciu-tarija"), ("t3", "ciu-tarija"), ("s1", None)])

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(PROPUESTA)):
        r = client.post("/admin/comercios/analizar-tanda?limite=20&ciudad=tarija", headers=_h(admin_token))

    body = r.json()
    assert r.status_code == 200, r.text
    assert sorted(f["slug"] for f in body["resultados"]) == ["t1", "t2", "t3"]
    assert body["restantes"] == 0
    for s in ("t1", "t2", "t3"):
        assert _por_slug(repo, s).get("ia_analizado_at"), s
    # Los de otra ciudad y el que no tiene ciudad quedan EXACTAMENTE como estaban.
    for s in ("b1", "b2", "s1"):
        assert not _por_slug(repo, s).get("ia_analizado_at"), s
    # Y siguen contando como pendientes del total general.
    assert client.get("/admin/comercios/pendientes-analisis", headers=_h(admin_token)).json() == {"pendientes": 3}


def test_tanda_con_filtro_respeta_el_limite_y_el_orden_por_antiguedad(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _repo_estricto(repo)
    _sembrar(repo, [("b1", "ciu-1"), ("t1", "ciu-tarija"), ("t2", "ciu-tarija"), ("t3", "ciu-tarija")])

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(PROPUESTA)):
        r = client.post("/admin/comercios/analizar-tanda?limite=2&ciudad=tarija", headers=_h(admin_token))

    body = r.json()
    assert [f["slug"] for f in body["resultados"]] == ["t1", "t2"]
    assert body["restantes"] == 1            # sólo t3: b1 no cuenta como «restante» de Tarija


def test_tanda_ciudad_valida_sin_pendientes_no_llama_a_la_ia(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _repo_estricto(repo)
    _sembrar(repo, [("b1", "ciu-1")])
    with patch("app.services.vision.httpx.post") as post:
        r = client.post("/admin/comercios/analizar-tanda?ciudad=santa-cruz", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() == {"procesados": 0, "restantes": 0, "resultados": [], "sin_mas": True}
    post.assert_not_called()
    assert not _por_slug(repo, "b1").get("ia_analizado_at")


def test_tanda_con_ciudad_vacia_equivale_a_sin_filtro(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _repo_estricto(repo)
    _sembrar(repo, [("b1", "ciu-1"), ("t1", "ciu-tarija")])
    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(PROPUESTA)):
        r = client.post("/admin/comercios/analizar-tanda?limite=20&ciudad=", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["procesados"] == 2


def test_tanda_con_slug_malicioso_es_404_y_no_gasta_cuota(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _repo_estricto(repo)
    _sembrar(repo, [("t1", "ciu-tarija")])
    with patch("app.services.vision.httpx.post") as post:
        r = client.post("/admin/comercios/analizar-tanda?ciudad=tarija'%20OR%20'1'='1", headers=_h(admin_token))
    assert r.status_code == 404
    post.assert_not_called()
    assert not _por_slug(repo, "t1").get("ia_analizado_at")


def test_tanda_resuelve_la_ciudad_una_sola_vez_por_ciudad(client, repo, admin_token, monkeypatch):
    """El cache por tanda: 3 comercios de Tarija = 1 consulta de ciudad."""
    _con_key(monkeypatch)
    _repo_estricto(repo)
    _sembrar(repo, [("t1", "ciu-tarija"), ("t2", "ciu-tarija"), ("t3", "ciu-tarija")])
    llamadas = []
    original = repo.get_ciudad_por_id
    repo.get_ciudad_por_id = lambda cid: llamadas.append(cid) or original(cid)

    with patch("app.api.moderacion.analizar_fotos", lambda u, r, c=None: dict(PROPUESTA)):
        r = client.post("/admin/comercios/analizar-tanda?limite=20", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert llamadas == ["ciu-tarija"]


def test_tanda_cada_comercio_recibe_el_prompt_de_su_ciudad_de_punta_a_punta(
        client, repo, admin_token, monkeypatch):
    """Sin mockear `analizar_fotos`: se mira el texto que llega al modelo. Un
    comercio de Bermejo (frontera) habla de Argentina; uno de Tarija no; uno sin
    ciudad dice sólo Bolivia."""
    _con_key(monkeypatch)
    _repo_estricto(repo)
    _sembrar(repo, [("b1", "ciu-1"), ("t1", "ciu-tarija"), ("s1", None)])
    prompts = []

    def falso_post(url, **kw):
        prompts.append(kw["json"]["contents"][0]["parts"][0]["text"])
        return _respuesta(PROPUESTA)

    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", side_effect=falso_post):
        r = client.post("/admin/comercios/analizar-tanda?limite=20", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert len(prompts) == 3
    bermejo, tarija, sin = prompts          # orden de created_at
    assert "en Bermejo, Bolivia — una ciudad de frontera" in bermejo and "Argentina" in bermejo
    assert "en Tarija, Bolivia" in tarija and "Argentina" not in tarija and "frontera" not in tarija.lower()
    assert "en Bolivia" in sin and "Bermejo" not in sin and "frontera" not in sin.lower()


# ───────────────────────────────────── analizar un comercio suelto
def test_analizar_comercio_suelto_le_pasa_su_ciudad_a_la_ia(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _repo_estricto(repo)
    c = repo.seed_comercio(slug="t1", nombre="T1", portada_url="http://x/t1.jpg", activo=True, ciudad_id="ciu-tarija")
    visto = {}

    def falso(urls, rubros, ciudad=None):
        visto["ciudad"] = ciudad
        return dict(PROPUESTA)

    with patch("app.api.moderacion.analizar_fotos", falso):
        r = client.post(f"/admin/comercio/{c['id']}/analizar", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert visto["ciudad"]["nombre"] == "Tarija"


def test_analizar_comercio_suelto_sin_ciudad_pasa_none_y_no_bermejo(client, repo, admin_token, monkeypatch):
    _con_key(monkeypatch)
    _repo_estricto(repo)
    c = repo.seed_comercio(slug="s1", nombre="S1", portada_url="http://x/s1.jpg", activo=True)
    visto = {"ciudad": "no-llamado"}

    def falso(urls, rubros, ciudad=None):
        visto["ciudad"] = ciudad
        return dict(PROPUESTA)

    with patch("app.api.moderacion.analizar_fotos", falso):
        r = client.post(f"/admin/comercio/{c['id']}/analizar", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert visto["ciudad"] is None


def test_analizar_comercio_con_ciudad_id_colgante_no_rompe_y_no_asume_bermejo(
        client, repo, admin_token, monkeypatch):
    """`ciudad_id` apunta a una fila que ya no existe: el repo devuelve None."""
    _con_key(monkeypatch)
    _repo_estricto(repo)
    c = repo.seed_comercio(slug="x", nombre="X", portada_url="http://x/x.jpg", activo=True, ciudad_id="ciu-borrada")
    visto = {}
    with patch("app.api.moderacion.analizar_fotos",
               lambda u, r, ciudad=None: visto.setdefault("c", ciudad) or dict(PROPUESTA)):
        r = client.post(f"/admin/comercio/{c['id']}/analizar", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert visto["c"] is None


# ───────────────────────────────────── prompt: bordes
def test_prompt_frontera_sin_pais_vecino_none_o_ausente_o_espacios():
    for ciudad in ({**BERMEJO, "pais_vecino": None},
                   {k: v for k, v in BERMEJO.items() if k != "pais_vecino"},
                   {**BERMEJO, "pais_vecino": "   "}):
        p = _prompt(RUBROS, ciudad)
        assert "frontera con el país vecino" in p, ciudad
        assert "None" not in p


def test_prompt_frontera_sin_nombre_no_dice_none_ni_bermejo():
    p = _prompt(RUBROS, {"es_frontera": True, "pais_vecino": "Argentina"})
    assert "None" not in p and "Bermejo" not in p
    assert "Esta ciudad es frontera con Argentina" in p
    assert "en Bolivia" in p


def test_prompt_ciudad_no_frontera_con_pais_vecino_cargado_no_lo_menciona():
    """Datos sucios: `es_frontera=False` pero `pais_vecino` con valor. Manda la bandera."""
    p = _prompt(RUBROS, {**TARIJA, "pais_vecino": "Argentina"})
    assert "Argentina" not in p and "frontera" not in p.lower()


def test_prompt_ciudad_dict_vacio_equivale_a_sin_ciudad():
    assert _prompt(RUBROS, {}) == _prompt(RUBROS, None)


@pytest.mark.parametrize("ciudad", [None, BERMEJO, TARIJA, {"nombre": "Pando {x} {{y}}", "es_frontera": False}])
def test_prompt_no_deja_llaves_de_formato_sin_resolver(ciudad):
    """El prompt es un f-string con un JSON de ejemplo: un `{{` o un `{regla`
    sin resolver significaría un prompt roto que el modelo obedece igual."""
    p = _prompt(RUBROS, ciudad)
    assert "{regla_sinonimos}" not in p and "{lugar}" not in p
    assert '"productos"' in p and "`sinonimos`" in p
    if not (ciudad and "{" in ciudad.get("nombre", "")):
        assert "{{" not in p


def test_prompt_nombre_de_ciudad_con_llaves_no_revienta_el_armado():
    p = _prompt(RUBROS, {"nombre": "Pando {x}", "es_frontera": True, "pais_vecino": "Brasil"})
    assert "Pando {x}" in p and "frontera con Brasil" in p


def test_analizar_fotos_sin_ciudad_sigue_funcionando_como_antes(monkeypatch):
    _con_key(monkeypatch)
    with patch("app.services.vision._descargar", return_value=b"jpg"), \
         patch("app.services.vision.httpx.post", return_value=_respuesta(PROPUESTA)) as post:
        out = analizar_fotos(["http://x/f.jpg"], RUBROS)
    texto = post.call_args.kwargs["json"]["contents"][0]["parts"][0]["text"]
    assert "en Bolivia" in texto and "Bermejo" not in texto
    assert out["confianza"] > 0


# ───────────────────────────────────── lugares y adornos: slug desconocido
@pytest.mark.parametrize("slug", ["no-existe", "BERMEJO", "bermejo ", "x'; drop table lugares;--",
                                  "../bermejo", "é" * 40])
def test_lugar_post_con_slug_raro_es_404_y_no_crea_nada(client, repo, admin_token, slug):
    _repo_estricto(repo)
    r = client.post("/admin/lugares", json={"nombre": "Mercado", "ciudad_slug": slug}, headers=_h(admin_token))
    assert r.status_code == 404, r.text
    assert not repo.lugares


@pytest.mark.parametrize("slug", ["no-existe", "BERMEJO", "x'; drop table mapa_adornos;--"])
def test_adorno_post_con_slug_raro_es_404_y_no_crea_nada(client, repo, admin_token, slug):
    _repo_estricto(repo)
    r = client.post("/admin/adornos", json={"tipo": "lapacho", "lat": -17.78, "lng": -63.18, "ciudad_slug": slug},
                    headers=_h(admin_token))
    assert r.status_code == 404, r.text
    assert not repo.adornos


def test_lugar_y_adorno_get_con_slug_desconocido_no_consultan_la_lista(client, repo, admin_token):
    _repo_estricto(repo)
    llamadas = []
    repo.list_lugares = lambda ciudad_id=None: llamadas.append(("lugares", ciudad_id)) or []
    repo.list_adornos = lambda ciudad_id=None: llamadas.append(("adornos", ciudad_id)) or []
    assert client.get("/admin/lugares?ciudad_slug=nope", headers=_h(admin_token)).status_code == 404
    assert client.get("/admin/adornos?ciudad_slug=nope", headers=_h(admin_token)).status_code == 404
    assert llamadas == []


def test_lugares_get_pasa_el_id_de_la_ciudad_pedida_y_no_el_de_bermejo(client, repo, admin_token):
    """El `FakeRepo.list_lugares` ignora la ciudad, así que el aislamiento se
    verifica espiando lo que el endpoint le pide al repo."""
    _repo_estricto(repo)
    pedidos = []
    repo.list_lugares = lambda ciudad_id=None: pedidos.append(ciudad_id) or []
    for slug in ("tarija", "santa-cruz", "bermejo"):
        assert client.get(f"/admin/lugares?ciudad_slug={slug}", headers=_h(admin_token)).status_code == 200
    assert pedidos == ["ciu-tarija", "ciu-santa-cruz", "ciu-1"]


def test_lugares_get_sin_parametro_default_bermejo_aunque_no_exista_otra_ciudad(client, repo, admin_token):
    _repo_estricto(repo)
    pedidos = []
    repo.list_lugares = lambda ciudad_id=None: pedidos.append(ciudad_id) or []
    assert client.get("/admin/lugares", headers=_h(admin_token)).status_code == 200
    assert pedidos == ["ciu-1"]


def test_lugar_post_ciudad_slug_null_cae_en_bermejo_como_los_bundles_viejos(client, repo, admin_token):
    _repo_estricto(repo)
    r = client.post("/admin/lugares", json={"nombre": "Mercado", "ciudad_slug": None}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["lugar"]["ciudad_id"] == "ciu-1"


def test_lugar_post_con_slug_vacio_no_cae_en_bermejo_en_silencio(client, repo, admin_token):
    """Un slug vacío no es «sin parámetro»: es un valor desconocido. Un panel que
    por un bug mande '' crearía el lugar en Bermejo sin avisar, que es justo lo
    que la spec dice que se terminó («una ciudad que no existe da error, no Bermejo»)."""
    _repo_estricto(repo)
    r = client.post("/admin/lugares", json={"nombre": "Mercado", "ciudad_slug": ""}, headers=_h(admin_token))
    assert r.status_code == 404, r.text
    assert not repo.lugares


def test_adorno_post_con_slug_vacio_no_cae_en_bermejo_en_silencio(client, repo, admin_token):
    _repo_estricto(repo)
    r = client.post("/admin/adornos", json={"tipo": "chalana", "lat": -22.7, "lng": -64.3, "ciudad_slug": ""},
                    headers=_h(admin_token))
    assert r.status_code == 404, r.text
    assert not repo.adornos


def test_get_con_slug_vacio_da_404_con_repo_estricto(client, repo, admin_token):
    """Igual que el POST de arriba: el GET trata '' como desconocido."""
    _repo_estricto(repo)
    assert client.get("/admin/lugares?ciudad_slug=", headers=_h(admin_token)).status_code == 404
    assert client.get("/admin/adornos?ciudad_slug=", headers=_h(admin_token)).status_code == 404


def test_adornos_aislados_por_ciudad_de_punta_a_punta(client, repo, admin_token):
    """El fake de adornos SÍ filtra por ciudad: crear en dos ciudades y listar."""
    _repo_estricto(repo)
    for slug, lat in (("tarija", -21.5), ("santa-cruz", -17.78), ("santa-cruz", -17.79)):
        r = client.post("/admin/adornos", json={"tipo": "lapacho", "lat": lat, "lng": -63.0, "ciudad_slug": slug},
                        headers=_h(admin_token))
        assert r.status_code == 200, r.text
    tarija = client.get("/admin/adornos?ciudad_slug=tarija", headers=_h(admin_token)).json()["items"]
    sc = client.get("/admin/adornos?ciudad_slug=santa-cruz", headers=_h(admin_token)).json()["items"]
    bermejo = client.get("/admin/adornos", headers=_h(admin_token)).json()["items"]
    assert len(tarija) == 1 and {a["ciudad_id"] for a in tarija} == {"ciu-tarija"}
    assert len(sc) == 2 and {a["ciudad_id"] for a in sc} == {"ciu-santa-cruz"}
    assert bermejo == []


def test_lugar_post_valida_nombre_antes_que_ciudad_y_no_crea_nada(client, repo, admin_token):
    _repo_estricto(repo)
    r = client.post("/admin/lugares", json={"nombre": "  ", "ciudad_slug": "no-existe"}, headers=_h(admin_token))
    assert r.status_code == 400
    assert not repo.lugares


def test_lugares_requieren_permiso_antes_de_resolver_la_ciudad(client, repo):
    _repo_estricto(repo)
    tok = auth.make_token("poco@y.com", rol="publicador", permisos=["moderar"])
    assert client.get("/admin/lugares?ciudad_slug=no-existe", headers=_h(tok)).status_code == 403
    assert client.post("/admin/lugares", json={"nombre": "M", "ciudad_slug": "no-existe"},
                       headers=_h(tok)).status_code == 403
    assert not repo.lugares


# ───────────────────────────────────── listado de comercios con ia_analizado_at
def test_listado_todos_trae_ia_analizado_at_y_la_ciudad_para_que_el_resumen_cierre(client, repo, admin_token):
    """El resumen por ciudad del panel necesita `ia_analizado_at` de CADA item y
    nunca debe faltar la clave (el chip cuenta `portada_url && !ia_analizado_at`)."""
    for i in range(5):
        repo.seed_comercio(slug=f"c{i}", nombre=f"C{i}", portada_url=f"http://x/{i}.jpg", activo=True,
                           **({"ia_analizado_at": "2026-08-21T10:00:00Z"} if i % 2 else {}))
    items = client.get("/moderacion/comercios?todos=true", headers=_h(admin_token)).json()["items"]
    assert len(items) == 5
    assert all("ia_analizado_at" in c for c in items)
    sin_clasificar = [c for c in items if c.get("portada_url") and not c["ia_analizado_at"]]
    assert len(sin_clasificar) == 3
    assert client.get("/admin/comercios/pendientes-analisis", headers=_h(admin_token)).json() == {"pendientes": 3}


def test_el_listado_real_sigue_trayendo_la_ciudad_embebida():
    """El resumen agrupa por `ciudades.slug`: si alguien saca el embed del SELECT,
    todo cae en «Sin ciudad». Se mira la constante (el fake no ejecuta el SELECT)."""
    from app.db.repository import _COLS_COMERCIO_ADMIN
    assert "ciudades(nombre, slug)" in _COLS_COMERCIO_ADMIN
    assert "ia_analizado_at" in _COLS_COMERCIO_ADMIN


# ───────────────────────────────────── texto de difusión
PUB = {"titulo": "Oferta"}


def test_difusion_ciudad_pasada_gana_sobre_la_embebida():
    c = {"nombre": "Casa X", "slug": "x", "ciudades": {"nombre": "Bermejo"}}
    t = difusion.texto_de(PUB, c, None, TARIJA)
    assert "📍 Casa X, Tarija" in t and "Bermejo" not in t


def test_difusion_embebida_como_lista_o_none_no_rompe_ni_inventa():
    for emb in ([{"nombre": "Tarija"}], None, "Tarija", 5):
        t = difusion.texto_de(PUB, {"nombre": "Casa X", "slug": "x", "ciudades": emb})
        assert "📍 Casa X" in t, emb
        assert "Casa X," not in t and "Tarija" not in t and "Bermejo" not in t, emb


def test_difusion_ciudad_con_nombre_vacio_none_o_espacios_lleva_solo_el_comercio():
    for ciudad in ({"nombre": ""}, {"nombre": None}, {"nombre": "   "}, {}):
        t = difusion.texto_de(PUB, {"nombre": "Casa X", "slug": "x"}, None, ciudad)
        assert "📍 Casa X\n" in t + "\n" and "Casa X," not in t, ciudad


def test_difusion_recorta_espacios_del_nombre_de_la_ciudad():
    t = difusion.texto_de(PUB, {"nombre": "Casa X", "slug": "x"}, None, {"nombre": "  Tarija  "})
    assert "📍 Casa X, Tarija" in t and "Tarija  " not in t


def test_difusion_sin_comercio_no_lleva_renglon_de_ubicacion():
    t = difusion.texto_de(PUB, None, None, TARIJA)
    assert "📍" not in t


@pytest.mark.parametrize("destino", ["facebook", "instagram", "wa_canal"])
def test_difusion_la_ciudad_sale_en_las_tres_redes_y_conserva_el_enlace(destino):
    t = difusion.texto_de(PUB, {"nombre": "Casa X", "slug": "x"}, destino, SANTA_CRUZ)
    assert "📍 Casa X, Santa Cruz" in t
    assert "/comercios/x?ref=" in t


def _preparar_envios(monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    monkeypatch.setattr(settings, "facebook_page_id", "111")
    monkeypatch.setattr(settings, "facebook_page_token", "tok")
    enviados = []
    monkeypatch.setattr(difusion, "_ENVIOS", {
        d: (lambda texto, img, _d=d: enviados.append(texto) or None) for d in difusion.DESTINOS})
    return enviados


def _encolar(repo, **kw):
    c = repo.seed_comercio(slug="x", nombre="Casa X", plan="destacado", **kw)
    pub = repo.insert_publicacion_directa(
        {"comercio_id": c["id"], "tipo": "oferta", "titulo": "algo", "estado": "aprobado"})
    repo.encolar_difusion(pub["id"], ["facebook"])
    return repo.difusion_pendientes(10)[0]


def test_procesar_comercio_sin_ciudad_id_no_consulta_ciudad_y_no_dice_bermejo(repo, monkeypatch):
    enviados = _preparar_envios(monkeypatch)
    consultas = []
    repo.get_ciudad_por_id = lambda cid: consultas.append(cid) or None
    fila = _encolar(repo)
    assert difusion.procesar(repo, fila)["estado"] == "enviado"
    assert consultas == []
    assert "📍 Casa X" in enviados[0] and "Bermejo" not in enviados[0] and "Casa X," not in enviados[0]


def test_procesar_si_la_consulta_de_ciudad_falla_igual_publica_sin_ciudad(repo, monkeypatch):
    enviados = _preparar_envios(monkeypatch)

    def boom(cid):
        raise RuntimeError("base caída")

    repo.get_ciudad_por_id = boom
    fila = _encolar(repo, ciudad_id="ciu-tarija")
    assert difusion.procesar(repo, fila)["estado"] == "enviado"
    assert "📍 Casa X" in enviados[0] and "Casa X," not in enviados[0] and "Bermejo" not in enviados[0]


def test_procesar_ciudad_id_colgante_publica_solo_con_el_nombre(repo, monkeypatch):
    enviados = _preparar_envios(monkeypatch)
    repo.get_ciudad_por_id = lambda cid: None
    fila = _encolar(repo, ciudad_id="ciu-borrada")
    assert difusion.procesar(repo, fila)["estado"] == "enviado"
    assert "📍 Casa X" in enviados[0] and "Casa X," not in enviados[0]


def test_procesar_ciudad_por_id_gana_sobre_la_embebida_vieja(repo, monkeypatch):
    """Si el comercio trae `ciudades` embebida desactualizada y `ciudad_id`, la
    fila resuelta por id es la que manda (es el argumento explícito de texto_de)."""
    enviados = _preparar_envios(monkeypatch)
    _repo_estricto(repo)
    fila = _encolar(repo, ciudad_id="ciu-santa-cruz", ciudades={"nombre": "Bermejo", "slug": "bermejo"})
    assert difusion.procesar(repo, fila)["estado"] == "enviado"
    assert "📍 Casa X, Santa Cruz" in enviados[0] and "Bermejo" not in enviados[0]
