"""QA: portada y permisos contra Postgres + PostgREST REALES (docs/portada-y-permisos.md).

Los tests de `test_portada_y_permisos*.py` usan un FakeRepo. Acá se corre el
`SupabaseRepo` de verdad, hablándole a un PostgREST que apunta a un Postgres con
la cadena de `selfhost/postgres-init` aplicada. Prueba lo que el fake no puede:

  - el embed `rubros!comercios_rubro_id_fkey(nombre)` de `list_comercios_dados_de_baja`;
  - `update_foto_comercio` / `reactivar_comercio` / `set_estado_publicacion` con los GRANTs reales;
  - `portada.usar_de_galeria` y `portada.poner_nueva` sobre filas reales (`portada_pos` a NULL);
  - que lo que ve el público (RLS de `comercios` y `publicaciones`, vista `feed_publico`)
    cambie al dar de baja / reactivar / bajar una oferta;
  - la migración 0146 (idempotente, sin duplicar el permiso).

Se salta solo si no están estas variables (ver el comando al final):

    URUKU_PG_TEST_CONTAINER   contenedor Postgres con la cadena aplicada (ej. qa-port-pg)
    URUKU_PGREST_URL          http://127.0.0.1:3999
    URUKU_PGREST_JWT_SECRET   el PGRST_JWT_SECRET de ese PostgREST

    docker run -d --name qa-port-pg -e POSTGRES_PASSWORD=x postgres:16-alpine
    # aplicar selfhost/postgres-init/* en orden (las conocidas 0049, 0069, 0070, 0092 fallan en vanilla)
    docker exec qa-port-pg psql -U postgres -c "alter role authenticator password 'x'"
    docker run -d --name qa-port-rest --link qa-port-pg -p 127.0.0.1:3999:3000 \
        -e PGRST_DB_URI=postgres://authenticator:x@qa-port-pg:5432/postgres -e PGRST_DB_SCHEMAS=public \
        -e PGRST_DB_ANON_ROLE=anon -e PGRST_JWT_SECRET=<secreto de 32+ caracteres> postgrest/postgrest:v12.2.3
"""
import json
import os
import shutil
import subprocess
import time
import uuid
from pathlib import Path

import httpx
import jwt as pyjwt
import pytest

from app.core.config import settings
from app.db.repository import SupabaseRepo
from app.services import portada
from app.services.imagenes import guardar_foto_local

CONTENEDOR = os.environ.get("URUKU_PG_TEST_CONTAINER")
REST = os.environ.get("URUKU_PGREST_URL")
SECRETO = os.environ.get("URUKU_PGREST_JWT_SECRET")
RAIZ = Path(__file__).resolve().parents[2]
BASE = "https://api.test/fotos"

pytestmark = pytest.mark.skipif(
    not (CONTENEDOR and REST and SECRETO and shutil.which("docker")),
    reason="sin Postgres+PostgREST de Docker (URUKU_PG_TEST_CONTAINER / URUKU_PGREST_URL / URUKU_PGREST_JWT_SECRET)")


def _psql(sql: str, check=True) -> str:
    p = subprocess.run(
        ["docker", "exec", "-i", CONTENEDOR, "psql", "-U", "postgres", "-d", "postgres",
         "-v", "ON_ERROR_STOP=1", "-At", "-q", "-F", "|", "-f", "-"],
        input=sql, capture_output=True, text=True, encoding="utf-8")
    if check and p.returncode != 0:
        raise AssertionError(p.stderr)
    return p.stdout.strip()


def _jwt(rol: str) -> str:
    return pyjwt.encode({"role": rol, "exp": int(time.time()) + 600}, SECRETO, algorithm="HS256")


class _Db:
    """Lo mínimo de supabase-py que usa SupabaseRepo: `.table(nombre)` sobre PostgREST."""

    def __init__(self, url, token):
        from postgrest import SyncPostgrestClient
        self._c = SyncPostgrestClient(f"{url}", headers={"Authorization": f"Bearer {token}", "apikey": token})

    def table(self, nombre):
        return self._c.from_(nombre)


@pytest.fixture(scope="module")
def repo():
    return SupabaseRepo(_Db(REST, _jwt("service_role")))


def _publico(path: str) -> list:
    """Lo que ve un visitante anónimo (sin Authorization)."""
    r = httpx.get(f"{REST}{path}", timeout=10)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture
def datos(tmp_path, monkeypatch):
    """Un comercio de Bermejo con rubro, dos fotos en la galería y una oferta aprobada. Se limpia al final."""
    monkeypatch.setattr(settings, "fotos_dir", str(tmp_path / "fotos"))
    monkeypatch.setattr(settings, "fotos_public_base_url", BASE)
    tag = uuid.uuid4().hex[:8]
    cid, rid, pid = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    slug = f"qa-{tag}"

    def f(n):
        return f"{BASE}/{slug}/{n}"
    for n in ("A.jpg", "A_t3.jpg", "B.jpg", "B_t3.jpg", "C.jpg", "C_t3.jpg"):
        guardar_foto_local(f"{slug}/{n}", b"x")
    _psql(f"""
        insert into rubros (id, slug, nombre) values ('{rid}', 'qa-rubro-{tag}', 'Rubro QA {tag}');
        insert into comercios (id, slug, nombre, whatsapp, activo, rubro_id, ciudad_id, portada_url, portada_thumb_url, portada_pos)
          values ('{cid}', '{slug}', 'QA {tag}', '5917{int(tag, 16) % 10**7:07d}', true, '{rid}',
                  (select id from ciudades where slug = 'bermejo'), '{f("A.jpg")}', '{f("A_t3.jpg")}', 30);
        insert into comercio_fotos (id, comercio_id, url, thumb_url, orden) values
          ('{uuid.uuid4()}', '{cid}', '{f("B.jpg")}', '{f("B_t3.jpg")}', 1),
          ('{uuid.uuid4()}', '{cid}', '{f("C.jpg")}', '{f("C_t3.jpg")}', 2);
        insert into publicaciones (id, comercio_id, titulo, estado, activo, tipo)
          values ('{pid}', '{cid}', 'Oferta QA {tag}', 'aprobado', true, 'oferta');
        insert into difusion_cola (publicacion_id, destino, estado) values ('{pid}', 'facebook', 'pendiente'), ('{pid}', 'instagram', 'enviado');
    """)
    try:
        yield {"cid": cid, "rid": rid, "pid": pid, "slug": slug, "tag": tag, "url": f}
    finally:
        _psql(f"""
            delete from difusion_cola where publicacion_id = '{pid}';
            delete from publicaciones where comercio_id = '{cid}';
            delete from comercio_fotos where comercio_id = '{cid}';
            delete from comercios where id = '{cid}';
            delete from rubros where id = '{rid}';
        """, check=False)


def _galeria(repo, cid):
    return [f["url"].rsplit("/", 1)[1] for f in repo.list_fotos_comercio(cid)]


# ───────────────────────────── dados de baja / reactivar

def test_dados_de_baja_trae_rubro_y_filtra_por_ciudad(repo, datos):
    cid = datos["cid"]
    assert cid not in [i["id"] for i in repo.list_comercios_dados_de_baja(None, 500)]
    repo.desactivar_comercio(cid)
    todos = repo.list_comercios_dados_de_baja(None)
    fila = next(i for i in todos if i["id"] == cid)
    assert set(fila) == {"id", "slug", "nombre", "rubro_nombre", "portada_thumb_url", "updated_at", "baja_motivo"}
    assert fila["baja_motivo"] == "admin"
    assert fila["rubro_nombre"] == f"Rubro QA {datos['tag']}"
    assert fila["portada_thumb_url"].endswith("/A_t3.jpg")
    assert cid in [i["id"] for i in repo.list_comercios_dados_de_baja("bermejo")]
    assert cid not in [i["id"] for i in repo.list_comercios_dados_de_baja("santa-cruz")]
    assert repo.list_comercios_dados_de_baja("ciudad-que-no-existe") == []
    # Los últimos dados de baja primero.
    stamps = [i["updated_at"] for i in todos]
    assert stamps == sorted(stamps, reverse=True)


def test_reactivar_devuelve_la_fila_y_un_id_inexistente_da_vacio(repo, datos):
    cid = datos["cid"]
    repo.desactivar_comercio(cid)
    assert repo.reactivar_comercio(cid)["activo"] is True
    assert repo.reactivar_comercio(cid)["activo"] is True                   # idempotente
    assert repo.reactivar_comercio(str(uuid.uuid4())) == {}


def test_un_id_que_no_es_uuid_revienta_en_la_base_pre_existente(repo):
    """Documenta: `/admin/comercio/no-existe/...` es 404 con el FakeRepo pero la base real
    contesta 22P02 (no es uuid) y la ruta devuelve 500. Pasa igual con `get_comercio`
    de siempre; no es de este cambio."""
    from postgrest.exceptions import APIError
    with pytest.raises(APIError):
        repo.reactivar_comercio("no-existe")


def test_publico_no_ve_el_comercio_dado_de_baja_ni_sus_ofertas_y_si_al_reactivar(repo, datos):
    cid, slug = datos["cid"], datos["slug"]
    visible = lambda: _publico(f"/comercios?id=eq.{cid}&select=id")
    en_feed = lambda: _publico(f"/feed_publico?comercio_id=eq.{cid}&select=id")
    assert len(visible()) == 1 and len(en_feed()) == 1
    repo.desactivar_comercio(cid)
    assert visible() == [] and en_feed() == []
    repo.reactivar_comercio(cid)
    assert len(visible()) == 1 and len(en_feed()) == 1


# ───────────────────────────── bajar una oferta aprobada (criterio 7)

def test_bajar_una_oferta_la_saca_del_feed_y_de_la_lectura_publica(repo, datos):
    cid, pid = datos["cid"], datos["pid"]
    assert len(_publico(f"/feed_publico?id=eq.{pid}&select=id")) == 1
    assert len(_publico(f"/publicaciones?id=eq.{pid}&select=id")) == 1
    fila = repo.set_estado_publicacion(pid, "rechazado", "Ya no hay stock", "pub@uruku.bo")
    assert fila["estado"] == "rechazado" and fila["motivo_moderacion"] == "Ya no hay stock"
    assert _publico(f"/feed_publico?id=eq.{pid}&select=id") == []
    assert _publico(f"/publicaciones?id=eq.{pid}&select=id") == []
    # Y lo que esperaba salir en las redes se descarta, no lo ya enviado.
    assert repo.descartar_difusion_de(pid, "bajada") == 1
    estados = _psql(f"select destino||':'||estado from difusion_cola where publicacion_id='{pid}' order by destino")
    assert estados.splitlines() == ["facebook:omitido", "instagram:enviado"]
    # Volver a aprobar la republica (y no pasa nada raro con las columnas de moderación).
    repo.set_estado_publicacion(pid, "aprobado", None, "pub@uruku.bo")
    assert len(_publico(f"/feed_publico?id=eq.{pid}&select=id")) == 1


# ───────────────────────────── portada sobre filas reales

def test_usar_de_galeria_intercambia_con_el_repo_real(repo, datos):
    cid = datos["cid"]
    comercio = repo.get_comercio(cid)
    foto_b = next(f for f in repo.list_fotos_comercio(cid) if f["url"].endswith("/B.jpg"))
    actualizado = portada.usar_de_galeria(repo, comercio, foto_b["id"])
    assert actualizado["portada_url"].endswith("/B.jpg") and actualizado["portada_thumb_url"].endswith("/B_t3.jpg")
    assert actualizado["portada_pos"] is None                               # el NULL llegó a la base
    assert _galeria(repo, cid) == ["A.jpg", "C.jpg"]                        # A ocupa el lugar de B
    fila = repo.list_fotos_comercio(cid)[0]
    assert fila["id"] == foto_b["id"] and fila["thumb_url"].endswith("/A_t3.jpg")
    for n in ("A", "B", "C"):
        assert (Path(settings.fotos_dir) / datos["slug"] / f"{n}.jpg").exists()


def test_usar_de_galeria_rechaza_la_foto_de_otro_comercio_con_el_repo_real(repo, datos):
    cid = datos["cid"]
    otro = str(uuid.uuid4())
    _psql(f"""insert into comercios (id, slug, nombre, whatsapp) values ('{otro}', 'qa-otro-{datos['tag']}', 'Otro', '59170000999');
              insert into comercio_fotos (id, comercio_id, url, orden) values ('{uuid.uuid4()}', '{otro}', '{BASE}/zz/Z.jpg', 0);""")
    try:
        ajena = repo.list_fotos_comercio(otro)[0]["id"]
        with pytest.raises(Exception) as e:
            portada.usar_de_galeria(repo, repo.get_comercio(cid), ajena)
        assert getattr(e.value, "status_code", None) == 404
        assert repo.get_comercio(cid)["portada_url"].endswith("/A.jpg")
        # update_foto_comercio no toca filas de otro comercio aunque se le pase el id.
        assert repo.update_foto_comercio(ajena, cid, {"url": "https://hack"}) is None
        assert repo.list_fotos_comercio(otro)[0]["url"].endswith("/Z.jpg")
    finally:
        _psql(f"delete from comercio_fotos where comercio_id='{otro}'; delete from comercios where id='{otro}'", check=False)


def test_poner_nueva_con_el_repo_real_reinicia_el_recorte_y_borra_solo_lo_que_nadie_usa(repo, datos):
    cid, slug = datos["cid"], datos["slug"]
    nueva = guardar_foto_local(f"{slug}/N.jpg", b"n")
    comercio = repo.get_comercio(cid)
    assert comercio["portada_pos"] == 30
    out = portada.poner_nueva(repo, comercio, f"{BASE}/{slug}/N.jpg", f"{BASE}/{slug}/N_t3.jpg")
    assert out["portada_url"].endswith("/N.jpg") and out["portada_pos"] is None
    assert not (Path(settings.fotos_dir) / slug / "A.jpg").exists()
    assert not (Path(settings.fotos_dir) / slug / "A_t3.jpg").exists()
    assert (Path(settings.fotos_dir) / slug / "B.jpg").exists()             # la galería sigue
    assert _galeria(repo, cid) == ["B.jpg", "C.jpg"]


def test_poner_nueva_no_borra_el_archivo_que_una_publicacion_usa_con_el_repo_real(repo, datos):
    cid, slug = datos["cid"], datos["slug"]
    _psql(f"update publicaciones set imagen_url = '{BASE}/{slug}/A.jpg' where id = '{datos['pid']}'")
    portada.poner_nueva(repo, repo.get_comercio(cid), f"{BASE}/{slug}/N.jpg", None)
    assert (Path(settings.fotos_dir) / slug / "A.jpg").exists()
    assert not (Path(settings.fotos_dir) / slug / "A_t3.jpg").exists()


# ───────────────────────────── migración 0146

def test_0146_en_postgres_real_es_idempotente_y_deja_una_sola_vez_el_permiso():
    sql = (RAIZ / "selfhost" / "postgres-init" / "0146_publicador_edita_fichas.sql").read_text(encoding="utf-8")
    previo = _psql("select permisos::text from roles where slug='publicador'")
    try:
        _psql("update roles set permisos = '{contenido,moderar}', descripcion = 'Carga la cotización, el estado del paso y los videos.' where slug='publicador'")
        _psql(sql)
        _psql(sql)
        fila = _psql("select (select count(*) from unnest(permisos) p where p='comercios.editar'), permisos::text, descripcion from roles where slug='publicador'")
        n, permisos, desc = fila.split("|", 2)
        assert n == "1" and permisos == "{contenido,moderar,comercios.editar}"
        assert desc == "Carga la cotización, el estado del paso y los videos, y corrige fichas."
        # Los demás roles no se tocan.
        assert _psql("select permisos::text from roles where slug='agente'") == "{comercios.cargar}"
        assert "comercios.editar" not in _psql("select permisos::text from roles where slug='agente'")
    finally:
        _psql(f"update roles set permisos = '{previo}' where slug='publicador'", check=False)


# ───────────────────────────── «Publicadas» del panel (criterio 7)

def test_una_oferta_publicada_vieja_se_puede_encontrar_para_bajarla(repo, datos):
    cid = datos["cid"]
    _psql(f"""
        insert into publicaciones (comercio_id, titulo, estado, activo, tipo, created_at)
        select '{cid}', 'Vieja ' || g, 'aprobado', true, 'oferta', now() - (g || ' hours')::interval
          from generate_series(1, 230) g;
    """)
    # Ronda 2: «Publicadas» pagina de a 100 con el total real y busca por título o comercio.
    items, total = repo.buscar_publicaciones("aprobado", None, 0, 100)
    assert len(items) == 100 and total >= 231
    ultima, total2 = repo.buscar_publicaciones("aprobado", None, 200, 100)
    assert "Vieja 230" in [p["titulo"] for p in ultima] and total2 == total
    por_titulo, n = repo.buscar_publicaciones("aprobado", "Vieja 230", 0, 100)
    assert [p["titulo"] for p in por_titulo] == ["Vieja 230"] and n == 1
    por_comercio, n2 = repo.buscar_publicaciones("aprobado", f"QA {datos['tag']}", 0, 100)
    assert n2 == 231 and len(por_comercio) == 100             # 230 + la oferta del fixture
