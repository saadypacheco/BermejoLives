"""Auth del panel: JWT HS256 self-contained + hash PBKDF2 (stdlib).

Mismo patrón que mentorcomercial: no dependemos de Supabase Auth para el
panel de moderación; el backend emite y valida sus propios tokens.
"""
import hashlib
import hmac
import secrets
import time

import jwt as pyjwt
import structlog
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.permisos import es_del_panel, permisos_de_roles, tiene as tiene_permiso
from app.db.repository import Repo, get_repo

logger = structlog.get_logger()

_bearer = HTTPBearer(auto_error=False)

# Corte de acceso del agente (docs/credencial-agentes.md §4): el JWT dura días, así
# que un agente dado de baja seguiría entrando hasta que venza. `require_agente`
# mira si su cuenta sigue activa, con un caché en memoria de 60 s para no ir a la
# base en cada pedido: el corte tarda como mucho ese minuto.
ACCESO_TTL_SEGUNDOS = 60
_ACCESO_MAX = 2000
_acceso_cache: dict[str, tuple[float, bool | None]] = {}


def reiniciar_cache_acceso(email: str | None = None) -> None:
    """Vacía el caché del corte de acceso (todo, o sólo el de un correo). Se llama
    al revocar con corte —así ese proceso lo aplica al instante— y en los tests."""
    if email is None:
        _acceso_cache.clear()
    else:
        _acceso_cache.pop((email or "").strip().lower(), None)


def _cuenta_activa(repo: Repo, email: str) -> bool | None:
    """`True`/`False` según la fila de `usuarios_panel`; `None` si no hay fila (la
    cuenta del `.env`). Cacheado `ACCESO_TTL_SEGUNDOS`."""
    clave = (email or "").strip().lower()
    ahora = time.monotonic()
    hit = _acceso_cache.get(clave)
    if hit and hit[0] > ahora:
        return hit[1]
    try:
        activa = repo.is_usuario_panel_activo(clave)
    except Exception as exc:  # noqa: BLE001
        # Si la base no contesta no se le cierra la puerta a todos los agentes de la
        # calle: se deja pasar (sin cachear) y queda en el log.
        logger.warning("auth.agente_estado_no_disponible", error=str(exc))
        return True
    if activa is None:
        logger.info("auth.agente_sin_fila", email=clave)
    if len(_acceso_cache) >= _ACCESO_MAX:
        for k in [k for k, (vence, _) in _acceso_cache.items() if vence <= ahora]:
            del _acceso_cache[k]
        if len(_acceso_cache) >= _ACCESO_MAX:
            _acceso_cache.clear()
    _acceso_cache[clave] = (ahora + ACCESO_TTL_SEGUNDOS, activa)
    return activa


def hash_password(password: str, salt: str | None = None) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return f"pbkdf2_sha256$100000${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, iters, salt, expected = stored.split("$")
        dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(iters))
        return hmac.compare_digest(dk.hex(), expected)
    except Exception:
        return False


def make_token(email: str, rol: str = "moderador", roles: list[str] | None = None,
               permisos: list[str] | None = None, ciudad_slug: str | None = None,
               nombre: str | None = None) -> str:
    """El token de alguien del equipo.

    Lleva los PERMISOS ya resueltos, no sólo el rol: así cada endpoint
    pregunta «¿puede hacer esto?» en vez de «¿es admin?», y un rol nuevo
    creado desde el panel funciona sin tocar código. `rol` sigue viajando
    para lo que todavía lo mire y para los tokens que ya están dando vuelta.
    """
    roles = roles or [rol]
    payload = {
        "sub": email,
        "email": email,
        "rol": roles[0] if roles else rol,
        "roles": roles,
        "permisos": permisos if permisos is not None else permisos_de_roles(roles),
        "exp": int(time.time()) + settings.jwt_ttl_hours * 3600,
    }
    if ciudad_slug:
        payload["ciudad"] = ciudad_slug
    if nombre:
        payload["nombre"] = nombre
    return pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def make_agente_token(email: str, ciudad_slug: str | None = None, nombre: str | None = None) -> str:
    """El token del agente de campo. Lleva SU ciudad: lo que carga nace ahí,
    sin que tenga que elegirla en el formulario (0125)."""
    return make_token(email, "agente", ciudad_slug=ciudad_slug, nombre=nombre)


def make_publicador_token(email: str) -> str:
    payload = {
        "sub": email,
        "email": email,
        "rol": "publicador",
        "exp": int(time.time()) + settings.jwt_ttl_hours * 3600,
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def make_comercio_token(comercio_id: str, email: str, cuenta_id: str | None = None,
                        ver: int | None = None) -> str:
    """El token de Mi comercio.

    Lleva `cuenta_id` y `ver` (la `credenciales_version` de esa cuenta al entrar):
    cuando la clave cambia —la genera el admin, se pide otra, se recupera por
    WhatsApp o se anula—, la versión de la cuenta sube y los tokens de antes dejan
    de servir (`core/sesion_comercio.py`). Un token sin `ver` (emitido antes de este
    cambio) cuenta como versión 0 hasta que venza."""
    payload = {
        "sub": email,
        "email": email,
        "rol": "comercio",
        "comercio_id": comercio_id,
        "exp": int(time.time()) + settings.jwt_ttl_hours * 3600,
    }
    if cuenta_id:
        payload["cuenta_id"] = str(cuenta_id)
        payload["ver"] = int(ver or 0)
    return pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def make_usuario_token(usuario_id: str, whatsapp: str) -> str:
    """Token del comprador/visitante — solo celular verificado, sin contraseña."""
    payload = {
        "sub": usuario_id,
        "whatsapp": whatsapp,
        "rol": "usuario",
        "usuario_id": usuario_id,
        "exp": int(time.time()) + 30 * 24 * 3600,  # sesión larga (30 días): no hay re-login por contraseña
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _decode(token: str) -> dict:
    return pyjwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def _claims(creds: HTTPAuthorizationCredentials | None) -> dict:
    if not creds:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        return _decode(creds.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Token inválido o expirado") from exc


def _con_permiso(creds: HTTPAuthorizationCredentials | None, permiso: str) -> dict:
    claims = _claims(creds)
    if not tiene_permiso(claims, permiso):
        raise HTTPException(status_code=403, detail="Tu cuenta no tiene permiso para esto")
    return claims


def require_permiso(permiso: str):
    """La guardia de un endpoint: «hace falta ESTE permiso».

    Se usa así:  _: dict = Depends(require_permiso("pagos"))
    Quién lo tiene lo decide el rol, y el rol se arma desde el panel."""
    def dep(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
        return _con_permiso(creds, permiso)
    return dep


def require_alguno(*permisos: str):
    """La guardia de un endpoint que sirve a más de un rol: «hace falta
    ALGUNO de estos permisos». Ej.: la lista de planes la lee quien modera y
    también quien cobra (Suscripciones asigna planes con `pagos`)."""
    def dep(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
        claims = _claims(creds)
        if not any(tiene_permiso(claims, p) for p in permisos):
            raise HTTPException(status_code=403, detail="Tu cuenta no tiene permiso para esto")
        return claims
    return dep


def require_panel(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Cualquier usuario logueado en el panel, sea cual sea su rol.

    Para lo que ve TODO el equipo (el tablero de Inicio): no pide un permiso
    puntual, pide ser del panel. Un agente de campo, un comercio o un comprador
    con token válido reciben 403."""
    claims = _claims(creds)
    if not es_del_panel(claims):
        raise HTTPException(status_code=403, detail="Tu cuenta no tiene acceso al panel")
    return claims


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Cosas de administración. Hoy es el permiso `equipo`: crear usuarios, cambiar planes, ver la plata."""
    return _con_permiso(creds, "equipo")


def require_agente(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                   repo: Repo = Depends(get_repo)) -> dict:
    """La app de campo: cargar comercios desde la calle.

    Además del token mira que la cuenta siga activa (corte de acceso). La cuenta
    del `.env` no tiene fila: pasa."""
    claims = _con_permiso(creds, "comercios.cargar")
    email = claims.get("email") or claims.get("sub") or ""
    if _cuenta_activa(repo, email) is False:
        raise HTTPException(status_code=401, detail="Tu acceso fue dado de baja")
    return claims


def require_publicador(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """El contenido del sitio: cotización, frontera, videos, redes."""
    return _con_permiso(creds, "contenido")


def require_moderador(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """La cola de moderación y lo que la rodea."""
    return _con_permiso(creds, "moderar")


def require_comercio(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Exige Bearer de un comercio logueado; devuelve sus claims (incluye comercio_id)."""
    if not creds:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        claims = _decode(creds.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Token inválido o expirado") from exc
    if claims.get("rol") != "comercio" or not claims.get("comercio_id"):
        raise HTTPException(status_code=403, detail="Requiere cuenta de comercio")
    return claims


def require_usuario(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Exige Bearer de un comprador/visitante verificado (celular + código)."""
    if not creds:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        claims = _decode(creds.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Token inválido o expirado") from exc
    if claims.get("rol") != "usuario" or not claims.get("usuario_id"):
        raise HTTPException(status_code=403, detail="Requiere cuenta de usuario")
    return claims


def mismo_email(escrito: str | None, esperado: str | None) -> bool:
    """Compara dos correos sin distinguir mayúsculas ni espacios de más.

    El teclado del celular pone mayúscula en la primera letra por su cuenta, así
    que un agente parado en la calle tipea "Agente@uruku.bo" sin darse cuenta y
    el ingreso lo rechaza. El error que ve es "credenciales incorrectas", que lo
    manda a revisar la contraseña — la parte que estaba bien.

    Los correos no distinguen mayúsculas en la práctica: nadie tiene dos cuentas
    que sólo se diferencien por eso. Comparar el texto exacto no protege nada y
    deja afuera a quien escribió bien.
    """
    return (escrito or "").strip().lower() == (esperado or "").strip().lower()
