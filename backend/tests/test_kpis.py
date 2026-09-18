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


def test_la_vista_guarda_de_donde_llego(client, repo):
    """El ?ref= del QR (volante, mesa, ficha) queda en la fila de la vista;
    lo raro se limpia y lo vacío no se guarda. Es lo que dice después si las
    tarjetas de mesa trajeron a alguien."""
    client.post("/lead", json={"comercio_id": "c1", "tipo": "vista", "origen": "mesa-rustico"})
    assert repo.leads[-1]["origen"] == "mesa-rustico"
    client.post("/lead", json={"comercio_id": "c1", "tipo": "vista", "origen": "  VOLANTE-Rustico "})
    assert repo.leads[-1]["origen"] == "volante-rustico"
    client.post("/lead", json={"comercio_id": "c1", "tipo": "vista"})
    assert "origen" not in repo.leads[-1]


def test_te_contesto_cuenta_por_comercio_y_una_sola_vez(client, repo):
    """El clic devuelve un id; con ese id el comprador dice si le contestaron.
    Una sola vez por contacto, y el comercio suma sí/no."""
    repo.comercios["c1"] = {"id": "c1", "slug": "c1", "nombre": "C1", "activo": True}
    r = client.post("/lead", json={"comercio_id": "c1", "tipo": "whatsapp"}).json()
    assert r["id"]
    ok = client.post(f"/lead/{r['id']}/respondio", json={"respondio": False}).json()
    assert ok == {"ok": True, "contacto_ok": 0, "contacto_no": 1}
    assert repo.comercios["c1"]["contacto_no"] == 1
    # Otra vez el mismo contacto: no suma.
    assert client.post(f"/lead/{r['id']}/respondio", json={"respondio": False}).json()["ya"] is True
    assert repo.comercios["c1"]["contacto_no"] == 1
    # Una vista no es un contacto: no se pregunta.
    v = client.post("/lead", json={"comercio_id": "c1", "tipo": "vista"}).json()
    assert client.post(f"/lead/{v['id']}/respondio", json={"respondio": True}).status_code == 404
    assert client.post("/lead/no-existe/respondio", json={"respondio": True}).status_code == 404
