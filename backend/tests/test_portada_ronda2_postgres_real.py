"""Ronda 2 contra Postgres + PostgREST REALES: baja_motivo, comercios.cuenta, defensas (0147).

Usa el mismo entorno y los mismos fixtures que `test_portada_postgres_real.py` (ver el
docstring de ese archivo para levantar el Postgres y PostgREST de Docker). Se salta solo
si no están las variables URUKU_PG_TEST_CONTAINER / URUKU_PGREST_URL / URUKU_PGREST_JWT_SECRET.
"""
import subprocess
import uuid
from pathlib import Path

import pytest

from app.core.config import settings
from app.services import fotos_galeria
from app.services.imagenes import guardar_foto_local
# Los fixtures (`repo`, `datos`) y el salto se reusan del archivo de la ronda 1.
from tests.test_portada_postgres_real import (  # noqa: F401
    BASE, CONTENEDOR, RAIZ, _psql, datos, pytestmark, repo,
)


def _fila(cid):
    return _psql(f"select activo || '|' || coalesce(baja_motivo, '-') || '|' || suspendido from comercios where id = '{cid}'")


def test_baja_motivo_de_ida_y_vuelta_con_el_repo_real(repo, datos):
    cid = datos["cid"]
    assert _fila(cid) == "true|-|false"
    repo.desactivar_comercio(cid)
    assert _fila(cid) == "false|admin|false"
    fila = next(i for i in repo.list_comercios_dados_de_baja(None) if i["id"] == cid)
    assert fila["baja_motivo"] == "admin"
    repo.reactivar_comercio(cid)
    assert _fila(cid) == "true|-|false"
    assert cid not in [i["id"] for i in repo.list_comercios_dados_de_baja(None)]


def test_dados_de_baja_lista_admin_y_sin_motivo_pero_no_vencido_ni_borrador(repo, datos):
    cid = datos["cid"]
    for motivo, esta in (("admin", True), ("null", True), ("vencido", False), ("borrador", False)):
        valor = "null" if motivo == "null" else f"'{motivo}'"
        _psql(f"update comercios set activo = false, baja_motivo = {valor} where id = '{cid}'")
        lista = repo.list_comercios_dados_de_baja(None)
        item = next((i for i in lista if i["id"] == cid), None)
        assert (item is not None) is esta, motivo
        if esta:
            assert item["baja_motivo"] == (None if motivo == "null" else motivo)


def test_el_job_de_vencimientos_marca_vencido_con_el_repo_real(repo, datos):
    cid = datos["cid"]
    _psql(f"update comercios set paga_hasta = current_date - 4000, plan_cortesia = false where id = '{cid}'")
    assert repo.ocultar_comercios_vencidos(dias=3990) >= 1          # sólo alcanza a lo más viejo que 3990 días
    assert _fila(cid) == "false|vencido|false"
    assert cid not in [i["id"] for i in repo.list_comercios_dados_de_baja(None)]


def test_activar_y_pagar_reactivan_al_vencido_pero_no_al_dado_de_baja_por_el_admin(repo, datos):
    cid = datos["cid"]
    pago = {"monto": 50, "meses": 1, "registrado_por": "admin@x.com"}
    _psql(f"update comercios set activo = false, baja_motivo = 'admin', suspendido = true where id = '{cid}'")
    repo.activar_comercio(cid)
    assert _fila(cid) == "false|admin|false"                         # sólo se levantó la suspensión
    repo.registrar_pago(cid, dict(pago))
    assert _fila(cid) == "false|admin|false"
    assert _psql(f"select paga_hasta is not null from comercios where id = '{cid}'") == "t"     # el pago se registró igual
    _psql(f"update comercios set baja_motivo = 'vencido', suspendido = true where id = '{cid}'")
    repo.activar_comercio(cid)
    assert _fila(cid) == "true|-|false"
    _psql(f"update comercios set activo = false, baja_motivo = 'vencido' where id = '{cid}'")
    repo.registrar_pago(cid, dict(pago))
    assert _fila(cid) == "true|-|false"
    _psql(f"update comercios set activo = false where id = '{cid}'")          # baja vieja sin motivo
    repo.activar_comercio(cid)
    assert _fila(cid) == "false|-|false"


def test_un_alta_inactiva_nace_borrador_con_el_repo_real(repo, datos):
    nuevo = repo.crear_comercio({"slug": f"qa-bor-{datos['tag']}", "nombre": "Borrador QA",
                                 "whatsapp": "59170001234", "activo": False})
    sano = None
    try:
        assert nuevo["baja_motivo"] == "borrador" and nuevo["activo"] is False
        sano = repo.crear_comercio({"slug": f"qa-ok-{datos['tag']}", "nombre": "Sano QA", "whatsapp": "59170001235"})
        assert sano["baja_motivo"] is None and sano["activo"] is True
    finally:
        for c in (nuevo, sano):
            if c:
                _psql(f"delete from comercios where id = '{c['id']}'", check=False)


def test_get_comercio_por_grupo_ignora_inactivos_con_el_repo_real(repo, datos):
    cid, jid = datos["cid"], f"qa{datos['tag']}@g.us"
    _psql(f"insert into comercio_wa_grupos (grupo_jid, comercio_id, origen) values ('{jid}', '{cid}', 'admin')")
    try:
        assert repo.get_comercio_por_grupo(jid)["id"] == cid
        repo.desactivar_comercio(cid)
        assert repo.get_comercio_por_grupo(jid) is None
        assert repo.get_comercio_por_grupo(jid, incluir_inactivos=True)["id"] == cid
        assert repo.get_comercio_por_grupo("no-existe@g.us") is None
    finally:
        _psql(f"delete from comercio_wa_grupos where grupo_jid = '{jid}'", check=False)


def test_foto_en_uso_por_comercios_con_el_repo_real(repo, datos):
    f = datos["url"]
    assert repo.foto_en_uso_por_comercios(f("A.jpg")) and repo.foto_en_uso_por_comercios(f("A_t3.jpg"))     # portada
    assert repo.foto_en_uso_por_comercios(f("B.jpg")) and repo.foto_en_uso_por_comercios(f("C_t3.jpg"))     # galería
    assert not repo.foto_en_uso_por_comercios(f("Z.jpg")) and not repo.foto_en_uso_por_comercios("")
    repo.desactivar_comercio(datos["cid"])
    assert repo.foto_en_uso_por_comercios(f("A.jpg"))                  # un comercio de baja se puede reactivar


def test_borrar_archivos_con_el_repo_real_respeta_la_galeria_y_la_portada(repo, datos):
    cid, slug = datos["cid"], datos["slug"]
    comercio = repo.get_comercio(cid)
    otro = {**comercio, "id": str(uuid.uuid4()), "portada_url": None, "portada_thumb_url": None}
    # Archivos que usan la portada (A) y la galería (B): no se borran aunque se pida.
    for n in ("A.jpg", "B.jpg"):
        fotos_galeria.borrar_archivos(otro, {"url": f"{BASE}/{slug}/{n}", "thumb_url": None}, repo)
        assert (Path(settings.fotos_dir) / slug / n).exists(), n
    guardar_foto_local(f"{slug}/Libre.jpg", b"x")
    fotos_galeria.borrar_archivos(comercio, {"url": f"{BASE}/{slug}/Libre.jpg", "thumb_url": None}, repo)
    assert not (Path(settings.fotos_dir) / slug / "Libre.jpg").exists()


def test_publicadas_busca_por_nombre_de_comercio_con_el_repo_real(repo, datos):
    items, total = repo.buscar_publicaciones("aprobado", f"QA {datos['tag']}", 0, 100)
    assert total == 1 and [p["id"] for p in items] == [datos["pid"]]
    assert items[0]["comercios"]["nombre"] == f"QA {datos['tag']}"
    # No distingue mayúsculas y no se rompe con la sintaxis de PostgREST.
    assert repo.buscar_publicaciones("aprobado", f"oferta qa {datos['tag']}".upper(), 0, 100)[1] == 1
    for raro in ("a,b", "x)", "(", '"', "%", "*", "\\"):
        repo.buscar_publicaciones("aprobado", raro, 0, 100)
    assert repo.buscar_publicaciones("aprobado", "zzz-no-esta", 0, 100) == ([], 0)
    assert repo.buscar_publicaciones("rechazado", f"QA {datos['tag']}", 0, 100) == ([], 0)


def test_0147_en_postgres_real_es_idempotente_clasifica_las_bajas_y_no_prende_roles_vaciados():
    sql = (RAIZ / "selfhost" / "postgres-init" / "0147_cuenta_y_baja_motivo.sql").read_text(encoding="utf-8")
    tag = uuid.uuid4().hex[:8]
    n = int(tag, 16) % 10**6
    ids = {k: str(uuid.uuid4()) for k in ("borrador", "vencido", "cortesia", "admin")}
    lista = ", ".join(f"'{i}'" for i in ids.values())
    previo = _psql("select permisos::text from roles where slug='moderador'")
    try:
        _psql(f"""
            insert into comercios (id, slug, nombre, whatsapp, activo, wa_jid, paga_hasta, plan_cortesia) values
              ('{ids['borrador']}', 'comercio-{n:06d}', 'Comercio 4242', '5919{n:06d}', false, '591999@c.us', null, false),
              ('{ids['vencido']}', 'qa-venc-{tag}', 'Vencido QA', '5918{n:06d}', false, null, current_date - 100, false),
              ('{ids['cortesia']}', 'qa-cort-{tag}', 'Cortesía QA', '5917{n:06d}', false, null, current_date - 100, true),
              ('{ids['admin']}', 'qa-adm-{tag}', 'Admin QA', '5916{n:06d}', false, null, null, false);
            update comercios set baja_motivo = null where id in ({lista});
            update roles set permisos = '{{moderar,comercios.editar}}' where slug = 'moderador';
        """)
        _psql(sql)
        _psql(sql)
        motivos = dict(l.split("|") for l in _psql(
            f"select id || '|' || coalesce(baja_motivo, '-') from comercios where id in ({lista})").splitlines())
        assert motivos[ids["borrador"]] == "borrador" and motivos[ids["vencido"]] == "vencido"
        assert motivos[ids["cortesia"]] == "-" and motivos[ids["admin"]] == "-"        # no se adivina
        assert _psql("select permisos::text from roles where slug='moderador'") == "{moderar,comercios.editar,comercios.cuenta}"
        # Un rol vaciado a propósito no se vuelve a encender; el publicador no lo recibe.
        _psql("update roles set permisos = '{}' where slug = 'moderador'")
        _psql(sql)
        assert _psql("select permisos::text from roles where slug='moderador'") == "{}"
        assert "comercios.cuenta" not in _psql("select permisos::text from roles where slug='publicador'")
        # La columna es privada para anon (regla 11) y respeta el check.
        assert _psql("select count(*) from information_schema.column_privileges where table_name='comercios' "
                     "and column_name='baja_motivo' and grantee in ('anon','authenticated')") == "0"
        r = subprocess.run(["docker", "exec", "-i", CONTENEDOR, "psql", "-U", "postgres", "-d", "postgres", "-At", "-c",
                            f"update comercios set baja_motivo = 'otro' where id = '{ids['admin']}'"],
                           capture_output=True, text=True, encoding="utf-8")
        assert "comercios_baja_motivo_check" in r.stderr
    finally:
        _psql(f"delete from comercios where id in ({lista})", check=False)
        _psql(f"update roles set permisos = '{previo}' where slug = 'moderador'", check=False)
