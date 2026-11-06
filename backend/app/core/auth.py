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
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings
from app.core.permisos import es_del_panel, permisos_de_roles, tiene as tiene_permiso
from app.db.repository import Repo, get_repo

logger = structlog.get_logger()

_bearer = HTTPBearer(auto_error=False)

# Corte de acceso (docs/credencial-agentes.md §4): el JWT dura días, así que alguien
# dado de baja seguiría entrando hasta que venza, y un agente al que le sacaron el rol
# conservaría los permisos que el token lleva escritos. Cada pedido del panel mira el
# estado ACTUAL de la cuenta (activa + permisos) con un caché en memoria de 60 s para
# no ir a la base en cada pedido: el corte tarda como mucho ese minuto.
ACCESO_TTL_SEGUNDOS = 60
_ACCESO_MAX = 2000
#: correo -> (vence, estado). `estado` es None si no hay fila (cuenta del `.env`) o
#: {"activo": bool, "permisos": list[str]} con los permisos de sus roles HOY.
_acceso_cache: dict[str, tuple[float, dict | None]] = {}


def reiniciar_cache_acceso(email: str | None = None) -> None:
    """Vacía el caché del corte de acceso (todo, o sólo el de un correo). Se llama
    al revocar/editar —así ese proceso lo aplica al instante— y en los tests."""
    if email is None:
        _acceso_cache.clear()
    else:
        _acceso_cache.pop((email or "").strip().lower(), None)


def _estado_cuenta(repo: Repo, email: str, evento_sin_fila: str | None = None) -> dict | None:
    """El estado actual de la cuenta, cacheado `ACCESO_TTL_SEGUNDOS`.

    Si la base no contesta se respeta lo último que se sabía de esa cuenta, aunque el
    caché esté vencido (stale-if-error): una baja conocida no se reabre por una caída.
    Sin estado previo se deja pasar (`None`) y no se cachea: no se le cierra la puerta
    a todos los agentes de la calle por una falla de la base."""
    clave = (email or "").strip().lower()
    ahora = time.monotonic()
    hit = _acceso_cache.get(clave)
    if hit and hit[0] > ahora:
        return hit[1]
    try:
        fila = repo.get_acceso_usuario_panel(clave)
        estado = None
        if fila is not None:
            catalogo = {r["slug"]: r.get("permisos") or [] for r in (repo.list_roles() or [])}
            estado = {"activo": bool(fila.get("activo")),
                      "permisos": permisos_de_roles(fila.get("roles") or [], catalogo)}
    except Exception as exc:  # noqa: BLE001
        logger.warning("auth.estado_de_cuenta_no_disponible", error=str(exc), con_estado_previo=bool(hit))
        return hit[1] if hit else None
    if estado is None and evento_sin_fila:
        logger.info(evento_sin_fila, email=clave)
    if len(_acceso_cache) >= _ACCESO_MAX:
        for k in [k for k, (vence, _) in _acceso_cache.items() if vence <= ahora]:
            del _acceso_cache[k]
        if len(_acceso_cache) >= _ACCESO_MAX:
            _acceso_cache.clear()
    _acceso_cache[clave] = (ahora + ACCESO_TTL_SEGUNDOS, estado)
    return estado


def _verificar_cuenta(claims: dict, repo: Repo, agente: bool = False) -> dict | None:
    """401 si la persona fue dada de baja. Para la app de campo (`agente`) además
    exige que HOY siga teniendo el permiso de cargar comercios. Sin fila en
    `usuarios_panel` (la cuenta del `.env`) pasa. Devuelve el estado actual (o None)."""
    email = claims.get("email") or claims.get("sub") or ""
    estado = _estado_cuenta(repo, email, "auth.agente_sin_fila" if agente else None)
    if estado is None:
        return None
    if not estado["activo"] or (agente and not tiene_permiso({"permisos": estado["permisos"]}, "comercios.cargar")):
        raise HTTPException(status_code=401, detail="Tu acceso fue dado de baja")
    return estado


def _vigente_tiene(estado: dict | None, permisos: tuple[str, ...]) -> bool:
    """¿Los permisos de HOY (los de la base, no los que el token trae escritos) alcanzan? Sin estado
    (cuenta del `.env` o base caída sin dato previo) no hay nada con qué contradecir al token."""
    if estado is None:
        return True
    vigentes = {"permisos": estado["permisos"]}
    return any(tiene_permiso(vigentes, p) for p in permisos)


#: PBKDF2 de siempre: lo usan las claves de Mi comercio y del comprador (se verifican en cada ingreso).
ITERACIONES_BASE = 100_000
#: PBKDF2 de las contraseñas del PANEL (equipo): quien entra ahí tiene permisos amplios, así que su hash
#: cuesta 6 veces más. Los hashes viejos (100.000) siguen sirviendo y se pasan a éste al entrar.
ITERACIONES_PANEL = 600_000
#: Largo mínimo de una contraseña NUEVA del panel.
MIN_LARGO_CLAVE_PANEL = 12


def hash_password(password: str, salt: str | None = None, iteraciones: int = ITERACIONES_BASE) -> str:
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), iteraciones)
    return f"pbkdf2_sha256${iteraciones}${salt}${dk.hex()}"


def hash_password_panel(password: str, salt: str | None = None) -> str:
    """El hash de una contraseña del panel: PBKDF2 a `ITERACIONES_PANEL`."""
    return hash_password(password, salt, ITERACIONES_PANEL)


def iteraciones_de(stored: str | None) -> int:
    """Cuántas iteraciones de PBKDF2 tiene un hash guardado (0 si no se entiende)."""
    try:
        return int((stored or "").split("$")[1])
    except Exception:  # noqa: BLE001
        return 0


def hash_panel_desactualizado(stored: str | None) -> bool:
    """¿Este hash del panel es de los viejos (menos iteraciones que las de hoy)?"""
    return iteraciones_de(stored) < ITERACIONES_PANEL


def verify_password(password: str, stored: str) -> bool:
    # Funciona con cualquier cantidad de iteraciones: lee la del propio hash (los viejos, de 100.000,
    # y los nuevos, de 600.000, conviven).
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


def _con_permiso(creds: HTTPAuthorizationCredentials | None, permiso: str, repo: Repo,
                 agente: bool = False) -> dict:
    claims = _claims(creds)
    if not tiene_permiso(claims, permiso):
        raise HTTPException(status_code=403, detail="Tu cuenta no tiene permiso para esto")
    estado = _verificar_cuenta(claims, repo, agente)
    if not _vigente_tiene(estado, (permiso,)):
        raise HTTPException(status_code=403, detail="Tu cuenta no tiene permiso para esto")
    return claims


def require_permiso(permiso: str):
    """La guardia de un endpoint: «hace falta ESTE permiso».

    Se usa así:  _: dict = Depends(require_permiso("pagos"))
    Quién lo tiene lo decide el rol, y el rol se arma desde el panel."""
    def dep(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), repo: Repo = Depends(get_repo)) -> dict:
        return _con_permiso(creds, permiso, repo)
    return dep


def require_alguno(*permisos: str):
    """La guardia de un endpoint que sirve a más de un rol: «hace falta
    ALGUNO de estos permisos». Ej.: la lista de planes la lee quien modera y
    también quien cobra (Suscripciones asigna planes con `pagos`)."""
    def dep(creds: HTTPAuthorizationCredentials | None = Depends(_bearer), repo: Repo = Depends(get_repo)) -> dict:
        claims = _claims(creds)
        if not any(tiene_permiso(claims, p) for p in permisos):
            raise HTTPException(status_code=403, detail="Tu cuenta no tiene permiso para esto")
        estado = _verificar_cuenta(claims, repo)
        if not _vigente_tiene(estado, permisos):
            raise HTTPException(status_code=403, detail="Tu cuenta no tiene permiso para esto")
        return claims
    return dep


def require_panel(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                  repo: Repo = Depends(get_repo)) -> dict:
    """Cualquier usuario logueado en el panel, sea cual sea su rol.

    Para lo que ve TODO el equipo (el tablero de Inicio): no pide un permiso
    puntual, pide ser del panel. Un agente de campo, un comercio o un comprador
    con token válido reciben 403."""
    claims = _claims(creds)
    if not es_del_panel(claims):
        raise HTTPException(status_code=403, detail="Tu cuenta no tiene acceso al panel")
    _verificar_cuenta(claims, repo)
    return claims


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                  repo: Repo = Depends(get_repo)) -> dict:
    """Cosas de administración. Hoy es el permiso `equipo`: crear usuarios, cambiar planes, ver la plata."""
    return _con_permiso(creds, "equipo", repo)


def require_agente(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                   repo: Repo = Depends(get_repo)) -> dict:
    """La app de campo: cargar comercios desde la calle.

    Además del token mira que la cuenta siga activa Y que hoy tenga el permiso de
    cargar comercios (el del token puede estar viejo). La cuenta del `.env` no tiene
    fila: pasa."""
    return _con_permiso(creds, "comercios.cargar", repo, agente=True)


def require_publicador(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                       repo: Repo = Depends(get_repo)) -> dict:
    """El contenido del sitio: cotización, frontera, videos, redes."""
    return _con_permiso(creds, "contenido", repo)


def require_moderador(creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
                      repo: Repo = Depends(get_repo)) -> dict:
    """La cola de moderación y lo que la rodea."""
    return _con_permiso(creds, "moderar", repo)


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


def require_integracion(scope: str | None = None):
    """La guardia de la API de integración (`/v1/integration/*`): «hace falta una API key válida (con este scope)».

    `Authorization: Bearer uki_<key_id>.<secreto>`. Hace, en orden: autenticar (401), límite de 60 pedidos por
    minuto por clave (429) y comprobar el scope (403). Devuelve el `Cliente` (quién es y qué puede). Los errores
    salen con el formato del contrato (`{"error": {"code", "message", "details"}}`)."""
    def dep(request: Request, repo: Repo = Depends(get_repo)):
        from app.services import integracion

        cliente = integracion.autenticar(repo, request.headers.get("authorization"))
        integracion.limitar(cliente)
        integracion.exigir_scope(cliente, scope)
        return cliente
    return dep
