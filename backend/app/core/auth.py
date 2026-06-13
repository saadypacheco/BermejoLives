"""Auth del panel: JWT HS256 self-contained + hash PBKDF2 (stdlib).

Mismo patrón que mentorcomercial: no dependemos de Supabase Auth para el
panel de moderación; el backend emite y valida sus propios tokens.
"""
import hashlib
import hmac
import secrets
import time

import jwt as pyjwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import settings

_bearer = HTTPBearer(auto_error=False)


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


def make_token(email: str, rol: str = "moderador") -> str:
    payload = {
        "sub": email,
        "email": email,
        "rol": rol,
        "exp": int(time.time()) + settings.jwt_ttl_hours * 3600,
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def make_agente_token(email: str) -> str:
    payload = {
        "sub": email,
        "email": email,
        "rol": "agente",
        "exp": int(time.time()) + settings.jwt_ttl_hours * 3600,
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def make_comercio_token(comercio_id: str, email: str) -> str:
    payload = {
        "sub": email,
        "email": email,
        "rol": "comercio",
        "comercio_id": comercio_id,
        "exp": int(time.time()) + settings.jwt_ttl_hours * 3600,
    }
    return pyjwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def _decode(token: str) -> dict:
    return pyjwt.decode(token, settings.jwt_secret, algorithms=["HS256"])


def require_admin(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Exige Bearer válido de un moderador/admin."""
    if not creds:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        claims = _decode(creds.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Token inválido o expirado") from exc
    if claims.get("rol") not in {"admin", "moderador"}:
        raise HTTPException(status_code=403, detail="Requiere rol de moderador")
    return claims


def require_agente(creds: HTTPAuthorizationCredentials | None = Depends(_bearer)) -> dict:
    """Exige Bearer de un agente de campo (o admin)."""
    if not creds:
        raise HTTPException(status_code=401, detail="No autenticado")
    try:
        claims = _decode(creds.credentials)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Token inválido o expirado") from exc
    if claims.get("rol") not in {"agente", "admin"}:
        raise HTTPException(status_code=403, detail="Requiere cuenta de agente de campo")
    return claims


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
