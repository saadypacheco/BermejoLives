"""Script `cargar_saber_local`: del JSON de una ciudad a la tabla `saber_local`.

Los fixtures son propios (en tmp_path); el archivo real (data/saber_local/bermejo.json)
sólo se prueba en dry-run, para que un JSON roto no llegue al servidor.
"""
import json
from pathlib import Path

import pytest

from app.api.asistente import SECCIONES
from app.scripts import cargar_saber_local as script
from app.services.asistente import _norm

REAL = Path(__file__).resolve().parents[1] / "data" / "saber_local" / "bermejo.json"


def _e(pregunta, respuesta="Una respuesta de prueba.", palabras=("uno", "dos"), tema="compras",
       verificado=True, **extra):
    return {"pregunta": pregunta, "respuesta": respuesta, "palabras": list(palabras), "tema": tema,
            "fuente": "https://ejemplo.bo", "consultado": "2026-10-21", "verificado": verificado, **extra}


@pytest.fixture
def json_ciudad(tmp_path):
    def _escribir(entradas, nombre="bermejo.json"):
        ruta = tmp_path / nombre
        ruta.write_text(json.dumps(entradas, ensure_ascii=False), encoding="utf-8")
        return str(ruta)
    return _escribir


def _sitio(repo):
    return {s["pregunta"]: s for s in repo.saber_local.values() if not s.get("comercio_id")}


# ------------------------------------------------------------------ qué entra

def test_por_defecto_entra_solo_lo_verificado(repo, json_ciudad, capsys):
    ruta = json_ciudad([_e("¿Dónde compro pilas?"), _e("¿Dónde hay un taller?", verificado=False)])
    assert script.main([ruta], repo=repo) == 0
    assert list(_sitio(repo)) == ["¿Dónde compro pilas?"]
    assert "Omite (no verificadas): 1" in capsys.readouterr().out


def test_todos_incluye_los_no_verificados(repo, json_ciudad):
    ruta = json_ciudad([_e("¿Dónde compro pilas?"), _e("¿Dónde hay un taller?", verificado=False)])
    assert script.main([ruta, "--todos"], repo=repo) == 0
    assert set(_sitio(repo)) == {"¿Dónde compro pilas?", "¿Dónde hay un taller?"}


def test_dry_run_muestra_y_no_escribe(repo, json_ciudad, capsys):
    repo.upsert_saber_local({"pregunta": "¿Dónde cambio dólares?", "respuesta": "vieja", "etiquetas": [], "activo": True})
    antes = json.dumps(repo.saber_local, sort_keys=True, default=str)
    ruta = json_ciudad([_e("¿Dónde compro pilas?"), _e("¿Dónde cambio dólares?", respuesta="nueva"),
                        _e("¿Dónde hay un taller?", verificado=False)])
    assert script.main([ruta, "--dry-run", "--todos"], repo=repo) == 0
    salida = capsys.readouterr().out
    assert json.dumps(repo.saber_local, sort_keys=True, default=str) == antes
    assert "crea" in salida and "actualiza" in salida and "DRY-RUN" in salida
    assert "Crea: 2 · Actualiza: 1" in salida


def test_dry_run_dice_que_omite_lo_no_verificado(repo, json_ciudad, capsys):
    ruta = json_ciudad([_e("¿Dónde hay un taller?", verificado=False)])
    script.main([ruta, "--dry-run"], repo=repo)
    assert "omite (no verificado)" in capsys.readouterr().out and not repo.saber_local


# ------------------------------------------------------------------ el mapeo a la tabla

def test_palabras_van_a_etiquetas_y_tema_a_seccion(repo, json_ciudad):
    ruta = json_ciudad([
        _e("¿Dónde compro pilas?", palabras=["Pilas", " baterias ", "pilas"], tema="compras"),
        _e("¿A qué hora pasa el bus?", tema="transporte"),
        _e("¿Qué es URUKU?", tema="uruku"),
        _e("¿Hay un hospital?", tema="salud"),
    ])
    assert script.main([ruta], repo=repo) == 0
    s = _sitio(repo)
    pilas = s["¿Dónde compro pilas?"]
    assert pilas["etiquetas"] == ["baterias", "pilas"] and pilas["seccion"] == "comercios"
    assert s["¿A qué hora pasa el bus?"]["seccion"] == "transporte"
    assert s["¿Qué es URUKU?"]["seccion"] == "general" and s["¿Hay un hospital?"]["seccion"] == "general"
    assert pilas["activo"] is True and pilas["ciudad_id"] == repo.get_ciudad_id("bermejo")
    assert pilas["creado_por"] == "import:bermejo"
    assert all(f["seccion"] in SECCIONES for f in s.values())


# ------------------------------------------------------------------ idempotencia

def test_correrlo_dos_veces_no_duplica_ni_toca_lo_que_no_cambio(repo, json_ciudad, capsys):
    ruta = json_ciudad([_e("¿Dónde compro pilas?"), _e("¿Dónde hay un taller?")])
    script.main([ruta], repo=repo)
    capsys.readouterr()
    filas = json.dumps(repo.saber_local, sort_keys=True, default=str)
    assert script.main([ruta], repo=repo) == 0
    assert "Crea: 0 · Actualiza: 0 · Sin cambios: 2" in capsys.readouterr().out
    assert len(repo.saber_local) == 2
    assert json.dumps(repo.saber_local, sort_keys=True, default=str) == filas     # ni updated_at


def test_si_cambia_la_respuesta_se_actualiza_la_misma_fila(repo, json_ciudad):
    script.main([json_ciudad([_e("¿Dónde compro pilas?", respuesta="vieja")])], repo=repo)
    id_antes = next(iter(repo.saber_local))
    script.main([json_ciudad([_e("¿Dónde compro pilas?", respuesta="nueva", palabras=["otra"])])], repo=repo)
    assert len(repo.saber_local) == 1
    fila = repo.saber_local[id_antes]
    assert fila["respuesta"] == "nueva" and fila["etiquetas"] == ["otra"]


def test_la_pregunta_se_compara_sin_tildes_ni_signos_y_actualiza_la_sembrada(repo, json_ciudad, capsys):
    """Las preguntas que sembraron las migraciones 0106/0107/0110 se ACTUALIZAN, no se duplican."""
    sembrada = repo.upsert_saber_local({
        "pregunta": "¿Dónde cambio dólares o pesos?", "respuesta": "de la migración", "etiquetas": ["dolar"],
        "seccion": "comercios", "ciudad_id": "ciu-1", "activo": True, "creado_por": "inicial"})
    ruta = json_ciudad([_e("donde CAMBIO dolares o pesos", respuesta="del JSON", palabras=["cambio", "dolar"],
                           tema="cambio")])
    script.main([ruta, "--dry-run"], repo=repo)
    assert "actualiza" in capsys.readouterr().out and len(repo.saber_local) == 1
    assert script.main([ruta], repo=repo) == 0
    assert len(repo.saber_local) == 1
    fila = repo.saber_local[sembrada["id"]]
    assert fila["respuesta"] == "del JSON" and fila["etiquetas"] == ["cambio", "dolar"]
    assert fila["pregunta"] == "¿Dónde cambio dólares o pesos?"                  # la pregunta no se pisa
    assert fila["creado_por"] == "inicial" and fila["ciudad_id"] == "ciu-1"       # lo que tenía, queda


def test_lo_que_el_admin_dio_de_baja_se_actualiza_pero_sigue_de_baja(repo, json_ciudad):
    baja = repo.upsert_saber_local({"pregunta": "¿Dónde compro pilas?", "respuesta": "vieja",
                                    "etiquetas": [], "activo": False})
    script.main([json_ciudad([_e("¿Dónde compro pilas?", respuesta="nueva")])], repo=repo)
    assert len(repo.saber_local) == 1
    assert repo.saber_local[baja["id"]]["respuesta"] == "nueva" and repo.saber_local[baja["id"]]["activo"] is False


def test_nunca_borra_lo_que_no_esta_en_el_archivo(repo, json_ciudad):
    repo.upsert_saber_local({"pregunta": "¿Algo que sólo está en la base?", "respuesta": "sí", "etiquetas": [], "activo": True})
    script.main([json_ciudad([_e("¿Dónde compro pilas?")])], repo=repo)
    assert "¿Algo que sólo está en la base?" in _sitio(repo) and len(repo.saber_local) == 2


def test_la_respuesta_de_un_comercio_con_la_misma_pregunta_no_se_toca(repo, json_ciudad):
    propia = repo.upsert_saber_local({"pregunta": "¿Dónde compro pilas?", "respuesta": "la del dueño",
                                      "etiquetas": [], "activo": True, "comercio_id": "com-1"})
    script.main([json_ciudad([_e("¿Dónde compro pilas?", respuesta="la de URUKU")])], repo=repo)
    assert repo.saber_local[propia["id"]]["respuesta"] == "la del dueño"
    assert len(repo.saber_local) == 2


def test_la_misma_pregunta_repetida_en_el_archivo_vale_la_ultima(repo, json_ciudad):
    script.main([json_ciudad([_e("¿Dónde compro pilas?", respuesta="primera"),
                              _e("donde compro pilas", respuesta="segunda")])], repo=repo)
    assert [f["respuesta"] for f in repo.saber_local.values()] == ["segunda"]


# ------------------------------------------------------------------ errores: no escribe nada

@pytest.mark.parametrize("entradas", [
    [_e("¿Dónde compro pilas?"), {"pregunta": "ab", "respuesta": "x" * 10}],          # pregunta corta
    [_e("¿Dónde compro pilas?"), _e("¿Pregunta sin respuesta?", respuesta="")],
    [_e("¿Dónde compro pilas?"), {**_e("¿Palabras mal?"), "palabras": "no es lista"}],
    {"pregunta": "no es una lista"},
])
def test_un_archivo_invalido_sale_con_1_y_no_escribe(repo, json_ciudad, entradas, capsys):
    assert script.main([json_ciudad(entradas)], repo=repo) == 1
    assert not repo.saber_local and capsys.readouterr().err


def test_archivo_que_no_existe_o_json_roto(repo, tmp_path):
    assert script.main([str(tmp_path / "nada.json")], repo=repo) == 1
    roto = tmp_path / "roto.json"
    roto.write_text("{ esto no es json", encoding="utf-8")
    assert script.main([str(roto)], repo=repo) == 1


def test_ciudad_invalida_o_inexistente(repo, json_ciudad):
    assert script.main(["../../etc/passwd"], repo=repo) == 1          # un slug, no una ruta
    assert script.main(["no-existe"], repo=repo) == 1                 # sin archivo
    ruta = json_ciudad([_e("¿Dónde compro pilas?")], nombre="atlantida.json")
    assert script.main([ruta], repo=repo) == 1 and not repo.saber_local   # ciudad que no está en la base


# ------------------------------------------------------------------ el archivo real

def test_el_archivo_real_de_bermejo_carga_en_dry_run_sin_errores(repo, capsys):
    assert REAL.exists(), "falta backend/data/saber_local/bermejo.json"
    crudo = json.loads(REAL.read_text(encoding="utf-8"))
    unicas = {_norm(e["pregunta"]) for e in crudo}
    verificadas = {_norm(e["pregunta"]) for e in crudo if e.get("verificado") is True}

    assert script.main(["bermejo", "--dry-run"], repo=repo) == 0
    sal = capsys.readouterr().out
    assert f"Crea: {len(verificadas)} " in sal and not repo.saber_local

    assert script.main(["bermejo", "--dry-run", "--todos"], repo=repo) == 0
    assert f"Crea: {len(unicas)} " in capsys.readouterr().out


def test_el_archivo_real_actualiza_las_preguntas_que_ya_sembraron_las_migraciones(repo, capsys):
    """Hay preguntas del JSON con el MISMO texto que filas de las migraciones 0106/0107/0110:
    ahí el script actualiza, no duplica."""
    crudo = json.loads(REAL.read_text(encoding="utf-8"))
    comunes = [e for e in crudo if e.get("verificado") is True][:3]
    for e in comunes:
        repo.upsert_saber_local({"pregunta": e["pregunta"], "respuesta": "sembrada", "etiquetas": [],
                                 "seccion": "general", "ciudad_id": "ciu-1", "activo": True, "creado_por": "inicial"})
    assert script.main(["bermejo", "--dry-run"], repo=repo) == 0
    assert "Actualiza: 3 " in capsys.readouterr().out
    assert script.main(["bermejo"], repo=repo) == 0
    assert len([s for s in repo.saber_local.values() if s["pregunta"] in {e["pregunta"] for e in comunes}]) == 3
    # y una segunda corrida no cambia nada
    capsys.readouterr()
    script.main(["bermejo"], repo=repo)
    assert "Crea: 0 · Actualiza: 0 " in capsys.readouterr().out
