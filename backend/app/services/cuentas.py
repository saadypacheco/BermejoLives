"""Cuentas de Mi comercio: lo que comparten el ingreso, la recuperación, el
alta de campo y el autoregistro alrededor de la clave de 6 números y del número
de WhatsApp que puede estar en más de un comercio."""
from __future__ import annotations

from app.core import clave as claves
from app.core.config import settings
from app.core.telefono import normalizar_whatsapp, whatsapp_para_guardar


def cuentas_de_numero(repo, whatsapp: str | None) -> list[dict]:
    """Las cuentas de Mi comercio de quien tiene ese número en su ficha, en
    orden determinista. Los números de URUKU nunca abren una cuenta: es lista
    vacía, igual que un número que no es de nadie."""
    if not whatsapp or settings.es_numero_propio(whatsapp):
        return []
    return repo.list_comercio_usuarios_por_whatsapp(whatsapp)


def nueva_clave_comercio(repo, comercio_id: str, cuenta: dict | None = None,
                         reiniciar_fallos: bool = False) -> str:
    """Genera una clave nueva para la cuenta de ese comercio, la guarda (sólo el
    hash) y la devuelve UNA vez, para mostrarla.

    En un número con varios comercios la clave no puede coincidir con la de
    otro de ellos: es lo que permite que la clave identifique cuál se abre. Se
    verifica contra los hashes de las demás cuentas de ese número.

    `reiniciar_fallos` SÓLO cuando el dueño acaba de probar el número por WhatsApp
    (la confirmación): ahí los fallos de ese número quedan obsoletos. Una clave
    pedida desde adentro (`POST /comercio/clave`) NO los borra: si no, quien
    comparte el número podría limpiarse el contador pidiendo claves."""
    cuenta = cuenta or repo.asegurar_comercio_usuario(comercio_id)
    comercio = repo.get_comercio(comercio_id) or {}
    hermanas = cuentas_de_numero(repo, comercio.get("whatsapp"))
    hashes = [u.get("clave_hash") for u in hermanas if u["id"] != cuenta["id"]]
    nueva = claves.clave_distinta_de(hashes)
    repo.set_clave_comercio(cuenta["id"], claves.hash_clave(nueva))
    if reiniciar_fallos and comercio.get("whatsapp"):
        numero = normalizar_whatsapp(comercio["whatsapp"]) or comercio["whatsapp"].strip()
        repo.reiniciar_fallos_clave("comercio_usuarios", numero[:32])
    return nueva


def numero_para_cambiar(repo, comercio_id: str, nuevo: str | None) -> str | None:
    """Valida el WhatsApp NUEVO de un comercio que ya existe y lo devuelve
    listo para guardar (normalizado si valida). None = se vacía el número.

    Un número que ya es de OTRO comercio activo se rechaza (409): colgar un
    comercio del número de otro es la puerta que usaba el ataque de la clave
    (entrar con la propia y resetearle el contador a la víctima)."""
    from fastapi import HTTPException

    if nuevo is None or not str(nuevo).strip():
        return None
    guardado = whatsapp_para_guardar(nuevo) or str(nuevo).strip()
    otros = [c for c in repo.list_comercios_por_whatsapp(guardado) if c["id"] != comercio_id]
    if otros:
        raise HTTPException(status_code=409,
                            detail="Ese número ya es de otro negocio en URUKU. Revisalo antes de cambiarlo.")
    return guardado


def mismo_numero(a: str | None, b: str | None) -> bool:
    """¿Son el mismo WhatsApp, aunque estén escritos distinto?"""
    na = normalizar_whatsapp(a) if a else ""
    nb = normalizar_whatsapp(b) if b else ""
    return (na or (a or "").strip()) == (nb or (b or "").strip())
