"""Modo agente de campo: alta rápida de comercios durante el recorrido.

El agente (un colaborador de confianza) carga nombre + celular + rubro +
modalidad, comparte el GPS y saca una foto del local. El comercio entra
'pendiente de verificar' (verificado=false), listo para que un moderador lo
confirme. La foto va a Supabase Storage (bucket público 'comercios').
"""
import httpx
import structlog
import re
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, Request
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from app.core import auth
from app.core.codigo import sin_codigo
from app.core.config import settings
from app.core.telefono import whatsapp_para_guardar
from app.core.text import limpiar_ref, slug_unico, slugify
from app.db.repository import Repo, get_repo
from app.models.schemas import LoginBody
from app.services.clasificador import sugerir_rubros
from app.services.imagenes import subir_foto_comercio, subir_foto_galeria, subir_video_comercio
from app.services import cargas, planes, que_hay_aca
from app.services import calles_mapa
from app.services import enlaces
from app.services import fotos_galeria, portada
from app.services import ficha_catalogo as catalogo_svc
from app.services.cuentas import nueva_clave_comercio
from app.services.rubros import aplicar_rubros

router = APIRouter()
logger = structlog.get_logger()

_MODALIDADES = {"mayorista", "minorista", "ambos"}
# "mapa" = tocó "Cómo llegar". Es contacto igual que el WhatsApp: nadie pide
# indicaciones para un local al que no piensa ir. Sin esto, el 400 del tipo
# desconocido se comía la métrica en silencio — `registrarLead` es
# fire-and-forget y no mira la respuesta.
# "reserva" = mandó una reserva por WhatsApp desde el carrito. Es el contacto
# que más vale: no preguntó, pidió algo concreto. Es LA métrica que
# justifica un plan pago, así que va contada aparte del WhatsApp suelto.
_TIPOS_LEAD  = {"whatsapp", "telefono", "email", "web", "vista", "mapa", "reserva"}


@router.post("/auth/campo/login")
def campo_login(body: LoginBody, repo: Repo = Depends(get_repo)) -> dict:
    """Entra un agente de campo.

    La misma puerta que el panel (0126): la cuenta está en `usuarios_panel`
    con el rol «agente» y su ciudad. La cuenta del `.env` queda de respaldo —
    es la que está en los teléfonos desde el principio."""
    from app.api.auth import entrar

    r = entrar(repo, body.email, body.password, "agente")
    if not r:
        raise HTTPException(status_code=401, detail="Credenciales incorrectas")
    return {**r, "agente": r["user"]}


@router.post("/campo/transcribir")
async def transcribir(
    audio: UploadFile = File(...),
    _agente: dict = Depends(auth.require_agente),
) -> dict:
    """Audio del '¿qué vende?' → texto. OpenAI si hay key; si no, faster-whisper local."""
    data = await audio.read()
    if not data:
        raise HTTPException(status_code=400, detail="Audio vacío")
    if len(data) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio demasiado largo")

    # Self-hosted (gratis) cuando no hay key de OpenAI
    if not settings.openai_api_key:
        from starlette.concurrency import run_in_threadpool
        from app.services.transcription import transcribir_local
        try:
            texto = await run_in_threadpool(transcribir_local, data)
        except Exception as exc:  # noqa: BLE001
            logger.warning("transcribir.local_error", error=str(exc))
            raise HTTPException(status_code=502, detail="No se pudo transcribir") from exc
        return {"texto": texto}

    # OpenAI Whisper API
    files = {"file": (audio.filename or "audio.webm", data, audio.content_type or "audio/webm")}
    form = {"model": "whisper-1", "language": "es"}
    try:
        async with httpx.AsyncClient(timeout=60) as client:
            r = await client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                data=form, files=files,
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("transcribir.error", error=str(exc))
        raise HTTPException(status_code=502, detail="No se pudo transcribir") from exc
    if r.status_code != 200:
        logger.warning("transcribir.api", status=r.status_code, body=r.text[:200])
        raise HTTPException(status_code=502, detail="No se pudo transcribir")
    return {"texto": (r.json().get("text") or "").strip()}


class SugerirRubrosBody(BaseModel):
    descripcion: str
    rubros: list[dict]


@router.post("/campo/sugerir-rubros")
def campo_sugerir_rubros(body: SugerirRubrosBody, _agente: dict = Depends(auth.require_agente)) -> dict:
    """A partir del audio transcripto (o texto escrito), sugiere rubros para
    que el agente no tenga que elegirlos a mano."""
    return {"rubro_slugs": sugerir_rubros(body.descripcion, body.rubros)}


_MAX_FOTO_BYTES = 15 * 1024 * 1024  # 15 MB de entrada


def _subir_foto(slug: str, foto: UploadFile, data: bytes) -> tuple[str | None, str | None]:
    """Sube la portada y devuelve (url_grande, url_thumb)."""
    if len(data) > _MAX_FOTO_BYTES:
        raise HTTPException(status_code=413, detail="La foto supera los 15 MB")
    try:
        return subir_foto_galeria(slug, data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


_RE_ALTA_UID = re.compile(r"^[A-Za-z0-9_.:\-]{1,64}$")


def _alta_uid_valido(valor: str | None) -> str | None:
    """El `alta_uid` limpio, o None si no vino. 400 si es más largo que 64 o trae caracteres raros."""
    if valor is None or not valor.strip():
        return None
    limpio = valor.strip()
    if not _RE_ALTA_UID.match(limpio):
        raise HTTPException(status_code=400, detail="alta_uid inválido (hasta 64 letras, números, guion, punto o dos puntos)")
    return limpio


def _es_alta_uid_repetido(exc: Exception) -> bool:
    texto = str(exc)
    return ("23505" in texto or "duplicate key" in texto.lower()) and "alta_uid" in texto


def _clave_nueva_del_alta(repo: Repo, comercio: dict) -> str | None:
    """Crea la cuenta si falta y genera la clave (la anterior, si había, queda invalidada).
    None si no se pudo: el dueño entra por «me olvidé» con su WhatsApp."""
    try:
        cuenta = repo.asegurar_comercio_usuario(comercio["id"])
        return nueva_clave_comercio(repo, comercio["id"], cuenta)
    except Exception:  # noqa: BLE001
        logger.warning("campo.alta_sin_cuenta", comercio=comercio["id"], exc_info=True)
        return None


def _alta_repetida(repo: Repo, previo: dict, response: Response | None, con_video: bool, agente: dict) -> dict:
    """El reintento de un alta ya cargada: no se crea nada, se devuelve el comercio y una
    clave NUEVA (la del primer intento queda invalidada)."""
    if previo.get("activo") is False:
        raise HTTPException(status_code=409, detail="Ese alta ya se cargó y el comercio fue dado de baja. Avisale al equipo.")
    clave = _clave_nueva_del_alta(repo, previo)
    try:
        rubros = len(repo.get_comercio_rubros(previo["id"]))
    except Exception:  # noqa: BLE001
        rubros = 0
    logger.info("campo.alta_repetida", comercio=previo.get("slug"), cargado_por=agente.get("email"))
    if response is not None:
        response.headers["Cache-Control"] = "no-store"
    return {"ok": True, "repetida": True,
            "comercio": {"id": previo["id"], "nombre": previo.get("nombre"), "slug": previo.get("slug"),
                         "ciudad": None, "rubros": rubros, "foto": bool(previo.get("portada_url")),
                         "gps": previo.get("lat") is not None, "video": con_video},
            "clave": clave, "clave_inicial": clave}


@router.post("/campo/comercio")
async def alta_campo(
    request: Request,
    nombre: str = Form(""),
    whatsapp: str | None = Form(None),
    telefono: str | None = Form(None),
    ciudad_slug: str = Form("bermejo"),           # ciudad donde está el negocio
    rubro_slugs: list[str] = Form(default=[]),    # uno o varios rubros
    modalidad: str = Form("mayorista"),
    direccion: str | None = Form(None),
    lugar_id: str | None = Form(None),            # si está DENTRO de un mercado/galería
    puesto: str | None = Form(None),              # N° de puesto/local dentro del lugar
    prod_obs_human: str | None = Form(None),   # lo que VE el agente. Opcional: si no, lo detecta la IA de las fotos.
    email: str | None = Form(None),
    tiktok_url: str | None = Form(None),
    facebook_url: str | None = Form(None),
    instagram_url: str | None = Form(None),
    sitio_web: str | None = Form(None),
    video_url: str | None = Form(None),
    lat: float | None = Form(None),
    lng: float | None = Form(None),
    consentimiento: bool = Form(False),  # nunca se presume: el agente tilda la casilla delante del dueño
    # Campos del diferencial fronterizo
    monedas_aceptadas: list[str] = Form(default=[]),
    envios_internacionales: bool = Form(False),
    origen_importacion: list[str] = Form(default=[]),
    pedido_minimo: str | None = Form(None),
    tiene_factura: bool = Form(False),
    horario: str | None = Form(None),
    tiene_stock: bool = Form(True),
    # Hora del celular al tocar «Guardar» (ISO 8601). Lo cargado sin señal llega
    # horas después: sin esto, «cuándo cargó» sería «cuándo volvió la señal».
    capturado_en: str | None = Form(None),
    # Identificador del alta, generado en el celular al tocar «Guardar» (≤ 64 caracteres).
    # La cola offline reintenta el mismo POST si se corta la señal a mitad; sin esto, un
    # reintento duplicaba el comercio. Con el mismo `alta_uid` del mismo agente no se
    # crea otro: se devuelve el que ya está, con una clave NUEVA (la del primer intento,
    # que el agente nunca llegó a ver, queda invalidada).
    alta_uid: str | None = Form(None),
    foto: UploadFile | None = File(None),
    response: Response = None,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    if modalidad not in _MODALIDADES:
        raise HTTPException(status_code=400, detail=f"modalidad inválida: {modalidad}")
    if lat is None or lng is None:
        # Qué llegó DE VERDAD. La cola offline del celular ya informa qué mandó;
        # sin esto no hay forma de comparar las dos puntas, y quedan altas de
        # campo trabadas con un error que apunta al dato equivocado: si el
        # cuerpo llega incompleto, TODOS los campos quedan vacíos y el primer
        # control que se cruza es el de la ubicación.
        try:
            recibidos = sorted((await request.form()).keys())
        except Exception:  # noqa: BLE001
            recibidos = ["(no se pudo leer el formulario)"]
        logger.warning(
            "campo.alta_sin_ubicacion",
            campos_recibidos=recibidos,
            content_type=(request.headers.get("content-type") or "")[:90],
            largo=request.headers.get("content-length"),
            agente=agente.get("email"),
        )
        raise HTTPException(status_code=400, detail="Falta la ubicación")
    # Las redes y el sitio se validan ANTES de guardar la foto: un enlace con
    # `javascript:` termina en el href de la ficha pública.
    try:
        enlaces.validar_redes({"tiktok_url": tiktok_url, "facebook_url": facebook_url,
                               "instagram_url": instagram_url, "sitio_web": sitio_web})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    # ¿Es el reintento de un alta que ya se cargó? Se mira ANTES de subir la foto.
    alta_uid = _alta_uid_valido(alta_uid)
    if alta_uid:
        previo = repo.get_comercio_por_alta_uid(agente["email"], alta_uid)
        if previo:
            return _alta_repetida(repo, previo, response, bool(video_url and video_url.strip()), agente)
    # Alta mínima: solo la ubicación es obligatoria; whatsapp/teléfono/descripción/foto opcionales.
    # La ciudad la deciden las COORDENADAS, no el selector: un comercio está
    # donde está, y así nadie carga treinta locales en la ciudad equivocada
    # por un desplegable que quedó como estaba. Si el punto no cae cerca de
    # ninguna ciudad activa, manda la ciudad del agente (0125) y, si tampoco
    # tiene, lo que vino del formulario.
    cercana = repo.ciudad_mas_cercana(lat, lng) or {}
    ciudad_slug = cercana.get("slug") or agente.get("ciudad") or ciudad_slug
    ciudad_id = cercana.get("id") or repo.get_ciudad_id(ciudad_slug) or repo.get_ciudad_id("bermejo")

    # rubros: resuelve los slugs a ids; el 1º es el principal
    rubro_ids = [rid for rid in (repo.get_rubro_id(s) for s in rubro_slugs if s) if rid]

    # SIN NOMBRE NO ES UN ERROR. En Bermejo la mayoría de los puestos no tiene
    # cartel, y llamarlos "Comercio 437" no le dice nada a nadie: 555 de 1.248
    # terminaron así. Cuando no viene nombre se marca `sin_cartel` y la base lo
    # arma sola con lo que vende y dónde está —"Ropa femenina · Calle 23 de
    # Marzo"— y lo mantiene al día si cambia el rubro o la calle (0129).
    sin_cartel = not (nombre and nombre.strip())
    nombre_final = nombre.strip() if not sin_cartel else None

    # El slug igual necesita algo legible ANTES de insertar (la foto se sube con
    # él). Sin nombre usa el rubro: el slug es la URL y no se vuelve a tocar,
    # así que no puede depender de un campo que todavía no existe.
    rubro_util = next((s for s in rubro_slugs if s and s != "otros"), None)
    base_slug = nombre_final or (repo.get_rubro_nombre(rubro_util) if rubro_util else None) or "comercio"
    slug = slug_unico(repo, slugify(base_slug))

    portada_url, portada_thumb = None, None
    if foto is not None:
        data = await foto.read()
        if data:
            # Pillow (decodificar, achicar, recomprimir) es CPU: fuera del event loop.
            portada_url, portada_thumb = await run_in_threadpool(_subir_foto, slug, foto, data)

    def _none(v: str | None) -> str | None:
        return v.strip() if v and v.strip() else None

    # La hora del celular sólo se guarda si es creíble: entre hace 7 días y
    # dentro de 5 minutos. Un reloj mal puesto no puede mover la carga a otro mes.
    capturado_dt = cargas.parse_ts(capturado_en)
    if not cargas.capturado_valido(capturado_dt):
        if capturado_en and capturado_en.strip():
            logger.warning("campo.capturado_en_descartado", capturado_en=capturado_en.strip()[:40],
                           entendida=capturado_dt is not None, agente=agente.get("email"))
        capturado_dt = None

    fila = {
        "slug": slug,
        # None y `sin_cartel` juntos: el trigger de la 0129 lo completa
        # antes de que la columna `not null` se entere.
        "nombre": nombre_final,
        "sin_cartel": sin_cartel,
        "prod_obs_human": _none(prod_obs_human),
        "whatsapp": whatsapp_para_guardar(whatsapp),
        "telefono": _none(telefono),
        "email": _none(email),
        "tiktok_url": _none(tiktok_url),
        "facebook_url": _none(facebook_url),
        "instagram_url": _none(instagram_url),
        "sitio_web": _none(sitio_web),
        "rubro_id": rubro_ids[0] if rubro_ids else None,
        "ciudad_id": ciudad_id,
        "modalidad": modalidad,
        "direccion": _none(direccion),
        "lugar_id": _none(lugar_id),
        "puesto": _none(puesto),
        "lat": lat,
        "lng": lng,
        "portada_url": portada_url,
        "portada_thumb_url": portada_thumb,
        "plan": "gratis",
        "confiable": False,
        "verificado": False,
        # Campos fronterizos
        "monedas_aceptadas": [m for m in monedas_aceptadas if m] or [],
        "envios_internacionales": envios_internacionales,
        "origen_importacion": [o for o in origen_importacion if o] or [],
        "pedido_minimo": _none(pedido_minimo),
        "tiene_factura": tiene_factura,
        "horario": _none(horario),
        "tiene_stock": tiene_stock,
        "fuente": "campo",
        "cargado_por": agente["email"],
        # La casilla «El dueño aceptó aparecer» del alta: antes sólo iba al log.
        # Queda guardada con la hora, para poder responder si alguien pregunta.
        "consentimiento_dueno": bool(consentimiento),
        "consentimiento_dueno_en": datetime.now(timezone.utc).isoformat(),
    }
    if capturado_dt:
        fila["capturado_en"] = capturado_dt.isoformat()
    if alta_uid:
        fila["alta_uid"] = alta_uid
    try:
        comercio = repo.crear_comercio(fila)
    except Exception as exc:  # noqa: BLE001
        # Dos reintentos del mismo alta en paralelo: el índice único (cargado_por, alta_uid)
        # frena al segundo. El comercio ya está: se devuelve ése.
        if alta_uid and _es_alta_uid_repetido(exc):
            previo = repo.get_comercio_por_alta_uid(agente["email"], alta_uid)
            if previo:
                return _alta_repetida(repo, previo, response, bool(video_url and video_url.strip()), agente)
        # El celular manda la hora SIEMPRE (también lo que ya estaba en cola).
        # Si el backend sube antes que la 0138, o PostgREST no recargó el
        # esquema, el insert falla por la columna que no conoce, y sin esto
        # TODAS las altas de campo darían 500 y la cola no subiría nunca. Se
        # pierde la hora del celular, no el comercio.
        if "capturado_en" not in fila or "capturado_en" not in str(exc):
            raise
        logger.error("campo.capturado_en_sin_columna", error=str(exc)[:200], agente=agente.get("email"))
        fila.pop("capturado_en")
        comercio = repo.crear_comercio(fila)
    # Los rubros se deducen de nombre + productos + descripción y se suman a los
    # que el agente haya elegido. En la calle no se eligen rubros: se anota lo que
    # se ve, y de ahí sale la categoría.
    aplicar_rubros(repo, comercio, rubro_slugs)
    calles_mapa.invalidar(comercio.get("ciudad_id") or fila.get("ciudad_id"))   # el mapa de calles cuenta este comercio

    # La cuenta de Mi comercio, igual que al pagar (`asegurar_comercio_usuario`).
    # Sin esto el comercio cargado en la calle no podía entrar jamás: la
    # recuperación por WhatsApp busca justamente esa fila. Si falla no se cae el
    # alta (el agente está en la calle, sin señal): la recuperación la crea al
    # vuelo si falta.
    #
    # Y su CLAVE (`PREFIJO-AZAR`, docs/clave-automatica.md): la app del agente la
    # muestra UNA vez, para dársela en mano en un papel aparte. Nunca va en el
    # volante ni en un WhatsApp, ni a un log. Se genera DESPUÉS de los rubros: en
    # un local sin cartel el prefijo sale de lo que vende. Si no se pudo crear la
    # cuenta, no hay clave que dar (`None`): entra por «me olvidé» con el WhatsApp.
    clave = _clave_nueva_del_alta(repo, comercio)

    # video (link TikTok) opcional → publicación pendiente tipo video
    vurl = _none(video_url)
    if vurl:
        pub_video = repo.insert_publicacion_directa({
            "comercio_id": comercio["id"], "tipo": "video", "titulo": nombre_final,
            "tiktok_url": vurl, "estado": "pendiente", "origen": "panel",
        })
        # El comercio es nuevo y tiene una sola publicación, así que el tope
        # nunca archiva nada acá; se llama igual para que el tope rija en TODOS
        # los caminos y no dependa de que alguien recuerde cuáles faltan. Sin
        # cuota ni cobro: lo sube URUKU, no el comerciante.
        if pub_video.get("id"):
            planes.archivar_excedentes(repo, comercio)

    logger.info("campo.alta", slug=slug, ciudad=ciudad_slug, rubros=len(rubro_ids),
                con_foto=bool(portada_url), con_gps=lat is not None, con_video=bool(vurl),
                consentimiento=consentimiento, cargado_por=agente["email"])
    if response is not None:
        response.headers["Cache-Control"] = "no-store"
    # El código URUKU-XXXX NO va acá: es sólo del admin (docs/clave-automatica.md).
    # Lo que se le da en mano al dueño es la CLAVE, y ésta es la única vez que se ve.
    return {"ok": True, "comercio": {"id": comercio["id"], "nombre": comercio["nombre"], "slug": slug,
                                     "ciudad": ciudad_slug, "rubros": len(rubro_ids),
                                     "foto": bool(portada_url), "gps": lat is not None,
                                     "video": bool(vurl)},
            # La clave que se le da en mano al dueño, UNA vez (`PREFIJO-AZAR`). Sólo en
            # la raíz (nunca dentro de `comercio`) y con `no-store`: que no quede en
            # ningún caché. `clave_inicial` es el nombre de antes: mismo valor.
            "clave": clave,
            "clave_inicial": clave}


class LugarBody(BaseModel):
    nombre: str
    tipo: str = "mercado"
    ciudad_slug: str = "bermejo"
    lat: float | None = None
    lng: float | None = None


@router.get("/campo/lugares")
def listar_lugares(
    ciudad_slug: str = "bermejo",
    _agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Mercados/galerías/paseos para el selector del alta (elegir dónde está el puesto)."""
    ciudad_id = repo.get_ciudad_id(ciudad_slug) or repo.get_ciudad_id("bermejo")
    return {"items": repo.list_lugares(ciudad_id)}


@router.post("/campo/lugares")
def crear_lugar(
    body: LugarBody,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Crea un mercado/galería en el momento (el agente lo carga la 1ª vez que lo encuentra)."""
    nombre = (body.nombre or "").strip()
    if not nombre:
        raise HTTPException(status_code=400, detail="Falta el nombre del lugar")
    ciudad_id = repo.get_ciudad_id(body.ciudad_slug) or repo.get_ciudad_id("bermejo")
    lugar = repo.crear_lugar({
        "nombre": nombre, "tipo": body.tipo or "mercado", "ciudad_id": ciudad_id,
        "lat": body.lat, "lng": body.lng,
    })
    logger.info("campo.lugar_creado", lugar=lugar["id"], nombre=nombre, by=agente["email"])
    return {"ok": True, "lugar": lugar}


class LugarEditBody(BaseModel):
    nombre: str | None = None
    tipo: str | None = None


@router.patch("/campo/lugares/{lugar_id}")
def editar_lugar(
    lugar_id: str,
    body: LugarEditBody,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Corrige el nombre/tipo de un mercado/galería (ej. arreglar un typo)."""
    patch: dict = {}
    if body.nombre is not None and body.nombre.strip():
        patch["nombre"] = body.nombre.strip()
    if body.tipo is not None and body.tipo.strip():
        patch["tipo"] = body.tipo.strip()
    if not patch:
        raise HTTPException(status_code=400, detail="Nada para actualizar")
    return {"ok": True, "lugar": repo.update_lugar(lugar_id, patch)}


@router.post("/campo/lugares/{lugar_id}/portada")
async def lugar_portada(
    lugar_id: str,
    foto: UploadFile = File(...),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Sube/reemplaza la foto de portada del lugar (el agente, parado ahí)."""
    data = await foto.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta la foto")
    try:
        url, thumb = await run_in_threadpool(subir_foto_galeria, f"lugares/{lugar_id}", data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"ok": True, "lugar": repo.update_lugar(lugar_id, {"portada_url": url, "portada_thumb_url": thumb})}


@router.post("/campo/lugares/{lugar_id}/video")
async def lugar_video(
    lugar_id: str,
    video: UploadFile = File(...),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Sube el video de recorrido del lugar (crudo, se sirve por /fotos)."""
    if not (video.content_type or "").startswith("video/"):
        raise HTTPException(status_code=400, detail="El archivo no es un video")
    data = await video.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta el video")
    url = subir_video_comercio(f"lugares/{lugar_id}", data, video.content_type)
    return {"ok": True, "lugar": repo.update_lugar(lugar_id, {"video_url": url})}


def _ciudad_del_agente(repo: Repo, agente: dict) -> str | None:
    """La ciudad que tiene asignada, que el token ya trae (`make_agente_token`)."""
    slug = (agente.get("ciudad") or "").strip()
    return repo.get_ciudad_id(slug) if slug else None


@router.get("/campo/mis-comercios")
def mis_comercios(agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    """Los comercios de SU CIUDAD, no sólo los que cargó él.

    Antes devolvía únicamente los propios, y eso rompía dos cosas en la calle:

      · Parado en una cuadra, el agente no podía ver si el local de enfrente ya
        estaba cargado. Entonces lo cargaba de nuevo, y quedaban dos fichas del
        mismo negocio — cosa que recién se descubre mirando el panel.

      · No podía mostrarle al comerciante lo que URUKU ya tiene de él, que es
        justo con lo que arranca la conversación de venta.

    Con dos agentes por ciudad el problema se duplica. La ciudad es la unidad
    de trabajo, no el agente: por eso se ve todo lo de la ciudad y se puede
    corregir todo lo de la ciudad.
    """
    # LO SUYO SIEMPRE, ESTÉ DONDE ESTÉ. Lo que él cargó va primero y sin
    # importar la ciudad: un agente de Santa Cruz que carga parado en Bermejo
    # —de visita, probando, o porque cruzó— archiva ese comercio en Bermejo,
    # que es lo correcto… y acto seguido desaparecía de su lista. El que acaba
    # de cargar algo tiene que verlo: si no, parece que no se guardó, y encima
    # no puede completarle la segunda pasada.
    propios = repo.list_comercios_por_agente(agente["email"])
    ciudad_id = _ciudad_del_agente(repo, agente)
    if not ciudad_id:
        logger.warning("campo.agente_sin_ciudad", agente=agente.get("email"))
        return {"items": [sin_codigo(c) for c in que_hay_aca.enriquecer(repo, propios)], "ciudad": None}

    # Los de su ciudad, más los propios de afuera. Sin repetir: los suyos que
    # SON de su ciudad ya vienen en la primera lista.
    de_la_ciudad = repo.list_comercios_de_ciudad(ciudad_id)
    vistos = {c["id"] for c in de_la_ciudad}
    afuera = [c for c in propios if c["id"] not in vistos]
    # Cada comercio suma `estado_plan`, `fotos_count` y `rubro_slug` (docs/que-hay-aca.md); las
    # fotos se cuentan en UNA consulta para toda la lista, y sin precios ni `paga_hasta`.
    items = que_hay_aca.enriquecer(repo, afuera + de_la_ciudad)
    return {"items": [sin_codigo(c) for c in items], "ciudad": agente.get("ciudad"),
            "propios_de_otra_ciudad": len(afuera)}


@router.get("/campo/planes")
def planes_pagos(_agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    """Los planes de pago activos, SÓLO nombre y slug: para «Le interesa un plan».
    Los precios no salen en la app del agente (están en la guía de venta)."""
    pagos = [p for p in repo.list_planes() if _es_plan_pago(p)]
    return {"items": [{"slug": p["slug"], "nombre": p.get("nombre") or p["slug"]} for p in pagos]}


def _es_plan_pago(plan: dict | None) -> bool:
    """Plan de pago = `precio_mes > 0` (la misma definición que la estrella, migración 0143)."""
    try:
        return float((plan or {}).get("precio_mes") or 0) > 0
    except (TypeError, ValueError):
        return False


@router.get("/campo/ejemplos")
def ejemplos_de_la_ciudad(
    rubro: str | None = Query(default=None, max_length=80, description="slug del rubro a preferir"),
    excluir: str | None = Query(default=None, max_length=64, description="id del comercio abierto"),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Hasta 3 comercios COMPLETOS de la ciudad del agente para mostrarle al dueño cómo se ve un
    local bien cargado. Prefiere el rubro pedido; si no alcanzan, completa con otros.
    «Completo» está definido en `que_hay_aca.es_completo`. Sin ciudad asignada: lista vacía."""
    ciudad_id = _ciudad_del_agente(repo, agente)
    if not ciudad_id:
        return {"items": []}
    return {"items": que_hay_aca.ejemplos(repo, ciudad_id, (rubro or "").strip() or None,
                                          (excluir or "").strip() or None)}


#: Tiempo en que el agente que dio de alta un comercio puede corregir el
#: WhatsApp que él mismo tipeó (se equivocó un dígito al cargarlo).
_CORREGIR_WA_MIN = 120


def _recien_cargado_por(comercio: dict, agente: dict) -> bool:
    """El comercio lo cargó ESTE agente hace menos de 2 horas.

    Corregir ahí el WhatsApp no abre nada nuevo: en el alta ya podía poner el
    número que quisiera. Pasado ese rato, o si lo cargó otro, el número ya
    cargado no se toca desde campo (ver `editar_mi_comercio`)."""
    from datetime import datetime, timedelta, timezone

    if (comercio.get("cargado_por") or "").lower() != (agente.get("email") or "").lower():
        return False
    try:
        creado = datetime.fromisoformat(str(comercio.get("created_at")).replace("Z", "+00:00"))
    except ValueError:
        return False
    if creado.tzinfo is None:
        creado = creado.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - creado <= timedelta(minutes=_CORREGIR_WA_MIN)


def _propio_o_404(repo: Repo, comercio_id: str, agente: dict) -> dict:
    """Puede tocar lo de SU CIUDAD, lo haya cargado él o el otro agente.

    El dueño de la ficha es la ciudad, no quien la cargó primero: si el agente
    está parado en el local y el horario está mal, tiene que poder arreglarlo
    ahí, sea quien sea que lo haya dado de alta. Lo que sigue cerrado es la
    ciudad ajena.
    """
    comercio = repo.get_comercio(comercio_id)
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    if comercio.get("cargado_por") == agente["email"]:
        return comercio
    ciudad_id = _ciudad_del_agente(repo, agente)
    if ciudad_id and comercio.get("ciudad_id") == ciudad_id:
        return comercio
    raise HTTPException(status_code=404, detail="Comercio no encontrado")


@router.get("/campo/mis-comercios/{comercio_id}")
def ver_mi_comercio(
    comercio_id: str,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Un comercio de su ciudad (o cargado por él), con lo mismo que trae la lista.

    Lo pide «Completar comercio» al final del alta: el recién creado no está en
    la lista que ya tiene el celular, y bajar la ciudad entera con la señal de
    la calle fallaba justo cuando hay que sacarle las fotos al local.
    """
    _propio_o_404(repo, comercio_id, agente)
    comercio = repo.get_comercio_campo(comercio_id)
    if not comercio:
        raise HTTPException(status_code=404, detail="Comercio no encontrado")
    return {"comercio": sin_codigo(que_hay_aca.enriquecer(repo, [comercio])[0])}


class _InteresBody(BaseModel):
    plan: str
    nota: str | None = None


_MAX_NOTA_INTERES = 300


@router.post("/campo/mis-comercios/{comercio_id}/interes")
def anotar_interes(
    comercio_id: str,
    body: _InteresBody,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """«Le interesa un plan»: el agente anota que el dueño quiere sumarse y el admin lo ve en
    Suscripciones. Queda en `comercio_eventos` (`interes_plan`, `detalle` = {plan, nota}).
    No cambia el plan ni cobra nada. Regla de ciudad de siempre (`_propio_o_404`)."""
    comercio = _propio_o_404(repo, comercio_id, agente)
    slug = (body.plan or "").strip()
    plan = repo.get_plan(slug) if slug else None
    if not plan or not plan.get("activo", True) or not _es_plan_pago(plan):
        raise HTTPException(status_code=400, detail="Elegí un plan de pago de la lista")
    nota = (body.nota or "").strip() or None
    if nota and len(nota) > _MAX_NOTA_INTERES:
        raise HTTPException(status_code=400, detail=f"La nota admite hasta {_MAX_NOTA_INTERES} caracteres")
    try:
        repo.registrar_evento_comercio(comercio["id"], "interes_plan", agente["email"],
                                       {"plan": plan["slug"], "nota": nota})
    except Exception as exc:  # noqa: BLE001
        logger.warning("campo.interes_plan_fallo", comercio=comercio["id"], exc_info=True)
        raise HTTPException(status_code=502, detail="No se pudo anotar el interés, probá de nuevo") from exc
    logger.info("campo.interes_plan", comercio=comercio["id"], plan=plan["slug"], agente=agente["email"])
    return {"ok": True, "plan": plan["slug"], "nota": nota}


class _EditarComercioBody(BaseModel):
    """Lo que el agente puede corregir desde la calle.

    Creció con la segunda pasada: el alta deja lo mínimo —foto, GPS, rubro— y
    todo lo demás se carga en la segunda visita, con el dueño presente. Antes
    estos campos sólo se podían tocar desde el panel, o sea nunca, porque quien
    está frente al comerciante es el agente y no el administrador.
    """
    nombre: str | None = None
    whatsapp: str | None = None
    #: El segundo número: el fijo del local, o el celular de quien atiende.
    telefono: str | None = None
    email: str | None = None
    modalidad: str | None = None
    direccion: str | None = None
    prod_obs_human: str | None = None
    rubro_slugs: list[str] | None = None
    #: Dentro de qué mercado o galería, y en qué puesto. En Bermejo es lo que
    #: de verdad permite encontrar un local: no tiene altura de calle.
    lugar_id: str | None = None
    puesto: str | None = None
    instagram_url: str | None = None
    facebook_url: str | None = None
    tiktok_url: str | None = None
    sitio_web: str | None = None
    #: Su propio canal de WhatsApp (0133), no el de URUKU.
    canal_wa_url: str | None = None
    #: Un ENLACE (Drive, una tienda). El PDF se sube aparte, por
    #: POST /campo/mis-comercios/{id}/catalogo. Vacío borra; sólo http(s).
    catalogo_url: str | None = None
    #: «Lo que suma» en la ficha (docs/ficha-destacados.md). Los booleanos en
    #: null no se tocan; el pedido mínimo admite hasta 120 caracteres.
    tiene_pasero: bool | None = None
    envios_internacionales: bool | None = None
    tiene_factura: bool | None = None
    talles_especiales: bool | None = None
    pedido_minimo: str | None = None
    #: El horario, como lo dicta el dueño («Lun-Sáb 8:00-12:00 y 14:30-20:00»).
    #: Faltaba: el filtro «Sin horario» de la app llevaba a un editor que no lo
    #: podía cargar. Es el dato que decide si alguien camina hasta el local.
    horario: str | None = None
    #: El GPS tomado en la puerta (docs/farmacias-de-turno.md). Van JUNTOS: con uno solo no
    #: hay punto. Al guardarlos la ubicación deja de ser «aproximada»
    #: (`ubicacion_aproximada = false`); si la IA o el cruce de calles la habían calculado,
    #: ahora la confirmó una persona parada en el local.
    lat: float | None = Field(None, ge=-90, le=90)
    lng: float | None = Field(None, ge=-180, le=180)


@router.patch("/campo/mis-comercios/{comercio_id}")
def editar_mi_comercio(
    comercio_id: str,
    body: _EditarComercioBody,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """El agente corrige un comercio de SU CIUDAD, parado en la puerta."""
    actual_comercio = _propio_o_404(repo, comercio_id, agente)
    if body.modalidad is not None and body.modalidad not in _MODALIDADES:
        raise HTTPException(status_code=400, detail=f"modalidad inválida: {body.modalidad}")
    patch = body.model_dump(exclude_unset=True, exclude={"rubro_slugs"})
    # Un campo que llega VACÍO se borra, no se guarda como "". Es lo que
    # permite deshacer: pegar mal un Instagram y después dejarlo en blanco
    # tiene que sacarlo de la ficha, no dejar un enlace a ninguna parte.
    patch = {k: (v if (v is None or str(v).strip()) else None) for k, v in patch.items()}
    if "whatsapp" in patch:
        # EL AGENTE COMPLETA EL NÚMERO, NO LO CAMBIA. Con el número en la mano
        # se entra a Mi comercio: si el agente pudiera reemplazarlo, pondría el
        # suyo, entraría por WhatsApp, recibiría la clave, y después volvería a
        # poner el original sin que nadie lo note. Un número ya cargado se
        # cambia con «Cambié de número» (lo aprueba el admin) o desde el panel.
        from app.services.cuentas import mismo_numero
        from app.core.telefono import whatsapp_para_guardar

        actual = (repo.get_comercio(comercio_id) or {}).get("whatsapp")
        if (actual and str(actual).strip() and not mismo_numero(actual, patch["whatsapp"])
                and not _recien_cargado_por(actual_comercio, agente)):
            raise HTTPException(
                status_code=400,
                detail="Este comercio ya tiene WhatsApp. Si cambió, el dueño lo pide desde «Cambié de número».",
            )
        if patch["whatsapp"]:
            patch["whatsapp"] = whatsapp_para_guardar(patch["whatsapp"]) or patch["whatsapp"].strip()
    if "lat" in patch or "lng" in patch:
        # El GPS se re-toma entero: lat y lng juntos y con valor. Un punto a medias (o un
        # `null`, que sería borrar la ubicación) saca al comercio del mapa.
        if patch.get("lat") is None or patch.get("lng") is None:
            raise HTTPException(status_code=400, detail="La ubicación necesita latitud y longitud")
        # Tomada con el GPS en la puerta: deja de ser la calculada desde la dirección.
        patch["ubicacion_aproximada"] = False
    if patch.get("horario"):
        # Lo dictó el dueño, parado en el local: deja de ser el estimado de la
        # calle (el que se carga por lote), igual que cuando lo escribe el admin.
        patch["horario"] = patch["horario"].strip()[:200]
        patch["horario_estimado"] = False
    try:
        enlaces.validar_redes(patch)
        catalogo_svc.normalizar_ficha(patch)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not patch and body.rubro_slugs is None:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")
    anterior = actual_comercio.get("catalogo_url") if "catalogo_url" in patch else None
    if anterior and anterior != patch.get("catalogo_url", anterior):
        # EL AGENTE NO BORRA. Vaciar el catálogo es quitarlo, y reemplazar un PDF
        # nuestro por un enlace es dejar el PDF sin dueño (se borraría del disco).
        # Cambiar un enlace por otro enlace no borra nada y se permite.
        if patch["catalogo_url"] is None or catalogo_svc.archivo_propio(anterior, comercio_id):
            raise HTTPException(status_code=403, detail=fotos_galeria.MSG_AGENTE_NO_BORRA)
    comercio = repo.update_comercio(comercio_id, patch, body.rubro_slugs)
    if "lat" in patch:
        calles_mapa.invalidar(comercio.get("ciudad_id") or actual_comercio.get("ciudad_id"))   # el comercio se movió de cuadra
    if "catalogo_url" in patch:
        # Cambió el catálogo (enlace por enlace: el anterior no era un PDF nuestro,
        # el agente no puede cambiar ese caso). Se deja por si cambia la regla.
        catalogo_svc.soltar_catalogo_reemplazado(anterior, patch["catalogo_url"], comercio_id)
    return {"ok": True, "comercio": sin_codigo(comercio)}


@router.post("/campo/mis-comercios/{comercio_id}/catalogo")
async def subir_catalogo_mi_comercio(
    comercio_id: str,
    request: Request,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """El agente sube el catálogo en PDF (multipart, campo `archivo`, hasta 8 MB)
    de un comercio de su ciudad. Reemplaza al anterior y borra el archivo viejo."""
    comercio = _propio_o_404(repo, comercio_id, agente)
    url = await catalogo_svc.subir_catalogo(repo, comercio, request, actor=agente["email"])
    return {"catalogo_url": url}


@router.delete("/campo/mis-comercios/{comercio_id}/catalogo")
async def quitar_catalogo_mi_comercio(
    comercio_id: str,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """El agente NO quita catálogos: borrar (y con eso el PDF del disco) es del admin y del comercio."""
    _propio_o_404(repo, comercio_id, agente)
    raise HTTPException(status_code=403, detail=fotos_galeria.MSG_AGENTE_NO_BORRA)


@router.post("/campo/mis-comercios/{comercio_id}/foto")
async def actualizar_foto_mi_comercio(
    comercio_id: str,
    foto: UploadFile = File(...),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """El agente sube una portada nueva a un comercio de su ciudad.

    Reinicia el recorte. El agente sólo sube y no borra archivos: la portada
    anterior PASA A LA GALERÍA (aunque eso supere el tope del plan: ya existía) y
    no se toca ningún archivo del disco.
    """
    comercio = _propio_o_404(repo, comercio_id, agente)
    data = await foto.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta la foto")
    portada_url, portada_thumb = await run_in_threadpool(_subir_foto, comercio["slug"], foto, data)
    if not portada_url:
        raise HTTPException(status_code=502, detail="No se pudo subir la foto, probá de nuevo")
    updated = portada.poner_nueva(repo, comercio, portada_url, portada_thumb, conservar_anterior=True)
    logger.info("campo.foto_update", comercio=comercio_id, agente=agente["email"])
    return {"ok": True, "comercio": sin_codigo(updated)}


@router.put("/campo/mis-comercios/{comercio_id}/portada")
def usar_como_portada_mi_comercio(
    comercio_id: str,
    body: portada.UsarPortadaBody,
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    """Una foto de la galería pasa a ser la portada (intercambio, sin tocar archivos)."""
    comercio = _propio_o_404(repo, comercio_id, agente)
    actualizado = portada.usar_de_galeria(repo, comercio, body.foto_id)
    logger.info("campo.portada_de_galeria", comercio=comercio_id, agente=agente["email"])
    return portada.respuesta(repo, actualizado)


# EL AGENTE SÓLO SUBE. No da de baja comercios ni borra fotos: eso lo hace el
# admin (docs/portada-y-permisos.md). Por eso no hay `DELETE /campo/mis-comercios/{id}`.


class _LeadIn(BaseModel):
    comercio_id: str
    tipo: str = "whatsapp"
    # De qué búsqueda salió este contacto. Vacío si llegó por el mapa, la home
    # o un link compartido: son caminos igual de válidos, no un dato faltante.
    busqueda_id: str | None = None
    # De dónde llegó (el `?ref=` de la URL): volante-<slug>, mesa-<slug>,
    # ficha-<slug>, fb, ig. Vacío si entró por el buscador o el mapa.
    origen: str | None = None


@router.post("/lead")
def registrar_lead(body: _LeadIn, repo: Repo = Depends(get_repo)) -> dict:
    """Registra un click de contacto (WhatsApp, teléfono, email…) o una vista de ficha."""
    tipo = body.tipo if body.tipo in _TIPOS_LEAD else "whatsapp"
    fila = {"comercio_id": body.comercio_id, "tipo": tipo}
    # Si el contacto salió de una búsqueda, se guarda cuál. Es lo que permite
    # medir después si el buscador acertó: qué se mostró contra qué se eligió.
    # Viene vacío cuando llegan por el mapa, la home o un link compartido.
    if body.busqueda_id:
        fila["busqueda_id"] = body.busqueda_id
    origen = limpiar_ref(body.origen)
    if origen:
        fila["origen"] = origen
    creado = repo.insert_lead(fila) or {}
    # El id vuelve para que el sitio pueda preguntar después «¿te contestó?».
    return {"ok": True, "id": creado.get("id")}


# ── Visitas al sitio (0130) ──────────────────────────────────────────────────
class _VisitaIn(BaseModel):
    """Una página vista. SIN cookies, sin IP, sin user-agent.

    `sesion` es un número al azar que vive en la pestaña y se pierde al
    cerrarla: sirve para no contar diez veces a la misma persona en una
    recorrida, no para seguir a nadie."""
    ruta: str = Field(max_length=200)
    sesion: str = Field(min_length=6, max_length=40)
    origen: str | None = None
    #: Sólo el host (google.com, facebook.com). La URL entera no hace falta y
    #: puede llevar datos de la otra página.
    referido: str | None = None
    ciudad: str | None = None
    #: Primera página de esta sesión: es lo que hace «personas» sin agrupar.
    primera: bool = False


#: Rutas que NO se cuentan: el panel, la carga de campo y el editor del
#: comercio son trabajo, no visitas. Contarlas inflaría el número justo con
#: quienes estamos construyendo el sitio, que es la peor forma de engañarse.
_RUTAS_INTERNAS = ("/admin", "/contenido", "/publicar", "/campo", "/mi-comercio", "/api/")


@router.post("/visita")
def registrar_visita(body: _VisitaIn, repo: Repo = Depends(get_repo)) -> dict:
    """Anota una página vista. Fuego y olvido: si falla, no rompe la visita."""
    ruta = (body.ruta or "/").strip()[:200]
    if not ruta.startswith("/") or ruta.startswith(_RUTAS_INTERNAS):
        return {"ok": True, "contada": False}

    limpio = lambda v, n: re.sub(r"[^a-z0-9_.:/-]", "", (v or "").strip().lower())[:n] or None
    fila = {
        "ruta": ruta,
        "sesion": re.sub(r"[^a-zA-Z0-9-]", "", body.sesion)[:40],
        "origen": limpiar_ref(body.origen),   # la misma regla que /lead
        "referido": limpio(body.referido, 80),
        "ciudad_slug": limpio(body.ciudad, 40),
        "primera": bool(body.primera),
    }
    repo.insert_visita({k: v for k, v in fila.items() if v is not None})
    return {"ok": True, "contada": True}


class _RespondioIn(BaseModel):
    respondio: bool


@router.post("/lead/{lead_id}/respondio")
def lead_respondio(lead_id: str, body: _RespondioIn, repo: Repo = Depends(get_repo)) -> dict:
    """«¿Te contestó?»: el comprador dice sí o no sobre un contacto suyo.

    Sólo sobre un contacto de WhatsApp de la última semana y una sola vez:
    el id es un uuid que sólo tiene quien hizo el clic, y con eso alcanza
    para que nadie pueda hundir a un comercio a fuerza de «no». Después se
    recuentan los contadores del comercio (últimos 90 días)."""
    from datetime import datetime, timezone, timedelta
    lead = repo.get_lead(lead_id)
    if not lead or lead.get("tipo") not in ("whatsapp", "telefono"):
        raise HTTPException(status_code=404, detail="contacto no encontrado")
    if lead.get("respondio") is not None:
        return {"ok": True, "ya": True}
    creado = lead.get("created_at")
    if isinstance(creado, str):
        try:
            hace = datetime.now(timezone.utc) - datetime.fromisoformat(creado.replace("Z", "+00:00"))
            if hace > timedelta(days=7):
                raise HTTPException(status_code=410, detail="ese contacto es de hace más de una semana")
        except ValueError:
            pass
    repo.marcar_lead_respondio(lead_id, body.respondio)
    conteo = repo.recontar_contactos(lead["comercio_id"])
    return {"ok": True, **conteo}


class _BusquedaIn(BaseModel):
    query: str
    resultados: int = 0
    comercios: list[str] | None = None   # ids que aparecieron, en orden (para análisis)


@router.post("/busquedas/log")
def log_busqueda(body: _BusquedaIn, repo: Repo = Depends(get_repo)) -> dict:
    """Loguea una búsqueda (KPIs: qué se busca, qué no da resultados y a quién encontró).

    Devuelve el id para que el front pueda atarle el click posterior: sin ese
    puente se sabe qué se mostró y qué se contactó, pero no si una cosa llevó a
    la otra — que es justo lo que dice si el buscador sirve.
    """
    q = (body.query or "").strip()
    if len(q) < 2:
        return {"ok": True}
    bid = repo.insert_busqueda(q, max(0, int(body.resultados)), body.comercios)
    return {"ok": True, "busqueda_id": bid}


class _ReclamoIn(BaseModel):
    nombre: str | None = None
    contacto: str | None = None
    comercio_id: str | None = None
    mensaje: str


@router.post("/reclamos")
def crear_reclamo(body: _ReclamoIn, repo: Repo = Depends(get_repo)) -> dict:
    """Deja un reclamo público (sobre un comercio o la plataforma en general)."""
    repo.crear_reclamo({
        "nombre": body.nombre,
        "contacto": body.contacto,
        "comercio_id": body.comercio_id,
        "mensaje": body.mensaje,
    })
    return {"ok": True}


# ============================================================
# Galería del comercio: fotos según el plan (services/fotos_galeria.py) + 5 videos (<=60s c/u).
# Los archivos van al disco del backend; la base guarda la referencia.
# Todos scoped al agente dueño del comercio (_propio_o_404).
# ============================================================
_MAX_VIDEOS = 5
_MAX_VIDEO_BYTES = 50 * 1024 * 1024  # 50 MB


@router.get("/campo/mis-comercios/{comercio_id}/fotos")
async def listar_fotos(comercio_id: str, agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    comercio = _propio_o_404(repo, comercio_id, agente)
    # `limite` = el tope de fotos de hoy (plan + extras): la galería muestra «23/50».
    return fotos_galeria.listado(repo, comercio)


@router.post("/campo/mis-comercios/{comercio_id}/fotos")
async def agregar_foto(
    comercio_id: str,
    foto: UploadFile = File(...),
    reemplazar: str | None = Form(None),
    extra: str | None = Form(None),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    comercio = _propio_o_404(repo, comercio_id, agente)
    if (reemplazar or "").strip():
        # Reemplazar es borrar la más vieja: el agente no borra. En el tope sólo cancela.
        raise HTTPException(status_code=403, detail=fotos_galeria.MSG_AGENTE_NO_BORRA)
    # El agente no puede pagar (403 si manda extra=pagar); en el tope, 409.
    subida = fotos_galeria.preparar(repo, comercio, reemplazar=reemplazar, extra=extra, puede_pagar=False)
    data = await foto.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta la foto")
    if len(data) > _MAX_FOTO_BYTES:
        raise HTTPException(status_code=413, detail="La foto supera los 15 MB")
    try:
        url, thumb = await run_in_threadpool(subir_foto_galeria, comercio["slug"], data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not url:
        raise HTTPException(status_code=502, detail="No se pudo subir la foto, probá de nuevo")
    row = fotos_galeria.registrar(repo, comercio, subida, url, thumb)
    logger.info("campo.foto_add", comercio=comercio_id, agente=agente["email"],
                reemplazo=bool(subida.reemplaza))
    return {"ok": True, "foto": row}


@router.delete("/campo/mis-comercios/{comercio_id}/fotos/{foto_id}")
async def borrar_foto(comercio_id: str, foto_id: str, agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    _propio_o_404(repo, comercio_id, agente)
    # El agente sólo sube: borrar fotos es del admin (y del propio comercio).
    raise HTTPException(status_code=403, detail=fotos_galeria.MSG_AGENTE_NO_BORRA)


@router.get("/campo/mis-comercios/{comercio_id}/videos")
async def listar_videos(comercio_id: str, agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    _propio_o_404(repo, comercio_id, agente)
    return {"items": repo.list_videos_comercio(comercio_id)}


@router.post("/campo/mis-comercios/{comercio_id}/videos")
async def agregar_video(
    comercio_id: str,
    video: UploadFile = File(...),
    duracion_seg: int | None = Form(None),
    agente: dict = Depends(auth.require_agente),
    repo: Repo = Depends(get_repo),
) -> dict:
    comercio = _propio_o_404(repo, comercio_id, agente)
    if repo.count_videos_comercio(comercio_id) >= _MAX_VIDEOS:
        raise HTTPException(status_code=409, detail=f"Máximo {_MAX_VIDEOS} videos por comercio")
    if not (video.content_type or "").lower().startswith("video/"):
        raise HTTPException(status_code=400, detail="El archivo no es un video")
    data = await video.read()
    if not data:
        raise HTTPException(status_code=400, detail="Falta el video")
    if len(data) > _MAX_VIDEO_BYTES:
        raise HTTPException(status_code=413, detail="El video supera los 50 MB")
    url = subir_video_comercio(comercio["slug"], data, video.content_type)
    if not url:
        raise HTTPException(status_code=502, detail="No se pudo subir el video, probá de nuevo")
    row = repo.add_video_comercio({
        "comercio_id": comercio_id, "url": url, "duracion_seg": duracion_seg,
        "orden": repo.count_videos_comercio(comercio_id),
    })
    logger.info("campo.video_add", comercio=comercio_id, agente=agente["email"])
    return {"ok": True, "video": row}


@router.delete("/campo/mis-comercios/{comercio_id}/videos/{video_id}")
async def borrar_video(comercio_id: str, video_id: str, agente: dict = Depends(auth.require_agente), repo: Repo = Depends(get_repo)) -> dict:
    _propio_o_404(repo, comercio_id, agente)
    # El agente sólo sube: borrar videos es del admin (y del propio comercio).
    raise HTTPException(status_code=403, detail=fotos_galeria.MSG_AGENTE_NO_BORRA)
