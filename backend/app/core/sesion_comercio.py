"""La sesión de Mi comercio sigue vigente mientras la clave no cambie.

El token del comercio dura 7 días. Si la clave se roba, se cambia o se anula, un
token anterior no tiene por qué seguir sirviendo: cada cuenta (`comercio_usuarios`)
tiene una `credenciales_version` que sube cada vez que su clave se genera, se
anula o se recupera, y el token lleva la versión con la que entró (`ver`). Acá se
comparan.

  - Token sin `ver` (de antes del cambio): versión 0. Sirve hasta que venza, salvo
    que la cuenta ya haya cambiado de clave.
  - Si la cuenta no existe (un comercio sin fila en `comercio_usuarios`), no hay
    nada con que comparar y el token sigue valiendo como siempre.
  - Token de un ADMIN que entró (`adm`, `POST /admin/comercios/{id}/entrar`): no
    depende de la cuenta ni de la versión de la clave del dueño (no se compara
    nada con `comercio_usuarios`); su vigencia es la de la cuenta del PANEL del
    admin (`auth.exigir_admin_vigente`, en cada pedido). Y no sirve para lo que
    cambia quién controla la cuenta o la plata (`exigir_dueno`).
"""
from __future__ import annotations

import structlog
from fastapi import Depends, HTTPException

from app.core import auth
from app.db.repository import Repo, get_repo

logger = structlog.get_logger()

MSG_SESION_CERRADA = "Tu sesión se cerró porque cambió la clave"
MSG_NO_COMO_ADMIN = "No disponible entrando como admin"


def exigir_sesion_vigente(claims: dict, repo: Repo) -> None:
    """401 si la clave de la cuenta cambió después de que este token se emitió. Un token de admin
    (`adm`) no se compara con la cuenta del dueño: se mira la cuenta del panel del admin."""
    if "adm" in claims:
        auth.exigir_admin_vigente(claims, repo)
        return
    cuenta = repo.get_cuenta_comercio(claims["comercio_id"], claims.get("cuenta_id"))
    if not cuenta:
        return
    try:
        ver_token = int(claims.get("ver") or 0)
    except (TypeError, ValueError):
        ver_token = 0
    if int(cuenta.get("credenciales_version") or 0) > ver_token:
        raise HTTPException(status_code=401, detail=MSG_SESION_CERRADA)


def require_comercio_vigente(
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Como `require_comercio`, y además la sesión tiene que seguir vigente."""
    exigir_sesion_vigente(claims, repo)
    return claims


def quien_actua(claims: dict) -> str | None:
    """Quién hizo el cambio, para los campos que guardan autor (`cargado_por`…): el correo del ADMIN si
    entró uno (nunca se le atribuye al dueño lo que hizo el equipo), si no el correo del token."""
    return claims.get("adm") or claims.get("email")


def exigir_dueno(claims: dict) -> None:
    """403 si el token es de un admin que entró: la acción es sólo del dueño (cambia quién controla la
    cuenta o mueve plata). Los endpoints así se marcan con la dependencia `comercio._comercio_dueno`, que
    llama a esto; `tests/test_entrar_como_comercio.py` lista cuáles son para que no se olvide ninguno."""
    if claims.get("adm"):
        logger.info("comercio.accion_bloqueada_como_admin", comercio_id=claims.get("comercio_id"),
                    admin=claims.get("adm"))
        raise HTTPException(status_code=403, detail=MSG_NO_COMO_ADMIN)
