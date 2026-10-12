"""Código del comercio: identificar un local sin que tenga número propio.

El caso que resuelve: el agente carga el local en la calle y le deja el código en
papel. El dueño manda una oferta desde el celular de quien sea, escribe el
código, y la publicación cae en el comercio correcto — sin número cargado, sin
login y sin haber pagado.
"""
import pytest

from app.core.codigo import extraer_codigo, formatear, generar_codigo, normalizar


# ------------------------------------------------------------------ el código
def test_generado_no_usa_caracteres_confundibles():
    """Se dicta por teléfono y se lee de un papel: 0/O y 1/I/L están fuera."""
    for _ in range(200):
        c = generar_codigo()
        assert len(c) == 4
        assert not (set(c) & set("01OIL"))


def test_los_codigos_no_son_secuenciales():
    codigos = {generar_codigo() for _ in range(200)}
    assert len(codigos) > 150  # aleatorios, no un contador


@pytest.mark.parametrize("entrada,esperado", [
    ("K7M2", "K7M2"),
    ("k7m2", "K7M2"),
    ("URUKU-K7M2", "K7M2"),
    ("uruku k7m2", "K7M2"),
    ("URUKU_K7M2", "K7M2"),
    ("  URUKU-k7m2  ", "K7M2"),
    ("K7M", None),          # corto
    ("K7M2X", None),        # largo
    ("K0M2", None),         # 0 no está en el alfabeto
    ("", None),
    (None, None),
])
def test_normalizar(entrada, esperado):
    assert normalizar(entrada) == esperado


def test_formatear():
    assert formatear("k7m2") == "URUKU-K7M2"


@pytest.mark.parametrize("texto,esperado", [
    ("URUKU-K7M2 tengo ofertas de zapatillas", "K7M2"),
    ("Hola! oferta del día\nuruku k7m2", "K7M2"),
    ("mi codigo es URUKUK7M2", "K7M2"),
    ("K7M2", "K7M2"),
    ("hola que tal, tengo una oferta", None),
])
def test_extraer_codigo_del_mensaje(texto, esperado):
    assert extraer_codigo(texto) == esperado


def test_prefijo_gana_sobre_una_palabra_suelta():
    """'ROPA' tiene 4 letras válidas: sin priorizar el prefijo, se colaría."""
    assert extraer_codigo("ROPA nueva, URUKU-K7M2") == "K7M2"


# -------------------------------------------------------------- alta y lookup
def test_todo_comercio_nace_con_codigo(repo):
    c = repo.crear_comercio({"slug": "ferreteria", "nombre": "Ferretería"})
    assert normalizar(c["codigo"]) == c["codigo"]


def test_buscar_por_codigo_acepta_las_formas_que_escribe_la_gente(repo):
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", activo=True)
    for forma in ["K7M2", "k7m2", "URUKU-K7M2", "uruku k7m2"]:
        assert repo.get_comercio_por_codigo(forma)["id"] == c["id"]


def test_codigo_inexistente_no_devuelve_nada(repo):
    repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", activo=True)
    assert repo.get_comercio_por_codigo("XXXX") is None


# ------------------------------------------------------------------- ingesta
def _ingestar(repo, phone, body, msg_id="msg-1"):
    from app.services import ingest
    return ingest.handle_message({
        "event": "message",
        "session": "obs@c.us",
        "payload": {
            "id": msg_id, "from": f"{phone}@c.us", "fromMe": False,
            "body": body, "type": "text", "timestamp": 1700000000,
        },
    }, repo)


def test_numero_desconocido_con_codigo_publica_en_el_comercio_correcto(repo):
    """El caso que motivó todo: local sin número propio, dueño escribe desde
    cualquier celular."""
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", activo=True)
    antes = len(repo.comercios)

    _ingestar(repo, "59177777777", "URUKU-K7M2 oferta: taladro a 300")

    assert len(repo.comercios) == antes, "no debe crear un comercio nuevo"
    pubs = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]]
    assert len(pubs) == 1
    assert pubs[0]["identidad_origen"] == "codigo"
    assert pubs[0]["codigo_recibido"] == "K7M2"


def test_el_numero_queda_autorizado_y_no_hay_que_repetir_el_codigo(repo):
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", activo=True)

    _ingestar(repo, "59177777777", "URUKU-K7M2 primera oferta", "msg-1")
    _ingestar(repo, "59177777777", "segunda oferta, sin código", "msg-2")

    pubs = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]]
    assert len(pubs) == 2
    # Lo reconoce sin el código, pero sigue marcado: lo autorizó el código.
    assert pubs[1]["identidad_origen"] == "numero_por_codigo"


def test_sin_codigo_y_numero_desconocido_no_crea_nada(repo):
    """Antes creaba un borrador apagado («Comercio 7777»). Desde la limpieza de
    circuitos el mensaje queda en la bandeja como `sin_comercio` y nada más."""
    antes = len(repo.comercios)
    res = _ingestar(repo, "59177777777", "hola tengo ofertas")
    assert len(repo.comercios) == antes
    assert repo.publicaciones == []
    assert res["publicada"] is False
    assert repo.wa_inbox["msg-1"]["resultado"] == "sin_comercio"


def test_un_numero_ya_conocido_no_necesita_codigo(repo):
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", whatsapp="59177777777", codigo="K7M2", activo=True)
    _ingestar(repo, "59177777777", "oferta del día")
    pubs = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]]
    assert pubs[0]["identidad_origen"] == "numero"


def test_identificado_por_codigo_nunca_auto_aprueba(repo):
    """El código está en un papel a la vista en el local: cualquiera que lo lea
    podría publicar. La primera vez pasa por moderación aunque sea confiable."""
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", confiable=True, activo=True)

    _ingestar(repo, "59177777777", "URUKU-K7M2 oferta")

    pub = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]][0]
    assert pub["estado"] == "pendiente"


def test_confiable_por_numero_conocido_si_auto_aprueba(repo):
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", whatsapp="59177777777",
                           codigo="K7M2", confiable=True, activo=True)
    _ingestar(repo, "59177777777", "oferta del día")
    pub = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]][0]
    assert pub["estado"] == "aprobado"


def test_numero_autorizado_por_codigo_nunca_publica_directo(repo):
    """El código se ve en el volante: quien lo lea manda una vez con el código
    (a moderación) y desde ahí su número queda reconocido. Ni así publica directo
    en un comercio confiable."""
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", confiable=True, activo=True)
    _ingestar(repo, "59177777777", "URUKU-K7M2 primera", "msg-1")
    _ingestar(repo, "59177777777", "segunda, sin código", "msg-2")
    _ingestar(repo, "59177777777", "tercera", "msg-3")
    pubs = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]]
    assert [p["estado"] for p in pubs] == ["pendiente", "pendiente", "pendiente"]


def test_cuando_el_equipo_autoriza_el_numero_publica_directo(repo):
    from app.services import ingest
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", confiable=True, activo=True)
    _ingestar(repo, "59177777777", "URUKU-K7M2 primera", "msg-1")
    # El admin lo autoriza en el negocio (POST /admin/comercio/{id}/numeros).
    repo.agregar_numero_comercio(c["id"], "59177777777", "dueño", "admin@uruku.bo")
    assert not repo.numero_autorizado_por_codigo("59177777777")
    _ingestar(repo, "59177777777", "segunda", "msg-2")
    pubs = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]]
    assert pubs[1]["identidad_origen"] == "numero"
    assert pubs[1]["estado"] == "aprobado"
    assert ingest.NUMERO_POR_CODIGO == "ingest-codigo"


def test_el_codigo_no_pisa_el_whatsapp_atado_al_comercio(repo):
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2",
                           wa_jid="59170000000@c.us", activo=True)
    _ingestar(repo, "59177777777", "URUKU-K7M2 hola")
    assert repo.comercios[c["id"]]["wa_jid"] == "59170000000@c.us"


def test_el_codigo_ata_el_whatsapp_si_el_comercio_no_tenia(repo):
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", activo=True)
    _ingestar(repo, "59177777777", "URUKU-K7M2 hola")
    assert repo.comercios[c["id"]]["wa_jid"] == "59177777777@c.us"


def test_la_ia_no_auto_aprueba_lo_que_entro_por_codigo():
    from app.services.revision_ia import _ORIGENES_SIEMPRE_HUMANOS
    assert {"codigo", "numero_por_codigo"} <= _ORIGENES_SIEMPRE_HUMANOS


# ------------------------------------------------ validación al aprobar
def test_aprobar_revalida_el_codigo(client, repo, admin_token):
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", activo=True)
    _ingestar(repo, "59177777777", "URUKU-K7M2 oferta")
    pub = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]][0]

    r = client.post(f"/moderacion/publicaciones/{pub['id']}",
                    json={"estado": "aprobado"},
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text


def test_aprobar_falla_si_el_codigo_del_comercio_cambio(client, repo, admin_token):
    """Entre que entró el mensaje y la aprobación pudo cambiar todo. Aprobar es
    el acto que lo hace público, así que la verificación se rehace ahí."""
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", activo=True)
    _ingestar(repo, "59177777777", "URUKU-K7M2 oferta")
    pub = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]][0]

    repo.comercios[c["id"]]["codigo"] = "P9QR"  # el comercio cambió de código

    r = client.post(f"/moderacion/publicaciones/{pub['id']}",
                    json={"estado": "aprobado"},
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 409
    assert "URUKU-K7M2" in r.json()["detail"]
    assert repo.get_publicacion(pub["id"])["estado"] == "pendiente"


def test_rechazar_no_valida_codigo(client, repo, admin_token):
    """Rechazar tiene que funcionar siempre: es la salida para lo que está mal."""
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", codigo="K7M2", activo=True)
    _ingestar(repo, "59177777777", "URUKU-K7M2 oferta")
    pub = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]][0]
    repo.comercios[c["id"]]["codigo"] = "P9QR"

    r = client.post(f"/moderacion/publicaciones/{pub['id']}",
                    json={"estado": "rechazado", "motivo": "no corresponde"},
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text


def test_publicacion_por_numero_se_aprueba_sin_codigo(client, repo, admin_token):
    c = repo.seed_comercio(slug="ferreteria", nombre="Ferretería", whatsapp="59177777777", codigo="K7M2", activo=True)
    _ingestar(repo, "59177777777", "oferta del día")
    pub = [p for p in repo.publicaciones if p["comercio_id"] == c["id"]][0]

    r = client.post(f"/moderacion/publicaciones/{pub['id']}",
                    json={"estado": "aprobado"},
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
