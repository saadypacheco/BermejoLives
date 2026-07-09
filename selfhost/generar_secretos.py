"""Genera los secretos para el self-host de Postgres+PostgREST.

Uso:
    python generar_secretos.py

Imprime lo necesario para pegar en dos archivos del VPS:
  - .env (raíz): POSTGRES_PASSWORD, AUTHENTICATOR_PASSWORD, PGRST_JWT_SECRET,
    NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY (JWT anon,
    público — se hornea en el bundle del frontend, no es secreto).
  - backend/.env: SUPABASE_SERVICE_ROLE_KEY (JWT service_role, SECRETO —
    bypassa RLS, solo lo usan los backends).

Corré esto UNA sola vez por proyecto (Encontralo). Si se re-corre después
de tener datos reales, invalida los tokens ya emitidos (no rompe nada,
pero si algún cliente cacheó el anon key viejo, hay que asegurarse de
haber redeployado el frontend con el nuevo antes de rotar).
"""
import secrets
import time

import jwt

JWT_TTL_AÑOS = 20  # el anon key vive "para siempre" (se hornea en el build del frontend)


def main() -> None:
    jwt_secret = secrets.token_urlsafe(48)
    authenticator_password = secrets.token_urlsafe(32)
    postgres_password = secrets.token_urlsafe(32)

    exp = int(time.time()) + JWT_TTL_AÑOS * 365 * 24 * 3600
    anon_token = jwt.encode({"role": "anon", "iss": "encontralo-selfhost", "exp": exp}, jwt_secret, algorithm="HS256")
    service_token = jwt.encode({"role": "service_role", "iss": "encontralo-selfhost", "exp": exp}, jwt_secret, algorithm="HS256")

    print("# --- pegar en el .env de la raíz (junto a docker-compose.prod.yml) ---")
    print(f"POSTGRES_PASSWORD={postgres_password}")
    print(f"AUTHENTICATOR_PASSWORD={authenticator_password}")
    print(f"PGRST_JWT_SECRET={jwt_secret}")
    print("NEXT_PUBLIC_SUPABASE_URL=https://db.encontralo.store")
    print(f"NEXT_PUBLIC_SUPABASE_ANON_KEY={anon_token}")
    print()
    print("# --- pegar en backend/.env (reemplaza el SUPABASE_SERVICE_ROLE_KEY viejo) ---")
    print(f"SUPABASE_SERVICE_ROLE_KEY={service_token}")


if __name__ == "__main__":
    main()
