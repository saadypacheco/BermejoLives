"""Los planes viven en la base y las cuotas se cuentan de verdad.

Antes de esto, la página de venta prometía 15 y 50 publicaciones por mes y el
sistema no contaba ninguna: un comercio del plan de 15 podía mandar 300 y salían
las 300. El plan caro no daba nada que el barato no tuviera.

Lo que se prueba acá es sobre todo lo que NO puede pasar: que a alguien se le
corte la publicación sin enterarse, que se le cobre dos veces la misma foto, o
que un problema nuestro lo deje sin publicar.
"""
from datetime import date, timedelta

import pytest

from app.services import ingest, planes


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _hoy(dias=0):
    return (date.today() + timedelta(days=dias)).isoformat()


def _publicar(repo, comercio, n, estado="aprobado", desde=0):
    for i in range(n):
        repo.insert_publicacion_directa({
            "comercio_id": comercio["id"], "tipo": "oferta", "titulo": f"of {i}",
            "estado": estado, "created_at": _hoy(desde)})


# ══════════════════════════════════════════════════ el plan y sus funciones

def test_el_plan_sale_de_la_base(repo):
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica")
    plan = planes.plan_de(repo, c)
    assert plan["nombre"] == "Publica"
    assert plan["publicaciones_mes"] == 15


def test_un_plan_que_ya_no_existe_no_deja_sin_publicar(repo):
    """Un dato viejo apuntando a un plan borrado no puede dejar a un comercio
    sin poder publicar: el problema es nuestro, no de él."""
    c = repo.seed_comercio(slug="x", nombre="X", plan="plan-fantasma")
    assert planes.plan_de(repo, c)["slug"] == "gratis"


def test_una_funcion_no_declarada_es_que_no(repo):
    """Lo que permite agregar una función sin migrar: el código puede preguntar
    por uno que todavía no existe y recibe "no" en vez de romperse."""
    assert planes.funcion(repo.get_plan("empleado_ia"), "asistente_24_7") is True
    assert planes.funcion(repo.get_plan("publica"), "asistente_24_7") is False
    assert planes.funcion(repo.get_plan("pro"), "una_que_no_inventamos_todavia") is False


# ══════════════════════════════════════════════════════════ el conteo

def test_cuenta_solo_lo_aprobado(repo):
    """Una publicación rechazada no puede consumir cuota: el comerciante no
    obtuvo nada por ella, y cobrársela sería cobrarle por un rechazo nuestro."""
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica")
    _publicar(repo, c, 3, estado="aprobado")
    _publicar(repo, c, 5, estado="rechazado")

    est = planes.estado(repo, c)
    assert est["usadas"] == 3
    assert est["quedan"] == 12


def test_el_ciclo_no_es_el_mes_calendario(repo):
    """Se paga un día y corren desde ese día. Contar por mes calendario le daría
    al que paga el 28 una cuota de tres días."""
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica",
                           paga_hasta=_hoy(10))
    inicio = planes.inicio_del_ciclo(c)
    assert inicio <= date.today()
    assert (date.today() - inicio).days < 30


def test_un_pago_vencido_hace_meses_no_cuenta_un_ciclo_viejo(repo):
    """Si el pago venció hace rato, el ciclo vigente es el que corre ahora.
    Contarle las publicaciones de un ciclo viejo sería cobrarle dos veces."""
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica",
                           paga_hasta=_hoy(-200))
    inicio = planes.inicio_del_ciclo(c)
    assert (date.today() - inicio).days < 31


def test_sin_limite_nunca_se_excede(repo):
    repo.upsert_plan("publica", {"publicaciones_mes": None})
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica")
    _publicar(repo, c, 40)
    est = planes.estado(repo, c)
    assert est["cuota"] is None and est["excedido"] is False


# ═══════════════════════════════════════════════ qué pasa al llegar al tope

def test_al_pasarse_se_publica_y_se_cobra(repo):
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica")
    _publicar(repo, c, 15)
    r = planes.revisar_antes_de_publicar(repo, c)
    assert r["puede"] is True
    assert r["consecuencia"] == "cobrar"


def test_si_el_plan_no_admite_extras_se_corta(repo):
    """Los dos caminos son válidos y la decisión es comercial, no técnica."""
    repo.upsert_plan("publica", {"permite_extras": False})
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica")
    _publicar(repo, c, 15)
    r = planes.revisar_antes_de_publicar(repo, c)
    assert r["puede"] is False
    assert r["consecuencia"] == "bloquear"


def test_el_aviso_lleva_las_dos_salidas(repo):
    """El que no quiere gastar de más igual tiene que enterarse del plan de
    arriba, y el apurado tiene que poder pagar la extra. Ofrecer una sola es
    elegir por él."""
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica")
    _publicar(repo, c, 15)
    est = planes.estado(repo, c)
    texto = planes.texto_de_aviso(est, planes.plan_siguiente(repo, est["plan"]))

    assert "Bs 5" in texto              # la extra
    assert "Destacado" in texto         # el plan de arriba
    assert "140" in texto               # cuánto sale


def test_el_precio_de_la_extra_se_cambia_sin_tocar_codigo(client, repo, admin_token):
    """El motivo entero de que los planes estén en la base: lo cambia quien
    vende, el día que lo decide."""
    r = client.put("/admin/planes/publica",
                   json={"precio_publicacion_extra": 8}, headers=_h(admin_token))
    assert r.status_code == 200, r.text

    c = repo.seed_comercio(slug="x", nombre="X", plan="publica")
    _publicar(repo, c, 15)
    est = planes.estado(repo, c)
    assert "Bs 8" in planes.texto_de_aviso(est, None)


def test_se_puede_crear_un_plan_nuevo_desde_el_panel(client, repo, admin_token):
    r = client.put("/admin/planes/mayorista",
                   json={"nombre": "Mayorista", "precio_mes": 900, "orden": 4,
                         "publicaciones_mes": 200,
                         "funciones": {"asistente_24_7": True, "vidriera": True}},
                   headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert repo.get_plan("mayorista")["nombre"] == "Mayorista"
    assert planes.funcion(repo.get_plan("mayorista"), "vidriera") is True


def test_un_plan_nuevo_sin_nombre_se_rechaza(client, admin_token):
    """Saldría en la página de venta como un slug."""
    r = client.put("/admin/planes/sinnombre", json={"precio_mes": 10},
                   headers=_h(admin_token))
    assert r.status_code == 400


# ═════════════════════════════════════════════════════════ el cargo

def test_la_misma_publicacion_no_se_cobra_dos_veces(repo):
    """El webhook de WhatsApp repite mensajes. Sin esto, un reenvío duplica el
    cargo y el comerciante recibe una factura que no entiende."""
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica")
    plan = repo.get_plan("publica")
    planes.cobrar_extra(repo, c, "pub-1", plan)
    planes.cobrar_extra(repo, c, "pub-1", plan)
    assert len(repo.cargos_extra) == 1


def test_un_fallo_al_cobrar_no_deja_sin_publicar(repo, monkeypatch):
    """Cambiar un problema de plata por uno de servicio es el peor negocio
    posible."""
    def _explota(*a, **k):
        raise RuntimeError("la base se cayó")
    monkeypatch.setattr(repo, "registrar_cargo_extra", _explota)
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica")
    planes.cobrar_extra(repo, c, "pub-1", repo.get_plan("publica"))  # no lanza


def test_el_panel_suma_lo_que_falta_cobrar(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica")
    plan = repo.get_plan("publica")
    planes.cobrar_extra(repo, c, "pub-1", plan)
    planes.cobrar_extra(repo, c, "pub-2", plan)

    r = client.get("/admin/cargos-extra", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["total"] == 10


# ═══════════════════════════════════════════ el camino completo, por WhatsApp

def _mensaje(repo, comercio, texto="oferta nueva"):
    repo.vincular_grupo_comercio("120363@g.us", comercio["id"], "G", "admin", "test")
    return {"event": "message", "session": "default", "payload": {
        "id": f"m{len(repo.publicaciones)}-{len(repo.wa_inbox)}",
        "from": "120363@g.us", "participant": "59170000009@c.us",
        "body": texto, "type": "text", "fromMe": False}}


def test_al_tope_avisa_en_el_mismo_chat(repo, monkeypatch):
    """El silencio es el peor resultado: manda otra foto, tampoco sale, y se va
    convencido de que esto no funciona."""
    avisos = []
    monkeypatch.setattr(ingest, "_avisar", lambda chat, texto: avisos.append((chat, texto)))
    repo.upsert_plan("publica", {"permite_extras": False})
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica", confiable=True)
    _publicar(repo, c, 15)

    r = ingest.handle_message(_mensaje(repo, c), repo)
    assert r["publicada"] is False
    assert avisos and avisos[0][0] == "120363@g.us"
    assert "Destacado" in avisos[0][1]


def test_si_no_se_puede_avisar_la_publicacion_sigue_su_curso(repo, monkeypatch):
    """Un aviso perdido es molesto; una oferta perdida por fallar al avisar es
    absurdo."""
    def _explota(chat, texto):
        raise RuntimeError("WAHA caído")
    monkeypatch.setattr("app.services.whatsapp_client.enviar_texto", _explota)
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica", confiable=True)
    _publicar(repo, c, 15)

    antes = len(repo.publicaciones)
    r = ingest.handle_message(_mensaje(repo, c), repo)

    # Lo que importa no es en qué estado quedó —eso lo decide si el remitente es
    # conocido, que es otra regla— sino que el mensaje siguió su curso: se creó
    # la publicación y quedó el cargo, con el aviso caído.
    assert r["captured"] is True
    assert len(repo.publicaciones) == antes + 1
    assert len(repo.cargos_extra) == 1


def test_dentro_de_la_cuota_no_avisa_ni_cobra(repo, monkeypatch):
    avisos = []
    monkeypatch.setattr(ingest, "_avisar", lambda chat, texto: avisos.append(texto))
    c = repo.seed_comercio(slug="x", nombre="X", plan="publica", confiable=True)
    _publicar(repo, c, 3)

    ingest.handle_message(_mensaje(repo, c), repo)
    assert avisos == []
    assert repo.cargos_extra == []


def test_el_plan_caro_trae_algo_que_el_barato_no(repo):
    """Un plan de Bs 1.250 que no suma ninguna función sobre el de 400 no tiene
    nada que vender: el comerciante mira los dos y elige el barato, con razón."""
    caro = repo.get_plan("empleado_ia")
    pro = repo.get_plan("pro")
    extras = set(caro["funciones"]) - set(pro["funciones"])
    assert "asistente_24_7" in extras
    assert float(caro["precio_mes"]) > float(pro["precio_mes"])
