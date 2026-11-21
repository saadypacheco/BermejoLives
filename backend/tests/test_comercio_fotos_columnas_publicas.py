"""Columnas públicas de `comercio_fotos` (migración 0203, docs/fotos-estilo-uruku.md §4): el espejo de
`test_comercios_columnas_publicas.py` (0145).

La 0203 le saca a anon y authenticated el `select` de tabla entera y les da 8 columnas. Con eso PostgREST falla (42501) todo
`select=*` sobre la tabla: el frontend tiene que pedir columnas explícitas, y ninguna puede ser la privada
(`diseno_propuesta_url`, la propuesta que el panel todavía no aprobó).

Qué se prueba:
- La lista pública sale del grant de la 0203; la privada no está en ella.
- Ningún `select` del frontend con el cliente anon sobre `comercio_fotos` pide `*`, ni columnas privadas, ni una que la 0203 no dé,
  y tampoco los embebidos tipo `comercios(... comercio_fotos(*))`.
- El frontend no nombra la columna privada en ningún lado (el panel habla con el backend, que usa service_role).
"""
import re

from app.services.fotos_galeria import PRIVADAS      # la MISMA tupla que usa el backend para sacarlas de las respuestas
from tests.test_comercios_columnas_publicas import (FRONT, RAIZ, _archivos_anon, _args_de_select, _primer_argumento,
                                                    _sin_comentarios_sql)



def _publicas_de_la_0203() -> list[str]:
    sql = _sin_comentarios_sql((RAIZ / "supabase/migrations/0203_fotos_estilo_uruku.sql").read_text(encoding="utf-8"))
    m = re.search(r"grant select \((.*?)\)\s+on public\.comercio_fotos to anon, authenticated;", sql, re.S)
    assert m, "la 0203 no tiene el grant select (columnas) de comercio_fotos"
    return [c.strip() for c in m.group(1).split(",") if c.strip()]


def _selects_sobre_comercio_fotos(texto: str) -> list[str]:
    """El primer argumento de cada `.select(...)` que sigue a `.from("comercio_fotos")` (en la misma cadena)."""
    out = []
    for m in re.finditer(r"""\.from\(\s*["']comercio_fotos["']\s*\)""", texto):
        resto = texto[m.end():]
        s = re.match(r"(?:\s|//[^\n]*\n)*\.select\(", resto)
        if s:
            out.append(_primer_argumento(_args_de_select(resto, s.end())))
        else:
            out.append(None)           # un from() sin select(): update/insert/delete con anon, que no se permite
    return out


def test_la_lista_publica_tiene_las_8_columnas_y_no_la_privada():
    publicas = _publicas_de_la_0203()
    assert publicas == ["id", "comercio_id", "url", "thumb_url", "orden", "created_at", "diseno_url", "diseno_thumb_url"]
    for privada in PRIVADAS:
        assert privada not in publicas


def test_el_buscador_de_archivos_anon_ve_a_comercio_fotos():
    vistos = sum(len(_selects_sobre_comercio_fotos(f.read_text(encoding="utf-8"))) for f in _archivos_anon())
    assert vistos >= 2          # getFotosDeComercios y getGaleriaComercio (lib/data.ts)


def test_ningun_select_anon_sobre_comercio_fotos_usa_asterisco_ni_privadas_ni_columnas_no_dadas():
    dadas = set(_publicas_de_la_0203())
    vistos = 0
    for f in _archivos_anon():
        texto = f.read_text(encoding="utf-8")
        for arg in _selects_sobre_comercio_fotos(texto):
            vistos += 1
            donde = f"{f.relative_to(RAIZ)}: select({arg})"
            assert arg is not None, f"comercio_fotos con anon sin select (escritura): {donde}"
            assert arg != "", f"select() sin columnas = '*': {donde}"
            assert arg[0] in "\"'`", f"select con algo que no puedo revisar: {donde}"
            lista = arg[1:-1]
            assert "${" not in lista, f"select armado en runtime: {donde}"
            assert "*" not in lista, f"select * sobre comercio_fotos con anon: {donde}"
            for col in (c.strip() for c in lista.split(",")):
                assert col in dadas, f"columna sin permiso para anon ({col}) en {donde}"
    assert vistos >= 2


def test_ningun_embebido_de_comercio_fotos_pide_asterisco_o_privadas():
    """`comercios(... comercio_fotos(*))`, `comercio_fotos!inner(*)`: tienen que listar sólo columnas dadas."""
    dadas = set(_publicas_de_la_0203())
    for f in _archivos_anon():
        texto = f.read_text(encoding="utf-8")
        for m in re.finditer(r"""["'`][^"'`]*\bcomercio_fotos(?:![\w]+)?\s*\(([^)]*)\)""", texto):
            interior = m.group(1).strip()
            donde = f"{f.relative_to(RAIZ)}: {m.group(0)[:100]}"
            assert "*" not in interior, f"embebido con *: {donde}"
            assert interior, f"embebido sin columnas: {donde}"
            for col in (c.strip() for c in interior.split(",")):
                assert col in dadas or col == "count", f"embebido con columna sin permiso ({col}): {donde}"


def test_el_frontend_no_nombra_la_columna_privada_de_la_propuesta():
    """El panel no lee la propuesta de la base: la pide al backend (`GalleryItem.proposal_url`, service_role)."""
    for ext in ("*.ts", "*.tsx"):
        for f in FRONT.rglob(ext):
            if set(f.relative_to(FRONT).parts) & {"node_modules", ".next", "out", "tests"}:
                continue                                  # (los tests del front arman filas de prueba con esa columna a propósito)
            texto = f.read_text(encoding="utf-8", errors="ignore")
            for privada in PRIVADAS:
                assert not re.search(rf"\b{privada}\b", texto), f"{f.relative_to(RAIZ)} nombra la columna privada {privada}"


def test_el_frontend_anon_no_filtra_ni_ordena_por_la_privada():
    privadas = "|".join(PRIVADAS)
    for f in _archivos_anon():
        texto = f.read_text(encoding="utf-8")
        filtro = re.search(rf"""\.(eq|neq|gt|gte|lt|lte|is|in|not|order|ilike|like|filter)\(\s*["']({privadas})["']""", texto)
        assert not filtro, f"{f.relative_to(RAIZ)}: filtra u ordena por una columna privada: {filtro.group(0)}"


def test_la_galeria_de_la_ficha_reintenta_sin_las_columnas_de_diseno_si_la_0203_todavia_no_corrio():
    """Orden de deploy (docs/deploy-qa.md): si el front sale antes que la 0203, las columnas `diseno_*` no existen y la consulta da
    42703; sin el reintento todas las fichas quedarían sin galería. El reintento pide lo de siempre y deja el error en el log."""
    texto = (FRONT / "lib/data.ts").read_text(encoding="utf-8")
    m = re.search(r"export async function getGaleriaComercio\(.*?\n}\n", texto, re.S)
    assert m, "no encontré getGaleriaComercio"
    fn = m.group(0)
    con = fn.index('select("id, url, thumb_url, diseno_url, diseno_thumb_url")')
    sin = fn.index('select("id, url, thumb_url")')
    assert con < fn.index("if (fotos.error)") < sin
    assert "logSupaError" in fn[con:sin]
    assert "ANTES que la migración 0203" in fn or "ANTES que la migración" in fn


def test_deploy_qa_dice_que_la_0203_va_antes_del_front():
    doc = (RAIZ / "docs/deploy-qa.md").read_text(encoding="utf-8")
    assert "primero la migración, después el front" in doc and "0203" in doc
