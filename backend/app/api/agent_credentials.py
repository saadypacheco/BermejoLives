"""Credencial de los agentes de campo (docs/credencial-agentes.md).

Cada agente lleva una tarjeta impresa con su foto, su nombre y apellido y un QR.
El QR abre `/agentes/<token>` en uruku.bo, que le pregunta a este módulo si esa
persona es (todavía) agente de URUKU.

- Admin (permiso `equipo`): emitir, reemitir, revocar la credencial y subir la foto.
- Público: la lista de agentes (`GET /public/agents`) y la verificación de una
  credencial (`GET /public/agents/{token}`).

Lo público no devuelve nunca correo, teléfono, ids, roles ni permisos, y la lista
no devuelve el token (el token es lo que prueba la tarjeta: sólo vive en el QR y
en el panel del admin). Nada se borra: revocar es `activo=false`.
"""
import re
import secrets
from datetime import datetime, timezone
from io import BytesIO

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core import auth
from app.core.auth import require_permiso
from app.core.ip import ip_cliente
from app.db.repository import Repo, get_repo
from app.services.imagenes import guardar_foto_local, procesar_imagen

router = APIRouter()
logger = structlog.get_logger()

#: Foto de la credencial: hasta 8 MB de entrada (el tope del middleware sigue a esto).
MAX_FOTO_BYTES = 8 * 1024 * 1024
#: La foto se re-codifica a JPEG de, como mucho, 800 px de lado.
FOTO_LADO_MAX = 800
FOTO_CALIDAD = 85
FORMATOS_FOTO = {"JPEG", "PNG", "WEBP"}

#: Un token es `secrets.token_urlsafe(16)` (22 caracteres). Lo que no tiene esa
#: forma ni se consulta: se contesta el mismo 404 de siempre.
_RE_TOKEN = re.compile(r"^[A-Za-z0-9_-]{22,64}$")
_PERMISO_DE_AGENTE = "comercios.cargar"

#: Un solo cuerpo para todo token que no existe: que no se pueda distinguir
#: «nunca existió» de nada más.
_NO_ES_DE_URUKU = "Esta credencial no es de URUKU"
_SIN_CACHE = {"Cache-Control": "no-store"}


# ── helpers ───────────────────────────────────────────────────────────────────
def _usuario_o_404(repo: Repo, usuario_id: str) -> dict:
    u = repo.get_usuario_panel_por_id(usuario_id)
    if not u:
        raise HTTPException(status_code=404, detail="No existe esa persona")
    return u


def _estado(repo: Repo, usuario: dict) -> dict:
    """Lo que ve el admin de un agente: su credencial vigente (con el token, para
    armar el QR), la foto, el nombre y la ciudad. Nunca el hash de la clave."""
    cred = repo.get_credencial_vigente(usuario["id"])
    ciudad = repo.get_ciudad_por_id(usuario.get("ciudad_id")) if usuario.get("ciudad_id") else None
    return {
        "credential": ({"token": cred["token"], "issued_at": cred.get("issued_at"),
                        "scan_count": int(cred.get("scan_count") or 0),
                        "last_scan_at": cred.get("last_scan_at")} if cred else None),
        "photo_url": usuario.get("photo_url") or None,
        "nombre": usuario.get("nombre") or None,
        "apellido": usuario.get("apellido") or None,
        "ciudad_nombre": (ciudad or {}).get("nombre"),
        "activo": bool(usuario.get("activo", True)),
    }


def _es_agente(repo: Repo, roles: list[str]) -> bool:
    """¿Tiene el rol `agente` o un rol que carga comercios?"""
    if "agente" in roles:
        return True
    catalogo = {r["slug"]: r.get("permisos") or [] for r in (repo.list_roles() or [])}
    return any(_PERMISO_DE_AGENTE in catalogo.get(r, []) for r in roles)


def _fecha(valor) -> str | None:
    """`YYYY-MM-DD` de un timestamp ISO (lo único que la lista pública muestra)."""
    return str(valor)[:10] if valor else None


# ── admin ─────────────────────────────────────────────────────────────────────
@router.get("/admin/agents/{usuario_id}/credential")
def ver_credencial(usuario_id: str, _: dict = Depends(require_permiso("equipo")),
                   repo: Repo = Depends(get_repo)) -> dict:
    return _estado(repo, _usuario_o_404(repo, usuario_id))


@router.post("/admin/agents/{usuario_id}/credential")
def emitir_credencial(usuario_id: str, admin: dict = Depends(require_permiso("equipo")),
                      repo: Repo = Depends(get_repo)) -> dict:
    """Emite una credencial nueva. Si había una vigente la revoca (`reemitida`): la
    tarjeta impresa vieja deja de valer."""
    u = _usuario_o_404(repo, usuario_id)
    if not u.get("activo", True):
        raise HTTPException(status_code=400, detail="Esta persona está desactivada: no se le puede emitir credencial")
    if not _es_agente(repo, u.get("roles") or []):
        raise HTTPException(status_code=400, detail="Esta persona no es agente: no tiene el rol de agente ni un rol que cargue comercios")
    if not (u.get("nombre") or "").strip():
        raise HTTPException(status_code=400, detail="Falta el nombre: completalo en Equipo antes de emitir la credencial")
    if not (u.get("apellido") or "").strip():
        raise HTTPException(status_code=400, detail="Falta el apellido: completalo en Equipo antes de emitir la credencial")
    if not u.get("photo_url"):
        raise HTTPException(status_code=400, detail="Falta la foto: subila antes de emitir la credencial")

    previa = repo.get_credencial_vigente(usuario_id)
    token = secrets.token_urlsafe(16)          # 128 bits, 22 caracteres
    repo.emitir_credencial(usuario_id, token, admin.get("email"))
    # Nunca se loguea el token: es la credencial.
    logger.info("credencial.emitida", usuario_id=usuario_id, reemitida=bool(previa), by=admin.get("email"))
    return _estado(repo, u)


class RevocarBody(BaseModel):
    reason: str = ""
    cut_access: bool = False


@router.post("/admin/agents/{usuario_id}/credential/revoke")
def revocar_credencial(usuario_id: str, body: RevocarBody, admin: dict = Depends(require_permiso("equipo")),
                       repo: Repo = Depends(get_repo)) -> dict:
    """Da de baja la credencial vigente. Con `cut_access` además desactiva la cuenta
    del panel: el agente recibe 401 en /campo/* a más tardar en un minuto."""
    u = _usuario_o_404(repo, usuario_id)
    motivo = (body.reason or "").strip()
    if not motivo:
        raise HTTPException(status_code=400, detail="Escribí el motivo de la baja")
    if len(motivo) > 500:
        raise HTTPException(status_code=400, detail="El motivo es demasiado largo (máximo 500 caracteres)")

    revocada = repo.revocar_credencial(usuario_id, motivo, admin.get("email"))
    if not revocada and not body.cut_access:
        raise HTTPException(status_code=400, detail="Esta persona no tiene una credencial vigente")
    if revocada:
        logger.info("credencial.revocada", usuario_id=usuario_id, by=admin.get("email"),
                    cut_access=body.cut_access)
    if body.cut_access:
        repo.update_usuario_panel(usuario_id, {"activo": False}, None)
        # Este proceso lo aplica al instante; otros, en cuanto venza su minuto de caché.
        auth.reiniciar_cache_acceso(u.get("email"))
        logger.info("credencial.acceso_cortado", usuario_id=usuario_id, by=admin.get("email"))
    return {"ok": True}


def _recodificar_foto(data: bytes) -> bytes:
    """Valida que sea jpg/png/webp y la re-codifica a JPEG de hasta 800 px, sin
    EXIF (la imagen nueva no arrastra metadatos: ni GPS ni modelo de celular)."""
    from PIL import Image

    try:
        with Image.open(BytesIO(data)) as img:
            formato = img.format
    except Exception as exc:  # noqa: BLE001
        raise ValueError("El archivo no es una imagen (usá jpg, png o webp)") from exc
    if formato not in FORMATOS_FOTO:
        raise ValueError("El archivo no es una imagen (usá jpg, png o webp)")
    try:
        return procesar_imagen(data, max_side=FOTO_LADO_MAX, quality=FOTO_CALIDAD)
    except Exception as exc:  # noqa: BLE001
        raise ValueError("No se pudo leer la imagen: probá con otra foto") from exc


@router.post("/admin/agents/{usuario_id}/photo")
async def subir_foto_agente(usuario_id: str, foto: UploadFile = File(...),
                            admin: dict = Depends(require_permiso("equipo")),
                            repo: Repo = Depends(get_repo)) -> dict:
    """La foto de la credencial. El nombre del archivo es aleatorio (no el id de la
    persona) y la foto anterior queda en el disco: las tarjetas ya impresas no la usan,
    pero un caché o un enlace viejo no se rompen."""
    u = _usuario_o_404(repo, usuario_id)
    data = await foto.read(MAX_FOTO_BYTES + 1)
    if not data:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if len(data) > MAX_FOTO_BYTES:
        raise HTTPException(status_code=413, detail="La foto supera los 8 MB")
    try:
        procesada = await run_in_threadpool(_recodificar_foto, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    url = await run_in_threadpool(guardar_foto_local, f"agentes/{secrets.token_urlsafe(16)}.jpg", procesada)
    if not url:
        raise HTTPException(status_code=500, detail="No se pudo guardar la foto")
    repo.update_usuario_panel(u["id"], {"photo_url": url}, None)
    logger.info("agente.foto_subida", usuario_id=usuario_id, by=admin.get("email"))
    return {"photo_url": url}


# ── público ───────────────────────────────────────────────────────────────────
@router.get("/public/agents")
def listar_agentes(response: Response, repo: Repo = Depends(get_repo)) -> dict:
    """Los agentes de URUKU: sólo activos, con credencial vigente y foto. Sin token,
    id, correo, teléfono ni roles. Nunca devuelve cuántos son (no hay total)."""
    filas = [f for f in repo.list_agentes_publicos()
             if (f.get("nombre") or "").strip() and (f.get("apellido") or "").strip()]
    filas.sort(key=lambda f: ((f.get("ciudad_nombre") or "").casefold(),
                              (f.get("apellido") or "").casefold(), (f.get("nombre") or "").casefold()))
    response.headers["Cache-Control"] = "public, max-age=60"
    return {"items": [{
        "nombre": f["nombre"].strip(), "apellido": f["apellido"].strip(),
        "ciudad_nombre": f.get("ciudad_nombre"), "ciudad_slug": f.get("ciudad_slug"),
        "photo_url": f.get("photo_url"), "desde": _fecha(f.get("issued_at")),
    } for f in filas]}


@router.get("/public/agents/{token}")
def verificar_credencial(token: str, request: Request, response: Response,
                         repo: Repo = Depends(get_repo)) -> dict:
    """Lo que abre el QR: ¿esta persona es agente de URUKU?

    `valid`: credencial vigente y cuenta activa. `revoked`: la credencial se dio de
    baja. `inactive`: la credencial sigue viva pero la persona está desactivada.
    Cualquier token que no exista contesta el mismo 404."""
    no_existe = HTTPException(status_code=404, detail=_NO_ES_DE_URUKU, headers=_SIN_CACHE)
    if not _RE_TOKEN.match(token or ""):
        raise no_existe
    cred = repo.get_credencial_por_token(token)
    if not cred:
        raise no_existe
    u = repo.get_usuario_panel_por_id(cred["usuario_id"])
    if not u:
        raise no_existe

    if not cred.get("activo"):
        estado = "revoked"
        logger.warning("credencial.revocada_escaneada", credencial_id=cred["id"],
                       usuario_id=cred["usuario_id"], ip=ip_cliente(request))
    elif not u.get("activo", True):
        estado = "inactive"
    else:
        estado = "valid"

    try:
        repo.registrar_escaneo_credencial(cred["id"])
    except Exception as exc:  # noqa: BLE001
        # Contar el escaneo no puede romper la respuesta: es lo que la gente necesita ver.
        logger.warning("credencial.escaneo_no_registrado", error=str(exc))

    ciudad = repo.get_ciudad_por_id(u.get("ciudad_id")) if u.get("ciudad_id") else None
    response.headers["Cache-Control"] = "no-store"
    return {
        "status": estado,
        "nombre": u.get("nombre") or None,
        "apellido": u.get("apellido") or None,
        "ciudad": (ciudad or {}).get("nombre"),
        "photo_url": u.get("photo_url") or None,
        "issued_at": cred.get("issued_at"),
        "checked_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }
