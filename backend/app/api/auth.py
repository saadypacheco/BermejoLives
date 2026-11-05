"""El ingreso del equipo: una sola puerta para todos los roles.

Antes había tres puertas distintas —admin, publicador, agente— y cada una
comparaba contra un par correo/clave del `.env`. Ahora las tres miran primero
la tabla `usuarios_panel` (0126), donde cada persona tiene su cuenta, sus
roles y sus permisos; el `.env` queda de llave de emergencia, para el día que
alguien se deje afuera a sí mismo.
"""
import hashlib
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request

from app.core import auth
from app.core import clave as claves
from app.core.config import settings
from app.core.ip import ip_cliente
from app.core.permisos import permisos_de_roles
from app.db.repository import Repo, get_repo
from app.models.schemas import LoginBody

router = APIRouter()
logger = structlog.get_logger()

_TABLA_PANEL = "usuarios_panel"


def _id_de_intento(email: str) -> str:
    """Lo que identifica a la cuenta en `clave_fallos.numero`: un hash del correo (sin el correo
    en claro, y de un largo fijo que entra en la columna)."""
    return hashlib.sha256((email or "").strip().lower().encode()).hexdigest()[:32]


def _abrir_intento_panel(repo: Repo, email: str, ip: str, cuenta_id: str | None) -> dict:
    """Registra el intento ANTES de verificar la clave (mismo mecanismo que Mi comercio: una función
    SQL inserta y cuenta bajo lock). Con 5 fallos en 15 minutos sobre esa cuenta, o 20 en una hora
    desde esa IP, corta con 429 sin verificar nada. Cubre también la llave de emergencia del `.env`."""
    intento = repo.registrar_intento_clave(_TABLA_PANEL, _id_de_intento(email), [cuenta_id] if cuenta_id else [], ip)
    if claves.bloqueado_por_ip(intento) or claves.bloqueado_15m(intento):
        repo.resolver_intento_clave(intento["id"], "bloqueado")
        logger.info("panel.ingreso_bloqueado", ip=ip)
        raise HTTPException(status_code=429, detail=claves.MENSAJE_BLOQUEADO)
    return intento


def entrar(repo: Repo, email: str, password: str, rol_env: str | None = None, ip: str = "?") -> dict | None:
    """Valida a alguien del equipo y arma su token. `None` si no entra.

    `rol_env` es el rol que le corresponde a la cuenta del `.env` de esa
    puerta (admin en /auth/login, publicador en /auth/publicador/login…):
    sólo se usa si la persona no está en la tabla.

    Bloqueo por cuenta: 5 fallos en 15 minutos (`_abrir_intento_panel`). Un ingreso correcto no borra
    fallos previos: sólo marca su propio intento como 'ok'."""
    u = repo.get_usuario_panel(email)
    intento = _abrir_intento_panel(repo, email, ip, (u or {}).get("id"))
    r = _entrar(repo, u, email, password, rol_env)
    repo.resolver_intento_clave(intento["id"], "ok" if r else "fallo")
    return r


def _entrar(repo: Repo, u: dict | None, email: str, password: str, rol_env: str | None) -> dict | None:
    if u and auth.verify_password(password, u.get("password_hash") or ""):
        roles = u.get("roles") or []
        catalogo = {r["slug"]: r.get("permisos") or [] for r in (repo.list_roles() or [])}
        permisos = permisos_de_roles(roles, catalogo)
        ciudad = repo.get_ciudad_por_id(u.get("ciudad_id")) if u.get("ciudad_id") else None
        patch = {"ultimo_acceso": datetime.now(timezone.utc).isoformat()}
        if auth.hash_panel_desactualizado(u.get("password_hash")):
            # Acaba de comprobarse la contraseña: es el momento de pasarla al hash de hoy (600.000).
            patch["password_hash"] = auth.hash_password_panel(password)
        repo.update_usuario_panel(u["id"], patch, None)
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
            # El correo del `.env`, no el tipeado: el teclado del celular pone
            # mayúscula sola, y ese texto termina en `cargado_por` de cada alta.
            email = esperado[0].strip().lower()
            token = auth.make_token(email, rol_env)
            return {"access_token": token,
                    "user": {"email": email, "rol": rol_env, "roles": [rol_env],
                             "permisos": permisos_de_roles([rol_env])}}
    return None


@router.post("/auth/login")
def login(body: LoginBody, request: Request, repo: Repo = Depends(get_repo)) -> dict:
    """La puerta del panel. Entra cualquiera del equipo; lo que ve adentro lo
    deciden sus permisos, no esta pantalla."""
    r = entrar(repo, body.email, body.password, "admin", ip_cliente(request))
    if not r:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return r
