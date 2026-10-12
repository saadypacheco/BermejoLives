"""Genera los secretos para el self-host de Postgres+PostgREST.

Uso:
    python generar_secretos.py

Imprime lo necesario para pegar en dos archivos del VPS:
  - .env (raíz): POSTGRES_PASSWORD, AUTHENTICATOR_PASSWORD, PGRST_JWT_SECRET,
    NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY (JWT anon,
    público — se hornea en el bundle del frontend, no es secreto).
  - backend/.env: SUPABASE_SERVICE_ROLE_KEY (JWT service_role, SECRETO —
    bypassa RLS, solo lo usan los backends) y CLAVE_PEPPER (pepper del hash de las
    claves de Mi comercio, SECRETO).

Corré esto UNA sola vez por proyecto (Encontralo). Si se re-corre después
de tener datos reales, invalida los tokens ya emitidos (no rompe nada,
pero si algún cliente cacheó el anon key viejo, hay que asegurarse de
haber redeployado el frontend con el nuevo antes de rotar).
"""
import secrets
import sys
import time

import jwt

JWT_TTL_AÑOS = 20  # el anon key vive "para siempre" (se hornea en el build del frontend)


def main() -> None:
    # Dominio del ambiente: uruku.bo (prod), encontralo.store (QA), etc.
    dominio = sys.argv[1] if len(sys.argv) > 1 else "encontralo.store"

    jwt_secret = secrets.token_urlsafe(48)
    clave_pepper = secrets.token_urlsafe(48)
    authenticator_password = secrets.token_urlsafe(32)
    postgres_password = secrets.token_urlsafe(32)

    exp = int(time.time()) + JWT_TTL_AÑOS * 365 * 24 * 3600
    iss = f"{dominio}-selfhost"
    anon_token = jwt.encode({"role": "anon", "iss": iss, "exp": exp}, jwt_secret, algorithm="HS256")
    service_token = jwt.encode({"role": "service_role", "iss": iss, "exp": exp}, jwt_secret, algorithm="HS256")

    print(f"# Secretos para el ambiente: {dominio}")
    print("# --- pegar en el .env de la raíz (junto a docker-compose.prod.yml) ---")
    print(f"POSTGRES_PASSWORD={postgres_password}")
    print(f"AUTHENTICATOR_PASSWORD={authenticator_password}")
    print(f"PGRST_JWT_SECRET={jwt_secret}")
    print(f"NEXT_PUBLIC_SUPABASE_URL=https://db.{dominio}")
    print(f"NEXT_PUBLIC_SUPABASE_ANON_KEY={anon_token}")
    print()
    print("# --- pegar en backend/.env (reemplaza el SUPABASE_SERVICE_ROLE_KEY viejo) ---")
    print(f"SUPABASE_SERVICE_ROLE_KEY={service_token}")
    print("# Pepper de las claves de Mi comercio (core/clave_comercio.py). SECRETO del backend; no lo")
    print("# cambies después de ponerlo: las claves guardadas con el pepper viejo dejarían de servir.")
    print(f"CLAVE_PEPPER={clave_pepper}")


if __name__ == "__main__":
    main()
