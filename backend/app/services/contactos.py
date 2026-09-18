"""La base de compradores: normalizar los números y armar el resumen.

Los teléfonos vienen como los escribió cada uno: "+54 9 387 512-3456",
"0387 15 512 3456", "3875123456", "71234567", "591 71234567". Todos tienen
que terminar como dígitos con país, que es como los guarda `usuarios` y como
los usa wa.me: 549… para Argentina, 591… para Bolivia.
"""
from __future__ import annotations

import re
import unicodedata


def normalizar_telefono(crudo: str | None, pais: str = "AR") -> tuple[str, bool]:
    """Devuelve (número con país, válido).

    Argentina: el 0 de área y el 15 del celular sobran; WhatsApp usa
    549 + área + número. Bolivia: 8 dígitos que empiezan en 6 o 7 → 591.
    Lo que no encaja se guarda igual, marcado como no válido, para que se
    vea en el panel y no se pierda."""
    if crudo is None:
        return "", False
    s = str(crudo).strip()
    # Excel suele guardar "5.49387E+12": se recupera el entero.
    if re.fullmatch(r"\d+(\.\d+)?[eE]\+?\d+", s):
        try:
            s = str(int(float(s)))
        except ValueError:
            pass
    digitos = re.sub(r"\D", "", s)
    if digitos.startswith("00"):
        digitos = digitos[2:]
    if not digitos:
        return "", False

    # Ya viene con país.
    # Argentina con país: 549 + área + número = 13 dígitos, siempre.
    if digitos.startswith("549") and len(digitos) == 13:
        return digitos, True
    if digitos.startswith("54") and not digitos.startswith("549") and len(digitos) == 12:
        return "549" + digitos[2:], True
    if digitos.startswith("591") and len(digitos) == 11:
        return digitos, True

    # Bolivia sin país: celular de 8 dígitos que empieza en 6 o 7.
    if len(digitos) == 8 and digitos[0] in "67":
        return "591" + digitos, True

    # Argentina sin país: "0387 15 5123456" → "387 5123456".
    if digitos.startswith("0"):
        digitos = digitos[1:]
    # El 15 después del área (2 a 4 dígitos): sólo si al sacarlo quedan 10.
    if len(digitos) == 12:
        for area in (2, 3, 4):
            if digitos[area:area + 2] == "15":
                candidato = digitos[:area] + digitos[area + 2:]
                if len(candidato) == 10:
                    digitos = candidato
                    break
    if len(digitos) == 10 and pais.upper() == "AR":
        return "549" + digitos, True
    if len(digitos) == 10 and digitos.startswith("9") and pais.upper() == "AR":
        return "54" + digitos, True
    return digitos, False


def slug_grupo(nombre: str | None) -> str:
    s = unicodedata.normalize("NFD", (nombre or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:48] or "sin-grupo"


def preparar_filas(filas: list[dict], origen: str, pais: str = "AR") -> tuple[list[dict], list[dict]]:
    """Filas del Excel → filas de `contactos_base`, deduplicadas por
    (teléfono, grupo). Devuelve (válidas, inválidas)."""
    vistas: set[tuple[str, str]] = set()
    buenas: list[dict] = []
    malas: list[dict] = []
    for f in filas:
        tel, ok = normalizar_telefono(f.get("telefono"), pais)
        grupo = str(f.get("grupo") or "").strip()[:120]
        gslug = slug_grupo(grupo)
        clave = (tel, gslug)
        if not tel or clave in vistas:
            if not tel:
                malas.append({"telefono": str(f.get("telefono") or ""), "grupo": grupo, "motivo": "sin número"})
            continue
        vistas.add(clave)
        fila = {
            "telefono": tel, "grupo": grupo, "grupo_slug": gslug,
            "ciudad": (str(f.get("ciudad") or "").strip()[:80] or None),
            "nombre": (str(f.get("nombre") or "").strip()[:120] or None),
            "origen": origen[:120], "valido": ok,
        }
        if ok:
            buenas.append(fila)
        else:
            malas.append({"telefono": str(f.get("telefono") or ""), "grupo": grupo, "motivo": "número que no se entiende"})
            buenas.append(fila)   # se guarda igual, marcado, para no perderlo
    return buenas, malas
