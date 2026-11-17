"""Completar el comercio que ya existe con lo que trae un importado repetido (docs/turismo-home-y-repetidos.md §1).

Un importado de turismo o de tarjeta con `duplicado_de` NO se promueve como comercio nuevo por defecto: el que ya está
en URUKU lo cargó alguien parado en la calle (punto exacto, foto) y la página de turismo trae más datos (teléfonos,
web, dirección escrita, horario). Se mira uno al lado del otro y se COMPLETA el existente.

- `comparar`: los dos lado a lado, campo por campo, con lo que se sugiere hacer con cada uno.
- `completar`: aplica. Lo vacío del existente se llena solo; si los dos tienen un dato distinto se queda el del
  existente salvo que la persona pida el nuevo. Nunca se tocan la foto, `verificado`, `confiable`, `cargado_por`,
  `codigo` ni el slug; el punto del existente gana siempre.
- `no_es_repetido`: saca el aviso de repetido (queda para promover como nuevo).

Las funciones de armado (`armar_campos`, `decidir`) son puras; el resto usa el repo.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

import structlog

from app.core.telefono import normalizar_whatsapp, validar_whatsapp, whatsapp_para_guardar
from app.core.telefonos_foto import clave_de_comparacion
from app.services import calles_mapa, enlaces
from app.services.rubros_auto import MAX_RUBROS
from app.services.subcategorias_turismo import subcategoria_de_importado

logger = structlog.get_logger()

#: Los campos que se comparan, en el orden en que sale en la pantalla.
CAMPOS = ("nombre", "direccion", "telefono", "whatsapp", "sitio_web", "email", "horario", "fuente_url",
          "subcategoria", "punto")
#: Los que se escriben como una columna de texto del comercio (el punto va en `lat` y `lng`).
CAMPOS_DE_TEXTO = tuple(c for c in CAMPOS if c != "punto")

MOTIVO = "completó el existente"
RUBRO_GENERICO = "otros"


class CompletarError(Exception):
    """Algo que el panel tiene que mostrar: `status` HTTP y `detail` en español."""

    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status = status
        self.detail = detail


# ───────────────────────────────────────────────────────────── puras

def _texto(valor) -> str | None:
    t = str(valor).strip() if valor is not None else ""
    return t or None


def _clave_texto(valor: str | None) -> str:
    return re.sub(r"\s+", " ", (valor or "").casefold()).strip()


def _clave_web(valor: str | None) -> str:
    v = (valor or "").casefold().strip()
    v = re.sub(r"^[a-z]+://", "", v)
    v = re.sub(r"^www\.", "", v)
    return v.rstrip("/")


def _claves_telefono(valor: str | None) -> set[str]:
    """Las claves de comparación de cada número de un texto con varios («a / b»)."""
    claves = set()
    for parte in re.split(r"[/;,]", str(valor or "")):
        k = clave_de_comparacion(parte)
        if k and len(k) >= 8:
            claves.add(k)
    return claves


def _punto(lat, lng) -> dict | None:
    try:
        if lat is None or lng is None:
            return None
        return {"lat": float(lat), "lng": float(lng)}
    except (TypeError, ValueError):
        return None


def _celular_para_guardar(valor: str | None) -> str | None:
    """El número como se guarda en `whatsapp` si es un CELULAR boliviano (591 + 6/7 + 7 dígitos) o argentino (549 +
    10 dígitos); `None` si es un fijo u otra cosa (un fijo no abre un chat)."""
    num = normalizar_whatsapp(valor)
    if not num or validar_whatsapp(valor) is not None:
        return None
    if num.startswith("591") or num.startswith("549"):
        return whatsapp_para_guardar(valor)
    return None


def valores_nuevos(imp: dict) -> dict:
    """Lo que aporta el importado, campo por campo, ya normalizado como se guarda en el comercio.

    El WhatsApp sólo cuenta si es un celular que valida (misma regla que al promover una tarjeta): un fijo no abre
    un chat. La subcategoría es la legible (`Guía de turismo`, `Radio móvil`…), no el slug de la página."""
    wa = _texto(imp.get("whatsapp"))
    return {
        "nombre": _texto(imp.get("nombre")),
        "direccion": _texto(imp.get("direccion")),
        "telefono": _texto(imp.get("telefono")),
        "whatsapp": _celular_para_guardar(wa),
        "sitio_web": enlaces.sanear_red(imp.get("website"), "El sitio web"),
        "email": _texto(imp.get("email")),
        "horario": _texto(imp.get("horario")),
        "fuente_url": _texto(imp.get("fuente_url")),
        "subcategoria": subcategoria_de_importado(imp),
        "punto": _punto(imp.get("lat"), imp.get("lng")),
    }


def valores_actuales(comercio: dict) -> dict:
    return {
        "nombre": _texto(comercio.get("nombre")),
        "direccion": _texto(comercio.get("direccion")),
        "telefono": _texto(comercio.get("telefono")),
        "whatsapp": _texto(comercio.get("whatsapp")),
        "sitio_web": _texto(comercio.get("sitio_web")),
        "email": _texto(comercio.get("email")),
        "horario": _texto(comercio.get("horario")),
        "fuente_url": _texto(comercio.get("fuente_url")),
        "subcategoria": _texto(comercio.get("subcategoria")),
        "punto": _punto(comercio.get("lat"), comercio.get("lng")),
    }


def _son_iguales(campo: str, actual, nuevo, comercio: dict) -> bool:
    if campo == "punto":
        return round(actual["lat"], 5) == round(nuevo["lat"], 5) and round(actual["lng"], 5) == round(nuevo["lng"], 5)
    if campo == "telefono":
        # Un número que el existente ya tiene (como teléfono o como WhatsApp) no es un dato nuevo.
        propios = _claves_telefono(actual) | _claves_telefono(comercio.get("whatsapp"))
        return _claves_telefono(nuevo) <= propios
    if campo == "whatsapp":
        return normalizar_whatsapp(actual) == normalizar_whatsapp(nuevo)
    if campo == "sitio_web":
        return _clave_web(actual) == _clave_web(nuevo)
    return _clave_texto(actual) == _clave_texto(nuevo)


def sugerir(campo: str, actual, nuevo, comercio: dict) -> str:
    """`completar` (el existente está vacío y el importado trae dato), `igual` (nada que sumar: el importado no
    trae dato o es el mismo) o `conservar` (los dos tienen un dato distinto: se queda el del existente)."""
    if not nuevo:
        return "igual"
    if campo == "telefono" and _son_iguales(campo, actual or "", nuevo, comercio):
        return "igual"                                  # el número ya está (como WhatsApp, por ejemplo)
    if not actual:
        return "completar"
    return "igual" if _son_iguales(campo, actual, nuevo, comercio) else "conservar"


def armar_campos(comercio: dict, imp: dict) -> list[dict]:
    """`[{campo, actual, nuevo, sugerido}]` en el orden de `CAMPOS`."""
    act, nue = valores_actuales(comercio), valores_nuevos(imp)
    return [{"campo": c, "actual": act[c], "nuevo": nue[c], "sugerido": sugerir(c, act[c], nue[c], comercio)}
            for c in CAMPOS]


def validar_usar(usar: dict | None) -> dict[str, str]:
    """`usar` sólo puede nombrar campos de la comparación y pedir `"nuevo"`."""
    limpio: dict[str, str] = {}
    for campo, valor in (usar or {}).items():
        if campo not in CAMPOS:
            raise CompletarError(400, f"Campo desconocido: «{campo}»")
        if valor != "nuevo":
            raise CompletarError(400, f"Del campo «{campo}» sólo se puede pedir el valor nuevo")
        limpio[campo] = valor
    return limpio


def decidir(campos: list[dict], usar: dict[str, str]) -> dict:
    """Qué se escribe en el comercio: `{columna: valor}` (el punto como `lat` y `lng`).

    - Lo vacío en el existente con dato en el importado se completa solo.
    - Con los dos datos distintos se conserva el existente, salvo `usar[campo] == "nuevo"`.
    - El nombre sólo cambia si viene en `usar`. El WhatsApp sólo se completa (nunca se reemplaza). El punto del
      existente gana siempre: sólo se copia si el existente no tiene."""
    patch: dict = {}
    for c in campos:
        campo, nuevo, sug = c["campo"], c["nuevo"], c["sugerido"]
        if not nuevo or sug == "igual":
            continue
        if campo == "punto":
            if sug == "completar":
                patch["lat"], patch["lng"] = nuevo["lat"], nuevo["lng"]
        elif campo == "whatsapp":
            if sug == "completar":
                patch["whatsapp"] = nuevo
        elif campo == "nombre":
            if usar.get("nombre") == "nuevo":
                patch["nombre"] = nuevo
        elif sug == "completar" or usar.get(campo) == "nuevo":
            patch[campo] = nuevo
    return patch


def comercio_comparado(comercio: dict) -> dict:
    """El comercio como lo ve el panel al compararlo (sin `codigo`, `confiable` ni nada privado)."""
    return {
        "id": comercio.get("id"), "nombre": comercio.get("nombre"), "slug": comercio.get("slug"),
        "direccion": comercio.get("direccion"), "telefono": comercio.get("telefono"),
        "whatsapp": comercio.get("whatsapp"), "sitio_web": comercio.get("sitio_web"),
        "email": comercio.get("email"), "horario": comercio.get("horario"),
        "lat": comercio.get("lat"), "lng": comercio.get("lng"),
        "tiene_foto": bool(comercio.get("portada_url") or comercio.get("portada_thumb_url")),
        "fuente_url": comercio.get("fuente_url"), "subcategoria": comercio.get("subcategoria"),
        "verificado": bool(comercio.get("verificado")),
    }


def rubro_a_aplicar(actuales: list[str], sugerido: str | None) -> tuple[str, list[str]]:
    """Qué hacer con el rubro sugerido: `(accion, rubros_finales)`.

    `igual` (ya lo tiene o no hay sugerido), `reemplazar` (no tenía rubro o el único era `otros`), `sumar`, o
    `tope` (ya tiene `MAX_RUBROS`: no se agrega)."""
    if not sugerido or sugerido in actuales:
        return "igual", list(actuales)
    if not actuales or actuales == [RUBRO_GENERICO]:
        return "reemplazar", [sugerido]
    if len(actuales) >= MAX_RUBROS:
        return "tope", list(actuales)
    return "sumar", [*actuales, sugerido]


# ───────────────────────────────────────────────────────────── con el repo

def rubro_es_no_comercial(repo, rubro_slug: str | None) -> bool:
    """¿El rubro existe y es NO comercial (`rubros.comercial = false`)? Uno que no se encuentra cuenta como comercial."""
    return any(r.get("slug") == rubro_slug and r.get("comercial") is False for r in repo.list_rubros())


def _cargar_par(repo, importado_id: str, comercio_id: str | None) -> tuple[dict, dict]:
    imp = repo.get_importado(importado_id)
    if not imp:
        raise CompletarError(404, "No existe ese importado")
    cid = (comercio_id or "").strip() or imp.get("duplicado_de")
    if not cid:
        raise CompletarError(400, "Este importado no tiene un repetido: indicá con qué comercio compararlo")
    comercio = repo.get_comercio(cid)
    if not comercio or comercio.get("activo") is False:
        raise CompletarError(404, "No existe ese comercio")
    return imp, comercio


def comparar(repo, importado_id: str, comercio_id: str | None = None) -> dict:
    """Los dos lado a lado: `{comercio, campos, rubro_sugerido, rubros_actuales}`."""
    imp, comercio = _cargar_par(repo, importado_id, comercio_id)
    return {
        "comercio": comercio_comparado(comercio),
        "campos": armar_campos(comercio, imp),
        "rubro_sugerido": _texto(imp.get("rubro_slug")),
        "rubros_actuales": repo.get_comercio_rubros(comercio["id"]),
    }


def completar(repo, importado_id: str, comercio_id: str, usar: dict | None, sumar_rubro: bool,
              por: str) -> dict:
    """Aplica la comparación al comercio existente y deja el importado promovido apuntando a él.

    Devuelve `{ok, comercio, cambiados, rubros}`: `cambiados` son los campos escritos (con `rubro` si cambió el
    rubro) y `rubros` los slugs que el comercio tiene al terminar."""
    imp, comercio = _cargar_par(repo, importado_id, comercio_id)
    pedido = validar_usar(usar)
    if imp.get("estado") != "nuevo":
        raise CompletarError(409, "Ese importado ya se revisó")

    campos = armar_campos(comercio, imp)
    patch = decidir(campos, pedido)
    cid = comercio["id"]
    if patch:
        comercio = repo.actualizar_campos_comercio(cid, patch) or {**comercio, **patch}
    cambiados = [c for c in CAMPOS_DE_TEXTO if c in patch]
    if "lat" in patch:
        cambiados.append("punto")
        calles_mapa.invalidar(comercio.get("ciudad_id") or imp.get("ciudad_id"))

    rubros = repo.get_comercio_rubros(cid)
    sugerido = _texto(imp.get("rubro_slug"))
    if sumar_rubro and sugerido:
        accion, finales = rubro_a_aplicar(rubros, sugerido)
        rid = repo.get_rubro_id(sugerido) if accion in ("reemplazar", "sumar") else None
        if rid and accion == "reemplazar":
            repo.reemplazar_comercio_rubros(cid, [rid])
        elif rid:
            repo.set_comercio_rubros(cid, [rid])
        if rid:
            cambiados.append("rubro")
            rubros = finales
        # Un rubro no comercial (`para-visitar`) lo puso una persona: lo masivo no se lo cambia.
        if sugerido in rubros and rubro_es_no_comercial(repo, sugerido):
            repo.marcar_rubro_revisado(cid, por)

    repo.marcar_importado(importado_id, {
        "estado": "promovido", "comercio_id": cid, "motivo": MOTIVO,
        "revisado_por": por, "revisado_at": datetime.now(timezone.utc).isoformat(),
    })
    logger.info("importado.completado", importado=importado_id, comercio=cid, cambiados=cambiados, by=por)
    return {"ok": True, "comercio": comercio_comparado(comercio), "cambiados": cambiados, "rubros": rubros}


def no_es_repetido(repo, importado_id: str) -> dict:
    """Saca el aviso de repetido: el importado queda `nuevo`, sin `duplicado_de`, para promoverlo como comercio
    nuevo. Devuelve la fila actualizada."""
    imp = repo.get_importado(importado_id)
    if not imp:
        raise CompletarError(404, "No existe ese importado")
    if imp.get("estado") != "nuevo":
        raise CompletarError(409, "Ese importado ya se revisó")
    fila = repo.marcar_importado(importado_id, {"duplicado_de": None})
    logger.info("importado.no_es_repetido", importado=importado_id, comercio=imp.get("duplicado_de"))
    return fila or {**imp, "duplicado_de": None}
