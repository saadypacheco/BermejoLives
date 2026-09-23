"""Qué puede hacer cada rol: el catálogo de permisos.

EL CATÁLOGO VIVE ACÁ Y NO EN LA BASE, a propósito. Un permiso es algo que el
código sabe hacer: «moderar», «editar comercios», «cargar contenido». Si el
nombre estuviera sólo en la base, alguien podría inventar el permiso
«facturar» desde el panel y no existiría ningún endpoint que lo mire — un
tilde que no hace nada es peor que no tener el tilde.

Lo que SÍ vive en la base (tabla `roles`) es **qué permisos tiene cada rol**,
y eso se arma desde el panel: se puede crear un rol nuevo («Cargador de Santa
Cruz») eligiendo de esta lista, sin tocar código ni desplegar.

Cada endpoint declara el permiso que necesita. Hasta hoy declaraba un ROL
(`require_admin`, `require_moderador`…), que es la forma de que el día que
aparece un rol nuevo haya que editar cien archivos.
"""
from __future__ import annotations

# ── el catálogo, agrupado como se ve en el panel ─────────────────────────────
# (permiso, qué significa, grupo)
CATALOGO: list[tuple[str, str, str]] = [
    ("moderar",          "Aprobar o rechazar lo que mandan los comercios",        "Día a día"),
    ("comercios.editar", "Editar la ficha de cualquier comercio",                 "Día a día"),
    ("comercios.cargar", "Cargar comercios desde la calle (app de campo)",        "Día a día"),
    ("contenido",        "Cotización, estado de la frontera, videos y redes",     "Día a día"),
    ("ayuda",            "Contestar preguntas y cargar el saber local",           "Día a día"),
    ("lugares",          "Mercados, galerías y puntos del mapa",                  "Día a día"),
    ("rubros",           "Rubros, palabras y revisión de la clasificación",       "Catálogo"),
    ("difusion",         "Publicar en las redes de URUKU",                        "Catálogo"),
    ("whatsapp",         "La bandeja de WhatsApp y los grupos",                   "Catálogo"),
    ("planes",           "Precios, cuotas y funciones de los planes",             "Plata"),
    ("pagos",            "Registrar pagos, suscripciones y vencimientos",         "Plata"),
    ("datos",            "KPIs, base de compradores y estadísticas",              "Plata"),
    ("equipo",           "Crear usuarios, asignar roles y cambiar permisos",      "Sistema"),
    # El cajón de lo que todavía no tiene permiso propio. Sirve para no
    # dejar un endpoint sin guardia mientras se reparte de a poco: quien lo
    # tenga entra a lo que quede sin clasificar.
    ("panel",            "El resto del panel (lo que no tiene permiso propio)",   "Sistema"),
]

TODOS = [p for p, _, _ in CATALOGO]

#: El permiso que abre todas las puertas. Un rol con esto no necesita los demás.
TODO = "*"


# ── los roles que trae el sistema ────────────────────────────────────────────
# Es la semilla de la tabla `roles` (migración 0126) y, además, el mapa que
# hace que un token VIEJO —de los que sólo llevan `rol`— siga funcionando
# mientras no venza. Sin esto, un deploy deja a todo el mundo afuera.
ROLES_BASE: dict[str, dict] = {
    "admin": {
        "nombre": "Administrador",
        "descripcion": "Todo. Es el rol de quien maneja URUKU.",
        "permisos": [TODO],
    },
    "moderador": {
        "nombre": "Moderador",
        "descripcion": "Aprueba lo que llega, corrige fichas y contesta la Ayuda.",
        "permisos": ["moderar", "comercios.editar", "ayuda", "lugares", "whatsapp", "rubros"],
    },
    "publicador": {
        "nombre": "Publicador",
        "descripcion": "Carga la cotización, el estado del paso y los videos.",
        "permisos": ["contenido", "moderar"],
    },
    "agente": {
        "nombre": "Agente de campo",
        "descripcion": "Carga comercios desde la calle, en su ciudad.",
        "permisos": ["comercios.cargar"],
    },
}


def permisos_de_roles(roles: list[str], catalogo: dict[str, list[str]] | None = None) -> list[str]:
    """Los permisos que suman esos roles. `catalogo` es lo que dice la base;
    sin él, los roles del sistema (para tokens viejos y para el `.env`)."""
    fuente = catalogo or {k: v["permisos"] for k, v in ROLES_BASE.items()}
    juntos: set[str] = set()
    for r in roles or []:
        juntos.update(fuente.get(r, []))
    return sorted(juntos)


def tiene(claims: dict, permiso: str) -> bool:
    """¿Este token puede hacer esto?

    Mira los permisos del token. Si no los trae —un token emitido antes de
    este cambio, que sigue vivo hasta que venza— cae en los roles del sistema,
    que es exactamente lo que ese token podía hacer ayer."""
    permisos = claims.get("permisos")
    if not permisos:
        roles = claims.get("roles") or ([claims["rol"]] if claims.get("rol") else [])
        permisos = permisos_de_roles(roles)
    return TODO in permisos or permiso in permisos
