"""Cuenta liviana del comprador/visitante: celular + una clave de 6 números.

La PRIMERA vez (y cuando se olvida la clave) confirma el número mandando un
WhatsApp entrante (CONFIRMAR-XXXXXX); ahí se le muestra su clave, una sola vez.
Después entra con celular + clave, sin WhatsApp de por medio.

Objetivo único: capturar el número con consentimiento para avisos/ofertas, y
permitir guardar comercios favoritos desde cualquier dispositivo. No tiene nada
que ver con las cuentas de comercio."""
import secrets
from datetime import datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel

from app.core import auth
from app.core import clave as claves
from app.core.config import settings
from app.core.ip import ip_cliente
from app.core.telefono import normalizar_whatsapp, validar_whatsapp
from app.db.repository import Repo, get_repo
from app.services import ingreso_clave

router = APIRouter()
logger = structlog.get_logger()


class SolicitarCodigoBody(BaseModel):
    whatsapp: str
    ref: str | None = None   # código de origen (referido/QR) — atribución first-touch
    # El tilde EXPLÍCITO de «quiero recibir ofertas». Sin tilde no hay
    # consentimiento: el `consentimiento_ofertas` que traía la tabla por defecto
    # no cuenta (se pensó antes de que el comprador pudiera decidir). Y con tilde
    # tampoco alcanza todavía: queda PENDIENTE hasta que el número se verifique
    # (cualquiera puede tipear el número de otro).
    consentimiento: bool = False


@router.post("/auth/usuario/solicitar-codigo")
def solicitar_codigo(body: SolicitarCodigoBody, repo: Repo = Depends(get_repo)) -> dict:
    """Crea el usuario si no existe (alta progresiva) y genera un código para
    que lo confirme mandando un WhatsApp entrante (no lo mandamos nosotros —
    ver docs/pendientes.md sección 0, evita riesgo de ban por envío saliente).

    El número se guarda en E.164 (`59170000001`): es lo que el webhook compara
    cuando llega el «CONFIRMAR-XXXXXX». Quien lo escribe sin el 591 también
    confirma."""
    if not body.whatsapp.strip():
        raise HTTPException(status_code=400, detail="Falta el número de WhatsApp")
    error = validar_whatsapp(body.whatsapp)
    if error:
        raise HTTPException(status_code=400, detail=error)
    numero = normalizar_whatsapp(body.whatsapp)
    if settings.es_numero_propio(numero):
        # Los números de URUKU nunca abren una cuenta.
        raise HTTPException(status_code=400, detail="Ese número no se puede usar para entrar")
    usuario = repo.get_usuario_por_whatsapp(numero) or repo.crear_usuario(numero, body.ref)
    # Se guarda como pendiente, atado a ESTE código: `consentimiento_en` se llena
    # recién cuando el número confirma por WhatsApp. Cada pedido lo pisa.
    repo.set_consentimiento_pendiente(usuario["id"], body.consentimiento)
    code = f"{secrets.randbelow(1_000_000):06d}"
    expira = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
    repo.set_reset_code_usuario(usuario["id"], code, expira)
    logger.info("usuario.solicitar_codigo", con_consentimiento=body.consentimiento)
    return {"ok": True, "codigo": code, "whatsapp": numero,
            "wa_link": settings.wa_link_confirmar(code, para="usuario")}


class VerificarBody(BaseModel):
    whatsapp: str
    codigo: str


@router.post("/auth/usuario/verificar")
def verificar(body: VerificarBody, request: Request, response: Response,
              repo: Repo = Depends(get_repo)) -> dict:
    """El frontend pollea esto después de mostrar el botón "Confirmar por
    WhatsApp" — falla con 400 hasta que el webhook marque el código como
    confirmado (mensaje entrante real), no alcanza con que el código matchee.

    Cada confirmación genera una clave NUEVA de 6 números (es también el camino
    de «me olvidé la clave») y la devuelve UNA vez en `clave_nueva`."""
    response.headers["Cache-Control"] = "no-store"
    usuario = None if settings.es_numero_propio(body.whatsapp) else repo.get_usuario_por_whatsapp(body.whatsapp)
    if not usuario or not usuario.get("reset_code") or usuario["reset_code"] != body.codigo:
        raise HTTPException(status_code=400, detail="Código incorrecto")
    expira = usuario.get("reset_code_expira")
    if not expira or datetime.fromisoformat(expira) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="El código venció, pedí uno nuevo")
    if not usuario.get("reset_code_confirmado_at"):
        raise HTTPException(status_code=400, detail="Todavía no confirmaste por WhatsApp")
    # Se gasta el código (y su marca temporal de «confirmado»), pero NO la prueba
    # de que el número es suyo: `verificado_en` la dejó el webhook al confirmar y
    # queda para siempre.
    repo.set_reset_code_usuario(usuario["id"], None, None)
    clave_nueva = claves.generar_clave()
    repo.set_clave_usuario(usuario["id"], claves.hash_clave(clave_nueva))
    # Probó que el número es suyo: los fallos de ese número dejan de contar.
    repo.reiniciar_fallos_clave("usuarios", (normalizar_whatsapp(usuario["whatsapp"]) or usuario["whatsapp"])[:32])

    # Una fila vieja quedó guardada sin el 591 (antes de normalizar al guardar):
    # ya probó que el número es suyo, así que se la lleva a su forma normalizada
    # (si no choca con otra fila, que lo decide el repo).
    numero = usuario["whatsapp"]
    normalizado = normalizar_whatsapp(numero)
    if normalizado and normalizado != numero and repo.normalizar_whatsapp_usuario(usuario["id"], normalizado):
        numero = normalizado

    token = auth.make_usuario_token(usuario["id"], numero)
    logger.info("usuario.verificado", usuario_id=usuario["id"], metodo="whatsapp", ip=ip_cliente(request))
    return {"access_token": token, "usuario": {"id": usuario["id"], "whatsapp": numero},
            "clave_nueva": clave_nueva}


class IngresarBody(BaseModel):
    whatsapp: str
    clave: str


@router.post("/auth/usuario/ingresar")
def ingresar(body: IngresarBody, request: Request, response: Response,
             repo: Repo = Depends(get_repo)) -> dict:
    """Entra con celular + clave de 6 números. El intento se registra en la base
    ANTES de verificar (atómico): 5 fallos en 15 minutos bloquean el número, 10 en
    24 horas anulan la clave y 20 por hora bloquean la IP; un ingreso correcto no
    borra fallos. Un número sin cuenta contesta igual que uno con otra clave
    (mismo 401, mismo bloqueo, mismo tiempo): no delata quién tiene cuenta."""
    response.headers["Cache-Control"] = "no-store"
    numero = (body.whatsapp or "").strip()
    if not numero:
        raise HTTPException(status_code=400, detail="Falta el número de WhatsApp")
    clave_num = normalizar_whatsapp(numero) or numero
    ip = ip_cliente(request)
    usuario = None if settings.es_numero_propio(numero) else repo.get_usuario_por_whatsapp(numero)
    ids = [usuario["id"]] if usuario else []

    intento = ingreso_clave.abrir_intento(repo, "usuarios", clave_num, ids, ip)

    hash_guardado = (usuario or {}).get("clave_hash")
    if not hash_guardado:
        claves.gastar_tiempo(body.clave)
    if usuario and claves.clave_coincide(body.clave, hash_guardado):
        ingreso_clave.cerrar_ok(repo, intento)
        token = auth.make_usuario_token(usuario["id"], usuario["whatsapp"])
        logger.info("usuario.ingresar.ok", usuario_id=usuario["id"], metodo="clave", ip=ip)
        return {"access_token": token, "usuario": {"id": usuario["id"], "whatsapp": usuario["whatsapp"]}}

    logger.info("usuario.ingresar.fallo", metodo="clave", ip=ip)
    ingreso_clave.cerrar_fallo(repo, "usuarios", intento, ids, ip)


@router.get("/usuario/favoritos")
def listar_favoritos(claims: dict = Depends(auth.require_usuario), repo: Repo = Depends(get_repo)) -> dict:
    items = repo.list_favoritos(claims["usuario_id"])
    return {"items": [i["comercios"] for i in items if i.get("comercios")]}


class FavoritoBody(BaseModel):
    comercio_id: str


@router.post("/usuario/favoritos")
def agregar_favorito(body: FavoritoBody, claims: dict = Depends(auth.require_usuario), repo: Repo = Depends(get_repo)) -> dict:
    repo.agregar_favorito(claims["usuario_id"], body.comercio_id)
    return {"ok": True}


@router.delete("/usuario/favoritos/{comercio_id}")
def quitar_favorito(comercio_id: str, claims: dict = Depends(auth.require_usuario), repo: Repo = Depends(get_repo)) -> dict:
    repo.quitar_favorito(claims["usuario_id"], comercio_id)
    return {"ok": True}
