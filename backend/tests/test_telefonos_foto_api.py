"""La API del panel «Teléfonos en fotos» (api/telefonos_foto.py): listar, resumen, aplicar, descartar y el lote.

Lo central: APLICAR va por el mismo camino que «Editar negocio» (`moderacion.editar_comercio`): la misma
validación del WhatsApp, el mismo permiso de cuenta, la misma clave anulada y el mismo registro de auditoría."""
import pytest
import structlog

from app.core import auth
from app.core.config import settings
from app.services import cost_switches
from tests.content_helpers import h


def token(*permisos, ciudad=None, email="mod@uruku.bo"):
    return h(auth.make_token(email, rol="x", roles=["x"], permisos=list(permisos), ciudad_slug=ciudad))


TODO = ("moderar", "comercios.editar", "comercios.cuenta")


@pytest.fixture
def moderador():
    return token(*TODO)


@pytest.fixture
def publicador():
    return token("moderar", "comercios.editar")             # sin `comercios.cuenta`


def comercio(repo, cid, **kw):
    base = {"id": cid, "slug": f"local-{cid}", "nombre": f"Local {cid}", "activo": True, "ciudad_id": "ciu-1",
            "whatsapp": None, "telefono": None, "portada_url": f"http://x/fotos/{cid}.jpg",
            "portada_thumb_url": f"http://x/fotos/{cid}-t.jpg"}
    base.update(kw)
    return repo.seed_comercio(**base)


def propuesta(trepo, cid, numero="+59170123456", tipo="celular", **kw):
    fila = {"comercio_id": cid, "numero": numero, "tipo": tipo, "texto_leido": numero[4:],
            "foto_url": f"http://x/fotos/{cid}.jpg", "motor": "tesseract", "estado": "pendiente", **kw}
    return trepo.insert_detectados([fila])[0]["id"]


URL = "/admin/telefonos-detectados"


# ═════════════════════════════════════════════════════════════ permisos

def test_sin_token_es_401_y_sin_moderar_es_403(client, repo, trepo):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1")
    assert client.get(URL).status_code in (401, 403)
    sin = token("comercios.editar", "comercios.cuenta")
    for r in (client.get(URL, headers=sin), client.get(f"{URL}/resumen", headers=sin),
              client.post(f"{URL}/{did}/descartar", headers=sin),
              client.post(f"{URL}/{did}/aplicar", json={"como": "telefono"}, headers=sin),
              client.post(f"{URL}/aplicar-lote", json={"ids": [did]}, headers=sin)):
        assert r.status_code == 403


def test_con_moderar_alcanza_para_ver_y_descartar_pero_aplicar_pide_tambien_editar(client, repo, trepo):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1")
    solo = token("moderar")
    assert client.get(URL, headers=solo).status_code == 200
    assert client.get(f"{URL}/resumen", headers=solo).status_code == 200
    assert client.post(f"{URL}/{did}/aplicar", json={"como": "telefono"}, headers=solo).status_code == 403
    assert client.post(f"{URL}/aplicar-lote", json={"ids": [did]}, headers=solo).status_code == 403
    assert repo.comercios["c1"]["telefono"] is None and trepo.detectados[did]["estado"] == "pendiente"
    assert client.post(f"{URL}/{did}/descartar", headers=solo).status_code == 200


def test_el_publicador_aplica_como_telefono_pero_no_como_whatsapp(client, repo, trepo, publicador):
    """Cambiar el WhatsApp es de la cuenta (`comercios.cuenta`), igual que en «Editar negocio»."""
    comercio(repo, "c1")
    did = propuesta(trepo, "c1")
    r = client.post(f"{URL}/{did}/aplicar", json={"como": "whatsapp"}, headers=publicador)
    assert r.status_code == 403 and "cuenta" in r.json()["detail"]
    assert repo.comercios["c1"]["whatsapp"] is None and trepo.detectados[did]["estado"] == "pendiente"
    r = client.post(f"{URL}/{did}/aplicar", json={"como": "telefono"}, headers=publicador)
    assert r.status_code == 200 and repo.comercios["c1"]["telefono"] == "+59170123456"


# ═════════════════════════════════════════════════════════════ listar

def test_el_listado_trae_el_shape_del_panel(client, repo, trepo, moderador):
    comercio(repo, "c1", whatsapp="59171111111", telefono="46612345")
    propuesta(trepo, "c1", "+59170123456", compartido=False)
    r = client.get(URL, headers=moderador)
    assert r.status_code == 200
    cuerpo = r.json()
    assert set(cuerpo) == {"items", "total"} and cuerpo["total"] == 1
    item = cuerpo["items"][0]
    assert set(item) == {"id", "comercio", "numero", "numero_visible", "tipo", "texto_leido", "foto_url",
                         "foto_thumb_url", "motor", "estado", "compartido", "otros_comercios"}
    assert item["comercio"] == {"id": "c1", "nombre": "Local c1", "slug": "local-c1", "whatsapp": "59171111111",
                                "telefono": "46612345", "ciudad": "Bermejo", "ciudad_slug": "bermejo"}
    assert item["numero"] == "+59170123456" and item["numero_visible"] == "+591 7012 3456"
    assert item["tipo"] == "celular" and item["motor"] == "tesseract" and item["estado"] == "pendiente"
    assert item["compartido"] is False and item["otros_comercios"] == 0
    assert item["foto_url"] == "http://x/fotos/c1.jpg" and item["foto_thumb_url"] == "http://x/fotos/c1-t.jpg"


def test_la_miniatura_solo_si_la_foto_sigue_siendo_la_portada(client, repo, trepo, moderador):
    comercio(repo, "c1")
    propuesta(trepo, "c1")
    repo.comercios["c1"]["portada_url"] = "http://x/fotos/nueva.jpg"
    assert client.get(URL, headers=moderador).json()["items"][0]["foto_thumb_url"] is None


def test_sin_estado_devuelve_todos_los_estados(client, repo, trepo, moderador):
    comercio(repo, "c1")
    for estado, numero in (("pendiente", "+59170000001"), ("coincide", "+59170000002"),
                           ("aplicado_whatsapp", "+59170000003"), ("aplicado_telefono", "+59170000004"),
                           ("descartado", "+59170000005")):
        propuesta(trepo, "c1", numero, estado=estado)
    todos = client.get(URL, headers=moderador).json()
    assert todos["total"] == 5 and {i["estado"] for i in todos["items"]} == {
        "pendiente", "coincide", "aplicado_whatsapp", "aplicado_telefono", "descartado"}
    solo = client.get(URL, params={"estado": "pendiente"}, headers=moderador).json()
    assert [i["numero"] for i in solo["items"]] == ["+59170000001"]


def test_un_estado_desconocido_es_400(client, moderador):
    assert client.get(URL, params={"estado": "inventado"}, headers=moderador).status_code == 400


def test_filtros_de_ciudad_y_sin_whatsapp(client, repo, trepo, moderador):
    comercio(repo, "sin", whatsapp=None)
    comercio(repo, "con", whatsapp="59171111111")
    comercio(repo, "scz", whatsapp=None, ciudad_id="ciu-santa-cruz")
    for cid, n in (("sin", "+59170000001"), ("con", "+59170000002"), ("scz", "+59170000003")):
        propuesta(trepo, cid, n)
    ids = lambda **p: sorted(i["comercio"]["id"] for i in client.get(URL, params=p, headers=moderador).json()["items"])
    assert ids() == ["con", "scz", "sin"]
    assert ids(sin_whatsapp="true") == ["scz", "sin"]
    assert ids(ciudad="bermejo") == ["con", "sin"]
    assert ids(ciudad="santa-cruz", sin_whatsapp="true") == ["scz"]
    assert client.get(URL, params={"ciudad": "narnia"}, headers=moderador).status_code == 404


def test_comercios_dados_de_baja_no_salen(client, repo, trepo, moderador):
    comercio(repo, "c1", activo=False)
    propuesta(trepo, "c1")
    assert client.get(URL, headers=moderador).json() == {"items": [], "total": 0}


def test_paginado(client, repo, trepo, moderador):
    comercio(repo, "c1")
    for i in range(7):
        propuesta(trepo, "c1", f"+5917000000{i}")
    p1 = client.get(URL, params={"limit": 3}, headers=moderador).json()
    p3 = client.get(URL, params={"limit": 3, "offset": 6}, headers=moderador).json()
    assert p1["total"] == 7 and len(p1["items"]) == 3 and len(p3["items"]) == 1
    assert client.get(URL, params={"limit": 0}, headers=moderador).status_code == 422
    assert client.get(URL, params={"limit": 201}, headers=moderador).status_code == 422
    assert client.get(URL, params={"offset": -1}, headers=moderador).status_code == 422


def test_otros_comercios_cuenta_a_los_demas_con_el_mismo_numero(client, repo, trepo, moderador):
    for cid in ("c1", "c2", "c3", "c4"):
        comercio(repo, cid)
        propuesta(trepo, cid, "+59170123456", compartido=True)
    comercio(repo, "c5")
    propuesta(trepo, "c5", "+59171234567")
    items = {i["comercio"]["id"]: i for i in client.get(URL, headers=moderador).json()["items"]}
    assert items["c1"]["otros_comercios"] == 3 and items["c1"]["compartido"] is True
    assert items["c5"]["otros_comercios"] == 0


def test_un_agente_limitado_a_su_ciudad_solo_ve_la_suya(client, repo, trepo):
    comercio(repo, "bermejo", ciudad_id="ciu-1")
    comercio(repo, "scz", ciudad_id="ciu-santa-cruz")
    propuesta(trepo, "bermejo", "+59170000001")
    propuesta(trepo, "scz", "+59170000002")
    de_scz = token(*TODO, ciudad="santa-cruz")
    r = client.get(URL, params={"ciudad": "bermejo"}, headers=de_scz).json()      # el ?ciudad= del cliente no cuenta
    assert [i["comercio"]["id"] for i in r["items"]] == ["scz"] and r["total"] == 1
    # su ciudad no existe en la base: no ve nada
    assert client.get(URL, headers=token(*TODO, ciudad="narnia")).json() == {"items": [], "total": 0}
    # el admin con alcance global sigue viendo las dos, aunque lleve una ciudad
    admin = h(auth.make_token("admin@x", rol="admin", ciudad_slug="santa-cruz"))
    assert client.get(URL, headers=admin).json()["total"] == 2


# ═════════════════════════════════════════════════════════════ resumen

def test_resumen_trae_los_cuatro_numeros_el_motor_y_el_worker(client, repo, trepo, crepo, moderador, monkeypatch):
    comercio(repo, "sin", whatsapp=None)
    comercio(repo, "con", whatsapp="59171111111")
    trepo.registrar_escaneada("http://x/fotos/con.jpg", "tesseract", "con", 0)
    propuesta(trepo, "sin", "+59170000001")
    propuesta(trepo, "sin", "+46612345".replace("+", "+591"), tipo="fijo")
    propuesta(trepo, "con", "+59170000002")
    r = client.get(f"{URL}/resumen", headers=moderador)
    assert r.status_code == 200
    assert r.json() == {"escaneadas": 1, "pendientes_de_escanear": 1, "numeros": 3, "sin_whatsapp_con_numero": 1,
                        "motor_activo": "tesseract", "worker": False, "tesseract_instalado": r.json()["tesseract_instalado"]}
    assert isinstance(r.json()["tesseract_instalado"], bool)


def test_resumen_motor_y_worker(client, crepo, moderador, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "k")
    monkeypatch.setattr(settings, "telefonos_foto_worker", True)
    cost_switches.set(crepo, cost_switches.GEMINI_PHONE_SCAN, True, "dueno@uruku.bo")
    r = client.get(f"{URL}/resumen", headers=moderador).json()
    assert r["motor_activo"] == "gemini" and r["worker"] is True


def test_resumen_por_ciudad(client, repo, trepo, moderador):
    comercio(repo, "b", whatsapp=None)
    comercio(repo, "s", whatsapp=None, ciudad_id="ciu-santa-cruz")
    propuesta(trepo, "b", "+59170000001")
    propuesta(trepo, "s", "+59170000002")
    assert client.get(f"{URL}/resumen", headers=moderador).json()["numeros"] == 2
    assert client.get(f"{URL}/resumen", params={"ciudad": "santa-cruz"}, headers=moderador).json()["numeros"] == 1
    assert client.get(f"{URL}/resumen", headers=token(*TODO, ciudad="bermejo")).json()["numeros"] == 1
    assert client.get(f"{URL}/resumen", params={"ciudad": "narnia"}, headers=moderador).status_code == 404


# ═════════════════════════════════════════════════════════════ aplicar

def test_aplicar_como_whatsapp_escribe_normalizado_y_marca_la_propuesta(client, repo, trepo, moderador):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1", "+59170123456")
    r = client.post(f"{URL}/{did}/aplicar", json={"como": "whatsapp"}, headers=moderador)
    assert r.status_code == 200
    assert r.json() == {"ok": True, "cambio": True, "estado": "aplicado_whatsapp",
                        "comercio": {"id": "c1", "whatsapp": "59170123456", "telefono": None}}
    assert repo.comercios["c1"]["whatsapp"] == "59170123456"
    d = trepo.detectados[did]
    assert d["estado"] == "aplicado_whatsapp" and d["revisado_por"] == "mod@uruku.bo" and d["revisado_at"]


def test_aplicar_como_telefono(client, repo, trepo, moderador):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1", "+59146612345", tipo="fijo")
    r = client.post(f"{URL}/{did}/aplicar", json={"como": "telefono"}, headers=moderador)
    assert r.status_code == 200 and r.json()["estado"] == "aplicado_telefono"
    assert repo.comercios["c1"]["telefono"] == "+59146612345" and repo.comercios["c1"]["whatsapp"] is None


def test_un_celular_tambien_se_puede_usar_como_telefono(client, repo, trepo, moderador):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1")
    assert client.post(f"{URL}/{did}/aplicar", json={"como": "telefono"}, headers=moderador).status_code == 200


def test_un_fijo_no_se_aplica_como_whatsapp_es_422(client, repo, trepo, moderador):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1", "+59146612345", tipo="fijo")
    r = client.post(f"{URL}/{did}/aplicar", json={"como": "whatsapp", "reemplazar": True}, headers=moderador)
    assert r.status_code == 422 and "fijo" in r.json()["detail"]
    assert repo.comercios["c1"]["whatsapp"] is None and trepo.detectados[did]["estado"] == "pendiente"


def test_aplicar_va_por_el_camino_de_editar_negocio_con_su_auditoria(client, repo, trepo, moderador):
    """El registro `moderacion.comercio_editado` sólo lo escribe `editar_comercio`: si aparece, es el mismo camino."""
    comercio(repo, "c1")
    did = propuesta(trepo, "c1")
    with structlog.testing.capture_logs() as logs:
        client.post(f"{URL}/{did}/aplicar", json={"como": "whatsapp"}, headers=moderador)
    editado = [l for l in logs if l["event"] == "moderacion.comercio_editado"]
    assert len(editado) == 1 and editado[0]["campos"] == ["whatsapp"] and editado[0]["by"] == "mod@uruku.bo"
    assert any(l["event"] == "telefonos_foto.aplicado" for l in logs)


def test_si_el_comercio_ya_tiene_otro_whatsapp_es_409_con_cual_es(client, repo, trepo, moderador):
    comercio(repo, "c1", whatsapp="59171111111")
    did = propuesta(trepo, "c1", "+59170123456")
    r = client.post(f"{URL}/{did}/aplicar", json={"como": "whatsapp"}, headers=moderador)
    assert r.status_code == 409 and "59171111111" in r.json()["detail"] and "reemplazar" in r.json()["detail"]
    assert repo.comercios["c1"]["whatsapp"] == "59171111111" and trepo.detectados[did]["estado"] == "pendiente"


def test_con_reemplazar_pisa_el_valor_y_anula_la_clave_como_al_editar_a_mano(client, repo, trepo, moderador):
    comercio(repo, "c1", whatsapp="59171111111")
    repo.usuarios["u1"] = {"id": "u1", "comercio_id": "c1", "clave_hash": "hash", "credenciales_version": 1,
                           "activo": True}
    did = propuesta(trepo, "c1", "+59170123456")
    r = client.post(f"{URL}/{did}/aplicar", json={"como": "whatsapp", "reemplazar": True}, headers=moderador)
    assert r.status_code == 200 and repo.comercios["c1"]["whatsapp"] == "59170123456"
    assert repo.usuarios["u1"]["clave_hash"] is None and repo.usuarios["u1"]["credenciales_version"] == 2


def test_si_el_comercio_ya_tiene_otro_telefono_tambien_es_409(client, repo, trepo, moderador):
    comercio(repo, "c1", telefono="46612345")
    did = propuesta(trepo, "c1", "+59146600000", tipo="fijo")
    r = client.post(f"{URL}/{did}/aplicar", json={"como": "telefono"}, headers=moderador)
    assert r.status_code == 409 and "46612345" in r.json()["detail"]
    assert client.post(f"{URL}/{did}/aplicar", json={"como": "telefono", "reemplazar": True},
                       headers=moderador).status_code == 200


def test_si_ya_es_el_valor_del_comercio_no_escribe_nada_y_queda_como_coincide(client, repo, trepo, moderador):
    comercio(repo, "c1", whatsapp="70123456")                    # guardado a la vieja, sin el 591
    did = propuesta(trepo, "c1", "+59170123456")
    with structlog.testing.capture_logs() as logs:
        r = client.post(f"{URL}/{did}/aplicar", json={"como": "whatsapp"}, headers=moderador)
    assert r.status_code == 200 and r.json()["cambio"] is False and r.json()["estado"] == "coincide"
    assert repo.comercios["c1"]["whatsapp"] == "70123456"
    assert not [l for l in logs if l["event"] == "moderacion.comercio_editado"]
    assert trepo.detectados[did]["estado"] == "coincide"


def test_un_numero_que_ya_es_de_otro_comercio_se_rechaza_como_al_editar(client, repo, trepo, moderador):
    """La regla de «Editar negocio»: colgar un comercio del WhatsApp de otro es la puerta del ataque de la clave."""
    comercio(repo, "c1")
    comercio(repo, "c2", whatsapp="59170123456")
    did = propuesta(trepo, "c1", "+59170123456")
    r = client.post(f"{URL}/{did}/aplicar", json={"como": "whatsapp"}, headers=moderador)
    assert r.status_code == 409 and "otro negocio" in r.json()["detail"]
    assert repo.comercios["c1"]["whatsapp"] is None and trepo.detectados[did]["estado"] == "pendiente"


def test_un_argentino_se_aplica_con_el_9_de_celular(client, repo, trepo, moderador):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1", "+5493878512345")
    assert client.post(f"{URL}/{did}/aplicar", json={"como": "whatsapp"}, headers=moderador).status_code == 200
    assert repo.comercios["c1"]["whatsapp"] == "5493878512345"


def test_aplicar_algo_ya_resuelto_es_409(client, repo, trepo, moderador):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1")
    client.post(f"{URL}/{did}/aplicar", json={"como": "telefono"}, headers=moderador)
    assert client.post(f"{URL}/{did}/aplicar", json={"como": "whatsapp"}, headers=moderador).status_code == 409
    did2 = propuesta(trepo, "c1", "+59171234567", estado="descartado")
    assert client.post(f"{URL}/{did2}/aplicar", json={"como": "whatsapp"}, headers=moderador).status_code == 409


def test_aplicar_con_cuerpo_invalido_es_422(client, repo, trepo, moderador):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1")
    for cuerpo in ({}, {"como": "email"}, {"como": 3}):
        assert client.post(f"{URL}/{did}/aplicar", json=cuerpo, headers=moderador).status_code == 422


def test_lo_que_no_existe_o_es_de_otra_ciudad_es_404(client, repo, trepo):
    comercio(repo, "scz", ciudad_id="ciu-santa-cruz")
    did = propuesta(trepo, "scz")
    de_bermejo = token(*TODO, ciudad="bermejo")
    for r in (client.post(f"{URL}/{did}/aplicar", json={"como": "telefono"}, headers=de_bermejo),
              client.post(f"{URL}/{did}/descartar", headers=de_bermejo),
              client.post(f"{URL}/no-existe/aplicar", json={"como": "telefono"}, headers=de_bermejo),
              client.post(f"{URL}/no-existe/descartar", headers=de_bermejo)):
        assert r.status_code == 404
    assert repo.comercios["scz"]["telefono"] is None and trepo.detectados[did]["estado"] == "pendiente"
    assert client.post(f"{URL}/{did}/aplicar", json={"como": "telefono"},
                       headers=token(*TODO, ciudad="santa-cruz")).status_code == 200


def test_un_comercio_dado_de_baja_es_404(client, repo, trepo, moderador):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1")
    repo.comercios["c1"]["activo"] = False
    assert client.post(f"{URL}/{did}/aplicar", json={"como": "telefono"}, headers=moderador).status_code == 404


# ═════════════════════════════════════════════════════════════ descartar

def test_descartar_marca_quien_y_cuando_y_no_toca_la_ficha(client, repo, trepo, moderador):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1")
    r = client.post(f"{URL}/{did}/descartar", headers=moderador)
    assert r.status_code == 200 and r.json() == {"ok": True, "estado": "descartado"}
    d = trepo.detectados[did]
    assert d["estado"] == "descartado" and d["revisado_por"] == "mod@uruku.bo" and d["revisado_at"]
    assert d["activo"] is True                                   # soft: la fila queda
    assert repo.comercios["c1"]["whatsapp"] is None
    assert client.post(f"{URL}/{did}/descartar", headers=moderador).status_code == 200      # idempotente


def test_no_se_descarta_lo_ya_aplicado(client, repo, trepo, moderador):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1")
    client.post(f"{URL}/{did}/aplicar", json={"como": "whatsapp"}, headers=moderador)
    assert client.post(f"{URL}/{did}/descartar", headers=moderador).status_code == 409
    assert trepo.detectados[did]["estado"] == "aplicado_whatsapp"


# ═════════════════════════════════════════════════════════════ lote

def test_el_lote_aplica_solo_lo_que_cumple_la_regla_y_dice_por_que_salteo_el_resto(client, repo, trepo, moderador):
    comercio(repo, "ok1")
    comercio(repo, "ok2")
    comercio(repo, "fijo")
    comercio(repo, "comp")
    comercio(repo, "tiene", whatsapp="59171111111")
    comercio(repo, "resuelto")
    comercio(repo, "scz", ciudad_id="ciu-santa-cruz")
    ids = {
        "ok1": propuesta(trepo, "ok1", "+59170000001"),
        "ok2": propuesta(trepo, "ok2", "+59170000002", estado="coincide"),          # coincide con el teléfono, sin whatsapp
        "fijo": propuesta(trepo, "fijo", "+59146612345", tipo="fijo"),
        "comp": propuesta(trepo, "comp", "+59170000003", compartido=True),
        "tiene": propuesta(trepo, "tiene", "+59170000004"),
        "resuelto": propuesta(trepo, "resuelto", "+59170000005", estado="descartado"),
        "scz": propuesta(trepo, "scz", "+59170000006"),
    }
    de_bermejo = token(*TODO, ciudad="bermejo")
    r = client.post(f"{URL}/aplicar-lote", json={"ids": [*ids.values(), "no-existe"]}, headers=de_bermejo)
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["aplicados"] == 2 and cuerpo["ids_aplicados"] == [ids["ok1"], ids["ok2"]]
    assert {s["id"]: s["motivo"] for s in cuerpo["saltados"]} == {
        ids["fijo"]: "no_celular", ids["comp"]: "compartido", ids["tiene"]: "tiene_whatsapp",
        ids["resuelto"]: "no_pendiente", ids["scz"]: "otra_ciudad", "no-existe": "no_existe"}
    assert repo.comercios["ok1"]["whatsapp"] == "59170000001" and repo.comercios["ok2"]["whatsapp"] == "59170000002"
    for cid in ("fijo", "comp", "resuelto", "scz"):
        assert repo.comercios[cid]["whatsapp"] is None
    assert repo.comercios["tiene"]["whatsapp"] == "59171111111"
    assert trepo.detectados[ids["ok1"]]["estado"] == "aplicado_whatsapp"


def test_los_motivos_del_lote_son_claves_cortas_en_snake_case():
    from app.api.telefonos_foto import MOTIVOS_LOTE
    import re
    assert all(re.fullmatch(r"[a-z]+(_[a-z]+)*", m) for m in MOTIVOS_LOTE)
    assert {"compartido", "tiene_whatsapp", "no_celular", "no_pendiente", "otra_ciudad", "no_existe"} <= set(MOTIVOS_LOTE)


def test_en_el_lote_el_segundo_numero_del_mismo_comercio_ya_ve_el_whatsapp_del_primero(client, repo, trepo, moderador):
    comercio(repo, "c1")
    a = propuesta(trepo, "c1", "+59170000001")
    b = propuesta(trepo, "c1", "+59170000002")
    r = client.post(f"{URL}/aplicar-lote", json={"ids": [a, b, a]}, headers=moderador).json()     # `a` repetido: una vez
    assert r["aplicados"] == 1 and r["saltados"] == [{"id": b, "motivo": "tiene_whatsapp"}]
    assert repo.comercios["c1"]["whatsapp"] == "59170000001"


def test_en_el_lote_un_numero_de_otro_comercio_se_saltea_con_su_motivo_y_el_detalle(client, repo, trepo, moderador):
    comercio(repo, "c1")
    comercio(repo, "c2", whatsapp="59170123456")
    did = propuesta(trepo, "c1", "+59170123456")
    r = client.post(f"{URL}/aplicar-lote", json={"ids": [did]}, headers=moderador).json()
    assert r["aplicados"] == 0 and r["saltados"][0]["motivo"] == "numero_en_uso"
    assert "otro negocio" in r["saltados"][0]["detalle"]


def test_en_el_lote_sin_comercios_cuenta_no_pasa_nada_y_dice_sin_permiso(client, repo, trepo, publicador):
    comercio(repo, "c1")
    did = propuesta(trepo, "c1")
    r = client.post(f"{URL}/aplicar-lote", json={"ids": [did]}, headers=publicador).json()
    assert r["aplicados"] == 0 and r["saltados"][0]["motivo"] == "sin_permiso"
    assert repo.comercios["c1"]["whatsapp"] is None


def test_el_lote_pide_ids_y_no_mas_de_100(client, repo, trepo, moderador):
    assert client.post(f"{URL}/aplicar-lote", json={"ids": []}, headers=moderador).status_code == 422
    assert client.post(f"{URL}/aplicar-lote", json={}, headers=moderador).status_code == 422
    assert client.post(f"{URL}/aplicar-lote", json={"ids": [str(i) for i in range(101)]},
                       headers=moderador).status_code == 422
    r = client.post(f"{URL}/aplicar-lote", json={"ids": [str(i) for i in range(100)]}, headers=moderador)
    assert r.status_code == 200 and len(r.json()["saltados"]) == 100


def test_las_rutas_no_se_pisan(client, repo, trepo, moderador):
    """`/resumen` y `/aplicar-lote` no son un `{id}`."""
    assert client.get(f"{URL}/resumen", headers=moderador).status_code == 200
    assert client.post(f"{URL}/aplicar-lote", json={"ids": ["x"]}, headers=moderador).status_code == 200
