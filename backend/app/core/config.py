"""Configuración central (pydantic-settings, lee de .env)."""
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

    # Auth del panel (JWT self-contained, igual patrón que mentorcomercial)
    jwt_secret: str = "bermejo-dev-secret-change-in-prod"
    jwt_ttl_hours: int = 168           # 7 días
    admin_email: str = "admin@bermejolive.com"
    admin_password: str = "bermejo1234"

    # Agente de campo (alta de comercios en el recorrido)
    agente_email: str = "agente@bermejolive.com"
    agente_password: str = "campo1234"

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
    gemini_model: str = "gemini-2.0-flash"

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


settings = Settings()
