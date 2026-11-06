"""Admin de la integración (alcance por comercio) y ciclo de vida de las API keys."""
from __future__ import annotations

import json
import uuid

import pytest

from app.core import auth
from app.services import integracion


@pytest.fixture
def cli(repo):
    return integracion.emitir_clave(repo, "Marketing", None, "test")


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _comercio(repo, **kw):
    cid = str(uuid.uuid4())
    return repo.seed_comercio(id=cid, slug=kw.pop("slug", f"c-{cid[:6]}"), nombre=kw.pop("nombre", "Comercio"), activo=True, **kw)


# ═════════════════════════════════════════════════════ permisos
def test_el_admin_de_integracion_pide_ser_admin(client, repo, cli):
    moderador = auth.make_token("mod@x.com", rol="moderador")
    for ruta in (f"/admin/integracion/clientes", f"/admin/integracion/clientes/{cli['grupo_id']}/comercios"):
        assert client.get(ruta).status_code == 401
        assert client.get(ruta, headers=_h(moderador)).status_code == 403
    r = client.post(f"/admin/integracion/clientes/{cli['grupo_id']}/comercios", headers=_h(moderador),
                    json={"comercio_ids": [str(uuid.uuid4())]})
    assert r.status_code == 403


def test_listar_clientes_nunca_muestra_el_hash_ni_el_secreto(client, repo, cli, admin_token):
    r = client.get("/admin/integracion/clientes", headers=_h(admin_token))
    assert r.status_code == 200
    assert [i["key_id"] for i in r.json()["items"]] == [cli["key_id"]]
    assert "key_hash" not in r.text and cli["clave"].split(".")[1] not in r.text


# ═════════════════════════════════════════════════════ alcance
def test_agregar_y_quitar_comercios_del_alcance_deja_rastro(client, repo, cli, admin_token):
    a, b = _comercio(repo, slug="a"), _comercio(repo, slug="b")
    ruta = f"/admin/integracion/clientes/{cli['grupo_id']}/comercios"
    r = client.post(ruta, headers=_h(admin_token), json={"comercio_ids": [a["id"], b["id"], a["id"]]})
    assert r.status_code == 200 and r.json() == {"agregados": [a["id"], b["id"]], "ya_estaban": []}
    assert repo.es_comercio_gestionado(a["id"]) and repo.es_comercio_gestionado(b["id"])
    assert client.post(ruta, headers=_h(admin_token), json={"comercio_ids": [a["id"]]}).json() == {"agregados": [], "ya_estaban": [a["id"]]}
    listado = client.get(ruta, headers=_h(admin_token)).json()
    assert {i["slug"] for i in listado["items"]} == {"a", "b"} and all(i["en_alcance"] for i in listado["items"])
    r = client.delete(f"{ruta}/{a['id']}", headers=_h(admin_token))
    assert r.status_code == 200 and not repo.es_comercio_gestionado(a["id"]) and repo.es_comercio_gestionado(b["id"])
    assert client.delete(f"{ruta}/{a['id']}", headers=_h(admin_token)).status_code == 404            # ya no estaba
    tipos = [e["tipo"] for e in repo.integ_eventos]
    assert tipos == ["clave_emitida", "alcance_agregado", "alcance_agregado", "alcance_quitado"]
    assert all(e["actor"] == "admin@bermejolive.com" for e in repo.integ_eventos[1:])
    # y quitado se puede volver a agregar (baja lógica, no borrado)
    assert client.post(ruta, headers=_h(admin_token), json={"comercio_ids": [a["id"]]}).json()["agregados"] == [a["id"]]


def test_alcance_valida_cliente_y_comercios(client, repo, cli, admin_token):
    ruta = f"/admin/integracion/clientes/{cli['grupo_id']}/comercios"
    assert client.post(ruta, headers=_h(admin_token), json={"comercio_ids": [str(uuid.uuid4())]}).status_code == 404
    assert client.post(ruta, headers=_h(admin_token), json={"comercio_ids": ["nope"]}).status_code == 422
    assert client.post(ruta, headers=_h(admin_token), json={"comercio_ids": []}).status_code == 422
    assert client.post(f"/admin/integracion/clientes/{uuid.uuid4()}/comercios", headers=_h(admin_token),
                       json={"comercio_ids": [str(uuid.uuid4())]}).status_code == 404
    assert client.get("/admin/integracion/clientes/xyz/comercios", headers=_h(admin_token)).status_code == 404


def test_la_clave_rotada_comparte_el_alcance_del_cliente(client, repo, cli, admin_token):
    a = _comercio(repo, slug="a")
    client.post(f"/admin/integracion/clientes/{cli['grupo_id']}/comercios", headers=_h(admin_token), json={"comercio_ids": [a["id"]]})
    nueva = integracion.rotar_clave(repo, cli["key_id"], "test")
    for clave in (cli["clave"], nueva["clave"]):
        r = client.get("/v1/integration/me", headers=_h(clave))
        assert r.status_code == 200 and r.json()["comercios"] == [a["id"]]
    assert nueva["grupo_id"] == cli["grupo_id"]
    # el alcance se administra por el cliente (grupo), no por la clave rotada
    assert client.get(f"/admin/integracion/clientes/{nueva['cliente_id']}/comercios", headers=_h(admin_token)).status_code == 404


def test_agregar_verificados_arma_el_piloto_sin_exponer_el_dato(client, repo, cli, admin_token):
    v1 = _comercio(repo, slug="v1", nombre="Verificado uno", verificado=True, codigo="AAAA")
    v2 = _comercio(repo, slug="v2", nombre="Verificado dos", verificado=True)
    _comercio(repo, slug="no", nombre="Sin verificar", verificado=False)
    baja = _comercio(repo, slug="baja", verificado=True)
    baja["activo"] = False
    ruta = f"/admin/integracion/clientes/{cli['grupo_id']}/comercios/verificados"
    sim = client.post(f"{ruta}?simular=true", headers=_h(admin_token)).json()
    assert sim["simulado"] is True and sim["agregados"] == 2 and not repo.es_comercio_gestionado(v1["id"])
    r = client.post(ruta, headers=_h(admin_token)).json()
    assert r["agregados"] == 2 and {c["slug"] for c in r["comercios"]} == {"v1", "v2"}
    assert repo.es_comercio_gestionado(v1["id"]) and repo.es_comercio_gestionado(v2["id"])
    assert client.post(ruta, headers=_h(admin_token)).json()["agregados"] == 0          # idempotente
    assert "AAAA" not in json.dumps(r) and "verificado" not in json.dumps(r).replace("Verificado", "")
    # y la integración ve «los comercios que me asignaron», sin saber por qué
    items = client.get("/v1/integration/merchants", headers=_h(cli["clave"])).json()["items"]
    assert {i["slug"] for i in items} == {"v1", "v2"} and all("verificado" not in i for i in items)


# ═════════════════════════════════════════════════════ claves
def test_emitir_muestra_el_secreto_una_vez_y_guarda_solo_el_hash(repo):
    r = integracion.emitir_clave(repo, "Marketing", ["publications:read"], "test")
    assert r["clave"].startswith("uki_") and r["key_id"] in r["clave"] and r["scopes"] == ["publications:read"]
    secreto = r["clave"].split(".", 1)[1]
    guardado = repo.integracion_cliente_por_key_id(r["key_id"])
    assert guardado["key_hash"] == integracion.hash_secreto(secreto) and secreto not in json.dumps(guardado)
    assert repo.integ_eventos[-1]["tipo"] == "clave_emitida" and secreto not in json.dumps(repo.integ_eventos)
    assert integracion.emitir_clave(repo, "Otra", None, "t")["clave"] != r["clave"]


def test_emitir_valida_nombre_y_scopes(repo):
    with pytest.raises(ValueError):
        integracion.emitir_clave(repo, "", None, "t")
    with pytest.raises(ValueError):
        integracion.emitir_clave(repo, "x", ["publications:read", "admin:todo"], "t")


def test_rotar_deja_dos_activas_y_revocar_corta_la_vieja(client, repo, cli):
    nueva = integracion.rotar_clave(repo, cli["key_id"], "test")
    assert nueva["reemplaza"] == cli["key_id"] and nueva["scopes"] == cli["scopes"] and nueva["clave"] != cli["clave"]
    assert repo.integracion_cliente_por_key_id(nueva["key_id"])["rotada_de"] == repo.integracion_cliente_por_key_id(cli["key_id"])["id"]
    assert client.get("/v1/integration/me", headers=_h(cli["clave"])).status_code == 200      # las dos andan
    assert client.get("/v1/integration/me", headers=_h(nueva["clave"])).status_code == 200
    assert integracion.revocar_clave(repo, cli["key_id"], "test") == {"key_id": cli["key_id"], "ya_revocada": False}
    assert client.get("/v1/integration/me", headers=_h(cli["clave"])).status_code == 401
    assert client.get("/v1/integration/me", headers=_h(nueva["clave"])).status_code == 200
    assert integracion.revocar_clave(repo, cli["key_id"], "test")["ya_revocada"] is True
    with pytest.raises(ValueError):
        integracion.rotar_clave(repo, cli["key_id"], "test")                                   # no se rota una revocada
    with pytest.raises(ValueError):
        integracion.revocar_clave(repo, "noexiste", "test")
    assert [e["tipo"] for e in repo.integ_eventos] == ["clave_emitida", "clave_rotada", "clave_revocada"]


def test_el_script_emite_rota_revoca_y_lista(repo, monkeypatch, capsys):
    from scripts import integracion_clave

    monkeypatch.setattr(integracion_clave, "get_repo", lambda: repo)
    assert integracion_clave.main(["emitir", "--nombre", "Marketing"]) == 0
    salida = capsys.readouterr().out
    clave = next(l.strip() for l in salida.splitlines() if l.strip().startswith("uki_"))
    key_id = clave.split("_", 1)[1].split(".", 1)[0]
    assert "no se vuelve a mostrar" in salida
    assert integracion_clave.main(["rotar", "--key-id", key_id]) == 0
    assert "SIGUE activa" in capsys.readouterr().out
    assert integracion_clave.main(["revocar", "--key-id", key_id]) == 0
    assert integracion_clave.main(["listar"]) == 0
    listado = capsys.readouterr().out
    assert "revocada" in listado and "activa" in listado and "uki_" not in listado           # el listado nunca imprime claves
    assert integracion_clave.main(["revocar", "--key-id", "inexistente"]) == 1
