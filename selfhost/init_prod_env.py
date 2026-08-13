"""Genera TODOS los secretos y escribe .env + backend/.env para un ambiente nuevo.

Uso (en el VPS, dentro del repo clonado):
    apt install -y python3-jwt
    python3 selfhost/init_prod_env.py uruku.bo

Crea/sobrescribe:
  - .env            (raíz, junto a docker-compose.prod.yml)
  - backend/.env

Y al final imprime las CREDENCIALES de acceso (admin/agente/publicador/WAHA) para
que las guardes. Los secretos "de máquina" (JWTs, passwords de DB) quedan solo en
los archivos, no se imprimen. NO pegues la salida en ningún chat.
"""
import os
import secrets
import sys
import time

try:
    import jwt
except ImportError:
    print("Falta PyJWT. Instalá con:  apt install -y python3-jwt")
    sys.exit(1)


def tok(n: int = 32) -> str:
    return secrets.token_urlsafe(n)


def main() -> None:
    if len(sys.argv) < 2:
        print("Uso: python3 selfhost/init_prod_env.py <dominio>   (ej: uruku.bo)")
        sys.exit(1)
    dom = sys.argv[1].strip().lower()
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # Secretos de la base / PostgREST
    pgrst_jwt = tok(48)
    postgres_pw = tok(32)
    authenticator_pw = tok(32)
    exp = int(time.time()) + 20 * 365 * 24 * 3600
    iss = f"{dom}-selfhost"
    anon = jwt.encode({"role": "anon", "iss": iss, "exp": exp}, pgrst_jwt, algorithm="HS256")
    service = jwt.encode({"role": "service_role", "iss": iss, "exp": exp}, pgrst_jwt, algorithm="HS256")

    # Backend / WhatsApp
    backend_jwt = tok(32)
    waha_api = tok(24)
    webhook = tok(24)
    waha_dash_user = "uruku"
    waha_dash_pw = tok(18)

    # Credenciales de login (las guardás para entrar a los paneles)
    admin_pw = tok(12)
    agente_pw = tok(12)
    publicador_pw = tok(12)

    env_root = (
        f"DOMAIN={dom}\n"
        f"MODO_CAPTURA=0\n"
        f"POSTGRES_PASSWORD={postgres_pw}\n"
        f"AUTHENTICATOR_PASSWORD={authenticator_pw}\n"
        f"PGRST_JWT_SECRET={pgrst_jwt}\n"
        f"NEXT_PUBLIC_SUPABASE_URL=https://db.{dom}\n"
        f"NEXT_PUBLIC_SUPABASE_ANON_KEY={anon}\n"
        f"WAHA_API_KEY={waha_api}\n"
        f"WEBHOOK_SECRET={webhook}\n"
        f"WAHA_DASHBOARD_USER={waha_dash_user}\n"
        f"WAHA_DASHBOARD_PASSWORD={waha_dash_pw}\n"
    )

    env_backend = (
        f"ENVIRONMENT=production\n"
        f"SUPABASE_URL=https://db.{dom}\n"
        f"SUPABASE_PUBLIC_URL=https://db.{dom}\n"
        f"SUPABASE_SERVICE_ROLE_KEY={service}\n"
        f"JWT_SECRET={backend_jwt}\n"
        f"ADMIN_EMAIL=admin@{dom}\n"
        f"ADMIN_PASSWORD={admin_pw}\n"
        f"AGENTE_EMAIL=agente@{dom}\n"
        f"AGENTE_PASSWORD={agente_pw}\n"
        f"PUBLICADOR_EMAIL=publicador@{dom}\n"
        f"PUBLICADOR_PASSWORD={publicador_pw}\n"
        f"FRONTEND_URL=https://{dom}\n"
        f"STORAGE_BUCKET=publicaciones\n"
        f"COMERCIOS_BUCKET=comercios\n"
        f"WEBHOOK_SECRET={webhook}\n"
        f"WAHA_BASE_URL=http://waha:3000\n"
        f"WAHA_API_KEY={waha_api}\n"
        f"OPENAI_API_KEY=\n"
    )

    with open(os.path.join(root, ".env"), "w", encoding="utf-8") as f:
        f.write(env_root)
    os.makedirs(os.path.join(root, "backend"), exist_ok=True)
    with open(os.path.join(root, "backend", ".env"), "w", encoding="utf-8") as f:
        f.write(env_backend)

    print("OK - escritos .env y backend/.env con secretos nuevos.\n")
    print("================ GUARDA ESTAS CREDENCIALES (no se vuelven a mostrar) ================")
    print(f"  Admin       ->  admin@{dom}       /  {admin_pw}")
    print(f"  Agente      ->  agente@{dom}      /  {agente_pw}")
    print(f"  Publicador  ->  publicador@{dom}  /  {publicador_pw}")
    print(f"  WAHA panel  ->  {waha_dash_user}  /  {waha_dash_pw}")
    print("=====================================================================================")
    print("NO pegues esta salida en ningun chat. Guardala en tu gestor de contrasenas.")


if __name__ == "__main__":
    main()
