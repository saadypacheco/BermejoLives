


# ── El puente búsqueda → contacto ───────────────────────────────────────────
# Sin él se sabe qué se mostró y qué se contactó, pero no si una cosa llevó a la
# otra — que es justo lo que dice si el buscador sirve.

def test_el_log_devuelve_el_id_para_atarle_el_click(client, repo):
    r = client.post("/busquedas/log",
                    json={"query": "ferreteria", "resultados": 3, "comercios": []})
    assert r.status_code == 200
    assert r.json().get("busqueda_id")


def test_el_contacto_guarda_de_que_busqueda_salio(client, repo):
    bid = client.post("/busquedas/log",
                      json={"query": "termo", "resultados": 5}).json()["busqueda_id"]
    cid = repo.crear_comercio_min("Bazar Lidia") if hasattr(repo, "crear_comercio_min") else None
    comercio_id = cid or next(iter(repo.comercios), "c1")

    r = client.post("/lead", json={"comercio_id": comercio_id, "tipo": "whatsapp",
                                   "busqueda_id": bid})
    assert r.status_code == 200
    assert repo.leads[-1]["busqueda_id"] == bid


def test_un_contacto_sin_busqueda_sigue_valiendo(client, repo):
    """Llegar por el mapa, la home o un link compartido no es un dato faltante:
    es otro camino, y tiene que registrarse igual."""
    comercio_id = next(iter(repo.comercios), "c1")
    r = client.post("/lead", json={"comercio_id": comercio_id, "tipo": "whatsapp"})
    assert r.status_code == 200
    assert repo.leads[-1].get("busqueda_id") is None


def test_una_busqueda_muy_corta_no_se_loguea(client, repo):
    antes = len(repo.busquedas)
    r = client.post("/busquedas/log", json={"query": "a", "resultados": 0})
    assert r.status_code == 200
    assert r.json().get("busqueda_id") is None
    assert len(repo.busquedas) == antes
