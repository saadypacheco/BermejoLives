# Deploy en QA (encontralo.store)

> **QA = el VPS actual.** Sirve para probar cambios antes de mandarlos a producción.
> Dominio: **encontralo.store** · repo en el VPS: **`/docker/buscadonde`**.
> Producción vive en otro VPS (ver [deploy-prod-nuevo-vps.md](deploy-prod-nuevo-vps.md)).

## Arquitectura del stack (QA)
Un solo VPS con Traefik + estos contenedores (`docker-compose.prod.yml`):

| Contenedor | Rol | Dominio |
|---|---|---|
| `buscadonde-frontend` | URUKU (Next.js) | `encontralo.store` (+ `www`) |
| `buscadonde-backend` | API (FastAPI) | `api.encontralo.store` |
| `buscadonde-postgres` | Base (Postgres 17) | — (red interna) |
| `buscadonde-postgrest` | REST sobre la base | `db.encontralo.store` |
| `buscadonde-waha` | Bridge WhatsApp | `waha.encontralo.store` |
| `reservalo-*` | Tienda (Reservalo) | `encontralo.store/tienda` |

Traefik enruta por dominio y emite los certificados (Let's Encrypt). La base es
**self-hosted** (Postgres + PostgREST en el mismo VPS), no Supabase Cloud.

---

## 1) Deploy de un cambio de código (lo habitual)

```bash
cd /docker/buscadonde
git pull
docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend
# si tocaste el backend, agregá 'backend':
# docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend backend
```

- El **frontend** hay que **rebuildearlo** siempre que cambien archivos del front
  o variables `NEXT_PUBLIC_*` (se hornean en el bundle).
- Verificá el commit que quedó: `git log -1 --oneline`.

## 2) Deploy con migración de base

Las migraciones nuevas **no se aplican solas** en una base que ya tiene datos
(`docker-entrypoint-initdb.d` solo corre en un volumen vacío). Se aplican a mano:

```bash
cd /docker/buscadonde
git pull
# Aplicar la/s migración/es nueva/s (ejemplo con la 0036):
docker exec -i buscadonde-postgres psql -U postgres -d postgres < supabase/migrations/0036_busqueda_comercios.sql
# Recargar el schema en PostgREST (para que exponga tablas/columnas nuevas):
docker exec buscadonde-postgres psql -U postgres -d postgres -c "NOTIFY pgrst, 'reload schema';"
# Rebuild de los servicios afectados:
docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend backend
```

> Las migraciones son idempotentes (`create ... if not exists`), pero **revisá**
> cada `.sql` antes de correrlo en QA. Si agregás una migración nueva al repo,
> corré también `bash selfhost/build-postgres-init.sh` para que un Postgres
> **nuevo** (ej. el VPS de prod) arranque completo.

## 3) Abrir/cerrar el sitio público (modo captura)

`NEXT_PUBLIC_MODO_CAPTURA` en el `.env`: `1` = solo `/bermejo` y `/admin`
(el resto "Próximamente"); `0` = sitio público abierto. Tras cambiarlo:

```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend
```

## 4) Verificar

```bash
curl -I https://encontralo.store            # 200, candado OK
curl -s https://api.encontralo.store/health # responde
curl -s "https://db.encontralo.store/comercios?limit=1"  # la base responde
```
Y a ojo: home, `/mapa`, `/buscar`, `/mi-comercio`, `/tienda` (Reservalo).

## 5) Ver logs / estado

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f --tail=100 frontend
docker compose -f docker-compose.prod.yml logs -f --tail=100 backend
```

## 6) Rollback

```bash
cd /docker/buscadonde
git log --oneline -5           # elegí el commit bueno
git checkout <commit>          # o: git reset --hard <commit>
docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend backend
git checkout main              # volvé a main cuando resuelvas
```
Una migración aplicada **no** se revierte con git — si una migración rompió algo,
hay que escribir el `.sql` inverso. Por eso QA existe: probá acá primero.

## Reservalo en QA
Reservalo es su propio repo/stack (`reservalo-frontend/-backend`). Se sirve en
`encontralo.store/tienda`. **Su compose es `docker-compose.yml`** (NO `.prod.yml`,
ese es el de URUKU) y está parametrizado por `${DOMAIN}` (que sale del `.env`:
`DOMAIN=encontralo.store`). Deploy desde su carpeta:
```bash
cd /docker/reservalo
git pull
# Rebuild frontend Y backend (la salida de Supabase tocó ambos). El compose
# ya trae el volumen reservalo_fotos y las envs FOTOS_* para el storage a disco.
docker compose --env-file .env up -d --build backend frontend
```
Tras el deploy sin-Supabase: el panel `encontralo.store/tienda/admin` pide login de
URUKU; para entrar como dueño-comprador, marcá tu usuario una vez:
`UPDATE usuarios SET rol='admin' WHERE id='<usuario_id de URUKU>';` (el admin de
plataforma con token URUKU rol=admin entra directo).

### Drift de esquema en QA (2026-08-16) — solo QA, NO prod
La base `reservalo-postgres` de QA se inicializó **antes** de que `postgres-init`
estuviera completo, y los init-scripts no se re-ejecutan sobre un volumen existente.
Faltaban la migración **016** (columna `productos.disponible`, `vendedor_id`, `moneda`,
tabla `vendedores`) y los **GRANTs** a `service_role`. Se parcheó a mano:
```sql
-- 016 idempotente
CREATE TABLE IF NOT EXISTS vendedores (id UUID PRIMARY KEY, nombre TEXT NOT NULL,
  slug TEXT UNIQUE NOT NULL, whatsapp TEXT, tipo TEXT NOT NULL DEFAULT 'minorista',
  activo BOOLEAN NOT NULL DEFAULT TRUE, moneda_default TEXT NOT NULL DEFAULT 'ARS',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW());
ALTER TABLE productos ADD COLUMN IF NOT EXISTS vendedor_id UUID REFERENCES vendedores(id);
ALTER TABLE productos ADD COLUMN IF NOT EXISTS moneda TEXT NOT NULL DEFAULT 'ARS';
ALTER TABLE productos ADD COLUMN IF NOT EXISTS disponible BOOLEAN NOT NULL DEFAULT TRUE;
-- grants de todo el esquema
GRANT ALL ON ALL TABLES IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO anon, authenticated;
NOTIFY pgrst, 'reload schema';
```
**Prod NO necesita esto**: arranca con volumen vacío → corre el `postgres-init`
actual completo (016 + `99-grants.sql` ya incluidos).
