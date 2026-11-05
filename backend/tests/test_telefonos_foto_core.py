"""La normalización pura de teléfonos leídos en fotos (core/telefonos_foto.py, docs/telefonos-en-fotos.md).

Lo que se prueba es la PRECISIÓN: que de un texto de OCR salgan los teléfonos y sólo los teléfonos. Cada falso
positivo es una propuesta que una persona tiene que descartar a mano, y son miles de portadas."""
import pytest

from app.core.config import settings
from app.core.telefonos_foto import (Telefono, clave_de_comparacion, es_de_uruku, extraer, mismo_numero,
                                     normalizar, numero_visible, numeros_de_uruku, whatsapp_de)


def numeros(texto):
    return [t.numero for t in extraer(texto)]


# ═════════════════════════════════════════════════════════════ Bolivia

@pytest.mark.parametrize("escrito", [
    "70123456", "7012 3456", "7012-3456", "70 123 456", "70.123.456", "70 12 34 56",
    "+591 70123456", "+591 7012 3456", "591 70123456", "591-7012-3456", "+591-7012-3456", "(591) 70123456",
    "00591 70123456", "+591 70 123 456",
])
def test_celular_boliviano_con_y_sin_prefijo(escrito):
    assert numeros(escrito) == ["+59170123456"]
    assert extraer(escrito)[0].tipo == "celular"


@pytest.mark.parametrize("primero", ["6", "7"])
def test_celulares_empiezan_en_6_o_7(primero):
    assert normalizar(f"{primero}1234567") == Telefono(f"+591{primero}1234567", "celular", f"{primero}1234567")


@pytest.mark.parametrize("escrito", ["80123456", "90123456", "50123456", "10234567", "01234567"])
def test_un_ocho_digitos_que_no_empieza_como_celular_ni_fijo_no_es_telefono(escrito):
    assert numeros(escrito) == []


@pytest.mark.parametrize("escrito, esperado", [
    ("(4) 6612345", "+59146612345"),
    ("4 6612345", "+59146612345"),
    ("4-661-2345", "+59146612345"),
    ("46612345", "+59146612345"),
    ("+591 4 6612345", "+59146612345"),
    ("(2) 2123456", "+59122123456"),
    ("3 3456789", "+59133456789"),
])
def test_fijo_con_codigo_de_area_2_3_o_4(escrito, esperado):
    tel = extraer(escrito)
    assert [t.numero for t in tel] == [esperado]
    assert tel[0].tipo == "fijo"


def test_siete_digitos_sin_codigo_de_area_se_descartan():
    """Sin código de área no se sabe de qué ciudad es: no se inventa."""
    assert numeros("6612345") == []
    assert numeros("Tel. 6612345") == []


def test_menos_de_siete_digitos_se_descartan():
    assert numeros("123456 12345 4321 987") == []


def test_dos_numeros_en_una_linea_pegados_se_separan():
    assert numeros("70123456 71234567") == ["+59170123456", "+59171234567"]
    assert numeros("Tel 4 6612345 / Cel 70123456 71234567") == ["+59146612345", "+59170123456", "+59171234567"]
    assert numeros("70123456,71234567") == ["+59170123456", "+59171234567"]
    assert numeros("591 70123456 71234567") == ["+59170123456", "+59171234567"]


def test_el_mismo_numero_escrito_distinto_sale_una_vez():
    assert numeros("70123456\n+591 7012 3456\n591-70123456") == ["+59170123456"]


def test_el_texto_leido_es_lo_que_se_vio_y_cabe_en_60():
    t = extraer("Cel: +591 7012 3456")[0]
    assert t.texto_leido == "+591 7012 3456"
    assert len(extraer("Cel " + "7012 3456 " * 40)[0].texto_leido) <= 60


@pytest.mark.parametrize("texto", ["Cel: 70123456", "Cel.70123456", "WhatsApp70123456", "Tel/Cel 70123456",
                                   "Llamá al 70123456!", "contacto: 70123456."])
def test_con_palabras_alrededor(texto):
    assert numeros(texto) == ["+59170123456"]


# ═════════════════════════════════════════════════════════════ Argentina (frontera)

@pytest.mark.parametrize("escrito, esperado, tipo", [
    ("+54 9 3878 51-2345", "+5493878512345", "celular"),     # el 9 marca el celular
    ("+54 9 387 412 3456", "+5493874123456", "celular"),
    ("549 387 4123456", "+5493874123456", "celular"),
    ("387 15 4123456", "+5493874123456", "celular"),         # el «15» marca el celular: se normaliza al 9
    ("0387 15 4123456", "+5493874123456", "celular"),
    ("(0387) 15-412-3456", "+5493874123456", "celular"),
    ("3878 15 512345", "+5493878512345", "celular"),
    # Sin 9 ni «15»: el dueño decidió tratarlos como CELULAR (salen con el 9, como se escribe en WhatsApp).
    ("54 387 4123456", "+5493874123456", "celular"),
    ("+54 3878 42-1234", "+5493878421234", "celular"),
    ("3878 421234", "+5493878421234", "celular"),
    ("387 4123456", "+5493874123456", "celular"),
    ("388 4123456", "+5493884123456", "celular"),            # Jujuy
    ("3885 421234", "+5493885421234", "celular"),            # La Quiaca
    ("3875 421234", "+5493875421234", "celular"),            # Salvador Mazza
])
def test_numeros_argentinos_de_la_region(escrito, esperado, tipo):
    tel = extraer(escrito)
    assert [(t.numero, t.tipo) for t in tel] == [(esperado, tipo)]


def test_diez_digitos_con_un_area_que_no_es_de_la_region_no_entran():
    assert numeros("1155551234") == []          # Buenos Aires: no es de frontera
    assert numeros("11 5555 1234") == []
    assert numeros("+54 11 5555 1234") == []


def test_un_argentino_sin_el_9_y_con_el_9_son_el_mismo_numero_para_comparar():
    assert mismo_numero("+543874123456", "5493874123456")
    assert mismo_numero("+5493874123456", "54 387 4123456")


# ═════════════════════════════════════════════════════════════ lo que NO es un teléfono

@pytest.mark.parametrize("texto", [
    "Promo del 20/11/2026 al 25/11/2026", "05-11-2026", "5.11.2026", "2026-11-05", "20261105", "05112026",
    "Vence 31-12-26", "Desde 01/12/2026 hasta 24/12/2026",
])
def test_fechas(texto):
    assert numeros(texto) == []


@pytest.mark.parametrize("texto", [
    "Horario 8:00 a 12:00 y 14:30 a 19:00", "20:00 22:00", "20 00 22 00", "2000 2200", "18 30 20 00",
    "Lunes a sábado 08.00 - 20.00", "8 a 12 y 14 a 20", "24/7", "abierto 24 hs 70123456 hs",
])
def test_horarios(texto):
    assert numeros(texto) == []


@pytest.mark.parametrize("texto", [
    "Bs 70123456", "Bs. 70123456", "$ 70123456", "70123456 Bs", "70123456 $", "70123456 bolivianos",
    "precio 1.250,50", "Bs 1.250.000,00", "12.500", "1.234.567", "7012345.50", "USD 70123456", "70123456 pesos",
])
def test_precios(texto):
    assert numeros(texto) == []


@pytest.mark.parametrize("texto", ["2024", "2025 2026", "2024 2025", "Desde 1998", "Año 2020 2021"])
def test_anios(texto):
    assert numeros(texto) == []


@pytest.mark.parametrize("texto", [
    "NIT 70123456", "NIT: 70123456", "N.I.T. 70123456", "CI 70123456", "C.I. 70123456", "RUC 70123456",
    "CUIT 3874123456", "DNI 70123456",
])
def test_nit_y_documentos(texto):
    assert numeros(texto) == []


@pytest.mark.parametrize("texto", ["Cód. 70123456", "Cod 70123456", "Código 70123456", "Ref 70123456",
                                   "SKU 70123456", "Art. 70123456", "Factura 70123456", "Lote 70123456"])
def test_codigos_de_producto_y_referencias(texto):
    assert numeros(texto) == []


def test_el_nit_no_se_lleva_puesto_al_telefono_de_al_lado():
    assert numeros("NIT: 70123456 Cel 71234567") == ["+59171234567"]
    assert numeros("Cel 71234567 NIT 70123456") == ["+59171234567"]


@pytest.mark.parametrize("texto", ["11111111", "22222222", "77777777", "70707070", "12345678", "76543210",
                                   "67890123", "70000000", "+591 77777777", "387 4444444"])
def test_numeros_repetidos_o_escalonados(texto):
    assert numeros(texto) == []


def test_numeros_muy_largos_o_basura_de_ocr():
    assert numeros("7790123456789") == []                       # un código de barras
    assert numeros("123456789012345678") == []
    assert numeros("") == [] and numeros(None) == []
    assert numeros("sin números acá") == []
    assert numeros("+ - . ( )") == []


def test_la_direccion_y_la_altura_de_la_calle_no_son_telefonos():
    assert numeros("Av. 6 de Agosto 123 esq. Calle 15 de Abril") == []
    assert numeros("Local 4 Galería Central") == []


# ═════════════════════════════════════════════════════════════ los números de URUKU

@pytest.mark.parametrize("escrito", [
    "67671888", "67 671 888", "+591 67671888", "591 6767 1888",          # el público
    "67677803", "+591 67677803",                                          # el explorador
    "75314737",                                                           # el Anfitrión de los volantes viejos
    "67991916", "64610187",                                               # la API de Meta y el Registrador
])
def test_los_numeros_de_uruku_se_descartan(escrito):
    assert numeros(escrito) == []


def test_un_numero_de_uruku_no_se_lleva_al_del_comercio():
    assert numeros("URUKU 67671888 Cel 70123456") == ["+59170123456"]
    assert numeros("67671888 70123456") == ["+59170123456"]


def test_los_numeros_de_la_config_tambien_se_descartan(monkeypatch):
    monkeypatch.setattr(settings, "wa_numeros_propios", "59170000099, 59170000098")
    monkeypatch.setattr(settings, "wa_numeros_grupo", "59171111112")
    monkeypatch.setattr(settings, "wa_numeros_explorador", "59172222223")
    monkeypatch.setattr(settings, "wa_contacto_explorador", "59173333334")
    monkeypatch.setattr(settings, "bot_whatsapp_numero", "59174444445")
    monkeypatch.setattr(settings, "wa_contacto_publico", "59175555556")
    for propio in ("70000099", "70000098", "71111112", "72222223", "73333334", "74444445", "75555556"):
        assert numeros(propio) == [], propio
        assert es_de_uruku(propio)
    assert numeros("70123456") == ["+59170123456"]
    assert {"59170000099", "59175555556"} <= numeros_de_uruku()
    assert not es_de_uruku("70123456")


def test_una_config_con_basura_no_rompe(monkeypatch):
    monkeypatch.setattr(settings, "wa_numeros_propios", "591XXXXXXXX, nada, ")
    assert numeros("70123456") == ["+59170123456"]


# ═════════════════════════════════════════════════════════════ normalizar / presentación

def test_normalizar_un_solo_numero():
    assert normalizar("+591 7012-3456").numero == "+59170123456"
    assert normalizar("  ") is None and normalizar(None) is None
    assert normalizar("hola") is None
    assert normalizar("+1 415 555 2671") is None            # Estados Unidos: no es de la región


def test_clave_de_comparacion_une_las_formas_del_mismo_numero():
    assert clave_de_comparacion("70123456") == clave_de_comparacion("+591 7012 3456") == "59170123456"
    assert clave_de_comparacion("") == "" and clave_de_comparacion(None) == ""
    assert mismo_numero("70123456", "59170123456")
    assert not mismo_numero("70123456", "70123457")
    assert not mismo_numero("", "")


def test_whatsapp_de_es_el_formato_de_la_ficha():
    assert whatsapp_de("+59170123456") == "59170123456"
    assert whatsapp_de("+5493874123456") == "5493874123456"


@pytest.mark.parametrize("numero, visible", [
    ("+59170123456", "+591 7012 3456"),
    ("+59146612345", "+591 4 661 2345"),
    ("+5493878512345", "+54 9 3878 51-2345"),
    ("+5493874123456", "+54 9 387 412-3456"),
    ("+543874123456", "+54 387 412-3456"),
])
def test_numero_visible(numero, visible):
    assert numero_visible(numero) == visible
