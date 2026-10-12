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
"""
from __future__ import annotations

from fastapi import Depends, HTTPException

from app.core import auth
from app.db.repository import Repo, get_repo

MSG_SESION_CERRADA = "Tu sesión se cerró porque cambió la clave"


def exigir_sesion_vigente(claims: dict, repo: Repo) -> None:
    """401 si la clave de la cuenta cambió después de que este token se emitió."""
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
