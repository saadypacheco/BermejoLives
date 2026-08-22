# Deploy de PRODUCCIÓN en un VPS nuevo (uruku.bo + Reservalo)

> Levanta un VPS **nuevo y limpio** para producción: **URUKU** (ex Encontralo) en
> `uruku.bo` + **Reservalo** en `uruku.bo/tienda` (misma PWA, un solo origen).
> El VPS actual (encontralo.store) queda como **QA** (ver [deploy-qa.md](deploy-qa.md)).
>
> **Regla de oro:** este VPS arranca con **secretos nuevos** (rotamos los viejos, que
> quedaron expuestos). No copies claves del VPS de QA.

## Arquitectura objetivo

| URL | Sirve | Contenedor |
|---|---|---|
| `uruku.bo` (+ `www`) | URUKU (mapa/home) | `frontend` |
| `api.uruku.bo` | API de URUKU | `backend` |
| `db.uruku.bo` | PostgREST (base URUKU) | `postgrest` |
| `waha.uruku.bo` | WhatsApp bridge (opcional) | `waha` |
| `uruku.bo/tienda/...` | Reservalo (tienda) | `reservalo-frontend` |
| `api.tienda.uruku.bo` | API de Reservalo | `reservalo-backend` |
| `tienda.uruku.bo` | **301 → `uruku.bo/tienda`** (atajo) | (router Traefik) |

`uruku.com.bo`, `urucu.bo`, `urucu.com.bo` → **301 → `uruku.bo`** (se resuelve en el DNS/Cloudflare o en Traefik).

## Organización de directorios (multi-sitio)

Este VPS puede alojar **varios sitios**. Regla: **un Traefik compartido** (puerta de
entrada de todos) + **una carpeta por sitio**, cada una con su repo, su `.env`, sus
contenedores y su base **aislados**. Traefik reparte por **dominio**.

```
/docker/
├── traefik/            ← reverse proxy ÚNICO y compartido
│   ├── docker-compose.yml
│   └── acme.json       ← certificados de TODOS los dominios
├── uruku/              ← URUKU (uruku.bo)            · repo BermejoLives
│   ├── docker-compose.prod.yml
│   ├── .env
│   └── backend/.env
├── reservalo/          ← Reservalo (uruku.bo/tienda) · repo reservalo
│   ├── docker-compose.yml   ← (NO .prod.yml; su compose se llama docker-compose.yml)
│   ├── .env                 ← DOMAIN + secretos de la base self-host
│   └── backend/.env         ← SUPABASE_URL self-host + JWT_SECRET compartido con URUKU
└── <otrositio>/        ← futuro sitio (otro dominio)
```

**Cómo se conectan:** cada stack se engancha a la red externa **`traefik`** (por ahí
se enruta) y tiene además su red **`internal`** privada (base + backend) que nadie más
ve. Traefik saca los certificados de todos (un solo `acme.json`).

**4 reglas para que no choquen al sumar sitios:**
1. **Nombres de contenedor únicos** por sitio (`uruku-frontend`, `reservalo-frontend`, …).
2. **Nombres de router/service de Traefik únicos** en los labels (`uruku-fe`, `reservalo-fe`, …).
3. **No publicar puertos al host** (`ports:`) — Traefik enruta por la red interna → nunca hay choque de puertos.
4. **Un `.env` por sitio** (su `DOMAIN` y secretos). Bases y volúmenes quedan separados (Docker los prefija por carpeta).

**Sumar un sitio nuevo = 5 pasos:** (1) `git clone <repo> /docker/<sitio>` · (2) su `.env`
con `DOMAIN=` · (3) labels de Traefik con nombres únicos + su dominio · (4) DNS del dominio
→ IP del VPS · (5) `docker compose ... up -d --build` (Traefik detecta y saca el cert solo).

> Nota: los contenedores de URUKU se llaman `buscadonde-*` (codename interno, cosmético).
> No molesta mientras haya **una** instancia de URUKU. Reservalo usará `reservalo-*`.

---

## Paso 0 · Provisionar el VPS
- Hostinger (u otro), **Ubuntu 22.04**, mínimo **4 GB RAM / 2 vCPU** (corren 2 stacks + Traefik).
- Anotá la **IP pública** del VPS (hPanel → VPS → Overview).
- Entrá por SSH como `root`.

## Paso 1 · Base (Docker + git + firewall)
```bash
apt update && apt -y upgrade
curl -fsSL https://get.docker.com | sh          # Docker + compose plugin
apt -y install git
# Firewall: solo SSH + web
ufw allow 22/tcp && ufw allow 80/tcp && ufw allow 443/tcp && ufw --force enable
docker --version && docker compose version
```

## Paso 2 · Traefik (reverse proxy + certificados)
Traefik es compartido por los dos stacks. Se crea una sola vez.
```bash
mkdir -p /docker/traefik && cd /docker/traefik
touch acme.json && chmod 600 acme.json
docker network create traefik
```
Creá `/docker/traefik/docker-compose.yml`:

> ⚠️ **Compatibilidad Docker/Traefik:** con Docker Engine nuevo (29+), Traefik **v3.1
> falla** (`client version 1.24 is too old`) → no ve los contenedores → no emite certs.
> Usá una imagen actual (`traefik:latest` o una v3 reciente). Una vez corriendo, fijá la
> versión exacta con `docker exec traefik traefik version` para que no cambie sola.

```yaml
services:
  traefik:
    image: traefik:latest
    container_name: traefik
    restart: unless-stopped
    command:
      - --providers.docker=true
      - --providers.docker.exposedbydefault=false
      - --providers.docker.network=traefik
      - --entrypoints.web.address=:80
      - --entrypoints.websecure.address=:443
      # Redirige todo HTTP → HTTPS
      - --entrypoints.web.http.redirections.entrypoint.to=websecure
      - --entrypoints.web.http.redirections.entrypoint.scheme=https
      - --certificatesresolvers.letsencrypt.acme.httpchallenge=true
      - --certificatesresolvers.letsencrypt.acme.httpchallenge.entrypoint=web
      - --certificatesresolvers.letsencrypt.acme.email=TU_EMAIL@dominio.com
      - --certificatesresolvers.letsencrypt.acme.storage=/acme.json
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock:ro
      - ./acme.json:/acme.json
    networks: [traefik]
networks:
  traefik:
    external: true
```
```bash
docker compose -f /docker/traefik/docker-compose.yml up -d
```

## Paso 3 · DNS (Cloudflare recomendado para los .bo)
En **nic.bo**, delegá los *nameservers* de `uruku.bo` a **Cloudflare** (plan gratis).
En Cloudflare, zona `uruku.bo`, creá registros **A** → IP del VPS, en **"DNS only" (nube gris)**
(gris = Let's Encrypt valida por HTTP igual que hoy):

| Tipo | Nombre | Valor | Proxy |
|---|---|---|---|
| A | `@` | IP del VPS | DNS only |
| A | `www` | IP del VPS | DNS only |
| A | `api` | IP del VPS | DNS only |
| A | `db` | IP del VPS | DNS only |
| A | `tienda` | IP del VPS | DNS only |
| A | `api.tienda` | IP del VPS | DNS only |
| A | `db.tienda` | IP del VPS | DNS only |
| A | `waha` | IP del VPS | DNS only (opcional) |

**Redirect de los otros 3 dominios** (`uruku.com.bo`, `urucu.bo`, `urucu.com.bo`):
agregalos como zonas en Cloudflare y creá una **Redirect Rule** 301 → `https://uruku.bo/$1`,
o apuntá su A al VPS y agregá un router de redirect en Traefik.

> Antes de deployar, confirmá que resuelven: `nslookup uruku.bo`, `nslookup api.uruku.bo`,
> `nslookup db.uruku.bo`, `nslookup api.tienda.uruku.bo`.

## Paso 4 · Stack URUKU
```bash
mkdir -p /docker && cd /docker
git clone https://github.com/saadypacheco/BermejoLives.git uruku
cd /docker/uruku
```

### 4a · Generar secretos NUEVOS
```bash
# En tu compu (o donde tengas python + pyjwt): imprime los secretos ya con el dominio
python selfhost/generar_secretos.py uruku.bo
python selfhost/generar_secretos_waha.py     # WAHA_API_KEY / WEBHOOK_SECRET / dashboard
openssl rand -hex 32                          # para JWT_SECRET del backend
```

### 4b · `.env` de la raíz (`/docker/uruku/.env`)
```
DOMAIN=uruku.bo
MODO_CAPTURA=0
# --- de generar_secretos.py uruku.bo ---
POSTGRES_PASSWORD=...
AUTHENTICATOR_PASSWORD=...
PGRST_JWT_SECRET=...
NEXT_PUBLIC_SUPABASE_URL=https://db.uruku.bo
NEXT_PUBLIC_SUPABASE_ANON_KEY=...
# --- de generar_secretos_waha.py (si vas a usar WhatsApp) ---
WAHA_API_KEY=...
WEBHOOK_SECRET=...
WAHA_DASHBOARD_USER=...
WAHA_DASHBOARD_PASSWORD=...
```

### 4c · `backend/.env` (`/docker/uruku/backend/.env`)
```
ENVIRONMENT=production
SUPABASE_URL=https://db.uruku.bo
SUPABASE_PUBLIC_URL=https://db.uruku.bo
SUPABASE_SERVICE_ROLE_KEY=...     # de generar_secretos.py (SECRETO)
JWT_SECRET=...                    # openssl rand -hex 32
ADMIN_EMAIL=admin@uruku.bo
ADMIN_PASSWORD=...                # elegí una fuerte
AGENTE_EMAIL=agente@uruku.bo
AGENTE_PASSWORD=...
PUBLICADOR_EMAIL=publicador@uruku.bo
PUBLICADOR_PASSWORD=...
FRONTEND_URL=https://uruku.bo
STORAGE_BUCKET=publicaciones
COMERCIOS_BUCKET=comercios
WEBHOOK_SECRET=...                # el mismo que en el .env raíz
WAHA_BASE_URL=http://waha:3000
WAHA_API_KEY=...                  # el mismo que en el .env raíz
OPENAI_API_KEY=                   # opcional (transcripción)
```

### 4d · Base fresca + deploy
La base **se inicializa sola** la primera vez (corre `selfhost/postgres-init/*.sql`
= todas las migraciones, sin datos de ejemplo). Aseguráte de que estén al día:
```bash
bash selfhost/build-postgres-init.sh    # sincroniza postgres-init con supabase/migrations
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=prod \
  docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```
Traefik pide los certificados de `uruku.bo`, `www`, `api`, `db` (y `waha`) solos.

> **Versión horneada:** el prefijo `GIT_SHA=… APP_ENV=prod` hace que el build guarde
> el commit + ambiente, visibles en el **footer** y en `GET /version`. Usalo **siempre**
> (también en los redeploys de abajo); sin él el commit cae a `dev`.

### 4e · Redeploy rutinario de PROD (un cambio de código ya mergeado)
```bash
cd /docker/uruku && git pull
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=prod \
  docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend
# agregá 'backend' al final si tocaste el backend. Luego verificá:
curl -s https://uruku.bo/version   # → {"commit":"<sha>","env":"prod",...}
```
La versión semántica (`1.0.0`) se sube a mano en `frontend/package.json` en cada hito.

### 4f · Si el deploy incluye una MIGRACIÓN — recargar PostgREST

**Obligatorio** cuando la migración agrega, renombra o rehace una columna o una
tabla. PostgREST cachea el esquema al arrancar y no se entera solo: hasta que se
reinicie, toda consulta que use lo nuevo falla.

```bash
cd /docker/uruku
docker compose -f docker-compose.prod.yml exec -T postgres   psql -U postgres -d postgres -f - < supabase/migrations/00XX_lo_que_sea.sql
docker compose -f docker-compose.prod.yml restart postgrest     # ← el paso que se olvida
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=prod   docker compose -f docker-compose.prod.yml --env-file .env up -d --build frontend backend
```

Cómo se ve cuando falta: el backend devuelve `PGRST204 · Could not find the 'X'
column of 'Y' in the schema cache`, o un 500 en cualquier endpoint que use
selects embebidos (`comercios(nombre, slug)`), porque la caché de relaciones
también quedó vieja. Desde el navegador puede aparecer disfrazado de error de
CORS o, en la app de campo, como "no tenés internet".

Nos pasó tres veces: con `comercio_numeros`, con `comercios.codigo` y con el
rehecho de `busqueda`. Cada una costó entre media hora y una hora de diagnóstico
buscando el problema en el lugar equivocado.

## Paso 5 · Stack Reservalo (path `/tienda`, base self-host, SIN Supabase)

> ✅ **Estado 2026-08-16:** Reservalo ya **no usa Supabase Cloud**. Trae su **propia base
> self-host** (Postgres + PostgREST) dentro del compose, **auth por el token de URUKU**
> (mismo `jwt_secret`, mismo origen), **imágenes/comprobantes a disco** (`/fotos`, volumen
> `reservalo_fotos`) y el **chat retirado**. El **mismo código** sirve prod y QA según `DOMAIN`.
> Su compose se llama **`docker-compose.yml`** (no `.prod.yml`).

**DNS (Cloudflare):** además de `tienda` y `api.tienda`, agregá **`db.tienda`** (A → IP del
VPS, gris). Confirmá: `nslookup api.tienda.uruku.bo` y `nslookup db.tienda.uruku.bo`.

**Prerequisito:** URUKU ya desplegado → existe `/docker/uruku/backend/.env` con su `JWT_SECRET`
(Reservalo comparte ese valor para validar el token del comprador).

```bash
cd /docker
git clone https://github.com/saadypacheco/reservalo.git reservalo
cd /docker/reservalo

# Genera .env + backend/.env de Reservalo, COMPARTIENDO el jwt_secret de URUKU
# y con secretos NUEVOS para su base self-host. Necesita PyJWT:
apt install -y python3-jwt || pip3 install pyjwt
python3 selfhost/init_reservalo_env.py uruku.bo "$(grep '^JWT_SECRET=' /docker/uruku/backend/.env | cut -d= -f2-)"

# (opcional) sincronizar postgres-init con las migraciones actuales del repo
bash selfhost/build-postgres-init.sh

# Levantar. La base self-host se inicializa sola la 1ra vez (corre postgres-init
# COMPLETO → trae 016 + grants, sin el drift que hubo en QA).
docker compose --env-file .env up -d --build
```

Traefik saca solos los certs de `api.tienda.uruku.bo`, `db.tienda.uruku.bo` y `tienda.uruku.bo`.

### 5a · Conectar URUKU → Reservalo (para que URUKU cree productos en la tienda)
El script imprime 3 líneas (`TIENDA_API_URL`, `TIENDA_API_SECRET`, `ADMIN_SYNC_SECRET`).
Pegalas en `/docker/uruku/backend/.env` y rebuildeá el backend de URUKU (deja el modo STUB):
```bash
cd /docker/uruku    # tras agregar las 3 líneas al backend/.env
docker compose -f docker-compose.prod.yml --env-file .env up -d --build backend
```

### 5b · Bootstrap del admin de la tienda
El dueño entra logueándose en URUKU (WhatsApp) y marcándose admin en la base de Reservalo, una vez.
El `id` es su `usuario_id` de URUKU (F12 en el navegador:
`JSON.parse(atob(localStorage.bermejo_usuario_token.split('.')[1])).usuario_id`):
```bash
docker exec -i reservalo-postgres psql -U postgres -d postgres -c \
 "INSERT INTO usuarios (id, whatsapp, rol) VALUES ('<usuario_id>', '<whatsapp>', 'admin') ON CONFLICT (id) DO UPDATE SET rol='admin';"
```
(El admin de plataforma, con token URUKU rol=admin, entra directo sin este paso.)

### Cross-links entre los dos sitios (ya en el código)
- Ficha/buscador de URUKU → tienda: `${DOMAIN}/tienda/productos/...` (const `RESERVALO_URL="/tienda"`).
- Reservalo → sitio URUKU: `NEXT_PUBLIC_ENCONTRALO_URL=https://${DOMAIN}` (Navbar).

## Paso 6 · Migrar el único comercio
Al ser 1 solo, lo más simple:
- **Re-registrarlo** en prod desde `uruku.bo/autoregistro` (y volver a subir sus fotos).

O copiarlo tal cual desde QA (con leads/publicaciones/fotos) — pedí el SQL de
export/import puntual y te lo dejo.

## Paso 7 · Verificar
```bash
curl -I https://uruku.bo
curl -s https://uruku.bo/version              # {"commit":"<sha>","env":"prod",...}
curl -s https://api.uruku.bo/health
curl -s "https://db.uruku.bo/comercios?limit=1"
curl -I https://uruku.bo/tienda/productos
curl -I https://tienda.uruku.bo               # 301 → uruku.bo/tienda
curl -s https://api.tienda.uruku.bo/health    # backend Reservalo → {"status":"ok"}
curl -s "https://api.tienda.uruku.bo/productos/" | head -c 200   # 200 (lista, aunque vacía)
```
A ojo: home + toggle de tema, `/mapa`, `/buscar`, `/tienda`, **instalar la PWA**
(debe ser **una sola** y cubrir `/` y `/tienda`), cross-links ficha ↔ producto.

## Paso 8 · Post-deploy
- **Publicador**: entrá a `uruku.bo/contenido` y cargá cotización, clima y las
  **redes sociales de URUKU** (así aparecen los íconos en la barra social).
- **Admin**: `uruku.bo/admin` (con `ADMIN_EMAIL`/`ADMIN_PASSWORD`).
- Confirmá que **QA quedó con las claves viejas** y prod con las nuevas (rotación hecha).
- (Opcional) Redirect 301 de `encontralo.store` → `uruku.bo` cuando decidas el cutover
  público — pero si querés dejar encontralo.store como QA, **no** lo redirijas.
