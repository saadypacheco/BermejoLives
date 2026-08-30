"""Configuración central (pydantic-settings, lee de .env)."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    # Supabase — service_role NUNCA se expone al frontend (lesson KB)
    supabase_url: str = ""                 # cómo lo alcanza el backend (host.docker.internal en Docker)
    supabase_public_url: str = ""          # cómo lo alcanza el navegador (localhost) — para URLs de fotos
    supabase_service_role_key: str = ""

    # Envío de OTP por WhatsApp — proveedor intercambiable (ver services/whatsapp_client.py)
    whatsapp_provider: str = "waha"     # "waha" | "cloud_api"

    # Bridge WhatsApp (WAHA) — red privada
    waha_base_url: str = "http://waha:3000"
    waha_api_key: str = ""
    webhook_secret: str = ""            # HMAC del webhook

    # WhatsApp Business Platform (Cloud API oficial) — requiere plantilla de
    # "Authentication" ya aprobada en el Meta Business Manager.
    whatsapp_cloud_phone_id: str = ""
    whatsapp_cloud_token: str = ""
    whatsapp_cloud_template_otp: str = "otp_login"

    # Número al que el usuario le manda "CONFIRMAR-XXXXXX" para probar que
    # el celular es suyo (login/recuperación por mensaje entrante, sin
    # riesgo de ban — ver services/whatsapp_client.py). Mismo número de la
    # sesión de WAHA.
    bot_whatsapp_numero: str = ""

    def wa_link_confirmar(self, codigo: str) -> str:
        return f"https://wa.me/{self.bot_whatsapp_numero}?text=CONFIRMAR-{codigo}"

    # Los números de URUKU que están dentro de los grupos de comerciantes,
    # separados por coma. En cada grupo hay tres participantes: el comercio, un
    # número de URUKU y el testigo.
    #
    # El testigo es el número vinculado a WAHA, así que sus mensajes llegan con
    # fromMe=true y la ingesta ya los descarta. El de URUKU NO: es otro
    # teléfono, entra como cualquier participante, y sin esta lista cada vez que
    # alguien de URUKU escriba "buen día" en el grupo se crea una publicación a
    # nombre del comerciante.
    wa_numeros_propios: str = ""

    # Los números de URUKU que se AGREGAN a cada grupo nuevo: los respaldos que
    # esperan el día del baneo. El operativo no va acá — es quien crea el grupo,
    # así que ya queda adentro. Ver docs/numeros-whatsapp-uruku.md.
    wa_numeros_grupo: str = ""

    def es_numero_propio(self, numero: str | None) -> bool:
        if not numero:
            return False
        from app.core.telefono import normalizar_whatsapp

        objetivo = normalizar_whatsapp(numero)
        return bool(objetivo) and objetivo in _numeros_propios(self.wa_numeros_propios)

    # Auth del panel (JWT self-contained, igual patrón que mentorcomercial)
    jwt_secret: str = "bermejo-dev-secret-change-in-prod"
    jwt_ttl_hours: int = 168           # 7 días
    admin_email: str = "admin@bermejolive.com"
    admin_password: str = "bermejo1234"

    # Agente de campo (alta de comercios en el recorrido)
    agente_email: str = "agente@bermejolive.com"
    agente_password: str = "campo1234"

    # Publicador (contenido del sitio: cotizaciones, clima, videos promocionales)
    publicador_email: str = "publicador@bermejolive.com"
    publicador_password: str = "publicar1234"
    # Worker que refresca el clima desde open-meteo cada 30 min (se apaga en tests)
    clima_worker: bool = True

    # ---- Ciclo de vida del comercio en el mapa ----
    # Días después de vencido el pago antes de sacarlo del mapa (10 de gracia +
    # ~1 mes en "solo mapa").
    dias_vencido_baja: int = 40
    # Días desde el alta que tiene un comercio que NUNCA pagó antes de caerse del
    # mapa. Es la segunda pasada: se carga rápido en la calle, y a los 2 meses o
    # paga o desaparece.
    #
    # APAGADO (None) a propósito: la lógica está lista y testeada, pero prenderla
    # sin revisar antes tiraría del mapa, de una, a todos los comercios cargados
    # hace más de 60 días que nunca pagaron — sin que nadie lo vea venir. Se
    # prende con DIAS_GRACIA_SIN_PAGO=60 después de revisar a quiénes alcanza
    # (POST /admin/bajas/ejecutar permite probarlo cuando se quiera).
    dias_gracia_sin_pago: int | None = None

    # Gate por plan de la ingesta por WhatsApp (mandar productos sin loguearse).
    # Arranca APAGADO a propósito: durante la captación conviene que cualquier
    # comercio pueda mandar productos, ofertas y servicios para que el catálogo
    # tenga volumen. Cuando la captación termine, se prende y pasa a ser una
    # función del plan más caro.
    ingesta_requiere_plan: bool = False
    # Planes habilitados a publicar por WhatsApp cuando el gate está prendido.
    planes_con_ingesta: str = "premium"

    # Transcripción de audio del "¿qué vende?".
    #  - Si OPENAI_API_KEY está seteada → usa la API de OpenAI Whisper.
    #  - Si no → usa faster-whisper SELF-HOSTED (gratis, en el VPS).
    openai_api_key: str = ""
    whisper_model: str = "small"      # tiny/base/small/medium
    whisper_device: str = "cpu"       # 'cuda' si hubiera GPU

    # Integración con el ecommerce (marketplace multi-vendedor).
    #  - tienda_api_url vacío → TiendaClient en modo STUB (dev/tests, sin red).
    #  - tienda_api_secret = X-API-Key compartido (servicio-a-servicio).
    tienda_api_url: str = ""
    tienda_api_secret: str = ""

    # Dashboard admin unificado: lee resumen/consultas de Reservalo (mismo
    # tienda_api_url, secret propio del endpoint /api/admin-sync/*).
    admin_sync_secret: str = ""

    # Clasificación de productos por IA (Gemini Flash, solo texto).
    #  - Si gemini_api_key vacío → fallback gratis (categoría = rubro del comercio).
    gemini_api_key: str = ""
    # Alias, NO una versión fija: los modelos concretos se retiran y el endpoint
    # empieza a devolver 404. Pasó con gemini-2.0-flash, que estaba acá clavado y
    # dejó de existir — el análisis por fotos falló sin que nada lo avisara hasta
    # que se leyó el error crudo. El alias sigue apuntando al flash vigente.
    # Para fijar una versión concreta, setear GEMINI_MODEL en el .env.
    gemini_model: str = "gemini-flash-latest"

    # Frontend (CORS)
    frontend_url: str = "http://localhost:3000"

    storage_bucket: str = "publicaciones"
    comercios_bucket: str = "comercios"

    # Fotos de comercio: se guardan en disco (volumen Docker) y las sirve el
    # propio backend por /fotos/... — reemplaza a Supabase Storage en el
    # self-host (ver services/imagenes.py).
    fotos_dir: str = "/data/fotos"
    fotos_public_base_url: str = "http://localhost:8000/fotos"  # cómo lo alcanza el navegador

    def public_photo_url(self, path: str) -> str:
        return f"{self.fotos_public_base_url.rstrip('/')}/{path}"


@lru_cache(maxsize=4)
def _numeros_propios(crudo: str) -> frozenset[str]:
    """Los números de URUKU del .env, validados y avisando de los que no sirven.

    POR QUÉ VALIDA EN VEZ DE NORMALIZAR Y LISTO
    ===========================================

    Porque el placeholder no da error, da basura. `591XXXXXXXX` —que es lo que
    queda si nadie reemplaza el ejemplo— normaliza a `591`: las X se descartan
    igual que un guión o un espacio. La variable queda "puesta", la lista tiene
    un elemento, y no coincide con ningún teléfono real. La guarda existe y no
    protege nada.

    Es la misma forma de fallar que ya costó horas en este proyecto: un embed
    roto que devuelve [] y se lee como "no hay datos", un script que informa
    "0 sin respaldo" cuando hay 37. Lo que no se puede es quedarse callado.

    Se descartan los inválidos y se avisa cuáles: mejor la guarda apagada y
    dicha, que apagada y en silencio.
    """
    import structlog

    from app.core.telefono import normalizar_whatsapp, validar_whatsapp

    log = structlog.get_logger()
    validos: set[str] = set()
    for bruto in (n.strip() for n in crudo.split(",")):
        if not bruto:
            continue
        error = validar_whatsapp(bruto)
        if error:
            log.warning("config.wa_numero_propio_invalido", valor=bruto, motivo=error)
            continue
        numero = normalizar_whatsapp(bruto)
        if numero:
            validos.add(numero)

    if crudo.strip() and not validos:
        log.warning("config.wa_numeros_propios_vacio",
                    detalle="WA_NUMEROS_PROPIOS está seteado pero ningún número es válido: "
                            "los mensajes de URUKU en los grupos van a generar publicaciones")
    return frozenset(validos)


settings = Settings()
