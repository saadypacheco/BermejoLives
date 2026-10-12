"""Columnas públicas de `comercios` (migración 0145, docs/fotos-por-plan.md parte B).

Desde la 0002 anon tenía `grant select on comercios` de tabla entera: cualquiera
podía leer `plan_cortesia`, `paga_hasta`, `cargado_por` y `capturado_en`. La 0145
pasa a `grant select (columnas)`. Con eso, PostgREST falla (42501) todo `select=*`
sobre la tabla: por eso el frontend tiene que pedir columnas explícitas.

Qué se prueba:
- La 0145 es idéntica en las dos carpetas, su lista NO incluye las privadas, cubre
  TODAS las demás columnas que hoy existen en las migraciones (si alguien agrega una
  columna a `comercios`, este test lo obliga a decidir: pública o privada) y es
  idempotente.
- Ningún `select` del frontend con el cliente anon (los archivos que importan
  `@/lib/supabase`) pide `*` sobre `comercios`, ni usa una columna privada, ni una
  que la 0145 no dé.
- Contra un Postgres real de Docker (opcional, variable `URUKU_PG_TEST_CONTAINER`):
  como anon, las privadas dan «permission denied» y las públicas andan.
"""
import os
import re
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
PRIVADAS = ("plan_cortesia", "paga_hasta", "cargado_por", "capturado_en")
# Otras que a propósito NO se dan (la 0145 lo explica): datos internos.
# `baja_motivo` (0147): por qué está dado de baja un comercio; dato interno, nace privada (regla 11).
PRIVADAS_EXTRA = ("fotos_extra", "wa_jid", "rubro_revisado_por", "baja_motivo", "codigo")
NO_VAN_EN_LA_LISTA = PRIVADAS + PRIVADAS_EXTRA
# `codigo` (URUKU-XXXX) estaba en la lista de la 0145 (la ficha pública lo leía). La
# 0148 (docs/clave-automatica.md) se lo quita a anon: desde ahí es privada. La 0145 ya
# está aplicada y no se toca, así que su lista conserva `codigo` y se descuenta acá.
CERRADAS_POR_0148 = ("codigo",)
NO_VAN_EN_LA_0145 = tuple(c for c in NO_VAN_EN_LA_LISTA if c not in CERRADAS_POR_0148)


def _0145(carpeta="supabase/migrations") -> str:
    return (RAIZ / carpeta / "0145_comercios_columnas_publicas.sql").read_text(encoding="utf-8")


def _0148(carpeta="supabase/migrations") -> str:
    return (RAIZ / carpeta / "0148_codigo_solo_admin.sql").read_text(encoding="utf-8")


def _sin_comentarios_sql(sql: str) -> str:
    return "\n".join(l for l in sql.splitlines() if not l.lstrip().startswith("--"))


def _columnas_dadas() -> list[str]:
    """La lista que da la 0145, tal cual está en el archivo (incluye `codigo`)."""
    sql = _sin_comentarios_sql(_0145())
    m = re.search(r"grant select \((.*?)\) on public\.comercios to anon, authenticated;", sql, re.S)
    assert m, "la 0145 no tiene el grant select (columnas)"
    return [c.strip() for c in m.group(1).split(",") if c.strip()]


def _columnas_publicas() -> list[str]:
    """Lo que anon puede leer HOY: la lista de la 0145 menos lo que cierra la 0148."""
    return [c for c in _columnas_dadas() if c not in CERRADAS_POR_0148]


# ───────────────────────────────────────────────────── la migración 0145

def test_la_0145_esta_igual_en_supabase_y_en_selfhost():
    a = (RAIZ / "supabase/migrations/0145_comercios_columnas_publicas.sql").read_bytes()
    b = (RAIZ / "selfhost/postgres-init/0145_comercios_columnas_publicas.sql").read_bytes()
    assert a == b and a


def test_la_0145_no_da_las_columnas_privadas():
    dadas = _columnas_dadas()
    for privada in NO_VAN_EN_LA_0145:
        assert privada not in dadas, privada
    # Ni siquiera nombradas en un grant: sólo aparecen en comentarios y en la comprobación.
    sql = _sin_comentarios_sql(_0145())
    grants = re.findall(r"grant[^;]*;", sql, re.I)
    for g in grants:
        for privada in NO_VAN_EN_LA_0145:
            assert privada not in g, (privada, g)
    assert len(dadas) == len(set(dadas)), "columnas repetidas en el grant"


def test_la_0145_quita_el_grant_de_tabla_y_es_idempotente():
    sql = _sin_comentarios_sql(_0145())
    assert "revoke select on public.comercios from anon, authenticated;" in sql
    # El revoke va antes del grant por columnas (el revoke de tabla borra también los de columna).
    assert sql.index("revoke select on public.comercios") < sql.index("grant select (")
    assert "grant all on public.comercios to service_role;" in sql
    assert "begin;" in sql and "commit;" in sql          # todo o nada
    assert sql.index("begin;") < sql.index("revoke select") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    assert not re.search(r"create table(?! if not exists)", sql)
    # Nunca un grant de tabla entera a anon.
    assert not re.search(r"grant\s+select\s+on\s+(public\.)?comercios\s+to\s+[^;]*anon", sql, re.I)


def test_la_0145_incluye_lo_que_usan_la_ficha_el_buscador_y_el_mapa():
    dadas = set(_columnas_dadas())
    # Lo imprescindible: filtros (activo, suspendido, ...), la ficha, el mapa, el índice de búsqueda.
    for col in ("id", "slug", "nombre", "activo", "suspendido", "plan", "verificado", "destacado",
                "horario", "horario_estimado", "lat", "lng", "rubro_id", "ciudad_id", "lugar_id",
                "portada_url", "portada_thumb_url", "whatsapp", "busqueda", "codigo", "created_at",
                "contacto_ok", "contacto_no", "tiene_pasero", "talles_especiales", "canal_wa_url",
                "catalogo_url", "calle", "prod_obs_human", "prod_det_ia", "subcategoria"):
        assert col in dadas, col


def _columnas_de_comercios_en_las_migraciones() -> set[str]:
    """Las columnas de `comercios` según las migraciones, en orden (create table de la
    0001 + cada `alter table comercios add/drop column`)."""
    cols: set[str] = set()
    carpeta = RAIZ / "supabase/migrations"
    init = (carpeta / "0001_init.sql").read_text(encoding="utf-8")
    m = re.search(r"create table(?: if not exists)? (?:public\.)?comercios\s*\((.*?)\n\);", init, re.S | re.I)
    assert m, "no encontré el create table comercios en la 0001"
    for linea in m.group(1).splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("--") or re.match(r"(primary|unique|constraint|check|foreign)\b", linea, re.I):
            continue
        cols.add(linea.split()[0].strip('",'))
    for f in sorted(carpeta.glob("*.sql")):
        sql = _sin_comentarios_sql(f.read_text(encoding="utf-8"))
        for alt in re.finditer(r"alter\s+table\s+(?:if exists\s+)?(?:only\s+)?(?:public\.)?comercios\b(.*?);", sql, re.S | re.I):
            cuerpo = alt.group(1)
            for add in re.finditer(r"\badd\s+column\s+(?:if not exists\s+)?(\w+)", cuerpo, re.I):
                cols.add(add.group(1))
            for ren in re.finditer(r"\brename\s+(?:column\s+)?(\w+)\s+to\s+(\w+)", cuerpo, re.I):
                cols.discard(ren.group(1))
                cols.add(ren.group(2))
            for drop in re.finditer(r"\bdrop\s+column\s+(?:if exists\s+)?(\w+)", cuerpo, re.I):
                cols.discard(drop.group(1))
    return cols


def test_la_0145_cubre_todas_las_columnas_de_comercios_menos_las_privadas():
    """Si alguien agrega una columna a `comercios` (alter table ... add column), este
    test falla hasta que decida: darla a anon en una migración y listarla acá, o
    sumarla a las privadas. Nace PRIVADA en la base; esto evita que se olvide."""
    existentes = _columnas_de_comercios_en_las_migraciones()
    dadas = set(_columnas_dadas())
    assert "plan_cortesia" in existentes and "paga_hasta" in existentes     # el parseo ve todo
    assert dadas <= existentes, f"la 0145 da columnas que no existen: {sorted(dadas - existentes)}"
    faltan = existentes - dadas - set(NO_VAN_EN_LA_LISTA)
    assert not faltan, f"columnas de comercios sin decidir (¿públicas? ¿privadas?): {sorted(faltan)}"


# ───────────────────────────────────────────────────── el frontend, con anon

FRONT = RAIZ / "frontend"


def _archivos_anon() -> list[Path]:
    """Los archivos del frontend que hablan con la base con el cliente anon."""
    salida = []
    for ext in ("*.ts", "*.tsx"):
        for f in FRONT.rglob(ext):
            partes = set(f.relative_to(FRONT).parts)
            if partes & {"node_modules", ".next", "out"}:
                continue
            texto = f.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"""from\s+["']@/lib/supabase["']|from\s+["']\./supabase["']""", texto) \
               and re.search(r"supabase\s*\.\s*(from|rpc)\b|supabase\s*\n\s*\.from", texto):
                salida.append(f)
    return salida


def _args_de_select(texto: str, desde: int) -> str:
    """Los argumentos de un `.select(` que abre en `desde` (justo después del '(')."""
    nivel, i = 1, desde
    while i < len(texto) and nivel:
        c = texto[i]
        if c in "\"'`":                      # salta strings
            q, i = c, i + 1
            while i < len(texto) and texto[i] != q:
                i += 2 if texto[i] == "\\" else 1
        elif c == "(":
            nivel += 1
        elif c == ")":
            nivel -= 1
        i += 1
    return texto[desde:i - 1]


def _primer_argumento(args: str) -> str:
    nivel, i = 0, 0
    while i < len(args):
        c = args[i]
        if c in "\"'`":                      # salta strings
            q, i = c, i + 1
            while i < len(args) and args[i] != q:
                i += 2 if args[i] == "\\" else 1
        elif c in "([{":
            nivel += 1
        elif c in ")]}":
            nivel -= 1
        elif c == "," and nivel == 0:
            return args[:i].strip()
        i += 1
    return args.strip()


def _selects_sobre_comercios(texto: str) -> list[str]:
    """El primer argumento de cada `.select(...)` que sigue a `.from("comercios")`."""
    out = []
    for m in re.finditer(r"""\.from\(\s*["']comercios["']\s*\)""", texto):
        resto = texto[m.end():]
        s = re.match(r"(?:\s|//[^\n]*\n)*\.select\(", resto)
        if s:
            out.append(_primer_argumento(_args_de_select(resto, s.end())))
    return out


def test_el_buscador_de_archivos_anon_encuentra_los_que_son():
    nombres = {f.name for f in _archivos_anon()}
    assert "data.ts" in nombres and "sitemap.ts" in nombres


def test_ningun_select_anon_sobre_comercios_usa_asterisco_ni_columnas_privadas_ni_no_dadas():
    dadas = set(_columnas_publicas())
    vistos = 0
    for f in _archivos_anon():
        texto = f.read_text(encoding="utf-8")
        for arg in _selects_sobre_comercios(texto):
            vistos += 1
            donde = f"{f.relative_to(RAIZ)}: select({arg})"
            assert arg != "", f"select() sin columnas = '*': {donde}"
            if arg == "COLUMNAS_COMERCIO":
                continue                      # su lista se prueba más abajo
            assert arg[0] in "\"'`", f"select con algo que no puedo revisar: {donde}"
            lista = arg[1:-1]
            assert "${" not in lista, f"select armado en runtime: {donde}"
            assert "*" not in lista, f"select * sobre comercios con anon: {donde}"
            for col in (c.strip() for c in lista.split(",")):
                assert col in dadas, f"columna sin permiso para anon ({col}) en {donde}"
    assert vistos >= 4          # data.ts (varios) + sitemap


def test_ningun_embebido_de_comercios_pide_asterisco_o_privadas():
    """`lugares(... comercios(*))`, `comercios!inner(*)`, etc.: sólo se permite `comercios(count)`."""
    for f in _archivos_anon():
        texto = f.read_text(encoding="utf-8")
        for m in re.finditer(r"""["'`][^"'`]*\bcomercios(?:![\w]+)?\s*\(([^)]*)\)""", texto):
            interior = m.group(1).strip()
            donde = f"{f.relative_to(RAIZ)}: {m.group(0)[:100]}"
            assert interior != "*" and "*" not in interior, f"embebido con *: {donde}"
            for privada in NO_VAN_EN_LA_LISTA:
                assert privada not in interior, f"embebido con columna privada: {donde}"


def test_el_frontend_anon_no_nombra_columnas_privadas_en_selects_ni_filtros():
    privadas = "|".join(NO_VAN_EN_LA_LISTA)
    for f in _archivos_anon():
        texto = f.read_text(encoding="utf-8")
        for m in re.finditer(r"\.select\(", texto):
            args = _args_de_select(texto, m.end())
            assert not re.search(rf"\b({privadas})\b", args), f"{f.relative_to(RAIZ)}: select con privada: {args[:120]}"
        filtro = re.search(rf"""\.(eq|neq|gt|gte|lt|lte|is|in|not|order|ilike|like|filter)\(\s*["']({privadas})["']""", texto)
        assert not filtro, f"{f.relative_to(RAIZ)}: filtra u ordena por una columna privada: {filtro.group(0)}"


def test_columnas_comercio_del_frontend_estan_todas_dadas():
    texto = (FRONT / "lib/data.ts").read_text(encoding="utf-8")
    m = re.search(r"export const COLUMNAS_COMERCIO = \[(.*?)\]\.join", texto, re.S)
    assert m, "lib/data.ts tiene que exportar COLUMNAS_COMERCIO"
    cols = re.findall(r'"(\w+)"', m.group(1))
    assert len(cols) == len(set(cols)), "columnas repetidas en COLUMNAS_COMERCIO"
    dadas = set(_columnas_publicas())
    assert set(cols) <= dadas, f"COLUMNAS_COMERCIO pide columnas sin permiso: {sorted(set(cols) - dadas)}"
    assert "codigo" not in cols          # 0148: el código es sólo del admin
    # Lo que lee la ficha pública.
    for col in ("id", "slug", "nombre", "plan", "horario", "horario_estimado", "rubro_id", "ciudad_id",
                "calle", "tiene_pasero", "talles_especiales", "canal_wa_url", "catalogo_url"):
        assert col in cols, col


def test_la_ficha_y_las_pantallas_publicas_piden_comercio_con_la_lista_explicita():
    texto = (FRONT / "lib/data.ts").read_text(encoding="utf-8")
    assert 'from("comercios").select(COLUMNAS_COMERCIO).eq("slug", slug)' in texto
    assert 'from("comercios").select(COLUMNAS_COMERCIO).eq("destacado", true)' in texto
    # El mapa ya no lee paga_hasta.
    assert "paga_hasta" not in re.sub(r"/\*.*?\*/", "", texto, flags=re.S).replace("`paga_hasta`", "")


# ───────────────────────────────────────────────────── contra un Postgres real (Docker)
# Opcional: URUKU_PG_TEST_CONTAINER=<contenedor postgres>. Arma una tabla `comercios` con
# TODAS las columnas (como texto), le aplica el grant de tabla viejo y corre la 0145 tal
# cual está en el archivo.

@pytest.fixture(scope="module")
def pg():
    contenedor = os.environ.get("URUKU_PG_TEST_CONTAINER")
    if not contenedor or not shutil.which("docker"):
        pytest.skip("sin Postgres de Docker (URUKU_PG_TEST_CONTAINER)")
    base = "t0145_" + uuid.uuid4().hex[:8]

    def psql(sql, db=base, check=True, rol=None):
        if rol:
            sql = f"set role {rol};\n{sql}"
        p = subprocess.run(
            ["docker", "exec", "-i", contenedor, "psql", "-U", "postgres", "-d", db,
             "-v", "ON_ERROR_STOP=1", "-At", "-q", "-F", "|", "-f", "-"],
            input=sql, capture_output=True, text=True, encoding="utf-8")
        if check and p.returncode != 0:
            raise AssertionError(p.stderr)
        return p

    psql(f'create database "{base}"', db="postgres")
    try:
        todas = sorted(_columnas_de_comercios_en_las_migraciones() - {"id", "activo"})
        columnas = ", ".join(f'"{c}" text' for c in todas)
        psql(f"""
            do $$ begin
              begin create role anon nologin; exception when duplicate_object then null; end;
              begin create role authenticated nologin; exception when duplicate_object then null; end;
              begin create role service_role nologin; exception when duplicate_object then null; end;
            end $$;
            grant usage on schema public to anon, authenticated, service_role;
            create table comercios (id uuid primary key default gen_random_uuid(), activo boolean not null default true, {columnas});
            insert into comercios (slug, nombre, plan_cortesia, paga_hasta, cargado_por, capturado_en)
              values ('x', 'X', 'true', '2026-12-31', 'agente@uruku.bo', '2026-10-01T10:00:00Z');
            -- Como en 0002: tabla entera.
            grant select on comercios to anon, authenticated;
            grant all on comercios to service_role;
        """)
        yield psql
    finally:
        psql(f'drop database if exists "{base}" with (force)', db="postgres", check=False)


def test_antes_de_la_0145_anon_veia_todo(pg):
    pg("select plan_cortesia, paga_hasta, cargado_por, capturado_en from comercios;", rol="anon")


def test_0145_en_postgres_cierra_las_privadas_y_deja_las_publicas(pg):
    pg(_0145())
    for rol in ("anon", "authenticated"):
        for privada in NO_VAN_EN_LA_0145:
            r = pg(f"select {privada} from comercios;", rol=rol, check=False)
            assert r.returncode != 0 and "permission denied" in r.stderr, (rol, privada, r.stderr)
        # select * también (PostgREST lo expande y falla entero: por eso las columnas explícitas).
        r = pg("select * from comercios;", rol=rol, check=False)
        assert r.returncode != 0 and "permission denied" in r.stderr
        # Las que usan la ficha, el buscador y el mapa.
        cols = ", ".join(_columnas_dadas())
        r = pg(f"select {cols} from comercios where activo;", rol=rol)     # tras la 0145 sola, `codigo` todavía se lee
        assert r.stdout.count("\n") == 1
    # Los filtros por columna privada también fallan.
    r = pg("select id from comercios where paga_hasta is not null;", rol="anon", check=False)
    assert r.returncode != 0 and "permission denied" in r.stderr
    # El backend sigue viendo todo.
    assert pg("select plan_cortesia, paga_hasta, cargado_por, capturado_en from comercios;", rol="service_role").stdout.startswith("true|")


def test_0145_en_postgres_es_idempotente(pg):
    pg(_0145())
    pg(_0145())
    r = pg("select paga_hasta from comercios;", rol="anon", check=False)
    assert r.returncode != 0 and "permission denied" in r.stderr
    pg(f"select {', '.join(_columnas_dadas())} from comercios;", rol="anon")


# ───────────────────────────────────────────────────── la migración 0148 (código sólo admin)

def test_la_0148_esta_igual_en_supabase_y_en_selfhost():
    a = (RAIZ / "supabase/migrations/0148_codigo_solo_admin.sql").read_bytes()
    b = (RAIZ / "selfhost/postgres-init/0148_codigo_solo_admin.sql").read_bytes()
    assert a == b and a


def test_la_0148_cierra_solo_codigo_y_es_idempotente_y_recarga_postgrest():
    sql = _sin_comentarios_sql(_0148())
    assert "revoke select (codigo) on public.comercios from anon, authenticated;" in sql
    assert "begin;" in sql and "commit;" in sql
    assert sql.index("begin;") < sql.index("revoke select (codigo)") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    # No vuelve a dar nada a anon ni toca otras columnas.
    assert not re.search(r"\bgrant\b[^;]*\banon\b", sql, re.I)
    assert len(re.findall(r"\brevoke\b", sql, re.I)) == 1
    assert not re.search(r"create table(?! if not exists)", sql)


def test_codigo_es_privada_para_el_test_y_no_la_pide_ningun_select_anon():
    assert "codigo" in PRIVADAS_EXTRA and "codigo" in NO_VAN_EN_LA_LISTA
    assert "codigo" not in _columnas_publicas() and "codigo" in _columnas_dadas()


def test_ninguna_vista_ni_funcion_publica_expone_codigo():
    """Revisión de las migraciones: `feed_publico`, `buscar_comercios`, `plan_publico` y
    `plan_orden_de` (las que anon puede ejecutar o leer) no nombran `codigo`. Las únicas que lo
    devuelven son las de revisión de rubros del panel (invoker: anon no las puede usar tras la 0148)."""
    carpeta = RAIZ / "supabase/migrations"
    permitidas = {"0044_comercio_codigo.sql", "0065_comercio_wa_grupos.sql", "0087_vista_previa_de_palabras.sql",
                  "0089_revision_humana_de_rubros.sql", "0091_un_solo_texto_que_clasifica.sql",
                  "0092_el_principal_sale_de_lo_que_el_negocio_es.sql", "0145_comercios_columnas_publicas.sql",
                  "0148_codigo_solo_admin.sql"}
    for f in sorted(carpeta.glob("*.sql")):
        sql = _sin_comentarios_sql(f.read_text(encoding="utf-8"))
        if re.search(r"\bcodigo\b", sql) and f.name not in permitidas:
            pytest.fail(f"{f.name} nombra `codigo`: ¿lo expone a anon? Revisalo y, si es del panel, agregalo a la lista")


def test_0148_en_postgres_cierra_codigo_y_deja_el_resto(pg):
    pg(_0145())
    pg("select codigo from comercios;", rol="anon")          # sigue abierto con la 0145 sola
    pg(_0148())
    for rol in ("anon", "authenticated"):
        r = pg("select codigo from comercios;", rol=rol, check=False)
        assert r.returncode != 0 and "permission denied" in r.stderr, (rol, r.stderr)
        r = pg("select id from comercios where codigo is not null;", rol=rol, check=False)
        assert r.returncode != 0 and "permission denied" in r.stderr
        r = pg("select * from comercios;", rol=rol, check=False)
        assert r.returncode != 0 and "permission denied" in r.stderr
        r = pg(f"select {', '.join(_columnas_publicas())} from comercios where activo;", rol=rol)
        assert r.stdout.count("\n") == 1
    # El backend (service_role) lo sigue leyendo: admin e ingesta.
    pg("select codigo from comercios;", rol="service_role")


def test_0148_en_postgres_es_idempotente(pg):
    pg(_0145())
    pg(_0148())
    pg(_0148())
    r = pg("select codigo from comercios;", rol="anon", check=False)
    assert r.returncode != 0 and "permission denied" in r.stderr
    pg(f"select {', '.join(_columnas_publicas())} from comercios;", rol="anon")


def test_0145_en_postgres_si_falta_una_columna_no_se_aplica_nada(pg):
    """Todo o nada: si la lista pide una columna que no existe, el grant de tabla sigue."""
    pg("grant select on comercios to anon;")
    roto = _0145().replace("select (\n  id,", "select (\n  id, columna_que_no_existe,")
    assert roto != _0145()
    r = pg(roto, check=False)
    assert r.returncode != 0
    # Quedó como antes de intentarlo: anon sigue leyendo la tabla entera.
    pg("select paga_hasta from comercios;", rol="anon")
    pg(_0145())
