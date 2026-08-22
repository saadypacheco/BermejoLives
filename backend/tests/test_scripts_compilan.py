"""Los scripts de mantenimiento tienen que parsear.

Nada los importaba, así que un error de sintaxis pasaba la suite entera y
aparecía recién en producción, al ejecutarlos a mano contra la base real — que
es el peor momento posible para descubrirlo.

No se ejecutan (tocan la base y la API de Gemini), sólo se compilan: alcanza
para que un archivo roto no llegue al servidor.
"""
import pathlib
import py_compile

import pytest

SCRIPTS = sorted((pathlib.Path(__file__).resolve().parents[1] / "scripts").glob("*.py"))


def test_hay_scripts_para_revisar():
    """Si el glob deja de encontrar archivos, el test de abajo pasa vacío y no
    protege nada."""
    assert SCRIPTS, "no se encontró ningún script en backend/scripts/"


@pytest.mark.parametrize("script", SCRIPTS, ids=lambda p: p.name)
def test_el_script_compila(script, tmp_path):
    py_compile.compile(str(script), cfile=str(tmp_path / "out.pyc"), doraise=True)
