"""Cuándo vence el diseño de una foto de galería (docs/fotos-estilo-uruku.md §3).

El diseño de la galería no lleva textos de la base: vence SÓLO si cambia la foto. Dos casos:
  (a) `update_foto_comercio` con un `url` distinto (el intercambio de `portada.usar_de_galeria`): el repositorio vacía las
      tres columnas `diseno_*` y quien llama suelta los archivos (el agente no borra);
  (b) se borra la fila (`borrar_foto`, que incluye el reemplazo en el tope): `borrar_archivos` suelta también los `diseno-*`.
La foto original nunca se borra por un diseño.
"""
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings
from app.db.repository import COLUMNAS_DISENO_FOTO, diseno_foto_vencido
from app.services import fotos_galeria, portada
from app.services.imagenes import guardar_foto_local

BASE = "https://api.test/fotos"
VACIAS = {c: None for c in COLUMNAS_DISENO_FOTO}
AGENTE = "agente@bermejolive.com"


@pytest.fixture(autouse=True)
def _base(monkeypatch):
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _jpeg(color="green") -> bytes:
    buf = BytesIO()
    Image.new("RGB", (600, 600), color).save(buf, format="JPEG")
    return buf.getvalue()


def _en_disco(url) -> bool:
    return (Path(settings.fotos_dir) / url[len(BASE) + 1:]).exists()


def _archivo(nombre: str, color="green") -> str:
    guardar_foto_local(f"local-v/{nombre}", _jpeg(color))
    return f"{BASE}/local-v/{nombre}"


@pytest.fixture
def mundo(repo):
    """Un comercio con portada, una foto de galería (`f1`) con diseño vigente + propuesta, y otra sin diseño (`f2`)."""
    portada_url = _archivo("portada.jpg")
    f1, f1t = _archivo("g1.jpg", "red"), _archivo("g1_t.jpg", "red")
    d, dt, p, pt = (_archivo(n, "blue") for n in ("diseno-aaa.jpg", "diseno-aaa-t.jpg", "diseno-bbb.jpg", "diseno-bbb-t.jpg"))
    f2 = _archivo("g2.jpg", "yellow")
    c = repo.seed_comercio(id="com-v", slug="local-v", nombre="Local V", whatsapp="59170000009", ciudad_id="ciu-1",
                           portada_url=portada_url, portada_thumb_url=None, cargado_por=AGENTE)
    repo.comercio_fotos.append({"id": "f1", "comercio_id": "com-v", "url": f1, "thumb_url": f1t, "orden": 0,
                                "created_at": "2026-01-01T00:00:00+00:00", "diseno_url": d, "diseno_thumb_url": dt,
                                "diseno_propuesta_url": p})
    repo.comercio_fotos.append({"id": "f2", "comercio_id": "com-v", "url": f2, "thumb_url": None, "orden": 1,
                                "created_at": "2026-01-02T00:00:00+00:00"})
    return {"c": c, "portada": portada_url, "f1": f1, "f1t": f1t, "d": d, "dt": dt, "p": p, "pt": pt, "f2": f2}


def _fila(repo, foto_id="f1") -> dict:
    return next(f for f in repo.comercio_fotos if f["id"] == foto_id)


def _vacia(fila) -> bool:
    return all(fila.get(c) is None for c in COLUMNAS_DISENO_FOTO)


# ══════════════════════════════════════════ la regla (repositorio)

def test_diseno_foto_vencido_es_puro_y_solo_mira_el_url():
    con = {"url": "a", "diseno_url": "d", "diseno_thumb_url": "dt", "diseno_propuesta_url": None}
    assert diseno_foto_vencido(con, {"url": "b"}) == VACIAS
    assert diseno_foto_vencido(con, {"url": "a"}) == {}                   # el mismo valor no vence nada
    assert diseno_foto_vencido(con, {"thumb_url": "x", "orden": 3}) == {}  # otros campos no cuentan
    assert diseno_foto_vencido({"url": "a", "diseno_propuesta_url": "p"}, {"url": "b"}) == VACIAS   # también la propuesta
    assert diseno_foto_vencido({"url": "a"}, {"url": "b"}) == {}           # sin diseño no hay nada que vaciar
    assert diseno_foto_vencido(None, {"url": "b"}) == {}


def test_el_repo_vacia_las_tres_columnas_si_cambia_el_url(repo, mundo):
    repo.update_foto_comercio("f1", "com-v", {"url": "https://otra/foto.jpg", "thumb_url": None})
    assert _vacia(_fila(repo)) and _fila(repo)["url"] == "https://otra/foto.jpg"


def test_el_repo_no_vacia_nada_si_el_url_es_el_mismo_o_no_viaja(repo, mundo):
    repo.update_foto_comercio("f1", "com-v", {"url": mundo["f1"], "thumb_url": mundo["f1t"]})
    repo.update_foto_comercio("f1", "com-v", {"orden": 5})
    f = _fila(repo)
    assert (f["diseno_url"], f["diseno_thumb_url"], f["diseno_propuesta_url"]) == (mundo["d"], mundo["dt"], mundo["p"])


def test_lo_que_el_llamador_pone_explicito_gana_sobre_el_vencimiento(repo, mundo):
    repo.update_foto_comercio("f1", "com-v", {"url": "https://otra/foto.jpg", "diseno_url": mundo["d"]})
    f = _fila(repo)
    assert f["diseno_url"] == mundo["d"] and f["diseno_thumb_url"] is None and f["diseno_propuesta_url"] is None


def test_el_repo_real_lee_la_fila_antes_de_escribir_solo_si_cambia_el_url():
    """`SupabaseRepo.update_foto_comercio`: una lectura previa sólo si el patch trae `url` (si no, ninguna ida y vuelta de más)."""
    from app.db.repository import SupabaseRepo

    class Q:
        def __init__(self, log, data):
            self.log, self.data = log, data

        def __getattr__(self, nombre):
            def llamar(*a, **kw):
                self.log.append(nombre)
                return self
            return llamar

        def execute(self):
            self.log.append("execute")
            return type("R", (), {"data": self.data})()

    log, escrituras = [], []
    repo = SupabaseRepo.__new__(SupabaseRepo)

    class Db:
        def table(self, nombre):
            q = Q(log, [{"id": "f1", "url": "a", "diseno_url": "d", "diseno_thumb_url": None, "diseno_propuesta_url": None}])
            original_update = q.update
            q.update = lambda patch: escrituras.append(patch) or original_update(patch)
            return q

    repo._db = Db()
    repo.update_foto_comercio("f1", "c", {"orden": 2})
    assert escrituras == [{"orden": 2}] and "select" not in log
    log.clear(), escrituras.clear()
    repo.update_foto_comercio("f1", "c", {"url": "b"})
    assert "select" in log and escrituras == [{**VACIAS, "url": "b"}]


# ══════════════════════════════════════════ (a) el intercambio con la portada

def test_el_intercambio_vacia_el_diseno_de_la_fila_y_suelta_sus_archivos(repo, mundo):
    c = repo.comercios["com-v"]
    portada.usar_de_galeria(repo, c, "f1")
    f = _fila(repo)
    assert f["url"] == mundo["portada"] and _vacia(f)                        # la fila ahora es la portada vieja, sin diseño
    for u in (mundo["d"], mundo["dt"], mundo["p"]):
        assert not _en_disco(u), u                                             # los archivos de diseño se soltaron
    assert repo.comercios["com-v"]["portada_url"] == mundo["f1"]
    for original in (mundo["f1"], mundo["f1t"], mundo["portada"], mundo["f2"]):
        assert _en_disco(original), original                                   # ninguna foto se borra


def test_el_intercambio_sin_portada_anterior_borra_la_fila_y_suelta_su_diseno(repo, mundo):
    repo.comercios["com-v"]["portada_url"] = None
    repo.comercios["com-v"]["portada_thumb_url"] = None
    portada.usar_de_galeria(repo, repo.comercios["com-v"], "f1")
    assert [f["id"] for f in repo.comercio_fotos] == ["f2"]
    for u in (mundo["d"], mundo["dt"], mundo["p"]):
        assert not _en_disco(u)
    assert _en_disco(mundo["f1"])


def test_el_agente_no_borra_archivos_solo_vacia_las_columnas(repo, mundo):
    portada.usar_de_galeria(repo, repo.comercios["com-v"], "f1", conservar_archivos=True)
    assert _vacia(_fila(repo))
    for u in (mundo["d"], mundo["dt"], mundo["p"]):
        assert _en_disco(u), u


def test_por_el_endpoint_del_agente_solo_se_vacian_las_columnas(client, repo, mundo, agente_token):
    # el agente: vacía las columnas y no borra nada
    r = client.put("/campo/mis-comercios/com-v/portada", headers=_h(agente_token), json={"foto_id": "f1"})
    assert r.status_code == 200, r.text
    assert _vacia(_fila(repo)) and all(_en_disco(mundo[k]) for k in ("d", "dt", "p"))


def test_por_el_endpoint_admin_el_intercambio_suelta_los_archivos(client, repo, mundo, admin_token):
    r = client.put("/admin/comercio/com-v/portada", headers=_h(admin_token), json={"foto_id": "f1"})
    assert r.status_code == 200, r.text
    assert _vacia(_fila(repo)) and not any(_en_disco(mundo[k]) for k in ("d", "dt", "p"))
    assert _en_disco(mundo["f1"]) and _en_disco(mundo["portada"])


def test_si_la_portada_falla_al_intercambiar_el_diseno_vuelve_y_no_quedan_huerfanos(repo, mundo, monkeypatch):
    def falla(*a, **kw):
        raise RuntimeError("base caída")

    monkeypatch.setattr(repo, "update_comercio", falla)
    with pytest.raises(RuntimeError):
        portada.usar_de_galeria(repo, repo.comercios["com-v"], "f1")
    f = _fila(repo)
    assert f["url"] == mundo["f1"] and (f["diseno_url"], f["diseno_thumb_url"], f["diseno_propuesta_url"]) == (
        mundo["d"], mundo["dt"], mundo["p"])
    assert all(_en_disco(mundo[k]) for k in ("d", "dt", "p"))


# ══════════════════════════════════════════ (b) se borra la fila

def test_borrar_la_foto_suelta_los_disenos_y_la_original_se_va_con_la_fila(repo, mundo):
    c = repo.comercios["com-v"]
    assert fotos_galeria.borrar_foto(repo, c, _fila(repo))
    assert [f["id"] for f in repo.comercio_fotos] == ["f2"]
    for u in (mundo["d"], mundo["dt"], mundo["p"], mundo["f1"], mundo["f1t"]):
        assert not _en_disco(u), u
    assert _en_disco(mundo["f2"]) and _en_disco(mundo["portada"])           # lo de las otras filas, intacto


def test_borrar_foto_por_id_y_el_endpoint_admin(client, repo, mundo, admin_token):
    r = client.delete("/admin/comercio/com-v/fotos/f1", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert not any(_en_disco(mundo[k]) for k in ("d", "dt", "p", "f1", "f1t"))
    assert _en_disco(mundo["f2"])


def test_el_reemplazo_en_el_tope_tambien_suelta_los_disenos(repo, mundo):
    """`registrar` con `reemplaza`: entra la nueva y recién después se borra la vieja, con todo lo suyo."""
    c = repo.comercios["com-v"]
    subida = fotos_galeria.Subida(fotos=list(repo.comercio_fotos), reemplaza=_fila(repo))
    nueva = _archivo("g3.jpg", "pink")
    fotos_galeria.registrar(repo, c, subida, nueva, None)
    assert "f1" not in [f["id"] for f in repo.comercio_fotos]
    assert not any(_en_disco(mundo[k]) for k in ("d", "dt", "p", "f1"))
    assert _en_disco(nueva)


def test_el_agente_no_puede_borrar_fotos_asi_que_sus_disenos_quedan(client, repo, mundo, agente_token):
    r = client.delete("/campo/mis-comercios/com-v/fotos/f1", headers=_h(agente_token))
    assert r.status_code == 403
    assert all(_en_disco(mundo[k]) for k in ("d", "dt", "p", "f1"))


def test_soltar_disenos_solo_toca_diseno_del_propio_comercio(repo, mundo):
    guardar_foto_local("otro-local/diseno-x.jpg", b"x")
    c = {"slug": "local-v"}
    fotos_galeria.soltar_disenos(c, [mundo["f2"], mundo["portada"], f"{BASE}/otro-local/diseno-x.jpg", None, "https://otro.host/local-v/diseno-aaa.jpg"])
    assert _en_disco(mundo["f2"]) and _en_disco(mundo["portada"]) and _en_disco(f"{BASE}/otro-local/diseno-x.jpg")
    assert _en_disco(mundo["d"])                                              # de otro host: no se toca
    fotos_galeria.soltar_disenos(c, [mundo["d"], mundo["d"]])
    assert not _en_disco(mundo["d"])
    fotos_galeria.soltar_disenos(c, None)                                     # no lanza


def test_borrar_archivos_con_una_fila_sin_columnas_de_diseno_anda_como_siempre(repo, mundo):
    repo.comercio_fotos[:] = [f for f in repo.comercio_fotos if f["id"] != "f2"]       # la fila ya no está: nadie apunta el archivo
    fotos_galeria.borrar_archivos(repo.comercios["com-v"], {"url": mundo["f2"], "thumb_url": None}, repo)
    assert not _en_disco(mundo["f2"]) and _en_disco(mundo["d"])
