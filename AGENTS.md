# AGENTS.md — Bermejo Live Market

> Guía para agentes y devs. Ecosistema comercial de Bermejo (frontera BO/AR).
> Metodología SDD (ver `docs/architect-journey.md`). Stack y decisiones en el
> ADR `architect-kb/decisions/2026-06-04-stack-bermejo.md`.

## 1. Qué es

Plataforma donde **los comerciantes publican ofertas / videos / novedades
enviando un mensaje de WhatsApp**; un moderador aprueba; el contenido aprobado
aparece en un **feed en vivo**. Además: perfiles de comercio con todos sus datos
(WhatsApp, TikTok, Facebook, Instagram, web, ubicación), catálogos, mapa
conceptual y panel de moderación. **No** es ecommerce (no hay checkout: el cierre
es por WhatsApp), **no** es directorio.

## 2. Stack

| Capa | Tech |
|------|------|
| Frontend | Next.js 14 App Router + TypeScript + Tailwind (`frontend/`) |
| Backend | FastAPI + Python 3.12 + Pydantic v2 + structlog (`backend/`) |
| BaaS | Supabase (Postgres + Auth + Storage + Realtime) (`supabase/`) |
| Bridge WhatsApp | WAHA (Docker, NOWEB) (`infra/`) |
| Salida WhatsApp | links `wa.me` |
| Videos | NO se hostean: link a TikTok |

## 3. Arquitectura (reparto de responsabilidades)

- **FastAPI = ingesta + escrituras** (service_role). Webhook de WAHA →
  `app/services/ingest.py` → crea `publicacion` `estado='pendiente'`. Moderación
  (aprobar/rechazar/cambios) también vía FastAPI con JWT de admin.
- **Next.js = lectura** vía Supabase **anon + RLS**, y **Realtime directo** para
  el feed (`components/live-feed.tsx`). El front **nunca** usa service_role.

## 4. Flujos de publicación

Dos canales, misma regla de confianza:

```
A) WhatsApp:  Comerciante → WAHA → POST /ingest/webhook (HMAC)
              → wa_inbox (idempotente) → upsert comercio por número
B) Chatbot:   Comercio logueado → /publicar (chatbot) → POST /comercio/publicar

Regla:  comercio.confiable = true  → estado 'aprobado' (publica DIRECTO)
        comercio.confiable = false → estado 'pendiente' (cola de moderación)

Moderador → /admin → aprobar → estado 'aprobado'
  → Supabase Realtime (INSERT/UPDATE estado=aprobado) → feed en vivo
```

- Cuentas de comercio: tabla `comercio_usuarios` + JWT propio (`rol='comercio'`,
  lleva `comercio_id`). Login `/auth/comercio/login`. El admin marca `confiable`.

## 5. Modelo de datos (`supabase/migrations/`)

- `zonas` · `comercios` (todos los datos del vendedor) · `productos` ·
  `publicaciones` (el feed + moderación) · `wa_inbox` (crudo) · vista `feed_publico`.
- **Soft-delete** con flag `activo` en todo (pattern KB). Nunca DELETE físico.
- **RLS + GRANTs explícitos** en cada migración (lessons KB; sin GRANT → error 42501).

## 6. Convenciones (idénticas a mentorcomercial / tienda)

- **Frontend:** componentes PascalCase, hooks `use*`, `'use client'` mínimo,
  Tailwind + clases del design system (`app/styles/`).
- **Backend:** archivos/funciones snake_case, clases PascalCase, schemas
  `NombreCreate/Update/Response`, `HTTPException` en español, structlog con
  eventos snake_case.
- **DB:** snake_case, tablas en plural, FKs `<tabla>_id`, comentarios en español.
- **Idioma:** comentarios/docstrings/errores en español; identificadores en inglés.

## 7. Reglas críticas (KB lessons)

1. `SUPABASE_SERVICE_ROLE_KEY` **nunca** en el frontend. Solo `backend/.env`.
2. **GRANTs explícitos** en cada migración (Supabase Cloud).
3. **RLS activo** en toda tabla; el público solo ve `comercios.activo` y
   `publicaciones.estado='aprobado'`.
4. **Idempotencia** de ingesta por `wa_message_id`.
5. **Realtime directo** desde el front, no proxy por FastAPI.
6. **Soft-delete** siempre; queries filtran `activo = true`.
7. WAHA en **red privada** + webhook **firmado (HMAC)**; usar número de WhatsApp
   **dedicado/descartable** (WAHA es bridge no-oficial).
8. `npx supabase ...` (no el binario cacheado).
9. Catálogo/perfil con **SSG + ISR** (`revalidate`), no SSR puro.
10. `/api/health` (front) y `/health` (back) para debug remoto.

## 8. Correr local

Ver `README.md`. Resumen: `supabase db push` → `backend` (uvicorn) →
`frontend` (`npm run dev`) → opcional `infra` (WAHA) para WhatsApp real.

## 9. Estado / próximos pasos

Fase actual y pendientes en `docs/architect-journey.md`. Features candidatas
F-000..F-007. Falta cablear: Storage de imágenes entrantes, publicación a TikTok,
pagos (F-007), alta self-service de comercios con verificación.
