"""Endpoints del panel que no tenía nadie probando.

Salieron a la luz cuando /admin/reclamos y /admin/solicitudes-cambio-numero
empezaron a devolver 500 en producción: eran justamente los únicos que ningún
test tocaba. Todo lo que se ejercita acá pasa por el mismo camino que usa el
panel — misma ruta, mismo rol, misma forma de respuesta.
"""
from datetime import date, timedelta

import pytest


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _fecha(dias: int) -> str:
    return (date.today() + timedelta(days=dias)).isoformat()


# ══════════════════════════════════════════════════════════ reclamos
def test_listar_reclamos_vacio_no_rompe(client, repo, admin_token):
    r = client.get("/admin/reclamos", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() == {"items": [], "total": 0}


def test_listar_reclamos_devuelve_items_y_total(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True)
    repo.crear_reclamo({"comercio_id": c["id"], "texto": "No atendieron"})

    r = client.get("/admin/reclamos", headers=_h(admin_token))
    body = r.json()
    assert r.status_code == 200
    assert body["total"] == 1
    assert body["items"][0]["texto"] == "No atendieron"


def test_filtrar_reclamos_por_estado(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True)
    uno = repo.crear_reclamo({"comercio_id": c["id"], "texto": "a"})
    repo.crear_reclamo({"comercio_id": c["id"], "texto": "b"})
    repo.responder_reclamo(uno["id"], "resuelto", "admin@x")

    pendientes = client.get("/admin/reclamos?estado=pendiente", headers=_h(admin_token)).json()
    assert pendientes["total"] == 1
    assert pendientes["items"][0]["texto"] == "b"


def test_responder_reclamo(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True)
    rec = repo.crear_reclamo({"comercio_id": c["id"], "texto": "No atendieron"})

    r = client.post(f"/admin/reclamos/{rec['id']}/responder",
                    json={"respuesta": "Ya se contactaron"}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.reclamos[rec["id"]]["estado"] == "respondido"


def test_responder_reclamo_inexistente_da_404(client, repo, admin_token):
    r = client.post("/admin/reclamos/no-existe/responder",
                    json={"respuesta": "x"}, headers=_h(admin_token))
    assert r.status_code == 404


def test_reclamos_requiere_admin(client, repo):
    assert client.get("/admin/reclamos").status_code in (401, 403)


# ═══════════════════════════════════════ solicitudes de cambio de número
def test_listar_solicitudes_vacio_no_rompe(client, repo, admin_token):
    r = client.get("/admin/solicitudes-cambio-numero", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json() == {"items": [], "total": 0}


def test_aprobar_solicitud_cambia_el_whatsapp_del_comercio(client, repo, admin_token):
    """Es el efecto que importa: aprobar no marca un estado, cambia el número por
    el que le van a llegar las reservas."""
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", whatsapp="59170000001", activo=True)
    sol = repo.crear_solicitud_cambio_numero({"comercio_id": c["id"], "whatsapp_nuevo": "59170000002"})

    r = client.post(f"/admin/solicitudes-cambio-numero/{sol['id']}/aprobar", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.comercios[c["id"]]["whatsapp"] == "59170000002"
    assert repo.solicitudes_numero[sol["id"]]["estado"] == "aprobada"


def test_rechazar_solicitud_no_toca_el_whatsapp(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", whatsapp="59170000001", activo=True)
    sol = repo.crear_solicitud_cambio_numero({"comercio_id": c["id"], "whatsapp_nuevo": "59170000002"})

    r = client.post(f"/admin/solicitudes-cambio-numero/{sol['id']}/rechazar", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.comercios[c["id"]]["whatsapp"] == "59170000001"
    assert repo.solicitudes_numero[sol["id"]]["estado"] == "rechazada"


def test_aprobar_solicitud_inexistente_da_404(client, repo, admin_token):
    r = client.post("/admin/solicitudes-cambio-numero/no-existe/aprobar", headers=_h(admin_token))
    assert r.status_code == 404


def test_solicitudes_requiere_admin(client, repo):
    assert client.get("/admin/solicitudes-cambio-numero").status_code in (401, 403)


# ══════════════════════════════════════════════════════ suscripciones
def test_listar_suscripciones_vacio_no_rompe(client, repo, admin_token):
    r = client.get("/admin/suscripciones", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 0


@pytest.mark.parametrize("kwargs,esperado", [
    ({},                                             "sin_plan"),
    ({"paga_hasta": None},                           "sin_plan"),
    ({"paga_hasta": "2020-01-01"},                   "vencido"),
    ({"suspendido": True, "paga_hasta": "2099-01-01"}, "suspendido"),
])
def test_estado_de_suscripcion(client, repo, admin_token, kwargs, esperado):
    repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True, **kwargs)
    items = client.get("/admin/suscripciones", headers=_h(admin_token)).json()["items"]
    assert items[0]["suscripcion_estado"] == esperado


def test_suscripcion_al_dia_y_por_vencer(client, repo, admin_token):
    repo.seed_comercio(slug="a", nombre="Al día", paga_hasta=_fecha(60), activo=True)
    repo.seed_comercio(slug="b", nombre="Por vencer", paga_hasta=_fecha(2), activo=True)

    por_slug = {c["slug"]: c["suscripcion_estado"]
                for c in client.get("/admin/suscripciones", headers=_h(admin_token)).json()["items"]}
    assert por_slug["a"] == "activo"
    assert por_slug["b"] == "por_vencer"


def test_suscripciones_ignora_los_dados_de_baja(client, repo, admin_token):
    repo.seed_comercio(slug="baja", nombre="De baja", activo=False)
    assert client.get("/admin/suscripciones", headers=_h(admin_token)).json()["total"] == 0


# ═════════════════════════════════════════ suspender / activar comercio
def test_suspender_y_reactivar(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True)

    client.post(f"/admin/comercio/{c['id']}/suspender", headers=_h(admin_token))
    assert repo.comercios[c["id"]]["suspendido"] is True

    client.post(f"/admin/comercio/{c['id']}/activar", headers=_h(admin_token))
    assert repo.comercios[c["id"]]["suspendido"] is False
    assert repo.comercios[c["id"]]["activo"] is True


def test_suspender_requiere_admin(client, repo):
    assert client.post("/admin/comercio/x/suspender").status_code in (401, 403)


# ═══════════════════════════════════════════════════════ estadísticas
def test_estadisticas_devuelve_la_forma_que_el_panel_espera(client, repo, admin_token):
    """El panel lee estas claves directo; si alguna falta, la pantalla se rompe."""
    repo.seed_comercio(slug="x", nombre="Casa Pepe", activo=True)

    r = client.get("/admin/estadisticas", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    body = r.json()
    for clave in ["comercios_nuevos_7d", "comercios_nuevos_30d", "alertas",
                  "ofertas_total", "ofertas_top_comercios", "contactos_30d",
                  "contactos_top_comercios"]:
        assert clave in body, f"el panel espera '{clave}' y no viene"
    for alerta in ["vencido", "suspendido", "por_vencer"]:
        assert alerta in body["alertas"]


def test_estadisticas_requiere_admin(client, repo):
    assert client.get("/admin/estadisticas").status_code in (401, 403)


# ════════════════════════════════════════════ búsqueda pública por nombre
def test_buscar_comercio_por_nombre(client, repo):
    """Sin login: la usa el dueño que perdió el acceso a su número."""
    repo.seed_comercio(slug="x", nombre="Ferretería Roque", activo=True)
    repo.seed_comercio(slug="y", nombre="Panadería Sol", activo=True)

    items = client.get("/comercio/buscar?q=ferre").json()["items"]
    assert len(items) == 1 and items[0]["slug"] == "x"


def test_buscar_ignora_mayusculas(client, repo):
    repo.seed_comercio(slug="x", nombre="Ferretería Roque", activo=True)
    assert len(client.get("/comercio/buscar?q=FERRE").json()["items"]) == 1


def test_buscar_exige_minimo_dos_letras(client, repo):
    assert client.get("/comercio/buscar?q=a").status_code == 422
