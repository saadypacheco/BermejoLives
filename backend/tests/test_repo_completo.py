"""SupabaseRepo tiene que implementar TODO lo que declara el Protocol.

Nace de un bug real que llegó a producción: tres implementaciones nuevas
quedaron pegadas dentro de la clase `Repo` (el Protocol) en vez de
`SupabaseRepo`. Todo compilaba, los 249 tests pasaban —porque corren contra
FakeRepo, que sí las tenía— y recién en el servidor aparecía
"'SupabaseRepo' object has no attribute 'list_rubros'".

El Protocol no da error en runtime si falta un método: no es una clase base
abstracta, sólo describe una forma. Este test hace ese chequeo explícito.
"""
from app.db.repository import Repo, SupabaseRepo
from tests.conftest import FakeRepo


def _metodos_del_protocolo() -> set[str]:
    return {n for n in dir(Repo) if not n.startswith("_") and callable(getattr(Repo, n, None))}


def test_supabase_repo_implementa_todo_el_protocolo():
    faltan = sorted(m for m in _metodos_del_protocolo() if not hasattr(SupabaseRepo, m))
    assert not faltan, (
        "SupabaseRepo no implementa estos métodos del Protocol — el código va a "
        f"fallar en producción con AttributeError: {faltan}"
    )


# Métodos del Protocol que el FakeRepo no implementa. Vacío = todo el Protocol
# es ejercitable desde los tests. Si alguna vez hay que sumar uno acá, que sea
# una decisión consciente: cada entrada es un endpoint que nadie prueba.
SIN_COBERTURA: set[str] = set()


def test_el_fake_no_se_queda_mas_corto_de_lo_que_ya_esta():
    """Si el fake se queda corto, los tests pasan por casualidad: ejercen un
    comportamiento que no existe en producción."""
    faltan = {m for m in _metodos_del_protocolo() if not hasattr(FakeRepo, m)}
    nuevos = sorted(faltan - SIN_COBERTURA)
    assert not nuevos, (
        "estos métodos no están en FakeRepo, así que nada de lo que dependa de "
        f"ellos está realmente testeado: {nuevos}"
    )


def test_la_lista_de_deuda_esta_al_dia():
    """Si un método de SIN_COBERTURA ya se implementó, hay que sacarlo de la
    lista para que el chequeo siga siendo estricto."""
    faltan = {m for m in _metodos_del_protocolo() if not hasattr(FakeRepo, m)}
    ya_resueltos = sorted(SIN_COBERTURA - faltan)
    assert not ya_resueltos, f"sacar de SIN_COBERTURA: {ya_resueltos}"


def test_el_protocolo_no_tiene_implementaciones_pegadas():
    """Un método del Protocol con cuerpo es la señal de que una implementación
    se insertó en la clase equivocada."""
    import inspect
    import re

    fuente = inspect.getsource(Repo)
    con_cuerpo = [
        m.group(1) for m in re.finditer(r"^    def (\w+)\(self[^\n]*:\n(?!\s*\.\.\.)", fuente, re.M)
        if not m.group(0).rstrip().endswith("...")
    ]
    assert not con_cuerpo, (
        "estos métodos del Protocol tienen cuerpo; probablemente iban en "
        f"SupabaseRepo: {con_cuerpo}"
    )
