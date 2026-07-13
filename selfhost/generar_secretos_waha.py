"""Genera los secretos para desplegar WAHA (bridge de WhatsApp).

Uso:
    python generar_secretos_waha.py

Imprime lo necesario para pegar en dos archivos del VPS:
  - .env (raíz): WAHA_API_KEY, WEBHOOK_SECRET, WAHA_DASHBOARD_USER,
    WAHA_DASHBOARD_PASSWORD — los usa docker-compose.prod.yml para
    configurar el contenedor de WAHA.
  - backend/.env: WAHA_API_KEY y WEBHOOK_SECRET (los MISMOS valores de
    arriba, no unos nuevos) — el backend los necesita para autenticar sus
    llamadas a WAHA y para validar la firma HMAC del webhook entrante.
"""
import secrets


def main() -> None:
    waha_api_key = secrets.token_urlsafe(32)
    webhook_secret = secrets.token_urlsafe(32)
    dashboard_user = "admin"
    dashboard_password = secrets.token_urlsafe(16)

    print("# --- pegar en el .env de la raíz ---")
    print(f"WAHA_API_KEY={waha_api_key}")
    print(f"WEBHOOK_SECRET={webhook_secret}")
    print(f"WAHA_DASHBOARD_USER={dashboard_user}")
    print(f"WAHA_DASHBOARD_PASSWORD={dashboard_password}")
    print()
    print("# --- pegar en backend/.env (MISMOS valores, no generar otros) ---")
    print(f"WAHA_API_KEY={waha_api_key}")
    print(f"WEBHOOK_SECRET={webhook_secret}")


if __name__ == "__main__":
    main()
