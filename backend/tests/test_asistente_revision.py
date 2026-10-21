"""Dax: once respuestas equivocadas detectadas corriendo `responder(repo, pregunta)` contra
la base de demo (sin ciudad = Bermejo con guía) con el saber local de
`backend/data/saber_local/bermejo.json` y las migraciones 0106/0107/0110 cargados.

Cada test reproduce UN caso con las filas mínimas (copiadas del JSON y de las migraciones,
no inventadas): el nombre del test dice el error que tenía. Al final, una prueba con todo
el saber junto, porque varios de los errores eran de una entrada contra otra.
"""
import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.config import settings
from app.services import asistente, turnos_farmacia

RAIZ = Path(__file__).resolve().parents[2]
MARTES_11 = datetime(2026, 10, 20, 11, 0)        # martes 11:00 hora de Bolivia
MIERCOLES_11 = datetime(2026, 10, 21, 11, 0)     # miércoles 11:00


@pytest.fixture(autouse=True)
def sin_modelo(monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    monkeypatch.setattr(settings, "wa_contacto_publico", "59167671888")


# ------------------------------------------------------------------ las filas de saber local

def _json() -> list[dict]:
    datos = json.loads((RAIZ / "backend" / "data" / "saber_local" / "bermejo.json").read_text(encoding="utf-8"))
    return [{"pregunta": d["pregunta"], "respuesta": d["respuesta"], "etiquetas": d["palabras"],
             "verificado": d.get("verificado", False)} for d in datos]


def _sql(archivo: str) -> list[dict]:
    texto = (RAIZ / "supabase" / "migrations" / archivo).read_text(encoding="utf-8")
    patron = re.compile(r"\(\s*'((?:[^']|'')*)',\s*'((?:[^']|'')*)',\s*array\[([^\]]*)\]", re.S)
    return [{"pregunta": m.group(1).replace("''", "'"), "respuesta": m.group(2).replace("''", "'"),
             "etiquetas": [e.strip().strip("'") for e in m.group(3).split(",")]} for m in patron.finditer(texto)]


def _todas() -> dict[str, dict]:
    """Todas las entradas por pregunta. Si una está en una migración y en el JSON (la de
    emergencias), vale la de la migración: es la que ya está cargada en las bases."""
    filas: dict[str, dict] = {f["pregunta"]: f for f in _json()}
    for archivo in ("0106_uruku_ayuda.sql", "0107_saber_local_compras.sql", "0110_guia_del_que_llega.sql"):
        filas.update({f["pregunta"]: f for f in _sql(archivo)})
    return filas


def _saber(repo, *preguntas: str) -> None:
    """Carga SÓLO esas entradas (por el principio de la pregunta). Falla fuerte si ya no existen."""
    todas = _todas()
    for inicio in preguntas:
        fila = next((f for p, f in todas.items() if p.startswith(inicio)), None)
        assert fila, f"ya no hay una entrada que empiece con «{inicio}»"
        repo.upsert_saber_local({"pregunta": fila["pregunta"], "respuesta": fila["respuesta"], "etiquetas": fila["etiquetas"]})


def _comercio(repo, cid, nombre, **extra):
    c = {"id": cid, "slug": cid, "nombre": nombre, "activo": True, "subcategoria": "", "horario": "Lun-Sáb 8:00-12:00 y 14:30-20:00",
         "direccion": "Calle Comercio 1", **extra}
    repo.comercios[cid] = c
    return c


def _preguntar(repo, texto, ahora=MARTES_11, **kw):
    return asistente.responder(repo, texto, ahora=ahora, **kw)


# ------------------------------------------------------------------ 1. «puente» no es un comercio

def test_el_puente_es_el_puente_no_la_casa_de_cambio(repo):
    _comercio(repo, "com-cambio", "Casa de Cambio El Puente", subcategoria="cambio")
    _saber(repo, "¿A qué hora abre el puente?")
    r = _preguntar(repo, "¿a qué hora abre el puente?")
    assert r.intent == "saber_local" and "24 horas" in r.texto
    assert "Casa de Cambio" not in r.texto


def test_el_puente_sin_la_entrada_exacta_igual_va_a_la_frontera(repo):
    """En la base de demo la entrada «¿A qué hora abre el puente?» no estaba (no verificada): el
    puente atiende 24 h según la de «¿Cómo cruzo de Aguas Blancas a Bermejo?», y la entrada
    genérica de «¿A qué hora abre el comercio?» no puede ganarle."""
    _comercio(repo, "com-cambio", "Casa de Cambio El Puente", subcategoria="cambio")
    _saber(repo, "¿Cómo cruzo de Aguas Blancas a Bermejo?", "¿A qué hora abre el comercio en Bermejo?")
    r = _preguntar(repo, "¿a qué hora abre el puente?")
    assert r.intent == "saber_local" and "24 horas" in r.texto and "Casa de Cambio" not in r.texto


def test_sin_ninguna_entrada_el_horario_del_puente_es_el_estado_de_hoy(repo):
    _comercio(repo, "com-cambio", "Casa de Cambio El Puente", subcategoria="cambio")
    r = _preguntar(repo, "¿hasta qué hora funciona el puente?")
    assert r.intent == "frontera_hoy" and "Casa de Cambio" not in r.texto


@pytest.mark.parametrize("pregunta", ["¿a qué hora atiende la aduana?", "¿dónde queda el puente?", "¿a qué hora abren las chalanas?"])
def test_ninguna_palabra_de_la_frontera_es_un_comercio(repo, pregunta):
    _comercio(repo, "com-ad", "Despachante Aduana Sur")
    _comercio(repo, "com-ch", "Chalanas Tour")
    _comercio(repo, "com-cambio", "Casa de Cambio El Puente", subcategoria="cambio")
    r = _preguntar(repo, pregunta)
    assert r.intent not in ("horario", "direccion", "desambiguar")
    assert all(n not in r.texto for n in ("Despachante", "Chalanas Tour", "Casa de Cambio"))


def test_con_el_nombre_completo_sigue_siendo_el_comercio(repo):
    _comercio(repo, "com-ferr", "Ferretería El Puente")
    _comercio(repo, "com-cambio", "Casa de Cambio El Puente", subcategoria="cambio")
    r = _preguntar(repo, "¿a qué hora abre Ferretería El Puente?")
    assert r.intent == "horario" and r.texto.startswith("Ferretería El Puente:")


def test_un_comercio_que_se_llama_exactamente_el_puente_se_encuentra(repo):
    _comercio(repo, "com-p", "El Puente")
    assert _preguntar(repo, "¿a qué hora abre El Puente?").intent == "horario"


# ------------------------------------------------------------------ 2. documentos antes que productos

def test_que_documentos_necesito_no_busca_el_producto_cruzar(repo):
    _comercio(repo, "com-tours", "Cruzar Viajes y Tours", subcategoria="turismo")
    _saber(repo, "¿Qué documentos necesito para cruzar?")
    r = _preguntar(repo, "¿qué documentos necesito para cruzar?")
    assert r.intent == "saber_local" and "pasaporte" in r.texto
    assert "Cruzar Viajes" not in r.texto


@pytest.mark.parametrize("pregunta", ["necesito documentos para cruzar", "¿qué necesito para cruzar con mi auto?",
                                      "¿qué necesito para pasar la aduana?"])
def test_necesito_para_hacer_algo_no_es_un_producto(repo, pregunta):
    _comercio(repo, "com-tours", "Cruzar Viajes y Tours", subcategoria="turismo", prod_obs_human="pasar aduana")
    _saber(repo, "¿Qué documentos necesito para cruzar?", "¿Cómo cruzo a Argentina?")
    r = _preguntar(repo, pregunta)
    assert r.intent != "buscar" and "Cruzar Viajes" not in r.texto


def test_necesito_un_producto_sigue_siendo_una_busqueda(repo):
    _comercio(repo, "com-zap", "Zapatería Luz", subcategoria="calzado", prod_obs_human="zapatillas")
    assert _preguntar(repo, "necesito zapatillas").intent == "buscar"


# ------------------------------------------------------------------ 3. menores

def test_un_menor_con_la_mama_va_a_documentos_no_a_la_franquicia(repo):
    _saber(repo, "¿Qué documentos necesito para cruzar?", "¿Cuánto puedo llevar de vuelta a Argentina sin pagar?")
    r = _preguntar(repo, "¿puede cruzar un menor solo con la mamá?")
    assert r.intent == "saber_local"
    assert r.fuentes[0]["nombre"].startswith("¿Qué documentos necesito para cruzar?")
    assert "autorización" in r.texto


def test_el_plural_y_el_singular_son_la_misma_palabra(repo):
    repo.upsert_saber_local({"pregunta": "¿Qué papeles piden?", "respuesta": "DNI.", "etiquetas": ["documento", "menor", "hijo"]})
    r = _preguntar(repo, "¿llevo documentos de mis menores?")
    assert r.intent == "saber_local"


# ------------------------------------------------------------------ 4. feriados ≠ ferias

def test_que_feriados_hay_no_son_los_mercados(repo):
    repo.lugares["l1"] = {"id": "l1", "nombre": "Mercado Central", "tipo": "mercado", "activo": True}
    _saber(repo, "¿Qué feriados de Bolivia cierran los comercios?")
    r = _preguntar(repo, "¿qué feriados hay?")
    assert r.intent == "saber_local" and "feriado" in r.texto.lower()
    assert "Mercado Central" not in r.texto


@pytest.mark.parametrize("pregunta", ["¿dónde está el mercado?", "¿qué días hay feria?", "¿qué galerías hay?"])
def test_mercados_y_ferias_siguen_contestando_los_lugares(repo, pregunta):
    repo.lugares["l1"] = {"id": "l1", "nombre": "Mercado Central", "tipo": "mercado", "activo": True}
    assert _preguntar(repo, pregunta).intent == "lugares"


# ------------------------------------------------------------------ 5. farmacia de turno

def _farmacia(repo, cid, nombre, **extra):
    return _comercio(repo, cid, nombre, subcategoria="farmacia", rubro_slug="farmacia", telefono="72920000", **extra)


def _turno(repo, cid, dia: str):
    from datetime import date
    inicio, fin = turnos_farmacia.ventana(date.fromisoformat(dia))
    repo.upsert_turnos_farmacia([{"comercio_id": cid, "fecha": dia, "inicio": inicio, "fin": fin, "fuente": "test"}])


def test_la_farmacia_de_turno_es_la_de_turno_no_todas(repo):
    _farmacia(repo, "f1", "Farmacia Ángeles", direccion="Calle Tarija 10")
    _farmacia(repo, "f2", "Farmacia Central")
    _farmacia(repo, "f3", "Farmacia Santa Rosa")
    _turno(repo, "f1", "2026-10-21")                 # 21/10 08:00 → 22/10 08:00
    _turno(repo, "f2", "2026-10-21")
    _turno(repo, "f3", "2026-10-22")                 # mañana: todavía no
    r = _preguntar(repo, "¿qué farmacia está de turno?", ahora=MIERCOLES_11)
    assert r.intent == "farmacia_turno" and not r.sin_respuesta
    assert "Farmacia Ángeles" in r.texto and "Farmacia Central" in r.texto and "Santa Rosa" not in r.texto
    assert "hasta mañana 08:00" in r.texto
    assert "https://uruku.bo/farmacias-de-turno" in r.texto
    assert "Calle Tarija 10" in r.texto and "72920000" in r.texto


def test_de_madrugada_el_turno_es_el_de_ayer_y_termina_hoy(repo):
    _farmacia(repo, "f1", "Farmacia Ángeles")
    _farmacia(repo, "f2", "Farmacia Central")
    _turno(repo, "f1", "2026-10-20")
    _turno(repo, "f2", "2026-10-21")
    r = _preguntar(repo, "farmacia de turno", ahora=datetime(2026, 10, 21, 3, 0))
    assert "Farmacia Ángeles" in r.texto and "Farmacia Central" not in r.texto
    assert "hasta hoy 08:00" in r.texto


def test_la_hora_con_zona_tambien_cuenta_como_hora_de_bolivia(repo):
    _farmacia(repo, "f1", "Farmacia Ángeles")
    _turno(repo, "f1", "2026-10-21")
    # 12:00 UTC = 08:00 en La Paz: justo cuando empieza el turno del 21/10.
    r = _preguntar(repo, "¿hay alguna farmacia de guardia?", ahora=datetime(2026, 10, 21, 12, 0, tzinfo=timezone.utc))
    assert r.intent == "farmacia_turno" and "Farmacia Ángeles" in r.texto and "hasta mañana 08:00" in r.texto
    # Un minuto antes todavía es el turno de ayer, que no está cargado.
    antes = _preguntar(repo, "¿hay alguna farmacia de guardia?", ahora=datetime(2026, 10, 21, 11, 59, tzinfo=timezone.utc))
    assert "no tengo cargado" in antes.texto.lower()


def test_un_turno_dado_de_baja_o_de_otra_ciudad_no_sale(repo):
    _farmacia(repo, "f1", "Farmacia Ángeles")
    _farmacia(repo, "f2", "Farmacia Villazón", ciudad_slug="villazon")
    _turno(repo, "f1", "2026-10-21")
    _turno(repo, "f2", "2026-10-21")
    r = _preguntar(repo, "¿qué farmacia está de turno?", ahora=MIERCOLES_11)
    assert "Farmacia Villazón" not in r.texto and "Farmacia Ángeles" in r.texto
    for t in repo.turnos_farmacia.values():
        t["activo"] = False
    assert "Farmacia Ángeles" not in _preguntar(repo, "¿qué farmacia está de turno?", ahora=MIERCOLES_11).texto.split("cargado")[0]


def test_sin_turnos_cargados_se_dice_y_se_muestra_lo_de_hoy(repo):
    _farmacia(repo, "f1", "Farmacia Ángeles")
    r = _preguntar(repo, "¿qué farmacia está de turno?", ahora=MIERCOLES_11)
    assert r.intent == "farmacia_turno"
    assert "no tengo cargado el rol de turnos" in r.texto.lower() and "Farmacia Ángeles" in r.texto
    assert "https://uruku.bo/farmacias-de-turno" in r.texto


def test_sin_turnos_ni_farmacias_manda_a_la_pagina(repo):
    r = _preguntar(repo, "¿qué farmacia está de turno?", ahora=MIERCOLES_11)
    assert r.intent == "farmacia_turno" and r.sin_respuesta
    assert "https://uruku.bo/farmacias-de-turno" in r.texto


def test_la_pregunta_por_farmacias_a_secas_sigue_listando(repo):
    _farmacia(repo, "f1", "Farmacia Ángeles")
    _turno(repo, "f1", "2026-10-21")
    r = _preguntar(repo, "¿dónde hay una farmacia?", ahora=MIERCOLES_11)
    assert r.intent == "buscar" and "Farmacia Ángeles" in r.texto


# ------------------------------------------------------------------ 6. el paso

def test_el_paso_sin_ciudad_es_aguas_blancas(repo):
    r = _preguntar(repo, "¿cómo está el paso hoy?")
    assert r.intent == "frontera_hoy" and r.texto.startswith("Hoy en la frontera con Aguas Blancas:")
    assert "frontera con la frontera" not in r.texto


def test_el_paso_sin_nombre_no_repite_la_palabra_frontera(repo):
    ciudad = {"slug": "villazon", "nombre": "Villazón", "guia_activa": True, "paso_nombre": None}
    r = _preguntar(repo, "¿cómo está el paso hoy?", ciudad=ciudad)
    assert r.intent == "frontera_hoy" and r.texto.startswith("Hoy en el paso de Villazón:")
    assert "frontera con la frontera" not in r.texto
    ciudad["paso_nombre"] = "  "
    assert _preguntar(repo, "¿cómo está el paso hoy?", ciudad=ciudad).texto.startswith("Hoy en el paso de Villazón:")


def test_el_paso_con_nombre_lo_dice(repo):
    ciudad = {"slug": "villazon", "nombre": "Villazón", "guia_activa": True, "paso_nombre": "La Quiaca"}
    assert _preguntar(repo, "¿cómo está el paso hoy?", ciudad=ciudad).texto.startswith("Hoy en la frontera con La Quiaca:")


# ------------------------------------------------------------------ 7. pesos

def test_aceptan_pesos_es_una_pregunta_de_pago_no_de_cambio(repo):
    _saber(repo, "¿Dónde cambio dólares o pesos?", "¿Con qué moneda pago en Bermejo?", "¿Dónde cambio plata en Bermejo?")
    r = _preguntar(repo, "¿aceptan pesos?")
    assert r.intent == "saber_local" and r.fuentes[0]["nombre"] == "¿Con qué moneda pago en Bermejo?"
    assert "pesos argentinos" in r.texto and "bolivianos" in r.texto and "dólares" in r.texto


@pytest.mark.parametrize("pregunta", ["¿aceptan dólares?", "¿se puede pagar con pesos?", "¿reciben pesos argentinos?"])
def test_otras_formas_de_preguntar_con_que_se_paga(repo, pregunta):
    _saber(repo, "¿Dónde cambio dólares o pesos?", "¿Con qué moneda pago en Bermejo?")
    assert _preguntar(repo, pregunta).fuentes[0]["nombre"] == "¿Con qué moneda pago en Bermejo?"


def test_donde_cambio_pesos_sigue_siendo_cambio(repo):
    _saber(repo, "¿Dónde cambio dólares o pesos?", "¿Con qué moneda pago en Bermejo?")
    assert _preguntar(repo, "¿dónde cambio pesos?").intent == "casas_de_cambio"


# ------------------------------------------------------------------ 8. encargos y guardería

@pytest.mark.parametrize("pregunta", [
    "¿me pueden comprar algo y guardármelo?", "¿pueden comprarme algo?", "¿alguien me puede guardar una compra?",
    "¿tienen servicio de encargos?", "¿me lo guardan hasta que vaya?", "¿hay guardería?",
])
def test_comprar_y_guardar_es_el_servicio_de_uruku(repo, pregunta):
    _saber(repo, "¿Me pueden mandar o guardar la compra?", "No puedo ir a Bermejo")
    r = _preguntar(repo, pregunta)
    assert r.intent == "encargo" and not r.sin_respuesta and "67 671 888" in r.texto
    assert "https://wa.me/59167671888" in r.texto


def test_el_encargo_sin_la_entrada_tambien_se_contesta(repo):
    r = _preguntar(repo, "¿me pueden comprar algo y guardármelo?")
    assert r.intent == "encargo" and "67 671 888" in r.texto and "guardería" in r.texto
    assert "https://wa.me/59167671888" in r.texto


def test_el_encargo_sin_numero_publico_no_inventa_uno(repo, monkeypatch):
    monkeypatch.setattr(settings, "wa_contacto_publico", "")
    r = _preguntar(repo, "¿me pueden comprar algo y guardármelo?")
    assert r.intent == "encargo" and "wa.me" not in r.texto and "uruku.bo" in r.texto


def test_comprar_a_secas_o_donde_comprar_no_es_un_encargo(repo):
    _comercio(repo, "com-zap", "Zapatería Luz", subcategoria="calzado", prod_obs_human="zapatillas")
    assert _preguntar(repo, "¿dónde puedo comprar zapatillas?").intent == "buscar"
    assert _preguntar(repo, "¿qué conviene comprar?").intent != "encargo"


def test_el_encargo_en_una_ciudad_sin_guia_no_se_ofrece(repo):
    ciudad = {"slug": "cobija", "nombre": "Cobija", "guia_activa": False}
    assert _preguntar(repo, "¿me pueden comprar algo y guardármelo?", ciudad=ciudad).intent != "encargo"


# ------------------------------------------------------------------ 9. cómo me muevo

def test_como_me_muevo_encuentra_la_de_taxis(repo):
    _saber(repo, "¿Cómo me muevo dentro de Bermejo?")
    r = _preguntar(repo, "¿cómo me muevo en Bermejo?")
    assert r.intent == "saber_local" and "taxis" in r.texto.lower()


def test_una_palabra_suelta_en_una_pregunta_de_dos_no_alcanza(repo):
    """El mínimo sigue siendo el de siempre: la excepción es sólo para la pregunta de UNA palabra útil."""
    _saber(repo, "¿Dónde cambio dólares o pesos?")
    assert _preguntar(repo, "cambio de aceite para moto").intent != "saber_local"


# ------------------------------------------------------------------ 10. productos sueltos

def test_perfumes_sin_resultados_ofrece_el_encargo_como_cualquier_producto(repo):
    r = _preguntar(repo, "perfumes")
    termo = _preguntar(repo, "¿dónde compro un termo stanley?")
    assert r.intent == termo.intent == "buscar" and r.sin_respuesta
    assert r.texto.startswith("No encontré «perfumes»") and "67 671 888" in r.texto and "wa.me/59167671888" in r.texto
    assert "https://uruku.bo/buscar?q=perfumes" in r.texto


def test_dos_palabras_de_producto_aunque_una_este_en_una_etiqueta(repo):
    _saber(repo, "¿Dónde compro juguetes, bazar o cosas para bebés?")
    r = _preguntar(repo, "mochilas escolares")
    assert r.intent == "buscar" and r.texto.startswith("No encontré «mochilas escolares»")


def test_perfumes_con_comercios_lista_los_comercios(repo):
    _comercio(repo, "com-perf", "Perfumería Bella", subcategoria="perfumería", prod_obs_human="perfumes, cremas")
    r = _preguntar(repo, "perfumes")
    assert r.intent == "buscar" and not r.sin_respuesta and "Perfumería Bella" in r.texto


@pytest.mark.parametrize("pregunta, intent", [
    ("hola", "saludo"), ("gracias", "gracias"), ("buenas tardes", "saludo"), ("ok gracias", "gracias"),
    ("franquicia", "saber_local"), ("aduana", "saber_local"), ("feriados", "saber_local"),
])
def test_lo_que_no_es_un_producto_sigue_igual(repo, pregunta, intent):
    _comercio(repo, "com-ad", "Despachante Aduana Sur", subcategoria="despachante", prod_obs_human="aduana franquicia")
    _saber(repo, "¿Cuánto puedo llevar de vuelta a Argentina sin pagar?", "¿Qué NO se puede pasar por la aduana?",
           "¿Qué feriados de Bolivia cierran los comercios?")
    assert _preguntar(repo, pregunta).intent == intent


def test_una_palabra_de_saber_local_gana_a_la_busqueda_sin_resultados(repo):
    _saber(repo, "¿Cómo me muevo dentro de Bermejo?")
    assert _preguntar(repo, "taxis").intent == "saber_local"


@pytest.mark.parametrize("pregunta", ["celular", "bazar", "mujer"])
def test_un_producto_que_termina_como_un_verbo_igual_se_busca(repo, pregunta):
    r = _preguntar(repo, pregunta)
    assert r.intent == "buscar" and r.texto.startswith(f"No encontré «{pregunta}»")


@pytest.mark.parametrize("pregunta", ["cuándo", "ayuda", "cruzar", "comprar", "pagar", "12", "ok"])
def test_lo_que_no_parece_un_producto_no_se_busca(repo, pregunta):
    r = _preguntar(repo, pregunta)
    assert r.intent != "buscar"


# ------------------------------------------------------------------ 11. hospital

def test_hay_hospital_con_entrada_de_salud_no_son_solo_los_telefonos(repo):
    _saber(repo, "¿A quién llamo en una emergencia en Bermejo?", "¿Hay hospital en Bermejo?")
    r = _preguntar(repo, "¿hay hospital?")
    assert r.intent == "saber_local" and r.fuentes[0]["nombre"].startswith("¿Hay hospital")
    assert "preferimos no inventarlos" in r.texto


def test_hay_hospital_sin_entrada_de_salud_contesta_los_telefonos(repo):
    _saber(repo, "¿A quién llamo en una emergencia en Bermejo?")
    r = _preguntar(repo, "¿hay hospital?")
    assert r.intent == "saber_local" and "168" in r.texto


def test_hospital_con_locales_de_emergencias_cargados_y_entrada_gana_la_entrada(repo):
    _comercio(repo, "com-pol", "Policía Bermejo", rubro_slug="emergencias", subcategoria="policía")
    _saber(repo, "¿Hay hospital en Bermejo?")
    assert _preguntar(repo, "¿hay hospital?").intent == "saber_local"


# ------------------------------------------------------------------ todo junto (la base de demo)

def _demo(repo):
    """La base de demo: las migraciones 0106/0107/0110 y las entradas VERIFICADAS del JSON."""
    todas = {f["pregunta"]: f for f in _json() if f["verificado"]}
    for archivo in ("0106_uruku_ayuda.sql", "0107_saber_local_compras.sql", "0110_guia_del_que_llega.sql"):
        todas.update({f["pregunta"]: f for f in _sql(archivo)})
    for f in todas.values():
        repo.upsert_saber_local({"pregunta": f["pregunta"], "respuesta": f["respuesta"], "etiquetas": f["etiquetas"]})
    _comercio(repo, "com-cambio", "Casa de Cambio El Puente", subcategoria="cambio", rubro_slug="cambio")
    _comercio(repo, "com-tours", "Cruzar Viajes y Tours", subcategoria="turismo")
    _farmacia(repo, "f1", "Farmacia Ángeles")
    repo.lugares["l1"] = {"id": "l1", "nombre": "Mercado Central", "tipo": "mercado", "activo": True}


def test_las_once_preguntas_contra_la_base_de_demo(repo):
    _demo(repo)
    ahora = MIERCOLES_11

    def r(q):
        return _preguntar(repo, q, ahora=ahora)
    assert "24 horas" in r("¿a qué hora abre el puente?").texto and "Casa de Cambio" not in r("¿a qué hora abre el puente?").texto
    assert r("¿qué documentos necesito para cruzar?").fuentes[0]["nombre"].startswith("¿Qué documentos necesito para cruzar?")
    assert r("¿puede cruzar un menor solo con la mamá?").fuentes[0]["nombre"].startswith("¿Qué documentos necesito para cruzar?")
    assert r("¿qué feriados hay?").intent == "saber_local" and "Mercado Central" not in r("¿qué feriados hay?").texto
    assert r("¿qué farmacia está de turno?").intent == "farmacia_turno"
    assert r("¿cómo está el paso hoy?").texto.startswith("Hoy en la frontera con Aguas Blancas:")
    assert r("¿aceptan pesos?").fuentes[0]["nombre"] == "¿Con qué moneda pago en Bermejo?"
    assert r("¿me pueden comprar algo y guardármelo?").intent == "encargo"
    assert r("¿cómo me muevo en Bermejo?").fuentes[0]["nombre"].startswith("¿Cómo me muevo dentro de Bermejo?")
    assert r("perfumes").texto.startswith("No encontré «perfumes»")
    assert r("mochilas escolares").texto.startswith("No encontré «mochilas escolares»")
    assert r("¿hay hospital?").intent == "saber_local"
    assert r("franquicia").intent == "saber_local" and r("hola").intent == "saludo" and r("gracias").intent == "gracias"
