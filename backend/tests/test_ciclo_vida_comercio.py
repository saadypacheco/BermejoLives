"""Ciclo de vida del comercio: alta mínima → segunda pasada → pago → login → publica.

Cada test cubre un tramo que antes estaba cortado.
"""
from datetime import date, datetime, timedelta, timezone

import pytest


# ---------------------------------------------------------------- puente al login
def test_comercio_de_campo_no_tiene_login_hasta_que_paga(repo):
    """El alta de campo crea el comercio pero no la cuenta: así se cargó rápido."""
    c = repo.seed_comercio(nombre="Ferretería", whatsapp="59170123456", activo=True)
    assert repo.get_comercio_usuario_por_whatsapp("59170123456") is None


def test_el_pago_le_crea_la_cuenta_al_comercio(client, repo, admin_token):
    """Este es el tramo 3→4: sin esto el comercio pagaba y no podía entrar."""
    c = repo.seed_comercio(nombre="Ferretería", whatsapp="59170123456", activo=True)

    r = client.post(f"/admin/comercio/{c['id']}/pago",
                    json={"monto": 150, "moneda": "BOB", "metodo": "efectivo", "meses": 1},
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    assert r.json()["login"] is True

    # Ahora sí la recuperación por WhatsApp encuentra la cuenta.
    assert repo.get_comercio_usuario_por_whatsapp("59170123456") is not None


def test_asegurar_usuario_es_idempotente(repo):
    c = repo.seed_comercio(nombre="Ferretería", whatsapp="59170123456", activo=True)
    primero = repo.asegurar_comercio_usuario(c["id"])
    segundo = repo.asegurar_comercio_usuario(c["id"])
    assert primero["id"] == segundo["id"]
    assert len(repo.usuarios) == 1


# ------------------------------------------------------------- caída del mapa
def _hace(dias: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=dias)).isoformat()


def test_el_que_nunca_pago_cae_a_los_60_dias(repo):
    """La segunda pasada: se carga rápido, y a los 2 meses o paga o desaparece.

    Antes esto no pasaba nunca: el filtro por paga_hasta excluye los NULL.
    """
    viejo = repo.seed_comercio(nombre="Viejo", created_at=_hace(70), activo=True)
    nuevo = repo.seed_comercio(nombre="Nuevo", created_at=_hace(10), activo=True)

    ocultos = repo.ocultar_comercios_vencidos(dias=40, dias_gracia=60)

    assert ocultos == 1
    assert repo.comercios[viejo["id"]]["activo"] is False
    assert repo.comercios[nuevo["id"]]["activo"] is True


def test_sin_gracia_configurada_no_se_toca_a_los_gratis(repo):
    """dias_gracia=None = comportamiento viejo, para la etapa de captación."""
    viejo = repo.seed_comercio(nombre="Viejo", created_at=_hace(400), activo=True)
    assert repo.ocultar_comercios_vencidos(dias=40, dias_gracia=None) == 0
    assert repo.comercios[viejo["id"]]["activo"] is True


def test_el_que_pago_y_vencio_cae_por_su_propio_reloj(repo):
    vencido = repo.seed_comercio(
        nombre="Vencido", created_at=_hace(5),
        paga_hasta=(date.today() - timedelta(days=50)).isoformat(), activo=True)
    al_dia = repo.seed_comercio(
        nombre="Al día", created_at=_hace(400),
        paga_hasta=(date.today() + timedelta(days=10)).isoformat(), activo=True)

    ocultos = repo.ocultar_comercios_vencidos(dias=40, dias_gracia=60)

    assert ocultos == 1
    assert repo.comercios[vencido["id"]]["activo"] is False
    # Pagó: su antigüedad no lo baja, aunque tenga 400 días.
    assert repo.comercios[al_dia["id"]]["activo"] is True


# ------------------------------------------------- identidad por número
def test_el_dueno_que_escribe_no_crea_un_comercio_duplicado(repo):
    """El comercio de campo tiene whatsapp pero no wa_jid: buscarlo sólo por jid
    creaba un 'Comercio 3456' nuevo cada vez."""
    c = repo.seed_comercio(nombre="Ferretería", whatsapp="59170123456", activo=True)
    antes = len(repo.comercios)

    encontrado = repo.upsert_comercio_by_jid("59170123456@c.us", "59170123456")

    assert encontrado["id"] == c["id"]
    assert len(repo.comercios) == antes
    assert repo.comercios[c["id"]]["wa_jid"] == "59170123456@c.us"


def test_reconcilia_aunque_el_agente_haya_cargado_el_numero_sin_prefijo(repo):
    """En la calle se tipea '70123456'; WhatsApp llega como '59170123456'."""
    c = repo.seed_comercio(nombre="Ferretería", whatsapp="70123456", activo=True)
    encontrado = repo.upsert_comercio_by_jid("59170123456@c.us", "59170123456")
    assert encontrado["id"] == c["id"]


def test_un_numero_desconocido_si_crea_comercio_nuevo(repo):
    antes = len(repo.comercios)
    creado = repo.upsert_comercio_by_jid("59171111111@c.us", "59171111111")
    assert len(repo.comercios) == antes + 1
    # Y queda autorizado, así que la próxima vez lo encuentra por número.
    assert repo.get_comercio_por_numero("59171111111")["id"] == creado["id"]


def test_numero_del_empleado_apunta_al_comercio(repo, client, admin_token):
    """El número que MANDA productos no es necesariamente el número público."""
    c = repo.seed_comercio(nombre="Ferretería", whatsapp="59170123456", activo=True)

    r = client.post(f"/admin/comercio/{c['id']}/numeros",
                    json={"numero": "60999888", "etiqueta": "vendedora del local"},
                    headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text

    # Ese número ahora resuelve al mismo comercio, sin ser el público.
    assert repo.get_comercio_por_numero("59160999888")["id"] == c["id"]
    assert repo.comercios[c["id"]]["whatsapp"] == "59170123456"


def test_numero_invalido_se_rechaza_al_autorizar(client, repo, admin_token):
    c = repo.seed_comercio(nombre="Ferretería", activo=True)
    r = client.post(f"/admin/comercio/{c['id']}/numeros",
                    json={"numero": "no tengo"}, headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 400


# ------------------------------------------------------------------ confiable
def test_admin_puede_marcar_confiable(client, repo, admin_token):
    """Antes no había forma de escribir este flag: todo iba a moderación."""
    c = repo.seed_comercio(nombre="Ferretería", activo=True)
    assert repo.comercios[c["id"]]["confiable"] is False

    r = client.post(f"/admin/comercio/{c['id']}/confiable",
                    json={"confiable": True}, headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    assert repo.comercios[c["id"]]["confiable"] is True

    r = client.post(f"/admin/comercio/{c['id']}/confiable",
                    json={"confiable": False}, headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200
    assert repo.comercios[c["id"]]["confiable"] is False


# ------------------------------------------------------- gate por plan
def test_ingesta_abierta_por_default(repo):
    """Durante la captación cualquiera puede mandar productos por WhatsApp."""
    from app.services.ingest import _puede_publicar_por_whatsapp
    assert _puede_publicar_por_whatsapp({"plan": "gratis"}) is True


def test_ingesta_gateada_cuando_se_prende(monkeypatch):
    from app.core.config import settings
    from app.services.ingest import _puede_publicar_por_whatsapp

    monkeypatch.setattr(settings, "ingesta_requiere_plan", True)
    monkeypatch.setattr(settings, "planes_con_ingesta", "premium")

    assert _puede_publicar_por_whatsapp({"plan": "premium"}) is True
    assert _puede_publicar_por_whatsapp({"plan": "pro"}) is False
    assert _puede_publicar_por_whatsapp({"plan": "gratis"}) is False
    assert _puede_publicar_por_whatsapp({}) is False


# --------------------------------------------------------- bajas manuales
def test_bajas_manual_no_toca_gratis_con_gracia_apagada(client, repo, admin_token):
    """Default de producción: la gracia está apagada hasta revisar a quién alcanza."""
    from app.core.config import settings
    assert settings.dias_gracia_sin_pago is None

    c = repo.seed_comercio(nombre="Viejo", created_at=_hace(400), activo=True)
    r = client.post("/admin/bajas/ejecutar", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    assert r.json()["ocultos"] == 0
    assert repo.comercios[c["id"]]["activo"] is True


def test_bajas_manual_con_gracia_prendida(client, repo, admin_token, monkeypatch):
    from app.core.config import settings
    monkeypatch.setattr(settings, "dias_gracia_sin_pago", 60)

    c = repo.seed_comercio(nombre="Viejo", created_at=_hace(400), activo=True)
    r = client.post("/admin/bajas/ejecutar", headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    assert r.json()["ocultos"] == 1
    assert repo.comercios[c["id"]]["activo"] is False
