"""Sumar un respaldo a los grupos que ya existen.

Es la salida a un problema de tiempo: el sistema mete a los respaldos que
estaban configurados cuando creó cada grupo, así que uno dado de alta después
queda afuera de todos los anteriores. El costo se paga tarde y entero — el día
del baneo, cada grupo sin respaldo es un comerciante perdido, y una cuenta ya
baneada no puede agregar a nadie.
"""
import pytest

from app.services import wa_grupos


def _h(token):
    return {"Authorization": f"Bearer {token}"}


RUTA = "/admin/whatsapp/grupos/agregar-numero"


@pytest.fixture
def tres_grupos(repo):
    for i, nombre in enumerate(["Ofertas Uno", "Ofertas Dos", "Ofertas Tres"]):
        c = repo.seed_comercio(slug=f"c{i}", nombre=nombre.replace("Ofertas ", ""))
        repo.vincular_grupo_comercio(f"12036{i}@g.us", c["id"], nombre, "admin", "test")
    return repo


def test_la_vista_previa_no_toca_whatsapp(client, admin_token, tres_grupos, monkeypatch):
    """Sin `aplicar` no se agrega nadie. Si esto se rompiera, el botón de mirar
    sería el botón de hacer — y en este panel hacer significa tocar los grupos
    de comerciantes reales."""
    monkeypatch.setattr(wa_grupos, "participantes_de_grupo", lambda jid: [])
    def _explota(*a, **k):
        raise AssertionError("la vista previa no puede agregar a nadie")
    monkeypatch.setattr(wa_grupos, "agregar_a_grupo", _explota)

    r = client.post(RUTA, json={"numero": "59168727584"}, headers=_h(admin_token))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["aplicado"] is False
    assert d["a_agregar"] == 3
    assert [g["nombre"] for g in d["grupos"]] == ["Ofertas Uno", "Ofertas Dos", "Ofertas Tres"]


def test_saltea_los_grupos_donde_el_numero_ya_esta(client, admin_token, tres_grupos, monkeypatch):
    """Repetir la corrida no puede volver a pedirle lo mismo a WhatsApp: pedir
    de más es exactamente lo que dispara el baneo."""
    monkeypatch.setattr(wa_grupos, "participantes_de_grupo",
                        lambda jid: ["59168727584"] if jid == "120360@g.us" else ["59164610187"])
    tocados = []
    monkeypatch.setattr(wa_grupos, "agregar_a_grupo",
                        lambda jid, nums: tocados.append(jid))

    r = client.post(RUTA, json={"numero": "59168727584", "aplicar": True},
                    headers=_h(admin_token))
    d = r.json()
    assert d["ya_estaba"] == 1
    assert d["agregados"] == 2
    assert "120360@g.us" not in tocados


def test_si_no_se_puede_leer_quien_esta_adentro_se_intenta_igual(
    client, admin_token, tres_grupos, monkeypatch,
):
    """`None` es "no sé", no "ya está". Dar por sentado que está adentro es cómo
    un respaldo termina faltando justo en el grupo donde hacía falta; un
    agregado repetido, en cambio, lo rechaza WhatsApp sin consecuencias."""
    monkeypatch.setattr(wa_grupos, "participantes_de_grupo", lambda jid: None)
    tocados = []
    monkeypatch.setattr(wa_grupos, "agregar_a_grupo", lambda jid, nums: tocados.append(jid))

    r = client.post(RUTA, json={"numero": "59168727584", "aplicar": True},
                    headers=_h(admin_token))
    assert r.json()["agregados"] == 3
    assert len(tocados) == 3


def test_el_tope_corta_la_tanda_y_avisa_cuantos_quedan(
    client, admin_token, tres_grupos, monkeypatch,
):
    """El tope es el freno contra el baneo, no un detalle de paginado: tiene que
    cortar de verdad y decir cuántos quedaron para la próxima."""
    monkeypatch.setattr(wa_grupos, "participantes_de_grupo", lambda jid: [])
    tocados = []
    monkeypatch.setattr(wa_grupos, "agregar_a_grupo", lambda jid, nums: tocados.append(jid))

    r = client.post(RUTA, json={"numero": "59168727584", "aplicar": True, "tope": 2},
                    headers=_h(admin_token))
    d = r.json()
    assert len(tocados) == 2
    assert d["agregados"] == 2
    assert d["quedan_despues"] == 1


def test_un_grupo_que_falla_no_corta_la_corrida_pero_se_informa(
    client, admin_token, tres_grupos, monkeypatch,
):
    """Los otros se agregan igual, y el que falló va con nombre y motivo:
    "2 de 3" sin decir cuál faltó es un número que no sirve para ir a
    arreglarlo."""
    monkeypatch.setattr(wa_grupos, "participantes_de_grupo", lambda jid: [])

    def _agregar(jid, nums):
        if jid == "120361@g.us":
            raise wa_grupos.GrupoError("HTTP 404: group not found")
    monkeypatch.setattr(wa_grupos, "agregar_a_grupo", _agregar)

    r = client.post(RUTA, json={"numero": "59168727584", "aplicar": True},
                    headers=_h(admin_token))
    d = r.json()
    assert d["agregados"] == 2
    assert len(d["fallaron"]) == 1
    assert d["fallaron"][0]["grupo"] == "Ofertas Dos"
    assert "404" in d["fallaron"][0]["motivo"]


def test_un_numero_invalido_se_rechaza_antes_de_tocar_nada(client, admin_token, tres_grupos):
    """Un número mal escrito no puede convertirse en una tanda de llamadas a
    WhatsApp con un JID inventado."""
    r = client.post(RUTA, json={"numero": "no-es-un-numero", "aplicar": True},
                    headers=_h(admin_token))
    assert r.status_code == 400


def test_solo_admin(client, tres_grupos):
    assert client.post(RUTA, json={"numero": "59168727584"}).status_code in (401, 403)
