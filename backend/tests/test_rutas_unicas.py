"""Ninguna ruta declarada dos veces.

Costó una pantalla en blanco en producción y dos días de buscar en el lugar
equivocado. `/admin/rubros/propuestos` estaba definida dos veces con cuerpos de
respuesta distintos: FastAPI se queda con la primera, así que la segunda —la que
el panel esperaba— nunca corrió. El panel recibía un 200 con un cuerpo sin el
campo que leía, y se caía al hacer `.length` de undefined.

Lo peor es dónde NO apareció: FastAPI acepta duplicados sin una advertencia, la
red devolvía 200, y ningún test pedía esa ruta. Un resultado plausible, que es
la forma cara de fallar.

Este test es barato y cubre todas las rutas, incluidas las que todavía no
existen. Es la clase de guarda que sí salta.
"""
from collections import Counter

from app.main import app


def test_ninguna_ruta_esta_declarada_dos_veces():
    vistas = Counter()
    for r in app.routes:
        for metodo in getattr(r, "methods", None) or []:
            vistas[(metodo, getattr(r, "path", ""))] += 1

    repetidas = {k: n for k, n in vistas.items() if n > 1}
    assert not repetidas, (
        "Hay rutas declaradas más de una vez. FastAPI usa la PRIMERA y la otra "
        f"queda muerta sin avisar: {sorted(repetidas)}")
