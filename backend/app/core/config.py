"""Configuración central (pydantic-settings, lee de .env)."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    # Supabase — service_role NUNCA se expone al frontend (lesson KB)
    supabase_url: str = ""                 # cómo lo alcanza el backend (host.docker.internal en Docker)
    supabase_public_url: str = ""          # cómo lo alcanza el navegador (localhost) — para URLs de fotos
    supabase_service_role_key: str = ""

    # Bridge WhatsApp (WAHA) — red privada
    waha_base_url: str = "http://waha:3000"
    waha_api_key: str = ""
    webhook_secret: str = ""            # HMAC del webhook

    # Auth del panel (JWT self-contained, igual patrón que mentorcomercial)
    jwt_secret: str = "bermejo-dev-secret-change-in-prod"
    jwt_ttl_hours: int = 168           # 7 días
    admin_email: str = "admin@bermejolive.com"
    admin_password: str = "bermejo1234"

    # Agente de campo (alta de comercios en el recorrido)
    agente_email: str = "agente@bermejolive.com"
    agente_password: str = "campo1234"

    # Transcripción de audio del "¿qué vende?" (OpenAI Whisper). Vacío = se escribe a mano.
    openai_api_key: str = ""

    # Frontend (CORS)
    frontend_url: str = "http://localhost:3000"

    storage_bucket: str = "publicaciones"
    comercios_bucket: str = "comercios"

    def public_photo_url(self, path: str) -> str:
        base = (self.supabase_public_url or self.supabase_url).rstrip("/")
        return f"{base}/storage/v1/object/public/{self.comercios_bucket}/{path}"


settings = Settings()
