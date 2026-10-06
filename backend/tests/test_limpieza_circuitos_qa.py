"""QA adversarial de la «Limpieza de circuitos» (docs/limpieza-circuitos.md).

Complementa `test_limpieza_circuitos.py` (el del dev) sin repetirlo: acá se
rompen los circuitos de ingreso con entradas raras (formatos de número, números
ajenos, códigos vencidos o reusados, mensajes vacíos) y se verifican los
criterios 1-8 desde afuera.

Los tests marcados `xfail(strict=True)` son BUGS encontrados: describen el
comportamiento esperado y hoy fallan. Cuando se arreglen el test pasa a XPASS y
`strict` lo hace fallar, que es la señal para sacarle la marca.
"""
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from app.core.config import settings
from app.services import ingest, revision_ia

DESCONOCIDO = "59199988877"


# ───────────────────────────────────────────────────────────────── helpers
def _wh(wamid, de, body="", tipo="text", media=False, extra=None):
    """Un mensaje 1 a 1 tal como lo manda WAHA."""
    payload = {"id": wamid, "from": f"{de}@c.us", "fromMe": False, "body": body,
               "type": tipo, "hasMedia": media, "timestamp": 1700000000}
    if media:
        payload.update({"mediaUrl": "https://x/f.jpg", "mimetype": "image/jpeg"})
    payload.update(extra or {})
    return {"event": "message", "session": "obs@c.us", "payload": payload}


def _confirmar(repo, desde, codigo, wamid=None, **kw):
    return ingest.handle_message(
        _wh(wamid or f"conf-{desde}-{codigo}", desde, f"CONFIRMAR-{codigo}", **kw), repo)


def _foto():
    buf = BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="JPEG")
    buf.seek(0)
    return {"foto": ("test.jpg", buf, "image/jpeg")}


def _alta_de_campo(client, whatsapp="70002222", nombre="Gomería El Rápido"):
    token = client.post("/auth/campo/login", json={"email": "agente@bermejolive.com",
                                                   "password": "campo1234"}).json()["access_token"]
    datos = {"nombre": nombre, "modalidad": "minorista", "lat": "-22.7361", "lng": "-64.3433"}
    if whatsapp is not None:
        datos["whatsapp"] = whatsapp
    r = client.post("/campo/comercio", headers={"Authorization": f"Bearer {token}"},
                    data=datos, files=_foto())
    assert r.status_code == 200, r.text
    return r.json()["comercio"]


def _nada_creado(repo):
    assert repo.comercios == {}, f"se creó un comercio fantasma: {list(repo.comercios.values())}"
    assert repo.publicaciones == []
    assert repo.comercio_numeros == []
    assert repo.usuarios == {}


# ═════════════════════════════════════════ 1. FANTASMA: 1 a 1 de un desconocido
@pytest.mark.parametrize("body,tipo,media", [
    ("Hola, buen día", "text", False),
    ("", "text", False),
    (None, "text", False),
    ("   \n  ", "text", False),
    (None, "image", True),                                  # sólo foto, sin texto
    ("Campera Bs 300", "image", True),                      # foto con precio
    ("URUKU-ZZZZ", "text", False),                          # código que no existe
    ("URUKU-ZZZZ taladro Bs 300", "image", True),           # código inexistente + foto
    ("https://tiktok.com/@x/video/9", "text", False),       # video
    ("uruku zzzz", "text", False),                          # código mal escrito
    ("' OR 1=1 --; <script>alert(1)</script>", "text", False),  # entrada maliciosa
    ("A" * 20000, "text", False),                           # texto enorme
])
def test_un_desconocido_sin_codigo_valido_no_crea_nada(repo, body, tipo, media):
    repo.seed_comercio(id="com-x", slug="x", nombre="X", codigo="K7M2", activo=True,
                       whatsapp="59170000009")
    res = ingest.handle_message(_wh("w-f", DESCONOCIDO, body, tipo, media), repo)
    assert res["captured"] is True and res["publicada"] is False
    assert list(repo.comercios) == ["com-x"]
    assert repo.publicaciones == []
    assert [n["numero"] for n in repo.comercio_numeros] == []
    fila = repo.wa_inbox["w-f"]
    assert fila["resultado"] == "sin_comercio"
    assert fila["motivo"]                                    # con un motivo claro
    assert fila["procesado"] is True


def test_una_ubicacion_de_un_desconocido_tampoco_crea_nada(repo):
    ev = _wh("w-loc", DESCONOCIDO, "", "location",
             extra={"location": {"latitude": -22.7, "longitude": -64.3, "address": "Plaza"}})
    res = ingest.handle_message(ev, repo)
    assert res["publicada"] is False
    _nada_creado(repo)
    assert repo.wa_inbox["w-f" if False else "w-loc"]["resultado"] == "sin_comercio"


def test_un_desconocido_que_insiste_diez_veces_sigue_sin_crear_nada(repo):
    for i in range(10):
        ingest.handle_message(_wh(f"w-{i}", DESCONOCIDO, f"hola {i}"), repo)
    _nada_creado(repo)
    assert len(repo.wa_inbox) == 10
    assert {f["resultado"] for f in repo.wa_inbox.values()} == {"sin_comercio"}


def test_el_mismo_mensaje_dos_veces_es_duplicado_y_no_crea_nada(repo):
    ingest.handle_message(_wh("w-dup", DESCONOCIDO, "hola"), repo)
    res = ingest.handle_message(_wh("w-dup", DESCONOCIDO, "hola"), repo)
    assert res.get("duplicate") is True
    _nada_creado(repo)


def test_un_numero_propio_1a1_sin_codigo_tampoco_deja_un_comercio(repo, monkeypatch):
    """Antes el 1 a 1 de un número de URUKU (el Anfitrión probando) creaba un
    «Comercio 1234». Ahora no crea nada."""
    monkeypatch.setattr(settings, "wa_numeros_propios", "59170000099", raising=False)
    ingest.handle_message(_wh("w-own", "59170000099", "probando"), repo)
    _nada_creado(repo)


def test_el_grupo_atado_por_un_numero_propio_sigue_andando(repo, monkeypatch):
    monkeypatch.setattr(settings, "wa_numeros_propios", "59170000099", raising=False)
    repo.seed_comercio(id="com-g", slug="mendo", nombre="Mendo", codigo="ABCD", activo=True)
    grupo = "120363999888777@g.us"
    ev = _wh("w-g", "x", "URUKU-ABCD")
    ev["payload"]["from"] = grupo
    ev["payload"]["participant"] = "59170000099@c.us"
    res = ingest.handle_message(ev, repo)
    assert res.get("grupo_atado")
    assert repo.get_comercio_por_grupo(grupo)["id"] == "com-g"
    assert repo.publicaciones == []                    # un número propio no publica


@pytest.mark.parametrize("texto", ["URUKU-K7M2 zapatillas Bs 250", "uruku k7m2 zapatillas 250",
                                   "Uruku_K7M2 zapatillas 250", "URUKU K7M2 zapatillas 250"])
def test_un_desconocido_con_un_codigo_valido_publica_y_queda_autorizado(repo, texto):
    c = repo.seed_comercio(id="com-x", slug="x", nombre="X", codigo="K7M2", activo=True)
    res = ingest.handle_message(_wh("w-c1", DESCONOCIDO, texto), repo)
    assert res.get("estado") == "pendiente", res
    assert repo.publicaciones[0]["comercio_id"] == c["id"]
    assert repo.publicaciones[0]["identidad_origen"] == "codigo"
    # El número queda atado: el próximo mensaje SIN código llega al mismo comercio.
    ingest.handle_message(_wh("w-c2", DESCONOCIDO, "chinelas Bs 80"), repo)
    assert [p["comercio_id"] for p in repo.publicaciones] == [c["id"], c["id"]]
    assert list(repo.comercios) == ["com-x"]


def test_el_codigo_de_un_comercio_apagado_no_sirve(repo):
    repo.seed_comercio(id="com-off", slug="off", nombre="Off", codigo="K7M2", activo=False)
    res = ingest.handle_message(_wh("w-off", DESCONOCIDO, "URUKU-K7M2 oferta 10"), repo)
    assert res["publicada"] is False
    assert repo.publicaciones == []


def test_el_explorador_con_codigo_va_a_la_cola_y_sin_codigo_no_crea_nada(repo, monkeypatch):
    explorador = "59170000555"
    monkeypatch.setattr(settings, "wa_numeros_explorador", explorador, raising=False)
    repo.seed_comercio(id="com-e", slug="am", nombre="A&M", codigo="AQP5", activo=True, confiable=True)
    ok = ingest.handle_message(_wh("w-e1", explorador, "URUKU-AQP5 zapatilla Bs 180"), repo)
    assert ok["origen"] == "explorador" and ok["estado"] == "pendiente"
    assert repo.publicaciones[0]["estado"] == "pendiente"        # aunque el comercio sea confiable
    sin = ingest.handle_message(_wh("w-e2", explorador, "zapatilla Bs 180"), repo)
    assert sin["publicada"] is False
    assert len(repo.publicaciones) == 1 and list(repo.comercios) == ["com-e"]


# ═════════════════════════════════════════════ 2. COMPRADOR: una sola identidad
@pytest.mark.parametrize("tipeado", ["70000001", "+591 7000-0001", "591 70000001",
                                     "00591 70000001", " 7000 0001 ", "(591) 7000-0001",
                                     "+591-70000001"])
def test_todas_las_formas_de_un_numero_boliviano_confirman_y_quedan_verificadas(client, repo, tipeado):
    r = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": tipeado})
    assert r.status_code == 200, r.text
    assert r.json()["whatsapp"] == "59170000001"
    codigo = r.json()["codigo"]
    (u,) = repo.compradores.values()
    assert u["whatsapp"] == "59170000001"

    # Todavía no entró: sin confirmar, /verificar dice que falta.
    r = client.post("/auth/usuario/verificar", json={"whatsapp": tipeado, "codigo": codigo})
    assert r.status_code == 400 and u["verificado_en"] is None

    assert _confirmar(repo, "59170000001", codigo)["confirmado"] is True
    assert u["verificado_en"] is not None
    r = client.post("/auth/usuario/verificar", json={"whatsapp": tipeado, "codigo": codigo})
    assert r.status_code == 200, r.text
    assert u["verificado_en"] is not None                    # no se borra al entrar
    assert len(repo.compradores) == 1


@pytest.mark.parametrize("tipeado,confirma_desde", [
    ("+54 387 4123456", "5493874123456"),          # sin el 9: se le agrega
    ("+54 9 387 412 3456", "5493874123456"),
    ("5493874123456", "5493874123456"),
    ("+54 387 4123456", "543874123456"),           # WAHA a veces manda sin el 9
])
def test_un_comprador_argentino_confirma(client, repo, tipeado, confirma_desde):
    r = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": tipeado})
    assert r.status_code == 200, r.text
    assert r.json()["whatsapp"] == "5493874123456"
    codigo = r.json()["codigo"]
    assert _confirmar(repo, confirma_desde, codigo)["confirmado"] is True
    (u,) = repo.compradores.values()
    assert u["verificado_en"] is not None
    assert client.post("/auth/usuario/verificar",
                       json={"whatsapp": tipeado, "codigo": codigo}).status_code == 200


def test_el_confirmar_llega_por_lid_con_el_numero_real_al_costado(client, repo):
    codigo = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
    ev = _wh("w-lid", "160138577080406", f"CONFIRMAR-{codigo}")
    ev["payload"]["from"] = "160138577080406@lid"
    ev["payload"]["_data"] = {"key": {"remoteJidAlt": "59170000001@s.whatsapp.net"}}
    assert ingest.handle_message(ev, repo)["confirmado"] is True


def test_confirmar_en_minusculas_o_con_espacios_tambien_vale(client, repo):
    codigo = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
    ev = _wh("w-min", "59170000001", f"  confirmar-{codigo}  ")
    assert ingest.handle_message(ev, repo)["confirmado"] is True


def test_otro_numero_no_puede_confirmar_el_codigo_de_un_comprador(client, repo):
    codigo = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
    res = _confirmar(repo, "59170000002", codigo)           # el código es de otro número
    assert res["confirmado"] is False
    (u,) = repo.compradores.values()
    assert u["verificado_en"] is None
    assert client.post("/auth/usuario/verificar",
                       json={"whatsapp": "70000001", "codigo": codigo}).status_code == 400


def test_un_codigo_equivocado_o_vencido_no_verifica(client, repo):
    codigo = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
    (u,) = repo.compradores.values()
    otro = "000000" if codigo != "000000" else "111111"
    assert _confirmar(repo, "59170000001", otro, wamid="w-mal")["confirmado"] is False
    assert u["verificado_en"] is None
    u["reset_code_expira"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    assert _confirmar(repo, "59170000001", codigo, wamid="w-venc")["confirmado"] is False
    assert u["verificado_en"] is None


def test_el_codigo_del_comprador_sirve_una_sola_vez(client, repo):
    codigo = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
    _confirmar(repo, "59170000001", codigo)
    cuerpo = {"whatsapp": "70000001", "codigo": codigo}
    assert client.post("/auth/usuario/verificar", json=cuerpo).status_code == 200
    assert client.post("/auth/usuario/verificar", json=cuerpo).status_code == 400


def test_pedir_otro_codigo_no_borra_la_verificacion_anterior(client, repo):
    codigo = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
    _confirmar(repo, "59170000001", codigo)
    (u,) = repo.compradores.values()
    primera = u["verificado_en"]
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"})
    assert u["verificado_en"] == primera


def test_una_fila_vieja_sin_591_se_reutiliza_al_pedir_el_codigo_y_no_se_duplica(client, repo):
    repo.compradores["viejo"] = {"id": "viejo", "whatsapp": "70000001", "activo": True,
                                 "reset_code": None, "reset_code_expira": None}
    r = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "+591 70000001"})
    assert r.status_code == 200
    assert list(repo.compradores) == ["viejo"]
    assert _confirmar(repo, "59170000001", r.json()["codigo"])["confirmado"] is True
    assert repo.compradores["viejo"]["verificado_en"] is not None
    # y entra, con el token del usuario viejo
    v = client.post("/auth/usuario/verificar", json={"whatsapp": "70000001", "codigo": r.json()["codigo"]})
    assert v.status_code == 200 and v.json()["usuario"]["id"] == "viejo"


@pytest.mark.parametrize("cuerpo,esperado", [
    ({}, False),
    ({"consentimiento": False}, False),
    ({"consentimiento": True}, True),
])
def test_el_consentimiento_solo_se_marca_con_true(client, repo, cuerpo, esperado):
    r = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001", **cuerpo})
    assert r.status_code == 200
    (u,) = repo.compradores.values()
    # Tercera ronda: el tilde queda PENDIENTE; cuenta recién al verificar el número.
    assert u["consentimiento_en"] is None and u["consentimiento_ofertas"] is False
    assert u["consentimiento_pendiente"] is esperado
    assert _confirmar(repo, "59170000001", r.json()["codigo"])["confirmado"] is True
    assert (u["consentimiento_en"] is not None) is esperado
    assert u["consentimiento_ofertas"] is esperado


def test_un_consentimiento_nulo_o_basura_no_marca_nada(client, repo):
    for malo in (None, [], {}):
        r = client.post("/auth/usuario/solicitar-codigo",
                        json={"whatsapp": "70000001", "consentimiento": malo})
        assert r.status_code == 422
    assert all(u["consentimiento_en"] is None for u in repo.compradores.values())


@pytest.mark.parametrize("malo", ["", "   ", "abc", "7000", "+", "12", "7" * 30, "'; drop table usuarios;--"])
def test_numeros_basura_se_rechazan_sin_crear_usuario(client, repo, malo):
    r = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": malo})
    assert r.status_code == 400, r.text
    assert repo.compradores == {}


def test_un_comprador_y_un_comercio_con_el_mismo_numero_confirman_cada_uno_lo_suyo(client, repo):
    c = repo.seed_comercio(id="com-d", slug="d", nombre="D", whatsapp="59170000001", activo=True)
    cod_comp = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"}).json()["codigo"]
    cod_com = client.post("/auth/comercio/recuperar", json={"whatsapp": "70000001"}).json()["codigo"]
    if cod_comp == cod_com:                                  # 1 en un millón; que no vuelva el test flaky
        pytest.skip("códigos iguales por azar")
    assert _confirmar(repo, "59170000001", cod_com)["confirmado"] is True
    (u,) = repo.compradores.values()
    assert u["verificado_en"] is None                        # el del comercio no verificó al comprador
    assert _confirmar(repo, "59170000001", cod_comp, wamid="w-2")["confirmado"] is True
    assert u["verificado_en"] is not None
    assert c["id"] in {x["comercio_id"] for x in repo.usuarios.values()}


# ═══════════════════════════════════════ 4. COMERCIO: entra por WhatsApp sin clave
def _entrar_por_whatsapp(client, repo, pide, confirma_desde, comercio_id):
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": pide})
    assert r.status_code == 200, r.text
    codigo = r.json()["codigo"]
    estado = lambda: client.get("/auth/comercio/recuperar/estado",
                                params={"whatsapp": pide, "codigo": codigo}).json()["confirmado"]
    assert estado() is False
    # Sin confirmar no se entra.
    assert client.post("/auth/comercio/recuperar/confirmar",
                       json={"whatsapp": pide, "codigo": codigo}).status_code == 400
    assert _confirmar(repo, confirma_desde, codigo)["confirmado"] is True
    assert estado() is True
    r = client.post("/auth/comercio/recuperar/confirmar", json={"whatsapp": pide, "codigo": codigo})
    assert r.status_code == 200, r.text
    assert r.json()["comercio"]["id"] == comercio_id
    return codigo, r.json()["access_token"]


@pytest.mark.parametrize("pide", ["70002222", "+591 70002222", "591 7000-2222", "00591 70002222",
                                  "59170002222", " 7000 2222 "])
def test_el_comercio_de_campo_pide_el_codigo_con_su_numero_en_cualquier_formato(client, repo, pide):
    com = _alta_de_campo(client, whatsapp="70002222")
    codigo, token = _entrar_por_whatsapp(client, repo, pide, "59170002222", com["id"])
    h = {"Authorization": f"Bearer {token}"}
    # El token sirve en las pantallas del comercio…
    assert client.get("/comercio/perfil", headers=h).status_code == 200
    assert client.get("/comercio/mis-publicaciones", headers=h).status_code == 200
    # …sin que se haya puesto contraseña…
    (cuenta,) = [u for u in repo.usuarios.values() if u["comercio_id"] == com["id"]]
    assert not cuenta.get("password_hash")
    # …y el código no se puede reusar.
    r = client.post("/auth/comercio/recuperar/confirmar", json={"whatsapp": pide, "codigo": codigo})
    assert r.status_code == 400


def test_un_codigo_de_comercio_equivocado_no_entra(client, repo):
    com = _alta_de_campo(client)
    codigo = client.post("/auth/comercio/recuperar", json={"whatsapp": "70002222"}).json()["codigo"]
    _confirmar(repo, "59170002222", codigo)
    otro = "000000" if codigo != "000000" else "111111"
    r = client.post("/auth/comercio/recuperar/confirmar", json={"whatsapp": "70002222", "codigo": otro})
    assert r.status_code == 400
    assert com["id"]


def test_otro_numero_no_puede_confirmar_el_codigo_de_un_comercio(client, repo):
    _alta_de_campo(client)
    codigo = client.post("/auth/comercio/recuperar", json={"whatsapp": "70002222"}).json()["codigo"]
    assert _confirmar(repo, "59170009999", codigo)["confirmado"] is False
    assert client.post("/auth/comercio/recuperar/confirmar",
                       json={"whatsapp": "70002222", "codigo": codigo}).status_code == 400


def test_un_codigo_de_comercio_vencido_no_entra(client, repo):
    _alta_de_campo(client)
    codigo = client.post("/auth/comercio/recuperar", json={"whatsapp": "70002222"}).json()["codigo"]
    _confirmar(repo, "59170002222", codigo)
    (cuenta,) = repo.usuarios.values()
    cuenta["reset_code_expira"] = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    assert client.post("/auth/comercio/recuperar/confirmar",
                       json={"whatsapp": "70002222", "codigo": codigo}).status_code == 400


def test_pedir_un_codigo_nuevo_invalida_el_anterior(client, repo):
    com = _alta_de_campo(client)
    viejo = client.post("/auth/comercio/recuperar", json={"whatsapp": "70002222"}).json()["codigo"]
    nuevo = client.post("/auth/comercio/recuperar", json={"whatsapp": "70002222"}).json()["codigo"]
    if viejo == nuevo:
        pytest.skip("códigos iguales por azar")
    _confirmar(repo, "59170002222", nuevo)
    r = client.post("/auth/comercio/recuperar/confirmar", json={"whatsapp": "70002222", "codigo": viejo})
    assert r.status_code == 400
    r = client.post("/auth/comercio/recuperar/confirmar", json={"whatsapp": "70002222", "codigo": nuevo})
    assert r.status_code == 200 and r.json()["comercio"]["id"] == com["id"]


@pytest.mark.parametrize("numero", ["59179999999", "70009999", "+54 387 4123456", "abc", "7"])
def test_un_numero_que_no_es_de_ningun_negocio_da_404_o_400_y_no_crea_nada(client, repo, numero):
    antes = (len(repo.comercios), len(repo.usuarios))
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": numero})
    assert r.status_code in (400, 404), r.text
    assert "codigo" not in r.json()
    assert (len(repo.comercios), len(repo.usuarios)) == antes


@pytest.mark.parametrize("cuerpo", [{"whatsapp": ""}, {"whatsapp": "   "}])
def test_recuperar_sin_numero_es_400(client, cuerpo):
    assert client.post("/auth/comercio/recuperar", json=cuerpo).status_code == 400


def test_recuperar_con_un_numero_que_es_de_un_comprador_pero_no_de_un_negocio_es_404(client, repo):
    client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": "70000001"})
    assert client.post("/auth/comercio/recuperar", json={"whatsapp": "70000001"}).status_code == 404


def test_el_numero_publicado_del_comercio_sin_cuenta_recibe_una_sola_cuenta_aunque_pida_muchas_veces(client, repo):
    repo.seed_comercio(id="com-s", slug="s", nombre="Sin cuenta", whatsapp="70123456", activo=True)
    for _ in range(5):
        assert client.post("/auth/comercio/recuperar", json={"whatsapp": "59170123456"}).status_code == 200
    assert len(repo.usuarios) == 1


def test_la_cuenta_de_campo_no_se_duplica_si_el_alta_la_creo_y_luego_se_pide_el_codigo(client, repo):
    com = _alta_de_campo(client)
    client.post("/auth/comercio/recuperar", json={"whatsapp": "70002222"})
    assert len([u for u in repo.usuarios.values() if u["comercio_id"] == com["id"]]) == 1


def test_si_falla_crear_la_cuenta_el_alta_de_campo_no_se_cae(client, repo, monkeypatch):
    """El agente está en la calle: un error al crear la cuenta no puede perder el alta."""
    def boom(_cid):
        raise RuntimeError("base caída")
    monkeypatch.setattr(repo, "asegurar_comercio_usuario", boom)
    com = _alta_de_campo(client, whatsapp="70003333", nombre="Kiosco Tres")
    assert com["id"] in repo.comercios and repo.usuarios == {}
    # La recuperación se la crea al vuelo cuando lo pide (con la base ya sana).
    monkeypatch.undo()
    assert client.post("/auth/comercio/recuperar", json={"whatsapp": "70003333"}).status_code == 200


def test_el_alta_de_campo_sin_whatsapp_no_rompe_y_no_tiene_como_entrar(client, repo):
    com = _alta_de_campo(client, whatsapp=None, nombre="Sin celular")
    assert com["id"] in repo.comercios
    assert client.post("/auth/comercio/recuperar", json={"whatsapp": "70003333"}).status_code == 404


def test_dos_comercios_con_el_mismo_whatsapp_entra_el_mismo_en_los_tres_pasos(client, repo):
    """Un dueño con dos puestos (o un duplicado por autoregistro). La spec
    (segunda ronda, punto 2) pide no elegir en silencio: el primer pedido da 409
    con la lista; la persona elige, y el comercio que recibe el código es el
    mismo que lo confirma y el que devuelve el token."""
    a = _alta_de_campo(client, whatsapp="70002222", nombre="Puesto A")
    b = _alta_de_campo(client, whatsapp="70002222", nombre="Puesto B")
    assert a["id"] != b["id"]
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "70002222"})
    assert r.status_code == 409
    assert {n["id"] for n in r.json()["negocios"]} == {a["id"], b["id"]}
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "70002222", "comercio_id": b["id"]})
    assert r.status_code == 200
    codigo = r.json()["codigo"]
    con_codigo = [u for u in repo.usuarios.values() if u.get("reset_code") == codigo]
    assert len(con_codigo) == 1 and con_codigo[0]["comercio_id"] == b["id"]
    assert _confirmar(repo, "59170002222", codigo)["confirmado"] is True
    r = client.post("/auth/comercio/recuperar/confirmar", json={"whatsapp": "70002222", "codigo": codigo})
    assert r.status_code == 200
    assert r.json()["comercio"]["id"] == b["id"]


def test_el_autoregistro_dos_veces_con_el_mismo_numero_da_409(client, repo):
    """Tercera ronda: el número no se verifica al registrarse, así que no se puede
    colgar un segundo comercio de un número que ya usa otro activo."""
    datos = {"nombre": "Mi Tienda", "whatsapp": "59170001111", "lat": "-22.7361", "lng": "-64.3433"}
    r1 = client.post("/auth/comercio/registro", data=datos, files=_foto())
    r2 = client.post("/auth/comercio/registro", data=datos, files=_foto())
    assert r1.status_code == 200 and r2.status_code == 409
    assert len(repo.comercios) == 1


# ── BUG: el número de la ficha se guarda tal cual se tipeó ──────────────────
@pytest.mark.parametrize("en_la_ficha", ["7000 2222", "7000-2222", "+591 70002222", "591-7000-2222",
                                         "(591) 70002222"])
def test_BUG1_un_comercio_con_la_ficha_en_formato_libre_puede_entrar(client, repo, en_la_ficha):
    com = _alta_de_campo(client, whatsapp=en_la_ficha)
    # el agente en la calle tipea con espacios, y el repo lo guarda sin normalizar (_none solo hace strip)
    r = client.post("/auth/comercio/recuperar", json={"whatsapp": "70002222"})
    assert r.status_code == 200, f"ficha={en_la_ficha!r} → {r.status_code} {r.text}"
    assert com["id"] in {u["comercio_id"] for u in repo.usuarios.values()}


def test_BUG1_el_autoregistro_con_numero_con_espacios_puede_volver_a_entrar(client, repo):
    r = client.post("/auth/comercio/registro",
                    data={"nombre": "Mi Tienda", "whatsapp": "+591 7000 1111",
                          "lat": "-22.7361", "lng": "-64.3433"}, files=_foto())
    assert r.status_code == 200
    assert client.post("/auth/comercio/recuperar", json={"whatsapp": "70001111"}).status_code == 200


# ═══════════════════════════════════════ 5. AUTOREGISTRO devuelve el código
def test_el_autoregistro_devuelve_codigo_y_codigo_formateado_distintos_en_cada_alta(client, repo):
    vistos = set()
    for i in range(5):
        r = client.post("/auth/comercio/registro",
                        data={"nombre": f"Tienda {i}", "whatsapp": f"5917000{i:04d}",
                              "lat": "-22.7361", "lng": "-64.3433"}, files=_foto())
        com = r.json()["comercio"]
        assert com["codigo_formateado"] == f"URUKU-{com['codigo']}"
        assert len(com["codigo"]) == 4 and com["codigo"].isalnum()
        vistos.add(com["codigo"])
        # y el código sirve de verdad para publicar 1 a 1 desde cualquier celular
    assert len(vistos) == 5


def test_el_codigo_del_autoregistro_sirve_para_publicar_desde_un_celular_cualquiera(client, repo):
    r = client.post("/auth/comercio/registro",
                    data={"nombre": "Mi Tienda", "whatsapp": "59170001111",
                          "lat": "-22.7361", "lng": "-64.3433"}, files=_foto())
    cf = r.json()["comercio"]["codigo_formateado"]
    res = ingest.handle_message(_wh("w-pub", DESCONOCIDO, f"{cf} zapatillas Bs 250"), repo)
    assert res["estado"] == "pendiente"
    assert repo.publicaciones[0]["comercio_id"] == r.json()["comercio"]["id"]


# ═══════════════════════════════ 6. LA IA NUNCA APRUEBA LO DEL EXPLORADOR
@pytest.fixture
def ia_aprueba_todo(monkeypatch):
    monkeypatch.setattr(revision_ia, "moderar_publicacion",
                        lambda t, d: {"veredicto": "aprobar", "motivo": "ok", "confianza": 1.0})


@pytest.mark.parametrize("perilla", [0.01, 0.5, 0.8, 1.0])
def test_el_explorador_nunca_se_aprueba_solo_con_ninguna_perilla(repo, monkeypatch, ia_aprueba_todo, perilla):
    monkeypatch.setattr(settings, "ia_auto_aprobar_desde", perilla)
    c = repo.seed_comercio(slug="x", nombre="X", plan="destacado", confiable=True, activo=True)
    base = {"comercio_id": c["id"], "tipo": "oferta", "estado": "pendiente",
            "created_at": "2026-09-10T10:00:00+00:00"}
    p_exp = repo.insert_publicacion_directa({**base, "titulo": "zapatilla", "origen": "explorador"})
    p_wa = repo.insert_publicacion_directa({**base, "titulo": "chinela", "origen": "whatsapp"})
    p_sin = repo.insert_publicacion_directa({**base, "titulo": "remera"})            # sin la clave origen
    p_none = repo.insert_publicacion_directa({**base, "titulo": "gorra", "origen": None})
    res = revision_ia.revisar_pendientes(repo)
    assert res["revisadas"] == 4 and res["auto_aprobadas"] == 3
    assert repo.get_publicacion(p_exp["id"])["estado"] == "pendiente"
    for p in (p_wa, p_sin, p_none):
        assert repo.get_publicacion(p["id"])["estado"] == "aprobado"
    assert all(f["publicacion_id"] != p_exp["id"] for f in repo.difusion)    # ni a la cola de difusión


def test_el_explorador_pasa_por_ingest_y_la_ia_lo_deja_en_la_cola(repo, monkeypatch, ia_aprueba_todo):
    monkeypatch.setattr(settings, "ia_auto_aprobar_desde", 0.8)
    monkeypatch.setattr(settings, "wa_numeros_explorador", "59170000555", raising=False)
    repo.seed_comercio(id="com-e", slug="am", nombre="A&M", codigo="AQP5", activo=True, confiable=True)
    ingest.handle_message(_wh("w-ex", "59170000555", "URUKU-AQP5 zapatilla urbana Bs 180"), repo)
    revision_ia.revisar_pendientes(repo)
    (p,) = repo.publicaciones
    assert p["origen"] == "explorador" and p["estado"] == "pendiente" and p["ia_veredicto"] == "aprobar"


def test_con_la_perilla_en_cero_nada_se_aprueba_solo(repo, monkeypatch, ia_aprueba_todo):
    monkeypatch.setattr(settings, "ia_auto_aprobar_desde", 0.0)
    c = repo.seed_comercio(slug="x", nombre="X", activo=True)
    p = repo.insert_publicacion_directa({"comercio_id": c["id"], "tipo": "oferta", "titulo": "a",
                                         "estado": "pendiente", "origen": "whatsapp"})
    revision_ia.revisar_pendientes(repo)
    assert repo.get_publicacion(p["id"])["estado"] == "pendiente"


def test_un_humano_si_puede_aprobar_lo_del_explorador(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="X", activo=True)
    p = repo.insert_publicacion_directa({"comercio_id": c["id"], "tipo": "oferta", "titulo": "a",
                                         "estado": "pendiente", "origen": "explorador"})
    r = client.post(f"/moderacion/publicaciones/{p['id']}",
                    headers={"Authorization": f"Bearer {admin_token}"}, json={"estado": "aprobado"})
    assert r.status_code == 200
    assert repo.get_publicacion(p["id"])["estado"] == "aprobado"


def test_auto_aprueba_exige_la_publicacion_y_frena_al_explorador(monkeypatch):
    """La spec (segunda ronda, punto 6) hace obligatoria la publicación: sin ella
    no se puede saber si es del explorador, y antes se aprobaba igual."""
    monkeypatch.setattr(settings, "ia_auto_aprobar_desde", 0.8)
    v = {"veredicto": "aprobar", "confianza": 0.9}
    with pytest.raises(TypeError):
        revision_ia._auto_aprueba(v)
    assert revision_ia._auto_aprueba(v, {"origen": "whatsapp"}) is True
    assert revision_ia._auto_aprueba(v, {"origen": "explorador"}) is False
    assert revision_ia._auto_aprueba(v, {"origen": "whatsapp", "identidad_origen": "explorador"}) is False


# ═════════════════════════════════════════════ 7. POST /mensaje ya no existe
@pytest.mark.parametrize("metodo", ["post", "get", "put", "delete"])
def test_mensaje_publico_no_existe_en_ningun_metodo(client, repo, metodo):
    repo.seed_comercio(id="com-p", slug="perf", nombre="X", whatsapp="591700")
    r = getattr(client, metodo)("/mensaje", **({"json": {"comercio_id": "com-p", "nombre": "A", "cuerpo": "hola"}}
                                                if metodo in ("post", "put") else {}))
    assert r.status_code in (404, 405)
    assert repo.mensajes == {}


def test_mensaje_no_esta_en_el_openapi_pero_el_del_admin_si():
    from app.main import app
    paths = app.openapi()["paths"]
    assert "/mensaje" not in paths
    assert any(p.endswith("/mensaje") and p.startswith("/admin/comercio") for p in paths)
    assert "/comercio/mensajes" in paths


def test_el_admin_sigue_pudiendo_mandar_mensajes_y_el_comercio_los_lee(client, repo, admin_token):
    c = repo.seed_comercio(id="com-m", slug="m", nombre="M", whatsapp="591700", activo=True)
    r = client.post(f"/admin/comercio/{c['id']}/mensaje",
                    headers={"Authorization": f"Bearer {admin_token}"}, json={"cuerpo": "Hola"})
    assert r.status_code == 200
    from tests.conftest import comercio_token
    box = client.get("/comercio/mensajes",
                     headers={"Authorization": f"Bearer {comercio_token(c['id'])}"}).json()
    assert box["items"][0]["nombre"] == "URUKU"


def test_enviar_codigo_otp_ya_no_esta_en_el_cliente_de_whatsapp():
    from app.services import whatsapp_client
    assert not hasattr(whatsapp_client, "enviar_codigo_otp")


def test_ningun_archivo_de_la_app_importa_lo_borrado():
    raiz = Path(__file__).resolve().parents[1] / "app"
    for py in raiz.rglob("*.py"):
        txt = py.read_text(encoding="utf-8")
        assert "upsert_comercio_by_jid" not in txt, py
        assert "from app.services.whatsapp_client import enviar_codigo_otp" not in txt, py
        assert "dejar_mensaje" not in txt, py


# ═══════════════════════════════════════════════ 8. FAVORITOS con soft-delete
def _token_comprador(client, repo, wa="70000001"):
    r = client.post("/auth/usuario/solicitar-codigo", json={"whatsapp": wa}).json()
    _confirmar(repo, "591" + wa[-8:], r["codigo"], wamid=f"c-{wa}")
    t = client.post("/auth/usuario/verificar", json={"whatsapp": wa, "codigo": r["codigo"]}).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}


def test_favoritos_quitar_inexistente_volver_a_agregar_y_aislamiento_entre_usuarios(client, repo):
    ha = _token_comprador(client, repo, "70000001")
    hb = _token_comprador(client, repo, "70000002")
    c = repo.seed_comercio(id="com-f", slug="f", nombre="F", activo=True)

    # quitar uno que nunca se agregó no rompe ni crea filas
    assert client.delete(f"/usuario/favoritos/{c['id']}", headers=ha).status_code == 200
    assert repo.favoritos == []

    for _ in range(3):                                       # agregar repetido: una sola fila
        client.post("/usuario/favoritos", headers=ha, json={"comercio_id": c["id"]})
    client.post("/usuario/favoritos", headers=hb, json={"comercio_id": c["id"]})
    assert len(repo.favoritos) == 2

    # B quita el suyo: el de A sigue
    client.delete(f"/usuario/favoritos/{c['id']}", headers=hb)
    assert [i["slug"] for i in client.get("/usuario/favoritos", headers=ha).json()["items"]] == ["f"]
    assert client.get("/usuario/favoritos", headers=hb).json()["items"] == []

    # A quita dos veces y vuelve a agregar: misma fila, activa
    client.delete(f"/usuario/favoritos/{c['id']}", headers=ha)
    client.delete(f"/usuario/favoritos/{c['id']}", headers=ha)
    assert client.get("/usuario/favoritos", headers=ha).json()["items"] == []
    client.post("/usuario/favoritos", headers=ha, json={"comercio_id": c["id"]})
    assert len(repo.favoritos) == 2                          # ninguna fila nueva, ninguna borrada
    assert [i["slug"] for i in client.get("/usuario/favoritos", headers=ha).json()["items"]] == ["f"]


def test_favoritos_sin_token_es_401(client):
    assert client.get("/usuario/favoritos").status_code == 401
    assert client.post("/usuario/favoritos", json={"comercio_id": "x"}).status_code == 401
    assert client.delete("/usuario/favoritos/x").status_code == 401


# ═══════════════════════════════ 3. LLEGADAS y contactos con origen
def test_una_visita_con_ref_y_un_lead_con_origen_aparecen_cada_uno_donde_debe(client, repo, admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    client.post("/visita", json={"ruta": "/", "sesion": "sesion-aaa111", "origen": "volante-x"})
    client.post("/visita", json={"ruta": "/buscar", "sesion": "sesion-aaa111", "origen": "volante-x"})
    client.post("/lead", json={"comercio_id": "c1", "tipo": "whatsapp", "origen": "volante-x"})
    client.post("/lead", json={"comercio_id": "c1", "tipo": "whatsapp"})            # sin ref: no cuenta
    d = client.get("/admin/estadisticas", headers=h).json()
    assert d["llegadas_30d"] == 1                                                    # personas, no páginas
    assert d["llegadas_top"] == [{"origen": "volante-x", "count": 1}]
    assert d["contactos_con_origen_30d"] == 1
    assert d["contactos_origen_top"] == [{"origen": "volante-x", "count": 1}]
    assert d["contactos_30d"] == 2


def test_un_lead_de_whatsapp_con_ref_guarda_el_origen_sanitizado(client, repo):
    for crudo, limpio in [("VOLANTE-X", "volante-x"), ("  mesa-sol ", "mesa-sol"),
                          ("<script>alert(1)</script>", "scriptalert1script"),
                          ("a" * 200, "a" * 64), ("grupo-ñandú", "grupo-and")]:
        client.post("/lead", json={"comercio_id": "c1", "tipo": "whatsapp", "origen": crudo})
        assert repo.leads[-1]["origen"] == limpio
    client.post("/lead", json={"comercio_id": "c1", "tipo": "whatsapp", "origen": "!!!"})
    assert "origen" not in repo.leads[-1]


def test_un_lead_con_tipo_raro_cae_en_whatsapp_y_conserva_el_origen(client, repo):
    client.post("/lead", json={"comercio_id": "c1", "tipo": "<b>x</b>", "origen": "fb"})
    assert repo.leads[-1]["tipo"] == "whatsapp" and repo.leads[-1]["origen"] == "fb"


def test_BUG2_el_mismo_ref_se_guarda_igual_en_visita_y_en_lead(client, repo):
    ref = "grupo:sol"
    client.post("/visita", json={"ruta": "/", "sesion": "sesion-aaa111", "origen": ref})
    client.post("/lead", json={"comercio_id": "c1", "tipo": "whatsapp", "origen": ref})
    assert repo.visitas[-1]["origen"] == repo.leads[-1]["origen"]


def test_las_rutas_internas_no_cuentan_como_llegada(client, repo):
    r = client.post("/visita", json={"ruta": "/mi-comercio", "sesion": "sesion-aaa111", "origen": "volante-x"})
    assert r.json()["contada"] is False and repo.visitas == []


# ═══════════════════════════════════════ 3-bis. MIGRACIÓN 0137 (lectura)
def _sql(nombre):
    return (Path(__file__).resolve().parents[2] / nombre).read_text(encoding="utf-8").lower()


def _sin_comentarios(sql):
    return "\n".join(l for l in sql.splitlines() if not l.strip().startswith("--"))


def test_0137_cada_sentencia_ddl_es_idempotente():
    sql = _sin_comentarios(_sql("supabase/migrations/0137_limpieza_de_circuitos.sql"))
    import re
    for s in re.findall(r"alter table \w+ add column[^;]*;", sql):
        assert "if not exists" in s, s
    for s in re.findall(r"create (?:unique )?index[^;]*;", sql):
        assert "if not exists" in s, s
    # El backfill del único INSERT se auto-protege: segunda corrida = 0 filas.
    ins = re.findall(r"insert into comercio_usuarios.*?;", sql, flags=re.S)
    assert len(ins) == 1 and "not exists" in ins[0] and "u.activo" in ins[0] and "c.activo" in ins[0]
    # Sin sentencias destructivas ni cambios de datos en filas viejas.
    for prohibido in ("drop ", "delete from", "truncate", "update usuarios", "update comercios"):
        assert prohibido not in sql, prohibido


def test_0137_no_abre_nada_a_anon_ni_authenticated():
    sql = _sin_comentarios(_sql("supabase/migrations/0137_limpieza_de_circuitos.sql"))
    # Los `revoke ... from public, anon, authenticated` QUITAN permisos: se ignoran.
    sql = "\n".join(l for l in sql.splitlines() if not l.strip().startswith("revoke"))
    for prohibido in ("anon", "authenticated", "public;", "create policy", "disable row level security"):
        assert prohibido not in sql, prohibido
    for tabla in ("usuarios", "favoritos", "comercio_usuarios", "clave_fallos"):
        assert f"alter table {tabla} enable row level security" in sql
        assert f"grant all on public.{tabla} to service_role" in sql


def test_0137_el_backfill_no_duplica_ni_pisa_cuentas_con_un_modelo_en_memoria():
    """Simula la semántica del INSERT … WHERE NOT EXISTS sobre filas de ejemplo."""
    comercios = [{"id": 1, "activo": True}, {"id": 2, "activo": True}, {"id": 3, "activo": False},
                 {"id": 4, "activo": True}]
    cuentas = [{"comercio_id": 2, "activo": True}, {"comercio_id": 4, "activo": False}]

    def backfill():
        nuevas = [{"comercio_id": c["id"], "activo": True} for c in comercios if c["activo"]
                  and not any(u["comercio_id"] == c["id"] and u["activo"] for u in cuentas)]
        cuentas.extend(nuevas)
        return len(nuevas)

    assert backfill() == 2            # el 1 y el 4 (cuenta desactivada: se le crea una NUEVA, ver reporte)
    assert backfill() == 0            # segunda corrida: nada
    assert sorted(u["comercio_id"] for u in cuentas if u["activo"]) == [1, 2, 4]


def test_0137_y_selfhost_son_identicas_y_el_numero_de_migracion_es_el_siguiente():
    raiz = Path(__file__).resolve().parents[2]
    assert (raiz / "supabase/migrations/0137_limpieza_de_circuitos.sql").read_bytes() == \
           (raiz / "selfhost/postgres-init/0137_limpieza_de_circuitos.sql").read_bytes()
    numeros = sorted(p.name[:4] for p in (raiz / "supabase/migrations").glob("0*.sql"))
    assert numeros.count("0137") == 1
    # 0137 era la última cuando se escribió el test; ahora hay migraciones
    # posteriores (0138: cargas del día). Alcanza con que no se haya saltado ni repetido.
    assert numeros[-1] >= "0137"
