# 🟢 Bermejo Live Market

> El ecosistema digital comercial de Bermejo (Bolivia, frontera con Argentina).
> **Todo lo que se vende en Bermejo, en tiempo real.**

Los comerciantes **publican ofertas, videos y novedades mandando un mensaje por
WhatsApp**. Un moderador aprueba. El contenido aprobado aparece al instante en un
**feed en vivo**. No es ecommerce ni directorio: se siente como una ciudad
comercial viva (TikTok + Google Maps + Mercado Libre + Instagram + Airbnb).

## 🏗️ Arquitectura

```
Comerciante ──WhatsApp──▶ WAHA ──webhook(HMAC)──▶ FastAPI ──▶ Supabase
                                                     │           (publicaciones: pendiente)
Moderador ──▶ /admin ──▶ FastAPI ──▶ Supabase (estado: aprobado)
                                         │
Comprador ◀── feed en vivo ◀── Supabase Realtime ◀──┘   (Next.js, anon + RLS)
```

- **`frontend/`** — Next.js 14 (App Router, Tailwind). Lee de Supabase (anon+RLS),
  feed en vivo con Realtime directo. Diseño dark premium portado del prototipo.
- **`backend/`** — FastAPI 3.12. Ingesta de WhatsApp (idempotente) + moderación
  (service_role). 
- **`supabase/migrations/`** — esquema: zonas, comercios, productos, publicaciones,
  wa_inbox + RLS + GRANTs + seed.
- **`infra/`** — docker-compose con WAHA (bridge WhatsApp).
- **`prototype/`** — prototipo HTML/CSS/JS original (referencia de diseño).

Decisión de stack y rationale: [`../architect-kb/decisions/2026-06-04-stack-bermejo.md`](../architect-kb/decisions/2026-06-04-stack-bermejo.md).
Metodología/estado: [`docs/architect-journey.md`](docs/architect-journey.md) · convenciones: [`AGENTS.md`](AGENTS.md).

## ▶️ Correr todo en Docker (recomendado)

El stack corre en Docker, como los demás proyectos. Supabase se levanta con su CLI
(patrón apops) y el backend + frontend en `docker compose`.

```bash
# 1) Supabase local (DB + Auth + Realtime + Studio) — puertos 5442x
npx supabase start          # primera vez baja imágenes; aplica migraciones
npx supabase status         # muestra URL + claves (anon/service_role legacy)

# 2) Backend + Frontend en Docker
cd infra
docker compose up -d --build

# (opcional) bridge de WhatsApp:
docker compose --profile whatsapp up -d
```

| Servicio | URL |
|----------|-----|
| App | http://localhost:3003 |
| Backend | http://localhost:8000/health |
| Supabase Studio (ver/editar DB) | http://localhost:54423 |

Manejo:
```bash
docker compose -f infra/docker-compose.yml ps        # estado
docker compose -f infra/docker-compose.yml logs -f   # logs
docker compose -f infra/docker-compose.yml down       # frenar app
npx supabase stop                                     # frenar Supabase
```

> **Networking:** Supabase corre en el host; los contenedores lo alcanzan por
> `host.docker.internal:54421` (SSR del front y backend), y el **navegador** por
> `localhost:54421` / `localhost:8000` (vars `NEXT_PUBLIC_*` horneadas en el build).
> Las claves locales son las **legacy JWT** de `supabase status -o env` (el CLI
> nuevo emite `sb_publishable/sb_secret`, que las libs pinneadas no aceptan).

## ▶️ Correr en local (sin Docker, modo dev con hot-reload)

### 1. Base de datos (Supabase)
```bash
# Con un proyecto Supabase (cloud o local) configurado:
npx supabase db push          # aplica supabase/migrations/0001..0003
```

### 2. Backend (FastAPI)
```bash
cd backend
cp .env.example .env          # completá SUPABASE_URL + SERVICE_ROLE_KEY
pip install -e .              # o: uv pip install -e .
uvicorn app.main:app --reload --port 8000
# Health: http://localhost:8000/health
```

### 3. Frontend (Next.js)
```bash
cd frontend
cp .env.example .env.local    # NEXT_PUBLIC_SUPABASE_URL + ANON_KEY + API_URL
npm install
npm run dev                   # http://localhost:3000
```
> Sin Supabase configurado, el front arranca igual con **datos demo** (degradación
> suave) para que veas el diseño. El feed en vivo y la moderación necesitan backend+DB.

### 4. WhatsApp real (opcional)
```bash
cd infra
cp .env.example .env
docker compose up -d          # levanta WAHA; escaneá el QR para vincular el número
```

## 📝 Publicar (comercios logueados + chatbot)

`/publicar` → login de comercio + **asistente conversacional** que arma la
publicación (oferta / video / novedad) paso a paso.

- Demo `abc@bermejolive.com` → comercio **confiable**: publica **directo, en vivo**.
- Demo `moda@bermejolive.com` → **no** confiable: va a **moderación**.
- Clave de ambos: `comercio1234`.

La misma regla aplica al canal WhatsApp: un comercio confiable que manda por
WhatsApp también publica directo. El flag `confiable` lo activa el admin.

## 🔑 Panel de moderación

`/admin` → demo: `admin@bermejolive.com` / `bermejo1234` (cambiá en `backend/.env`).
Aprobá / rechazá / pedí cambios sobre las publicaciones pendientes.

## 📋 Datos del comercio (vendedor)

Cada comercio registra y muestra: **WhatsApp** (obligatorio), teléfono, email,
**TikTok**, **Facebook**, **Instagram**, **sitio web**, **dirección + ubicación
(lat/lng)**, zona, logo, portada, plan y verificación. Ver `comercios` en
[`supabase/migrations/0001_init.sql`](supabase/migrations/0001_init.sql) y el
perfil en [`frontend/app/comercios/[slug]/page.tsx`](frontend/app/comercios/).

## 🚦 Estado

MVP de producción en construcción. Pendiente: Storage de imágenes entrantes,
publicación a TikTok (operador/API), pagos y suscripciones (F-007), alta
self-service de comercios con verificación. Detalle en `docs/architect-journey.md`.
