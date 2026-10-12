"""Columnas públicas de `publicaciones` (migración 0149, revisión de seguridad del 12/10).

Desde la 0002 anon tenía `grant select on publicaciones` de tabla entera: de las filas
aprobadas y activas se leía TODO por la API (`raw`, `codigo_recibido`, `identidad_origen`,
`moderado_por`, `ia_*`...). La 0149 pasa a `grant select (columnas)`, igual que la 0145 con
`comercios`. Con eso PostgREST falla (42501) todo `select=*` sobre la tabla: el frontend
tiene que pedir columnas explícitas (hoy sólo `id`, `estado`, `activo` y `descuento_pct`).

Qué se prueba:
- La 0149 es idéntica en las dos carpetas, su lista NO incluye las privadas, cubre TODAS las
  demás columnas que hoy existen en las migraciones (si alguien agrega una columna a
  `publicaciones`, este test lo obliga a decidir: pública o privada), es una transacción,
  idempotente y recarga PostgREST.
- Ningún `select` del frontend con el cliente anon sobre `publicaciones` pide `*` ni una
  columna privada ni una que la 0149 no dé; `feed_publico` (vista) sigue abierta.
- La ingesta ya no copia el crudo a `publicaciones.raw` (queda en `wa_inbox.raw`).
- Contra un Postgres real de Docker (opcional, `URUKU_PG_TEST_CONTAINER`): como anon y
  authenticated las privadas dan «permission denied», las públicas andan (también el
  conteo y la vista `feed_publico`), service_role sigue viendo todo, y la migración corre
  dos veces. Las dos funciones del panel dejan de ser ejecutables por anon.
"""
import re
from pathlib import Path

import pytest

from tests.pg_0149 import RAIZ, columnas_de_tabla, leer_0149, pg0149, sin_comentarios_sql  # noqa: F401

# Lo que el público NO tiene por qué ver de una publicación aprobada.
PRIVADAS = ("raw", "codigo_recibido", "identidad_origen", "moderado_por", "moderado_at",
            "motivo_moderacion", "wa_message_id", "costo", "cobrado", "producto_ref_id",
            "terminos_ia", "ia_analizado_at", "ia_veredicto", "ia_motivo", "ia_confianza",
            "ia_revisado_at", "busqueda")
FRONT = RAIZ / "frontend"


def _columnas_dadas() -> list[str]:
    sql = sin_comentarios_sql(leer_0149())
    m = re.search(r"grant select \((.*?)\) on public\.publicaciones to anon, authenticated;", sql, re.S)
    assert m, "la 0149 no tiene el grant select (columnas) de publicaciones"
    return [c.strip() for c in m.group(1).split(",") if c.strip()]


# ───────────────────────────────────────────────────── la migración 0149 (estática)
def test_la_0149_esta_igual_en_supabase_y_en_selfhost():
    a = (RAIZ / "supabase/migrations/0149_publicaciones_columnas_y_codigos.sql").read_bytes()
    b = (RAIZ / "selfhost/postgres-init/0149_publicaciones_columnas_y_codigos.sql").read_bytes()
    assert a == b and a


def test_la_0149_no_da_las_columnas_privadas_de_publicaciones():
    dadas = _columnas_dadas()
    for privada in PRIVADAS:
        assert privada not in dadas, privada
    assert len(dadas) == len(set(dadas)), "columnas repetidas en el grant"
    # Ni nombradas en un grant a anon: sólo aparecen en comentarios y en la comprobación.
    sql = sin_comentarios_sql(leer_0149())
    for g in re.findall(r"grant[^;]*to anon[^;]*;", sql, re.I):
        for privada in PRIVADAS:
            assert not re.search(rf"\b{privada}\b", g), (privada, g)


def test_la_0149_quita_el_grant_de_tabla_de_publicaciones_y_es_una_transaccion():
    sql = sin_comentarios_sql(leer_0149())
    assert "revoke select on public.publicaciones from anon, authenticated;" in sql
    # El revoke de tabla va antes del grant por columnas (el revoke de tabla borra también los de columna).
    assert sql.index("revoke select on public.publicaciones") < sql.index("grant select (")
    assert "grant all on public.publicaciones to service_role;" in sql
    assert sql.index("begin;") < sql.index("revoke select on public.publicaciones") < sql.index("commit;")
    assert sql.rstrip().endswith("notify pgrst, 'reload schema';")
    # Nunca un grant de tabla entera a anon, ni sobre publicaciones ni sobre las tablas nuevas.
    assert not re.search(r"grant\s+(select|all)\s+on\s+(public\.)?(publicaciones|comercio_eventos|comercio_usuarios)\s+to\s+[^;]*(anon|authenticated|public)",
                         sql, re.I)
    assert not re.search(r"create table(?! if not exists)", sql)


def test_la_0149_cubre_todas_las_columnas_de_publicaciones_menos_las_privadas():
    """Si alguien agrega una columna a `publicaciones`, este test falla hasta que decida:
    darla a anon en una migración y listarla acá, o sumarla a `PRIVADAS`. Nace PRIVADA en la base."""
    existentes = set(columnas_de_tabla("publicaciones"))
    dadas = set(_columnas_dadas())
    assert {"raw", "codigo_recibido", "ia_veredicto", "motivo_moderacion"} <= existentes     # el parseo ve todo
    assert dadas <= existentes, f"la 0149 da columnas que no existen: {sorted(dadas - existentes)}"
    faltan = existentes - dadas - set(PRIVADAS)
    assert not faltan, f"columnas de publicaciones sin decidir (¿públicas? ¿privadas?): {sorted(faltan)}"
    assert not (set(PRIVADAS) - existentes), "una 'privada' del test ya no existe"


def test_lo_que_ya_muestra_feed_publico_sigue_leyendose():
    """Las columnas de `publicaciones` que usa la vista `feed_publico` (su última definición, 0123)
    están dadas: así un `select` directo a la tabla ve lo mismo que el feed, no más."""
    vista = sin_comentarios_sql((RAIZ / "supabase/migrations/0123_feed_por_ciudad.sql").read_text(encoding="utf-8"))
    usadas = set(re.findall(r"\bp\.(\w+)", vista))
    assert usadas, "no encontré columnas de p. en la vista"
    assert usadas <= set(_columnas_dadas()), sorted(usadas - set(_columnas_dadas()))


def test_ninguna_funcion_publica_lee_publicaciones_con_los_permisos_de_anon():
    """Las funciones que leen `publicaciones` y anon puede ejecutar tienen que ser SECURITY DEFINER
    (desde la 0143 `buscar_comercios` lo es). Si no, el cierre de la 0149 las rompería."""
    texto = (RAIZ / "supabase/migrations/0143_estrella_y_cortesia.sql").read_text(encoding="utf-8")
    m = re.search(r"create function buscar_comercios\((.*?)\n\$\$;", texto, re.S | re.I)
    assert m and re.search(r"security definer", m.group(0), re.I)


# ───────────────────────────────────────────────────── el frontend, con anon
def _archivos_anon() -> list[Path]:
    salida = []
    for ext in ("*.ts", "*.tsx"):
        for f in FRONT.rglob(ext):
            if set(f.relative_to(FRONT).parts) & {"node_modules", ".next", "out"}:
                continue
            texto = f.read_text(encoding="utf-8", errors="ignore")
            if re.search(r"""from\s+["']@/lib/supabase["']|from\s+["']\./supabase["']""", texto) \
               and re.search(r"supabase\s*\.\s*(from|rpc)\b|supabase\s*\n\s*\.from", texto):
                salida.append(f)
    return salida


def _cadena_desde(texto: str, desde: int) -> str:
    """La cadena de métodos que sigue a un `.from("publicaciones")`: hasta el `;` o el cierre del
    paréntesis que lo contiene, saltando strings."""
    nivel, i = 0, desde
    while i < len(texto):
        c = texto[i]
        if c in "\"'`":
            q, i = c, i + 1
            while i < len(texto) and texto[i] != q:
                i += 2 if texto[i] == "\\" else 1
        elif c in "([{":
            nivel += 1
        elif c in ")]}":
            nivel -= 1
            if nivel < 0:
                break
        elif c == ";" and nivel == 0:
            break
        i += 1
    return texto[desde:i]


def test_el_buscador_de_archivos_anon_encuentra_data_ts():
    assert "data.ts" in {f.name for f in _archivos_anon()}


def test_ningun_select_anon_sobre_publicaciones_usa_asterisco_ni_columnas_privadas_ni_no_dadas():
    dadas = set(_columnas_dadas())
    vistos = 0
    for f in _archivos_anon():
        texto = f.read_text(encoding="utf-8")
        for m in re.finditer(r"""\.from\(\s*["']publicaciones["']\s*\)""", texto):
            vistos += 1
            cadena = _cadena_desde(texto, m.end())
            donde = f"{f.relative_to(RAIZ)}: {cadena.strip()[:160]}"
            sel = re.search(r"""\.select\(\s*["'`]([^"'`]*)["'`]""", cadena)
            assert sel, f"select que no puedo revisar: {donde}"
            columnas = [c.strip() for c in sel.group(1).split(",")]
            assert "*" not in sel.group(1) and "" not in columnas, f"select * sobre publicaciones con anon: {donde}"
            usadas = set(columnas)
            # Los filtros y el orden también leen la columna.
            usadas |= set(re.findall(r"""\.(?:eq|neq|gt|gte|lt|lte|is|in|not|order|ilike|like|filter)\(\s*["'](\w+)["']""", cadena))
            for col in usadas:
                assert col not in PRIVADAS, f"columna privada ({col}) en {donde}"
                assert col in dadas, f"columna sin permiso para anon ({col}) en {donde}"
    assert vistos >= 2          # getVolumenes + getFiltrosDisponibles


def test_ningun_embebido_de_publicaciones_en_el_frontend_pide_asterisco_o_privadas():
    for f in _archivos_anon():
        texto = f.read_text(encoding="utf-8")
        for m in re.finditer(r"""["'`][^"'`]*\bpublicaciones(?:![\w]+)?\s*\(([^)]*)\)""", texto):
            interior = m.group(1).strip()
            assert "*" not in interior, f"{f.relative_to(RAIZ)}: embebido con *"
            for privada in PRIVADAS:
                assert not re.search(rf"\b{privada}\b", interior), f"{f.relative_to(RAIZ)}: embebido con {privada}"


def test_el_feed_publico_se_lee_como_vista_y_no_pide_nada_de_la_tabla():
    """`feed_publico` corre con su dueño: el cierre de la tabla no lo toca. Sólo hay que cuidar que
    el frontend no pida de la vista algo que no tiene."""
    texto = (FRONT / "lib/data.ts").read_text(encoding="utf-8")
    assert texto.count('.from("feed_publico")') >= 3


# ───────────────────────────────────────────────────── la ingesta ya no copia el crudo
def _evento(wamid, body="Oferta zapatillas 120 Bs", phone="59170000009"):
    return {"event": "message", "session": "obs@c.us",
            "payload": {"id": wamid, "from": f"{phone}@c.us", "fromMe": False, "body": body,
                        "type": "text", "timestamp": 1700000000}}


def test_la_ingesta_no_copia_el_crudo_a_publicaciones(repo):
    from app.services import ingest

    repo.seed_comercio(slug="zap", nombre="Zapatería", whatsapp="59170000009", activo=True, confiable=True)
    ingest.handle_message(_evento("wa-raw-1"), repo)
    assert len(repo.publicaciones) == 1
    assert "raw" not in repo.publicaciones[0]
    # El crudo SÍ queda en la bandeja (de ahí lo lee el reproceso).
    assert repo.wa_inbox["wa-raw-1"]["raw"]["body"] == "Oferta zapatillas 120 Bs"


def test_el_explorador_tampoco_copia_el_crudo(repo, monkeypatch):
    from app.core.config import settings
    from app.services import ingest

    repo.seed_comercio(slug="zap", nombre="Zapatería", codigo="K7M2", activo=True)
    monkeypatch.setattr(settings, "wa_numeros_explorador", "59171112222")
    ingest.handle_message(_evento("wa-raw-2", body="URUKU-K7M2 zapatilla urbana Bs 180", phone="59171112222"), repo)
    assert len(repo.publicaciones) == 1 and repo.publicaciones[0]["origen"] == "explorador"
    assert "raw" not in repo.publicaciones[0]


def test_nada_del_backend_lee_el_crudo_de_publicaciones():
    """Sólo `wa_inbox.raw` se lee (el reproceso). Si alguien empezara a leer `publicaciones.raw`
    (o a escribirlo de nuevo en la ingesta) este test lo avisa."""
    ingesta = (RAIZ / "backend/app/services/ingest.py").read_text(encoding="utf-8")
    # El crudo se escribe UNA vez, en la bandeja (`wa_inbox`); la copia enmascarada de una clave
    # mandada por WhatsApp va también a la bandeja. Ninguna fila de publicación lo lleva.
    assert ingesta.count('"raw": event.payload') == 1
    assert ingesta.count('"raw": clave_filtrada.enmascarar(event.payload') == 1
    for f in (RAIZ / "backend/app").rglob("*.py"):
        texto = f.read_text(encoding="utf-8")
        assert not re.search(r"""publicacion\w*\s*(?:\.get\(\s*|\[\s*)["']raw["']""", texto), f"{f.name} lee el crudo de una publicación"


# ───────────────────────────────────────────────────── contra un Postgres real (Docker)
def _insertar_publicaciones(psql):
    psql("""
        insert into comercios (id, slug, nombre, activo) values
          ('11111111-1111-4111-8111-111111111111', 'zapateria', 'Zapatería', true);
        insert into publicaciones (comercio_id, tipo, titulo, estado, activo, raw, codigo_recibido,
                                   identidad_origen, moderado_por, motivo_moderacion, wa_message_id,
                                   ia_veredicto, ia_motivo, ia_confianza, descuento_pct, contacto_whatsapp)
          values ('11111111-1111-4111-8111-111111111111', 'oferta', 'Zapatillas', 'aprobado', true,
                  '{"from":"59170000009@c.us"}', 'K7M2', 'codigo', 'ana@uruku.bo', 'ok', 'wamid-1',
                  'aprobar', 'se ve bien', '0.93', '20', '59170000009'),
                 ('11111111-1111-4111-8111-111111111111', 'oferta', 'Pendiente', 'pendiente', true,
                  '{"x":1}', 'K7M2', 'codigo', null, null, 'wamid-2', null, null, null, null, null);
    """)


def test_antes_de_la_0149_anon_leia_todo(pg0149):
    _insertar_publicaciones(pg0149)
    r = pg0149("select raw, codigo_recibido, moderado_por, ia_veredicto from publicaciones;", rol="anon")
    assert "K7M2" in r.stdout and "ana@uruku.bo" in r.stdout          # el problema, tal cual era
    r = pg0149("select count(*) from publicaciones;", rol="anon")
    assert r.stdout.strip() == "1"                                     # la policy ya dejaba sólo las aprobadas


@pytest.fixture(scope="module")
def migrada(pg0149):
    pg0149(leer_0149())
    return pg0149


def test_0149_en_postgres_cierra_las_privadas_y_deja_las_publicas(migrada):
    for rol in ("anon", "authenticated"):
        for privada in PRIVADAS:
            r = migrada(f"select {privada} from publicaciones;", rol=rol, check=False)
            assert r.returncode != 0 and "permission denied" in r.stderr, (rol, privada, r.stderr)
            # Filtrar u ordenar por una privada también lee la columna.
            r = migrada(f"select id from publicaciones where {privada} is not null;", rol=rol, check=False)
            assert r.returncode != 0 and "permission denied" in r.stderr, (rol, privada)
        # `select *` (PostgREST lo expande) falla entero: por eso las columnas explícitas.
        r = migrada("select * from publicaciones;", rol=rol, check=False)
        assert r.returncode != 0 and "permission denied" in r.stderr
        # Lo que lee el sitio: las columnas dadas, sólo de las aprobadas y activas (la policy sigue).
        r = migrada(f"select {', '.join(_columnas_dadas())} from publicaciones;", rol=rol)
        assert r.stdout.count("\n") == 1 and "Zapatillas" in r.stdout and "Pendiente" not in r.stdout
        # El conteo de `getVolumenes` y `getFiltrosDisponibles`.
        r = migrada("select count(*) from publicaciones where estado = 'aprobado' and activo and descuento_pct is not null;", rol=rol)
        assert r.stdout.strip() == "1"
        r = migrada("select count(*) from publicaciones where estado = 'aprobado';", rol=rol)
        assert r.stdout.strip() == "1"


def test_0149_en_postgres_feed_publico_sigue_abierto_y_sin_privadas(migrada):
    for rol in ("anon", "authenticated"):
        r = migrada("select titulo, comercio_slug from feed_publico;", rol=rol)
        assert r.stdout.strip() == "Zapatillas|zapateria"
        r = migrada("select * from feed_publico;", rol=rol)           # la vista no trae privadas
        assert "K7M2" not in r.stdout and "ana@uruku.bo" not in r.stdout


def test_0149_en_postgres_service_role_sigue_viendo_todo(migrada):
    r = migrada("select raw, codigo_recibido, ia_veredicto, wa_message_id from publicaciones order by wa_message_id;", rol="service_role")
    assert "59170000009@c.us" in r.stdout and "K7M2" in r.stdout and "aprobar" in r.stdout
    assert r.stdout.count("\n") == 2                                   # service_role bypassa la policy
    migrada("insert into publicaciones (comercio_id, tipo, estado, raw) values "
            "('11111111-1111-4111-8111-111111111111', 'novedad', 'pendiente', '{}');", rol="service_role")


def test_0149_en_postgres_las_funciones_del_panel_no_las_ejecuta_anon(migrada):
    for rol in ("anon", "authenticated"):
        for llamada in ("select * from previsualizar_patron('zapatilla', null);", "select * from rubros_a_revisar();"):
            r = migrada(llamada, rol=rol, check=False)
            assert r.returncode != 0 and "permission denied for function" in r.stderr, (rol, llamada, r.stderr)
    assert migrada("select * from previsualizar_patron('zapatilla', null);", rol="service_role").stdout.strip() == "K7M2"
    assert migrada("select * from rubros_a_revisar('dudosos', 5);", rol="service_role").stdout.strip() == "K7M2"


def test_0149_en_postgres_es_idempotente(migrada):
    migrada(leer_0149())
    migrada(leer_0149())
    r = migrada("select raw from publicaciones;", rol="anon", check=False)
    assert r.returncode != 0 and "permission denied" in r.stderr
    migrada(f"select {', '.join(_columnas_dadas())} from publicaciones;", rol="anon")
    r = migrada("select * from previsualizar_patron('x', null);", rol="anon", check=False)
    assert r.returncode != 0 and "permission denied for function" in r.stderr


def test_0149_en_postgres_si_una_columna_publica_no_existe_no_se_aplica_nada(pg0149):
    """Todo o nada: con una columna inexistente en el grant, la transacción se revierte y los
    permisos quedan como estaban."""
    roto = leer_0149().replace("select (\n  id,", "select (\n  id, columna_que_no_existe,")
    assert roto != leer_0149()
    antes = pg0149("select has_column_privilege('anon', 'public.publicaciones', 'estado', 'select');").stdout.strip()
    r = pg0149(roto, check=False)
    assert r.returncode != 0
    assert pg0149("select has_column_privilege('anon', 'public.publicaciones', 'estado', 'select');").stdout.strip() == antes
