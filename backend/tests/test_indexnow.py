"""B2: IndexNow (docs/visibilidad-buscadores-ia.md §3.12)."""
from datetime import datetime, timedelta, timezone

import pytest

from app.services import indexnow

CLAVE = "0123456789abcdef0123456789abcdef"


@pytest.fixture(autouse=True)
def _config(monkeypatch):
    monkeypatch.setattr(indexnow.settings, "sitio_url", "https://uruku.bo")
    monkeypatch.setattr(indexnow.settings, "indexnow_key", CLAVE)
    monkeypatch.setattr(indexnow.settings, "app_env", "prod")
    monkeypatch.setattr(indexnow.settings, "indexnow_worker", True)
    monkeypatch.setattr(indexnow.settings, "indexnow_endpoint", "https://api.indexnow.org/indexnow")


class _Resp:
    def __init__(self, status=200, text=""):
        self.status_code, self.text = status, text


def _capturar(monkeypatch, status=200, falla=None):
    llamadas = []

    def post(url, json=None, timeout=None, headers=None):
        llamadas.append({"url": url, "json": json, "timeout": timeout})
        if falla:
            raise falla
        return _Resp(status)

    monkeypatch.setattr(indexnow.httpx, "post", post)
    return llamadas


# ── reglas de indexación (§3.1) ─────────────────────────────────────────────────
def _c(**kw):
    base = {"slug": "farmacia-sol", "nombre": "Farmacia Sol", "activo": True, "suspendido": False,
            "rubro_slug": "farmacia", "subcategoria": None, "descripcion": None,
            "prod_obs_human": None, "prod_det_ia": None}
    base.update(kw)
    return base


def test_ficha_fina_son_los_cuatro_casos_de_la_spec():
    # con rubro real: indexable aunque no tenga texto
    assert not indexnow.is_business_thin(_c())
    # sin rubro / otros y sin nada de texto: fina
    assert indexnow.is_business_thin(_c(rubro_slug=None))
    assert indexnow.is_business_thin(_c(rubro_slug="otros", descripcion="   "))
    # otros pero con algún texto: no es fina
    assert not indexnow.is_business_thin(_c(rubro_slug="otros", subcategoria="Zapatos"))
    assert not indexnow.is_business_thin(_c(rubro_slug=None, prod_det_ia="remeras"))
    # «a clasificar» siempre es fina, aunque tenga rubro
    assert indexnow.is_business_thin(_c(nombre="Otros (A Clasificar)"))


def test_indexable_exige_activo_y_no_suspendido():
    assert indexnow.is_business_indexable(_c())
    assert not indexnow.is_business_indexable(_c(activo=False))
    assert not indexnow.is_business_indexable(_c(suspendido=True))


def test_las_urls_son_solo_de_fichas_indexables_y_sin_repetir():
    filas = [_c(slug="a"), _c(slug="a"), _c(slug="fina", rubro_slug="otros"),
             _c(slug="susp", suspendido=True), _c(slug="")]
    assert indexnow.business_urls(filas) == ["https://uruku.bo/comercios/a"]


# ── habilitación ────────────────────────────────────────────────────────────────
def test_sin_clave_o_fuera_de_prod_no_arranca(monkeypatch):
    assert indexnow.habilitado()
    monkeypatch.setattr(indexnow.settings, "indexnow_key", "")
    assert not indexnow.habilitado()
    monkeypatch.setattr(indexnow.settings, "indexnow_key", CLAVE)
    monkeypatch.setattr(indexnow.settings, "app_env", "qa")
    assert not indexnow.habilitado()
    monkeypatch.setattr(indexnow.settings, "app_env", "")
    assert not indexnow.habilitado()
    monkeypatch.setattr(indexnow.settings, "app_env", "prod")
    monkeypatch.setattr(indexnow.settings, "indexnow_worker", False)
    assert not indexnow.habilitado()


@pytest.mark.parametrize("clave", ["corta", "tiene espacio 12345678", "../../etc/passwd", "a" * 129, ""])
def test_una_clave_invalida_no_habilita(monkeypatch, clave):
    monkeypatch.setattr(indexnow.settings, "indexnow_key", clave)
    assert not indexnow.habilitado()


# ── envío ───────────────────────────────────────────────────────────────────────
def test_submit_manda_el_cuerpo_del_protocolo(monkeypatch):
    llamadas = _capturar(monkeypatch)
    assert indexnow.submit(["https://uruku.bo/comercios/a"]) is True
    assert llamadas[0]["url"] == "https://api.indexnow.org/indexnow"
    assert llamadas[0]["json"] == {
        "host": "uruku.bo", "key": CLAVE,
        "keyLocation": f"https://uruku.bo/{CLAVE}.txt",
        "urlList": ["https://uruku.bo/comercios/a"],
    }
    assert llamadas[0]["timeout"] and llamadas[0]["timeout"] <= 15


def test_submit_parte_en_pedidos_de_10000(monkeypatch):
    llamadas = _capturar(monkeypatch)
    urls = [f"https://uruku.bo/comercios/c{i}" for i in range(10_001)]
    assert indexnow.submit(urls) is True
    assert [len(c["json"]["urlList"]) for c in llamadas] == [10_000, 1]


def test_submit_sin_urls_no_llama(monkeypatch):
    llamadas = _capturar(monkeypatch)
    assert indexnow.submit([]) is True and llamadas == []


@pytest.mark.parametrize("status", [403, 422, 429, 500])
def test_submit_devuelve_false_ante_un_error_http_sin_lanzar(monkeypatch, status):
    _capturar(monkeypatch, status=status)
    assert indexnow.submit(["https://uruku.bo/comercios/a"]) is False


def test_submit_no_lanza_si_la_red_falla(monkeypatch):
    _capturar(monkeypatch, falla=RuntimeError("sin red"))
    assert indexnow.submit(["https://uruku.bo/comercios/a"]) is False


def test_submit_sin_clave_valida_no_llama(monkeypatch):
    llamadas = _capturar(monkeypatch)
    monkeypatch.setattr(indexnow.settings, "indexnow_key", "")
    assert indexnow.submit(["https://uruku.bo/comercios/a"]) is False and llamadas == []


def test_submit_loguea_los_eventos_con_nombre_snake_case(monkeypatch):
    eventos = []
    monkeypatch.setattr(indexnow.logger, "info", lambda ev, **kw: eventos.append(ev))
    monkeypatch.setattr(indexnow.logger, "warning", lambda ev, **kw: eventos.append(ev))
    _capturar(monkeypatch)
    indexnow.submit(["https://uruku.bo/comercios/a"])
    _capturar(monkeypatch, status=500)
    indexnow.submit(["https://uruku.bo/comercios/a"])
    assert eventos == ["indexnow_submitted", "indexnow_failed"]


# ── una vuelta del loop, contra el repo de prueba ─────────────────────────────────
def _alta(repo, slug, updated_at, **kw):
    fila = {"id": f"id-{slug}", "slug": slug, "nombre": kw.pop("nombre", slug.title()),
            "activo": True, "rubro_id": "rub-ropa", "updated_at": updated_at}
    fila.update(kw)
    repo.comercios[fila["id"]] = fila


def test_una_vuelta_avisa_la_ficha_editada_y_avanza_el_cursor(repo, monkeypatch):
    llamadas = _capturar(monkeypatch)
    cursor = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    _alta(repo, "vieja", "2026-11-02T11:00:00+00:00")                       # anterior al cursor
    _alta(repo, "editada", "2026-11-02T12:05:00+00:00")
    _alta(repo, "fina", "2026-11-02T12:10:00+00:00", rubro_id="rub-otros")  # sin texto: no se avisa
    nuevo, n = indexnow.run_once(repo, cursor)
    assert [c["json"]["urlList"] for c in llamadas] == [["https://uruku.bo/comercios/editada"]]
    assert n == 1
    assert nuevo == datetime(2026, 11, 2, 12, 10, tzinfo=timezone.utc)      # incluye la fina
    # segunda vuelta: nada nuevo, no llama
    nuevo2, n2 = indexnow.run_once(repo, nuevo)
    assert n2 == 0 and nuevo2 == nuevo and len(llamadas) == 1


def test_si_el_envio_falla_el_cursor_no_avanza(repo, monkeypatch):
    _capturar(monkeypatch, status=500)
    cursor = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    _alta(repo, "editada", "2026-11-02T12:05:00+00:00")
    nuevo, n = indexnow.run_once(repo, cursor)
    assert nuevo == cursor and n == 0


def test_la_vuelta_diaria_suma_las_paginas_fijas_y_las_farmacias_de_turno_por_ciudad(repo, monkeypatch):
    llamadas = _capturar(monkeypatch)
    cursor = datetime.now(timezone.utc) - timedelta(minutes=1)
    # Bermejo tiene un turno vigente; Santa Cruz no (su página propia daría 404)
    repo.seed_comercio(id="farm-1", slug="farm-1", nombre="Farm", ciudad_slug="bermejo")
    ahora = datetime.now(timezone.utc)
    repo.turnos_farmacia["t1"] = {"id": "t1", "comercio_id": "farm-1", "activo": True,
                                  "inicio": (ahora - timedelta(hours=1)).isoformat(),
                                  "fin": (ahora + timedelta(hours=1)).isoformat()}
    _nuevo, n = indexnow.run_once(repo, cursor, incluir_fijas=True)
    assert llamadas[0]["json"]["urlList"] == [
        "https://uruku.bo/", "https://uruku.bo/cambio", "https://uruku.bo/bermejo/farmacias-de-turno"]
    assert n == 3
    assert "https://uruku.bo/farmacias-de-turno" not in llamadas[0]["json"]["urlList"]


def test_sin_turnos_cargados_no_se_avisa_ninguna_farmacias_de_turno(repo):
    assert indexnow.fixed_urls(repo) == ["https://uruku.bo/", "https://uruku.bo/cambio"]
    assert indexnow.fixed_urls() == ["https://uruku.bo/", "https://uruku.bo/cambio"]


def test_turnos_urls_no_lanza_si_el_repo_falla():
    class Roto:
        def list_ciudades(self):
            raise RuntimeError("caída")

    assert indexnow.turnos_urls(Roto()) == []


# ── 4xx avanza el cursor; 5xx / red / 429 lo dejan ────────────────────────────────
@pytest.mark.parametrize("status", [400, 403, 422])
def test_un_4xx_avanza_el_cursor_y_loguea_el_status(repo, monkeypatch, status):
    _capturar(monkeypatch, status=status)
    avisos = []
    monkeypatch.setattr(indexnow.logger, "warning", lambda ev, **kw: avisos.append((ev, kw)))
    cursor = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    _alta(repo, "editada", "2026-11-02T12:05:00+00:00")
    nuevo, n = indexnow.run_once(repo, cursor)
    assert nuevo == datetime(2026, 11, 2, 12, 5, tzinfo=timezone.utc) and n == 0
    assert avisos and avisos[0][0] == "indexnow_failed" and avisos[0][1]["status"] == status


@pytest.mark.parametrize("status", [429, 500, 503])
def test_un_5xx_o_429_deja_el_cursor_para_reintentar(repo, monkeypatch, status):
    _capturar(monkeypatch, status=status)
    cursor = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    _alta(repo, "editada", "2026-11-02T12:05:00+00:00")
    assert indexnow.run_once(repo, cursor) == (cursor, 0)


def test_un_error_de_red_deja_el_cursor_para_reintentar(repo, monkeypatch):
    _capturar(monkeypatch, falla=RuntimeError("sin red"))
    cursor = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    _alta(repo, "editada", "2026-11-02T12:05:00+00:00")
    assert indexnow.run_once(repo, cursor) == (cursor, 0)


# ── fichas dadas de baja o suspendidas: se avisan para que salgan del índice ─────────
def test_las_fichas_dadas_de_baja_o_suspendidas_tambien_se_avisan(repo, monkeypatch):
    llamadas = _capturar(monkeypatch)
    cursor = datetime(2026, 11, 2, 12, 0, tzinfo=timezone.utc)
    _alta(repo, "editada", "2026-11-02T12:05:00+00:00")
    _alta(repo, "baja", "2026-11-02T12:06:00+00:00", activo=False)
    _alta(repo, "suspendida", "2026-11-02T12:07:00+00:00", suspendido=True)
    _alta(repo, "baja-vieja", "2026-11-02T11:00:00+00:00", activo=False)  # anterior al cursor
    nuevo, n = indexnow.run_once(repo, cursor)
    assert llamadas[0]["json"]["urlList"] == [
        "https://uruku.bo/comercios/editada",
        "https://uruku.bo/comercios/baja",
        "https://uruku.bo/comercios/suspendida"]
    assert n == 3 and nuevo == datetime(2026, 11, 2, 12, 7, tzinfo=timezone.utc)


def test_removed_urls_solo_incluye_baja_o_suspension():
    filas = [_c(slug="ok"), _c(slug="baja", activo=False), _c(slug="susp", suspendido=True),
             _c(slug="baja", activo=False), _c(slug="", activo=False)]
    assert indexnow.removed_urls(filas) == ["https://uruku.bo/comercios/baja",
                                            "https://uruku.bo/comercios/susp"]


# ── paridad de «ficha fina» con SQL 0180 / frontend ──────────────────────────────────
def test_texto_solo_con_espacios_cuenta_como_vacio_en_todos_los_campos():
    assert indexnow.is_business_thin(_c(rubro_slug="otros", subcategoria=" ", descripcion="\t\n",
                                        prod_obs_human="  ", prod_det_ia=" "))
    assert indexnow.is_business_thin(_c(rubro_slug="  "))
    assert not indexnow.is_business_thin(_c(rubro_slug="otros", prod_det_ia=" remeras "))


def test_si_el_repo_falla_no_lanza(monkeypatch):
    class Roto:
        def comercios_para_indexnow(self, *_a, **_k):
            raise RuntimeError("base caída")

    cursor = datetime(2026, 11, 2, tzinfo=timezone.utc)
    assert indexnow.run_once(Roto(), cursor) == (cursor, 0)


# ── el repo de verdad ───────────────────────────────────────────────────────────
class _Q:
    """Un `table()` de juguete con lo que usa el repo: select, gt, or_ (keyset), order, limit."""
    def __init__(self, filas, pedidos):
        self._f, self._p, self._orden, self._lim = list(filas), pedidos, [], None

    def select(self, *a, **k): return self
    def eq(self, *a, **k): self._p.append(("eq", a)); return self

    def gt(self, col, v):
        self._p.append(("gt", (col, v)))
        self._f = [f for f in self._f if f[col] > v]
        return self

    def or_(self, expr):
        import re
        self._p.append(("or_", expr))
        m = re.fullmatch(r"updated_at\.gt\.(.+),and\(updated_at\.eq\.(.+),id\.gt\.(.+)\)", expr)
        u, u2, i = m.groups()
        assert u == u2
        self._f = [f for f in self._f if f["updated_at"] > u or (f["updated_at"] == u and f["id"] > i)]
        return self

    def order(self, col): self._orden.append(col); return self
    def limit(self, n): self._lim = n; return self

    def execute(self):
        filas = sorted(self._f, key=lambda f: tuple(f[c] for c in self._orden))
        class R: pass
        r = R(); r.data = filas[:self._lim]; return r


class _Db:
    def __init__(self, comercios, rubros):
        self.pedidos, self._c, self._r = [], comercios, rubros

    def table(self, nombre):
        return _Q(self._c if nombre == "comercios" else self._r, self.pedidos)


def test_el_repo_real_resuelve_el_rubro_y_filtra_por_fecha():
    from app.db.repository import SupabaseRepo

    db = _Db([{"id": "1", "slug": "a", "nombre": "A", "updated_at": "2026-11-02T12:00:00+00:00",
               "activo": True, "rubro_id": "r1"}],
             [{"id": "r1", "slug": "ropa", "activo": True}])
    filas = SupabaseRepo(db).comercios_para_indexnow("2026-11-02T00:00:00+00:00")
    assert filas[0]["rubro_slug"] == "ropa"
    assert ("gt", ("updated_at", "2026-11-02T00:00:00+00:00")) in db.pedidos
    # ya no filtra por activo: las dadas de baja también se avisan
    assert not [p for p in db.pedidos if p[0] == "eq"]


def test_el_repo_real_no_pierde_filas_con_el_mismo_updated_at_mas_alla_del_limite():
    from app.db.repository import SupabaseRepo

    mismo = "2026-11-02T12:00:00+00:00"
    comercios = [{"id": f"{i:05d}", "slug": f"c{i}", "nombre": "C", "updated_at": mismo,
                  "activo": True, "rubro_id": "r1"} for i in range(2500)]
    comercios.append({"id": "99999", "slug": "ultima", "nombre": "U",
                      "updated_at": "2026-11-02T12:00:01+00:00", "activo": True, "rubro_id": "r1"})
    db = _Db(comercios, [{"id": "r1", "slug": "ropa", "activo": True}])
    filas = SupabaseRepo(db).comercios_para_indexnow("2026-11-02T00:00:00+00:00", limite=1000)
    assert len(filas) == 2501
    assert len({f["id"] for f in filas}) == 2501          # sin repetidas
    assert filas[-1]["slug"] == "ultima"


def test_el_repo_real_trata_un_rubro_inactivo_como_sin_rubro():
    from app.db.repository import SupabaseRepo

    db = _Db([{"id": "1", "slug": "a", "nombre": "A", "updated_at": "2026-11-02T12:00:00+00:00",
               "activo": True, "rubro_id": "r-viejo"}],
             [{"id": "r-viejo", "slug": "ropa", "activo": False}])
    fila = SupabaseRepo(db).comercios_para_indexnow("2026-11-02T00:00:00+00:00")[0]
    assert fila["rubro_slug"] is None
    assert indexnow.is_business_thin(fila)          # sin texto: fina, como en SQL 0180 y el front
    assert indexnow.business_urls([fila]) == []


# ── el loop del arranque ────────────────────────────────────────────────────────
def test_main_define_el_loop_y_lo_arranca_solo_si_esta_habilitado():
    from pathlib import Path
    src = (Path(__file__).resolve().parents[1] / "app" / "main.py").read_text(encoding="utf-8")
    assert "async def _indexnow_loop" in src
    assert "if indexnow.habilitado():" in src and "_indexnow_loop()" in src
