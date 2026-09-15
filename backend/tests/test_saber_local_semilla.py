"""La semilla de saber local (0107) se encuentra con las preguntas que la gente hace.

Se lee el SQL, se cargan las entradas en el repo falso y se pregunta como
preguntaría alguien que llega a Bermejo. Si una entrada no se encuentra con
la pregunta obvia, sobra la entrada o faltan etiquetas — y mejor saberlo acá
que cuando alguien pregunte en la frontera.
"""
import re
from pathlib import Path

import pytest

from app.core.config import settings
from app.services import asistente

SQL = Path(__file__).resolve().parents[2] / "selfhost" / "postgres-init" / "0107_saber_local_compras.sql"


def _entradas() -> list[dict]:
    texto = SQL.read_text(encoding="utf-8")
    patron = re.compile(r"\(\s*'([^']+)',\s*'([^']+)',\s*array\[([^\]]+)\]\)", re.S)
    out = []
    for m in patron.finditer(texto):
        etiquetas = [e.strip().strip("'") for e in m.group(3).split(",")]
        out.append({"pregunta": m.group(1), "respuesta": m.group(2), "etiquetas": etiquetas})
    return out


@pytest.fixture
def repo_con_semilla(repo, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    for e in _entradas():
        repo.upsert_saber_local(e)
    return repo


def test_la_semilla_tiene_entradas_y_ninguna_comilla_sin_escapar():
    entradas = _entradas()
    assert len(entradas) >= 12
    for e in entradas:
        assert len(e["etiquetas"]) >= 3, e["pregunta"]
    # Un apóstrofo suelto dentro de un literal rompe el INSERT entero.
    cuerpo = SQL.read_text(encoding="utf-8").split("from (values", 1)[1]
    assert "''" not in cuerpo


@pytest.mark.parametrize("pregunta, esperado", [
    ("¿cómo cruzo a Bermejo desde Aguas Blancas?", "cruzo"),
    ("qué documentos necesito para pasar", "documentos"),
    ("a qué hora abre el comercio", "hora abre"),
    ("qué conviene comprar acá?", "conviene comprar"),
    ("se compra por docena?", "docena"),
    ("con qué moneda pago", "moneda pago"),
    ("puedo pagar con mercado pago?", "moneda pago"),
    ("cuánto puedo llevar de vuelta a argentina sin pagar aduana", "llevar de vuelta"),
    ("cómo llego desde Tarija en bus", "desde Tarija"),
    ("hay tours desde Salta?", "Salta u Orán"),
    ("qué hay para hacer aparte de comprar, algún balneario?", "aparte de comprar"),
    ("cuándo es la fiesta de san santiago", "fiesta de Bermejo"),
    ("es seguro venir? algún consejo", "seguro"),
])
def test_cada_pregunta_obvia_encuentra_su_entrada(repo_con_semilla, pregunta, esperado):
    r = asistente.responder(repo_con_semilla, pregunta)
    assert r.intent == "saber_local", (pregunta, r.intent, r.texto[:80])
    assert esperado.lower() in r.fuentes[0]["nombre"].lower(), (pregunta, r.fuentes[0]["nombre"])


def test_donde_cambio_sigue_siendo_el_nivel_0_con_el_mapa(repo_con_semilla):
    """La entrada de cambio existe para el modelo, pero la pregunta directa
    la contesta el Nivel 0 con las casas de cambio y el mapa."""
    r = asistente.responder(repo_con_semilla, "¿dónde cambio dólares?")
    assert r.intent == "casas_de_cambio"
