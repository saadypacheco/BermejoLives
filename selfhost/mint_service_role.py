"""Emite un JWT service_role a partir de un PGRST_JWT_SECRET ya existente.

Uso (en el VPS, para no tener que pegar el secret en ningún lado):
    cd /docker/buscadonde
    PGRST_JWT_SECRET=$(grep PGRST_JWT_SECRET .env | cut -d= -f2-) python3 selfhost/mint_service_role.py

Sirve para recuperar/regenerar el service_role key si se perdió, sin tener
que rotar el PGRST_JWT_SECRET (que invalidaría también el anon key ya
horneado en el frontend).
"""
import os
import time

import jwt

secret = os.environ["PGRST_JWT_SECRET"]
exp = int(time.time()) + 20 * 365 * 24 * 3600
token = jwt.encode({"role": "service_role", "iss": "encontralo-selfhost", "exp": exp}, secret, algorithm="HS256")
print(f"SUPABASE_SERVICE_ROLE_KEY={token}")
