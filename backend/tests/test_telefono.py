"""Validación del WhatsApp — se aplica cuando el comercio empieza a pagar."""
import pytest

from app.core.telefono import normalizar_whatsapp, validar_whatsapp


@pytest.mark.parametrize("entrada,esperado", [
    ("70123456", "59170123456"),        # local, se le antepone 591
    ("60123456", "59160123456"),
    ("59170123456", "59170123456"),     # ya normalizado
    ("+591 70123456", "59170123456"),   # con + y espacios
    ("591-701-234-56", "59170123456"),  # con guiones
    ("0059170123456", "59170123456"),   # prefijo internacional 00
    ("", None),
    (None, None),
    ("sin numero", None),
])
def test_normalizar(entrada, esperado):
    assert normalizar_whatsapp(entrada) == esperado


@pytest.mark.parametrize("valido", [
    "70123456", "59170123456", "+591 70123456", "59160123456",
    "5491133821989",  # otro país: no se conocen las reglas, pasa si es plausible
])
def test_validos(valido):
    assert validar_whatsapp(valido) is None


def test_vacio_avisa_que_falta():
    assert "no tiene WhatsApp" in validar_whatsapp(None)
    assert "no tiene WhatsApp" in validar_whatsapp("   ")


def test_celular_boliviano_corto():
    # 7 dígitos: el link de wa.me se abriría contra un número inexistente.
    error = validar_whatsapp("7012345")
    assert error is not None and "dígitos" in error


def test_fijo_boliviano_no_sirve_para_whatsapp():
    # Los fijos arrancan con 4 (Cochabamba/Tarija), no con 6 o 7.
    error = validar_whatsapp("59146123456")
    assert error is not None


def test_texto_basura():
    assert validar_whatsapp("no tengo") is not None


# ---- Argentina: Bermejo es frontera y hay comercios con número argentino ----
@pytest.mark.parametrize("entrada,esperado", [
    ("5493514123456", "5493514123456"),   # ya completo
    ("543514123456",  "5493514123456"),   # le falta el 9 de móvil: se agrega
    ("+54 9 351 412-3456", "5493514123456"),
    ("0054 9 3514123456",  "5493514123456"),
])
def test_normalizar_argentina(entrada, esperado):
    assert normalizar_whatsapp(entrada) == esperado


def test_argentino_valido():
    assert validar_whatsapp("5493514123456") is None
    assert validar_whatsapp("543514123456") is None   # se completa el 9 solo


def test_argentino_incompleto():
    error = validar_whatsapp("54935141")
    assert error is not None and "argentino" in error


def test_el_9_es_lo_que_hace_que_el_link_abra():
    """Sin el 9, wa.me no abre chat con un celular argentino. Es el error más
    fácil de cometer al cargar y el más difícil de notar."""
    assert normalizar_whatsapp("543514123456").startswith("549")
