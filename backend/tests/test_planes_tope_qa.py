"""QA adversarial de «Planes: cuota, extra y tope de publicaciones guardadas».

Complementa a `test_planes_tope.py` (del dev) sin repetirlo. Lo que se busca acá:
- el archivado en los bordes: empates de `created_at`, el tope que baja de golpe,
  planes inexistentes / sin la columna, dos publicaciones casi a la vez;
- qué archivos se borran y cuáles NO, incluido un comercio que apunta a la foto
  de otro (multi-tenant);
- que un 402 no inserte ni archive nada, y que el cargo extra sea uno solo;
- que ningún texto que llegue a un comerciante o comprador lleve `precio_mes`.

Los tests marcados `xfail(strict=True)` documentan un BUG real: hoy fallan y el
reporte de QA dice por qué. Cuando se arreglen van a pasar, y `strict` hace que
la suite avise para sacarles la marca.
"""
import json
from datetime import date, datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.services import asistente, ingest, planes

BASE_FOTOS = "https://api.test/fotos"

# Precios "centinela": números que no aparecen en ninguna cuota, extra ni texto
# del sistema, para que encontrarlos en un texto sólo pueda significar "se filtró
# el precio de un plan" (el test del dev busca el 70/140/400, que se puede
# confundir con otros números).
CENTINELAS = {"publica": 3137, "destacado": 4242, "pro": 5959,
              "empleado_ia": 7171, "premium": 8383}


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _hoy(dias=0):
    return (date.today() + timedelta(days=dias)).isoformat()


class _Volumen:
    def __init__(self, raiz):
        self.raiz = raiz

    def foto(self, relativa: str):
        ruta = self.raiz / relativa
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_bytes(b"jpg")
        return f"{BASE_FOTOS}/{relativa}", ruta


@pytest.fixture
def volumen(tmp_path, monkeypatch):
    raiz = tmp_path / "volumen"
    raiz.mkdir()
    monkeypatch.setattr(settings, "fotos_dir", str(raiz))
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE_FOTOS)
    return _Volumen(raiz)


def _pub(repo, comercio, minutos, imagen_url=None, estado="aprobado", **extra):
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return repo.insert_publicacion_directa({
        "comercio_id": comercio["id"], "tipo": "oferta", "titulo": f"of {minutos}",
        "estado": estado, "imagen_url": imagen_url,
        "created_at": (base + timedelta(minutes=minutos)).isoformat(), **extra})


def _comercio(repo, plan="publica", slug="local", **kw):
    return repo.seed_comercio(slug=slug, nombre=slug.title(), plan=plan, **kw)


def _activas(repo, comercio):
    return [p for p in repo.publicaciones
            if p["comercio_id"] == comercio["id"] and p["activo"]]


def _hoy_n(repo, comercio, n):
    """n aprobadas de hoy: gasta la cuota del ciclo."""
    for i in range(n):
        repo.insert_publicacion_directa({
            "comercio_id": comercio["id"], "tipo": "oferta", "titulo": f"hoy {i}",
            "estado": "aprobado", "created_at": _hoy(0)})


def _con_precios_centinela(repo):
    for slug, precio in CENTINELAS.items():
        repo.upsert_plan(slug, {"precio_mes": precio})


def _tiene_centinela(texto: str) -> list[str]:
    """Cada centinela, escrito como 3137 o 3.137 o 3,137, dentro de `texto`."""
    malos = []
    for n in CENTINELAS.values():
        for forma in (str(n), f"{n:,}".replace(",", "."), f"{n:,}"):
            if forma in texto:
                malos.append(forma)
    return malos


# ═══════════════════════════════════════════════ archivado: bordes

def test_el_tope_baja_de_70_a_5_converge_de_a_5_por_publicacion_y_termina_en_5(repo, volumen):
    """Qué pasa cuando Admin baja el tope. El código frena el archivado masivo
    (`_MAX_ARCHIVAR_POR_VEZ`): la próxima publicación archiva como mucho 5, las
    más viejas, y el comercio converge al tope publicación a publicación. Se
    verifica orden (las más viejas primero), que no se pase del freno, que el
    freno no deje al comercio por debajo del tope y que el final sea el correcto."""
    c = _comercio(repo)
    rutas = []
    for m in range(70):
        url, ruta = volumen.foto(f"local/ofertas/f{m:02d}.jpg")
        _pub(repo, c, m, url)
        rutas.append(ruta)
    repo.upsert_plan("publica", {"publicaciones_guardadas": 5})

    primera = planes.archivar_excedentes(repo, c)

    assert primera == planes._MAX_ARCHIVAR_POR_VEZ == 5
    assert len(_activas(repo, c)) == 65
    assert [r.exists() for r in rutas[:6]] == [False] * 5 + [True]    # las 5 más viejas, no otras

    pasadas = 1
    while planes.archivar_excedentes(repo, c):
        pasadas += 1
        assert len(_activas(repo, c)) >= 5                 # nunca por debajo del tope
    assert pasadas == 13                                    # 65 sobrantes / 5 por vez
    assert len(_activas(repo, c)) == 5
    assert [r.exists() for r in rutas] == [False] * 65 + [True] * 5


def test_varias_publicaciones_con_el_mismo_created_at_archivan_justo_las_que_sobran(repo, volumen):
    repo.upsert_plan("publica", {"publicaciones_guardadas": 2})
    c = _comercio(repo)
    mismas = [_pub(repo, c, 7) for _ in range(6)]       # seis con el MISMO instante

    assert planes.archivar_excedentes(repo, c) == 4

    assert sum(1 for p in mismas if p["activo"]) == 2
    assert planes.archivar_excedentes(repo, c) == 0      # idempotente: la segunda no hace nada


@pytest.mark.parametrize("plan_del_comercio", ["fantasma", "", "   ", None])
def test_un_comercio_con_plan_inexistente_cae_al_gratis_tambien_para_el_tope(repo, volumen, plan_del_comercio):
    repo.upsert_plan("gratis", {"publicaciones_guardadas": 2})
    c = _comercio(repo, plan=plan_del_comercio)
    pubs = [_pub(repo, c, m) for m in range(4)]

    assert planes.archivar_excedentes(repo, c) == 2
    assert [p["activo"] for p in pubs] == [False, False, True, True]


def test_si_la_base_todavia_no_tiene_la_columna_no_se_archiva_nada_y_no_rompe(repo, volumen):
    """Backend nuevo con la migración 0134 sin correr: el plan viene sin la clave.
    Tiene que degradarse a "sin tope", no a un error ni a "tope 0"."""
    for p in repo.planes.values():
        p.pop("publicaciones_guardadas", None)
    c = _comercio(repo)
    for m in range(80):
        _pub(repo, c, m)

    assert planes.archivar_excedentes(repo, c) == 0
    assert len(_activas(repo, c)) == 80


@pytest.mark.parametrize("basura", ["abc", "", [], {}, -3, 0])
def test_un_tope_corrupto_en_la_base_no_lanza_ni_archiva(repo, volumen, basura):
    repo.upsert_plan("publica", {"publicaciones_guardadas": basura})
    c = _comercio(repo)
    for m in range(5):
        _pub(repo, c, m)

    assert planes.archivar_excedentes(repo, c) == 0
    assert len(_activas(repo, c)) == 5


def test_un_tope_en_texto_numerico_se_respeta(repo, volumen):
    repo.upsert_plan("publica", {"publicaciones_guardadas": "2"})
    c = _comercio(repo)
    for m in range(4):
        _pub(repo, c, m)
    assert planes.archivar_excedentes(repo, c) == 2


def test_dos_publicaciones_casi_simultaneas_no_archivan_de_mas(repo, volumen, monkeypatch):
    """Dos peticiones leen la lista de activas ANTES de que la otra archive.
    Las dos archivan "las más viejas de lo que vieron": la unión sigue siendo las
    más viejas, así que el comercio queda en el tope y no por debajo."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": 3})
    c = _comercio(repo)
    urls = []
    for m in range(5):
        url, ruta = volumen.foto(f"local/ofertas/s{m}.jpg")
        _pub(repo, c, m, url)
        urls.append(ruta)

    foto_vista = list(repo.publicaciones_activas_de(c["id"]))     # lo que vieron AMBAS
    monkeypatch.setattr(repo, "publicaciones_activas_de", lambda cid: list(foto_vista))

    primera = planes.archivar_excedentes(repo, c)
    segunda = planes.archivar_excedentes(repo, c)                  # con la lista vieja

    assert primera == 2
    assert segunda == 2                       # "archiva" lo que ya estaba archivado: no-op
    assert len(_activas(repo, c)) == 3
    assert [r.exists() for r in urls] == [False, False, True, True, True]


def test_dos_viejas_con_la_misma_foto_que_se_archivan_juntas_dejan_el_disco_limpio(repo, volumen):
    """La primera en archivarse ve a la otra todavía activa y no borra; la segunda
    ya no tiene a nadie que la use. Al final el archivo no puede quedar huérfano."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": 1})
    c = _comercio(repo)
    url, ruta = volumen.foto("local/ofertas/doble.jpg")
    _pub(repo, c, 0, url)
    _pub(repo, c, 1, url)
    _pub(repo, c, 2)

    assert planes.archivar_excedentes(repo, c) == 2
    assert not ruta.exists()


def test_archivar_no_devuelve_cuota_las_archivadas_siguen_contando_en_el_ciclo(repo, volumen):
    """Si archivar liberara cuota, un comercio podría publicar sin límite
    mientras el tope mueva sus publicaciones viejas afuera del conteo."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": 5})
    c = _comercio(repo, confiable=True)
    _hoy_n(repo, c, 25)                                  # cuota de 25 gastada

    antes = planes.estado(repo, c)
    assert antes["excedido"] is True

    total = 0
    while (n := planes.archivar_excedentes(repo, c)):
        total += n
    assert total == 20
    assert len(_activas(repo, c)) == 5
    despues = planes.estado(repo, c)
    assert despues["usadas"] == 25 and despues["excedido"] is True


# ═══════════════════════════════════════════════ archivos: qué se borra y qué no

def _con_tope_uno(repo, slug="local", plan="publica"):
    repo.upsert_plan(plan, {"publicaciones_guardadas": 1})
    return _comercio(repo, plan=plan, slug=slug)


def test_si_la_ruta_es_un_directorio_no_lanza_y_la_publicacion_queda_archivada(repo, volumen):
    c = _con_tope_uno(repo)
    (volumen.raiz / "local" / "ofertas" / "carpeta.jpg").mkdir(parents=True)
    vieja = _pub(repo, c, 0, f"{BASE_FOTOS}/local/ofertas/carpeta.jpg")
    _pub(repo, c, 1)

    assert planes.archivar_excedentes(repo, c) == 1
    assert vieja["activo"] is False
    assert (volumen.raiz / "local" / "ofertas" / "carpeta.jpg").is_dir()


def test_una_url_con_el_host_en_mayusculas_no_se_considera_propia_y_no_lanza(repo, volumen):
    """Lado seguro: ante la duda no se borra (el archivo queda huérfano, nada se
    rompe). Se documenta para que un cambio de normalización sea consciente."""
    c = _con_tope_uno(repo)
    _, ruta = volumen.foto("local/ofertas/x.jpg")
    _pub(repo, c, 0, "HTTPS://API.TEST/fotos/local/ofertas/x.jpg")
    _pub(repo, c, 1)

    assert planes.archivar_excedentes(repo, c) == 1
    assert ruta.exists()


@pytest.mark.parametrize("sufijo", ["?v=2&x=%2e%2e", "#frag", "?", "?v=2"])
def test_una_url_no_canonica_con_query_o_fragmento_no_se_borra_pero_se_archiva(repo, volumen, sufijo):
    """Política vigente: sólo se borra la URL EXACTA `<slug>/ofertas/<archivo>`.
    Con `?` o `#` se archiva la fila y el archivo queda (lado seguro)."""
    c = _con_tope_uno(repo)
    url, ruta = volumen.foto("local/ofertas/x.jpg")
    vieja = _pub(repo, c, 0, url + sufijo)
    _pub(repo, c, 1)

    assert planes.archivar_excedentes(repo, c) == 1
    assert vieja["activo"] is False
    assert ruta.exists()


def test_una_url_con_caracteres_codificados_no_se_borra(repo, volumen):
    c = _con_tope_uno(repo)
    _, ruta = volumen.foto("local/ofertas/mi foto.jpg")
    _pub(repo, c, 0, f"{BASE_FOTOS}/local/ofertas/mi%20foto.jpg")
    _pub(repo, c, 1)

    planes.archivar_excedentes(repo, c)
    assert ruta.exists()


def test_el_nombre_que_arma_uruku_se_borra(repo, volumen):
    """La forma real: `wa_media.guardar_imagen_publicacion` -> `<slug>/ofertas/<hex16>.jpg`.
    Si este test falla, el tope archiva pero el disco ya no baja."""
    import secrets

    c = _con_tope_uno(repo)
    nombre = f"{secrets.token_hex(8)}.jpg"
    url, ruta = volumen.foto(f"local/ofertas/{nombre}")
    _pub(repo, c, 0, url)
    _pub(repo, c, 1)

    planes.archivar_excedentes(repo, c)
    assert not ruta.exists()


def test_si_el_slug_del_comercio_cambio_las_fotos_viejas_no_se_borran(repo, volumen):
    """LIMITACIÓN (no bug de seguridad): `update_comercio` rearma el slug al
    renombrar un comercio con slug genérico (`comercio-N`), y las fotos ya
    guardadas siguen en la carpeta del slug viejo. Con la guarda de propiedad por
    slug esas fotos quedan huérfanas al archivarse. Seguro, pero el disco no baja
    para esos comercios."""
    c = _con_tope_uno(repo, slug="panaderia-don-pepe")        # slug nuevo
    _, ruta = volumen.foto("comercio-7/ofertas/vieja.jpg")     # foto guardada con el slug viejo
    _pub(repo, c, 0, f"{BASE_FOTOS}/comercio-7/ofertas/vieja.jpg")
    _pub(repo, c, 1)

    assert planes.archivar_excedentes(repo, c) == 1
    assert ruta.exists()


@pytest.mark.parametrize("relativa", [
    "local/ofertas/sub/x.jpg",          # `ofertas` no es la carpeta inmediata
    "local/ofertas/",                   # sin nombre de archivo
    "ofertas/x.jpg",                    # sin slug
    "local//ofertas/x.jpg",             # parte vacía
    "local/ofertas/./x.jpg",
    "local/ofertas/x.jpg%00.png",       # byte nulo
])
def test_formas_raras_de_url_no_borran_nada_y_no_lanzan(repo, volumen, relativa):
    c = _con_tope_uno(repo)
    url, ruta = volumen.foto("local/ofertas/x.jpg")
    _pub(repo, c, 0, f"{BASE_FOTOS}/{relativa}")
    _pub(repo, c, 1)

    assert planes.archivar_excedentes(repo, c) == 1
    assert ruta.exists()


@pytest.mark.parametrize("sufijo", ["", "?x=1", "#x", "%2e"])
def test_un_comercio_no_puede_hacer_borrar_la_foto_de_otro_apuntando_a_ella(repo, volumen, sufijo):
    """REGRESIÓN de QA-1 (corregido en el árbol mientras se hacía este QA). Antes,
    `imagen_en_uso` comparaba la URL exacta pero el borrado ignoraba `?`/`#`: un
    comercio con tope bajo apuntaba su publicación a la foto de OTRO con `?x` y,
    al archivarse la suya, se borraba la de la víctima. Es posible porque
    `PublicarBody.imagen_url` es texto libre sin validar."""
    atacante = _con_tope_uno(repo, slug="atacante")
    victima = _comercio(repo, slug="victima")
    url_victima, ruta_victima = volumen.foto("victima/ofertas/oferta.jpg")
    _pub(repo, victima, 0, url_victima)             # la foto de la víctima, activa y legítima

    _pub(repo, atacante, 0, url_victima + sufijo)
    _pub(repo, atacante, 1)                         # al entrar la siguiente se archiva la suya

    planes.archivar_excedentes(repo, atacante)

    assert ruta_victima.exists(), "se borró la foto de OTRO comercio"


def test_un_comercio_no_borra_una_foto_de_ofertas_de_otro_aunque_nadie_mas_la_use(repo, volumen):
    """Aun huérfana, una foto bajo la carpeta de otro comercio no es del que archiva."""
    atacante = _con_tope_uno(repo, slug="atacante")
    url_ajena, ruta_ajena = volumen.foto("victima/ofertas/huerfana.jpg")
    _pub(repo, atacante, 0, url_ajena)
    _pub(repo, atacante, 1)

    assert planes.archivar_excedentes(repo, atacante) == 1
    assert ruta_ajena.exists()


def test_misma_foto_con_distinta_forma_de_url_no_se_borra_si_otra_activa_la_usa(repo, volumen):
    """REGRESIÓN de QA-1b: dos filas del mismo comercio, una con `?v=2`."""
    c = _con_tope_uno(repo)
    url, ruta = volumen.foto("local/ofertas/x.jpg")
    _pub(repo, c, 0, url + "?v=2")
    _pub(repo, c, 1, url)                           # activa y usa el mismo archivo

    planes.archivar_excedentes(repo, c)

    assert ruta.exists()


# ═══════════════════════════════════════════════ el explorador

def test_una_publicacion_del_explorador_archiva_la_del_comerciante_con_su_foto_sin_cobrar(repo, volumen, monkeypatch):
    monkeypatch.setattr(settings, "wa_numeros_explorador", "59170000555", raising=False)
    repo.upsert_plan("publica", {"publicaciones_guardadas": 3})
    c = repo.seed_comercio(id="com-e1", slug="local", nombre="Local", codigo="AQP5", plan="publica")
    url, ruta = volumen.foto("local/ofertas/del-comerciante.jpg")
    suya = _pub(repo, c, 0, url)
    _pub(repo, c, 1)
    _pub(repo, c, 2)
    _hoy_n(repo, c, 0)

    ingest.handle_message({"event": "message", "session": "obs@c.us", "payload": {
        "id": "wa-x1", "from": "59170000555@c.us", "fromMe": False,
        "body": "URUKU-AQP5 zapatilla Bs 180", "type": "text", "timestamp": 1700000000}}, repo)

    assert suya["activo"] is False                # la oferta del comerciante, la más vieja, se fue
    assert not ruta.exists()
    assert len(_activas(repo, c)) == 3
    assert repo.cargos_extra == []


# ═══════════════════════════════════════════════ /comercio/publicar: 402 y cargo

def _post_publicar(client, comercio_id, **extra):
    from tests.conftest import comercio_token

    return client.post("/comercio/publicar",
                       json={"tipo": "oferta", "titulo": "una más", **extra},
                       headers=_h(comercio_token(comercio_id)))


def test_con_plan_vencido_da_402_y_no_inserta_ni_archiva_ni_cobra(client, repo, volumen):
    """Aunque el comercio esté pasado del tope de guardadas: un 402 no puede tener
    efectos secundarios (ni borrar fotos)."""
    repo.upsert_plan("gratis", {"publicaciones_guardadas": 2})
    c = repo.seed_comercio(id="com-v", slug="local", nombre="V", plan="gratis",
                           created_at=_hoy(-200))
    url, ruta = volumen.foto("local/ofertas/x.jpg")
    pubs = [_pub(repo, c, 0, url), _pub(repo, c, 1), _pub(repo, c, 2)]
    antes = len(repo.publicaciones)

    r = _post_publicar(client, "com-v")

    assert r.status_code == 402
    assert len(repo.publicaciones) == antes
    assert all(p["activo"] for p in pubs)
    assert ruta.exists()
    assert repo.cargos_extra == []


def test_sin_extras_pasada_la_cuota_da_402_y_no_archiva(client, repo, volumen):
    repo.upsert_plan("publica", {"permite_extras": False, "publicaciones_guardadas": 2})
    c = repo.seed_comercio(id="com-b", slug="local", nombre="B", plan="publica", confiable=True)
    _hoy_n(repo, c, 25)
    url, ruta = volumen.foto("local/ofertas/x.jpg")
    repo.publicaciones[0]["imagen_url"] = url
    activas_antes = len(_activas(repo, c))

    r = _post_publicar(client, "com-b")

    assert r.status_code == 402
    assert len(_activas(repo, c)) == activas_antes
    assert ruta.exists()
    assert repo.cargos_extra == []


def test_el_cargo_extra_se_registra_una_sola_vez_por_publicacion(client, repo):
    c = repo.seed_comercio(id="com-q", slug="q", nombre="Q", plan="publica", confiable=True)
    _hoy_n(repo, c, 25)

    r1 = _post_publicar(client, "com-q")
    assert r1.status_code == 200 and len(repo.cargos_extra) == 1

    # Un reintento interno del cobro para la MISMA publicación no duplica.
    planes.cobrar_extra(repo, c, r1.json()["publicacion"]["id"], repo.get_plan("publica"))
    assert len(repo.cargos_extra) == 1

    # Una publicación nueva sí genera su propio cargo (una por publicación).
    r2 = _post_publicar(client, "com-q")
    assert r2.status_code == 200
    assert len(repo.cargos_extra) == 2
    assert len({c_["publicacion_id"] for c_ in repo.cargos_extra}) == 2


def test_dentro_de_la_cuota_y_pasado_el_tope_se_archiva_sin_cobrar_ni_avisar(client, repo, volumen):
    """El tope de guardadas y la cuota son cosas distintas: archivar no genera
    cargo ni aviso."""
    repo.upsert_plan("publica", {"publicaciones_guardadas": 2, "publicaciones_mes": 500})
    c = repo.seed_comercio(id="com-g", slug="local", nombre="G", plan="publica", confiable=True)
    _pub(repo, c, 0)
    _pub(repo, c, 1)

    r = _post_publicar(client, "com-g")

    assert r.status_code == 200
    assert r.json()["aviso"] is None
    assert repo.cargos_extra == []
    assert len(_activas(repo, c)) == 2


def test_un_comercio_con_plan_inexistente_puede_publicar_como_gratis(client, repo):
    c = repo.seed_comercio(id="com-f", slug="f", nombre="F", plan="fantasma", confiable=True)

    r = _post_publicar(client, "com-f")

    assert r.status_code == 200, r.text
    assert r.json()["aviso"] is None
    assert len(_activas(repo, c)) == 1


def test_el_webhook_repetido_no_cobra_ni_archiva_dos_veces(repo, volumen, monkeypatch):
    """Idempotencia: WAHA reenvía el mismo mensaje. Una sola publicación, un solo
    cargo, y el tope se aplica una vez."""
    monkeypatch.setattr(ingest, "_avisar", lambda chat, texto: True)
    repo.upsert_plan("publica", {"publicaciones_guardadas": 30})
    c = _comercio(repo, confiable=True)
    _hoy_n(repo, c, 25)                              # cuota gastada: la próxima se cobra
    repo.vincular_grupo_comercio("120363@g.us", c["id"], "G", "admin", "test")
    evento = {"event": "message", "session": "default", "payload": {
        "id": "m-repetido", "from": "120363@g.us", "participant": "59170000009@c.us",
        "body": "oferta nueva", "type": "text", "fromMe": False}}

    ingest.handle_message(evento, repo)
    n_pubs = len(repo.publicaciones)
    ingest.handle_message(evento, repo)

    assert len(repo.publicaciones) == n_pubs
    assert len(repo.cargos_extra) == 1


# ═══════════════════════════════════════════════ sin precios de planes en ningún texto

def test_ningun_texto_de_aviso_lleva_un_precio_centinela(repo):
    _con_precios_centinela(repo)
    textos = []
    for plan in repo.list_planes():
        for consecuencia in ("cobrar", "bloquear", "vencido"):
            for siguiente in (None, *repo.list_planes()):
                est = {"plan": {**plan, "permite_extras": consecuencia != "bloquear",
                                "publica_meses": plan.get("publica_meses") or 2},
                       "cuota": plan.get("publicaciones_mes") or 1,
                       "consecuencia": consecuencia}
                textos.append(planes.texto_de_aviso(est, siguiente))
    assert len(textos) > 100
    for t in textos:
        assert _tiene_centinela(t) == [], t


def test_publicar_pasado_de_cuota_no_filtra_ningun_precio_en_toda_la_respuesta(client, repo):
    _con_precios_centinela(repo)
    repo.seed_comercio(id="com-q", slug="q", nombre="Q", plan="publica", confiable=True)
    _hoy_n(repo, repo.comercios["com-q"], 25)

    r = _post_publicar(client, "com-q")

    assert r.status_code == 200
    crudo = json.dumps(r.json(), ensure_ascii=False)
    assert _tiene_centinela(crudo) == []
    assert "precio_mes" not in crudo


@pytest.mark.parametrize("plan_slug,preparar", [
    ("publica", lambda repo, c: (repo.upsert_plan("publica", {"permite_extras": False}), _hoy_n(repo, c, 25))),
    ("gratis", lambda repo, c: c.update(created_at=_hoy(-200))),
])
def test_el_402_no_filtra_ningun_precio(client, repo, plan_slug, preparar):
    _con_precios_centinela(repo)
    c = repo.seed_comercio(id="com-4", slug="c4", nombre="C4", plan=plan_slug, confiable=True)
    preparar(repo, c)

    r = _post_publicar(client, "com-4")

    assert r.status_code == 402
    crudo = json.dumps(r.json(), ensure_ascii=False)
    assert _tiene_centinela(crudo) == []
    assert "precio_mes" not in crudo


@pytest.mark.parametrize("pregunta", [
    "¿cuánto cuestan los planes?",
    "precio de los planes",
    "cuanto cuesta el plan pro",
    "¿es gratis? ¿hay que pagar?",
    "quiero un chatbot para mi negocio",
    "qué planes tienen",
])
def test_el_asistente_no_filtra_ningun_precio_de_plan(repo, monkeypatch, pregunta):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    _con_precios_centinela(repo)
    r = asistente.responder(repo, pregunta, ahora=datetime(2026, 9, 15, 11, 0))
    assert _tiene_centinela(r.texto) == [], r.texto
    assert "precio_mes" not in r.texto


# ═══════════════════════════════════════════════ Admin › Planes

@pytest.mark.parametrize("valor", ["abc", 2.5, [], {}, "dos"])
def test_el_panel_rechaza_un_tope_que_no_es_entero(client, repo, admin_token, valor):
    r = client.put("/admin/planes/publica", json={"publicaciones_guardadas": valor},
                   headers=_h(admin_token))
    assert r.status_code == 422, r.text
    assert repo.get_plan("publica")["publicaciones_guardadas"] == 70


def test_el_panel_exige_autenticacion_para_cambiar_el_tope(client, repo):
    from tests.conftest import comercio_token

    sin = client.put("/admin/planes/publica", json={"publicaciones_guardadas": 1})
    assert sin.status_code in (401, 403)
    comercio = client.put("/admin/planes/publica", json={"publicaciones_guardadas": 1},
                          headers=_h(comercio_token("com-1")))
    assert comercio.status_code in (401, 403)
    assert repo.get_plan("publica")["publicaciones_guardadas"] == 70


def test_un_cuerpo_vacio_sigue_siendo_400_y_no_toca_el_tope(client, repo, admin_token):
    r = client.put("/admin/planes/publica", json={}, headers=_h(admin_token))
    assert r.status_code == 400
    assert repo.get_plan("publica")["publicaciones_guardadas"] == 70


def test_un_plan_nuevo_sin_nombre_y_con_solo_el_tope_null_sigue_pidiendo_nombre(client, repo, admin_token):
    r = client.put("/admin/planes/inventado", json={"publicaciones_guardadas": None},
                   headers=_h(admin_token))
    assert r.status_code == 400


def test_el_formulario_del_panel_con_todos_los_campos_y_tope_vacio_deja_sin_tope(client, repo, admin_token):
    """Lo que manda `planes-panel.tsx` al guardar con el campo vacío."""
    r = client.put("/admin/planes/publica", headers=_h(admin_token), json={
        "nombre": "Publica", "precio_mes": 70, "publicaciones_mes": 25,
        "publicaciones_guardadas": None, "precio_publicacion_extra": 5,
        "permite_extras": True, "publica_meses": None, "descripcion": "x",
        "incluye": [], "visible": True})
    assert r.status_code == 200, r.text
    assert repo.get_plan("publica")["publicaciones_guardadas"] is None
    # y entonces no se archiva nada
    c = _comercio(repo)
    for m in range(90):
        _pub(repo, c, m)
    assert planes.archivar_excedentes(repo, c) == 0


def test_el_panel_rechaza_un_tope_que_no_entra_en_un_int4(client, repo, admin_token):
    """La columna es `int`: un valor fuera de rango daba un 500 en Postgres en
    vez de un 422 que dice qué está mal."""
    r = client.put("/admin/planes/publica", json={"publicaciones_guardadas": 2**31},
                   headers=_h(admin_token))
    assert r.status_code == 422
