"""Normalización y validación de números de WhatsApp.

El alta de comercios es deliberadamente mínima (el agente de campo carga rápido,
a veces sin número), así que NO se valida al registrar ni al publicar. El control
entra cuando el comercio empieza a pagar: ahí el número deja de ser un dato
opcional y pasa a ser el canal por el que le llegan las reservas.

Formato destino: E.164 sin '+', que es lo que espera wa.me. Para Bolivia son
591 + 8 dígitos de celular, y los celulares arrancan con 6 o 7.
"""
from __future__ import annotations

import re

PREFIJO_BO = "591"
_LARGO_MOVIL_BO = 8
_INICIOS_MOVIL_BO = ("6", "7")

# Bermejo es frontera: hay comercios con número argentino. Para wa.me el móvil
# argentino va como 54 + 9 + área + número (10 dígitos después del 9). El "9" es
# el que marca que es celular; sin él el link no abre ningún chat.
PREFIJO_AR = "549"
_LARGO_MOVIL_AR = 10


def normalizar_whatsapp(valor: str | None, prefijo_default: str = PREFIJO_BO) -> str | None:
    """Devuelve el número en E.164 sin '+', o None si no se puede interpretar.

    Acepta lo que suele cargarse a mano: espacios, guiones, paréntesis, '+' y
    números locales sin código de país (se les antepone el prefijo default).
    """
    if not valor:
        return None
    digitos = re.sub(r"\D", "", str(valor))
    if not digitos:
        return None
    # '00591...' → '591...'
    if digitos.startswith("00"):
        digitos = digitos[2:]
    # '54' + 10 dígitos: le falta el 9 de móvil. Se agrega, porque un número
    # argentino sin el 9 produce un link de WhatsApp que no abre nada.
    if digitos.startswith("54") and not digitos.startswith(PREFIJO_AR):
        resto_ar = digitos[2:]
        if len(resto_ar) == _LARGO_MOVIL_AR:
            return PREFIJO_AR + resto_ar

    # Local sin código de país: arranca en 6 o 7 y no llega al largo de un
    # número internacional. Se le antepone el prefijo aunque le falten dígitos,
    # para que validar_whatsapp pueda decir "es un celular boliviano incompleto"
    # en vez del mensaje genérico de número internacional.
    if len(digitos) <= _LARGO_MOVIL_BO and digitos[0] in _INICIOS_MOVIL_BO:
        return prefijo_default + digitos
    return digitos


def variantes_whatsapp(valor: str | None) -> list[str]:
    """Las formas en que puede estar guardado un mismo número, la normalizada primero.

    El número público de un comercio se cargó a mano durante meses («70123456»)
    y los más nuevos vienen normalizados («59170123456»): para encontrar a
    alguien por su número hay que mirar las dos. Lista vacía si no hay número."""
    num = normalizar_whatsapp(valor)
    if not num:
        return []
    variantes = [num]
    if num.startswith(PREFIJO_BO) and len(num) == len(PREFIJO_BO) + _LARGO_MOVIL_BO:
        variantes.append(num[len(PREFIJO_BO):])
    return variantes


def whatsapp_para_guardar(valor: str | None) -> str | None:
    """El WhatsApp tal como se guarda en la ficha del comercio.

    Si el número valida, se guarda NORMALIZADO (E.164: `59170123456`): así la
    ficha «+591 7012-3456» y quien entra escribiendo «70123456» son el mismo
    número. Si no valida se guarda como vino (sin espacios de más): el alta es
    deliberadamente mínima y no se inventa un número que nadie dio. Vacío → None.
    """
    if valor is None:
        return None
    crudo = str(valor).strip()
    if not crudo:
        return None
    if validar_whatsapp(crudo) is None:
        return normalizar_whatsapp(crudo)
    return crudo


def validar_whatsapp(valor: str | None) -> str | None:
    """Devuelve un mensaje de error si el número no sirve, o None si está bien.

    Sólo valida el formato: que el número exista y que un link de wa.me armado
    con él tenga chance de abrir un chat real. No verifica que la línea exista
    (eso sólo se sabe mandando un mensaje).
    """
    if not valor or not str(valor).strip():
        return "El comercio no tiene WhatsApp cargado"

    numero = normalizar_whatsapp(valor)
    if not numero:
        return f"El WhatsApp «{valor}» no tiene dígitos válidos"

    if numero.startswith(PREFIJO_BO):
        resto = numero[len(PREFIJO_BO):]
        if len(resto) != _LARGO_MOVIL_BO:
            return (f"El WhatsApp «{valor}» no es un celular boliviano válido: "
                    f"esperaba {_LARGO_MOVIL_BO} dígitos después de {PREFIJO_BO}, tiene {len(resto)}")
        if resto[0] not in _INICIOS_MOVIL_BO:
            return (f"El WhatsApp «{valor}» no parece un celular: "
                    f"los móviles bolivianos empiezan con {' o '.join(_INICIOS_MOVIL_BO)}")
        return None

    if numero.startswith(PREFIJO_AR):
        resto = numero[len(PREFIJO_AR):]
        if len(resto) != _LARGO_MOVIL_AR:
            return (f"El WhatsApp «{valor}» no es un celular argentino válido: "
                    f"esperaba {_LARGO_MOVIL_AR} dígitos después de {PREFIJO_AR} "
                    f"(área + número), tiene {len(resto)}")
        return None

    # Otro país: no se conocen las reglas locales, sólo se chequea que sea
    # plausible como E.164 (código de país + número).
    if not 8 <= len(numero) <= 15:
        return f"El WhatsApp «{valor}» no parece un número internacional válido"
    return None
