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

> **Si el cambio trae una migración**: después de correrla hay que reiniciar
> PostgREST (`docker compose -f docker-compose.prod.yml restart postgrest`).
> Cachea el esquema al arrancar y, sin ese reinicio, toda consulta que use la
> columna o tabla nueva falla — a veces disfrazado de error de CORS o de "sin
> internet". Ver la sección 4f del runbook de prod.

## 1) Deploy de un cambio de código (lo habitual)

> **Siempre** con el prefijo `GIT_SHA=… APP_ENV=qa` — así el build hornea la versión
> (commit + ambiente) y se puede verificar con `GET /version`. Sin ese prefijo el
> commit cae a `dev` y no sabés qué está corriendo.

```bash
cd /docker/buscadonde
git pull
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=qa \
  docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend
# si tocaste el backend, agregá 'backend' al final:
# GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=qa \
#   docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend backend
```

- El **frontend** hay que **rebuildearlo** siempre que cambien archivos del front
  o variables `NEXT_PUBLIC_*` (se hornean en el bundle).
- Verificá qué build quedó corriendo (commit + ambiente + fecha de build):
  ```bash
  curl -s https://encontralo.store/version
  # → {"version":"1.0.0","commit":"<sha>","buildTime":"...","env":"qa"}
  ```
  También se ve en el **footer** del sitio (`v1.0.0 · qa · <sha> · <fecha>`).
- La versión semántica (`1.0.0`) se sube a mano en `frontend/package.json` en cada hito.

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
# Rebuild de los servicios afectados (con la versión horneada):
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=qa \
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
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=qa \
  docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend
```

## 4) Verificar

```bash
curl -I https://encontralo.store            # 200, candado OK
curl -s https://encontralo.store/version     # {"commit":"<sha>","env":"qa",...}
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

---

## Clonar la base de PRODUCCIÓN en QA

Para probar con volumen real (y de paso **verificar que el backup restaura**,
que es la única forma de saber que sirve). Reemplaza la base de QA entera.

> **Antes de empezar.** QA queda con los datos reales: nombres, teléfonos y
> ubicaciones de comercios de verdad. Dos consecuencias:
> - Si alguien toca "WhatsApp" en QA, **le escribe a un comerciante real**.
> - QA no se indexa desde `app/robots.ts` (bloquea salvo `APP_ENV=prod`), así
>   que asegurate de que el frontend de QA esté construido **sin** ese prefijo.

### 1. Backup fresco en prod

```bash
# en PROD
/docker/backup.sh
ls -lh /docker/backups/buscadonde-postgres-*.sql.gz | tail -1
md5sum /docker/backups/buscadonde-postgres-<STAMP>.sql.gz    # anotar
```

### 2. Averiguar las IPs

Los nombres `srv…` son internos de Hostinger y los dominios pueden estar detrás
de Cloudflare (ahí SSH no llega, porque el dominio resuelve a Cloudflare y no al
VPS). Se usan las IPs:

```bash
curl -s ifconfig.me      # correr en PROD y anotar
curl -s ifconfig.me      # correr en QA y anotar
```

### 3. Copiar el archivo

**Opción A — directo de prod a QA** (una sola orden, desde la consola de prod):

```bash
# en PROD
scp /docker/backups/buscadonde-postgres-<STAMP>.sql.gz root@<IP_QA>:/tmp/
```

Pide la contraseña de root de QA. Si el servidor rechaza la contraseña es porque
QA tiene el login por clave desactivado: usar la opción B.

**Opción B — haciendo escala en tu máquina:**

```bash
# en TU MÁQUINA
scp root@<IP_PROD>:/docker/backups/buscadonde-postgres-<STAMP>.sql.gz .
scp buscadonde-postgres-<STAMP>.sql.gz root@<IP_QA>:/tmp/
```

**Verificar que llegó entero** — un archivo cortado restaura una base a medias
sin avisar:

```bash
# en QA
md5sum /tmp/buscadonde-postgres-<STAMP>.sql.gz     # tiene que dar igual que en prod
gunzip -t /tmp/buscadonde-postgres-<STAMP>.sql.gz && echo "gzip íntegro"
```

### 4. Restaurar

```bash
# en QA
cd /docker/buscadonde
docker compose -f docker-compose.prod.yml stop frontend backend postgrest

# La base se borra y se crea de cero. `template1` es la conexión de
# mantenimiento: no se puede borrar la base a la que uno está conectado.
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d template1 -c "drop database postgres;"
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d template1 -c "create database postgres;"

gunzip -c /tmp/buscadonde-postgres-<STAMP>.sql.gz | \
  docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d postgres

docker compose -f docker-compose.prod.yml start postgrest backend frontend
docker compose -f docker-compose.prod.yml restart postgrest   # cachea el esquema al arrancar
```

Los roles (`service_role`, `anon`, `authenticated`) son del CLÚSTER, no de la
base, así que sobreviven al borrado y no hay que recrearlos.

### 5. Verificar

```bash
docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d postgres -c \
"select (select count(*) from comercios where activo)      as comercios,
        (select count(*) from rubro_palabras)              as palabras,
        (select count(*) from mapa_adornos)                as adornos,
        (select count(*) from producto_sinonimos)          as sinonimos;"
```

Los números tienen que coincidir con los de prod. Después, abrir
`encontralo.store` y ver el mapa con los comercios.

**Las fotos NO viajan en el dump**: viven en el volumen `comercio_fotos`, no en
la base. Las fichas de QA van a quedar sin imagen. Para probar el mapa alcanza;
si hacen falta:

```bash
# en PROD
docker run --rm -v uruku_comercio_fotos:/d -v /tmp:/b alpine \
  tar czf /b/fotos.tgz -C /d .
# copiar fotos.tgz a QA y, en QA:
docker run --rm -v buscadonde_comercio_fotos:/d -v /tmp:/b alpine \
  tar xzf /b/fotos.tgz -C /d
```

(El nombre real del volumen sale de `docker volume ls | grep fotos`.)
