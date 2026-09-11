"""La oferta aprobada sale a las redes de URUKU.

Lo que se prueba acá no es que la llamada a Meta funcione —eso lo dice Meta—,
sino las reglas que hacen que el muro de la marca no se ensucie: que no salga
nada sin aprobar, que nada salga dos veces, y que un envío fallido quede
visible en vez de perderse.
"""
import pytest

from app.core.config import settings
from app.services import difusion


def _h(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def config_completa(monkeypatch):
    # Estos tests prueban las ESCRITURAS a las redes, así que apagan la llave
    # de sólo lectura. Que arranque puesta se prueba aparte, más abajo.
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    monkeypatch.setattr(settings, "wa_canal_id", "1203@newsletter")
    monkeypatch.setattr(settings, "waha_base_url", "http://waha:3000")
    monkeypatch.setattr(settings, "waha_api_key", "k")
    monkeypatch.setattr(settings, "facebook_page_id", "111")
    monkeypatch.setattr(settings, "facebook_page_token", "tok")
    monkeypatch.setattr(settings, "instagram_user_id", "222")


@pytest.fixture
def sin_red(monkeypatch):
    """Nadie llama a un servidor de verdad en los tests."""
    enviados = []
    monkeypatch.setattr(difusion, "_ENVIOS", {
        d: (lambda texto, img, _d=d: enviados.append((_d, texto, img)) or None)
        for d in difusion.DESTINOS
    })
    return enviados


# ═══════════════════════════════════════════════════════════ el texto

def test_el_texto_lleva_el_comercio_y_el_enlace():
    """Sin el nombre, la oferta parece de URUKU y el comerciante no recibe nada
    de lo que se le prometió. Sin el enlace, el que la ve no tiene cómo llegar
    y el posteo es decoración."""
    t = difusion.texto_de(
        {"titulo": "Zapatillas", "precio": 250, "moneda": "BOB"},
        {"nombre": "Calzados Top", "slug": "calzados-top"})
    assert "Zapatillas" in t
    assert "Bs 250" in t
    assert "Calzados Top" in t
    assert "/comercios/calzados-top" in t


def test_una_oferta_sin_precio_no_inventa_uno():
    t = difusion.texto_de({"titulo": "Llegó mercadería"}, {"nombre": "X", "slug": "x"})
    assert "Bs" not in t


# ═══════════════════════════════════════════════════════ qué sale y qué no

def test_solo_sale_lo_aprobado(client, repo, sin_red, config_completa):
    """La guarda que impide que una foto sin mirar aparezca en el muro de la
    marca. Es un error que no se deshace: rechazar la publicación en el panel no
    la baja de Facebook."""
    c = repo.seed_comercio(slug="x", nombre="X")
    pub = repo.insert_publicacion_directa(
        {"comercio_id": c["id"], "tipo": "oferta", "titulo": "algo", "estado": "pendiente"})
    difusion.encolar(repo, pub["id"])

    r = difusion.enviar_pendientes(repo, 10, solo_auto=False)
    assert r["resumen"]["enviado"] == 0
    assert r["resumen"]["omitido"] == 3
    assert sin_red == []


def test_la_misma_oferta_no_se_encola_dos_veces(repo, monkeypatch):
    """Se rechaza y se vuelve a aprobar: encola de nuevo. Sin la clave única,
    eso son dos posteos idénticos en el mismo muro — que es justo lo que hace
    que la gente deje de seguir la página."""
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    c = repo.seed_comercio(slug="x", nombre="X")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado"})

    assert difusion.encolar(repo, pub["id"]) == 3
    assert difusion.encolar(repo, pub["id"]) == 0


def test_lo_aprobado_sale_a_las_tres_redes(client, repo, admin_token, sin_red, config_completa):
    c = repo.seed_comercio(slug="x", nombre="X")
    pub = repo.insert_publicacion_directa(
        {"comercio_id": c["id"], "tipo": "oferta", "titulo": "oferta", "estado": "aprobado"})
    difusion.encolar(repo, pub["id"])

    r = client.post("/admin/difusion/enviar?limite=10", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["resumen"]["enviado"] == 3
    assert {d for d, _, _ in sin_red} == set(difusion.DESTINOS)


def test_solo_auto_manda_los_destinos_del_env(repo, sin_red, config_completa, monkeypatch):
    """El automático es sólo el canal de WhatsApp: lo siguen personas que se
    anotaron para recibir ofertas. Un muro de Facebook con veinte ofertas por
    día es cómo una página pierde alcance."""
    monkeypatch.setattr(settings, "difusion_auto", "wa_canal")
    c = repo.seed_comercio(slug="x", nombre="X")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado"})
    difusion.encolar(repo, pub["id"])

    difusion.enviar_pendientes(repo, 10, solo_auto=True)
    assert [d for d, _, _ in sin_red] == ["wa_canal"]


# ═══════════════════════════════════════════════════ cuando algo falla

def test_un_destino_sin_configurar_espera_en_vez_de_perderse(repo, monkeypatch):
    """Queda pendiente, no en error: el día que pegan el token se manda lo
    atrasado. Si no se encolara, todo lo aprobado antes de configurar Facebook
    habría que buscarlo a mano en la base."""
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    monkeypatch.setattr(settings, "facebook_page_token", "")
    monkeypatch.setattr(settings, "facebook_page_id", "")
    c = repo.seed_comercio(slug="x", nombre="X")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado"})
    difusion.encolar(repo, pub["id"])

    fila = next(f for f in repo.difusion if f["destino"] == "facebook")
    r = difusion.procesar(repo, fila)
    assert r["estado"] == "pendiente"
    assert "no está configurado" in fila["motivo"]


def test_un_envio_que_falla_queda_con_el_motivo(repo, config_completa, monkeypatch):
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    """Un error invisible es una oferta que el comerciante espera ver y no
    aparece. El motivo se guarda para que el panel lo muestre."""
    def _explota(texto, img):
        raise difusion.DifusionError("HTTP 401: token vencido")
    monkeypatch.setattr(difusion, "_ENVIOS", {d: _explota for d in difusion.DESTINOS})

    c = repo.seed_comercio(slug="x", nombre="X")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado"})
    difusion.encolar(repo, pub["id"])
    fila = repo.difusion[0]

    r = difusion.procesar(repo, fila)
    assert r["estado"] == "error"
    assert "token vencido" in fila["motivo"]
    assert fila["intentos"] == 1


def test_encolar_nunca_rompe_la_aprobacion(repo, monkeypatch):
    """La regla que sostiene todo lo demás: aprobar una oferta no puede fallar
    porque a Meta se le venció un token."""
    def _explota(*a, **k):
        raise RuntimeError("la base se cayó")
    monkeypatch.setattr(repo, "encolar_difusion", _explota)
    assert difusion.encolar(repo, "id-cualquiera") == 0


def test_instagram_no_publica_sin_imagen(config_completa):
    with pytest.raises(difusion.DifusionError, match="sin imagen"):
        difusion._enviar_instagram("texto", None)


# ══════════════════════════════════════════════════════════ el panel

def test_aprobar_desde_el_panel_encola(client, repo, admin_token, monkeypatch):
    """El enganche: si esto se rompe, la difusión existe y no la dispara nadie."""
    monkeypatch.setattr(settings, "wa_solo_lectura", False)
    c = repo.seed_comercio(slug="x", nombre="X", codigo="AB12")
    pub = repo.insert_publicacion_directa(
        {"comercio_id": c["id"], "tipo": "oferta", "titulo": "t", "estado": "pendiente",
         "codigo_recibido": "AB12"})

    r = client.post(f"/moderacion/publicaciones/{pub['id']}",
                    json={"estado": "aprobado"}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    assert r.json()["difusion_encolada"] == 3


def test_rechazar_no_encola(client, repo, admin_token):
    c = repo.seed_comercio(slug="x", nombre="X")
    pub = repo.insert_publicacion_directa(
        {"comercio_id": c["id"], "tipo": "oferta", "estado": "pendiente"})

    client.post(f"/moderacion/publicaciones/{pub['id']}",
                json={"estado": "rechazado"}, headers=_h(admin_token))
    assert repo.difusion == []


def test_no_se_puede_reintentar_algo_ya_publicado(client, repo, admin_token, config_completa):
    """Reintentar lo enviado es publicarlo dos veces."""
    c = repo.seed_comercio(slug="x", nombre="X")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado"})
    difusion.encolar(repo, pub["id"])
    fila = repo.difusion[0]
    repo.marcar_difusion(fila["id"], "enviado", None, "https://facebook.com/1")

    r = client.post(f"/admin/difusion/{fila['id']}/reintentar", headers=_h(admin_token))
    assert r.status_code == 409
    assert "duplicar" in r.json()["detail"]


def test_el_panel_dice_que_destinos_faltan(client, repo, admin_token, monkeypatch):
    """Sin esto, "no se publica nada en Facebook" y "se publica y falla" se ven
    igual — y se arreglan de maneras opuestas."""
    monkeypatch.setattr(settings, "facebook_page_token", "")
    r = client.get("/admin/difusion", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    fb = next(d for d in r.json()["destinos"] if d["clave"] == "facebook")
    assert fb["configurado"] is False


def test_los_envios_van_espaciados(repo, sin_red, config_completa, monkeypatch):
    """La pausa entre envíos es lo que evita el baneo del operativo.

    Después de una tanda de moderación se aprueban muchas ofertas de golpe; sin
    pausa saldrían todas en pocos segundos, que es la ráfaga que WhatsApp lee
    como automatización. Y el baneado sería el número vinculado a WAHA, que es
    el mismo que está en todos los grupos y el dueño del canal: se caen las tres
    cosas juntas.

    No espera de verdad —eso haría la suite inservible—: comprueba que pide la
    espera, una vez menos que envíos.
    """
    monkeypatch.setattr(settings, "difusion_pausa_seg", 20)
    esperas = []
    monkeypatch.setattr("time.sleep", lambda s: esperas.append(s))

    c = repo.seed_comercio(slug="x", nombre="X")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado"})
    difusion.encolar(repo, pub["id"])

    r = difusion.enviar_pendientes(repo, 10, solo_auto=False)
    assert r["resumen"]["enviado"] == 3
    assert esperas == [20, 20]


# ══════════════════════════════════════════════════════ el tope del canal

def test_el_canal_no_publica_mas_de_lo_configurado(repo, sin_red, config_completa, monkeypatch):
    """Cada publicación al canal es una notificación en el teléfono de cada
    seguidor. Cincuenta por día es cómo se pierde a los seguidores, que son lo
    único que no se puede rehacer."""
    monkeypatch.setattr(settings, "difusion_canal_max_dia", 2)
    monkeypatch.setattr(settings, "difusion_auto", "wa_canal")
    c = repo.seed_comercio(slug="x", nombre="X")
    for i in range(5):
        pub = repo.insert_publicacion_directa(
            {"comercio_id": c["id"], "titulo": f"of {i}", "estado": "aprobado"})
        difusion.encolar(repo, pub["id"])

    difusion.enviar_pendientes(repo, 20, solo_auto=True)
    assert len([d for d, _, _ in sin_red if d == "wa_canal"]) == 2


def test_lo_que_no_entra_hoy_espera_para_mañana(repo, sin_red, config_completa, monkeypatch):
    """Pendiente, no omitida. Una oferta descartada por el tope de ayer es una
    que el comerciante nunca va a ver publicada."""
    monkeypatch.setattr(settings, "difusion_canal_max_dia", 1)
    monkeypatch.setattr(settings, "difusion_auto", "wa_canal")
    c = repo.seed_comercio(slug="x", nombre="X")
    for i in range(3):
        pub = repo.insert_publicacion_directa(
            {"comercio_id": c["id"], "titulo": f"of {i}", "estado": "aprobado"})
        difusion.encolar(repo, pub["id"])

    difusion.enviar_pendientes(repo, 20, solo_auto=True)
    esperando = [f for f in repo.difusion
                 if f["destino"] == "wa_canal" and f["estado"] == "pendiente"]
    assert len(esperando) == 2
    assert "sale mañana" in esperando[0]["motivo"]


def test_el_tope_no_frena_facebook_ni_instagram(repo, sin_red, config_completa, monkeypatch):
    """Esas redes tienen algoritmo: el que no quiere ver sigue scrolleando. El
    canal es una notificación en el teléfono, y por eso es el único con tope."""
    monkeypatch.setattr(settings, "difusion_canal_max_dia", 1)
    c = repo.seed_comercio(slug="x", nombre="X")
    for i in range(3):
        pub = repo.insert_publicacion_directa(
            {"comercio_id": c["id"], "titulo": f"of {i}", "estado": "aprobado"})
        difusion.encolar(repo, pub["id"])

    difusion.enviar_pendientes(repo, 30, solo_auto=False)
    assert len([d for d, _, _ in sin_red if d == "facebook"]) == 3
    assert len([d for d, _, _ in sin_red if d == "wa_canal"]) == 1


def test_el_lugar_en_el_canal_se_puede_reservar_a_los_planes_que_lo_pagan(
    repo, sin_red, config_completa, monkeypatch,
):
    """Es lo que convierte el problema de volumen en una razón para subir de
    plan, en vez de un derecho ilimitado que arruina el canal para todos."""
    monkeypatch.setattr(settings, "difusion_canal_solo_planes", True)
    monkeypatch.setattr(settings, "difusion_auto", "wa_canal")
    barato = repo.seed_comercio(slug="a", nombre="A", plan="publica")
    caro = repo.seed_comercio(slug="b", nombre="B", plan="destacado")
    for c in (barato, caro):
        pub = repo.insert_publicacion_directa(
            {"comercio_id": c["id"], "titulo": "of", "estado": "aprobado"})
        difusion.encolar(repo, pub["id"])

    difusion.enviar_pendientes(repo, 20, solo_auto=True)
    assert len([d for d, _, _ in sin_red if d == "wa_canal"]) == 1


def test_reservarlo_a_los_planes_arranca_apagado():
    """Hoy no paga nadie: encenderlo antes de que haya un plan contratado
    dejaría el canal vacío sin dar ningún error."""
    assert settings.difusion_canal_solo_planes is False


# ═══════════════════════════════════════════ WAHA sólo lee (decisión del 11/9)

def test_por_defecto_waha_solo_lee():
    """El Registrador existe para llevar lo que llega a la base. Nada más."""
    assert settings.wa_solo_lectura is True


def test_con_solo_lectura_el_canal_no_se_encola(repo):
    """Se publica a mano desde la tablet. Encolarlo igual llenaría la cola de
    filas que nunca van a salir, y el panel diría "N esperando" para siempre."""
    c = repo.seed_comercio(slug="x", nombre="X")
    pub = repo.insert_publicacion_directa({"comercio_id": c["id"], "estado": "aprobado"})
    assert difusion.encolar(repo, pub["id"]) == 2
    assert {f["destino"] for f in repo.difusion} == {"facebook", "instagram"}


def test_con_solo_lectura_el_canal_figura_como_manual(client, admin_token):
    r = client.get("/admin/difusion", headers=_h(admin_token))
    canal = next(d for d in r.json()["destinos"] if d["clave"] == "wa_canal")
    assert canal["manual"] is True
    assert canal["configurado"] is False


def test_con_solo_lectura_nada_sale_por_waha(monkeypatch):
    """La única puerta de salida por WAHA, cerrada con llave. Si esto se
    rompiera, el Registrador empezaría a escribir en los grupos."""
    from app.services import mensajeria

    llamadas = []
    monkeypatch.setattr(mensajeria, "_waha_texto", lambda c, t: llamadas.append(c) or True)
    monkeypatch.setattr(mensajeria, "_waha_imagen", lambda c, u, t: llamadas.append(c) or True)
    assert mensajeria.enviar_texto("120363@g.us", "hola") is False
    assert mensajeria.enviar_imagen("120363@g.us", "http://x/1.jpg") is False
    assert llamadas == []


def test_la_api_oficial_no_esta_sujeta_a_la_llave(monkeypatch):
    """La llave es sobre WAHA. El número de la marca, por la API oficial, sí
    escribe — para eso existe."""
    from app.services import mensajeria

    monkeypatch.setattr(settings, "whatsapp_provider", "cloud_api")
    llamadas = []
    monkeypatch.setattr(mensajeria, "_cloud_texto", lambda c, t: llamadas.append(c) or True)
    assert mensajeria.enviar_texto("59170000001", "hola") is True
    assert llamadas == ["59170000001"]
