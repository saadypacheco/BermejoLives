"""Subcategoría legible de lo que viene de una página de turismo (docs/turismo-home-y-repetidos.md §2).

El importador guarda en `importados.categoria` el slug de la subcategoría de la página (`guias`, `radio-moviles`,
`hoteles`…). Al promover (o al completar un comercio que ya existe) ese slug pasa a `comercios.subcategoria` con una
etiqueta en castellano. Es una tabla fija: lo que no está queda como venía (o sin subcategoría).

Sin dependencias (lo importan `tarjetas`, `completar_importado` y el router): no importar nada de `app` acá.
"""
from __future__ import annotations

#: Los textos EXACTOS con los que la home de turismo separa guías de agencias y radio móviles de transportes: el
#: frontend filtra `comercios.subcategoria` por este texto. No cambiarlos sin cambiar el front.
SUB_GUIA = "Guía de turismo"
SUB_RADIO_MOVIL = "Radio móvil"
SUB_TRANSPORTE_ALREDEDORES = "Transporte a los alrededores"
ETIQUETAS_DE_LA_HOME = (SUB_GUIA, SUB_RADIO_MOVIL, SUB_TRANSPORTE_ALREDEDORES)

#: slug de la subcategoría de la página → etiqueta legible.
ETIQUETA_POR_SLUG: dict[str, str] = {
    # tablas de «Cómo moverse» y de «Guías de turismo autorizados»
    "guias": SUB_GUIA, "guias-de-turismo-autorizados": SUB_GUIA,
    "radio-moviles": SUB_RADIO_MOVIL, "transporte-alrededores": SUB_TRANSPORTE_ALREDEDORES,
    # agencias y operadoras
    "agencias-de-viajes": "Agencia de viajes", "operadoras-de-turismo": "Operadora de turismo",
    # dónde dormir
    "hoteles": "Hotel", "apart-hotel": "Apart hotel", "hostales": "Hostal", "hostels": "Hostel",
    "alojamientos": "Alojamiento", "residenciales": "Residencial",
    # dónde comer
    "churrasquerias": "Churrasquería", "boliviana-regional-criolla": "Comida boliviana",
    "resto-bar": "Resto bar", "saludable-vegetariana": "Comida saludable", "pizzeria": "Pizzería",
    "pescados-y-mariscos": "Pescados y mariscos", "afuera-de-la-ciudad-campestre": "Restaurante campestre",
    "cocina-italiana-pastas": "Cocina italiana", "saltenerias": "Salteñería", "comida-rapida": "Comida rápida",
    "patio-de-comidas": "Patio de comidas", "cafeteria": "Cafetería", "heladerias-dulces": "Heladería y dulces",
    # qué hacer
    "bodegas-y-vinotecas": "Bodega", "diversion-nocturna": "Diversión nocturna",
    "complejos-deportivos-y-gimnasios": "Complejo deportivo", "complejos-turisticos": "Complejo turístico",
    "balneareos-privados": "Balneario", "diversion-en-familia": "Diversión en familia",
}

#: Si la subcategoría no está en la tabla pero la fila viene de una de estas secciones de la página, se usa la de la
#: sección (una agencia con una categoría rara sigue siendo una agencia).
ETIQUETA_POR_SECCION: dict[str, str] = {
    "agencias-de-viajes": "Agencia de viajes", "operadoras-de-turismo": "Operadora de turismo",
    "guias-de-turismo-autorizados": SUB_GUIA,
}


def etiqueta_de(categoria: str | None, seccion: str | None = None) -> str | None:
    """La etiqueta legible de una categoría de la página de turismo; `None` si no hay una para ella."""
    cat = (categoria or "").strip().lower()
    if cat in ETIQUETA_POR_SLUG:
        return ETIQUETA_POR_SLUG[cat]
    return ETIQUETA_POR_SECCION.get((seccion or "").strip().lower())


def subcategoria_de_importado(imp: dict) -> str | None:
    """La subcategoría con la que queda el comercio al promover (o completar) este importado.

    Si el importado ya trae `subcategoria` (los lugares para visitar: Plaza, Mirador…) manda esa. Si no y viene de
    una página de turismo, la etiqueta legible de su categoría. Lo que no está en la tabla queda como venía (la
    categoría cruda de un importado de turismo no se copia: es un slug técnico)."""
    propia = (imp.get("subcategoria") or "").strip()
    if propia:
        return propia
    if imp.get("fuente") != "turismo":
        return None
    tags = imp.get("tags") if isinstance(imp.get("tags"), dict) else {}
    seccion = ((tags.get("turismo") or {}).get("seccion") if isinstance(tags.get("turismo"), dict) else None)
    return etiqueta_de(imp.get("categoria"), seccion)
