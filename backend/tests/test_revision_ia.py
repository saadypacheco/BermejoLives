"""La IA revisa lo que entra, antes de que lo mire una persona.

Lo que se prueba acá no es que Gemini opine bien —eso no se puede probar sin
Gemini— sino las reglas alrededor: que revise sólo lo que corresponde, que la
cola llegue ordenada, que un fallo no corte el loop, y sobre todo que NO
apruebe sola salvo que alguien lo haya decidido a propósito.
"""
import pytest

from app.core.config import settings
from app.services import revision_ia


def _h(token):
    return {"Authorization": f"Bearer {token}"}


def _pub(repo, comercio, titulo, estado="pendiente", **extra):
    return repo.insert_publicacion_directa(
        {"comercio_id": comercio["id"], "tipo": "oferta", "titulo": titulo,
         "estado": estado, "created_at": "2026-09-10T10:00:00+00:00", **extra})


@pytest.fixture
def ia(monkeypatch):
    """Una IA de mentira que contesta según el título. Deja anotado a quién le
    preguntaron, que es la mitad de lo que hay que verificar."""
    consultas = []

    def _moderar(titulo, descripcion):
        consultas.append(titulo)
        if "droga" in (titulo or "").lower():
            return {"veredicto": "rechazar", "motivo": "ilegal", "confianza": 0.95}
        if "raro" in (titulo or "").lower():
            return {"veredicto": "dudoso", "motivo": "no se entiende", "confianza": 0.4}
        return {"veredicto": "aprobar", "motivo": "producto normal", "confianza": 0.9}

    monkeypatch.setattr(revision_ia, "moderar_publicacion", _moderar)
    return consultas


# ══════════════════════════════════════════════════════ qué revisa

def test_revisa_solo_lo_pendiente_sin_veredicto(repo, ia):
    c = repo.seed_comercio(slug="x", nombre="X")
    p1 = _pub(repo, c, "zapatillas")
    _pub(repo, c, "ya aprobada", estado="aprobado")
    _pub(repo, c, "ya revisada", ia_veredicto="aprobar")

    r = revision_ia.revisar_pendientes(repo)
    assert r["revisadas"] == 1
    assert ia == ["zapatillas"]
    assert repo.get_publicacion(p1["id"])["ia_veredicto"] == "aprobar"


def test_el_veredicto_queda_en_la_fila(repo, ia):
    """Antes vivía en el navegador y se iba al recargar. Ahora es un dato."""
    c = repo.seed_comercio(slug="x", nombre="X")
    p = _pub(repo, c, "algo raro")
    revision_ia.revisar_pendientes(repo)
    fila = repo.get_publicacion(p["id"])
    assert fila["ia_veredicto"] == "dudoso"
    assert fila["ia_motivo"] == "no se entiende"
    assert fila["ia_confianza"] == 0.4
    assert fila["ia_revisado_at"]


def test_una_segunda_vuelta_no_vuelve_a_preguntar(repo, ia):
    """Cada consulta a Gemini cuesta. Repetirla sobre lo ya revisado es pagar
    dos veces por la misma opinión."""
    c = repo.seed_comercio(slug="x", nombre="X")
    _pub(repo, c, "zapatillas")
    revision_ia.revisar_pendientes(repo)
    revision_ia.revisar_pendientes(repo)
    assert len(ia) == 1


def test_un_fallo_en_una_no_corta_las_demas(repo, monkeypatch):
    """Una excepción acá dejaría la cola sin revisar hasta el próximo reinicio."""
    llamadas = []

    def _moderar(titulo, descripcion):
        llamadas.append(titulo)
        if titulo == "explota":
            raise RuntimeError("Gemini caído")
        return {"veredicto": "aprobar", "motivo": "", "confianza": 0.9}
    monkeypatch.setattr(revision_ia, "moderar_publicacion", _moderar)

    c = repo.seed_comercio(slug="x", nombre="X")
    _pub(repo, c, "explota")
    _pub(repo, c, "sana")
    r = revision_ia.revisar_pendientes(repo)
    assert r == {"revisadas": 1, "auto_aprobadas": 0, "fallidas": 1}
    assert len(llamadas) == 2


# ══════════════════════════════════════════════ no aprueba sola, salvo…

def test_por_defecto_nunca_aprueba_sola(repo, ia):
    """Aprobar manda a la cola de difusión —al canal y a las redes de la
    marca—. Una foto que ninguna persona miró en el muro de URUKU no se
    deshace con un "rechazar"."""
    assert settings.ia_auto_aprobar_desde == 0
    c = repo.seed_comercio(slug="x", nombre="X")
    p = _pub(repo, c, "zapatillas")           # la IA dice aprobar con 0.9
    r = revision_ia.revisar_pendientes(repo)
    assert r["auto_aprobadas"] == 0
    assert repo.get_publicacion(p["id"])["estado"] == "pendiente"
    assert repo.difusion == []


def test_con_la_perilla_encendida_aprueba_y_encola(repo, ia, monkeypatch):
    monkeypatch.setattr(settings, "ia_auto_aprobar_desde", 0.8)
    c = repo.seed_comercio(slug="x", nombre="X")
    p = _pub(repo, c, "zapatillas")           # aprobar, 0.9
    r = revision_ia.revisar_pendientes(repo)
    assert r["auto_aprobadas"] == 1
    fila = repo.get_publicacion(p["id"])
    assert fila["estado"] == "aprobado"
    assert fila["moderado_por"] == "ia-auto"
    assert len(repo.difusion) == 3            # a las tres redes


def test_con_la_perilla_encendida_lo_dudoso_sigue_esperando(repo, ia, monkeypatch):
    monkeypatch.setattr(settings, "ia_auto_aprobar_desde", 0.8)
    c = repo.seed_comercio(slug="x", nombre="X")
    p = _pub(repo, c, "algo raro")            # dudoso, 0.4
    revision_ia.revisar_pendientes(repo)
    assert repo.get_publicacion(p["id"])["estado"] == "pendiente"


def test_la_confianza_justa_por_debajo_no_alcanza(repo, monkeypatch):
    monkeypatch.setattr(settings, "ia_auto_aprobar_desde", 0.8)
    monkeypatch.setattr(revision_ia, "moderar_publicacion",
                        lambda t, d: {"veredicto": "aprobar", "motivo": "", "confianza": 0.79})
    c = repo.seed_comercio(slug="x", nombre="X")
    p = _pub(repo, c, "casi")
    revision_ia.revisar_pendientes(repo)
    assert repo.get_publicacion(p["id"])["estado"] == "pendiente"


# ══════════════════════════════════════════════════════ el orden

def test_la_cola_llega_ordenada_al_moderador(client, repo, admin_token, ia):
    """Rechazable y dudoso arriba —piden decisión—, sin veredicto en el medio,
    lo aprobable abajo para despachar en tanda."""
    c = repo.seed_comercio(slug="x", nombre="X")
    _pub(repo, c, "zapatillas")               # → aprobar
    _pub(repo, c, "algo raro")                # → dudoso
    _pub(repo, c, "vendo droga")              # → rechazar
    revision_ia.revisar_pendientes(repo)
    _pub(repo, c, "sin revisar todavía")      # queda None

    r = client.get("/moderacion/publicaciones?estado=pendiente", headers=_h(admin_token))
    assert r.status_code == 200, r.text
    orden = [p["titulo"] for p in r.json()["items"]]
    assert orden == ["vendo droga", "algo raro", "sin revisar todavía", "zapatillas"]


def test_dentro_del_mismo_grupo_lo_nuevo_primero():
    items = [
        {"ia_veredicto": "dudoso", "created_at": "2026-09-01T00:00:00+00:00", "t": "vieja"},
        {"ia_veredicto": "dudoso", "created_at": "2026-09-10T00:00:00+00:00", "t": "nueva"},
    ]
    assert [p["t"] for p in revision_ia.ordenar_para_moderar(items)] == ["nueva", "vieja"]


def test_una_fecha_rota_no_rompe_el_orden():
    """Un `created_at` raro en una fila no puede tirar abajo la cola entera."""
    items = [{"ia_veredicto": None, "created_at": "no-es-fecha"},
             {"ia_veredicto": "rechazar", "created_at": None}]
    assert revision_ia.ordenar_para_moderar(items)[0]["ia_veredicto"] == "rechazar"
