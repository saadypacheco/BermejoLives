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
