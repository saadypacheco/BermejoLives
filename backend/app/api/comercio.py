"""Panel del comercio logueado: login, publicar (chatbot) y ver mis publicaciones.

Regla de negocio clave:
  - comercio.confiable = True  -> la publicación se publica DIRECTO (estado='aprobado').
  - comercio.confiable = False -> la publicación va a la cola de moderación.
"""
import secrets
from datetime import date, datetime, timedelta, timezone

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core import auth
from app.core.config import settings
from app.core.text import slug_unico, slugify
from app.db.repository import Repo, get_repo
from app.models.schemas import LoginBody, PublicarBody
from app.services.clasificador import clasificar, generar_texto_comercio, sugerir_rubros
from app.services.imagenes import guardar_foto_local, procesar_imagen, subir_foto_comercio
from app.services.tienda_client import get_tienda_client

router = APIRouter()
logger = structlog.get_logger()

_TIPOS = {"oferta", "video", "novedad"}
_PLANES = {"gratis", "pro", "premium"}
_MODALIDADES = {"mayorista", "minorista", "ambos"}

# Campos que el comercio PUEDE editar de su propio perfil. Todo lo demás
# (verificado, confiable, plan, paga_hasta, suspendido, slug, rating) es
# administrado solo por el admin y nunca se toca desde este endpoint.
_CAMPOS_EDITABLES = {
    "nombre", "descripcion", "whatsapp", "telefono", "email",
    "facebook_url", "instagram_url", "tiktok_url", "sitio_web", "logo_url",
    "direccion", "como_llegar", "horario", "pedido_minimo", "modalidad",
    "lat", "lng",
}


@router.post("/auth/comercio/registro")
async def comercio_registro(
    nombre: str = Form(...),
    whatsapp: str = Form(...),
    modalidad: str = Form("mayorista"),
    rubro_slugs: list[str] = Form(default=[]),
    descripcion: str | None = Form(None),
    direccion: str | None = Form(None),
    lat: float = Form(...),
    lng: float = Form(...),
    foto: UploadFile = File(...),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Alta self-service: el dueño se registra a sí mismo. Sin email/contraseña —
    el comercio queda identificado por WhatsApp; para volver a entrar pide un
    código por WhatsApp (mismo mecanismo que /auth/comercio/recuperar)."""
    if modalidad not in _MODALIDADES:
        raise HTTPException(status_code=400, detail=f"modalidad inválida: {modalidad}")
    if not nombre.strip() or not whatsapp.strip():
        raise HTTPException(status_code=400, detail="Faltan nombre y/o WhatsApp")

    rubro_ids = [rid for rid in (repo.get_rubro_id(s) for s in rubro_slugs if s) if rid]
    slug = slug_unico(repo, slugify(nombre))

    data = await foto.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta la foto del negocio")
    try:
        portada_url = subir_foto_comercio(slug, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    comercio = repo.crear_comercio(
        {
            "slug": slug,
            "nombre": nombre.strip(),
            "descripcion": descripcion.strip() if descripcion and descripcion.strip() else None,
            "whatsapp": whatsapp.strip(),
            "direccion": direccion.strip() if direccion and direccion.strip() else None,
            "lat": lat,
            "lng": lng,
            "portada_url": portada_url,
            "rubro_id": rubro_ids[0] if rubro_ids else None,
            "ciudad_id": repo.get_ciudad_id("bermejo"),
            "modalidad": modalidad,
            "plan": "gratis",
            "confiable": False,            # nuevo comercio NO publica directo hasta ser verificado
            "verificado": False,
        }
    )
    if rubro_ids:
        repo.set_comercio_rubros(comercio["id"], rubro_ids)

    repo.crear_comercio_usuario({"comercio_id": comercio["id"], "nombre": nombre.strip()})

    token = auth.make_comercio_token(comercio["id"], whatsapp.strip())
    logger.info("comercio.registro", slug=slug, con_gps=True, con_foto=bool(portada_url))
    return {
        "access_token": token,
        "comercio": {
            "id": comercio["id"],
            "nombre": comercio["nombre"],
            "slug": comercio["slug"],
            "confiable": False,
        },
    }


@router.post("/auth/comercio/login")
def comercio_login(body: LoginBody, repo: Repo = Depends(get_repo)) -> dict:
    user = repo.get_comercio_usuario(body.email)
    if not user or not auth.verify_password(body.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    comercio = repo.get_comercio(user["comercio_id"])
    token = auth.make_comercio_token(user["comercio_id"], body.email)
    return {
        "access_token": token,
        "comercio": {
            "id": comercio["id"],
            "nombre": comercio["nombre"],
            "slug": comercio["slug"],
            "confiable": comercio.get("confiable", False),
        },
    }


class GenerarDescripcionBody(BaseModel):
    nombre: str
    que_vende: str
    rubros: list[dict]


@router.post("/comercio/generar-descripcion")
def comercio_generar_descripcion(body: GenerarDescripcionBody) -> dict:
    """Genera descripción + rubros sugeridos (1-3) a partir de texto libre,
    usado en el registro — misma lógica de categorías que /publicar. Si no hay
    GEMINI_API_KEY o falla, devuelve el texto tal cual y sin rubros (el
    frontend deja elegir manualmente)."""
    resultado = generar_texto_comercio(body.nombre, body.que_vende, body.rubros)
    descripcion = resultado["descripcion"] if resultado else body.que_vende
    rubro_slugs = sugerir_rubros(descripcion, body.rubros)
    return {"descripcion": descripcion, "rubro_slugs": rubro_slugs}


@router.get("/comercio/buscar")
def comercio_buscar(q: str = Query(..., min_length=2), repo: Repo = Depends(get_repo)) -> dict:
    """Búsqueda simple por nombre — usada en el flujo de "cambié de número"
    para que el dueño encuentre su negocio sin necesitar login."""
    return {"items": repo.buscar_comercios_por_nombre(q)}


@router.post("/comercio/{comercio_id}/solicitar-cambio-numero")
async def solicitar_cambio_numero(
    comercio_id: str,
    whatsapp_nuevo: str = Form(...),
    lat: float = Form(...),
    lng: float = Form(...),
    mensaje: str | None = Form(None),
    foto: UploadFile = File(...),
    repo: Repo = Depends(get_repo),
) -> dict:
    """El dueño perdió acceso a su número viejo: pide el cambio con una foto
    actual del local + su ubicación. SIEMPRE queda pendiente de un admin —
    nadie lo aprueba automático, la decisión es manual."""
    comercio = repo.get_comercio(comercio_id)
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    if not whatsapp_nuevo.strip():
        raise HTTPException(status_code=400, detail="Falta el WhatsApp nuevo")

    data = await foto.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta la foto del local")
    try:
        foto_url = subir_foto_comercio(f"cambio-numero-{comercio['slug']}", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    repo.crear_solicitud_cambio_numero({
        "comercio_id": comercio_id,
        "whatsapp_nuevo": whatsapp_nuevo.strip(),
        "foto_url": foto_url,
        "lat": lat,
        "lng": lng,
        "mensaje": mensaje.strip() if mensaje and mensaje.strip() else None,
    })
    logger.info("comercio.solicitud_cambio_numero", comercio=comercio["slug"])
    return {"ok": True}


class RecuperarBody(BaseModel):
    whatsapp: str


@router.post("/auth/comercio/recuperar")
def comercio_recuperar(body: RecuperarBody, repo: Repo = Depends(get_repo)) -> dict:
    """Genera un código para confirmar por WhatsApp entrante (no lo mandamos
    nosotros — ver docs/pendientes.md sección 0). Respuesta siempre con la
    misma forma exista o no el número (evita enumeración): si no existe, el
    código nunca va a poder confirmarse, pero el link se ve igual."""
    code = f"{secrets.randbelow(1_000_000):06d}"
    user = repo.get_comercio_usuario_por_whatsapp(body.whatsapp)
    if user:
        expira = (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat()
        repo.set_reset_code(user["id"], code, expira)
        logger.info("comercio.recuperar.solicitado", whatsapp=body.whatsapp)
    return {"ok": True, "codigo": code, "wa_link": settings.wa_link_confirmar(code)}


@router.get("/auth/comercio/recuperar/estado")
def comercio_recuperar_estado(whatsapp: str, codigo: str, repo: Repo = Depends(get_repo)) -> dict:
    """Polling: el frontend consulta esto después de mostrar el botón
    "Confirmar por WhatsApp", antes de pedir la contraseña nueva."""
    user = repo.get_comercio_usuario_por_whatsapp(whatsapp)
    confirmado = bool(user and user.get("reset_code") == codigo and user.get("reset_code_confirmado_at"))
    return {"confirmado": confirmado}


class RecuperarConfirmarBody(BaseModel):
    whatsapp: str
    codigo: str
    nueva_password: str


@router.post("/auth/comercio/recuperar/confirmar")
def comercio_recuperar_confirmar(body: RecuperarConfirmarBody, repo: Repo = Depends(get_repo)) -> dict:
    if len(body.nueva_password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")
    user = repo.get_comercio_usuario_por_whatsapp(body.whatsapp)
    if not user or not user.get("reset_code") or user["reset_code"] != body.codigo:
        raise HTTPException(status_code=400, detail="Código incorrecto")
    expira = user.get("reset_code_expira")
    if not expira or datetime.fromisoformat(expira) < datetime.now(timezone.utc):
        raise HTTPException(status_code=400, detail="El código venció, pedí uno nuevo")
    if not user.get("reset_code_confirmado_at"):
        raise HTTPException(status_code=400, detail="Todavía no confirmaste por WhatsApp")
    repo.set_password(user["id"], auth.hash_password(body.nueva_password))
    logger.info("comercio.recuperar.confirmado", whatsapp=body.whatsapp)

    comercio = repo.get_comercio(user["comercio_id"])
    token = auth.make_comercio_token(user["comercio_id"], user["email"])
    return {
        "access_token": token,
        "comercio": {
            "id": comercio["id"],
            "nombre": comercio["nombre"],
            "slug": comercio["slug"],
            "confiable": comercio.get("confiable", False),
        },
    }


@router.get("/comercio/mis-publicaciones")
def mis_publicaciones(
    claims: dict = Depends(auth.require_comercio), repo: Repo = Depends(get_repo)
) -> dict:
    items = repo.list_publicaciones_de_comercio(claims["comercio_id"])
    return {"items": items, "total": len(items)}


_PUB_EDITABLES = {
    "titulo", "descripcion", "precio", "moneda",
    "imagen_url", "tiktok_url", "descuento_pct", "vence_el",
}


class PublicacionUpdate(BaseModel):
    titulo: str | None = None
    descripcion: str | None = None
    precio: float | None = None
    moneda: str | None = None
    imagen_url: str | None = None
    tiktok_url: str | None = None
    descuento_pct: int | None = None
    vence_el: str | None = None


@router.patch("/comercio/publicaciones/{pub_id}")
def editar_publicacion(
    pub_id: str,
    body: PublicacionUpdate,
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    patch = {
        k: v for k, v in body.model_dump(exclude_unset=True).items()
        if k in _PUB_EDITABLES
    }
    if not patch:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    if patch.get("descuento_pct") is not None:
        patch["descuento_pct"] = max(1, min(99, int(patch["descuento_pct"])))

    comercio = repo.get_comercio(claims["comercio_id"])
    if not comercio:
        raise HTTPException(status_code=404, detail="comercio no encontrado")

    # Re-moderación: una edición de un comercio NO confiable vuelve a pendiente.
    now = datetime.now(timezone.utc).isoformat()
    if bool(comercio.get("confiable")):
        patch["estado"], patch["approved_at"] = "aprobado", now
    else:
        patch["estado"], patch["approved_at"] = "pendiente", None

    updated = repo.update_publicacion_de_comercio(pub_id, claims["comercio_id"], patch)
    if not updated:
        raise HTTPException(status_code=404, detail="publicación no encontrada")
    logger.info("comercio.publicacion_update", comercio=claims["comercio_id"], pub=pub_id, campos=list(patch))
    return {"ok": True, "estado": updated.get("estado"), "item": updated}


@router.delete("/comercio/publicaciones/{pub_id}")
def baja_publicacion(
    pub_id: str,
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    if not repo.baja_publicacion_de_comercio(pub_id, claims["comercio_id"]):
        raise HTTPException(status_code=404, detail="publicación no encontrada")
    logger.info("comercio.publicacion_baja", comercio=claims["comercio_id"], pub=pub_id)
    return {"ok": True}


# ---- Panel "Mi comercio": perfil, suscripción, métricas ----

# Campos que el comercio ve de su perfil (subconjunto seguro de la fila completa).
_CAMPOS_PERFIL = (
    "id", "slug", "nombre", "descripcion", "whatsapp", "telefono", "email",
    "facebook_url", "instagram_url", "tiktok_url", "sitio_web", "logo_url",
    "portada_url", "direccion", "como_llegar", "horario", "pedido_minimo",
    "modalidad", "monedas_aceptadas", "plan", "verificado", "confiable",
    "lat", "lng",
)


def _perfil_dict(repo: Repo, comercio: dict) -> dict:
    out = {k: comercio.get(k) for k in _CAMPOS_PERFIL}
    out["rubro_slugs"] = repo.get_comercio_rubros(comercio["id"])
    return out


class PerfilUpdate(BaseModel):
    nombre: str | None = None
    descripcion: str | None = None
    whatsapp: str | None = None
    telefono: str | None = None
    email: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    tiktok_url: str | None = None
    sitio_web: str | None = None
    logo_url: str | None = None
    direccion: str | None = None
    como_llegar: str | None = None
    horario: str | None = None
    pedido_minimo: str | None = None
    modalidad: str | None = None
    lat: float | None = None
    lng: float | None = None
    rubro_slugs: list[str] | None = None


@router.get("/comercio/perfil")
def get_perfil(
    claims: dict = Depends(auth.require_comercio), repo: Repo = Depends(get_repo)
) -> dict:
    comercio = repo.get_comercio(claims["comercio_id"])
    if not comercio:
        raise HTTPException(status_code=404, detail="comercio no encontrado")
    return _perfil_dict(repo, comercio)


@router.put("/comercio/perfil")
def update_perfil(
    body: PerfilUpdate,
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    campos = body.model_dump(exclude_unset=True, exclude={"rubro_slugs"})
    # Solo los campos efectivamente enviados, y solo los de la whitelist.
    patch = {k: v for k, v in campos.items() if k in _CAMPOS_EDITABLES}
    if "modalidad" in patch and patch["modalidad"] not in _MODALIDADES:
        raise HTTPException(status_code=400, detail=f"modalidad inválida: {patch['modalidad']}")
    if not patch and body.rubro_slugs is None:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    comercio = repo.update_comercio(claims["comercio_id"], patch, body.rubro_slugs)
    logger.info("comercio.perfil_update", comercio=claims["comercio_id"], campos=list(patch))
    return _perfil_dict(repo, comercio)


@router.put("/comercio/perfil/foto")
async def update_perfil_foto(
    foto: UploadFile = File(...),
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    comercio = repo.get_comercio(claims["comercio_id"])
    if not comercio:
        raise HTTPException(status_code=404, detail="comercio no encontrado")
    data = await foto.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta la foto")
    try:
        portada_url = subir_foto_comercio(comercio["slug"], data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not portada_url:
        raise HTTPException(status_code=502, detail="No se pudo subir la foto, probá de nuevo")
    updated = repo.update_comercio(claims["comercio_id"], {"portada_url": portada_url}, None)
    logger.info("comercio.perfil_foto_update", comercio=claims["comercio_id"])
    return _perfil_dict(repo, updated)


def _estado_suscripcion(comercio: dict) -> dict:
    """Resume el estado de pago para mostrárselo al comercio."""
    plan = comercio.get("plan") or "gratis"
    suspendido = bool(comercio.get("suspendido"))
    paga_hasta = comercio.get("paga_hasta")  # 'YYYY-MM-DD' | None

    dias = None
    if paga_hasta:
        try:
            dias = (date.fromisoformat(str(paga_hasta)[:10]) - date.today()).days
        except ValueError:
            dias = None

    if plan == "gratis":
        estado = "gratis"
    elif suspendido:
        estado = "suspendido"
    elif dias is None:
        estado = "sin_pago"
    elif dias < 0:
        estado = "vencido"
    elif dias <= 7:
        estado = "por_vencer"
    else:
        estado = "activo"

    return {
        "plan": plan,
        "paga_hasta": paga_hasta,
        "dias_restantes": dias,
        "suspendido": suspendido,
        "estado": estado,
    }


@router.get("/comercio/suscripcion")
def get_suscripcion(
    claims: dict = Depends(auth.require_comercio), repo: Repo = Depends(get_repo)
) -> dict:
    comercio = repo.get_comercio(claims["comercio_id"])
    if not comercio:
        raise HTTPException(status_code=404, detail="comercio no encontrado")
    sub = _estado_suscripcion(comercio)
    # Cargos acumulados por publicaciones destacadas aún no cobradas.
    # (El campo `costo`/`cobrado` llega con la migración del destacado cobrable.)
    pubs = repo.list_publicaciones_de_comercio(claims["comercio_id"])
    cargos = [
        {"id": p["id"], "titulo": p.get("titulo"), "costo": p.get("costo")}
        for p in pubs
        if p.get("costo") and not p.get("cobrado")
    ]
    sub["cargos_pendientes"] = cargos
    sub["total_cargos"] = sum(float(c["costo"]) for c in cargos)
    return sub


@router.get("/comercio/metricas")
def get_metricas(
    claims: dict = Depends(auth.require_comercio), repo: Repo = Depends(get_repo)
) -> dict:
    """Resumen para el comercio: quién lo contactó (leads) y sus publicaciones."""
    leads = repo.list_leads_by_comercio(claims["comercio_id"], 30)
    por_tipo: dict[str, int] = {}
    for lead in leads:
        t = lead.get("tipo") or "otro"
        por_tipo[t] = por_tipo.get(t, 0) + 1

    pubs = repo.list_publicaciones_de_comercio(claims["comercio_id"])
    por_estado: dict[str, int] = {}
    for p in pubs:
        e = p.get("estado") or "otro"
        por_estado[e] = por_estado.get(e, 0) + 1

    return {
        "contactos_30d": len(leads),
        "contactos_por_tipo": por_tipo,
        "publicaciones_total": len(pubs),
        "publicaciones_por_estado": por_estado,
    }


@router.post("/comercio/publicar")
def publicar(
    body: PublicarBody,
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    if body.tipo not in _TIPOS:
        raise HTTPException(status_code=400, detail=f"tipo inválido: {body.tipo}")

    comercio = repo.get_comercio(claims["comercio_id"])
    if not comercio:
        raise HTTPException(status_code=404, detail="comercio no encontrado")

    confiable = bool(comercio.get("confiable"))
    now = datetime.now(timezone.utc).isoformat()
    # Descuento/vencimiento solo aplican a ofertas; el % se acota a 1..99.
    descuento = None
    if body.tipo == "oferta" and body.descuento_pct is not None:
        descuento = max(1, min(99, int(body.descuento_pct)))
    vence = body.vence_el if (body.tipo == "oferta" and body.vence_el) else None
    row = {
        "comercio_id": comercio["id"],
        "tipo": body.tipo,
        "titulo": body.titulo,
        "descripcion": body.descripcion,
        "precio": body.precio,
        "moneda": body.moneda,
        "imagen_url": body.imagen_url,
        "tiktok_url": body.tiktok_url,
        "descuento_pct": descuento,
        "vence_el": vence,
        "origen": "panel",
        "estado": "aprobado" if confiable else "pendiente",
        "approved_at": now if confiable else None,
        "moderado_por": "auto-confiable" if confiable else None,
        "moderado_at": now if confiable else None,
    }
    pub = repo.insert_publicacion_directa(row)
    logger.info("comercio.publicar", comercio=comercio["slug"], estado=row["estado"], confiable=confiable)
    return {
        "ok": True,
        "estado": row["estado"],
        "publicado_directo": confiable,
        "publicacion": pub,
    }


# ---- Productos del marketplace (puente con el ecommerce) ----
_MONEDAS = {"ARS", "BOB", "USD"}


def _moneda_default(comercio: dict | None) -> str:
    monedas = (comercio or {}).get("monedas_aceptadas") or []
    return monedas[0] if monedas else "ARS"


def _categoria_fallback(categorias: list[dict]) -> str | None:
    slugs = [c["slug"] for c in categorias if c.get("slug")]
    if not slugs:
        return None
    return "otros" if "otros" in slugs else slugs[0]


class DraftBody(BaseModel):
    titulo: str
    descripcion: str | None = None
    precio: float | None = None
    moneda: str | None = None


@router.post("/comercio/productos/draft")
def producto_draft(
    body: DraftBody,
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Arma el borrador para el preview: la IA infiere la categoría (o fallback)."""
    if not body.titulo.strip():
        raise HTTPException(status_code=400, detail="Falta el título")
    client = get_tienda_client()
    categorias = client.list_categorias()
    slug = clasificar(body.titulo, body.descripcion, categorias) or _categoria_fallback(categorias)
    cat = next((c for c in categorias if c["slug"] == slug), None)
    comercio = repo.get_comercio(claims["comercio_id"])
    return {
        "titulo": body.titulo.strip(),
        "descripcion": (body.descripcion or "").strip() or None,
        "precio": body.precio,
        "moneda": body.moneda or _moneda_default(comercio),
        "categoria_slug": slug,
        "categoria_nombre": cat["nombre"] if cat else None,
        "categorias": categorias,   # para que el preview ofrezca cambiarla
    }


@router.get("/comercio/productos")
def list_productos(
    claims: dict = Depends(auth.require_comercio), repo: Repo = Depends(get_repo)
) -> dict:
    items = repo.list_producto_refs(claims["comercio_id"])
    return {"items": items, "total": len(items)}


@router.post("/comercio/productos")
async def crear_producto(
    titulo: str = Form(...),
    precio: float = Form(...),
    moneda: str = Form("ARS"),
    categoria_slug: str = Form(...),
    descripcion: str | None = Form(None),
    fotos: list[UploadFile] = File(default=[]),
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Confirma y publica: upsert del vendedor + alta del producto en el ecommerce + producto_ref."""
    if not titulo.strip():
        raise HTTPException(status_code=400, detail="Falta el título")
    if moneda not in _MONEDAS:
        raise HTTPException(status_code=400, detail=f"moneda inválida: {moneda}")
    if len(fotos) > 3:
        raise HTTPException(status_code=400, detail="Máximo 3 fotos por producto")

    comercio = repo.get_comercio(claims["comercio_id"])
    if not comercio:
        raise HTTPException(status_code=404, detail="comercio no encontrado")

    # Lee y procesa las fotos (valida + resize). 1–3 imágenes.
    imgs: list[bytes] = []
    for f in fotos:
        data = await f.read()
        if not data:
            continue
        try:
            imgs.append(procesar_imagen(data))
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=400, detail="Una de las fotos no es válida")

    client = get_tienda_client()
    # 1) asegurar el vendedor en el ecommerce, 2) crear el producto (en threadpool: httpx sync)
    await run_in_threadpool(client.upsert_vendedor, comercio["id"], {
        "nombre": comercio["nombre"], "slug": comercio["slug"],
        "whatsapp": comercio.get("whatsapp"), "activo": True,
        "lat": comercio.get("lat"), "lng": comercio.get("lng"),
    })
    res = await run_in_threadpool(client.crear_producto, comercio["id"], {
        "nombre": titulo.strip(), "precio": precio, "moneda": moneda,
        "categoria_slug": categoria_slug, "descripcion": (descripcion or "").strip() or None,
        "slug": comercio["slug"],
    }, imgs)

    ref = repo.crear_producto_ref({
        "comercio_id": comercio["id"],
        "tienda_producto_id": str(res.get("producto_id")) if res.get("producto_id") is not None else None,
        "url": res.get("url"),
        "foto_url": res.get("imagen_url"),   # el ecommerce devuelve la URL pública de la 1ª foto
        "titulo": titulo.strip(),
        "precio": precio,
        "moneda": moneda,
        "estado": "publicado",
        "cargado_por": claims.get("email"),
    })
    logger.info("comercio.producto_alta", comercio=comercio["slug"],
                producto=res.get("producto_id"), fotos=len(imgs), stub=client.stub)
    return {"ok": True, "producto_ref": ref, "url": res.get("url")}


@router.delete("/comercio/productos/{ref_id}")
def borrar_producto(
    ref_id: str,
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    ref = repo.get_producto_ref(ref_id)
    if not ref or ref.get("comercio_id") != claims["comercio_id"]:
        raise HTTPException(status_code=404, detail="producto no encontrado")
    if ref.get("tienda_producto_id"):
        get_tienda_client().delete_producto(ref["tienda_producto_id"])
    repo.delete_producto_ref(ref_id)
    return {"ok": True}


_DESTACADO_COSTO = 1000.0   # ARS por publicación destacada (se factura con la suscripción)


@router.post("/comercio/productos/{ref_id}/destacar")
def destacar_producto(
    ref_id: str,
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Crea una publicación destacada en el feed para este producto. Tiene COSTO,
    que se acumula y se cobra junto con la suscripción."""
    ref = repo.get_producto_ref(ref_id)
    if not ref or ref.get("comercio_id") != claims["comercio_id"]:
        raise HTTPException(status_code=404, detail="producto no encontrado")
    if ref.get("destacado_pub_id"):
        raise HTTPException(status_code=409, detail="Este producto ya está destacado")

    comercio = repo.get_comercio(claims["comercio_id"])
    confiable = bool(comercio.get("confiable"))
    now = datetime.now(timezone.utc).isoformat()
    pub = repo.insert_publicacion_directa({
        "comercio_id": comercio["id"],
        "tipo": "oferta",
        "titulo": ref.get("titulo"),
        "precio": ref.get("precio"),
        "moneda": ref.get("moneda"),
        "imagen_url": ref.get("foto_url"),
        "tiktok_url": ref.get("url"),          # link al producto en el ecommerce
        "producto_ref_id": ref_id,
        "costo": _DESTACADO_COSTO,
        "cobrado": False,
        "origen": "panel",
        "estado": "aprobado" if confiable else "pendiente",
        "approved_at": now if confiable else None,
        "moderado_por": "auto-confiable" if confiable else None,
        "moderado_at": now if confiable else None,
    })
    repo.update_producto_ref(ref_id, {"destacado_pub_id": pub["id"]})
    logger.info("comercio.destacar", comercio=comercio["slug"], ref=ref_id, estado=pub["estado"])
    return {"ok": True, "estado": pub["estado"], "costo": _DESTACADO_COSTO}


# ---- Pago QR self-service (el comercio sube su comprobante) ----
_METODOS_PAGO = {"qr-bolivia", "qr-argentina", "transferencia", "efectivo"}


def _subir_comprobante(comercio_id: str, data: bytes) -> str | None:
    """Procesa y sube el comprobante (foto) al bucket. No bloquea si falla el storage."""
    try:
        procesada = procesar_imagen(data)
    except Exception:  # noqa: BLE001
        raise HTTPException(status_code=400, detail="El comprobante no es una imagen válida")
    path = f"comprobantes/{comercio_id}/{secrets.token_hex(8)}.jpg"
    return guardar_foto_local(path, procesada)


@router.post("/comercio/pago")
async def comercio_pago(
    monto: float = Form(...),
    moneda: str = Form("ARS"),
    metodo: str = Form("qr-bolivia"),
    referencia: str | None = Form(None),
    comprobante: UploadFile | None = File(None),
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    """El comercio declara un pago con comprobante → queda PENDIENTE de confirmación del admin."""
    if monto <= 0:
        raise HTTPException(status_code=400, detail="Monto inválido")
    if metodo not in _METODOS_PAGO:
        raise HTTPException(status_code=400, detail=f"método inválido: {metodo}")

    comercio = repo.get_comercio(claims["comercio_id"])
    if not comercio:
        raise HTTPException(status_code=404, detail="comercio no encontrado")

    comprobante_url = None
    if comprobante is not None:
        data = await comprobante.read()
        if data:
            comprobante_url = _subir_comprobante(comercio["id"], data)

    pago = repo.crear_pago_pendiente(claims["comercio_id"], {
        "monto": monto, "moneda": moneda, "metodo": metodo,
        "referencia": (referencia or "").strip() or None, "comprobante_url": comprobante_url,
    })
    logger.info("comercio.pago_pendiente", comercio=comercio["slug"], monto=monto,
                metodo=metodo, con_comprobante=bool(comprobante_url))
    return {"ok": True, "estado": "pendiente", "pago_id": pago["id"]}


# ---- Mensajes (bandeja del comercio: cliente + admin) ----
class MensajeClienteBody(BaseModel):
    comercio_id: str
    nombre: str
    cuerpo: str
    contacto: str | None = None


@router.post("/mensaje")
def dejar_mensaje(body: MensajeClienteBody, repo: Repo = Depends(get_repo)) -> dict:
    """Público: un cliente le deja un mensaje al comercio desde su ficha
    (por si no tiene su WhatsApp o el comercio cambió de número)."""
    if not body.nombre.strip() or not body.cuerpo.strip():
        raise HTTPException(status_code=400, detail="Faltan nombre y mensaje")
    if not repo.get_comercio(body.comercio_id):
        raise HTTPException(status_code=404, detail="comercio no encontrado")
    repo.crear_mensaje({
        "comercio_id": body.comercio_id, "autor": "cliente",
        "nombre": body.nombre.strip(), "contacto": (body.contacto or "").strip() or None,
        "cuerpo": body.cuerpo.strip(),
    })
    return {"ok": True}


@router.get("/comercio/mensajes")
def mis_mensajes(
    claims: dict = Depends(auth.require_comercio), repo: Repo = Depends(get_repo)
) -> dict:
    items = repo.list_mensajes_de_comercio(claims["comercio_id"])
    no_leidos = sum(1 for m in items if not m.get("leido"))
    return {"items": items, "no_leidos": no_leidos}


@router.post("/comercio/mensajes/{mensaje_id}/leido")
def marcar_leido(
    mensaje_id: str,
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    m = repo.marcar_mensaje_leido(mensaje_id, claims["comercio_id"])
    if not m:
        raise HTTPException(status_code=404, detail="mensaje no encontrado")
    return {"ok": True}
