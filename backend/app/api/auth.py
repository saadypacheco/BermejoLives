"""Auth del panel de moderación (login simple contra credenciales de config)."""
from fastapi import APIRouter, HTTPException

from app.core import auth
from app.core.config import settings
from app.models.schemas import LoginBody

router = APIRouter()


@router.post("/auth/login")
def login(body: LoginBody) -> dict:
    # MVP: credencial única de admin desde config. En F-007 se mueve a tabla.
    if body.email != settings.admin_email or body.password != settings.admin_password:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    token = auth.make_token(body.email, rol="admin")
    return {"access_token": token, "user": {"email": body.email, "rol": "admin"}}
