# Deploy a Hostinger (buscadonde.com)

Sigue el **RUNBOOK_DEPLOY_HOSTINGER.md** general. Acá solo los deltas de este proyecto.

- **PROYECTO** = `buscadonde` · **DOMINIO** = `buscadonde.com`
- Archivos ya versionados: `docker-compose.prod.yml`, `.env.prod.example`,
  `backend/.env.prod.example`.

## Diferencias clave vs el runbook

1. **Claves de Supabase Cloud:** usar las **legacy JWT** de *Settings → API*
   → `anon public` (NEXT_PUBLIC_SUPABASE_ANON_KEY) y `service_role`
   (SUPABASE_SERVICE_ROLE_KEY). (Las nuevas `sb_publishable/sb_secret` no las
   aceptan las libs pinneadas.)
2. **La app usa REST** (SUPABASE_URL + service_role), no `DATABASE_URL`.
   `DATABASE_URL` (Session pooler) se usa **solo** para correr las migraciones.
3. **Migraciones** en `supabase/migrations/*.sql` (no `backend/migrations`):
   ```bash
   cd /docker/buscadonde
   docker run --rm --env-file backend/.env -v "$PWD/supabase/migrations:/m" postgres:15 \
     bash -c 'for f in /m/*.sql; do echo ">>> $(basename "$f")"; psql "$DATABASE_URL" -v ON_ERROR_STOP=1 -f "$f" || exit 1; done'
   ```
4. **Extensiones:** solo `pgcrypto` (la crea `0001`). No hace falta habilitar nada
   a mano en Supabase.
5. **Sin "usuario dueño" auto-creado:** las credenciales admin/agente salen del
   `.env` (ADMIN_*, AGENTE_*). Las cuentas de comercio se crean por registro.
6. **Datos demo:** las migraciones traen comercios/ofertas de ejemplo (Importadora
   ABC, etc.). Para un lanzamiento limpio, después de migrar:
   ```bash
   docker run --rm --env-file backend/.env postgres:15 \
     psql "$DATABASE_URL" -c "delete from comercios where wa_jid like '%@c.us'; delete from comercio_usuarios;"
   ```
   (Mantiene zonas, **rubros** y **ciudades**, que son datos reales.)

## DNS (Hostinger): 3 registros A → IP del VPS
`@`, `www`, `api` → `<IP_VPS>`.

## Levantar
```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
docker compose -f docker-compose.prod.yml ps
```
buscadonde.com (front) · api.buscadonde.com (backend) · TLS automático por Traefik.
