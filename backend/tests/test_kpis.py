"""KPIs del admin: log de búsquedas + agregados."""
from app.core import auth


def _admin():
    return {"Authorization": f"Bearer {auth.make_token('admin@bermejolive.com', rol='admin')}"}


def test_log_busqueda_y_kpis(client, repo):
    client.post("/busquedas/log", json={"query": "zapatillas", "resultados": 3})
    client.post("/busquedas/log", json={"query": "Zapatillas ", "resultados": 3})  # se normaliza
    client.post("/busquedas/log", json={"query": "sushi", "resultados": 0})
    r = client.get("/admin/kpis", headers=_admin())
    assert r.status_code == 200
    data = r.json()
    top = {b["query"]: b["n"] for b in data["top_busquedas"]}
    assert top.get("zapatillas") == 2
    assert "sushi" in {b["query"] for b in data["sin_resultado"]}
    assert "monetizacion" in data and "pagando" in data["monetizacion"]


def test_kpis_sin_auth_401(client):
    assert client.get("/admin/kpis").status_code == 401


def test_log_busqueda_corta_ignora(client, repo):
    client.post("/busquedas/log", json={"query": "a", "resultados": 0})
    assert repo.busquedas == []


def test_vista_como_lead(client, repo):
    r = client.post("/lead", json={"comercio_id": "c1", "tipo": "vista"})
    assert r.status_code == 200 and repo.leads[-1]["tipo"] == "vista"
