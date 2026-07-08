"""Tests de observabilidad: endpoints públicos + dedupe por fingerprint.

Se monkeypatchea get_supabase() con un fake mínimo en memoria — no requiere
Supabase real (mismo espíritu que el resto de la suite con FakeRepo).
"""
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import observabilidad


class _FakeQuery:
    def __init__(self, table, op, payload=None):
        self.table = table
        self.op = op
        self.payload = payload
        self._filters: list[tuple[str, str, object]] = []
        self._limit = None

    def eq(self, col, val):
        self._filters.append(("eq", col, val))
        return self

    def lt(self, col, val):
        self._filters.append(("lt", col, val))
        return self

    def limit(self, n):
        self._limit = n
        return self

    def _matches(self, row):
        for op, col, val in self._filters:
            if op == "eq" and row.get(col) != val:
                return False
            if op == "lt" and not (row.get(col) is not None and row[col] < val):
                return False
        return True

    def execute(self):
        rows = self.table._rows
        if self.op == "insert":
            row = {**self.payload, "id": f"id-{len(rows) + 1}"}
            rows.append(row)
            return type("R", (), {"data": [row]})()
        if self.op == "select":
            matched = [r for r in rows if self._matches(r)]
            if self._limit:
                matched = matched[: self._limit]
            return type("R", (), {"data": matched})()
        if self.op == "update":
            matched = [r for r in rows if self._matches(r)]
            for r in matched:
                r.update(self.payload)
            return type("R", (), {"data": matched})()
        if self.op == "delete":
            matched = [r for r in rows if self._matches(r)]
            for r in matched:
                rows.remove(r)
            return type("R", (), {"data": matched})()
        raise AssertionError(self.op)


class _FakeTable:
    def __init__(self):
        self._rows: list[dict] = []

    def insert(self, payload):
        return _FakeQuery(self, "insert", payload)

    def select(self, *_a, **_kw):
        return _FakeQuery(self, "select")

    def update(self, payload):
        return _FakeQuery(self, "update", payload)

    def delete(self):
        return _FakeQuery(self, "delete")


class FakeSupabase:
    def __init__(self):
        self._tables: dict[str, _FakeTable] = {}

    def table(self, name):
        return self._tables.setdefault(name, _FakeTable())


@pytest.fixture
def fake_db(monkeypatch):
    db = FakeSupabase()
    monkeypatch.setattr(observabilidad, "get_supabase", lambda: db)
    return db


@pytest.fixture
def client():
    return TestClient(app)


def test_registrar_error_agrupa_por_fingerprint(fake_db):
    observabilidad.registrar_error("frontend", "boom", ruta="/x")
    observabilidad.registrar_error("frontend", "boom", ruta="/x")
    rows = fake_db.table("error_logs")._rows
    assert len(rows) == 1
    assert rows[0]["ocurrencias"] == 2


def test_registrar_error_distinto_mensaje_no_agrupa(fake_db):
    observabilidad.registrar_error("frontend", "boom", ruta="/x")
    observabilidad.registrar_error("frontend", "otro error", ruta="/x")
    assert len(fake_db.table("error_logs")._rows) == 2


def test_post_errores_no_falla_aunque_db_explote(client, monkeypatch):
    def _explota():
        raise RuntimeError("sin credenciales")

    monkeypatch.setattr(observabilidad, "get_supabase", _explota)
    res = client.post("/errores", json={"mensaje": "algo falló", "ruta": "/mapa"})
    assert res.status_code == 200
    assert res.json() == {"ok": True}


def test_post_metricas_guarda_evento(client, fake_db):
    res = client.post("/metricas", json={"ruta": "/", "metrica": "lcp", "valor_ms": 1800})
    assert res.status_code == 200
    rows = fake_db.table("perf_events")._rows
    assert len(rows) == 1
    assert rows[0]["metrica"] == "lcp"


def test_endpoint_no_autenticado_no_cuenta_rate_limit_de_auth(client, fake_db):
    for _ in range(25):
        res = client.post("/errores", json={"mensaje": "x"})
        assert res.status_code == 200
