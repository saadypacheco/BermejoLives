"""El listado completo de comercios del panel (`list_todos_comercios`).

El 2/11/2026 el panel mostraba «5000 negocios» con 5932 activos: el tope era 5000
y las importaciones de ciudades lo pasaron. Además las importaciones crean miles de
filas con el mismo `created_at`, y paginar sólo por fecha podía repetir una fila en
dos páginas y saltear otra.
"""
from app.db.repository import LIMITE_COMERCIOS_TODOS, SupabaseRepo


class _Consulta:
    """Imita la cadena de PostgREST: ordena por las columnas pedidas y corta en 1000."""

    def __init__(self, filas):
        self._filas = filas
        self._orden = []
        self._desde, self._hasta = 0, None

    def select(self, *_a, **_k): return self
    def eq(self, *_a, **_k): return self

    def order(self, col, desc=False):
        self._orden.append((col, desc))
        return self

    def limit(self, n):
        self._desde, self._hasta = 0, n - 1
        return self

    def range(self, desde, hasta):
        self._desde, self._hasta = desde, hasta
        return self

    def execute(self):
        filas = list(self._filas)
        for col, desc in reversed(self._orden):
            filas.sort(key=lambda f: f[col], reverse=desc)
        if [c for c, _ in self._orden] == ["created_at"]:
            # Sin desempate, Postgres no garantiza el orden de las filas empatadas:
            # cada página puede venir en otro orden.
            filas.reverse() if self._desde % 2000 else None
        hasta = min(self._hasta, self._desde + 999)
        return type("R", (), {"data": filas[self._desde:hasta + 1]})()


class _Db:
    def __init__(self, filas):
        self._filas = filas

    def table(self, _nombre):
        return _Consulta(self._filas)


def _filas(n):
    # Todas con el mismo created_at, como una importación.
    return [{"id": f"{i:05d}", "created_at": "2026-10-20T10:00:00+00:00"} for i in range(n)]


def test_el_tope_alcanza_para_los_comercios_de_hoy():
    assert LIMITE_COMERCIOS_TODOS >= 10000


def test_pagina_sin_repetir_ni_perder_filas_con_el_mismo_created_at():
    repo = SupabaseRepo(client=_Db(_filas(5932)))
    filas = repo.list_todos_comercios(None, LIMITE_COMERCIOS_TODOS)
    ids = [f["id"] for f in filas]
    assert len(ids) == 5932
    assert len(set(ids)) == 5932


def test_no_devuelve_mas_que_el_limite_pedido():
    repo = SupabaseRepo(client=_Db(_filas(2500)))
    assert len(repo.list_todos_comercios(None, 1500)) == 1500
