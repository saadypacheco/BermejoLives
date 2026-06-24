"""Panel del comercio logueado: login, publicar (chatbot) y ver mis publicaciones.

Regla de negocio clave:
  - comercio.confiable = True  -> la publicación se publica DIRECTO (estado='aprobado').
  - comercio.confiable = False -> la publicación va a la cola de moderación.
"""
import secrets
from datetime import date, datetime, timezone

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from app.core import auth
from app.core.config import settings
from app.core.text import slug_unico, slugify
from app.db.repository import Repo, get_repo
from app.db.session import get_supabase
from app.models.schemas import LoginBody, PublicarBody, RegistroBody
from app.services.clasificador import clasificar
from app.services.imagenes import procesar_imagen
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
}


@router.post("/auth/comercio/registro")
def comercio_registro(body: RegistroBody, repo: Repo = Depends(get_repo)) -> dict:
    """Alta self-service: crea comercio + cuenta y devuelve sesión (auto-login)."""
    if body.plan not in _PLANES:
        raise HTTPException(status_code=400, detail=f"plan inválido: {body.plan}")
    if body.modalidad not in _MODALIDADES:
        raise HTTPException(status_code=400, detail=f"modalidad inválida: {body.modalidad}")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="La contraseña debe tener al menos 6 caracteres")

    if repo.get_comercio_usuario(body.email):
        raise HTTPException(status_code=409, detail="Ya existe una cuenta con ese email")

    zona_id = repo.get_zona_id(body.zona_slug) if body.zona_slug else None
    rubro_id = repo.get_rubro_id(body.rubro_slug) if body.rubro_slug else None
    slug = slug_unico(repo, slugify(body.nombre))

    comercio = repo.crear_comercio(
        {
            "slug": slug,
            "nombre": body.nombre,
            "descripcion": body.descripcion,
            "whatsapp": body.whatsapp,
            "zona_id": zona_id,
            "rubro_id": rubro_id,
            "ciudad_id": repo.get_ciudad_id("bermejo"),
            "modalidad": body.modalidad,
            "plan": body.plan,
            "confiable": False,            # nuevo comercio NO publica directo hasta ser verificado
            "verificado": False,
        }
    )
    repo.crear_comercio_usuario(
        {
            "comercio_id": comercio["id"],
            "email": body.email,
            "password_hash": auth.hash_password(body.password),
            "nombre": body.nombre,
        }
    )

    token = auth.make_comercio_token(comercio["id"], body.email)
    logger.info("comercio.registro", slug=slug, plan=body.plan)
    return {
        "access_token": token,
        "comercio": {
            "id": comercio["id"],
            "nombre": comercio["nombre"],
            "slug": comercio["slug"],
            "confiable": False,
            "plan": body.plan,
        },
        # pro/premium quedan registrados pero el cobro real es F-007 (pagos).
        "pago_pendiente": body.plan != "gratis",
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


@router.get("/comercio/mis-publicaciones")
def mis_publicaciones(
    claims: dict = Depends(auth.require_comercio), repo: Repo = Depends(get_repo)
) -> dict:
    items = repo.list_publicaciones_de_comercio(claims["comercio_id"])
    return {"items": items, "total": len(items)}


# ---- Panel "Mi comercio": perfil, suscripción, métricas ----

# Campos que el comercio ve de su perfil (subconjunto seguro de la fila completa).
_CAMPOS_PERFIL = (
    "id", "slug", "nombre", "descripcion", "whatsapp", "telefono", "email",
    "facebook_url", "instagram_url", "tiktok_url", "sitio_web", "logo_url",
    "portada_url", "direccion", "como_llegar", "horario", "pedido_minimo",
    "modalidad", "monedas_aceptadas", "plan", "verificado", "confiable",
)


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


@router.get("/comercio/perfil")
def get_perfil(
    claims: dict = Depends(auth.require_comercio), repo: Repo = Depends(get_repo)
) -> dict:
    comercio = repo.get_comercio(claims["comercio_id"])
    if not comercio:
        raise HTTPException(status_code=404, detail="comercio no encontrado")
    return {k: comercio.get(k) for k in _CAMPOS_PERFIL}


@router.put("/comercio/perfil")
def update_perfil(
    body: PerfilUpdate,
    claims: dict = Depends(auth.require_comercio),
    repo: Repo = Depends(get_repo),
) -> dict:
    # Solo los campos efectivamente enviados, y solo los de la whitelist.
    patch = {
        k: v for k, v in body.model_dump(exclude_unset=True).items()
        if k in _CAMPOS_EDITABLES
    }
    if "modalidad" in patch and patch["modalidad"] not in _MODALIDADES:
        raise HTTPException(status_code=400, detail=f"modalidad inválida: {patch['modalidad']}")
    if not patch:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    comercio = repo.update_comercio(claims["comercio_id"], patch, None)
    logger.info("comercio.perfil_update", comercio=claims["comercio_id"], campos=list(patch))
    return {k: comercio.get(k) for k in _CAMPOS_PERFIL}


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
    row = {
        "comercio_id": comercio["id"],
        "tipo": body.tipo,
        "titulo": body.titulo,
        "descripcion": body.descripcion,
        "precio": body.precio,
        "moneda": body.moneda,
        "imagen_url": body.imagen_url,
        "tiktok_url": body.tiktok_url,
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
    try:
        path = f"comprobantes/{comercio_id}/{secrets.token_hex(8)}.jpg"
        get_supabase().storage.from_(settings.comercios_bucket).upload(
            path, procesada, {"content-type": "image/jpeg", "upsert": "true"}
        )
        return settings.public_photo_url(path)
    except Exception as exc:  # noqa: BLE001
        logger.warning("comercio.comprobante_error", error=str(exc))
        return None


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
