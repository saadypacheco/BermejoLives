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
│   ├── docker-compose.prod.yml
│   └── .env
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
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```
Traefik pide los certificados de `uruku.bo`, `www`, `api`, `db` (y `waha`) solos.

## Paso 5 · Stack Reservalo (path `/tienda`, misma PWA)
```bash
cd /docker
git clone https://github.com/saadypacheco/reservalo.git reservalo
cd /docker/reservalo
```
**Cambios necesarios en el repo de Reservalo** (los preparo yo si querés — checklist):
1. `frontend/next.config.*`: `basePath` y `assetPrefix` de `/reservalo` → **`/tienda`**.
2. Traefik labels (compose de Reservalo):
   - Router tienda: `Host(\`uruku.bo\`) && PathPrefix(\`/tienda\`)`, `priority=1000`.
   - Router API: `Host(\`api.tienda.uruku.bo\`)`.
   - Router 301: `Host(\`tienda.uruku.bo\`)` → redirect a `https://uruku.bo/tienda`.
3. `SITE_URL=https://uruku.bo/tienda` y `NEXT_PUBLIC_API_URL=https://api.tienda.uruku.bo`.
4. Secretos propios de Reservalo (su base/JWT) — generados nuevos, no copiados de QA.

Deploy:
```bash
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```

### Cross-links entre los dos sitios (en ambos repos)
- Ficha de URUKU → producto: `https://uruku.bo/tienda/productos/{slug}`.
- Reservalo → ficha del local: `https://uruku.bo/comercios/{slug}`.

## Paso 6 · Migrar el único comercio
Al ser 1 solo, lo más simple:
- **Re-registrarlo** en prod desde `uruku.bo/autoregistro` (y volver a subir sus fotos).

O copiarlo tal cual desde QA (con leads/publicaciones/fotos) — pedí el SQL de
export/import puntual y te lo dejo.

## Paso 7 · Verificar
```bash
curl -I https://uruku.bo
curl -s https://api.uruku.bo/health
curl -s "https://db.uruku.bo/comercios?limit=1"
curl -I https://uruku.bo/tienda/productos
curl -I https://tienda.uruku.bo            # 301 → uruku.bo/tienda
```
A ojo: home + toggle de tema, `/mapa`, `/buscar`, `/tienda`, **instalar la PWA**
(debe ser **una sola** y cubrir `/` y `/tienda`), cross-links ficha ↔ producto.

## Paso 8 · Post-deploy
- **Publicador**: entrá a `uruku.bo/publicador` y cargá cotización, clima y las
  **redes sociales de URUKU** (así aparecen los íconos en la barra social).
- **Admin**: `uruku.bo/admin` (con `ADMIN_EMAIL`/`ADMIN_PASSWORD`).
- Confirmá que **QA quedó con las claves viejas** y prod con las nuevas (rotación hecha).
- (Opcional) Redirect 301 de `encontralo.store` → `uruku.bo` cuando decidas el cutover
  público — pero si querés dejar encontralo.store como QA, **no** lo redirijas.
