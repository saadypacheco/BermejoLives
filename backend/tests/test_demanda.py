"""El informe de demanda: qué busca la gente y qué no encuentra.

Es el primero de los agentes de Uruku AI y el único que se puede construir hoy,
porque es el único que no necesita datos que todavía no existen. No usa modelo:
es una cuenta sobre las búsquedas que ya se registran.

Lo que se prueba acá es sobre todo que el informe no sea vergonzoso delante de
un comerciante — que es el uso real que va a tener.
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.services import demanda


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _buscar(repo, termino, resultados=5, veces=1):
    for _ in range(veces):
        repo.insert_busqueda(termino, resultados)


# ═════════════════════════════════════════════════════════ normalización

def test_la_misma_demanda_no_se_parte_en_tres():
    """"Zapatillas", "zapatillas " y "ZAPATILLAS" son lo mismo. Contarlas
    aparte divide el número y hace que nada parezca importante."""
    assert (demanda.normalizar("Zapatillas ") == demanda.normalizar("ZAPATILLAS")
            == demanda.normalizar("zapatillas"))


def test_las_tildes_no_separan():
    assert demanda.normalizar("Colchón") == demanda.normalizar("colchon")


# ══════════════════════════════════════════════════════════ el tecleo

def test_el_tecleo_no_aparece_como_demanda(repo):
    """El buscador registra mientras la persona escribe, así que una búsqueda de
    "zapatillas" deja también "zap", "zapa", "zapati"…

    Sin filtrarlo, el informe dice que lo más buscado en Bermejo es "zap" — y
    eso, mostrado a un comerciante, no vuelve a abrir esa puerta.
    """
    for t in ("zap", "zapa", "zapati", "zapatill", "zapatillas"):
        _buscar(repo, t)

    inf = demanda.informe(repo)
    assert [f["termino"] for f in inf["top"]] == ["zapatillas"]
    assert inf["descartados_por_tecleo"] == 4


def test_un_termino_corto_que_se_busca_solo_sigue_contando(repo):
    """"sillas" no es el tecleo de "sillas de oficina" si se buscó más veces por
    su cuenta. Descartarlo perdería demanda real."""
    _buscar(repo, "sillas", veces=10)
    _buscar(repo, "sillas de oficina", veces=2)

    inf = demanda.informe(repo)
    terminos = [f["termino"] for f in inf["top"]]
    assert "sillas" in terminos and "sillas de oficina" in terminos


def test_lo_muy_corto_se_ignora(repo):
    """Menos de tres letras no es una búsqueda, es alguien tanteando."""
    _buscar(repo, "a", veces=50)
    _buscar(repo, "ropa", veces=2)

    assert [f["termino"] for f in demanda.informe(repo)["top"]] == ["ropa"]


# ═══════════════════════════════════════════════ la parte que se vende

def test_lo_que_no_encontro_nada_va_aparte_y_ordenado(repo):
    """Es lo único que vale del informe: demanda que hoy se va sin comprar."""
    _buscar(repo, "heladeras", resultados=0, veces=7)
    _buscar(repo, "pañales", resultados=0, veces=3)
    _buscar(repo, "ropa", resultados=12, veces=30)

    inf = demanda.informe(repo)
    assert [f["termino"] for f in inf["oportunidades"]] == ["heladeras", "pañales"]
    assert inf["oportunidades"][0]["sin_resultado"] == 7


def test_un_termino_que_a_veces_encuentra_y_a_veces_no(repo):
    """El mismo término puede dar resultados un día y ninguno otro. Cuenta las
    veces que falló, no si alguna vez anduvo."""
    _buscar(repo, "colchones", resultados=0, veces=4)
    _buscar(repo, "colchones", resultados=3, veces=1)

    inf = demanda.informe(repo)
    fila = inf["oportunidades"][0]
    assert fila["veces"] == 5 and fila["sin_resultado"] == 4


def test_la_frase_de_venta_sale_armada(repo):
    _buscar(repo, "heladeras", resultados=0, veces=9)
    frase = demanda.frase_de_venta(demanda.informe(repo))
    assert "9 personas" in frase and "heladeras" in frase


def test_no_se_arma_una_frase_con_dos_busquedas(repo):
    """Se dice una sola vez, delante de alguien. Un número ridículo pierde la
    conversación entera, y eso es peor que no decir nada."""
    _buscar(repo, "heladeras", resultados=0, veces=2)
    assert demanda.frase_de_venta(demanda.informe(repo)) is None


def test_sin_busquedas_no_inventa_nada(repo):
    inf = demanda.informe(repo)
    assert inf["top"] == [] and inf["oportunidades"] == []
    assert demanda.frase_de_venta(inf) is None


# ═════════════════════════════════════════════════════════ la ventana

def test_solo_mira_los_dias_pedidos(repo):
    """Una demanda de hace tres meses no es una oportunidad de hoy."""
    _buscar(repo, "paraguas", resultados=0, veces=5)
    viejo = (datetime.now(timezone.utc) - timedelta(days=60)).isoformat()
    for b in repo.busquedas:
        b["created_at"] = viejo

    assert demanda.informe(repo, dias=7)["top"] == []
    assert demanda.informe(repo, dias=90)["top"] != []


# ═══════════════════════════════════════════════════════════ el panel

def test_el_endpoint_devuelve_el_informe(client, repo, admin_token):
    _buscar(repo, "heladeras", resultados=0, veces=6)
    r = client.get("/admin/demanda?dias=7", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["oportunidades"][0]["termino"] == "heladeras"
    assert "6 personas" in d["frase"]


def test_solo_moderador(client):
    assert client.get("/admin/demanda").status_code in (401, 403)


def test_la_eñe_y_la_u_con_dieresis_sobreviven():
    """No son vocales con tilde: son letras distintas, y sacarles el signo
    cambia la palabra. "pañales" se vuelve "panales" y "año" se vuelve algo que
    no se le muestra a un comerciante."""
    assert demanda.normalizar("Pañales") == "pañales"
    assert demanda.normalizar("AÑO") == "año"
    assert demanda.normalizar("Pingüino") == "pingüino"
    # Y las tildes de verdad sí se van, que es para lo que existe la función.
    assert demanda.normalizar("Colchón") == "colchon"
