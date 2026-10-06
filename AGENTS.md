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
| Base | Postgres + PostgREST self-hosted en el VPS (`selfhost/`; migraciones en `supabase/migrations/`). Sin Auth, Storage ni Realtime de Supabase: las fotos van al disco del backend |
| Bridge WhatsApp | WAHA (Docker, NOWEB) (`infra/`) |
| Salida WhatsApp | links `wa.me` |
| Videos | NO se hostean: link a TikTok |

## 3. Arquitectura (reparto de responsabilidades)

- **FastAPI = ingesta + escrituras** (service_role). Webhook de WAHA →
  `app/services/ingest.py` → identifica comercio (por grupo atado, número conocido,
  código en mensaje) → crea `publicacion` `estado='pendiente'` o `'aprobado'`
  (según confiable). Moderación (aprobar/rechazar/cambios) también vía FastAPI
  con JWT de admin. Si no se identifica el comercio, el mensaje queda en
  `wa_inbox` como `sin_comercio` y no crea nada.
- **Next.js = lectura** vía PostgREST (cliente `supabase-js`) con **anon + RLS**.
  No hay Realtime: el feed se lee al cargar la página. El front **nunca** usa
  service_role. Componentes borrados
  en limpieza (6/10): `live-feed.tsx`, `mobile-home.tsx`, `home-map.tsx`,
  `search-hero.tsx`.

## 4. Flujos de publicación

Cuatro canales de entrada, misma regla de confianza:

```
A) Grupo WhatsApp:   Comerciante → grupo (atado a comercio) → WAHA → webhook
                     → identifica por grupo atado → publicacion

B) Chat 1-a-1 código: Comerciante → CONFIRMAR-XXXXXX o URUKU-XXXX →
                     WAHA → webhook → identifica por código → publicacion

C) Chatbot/Cuenta:   Comercio logueado → /comercio/publicar → POST con foto/texto
                     → publicacion

D) Explorador:       Explorador (67677803) → URUKU-XXXX + foto →
                     WAHA → webhook → identifica por código →
                     publicacion A NOMBRE DEL COMERCIO (no ficticio)

Regla:  comercio.confiable = true  → estado 'aprobado' (DIRECTO)
        comercio.confiable = false → estado 'pendiente' (cola de moderación)
        EXCEPTO explorador → SIEMPRE a cola (identidad_origen = 'explorador')

Sin comercio identificado → entra en wa_inbox como 'sin_comercio' (NO se crea publicacion)

Moderador → /admin › Publicaciones → aprobar/rechazar/cambios → estado 'aprobado'
  → Supabase (INSERT/UPDATE estado=aprobado) → RLS → aparece en feed público
```

- **Cuentas de comercio:** tabla `comercio_usuarios` + JWT propio (`rol='comercio'`,
  lleva `comercio_id`). **Entrada:** celular + clave de 6 números (lo normal), o
  WhatsApp + confirmación (primera vez / olvido de clave). El admin marca
  `confiable`.

## 5. Modelo de datos (`supabase/migrations/`)

- `zonas` · `comercios` (todos los datos del vendedor) · `productos` ·
  `publicaciones` (el feed + moderación) · `wa_inbox` (crudo) · vista `feed_publico`.
- **Soft-delete** con flag `activo` en todo (pattern KB). Nunca DELETE físico.
- **RLS + GRANTs explícitos** en cada migración (lessons KB; sin GRANT → error 42501).

## 6. Convenciones (idénticas a mentorcomercial / tienda)

- **Frontend:** componentes PascalCase, hooks `use*`, `'use client'` mínimo,
  Tailwind + clases del design system (`app/styles/`).
- **Íconos: nunca un emoji.** Todos salen de `components/ic.tsx`
  (`<Ic n="ofertas" />`, `<IcRubro slug={...} />`): Phosphor duotono, como fija
  el manual de identidad. Un emoji lo dibuja el sistema operativo, así que la
  marca se ve distinta en cada teléfono. Clave nueva → agregarla al catálogo y
  correr `npm run iconos` (regenera `lib/iconos-dibujos.ts`). Los pines del
  mapa usan `lib/iconos-mapa.ts`, que es lo mismo en texto porque Leaflet arma
  el pin con HTML.
- **Backend:** archivos/funciones snake_case, clases PascalCase, schemas
  `NombreCreate/Update/Response`, `HTTPException` en español, structlog con
  eventos snake_case.
- **DB:** snake_case, tablas en plural, FKs `<tabla>_id`, comentarios en español.
- **Idioma:** comentarios/docstrings/errores en español; identificadores en inglés.

## 7. Reglas críticas (KB lessons)

1. `SUPABASE_SERVICE_ROLE_KEY` **nunca** en el frontend. Solo `backend/.env`.
2. **GRANTs explícitos** en cada migración (sin GRANT, PostgREST contesta 42501).
3. **RLS activo** en toda tabla; el público solo ve `comercios.activo` y
   `publicaciones.estado='aprobado'`.
4. **Idempotencia** de ingesta por `wa_message_id`.
5. **Sin Realtime** (el self-host no lo corre): lo nuevo aparece al recargar. No sumar suscripciones `postgres_changes`.
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
