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
    # Local sin código de país: arranca en 6 o 7 y no llega al largo de un
    # número internacional. Se le antepone el prefijo aunque le falten dígitos,
    # para que validar_whatsapp pueda decir "es un celular boliviano incompleto"
    # en vez del mensaje genérico de número internacional.
    if len(digitos) <= _LARGO_MOVIL_BO and digitos[0] in _INICIOS_MOVIL_BO:
        return prefijo_default + digitos
    return digitos


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

    # Otro país: no se conocen las reglas locales, sólo se chequea que sea
    # plausible como E.164 (código de país + número).
    if not 8 <= len(numero) <= 15:
        return f"El WhatsApp «{valor}» no parece un número internacional válido"
    return None
