"""El ingreso del equipo: una sola puerta para todos los roles.

Antes había tres puertas distintas —admin, publicador, agente— y cada una
comparaba contra un par correo/clave del `.env`. Ahora las tres miran primero
la tabla `usuarios_panel` (0126), donde cada persona tiene su cuenta, sus
roles y sus permisos; el `.env` queda de llave de emergencia, para el día que
alguien se deje afuera a sí mismo.
"""
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core import auth
from app.core.config import settings
from app.core.permisos import permisos_de_roles
from app.db.repository import Repo, get_repo
from app.models.schemas import LoginBody

router = APIRouter()


def entrar(repo: Repo, email: str, password: str, rol_env: str | None = None) -> dict | None:
    """Valida a alguien del equipo y arma su token. `None` si no entra.

    `rol_env` es el rol que le corresponde a la cuenta del `.env` de esa
    puerta (admin en /auth/login, publicador en /auth/publicador/login…):
    sólo se usa si la persona no está en la tabla."""
    u = repo.get_usuario_panel(email)
    if u and auth.verify_password(password, u.get("password_hash") or ""):
        roles = u.get("roles") or []
        catalogo = {r["slug"]: r.get("permisos") or [] for r in (repo.list_roles() or [])}
        permisos = permisos_de_roles(roles, catalogo)
        ciudad = repo.get_ciudad_por_id(u.get("ciudad_id")) if u.get("ciudad_id") else None
        repo.update_usuario_panel(u["id"], {"ultimo_acceso": datetime.now(timezone.utc).isoformat()}, None)
        token = auth.make_token(u["email"], roles[0] if roles else "", roles, permisos,
                                (ciudad or {}).get("slug"), u.get("nombre"))
        return {"access_token": token,
                "user": {"email": u["email"], "nombre": u.get("nombre"), "rol": roles[0] if roles else None,
                         "roles": roles, "permisos": permisos,
                         "ciudad": (ciudad or {}).get("slug"), "ciudad_nombre": (ciudad or {}).get("nombre")}}
    # La llave de emergencia del `.env`.
    if rol_env:
        esperado = {"admin": (settings.admin_email, settings.admin_password),
                    "publicador": (settings.publicador_email, settings.publicador_password),
                    "agente": (settings.agente_email, settings.agente_password)}[rol_env]
        if auth.mismo_email(email, esperado[0]) and password == esperado[1]:
            token = auth.make_token(email, rol_env)
            return {"access_token": token,
                    "user": {"email": email, "rol": rol_env, "roles": [rol_env],
                             "permisos": permisos_de_roles([rol_env])}}
    return None


@router.post("/auth/login")
def login(body: LoginBody, repo: Repo = Depends(get_repo)) -> dict:
    """La puerta del panel. Entra cualquiera del equipo; lo que ve adentro lo
    deciden sus permisos, no esta pantalla."""
    r = entrar(repo, body.email, body.password, "admin")
    if not r:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return r
