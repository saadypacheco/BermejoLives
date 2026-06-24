---
project: bermejo
created: 2026-06-04
last-updated: 2026-06-04
current-phase: F1-stack-bootstrap
current-feature: null
current-session: 2
last-skill: /architect-stack (manual) + bootstrap
context-pct: ~70
cognitive-mix: mixed

adrs:
  - id: 2026-06-04-stack-bermejo
    title: Stack para Encontralo
    decision: Next.js 14 + FastAPI 3.12 + Supabase + bridge WhatsApp (WAHA)
    confidence: medium
    file: ../architect-kb/decisions/2026-06-04-stack-bermejo.md

sessions:
  - n: 1
    date: 2026-06-04
    phase: F0-discovery
    skills: [/architect-idea]
    status: cerrada
  - n: 2
    date: 2026-06-04
    phase: F1-stack-bootstrap
    skills: [/architect-stack-manual, bootstrap-manual]
    status: en-curso

features:
  # Features candidatas identificadas en F0. Los IDs F-NNN se reservan acá;
  # branch + spec se crean cuando /architect-feature las arranque.

  F-000:
    name: platform-foundation
    status: candidate
    priority: P0
    rationale: >
      Auth (Supabase Auth), roles (comprador, comerciante, moderador, admin),
      RLS por comercio, soft-delete, storage de imágenes, base del esquema.
      No es feature de negocio pero bloquea TODAS las demás.
    sub-problems-solved: []
    core-solution: TBD-en-F1
    cost-profile: nulo
    depends-on: []

  F-001:
    name: comercio-profile-catalogo
    status: candidate
    priority: P0
    rationale: >
      El comercio es la entidad central. Perfil tipo red social (portada, logo,
      WhatsApp, ubicación, redes) + catálogo de productos con tabs
      (Productos · Videos · Ofertas · Información).
    sub-problems-solved: [comercio-sin-presencia-digital]
    core-solution: >
      CRUD de comercio + productos en Supabase. Página pública SSG/ISR
      (lección KB: ssg-isr-en-catalogo-no-ssr-puro). Botón WhatsApp vía wa.me
      (pattern KB: wa-me-link-sin-api).
    cost-profile: nulo
    depends-on: [F-000]

  F-002:
    name: feed-en-vivo
    status: candidate
    priority: P0
    rationale: >
      La sensación de "ciudad comercial viva" depende de este feed. Publicaciones
      aprobadas que aparecen al instante. Es el diferenciador vs un directorio.
    sub-problems-solved: [no-hay-lugar-unico-de-ofertas-en-tiempo-real]
    core-solution: >
      Supabase Realtime sobre tabla de publicaciones aprobadas. Cliente se
      suscribe directo (lección KB: supabase-realtime-directo-bypass-backend).
      Solo se emiten filas con status=aprobado.
    cost-profile: bajo
    depends-on: [F-000, F-001, F-004]

  F-003:
    name: ingesta-whatsapp-moderacion
    status: candidate
    priority: P0
    rationale: >
      Corazón operativo del producto: las publicaciones (ofertas y videos) ENTRAN
      por WhatsApp, pasan por cola de moderación y recién aprobadas se publican.
      Subsistema de integración/automatización dentro del producto.
    sub-problems-solved: [publicar-es-fricción, contenido-sin-control-de-calidad]
    core-solution: >
      Webhook de WhatsApp Business API (proveedor a definir en F1: Meta Cloud API
      vs Twilio vs 360dialog) → FastAPI normaliza el mensaje → fila en cola de
      moderación (status=pendiente). Panel de moderación con Aprobar / Rechazar /
      Solicitar cambios. Idempotencia por message-id (riesgo: webhooks duplicados).
    cost-profile: medio (costo por conversación de WhatsApp Business API)
    depends-on: [F-000]

  F-004:
    name: mapa-comercial-isometrico
    status: candidate
    priority: P1
    rationale: >
      Mapa conceptual (NO calles reales) de zonas/galerías de Bermejo con
      indicadores de comercios y ofertas activas. Identidad visual del producto.
    sub-problems-solved: [descubrimiento-por-zona]
    core-solution: >
      Mapa isométrico conceptual (CSS/SVG en el prototipo; evaluar Three.js o
      SVG ilustrado en F1). Zonas → conteos agregados de comercios/ofertas desde
      Supabase. Hover = mini-tarjetas, click = detalle de zona.
    cost-profile: nulo
    depends-on: [F-000, F-001]

  F-005:
    name: videos-tiktok-link
    status: candidate
    priority: P1
    rationale: >
      Videos cortos estilo TikTok SIN hostear video propio. El video se publica
      en una cuenta de TikTok y la plataforma guarda y embebe el link.
    sub-problems-solved: [video-marketing-sin-infra-de-video]
    core-solution: >
      Flujo: comerciante envía video por WhatsApp → moderación aprueba → operador
      publica en cuenta TikTok (manual u oficial Content Posting API, a decidir
      en F1) → se guarda la URL de TikTok → feed vertical de embeds de TikTok.
      CERO transcoding / storage de video pesado en la plataforma.
    cost-profile: nulo (sin infra de video; costo es operativo/humano)
    depends-on: [F-003]

  F-006:
    name: producto-detalle
    status: candidate
    priority: P1
    rationale: >
      Página de producto con fotos grandes, video (embed TikTok si existe),
      precio, "Contactar por WhatsApp" y "Cómo llegar".
    sub-problems-solved: [conversión-comprador-comerciante]
    core-solution: >
      Página pública SSG/ISR. wa.me con mensaje pre-cargado. Deep-link a mapa.
    cost-profile: nulo
    depends-on: [F-001]

  F-007:
    name: admin-suscripciones-pagos
    status: candidate
    priority: P2
    rationale: >
      Dashboard SaaS (comercios, usuarios, publicaciones, videos, estadísticas)
      + suscripciones y pagos. Modelo de monetización del producto.
    sub-problems-solved: [monetización]
    core-solution: >
      Dashboard admin + planes de suscripción. Pagos vía MercadoPago (lección KB:
      mercadopago-webhook-validar-firma). Mercado: frontera BO/AR, evaluar
      monedas Bs/USD/ARS en F1.
    cost-profile: bajo
    depends-on: [F-000]

f0-discovery:
  problem: >
    Construir el principal ecosistema digital comercial de Bermejo (Bolivia,
    frontera con Argentina): una plataforma que conecte compradores y comerciantes
    mostrando "todo lo que se vende en Bermejo, en tiempo real". Feed de ofertas
    en vivo, mapa comercial conceptual, catálogos, videos cortos estilo TikTok,
    integración con WhatsApp y publicaciones aprobadas por moderadores. Debe
    sentirse como una ciudad comercial viva — NO un ecommerce tradicional, NO un
    directorio de empresas, NO una página institucional.
  users:
    compradores: público general de Bermejo y de la frontera Bolivia-Argentina
    comerciantes: dueños de comercios de Bermejo (galerías, importadoras, moda,
      tecnología, gastronomía) que publican ofertas/productos/videos
    moderadores: equipo interno que aprueba/rechaza publicaciones que entran por WhatsApp
    admin: operación de la plataforma (estadísticas, suscripciones, pagos)
    escala-referencia-prototipo: ~1250 comercios, ~12.500 usuarios/mes (cifras
      ilustrativas del prototipo, a validar con tracción real)
  context-of-use:
    devices: mobile-first (comerciantes y compradores usan celular; WhatsApp es central)
    connectivity: online (el feed en vivo y la ingesta WhatsApp requieren conexión;
      no es offline-first)
    frequency: uso recurrente / impulsivo (descubrir ofertas del día antes de comprar
      o cruzar la frontera)
    realtime: SÍ — el feed muestra publicaciones aprobadas al instante (Supabase Realtime)
  hard-constraints:
    stack-declarado: Next.js + Supabase + FastAPI (obligatorio por el usuario)
    repo: https://github.com/saadypacheco/BermejoLives (público, hay que publicar)
    whatsapp: ingesta de publicaciones DESDE WhatsApp (Business API) + salida por wa.me
    video: NO hostear video propio — publicar en TikTok y guardar el link
    mercado: Bermejo + frontera Bolivia-Argentina (posible multi-moneda Bs/USD/ARS)
    regulacion: TBD (datos personales de comercios; términos de WhatsApp y TikTok)
    deadline: no declarado
    presupuesto: no declarado (bootstrapped asumido)
  stack-preferences-declared:
    frontend: Next.js (declarado)
    backend: FastAPI (declarado)
    db-auth-storage-realtime: Supabase (declarado)
    nota-path-dependence: >
      Stack pre-decidido por el usuario y coincide con proyectos previos de la KB
      (tienda/apops usan Next+Supabase; hay patterns de FastAPI). /architect-stack
      debe validar honestamente este combo contra alternativas (ej: Next + Server
      Actions sin FastAPI separado) y declarar si la elección es path dependence
      legítima o conviene simplificar.
  scope: production-real (gente de Bermejo va a depender; auth/RLS/soft-delete/
    moderación/backups bien desde día 1)
  product-types-classified:
    - "Web full-stack (#1) — principal"
    - "Real-time / colaborativo (#13) — secundario (feed en vivo, Supabase Realtime)"
    - "Integración / automatización (#8) — componente clave (ingesta WhatsApp → moderación → TikTok)"
  product-types-considered-new: []
  classification-rationale: >
    Chasis claramente web full-stack: marketplace social multi-usuario con auth,
    roles (comprador/comerciante/moderador/admin), datos persistentes y catálogos
    (#1). El "tiempo real" no es cosmético: el feed empuja publicaciones aprobadas
    al instante vía Supabase Realtime, lo que justifica #13 como secundario (no es
    colaborativo estilo CRDT, es difusión en vivo). La ingesta de contenido entra
    por WhatsApp y se reenvía a TikTok — eso es un subsistema de integración/
    automatización (#8) con webhooks, idempotencia y falla parcial como norma;
    se registra como componente clave aunque no sea la clasificación principal.
    NO es AI-first, NO es directorio, NO es ecommerce tradicional (el cierre de
    venta ocurre por WhatsApp, no hay checkout/carrito en la plataforma).

key-architecture-notes-preliminary:
  whatsapp-strategy: >
    Doble vía. SALIDA: links wa.me sin API (gratis, pattern KB wa-me-link-sin-api).
    ENTRADA: WhatsApp Business API para ingestar publicaciones (proveedor a elegir
    en F1: Meta Cloud API directo vs Twilio vs 360dialog). Costo por conversación
    y aprobación de Meta son constraints reales. Webhook debe ser idempotente.
  video-strategy: >
    La plataforma NO aloja video. El video llega por WhatsApp, se aprueba, se
    publica en una cuenta de TikTok (manual por operador, o vía TikTok Content
    Posting API — decidir en F1) y se guarda SOLO la URL. El "feed TikTok" del
    front son embeds. Elimina Mux/Cloudflare Stream/transcoding y su costo.
  realtime-strategy: >
    Supabase Realtime sobre la tabla de publicaciones aprobadas. Cliente suscrito
    directo (lección KB supabase-realtime-directo-bypass-backend). Solo se emiten
    filas status=aprobado para no filtrar contenido sin moderar.
  backend-split-question: >
    Pregunta abierta para F1: ¿hace falta FastAPI separado, o Next.js Server
    Actions + Supabase cubren casi todo y FastAPI queda solo para el subsistema
    WhatsApp/TikTok (webhooks, jobs, integración)? Probable rol de FastAPI:
    integración/automatización, no CRUD de la app.
  catalogo-rendering: SSG/ISR para catálogos públicos (lección KB ssg-isr-en-catalogo-no-ssr-puro), no SSR puro.
  data-hygiene: soft-delete con flag activo (pattern KB soft-delete-activo-flag); nunca delete físico (lección KB).

prototipo-existente:
  tipo: prototipo visual estático (HTML/CSS/JS, sin backend)
  ubicacion: raíz del repo (index.html, negocio.html, producto.html, admin.html, css/, js/)
  rol: referencia de diseño/UX, NO la codebase de producción
  destino: re-implementar en Next.js; conservar como referencia visual o mover a /prototype

open-questions-doc: docs/open-questions.md

tensions-detected:
  - >
    Stack declarado incluye FastAPI separado + Supabase. Riesgo de sobre-ingeniería
    si Next Server Actions + Supabase ya cubren el CRUD. /architect-stack debe
    decidir el rol real de FastAPI (probablemente solo integración WhatsApp/TikTok).
  - >
    Producción real + WhatsApp Business API + TikTok publishing + moderación +
    pagos multi-moneda = alcance grande. Priorizar núcleo (F-000..F-003) para
    primera entrega usable.
  - >
    Dependencia de plataformas externas (Meta/WhatsApp, TikTok) con sus términos,
    costos y aprobaciones. Bloquea partes de F-003/F-005 hasta resolver proveedor
    y método de publicación.

next-steps:
  - Cerrar preguntas 🔴 bloqueantes en docs/open-questions.md
  - Correr /architect-stack para decidir arquitectura (rol de FastAPI vs Server
    Actions, proveedor WhatsApp, método de publicación TikTok, hosting, multi-moneda)
---

# Journey de bermejo

## Sesión 1 — 2026-06-04 08:38 — en curso

**Fase:** F0 · Discovery
**Modo cognitivo:** clean
**Skills invocadas:** /architect-idea

### Lo que pasó

- Entrevista F0 completada (las 6 dimensiones; las 4 bifurcaciones ambiguas se
  resolvieron con el usuario antes de clasificar).
- Idea: **Encontralo** — ecosistema digital comercial de Bermejo (Bolivia,
  frontera con Argentina). "Todo lo que se vende en Bermejo, en tiempo real."
- Producto que debe sentirse como una **ciudad comercial viva**: feed en vivo,
  mapa conceptual, catálogos, videos TikTok, WhatsApp y moderación. Explícitamente
  **NO** ecommerce tradicional, **NO** directorio, **NO** página institucional.
- Stack declarado por el usuario: **Next.js + Supabase + FastAPI**.
- Repo a publicar: https://github.com/saadypacheco/BermejoLives
- Alcance: **producción real desde día 1**.

### Decisiones clave capturadas en F0

- **WhatsApp doble vía:** salida con links `wa.me` (sin API), entrada de
  publicaciones vía **WhatsApp Business API** (proveedor a definir en F1).
- **Videos sin hosting propio:** el video se publica en **TikTok** y la plataforma
  guarda solo el **link**; el feed son embeds. Sin transcoding/Storage de video.
- **Feed en tiempo real real:** **Supabase Realtime** sobre publicaciones aprobadas.
- **FastAPI probablemente acotado** al subsistema de integración (WhatsApp/TikTok,
  webhooks, jobs), no al CRUD de la app — a confirmar en F1.

### Clasificación de producto

- **Web full-stack (#1)** principal + **Real-time (#13)** secundario +
  **Integración/automatización (#8)** como componente clave (ingesta WhatsApp →
  moderación → TikTok).

### Features candidatas identificadas

- **F-000 Platform foundation** (P0) — auth, roles, RLS, soft-delete, storage.
- **F-001 Comercio: perfil + catálogo** (P0) — perfil social + productos, tabs.
- **F-002 Feed en vivo** (P0) — Supabase Realtime sobre publicaciones aprobadas.
- **F-003 Ingesta WhatsApp + moderación** (P0) — webhook → cola → aprobar/rechazar/cambios.
- **F-004 Mapa comercial isométrico** (P1) — conceptual, zonas con indicadores.
- **F-005 Videos TikTok (link)** (P1) — publicar en TikTok, guardar URL, feed de embeds.
- **F-006 Producto detalle** (P1) — fotos, precio, WhatsApp, cómo llegar.
- **F-007 Admin + suscripciones/pagos** (P2) — dashboard + monetización (MercadoPago).

### Artefactos de esta sesión

- [docs/architect-journey.md](docs/architect-journey.md) — este archivo.
- [docs/open-questions.md](docs/open-questions.md) — preguntas abiertas para F1.
- Prototipo visual estático ya existente en la raíz (referencia de diseño, no producción).

### Tensiones detectadas (a resolver en F1)

1. Rol real de **FastAPI** vs Next Server Actions + Supabase (riesgo de sobre-ingeniería).
2. Alcance grande para producción día 1 — priorizar núcleo F-000..F-003.
3. Dependencia de **Meta/WhatsApp** y **TikTok** (términos, costos, aprobaciones).

### Estado al cierre de F0

- F0 completa. Idea documentada y clasificada.
- Próximo paso explícito: **correr `/architect-stack`** (tras revisar open-questions).

## Sesión 2 — 2026-06-04 — en curso

**Fase:** F1 · Stack + Bootstrap
**Modo cognitivo:** mixed (stack-decision + bootstrap + implement inicial)
**Skills invocadas:** /architect-stack (manual), bootstrap manual

### Decisión de stack (ADR)

- Escrito `architect-kb/decisions/2026-06-04-stack-bermejo.md`.
- **Next.js 14 + FastAPI 3.12 + Supabase + bridge WhatsApp WAHA**, reusando el
  chasis probado de `mentorcomercial` (resuelve el subproblema más riesgoso:
  captura de WhatsApp idempotente).
- Refinamientos sobre F0: WhatsApp por **WAHA** (no Business API oficial) — sin
  costo ni aprobación de Meta; **FastAPI acotado a ingesta + escrituras**
  (service_role), el front lee con anon+RLS y **Realtime directo**.
- Path dependence declarada y justificada (no inercia: reuso de mentorcomercial).

### Bootstrap (monorepo creado)

```
frontend/   Next.js 14 (App Router) — diseño portado del prototipo, feed Realtime,
            perfil de comercio con TODOS los datos del vendedor, panel /admin.
backend/    FastAPI — webhook WAHA (ingesta idempotente), moderación con JWT.
supabase/   migraciones 0001 init · 0002 RLS+GRANTs · 0003 seed.
infra/      docker-compose con WAHA.
prototype/  HTML/CSS/JS original (referencia de diseño).
```

### Modelo de datos del vendedor (pedido explícito del usuario)

`comercios` guarda y muestra: whatsapp (obligatorio), teléfono, email, tiktok_url,
facebook_url, instagram_url, sitio_web, dirección, lat/lng, zona, logo, portada,
plan, verificado, rating. + `productos`, `publicaciones` (feed+moderación),
`wa_inbox`, vista `feed_publico`.

### Flujo central implementado

WhatsApp → WAHA → `/ingest/webhook` (HMAC) → `wa_inbox` (idempotente) → upsert
comercio por número → `publicaciones.estado='pendiente'` → `/admin` aprueba →
`estado='aprobado'` → Supabase Realtime → feed en vivo.

### Verificación

- Backend: `py_compile` OK en todos los módulos.
- Frontend: `next build` OK (6 rutas: `/`, `/admin`, `/comercios/[slug]`,
  `/api/health`). Degradación suave con datos demo si falta Supabase.

### Pendiente (próximas sesiones)

- Storage de imágenes entrantes de WhatsApp (hoy se guarda media_url cruda).
- Publicación a TikTok (operador/API) + guardar link en la publicación.
- Alta self-service de comercios + verificación; pagos/suscripciones (F-007).
- Aplicar migraciones contra un Supabase real y probar el flujo end-to-end.
- Publicar el repo en https://github.com/saadypacheco/BermejoLives.

## Sesión 3 — 2026-06-09 — en curso

**Fase:** F3 · Feature implement
**Feature:** F-008 · Chatbot de publicación + comercios confiables
**Skills invocadas:** (build directo)

### F-008 — Publicación por comercio logueado

Pedido del usuario: para usuarios logueados, un **chatbot** para enviar las
publicaciones/ofertas; y para **clientes confiables**, que publiquen **directo**
en el sitio sin moderación.

**Implementado:**
- Migración `0004_comercio_login_confiable.sql`: flag `comercios.confiable` +
  tabla `comercio_usuarios` (login propio con JWT, mismo patrón que el admin) +
  GRANTs + RLS + seed (abc = confiable, moda = no confiable; clave `comercio1234`).
- Backend `app/api/comercio.py`: `/auth/comercio/login`, `/comercio/publicar`,
  `/comercio/mis-publicaciones`. Regla: `confiable` ⇒ `estado='aprobado'`
  (publica directo), si no ⇒ `pendiente` (moderación). `require_comercio` valida
  el JWT de comercio.
- `ingest.py` ahora respeta `confiable` también en el canal WhatsApp (un comercio
  confiable que manda por WhatsApp publica directo, sin pasar por moderación).
- Frontend `/publicar`: login de comercio + **chatbot conversacional** (máquina de
  pasos determinista: tipo → título → precio → descripción → tiktok/imagen →
  confirmar → publicar). Muestra si quedó EN VIVO (confiable) o EN REVISIÓN.
- `live-feed.tsx`: la suscripción Realtime ahora escucha INSERT **y** UPDATE con
  `estado=aprobado`, para captar también las publicaciones directas de confiables.

**Nota de diseño:** el "chatbot" es un compositor guiado determinista (cero costo,
captura estructurada confiable). Upgrade futuro: LLM (LiteLLM/Gemini, como
mentorcomercial) para conversación libre. Auth de comercio con JWT propio para no
introducir Supabase Auth todavía; reevaluar si se quiere magic-link.

**Verificación:** backend `py_compile` OK; frontend `next build` OK (7 rutas,
nueva `/publicar`).

### F-009 — Registro self-service de comercios + elección de plan

Pedido: que un comercio se dé de alta solo, eligiendo el plan por el que paga.

**Implementado:**
- Backend `POST /auth/comercio/registro`: crea `comercios` (slug único auto desde
  el nombre, `_slugify` + sufijo si colisiona) + `comercio_usuarios` (password
  hasheada), valida email no duplicado y password ≥ 6, devuelve token (auto-login).
  Nuevo comercio nace `confiable=false` y `verificado=false`.
- Frontend `/publicar`: la vista de auth ahora tiene tabs **Ingresar / Crear
  cuenta**. El registro pide nombre, WhatsApp, email, contraseña y **plan**
  (gratis/pro/premium con tarjetas seleccionables). Tras registrarse, auto-login →
  chatbot.
- Mapeo de "paga → publica": tener cuenta habilita publicar; el **plan** se
  registra pero el cobro real es **F-007** (pagos, pendiente); la **publicación
  directa** depende de `confiable` (se habilita al verificar el comercio, no por
  el plan todavía). Respuesta del backend trae `pago_pendiente` para planes pagos.

**Decisión:** no se gatea el permiso de publicar por plan todavía (todo comercio
registrado publica, con moderación). Si se quiere "gratis no publica / cupo por
plan", es una regla a sumar en `/comercio/publicar`. Verificación: build OK.

### Hardening — suite de tests del backend (25 tests, verde)

Como nada se había ejecutado aún contra una DB real, blindé la lógica de negocio
con tests (patrón mentorcomercial: repo en memoria, sin Supabase ni red).

- Refactor: `db/session.py` con import perezoso de `supabase` (la app importa sin
  el paquete); endpoints inyectan el repo vía `Depends(get_repo)` → testeables con
  `app.dependency_overrides`. `main.py` migrado a `lifespan` (sin warnings).
- `tests/conftest.py`: `FakeRepo` en memoria + `TestClient`.
- `tests/test_auth.py`: hash/verify, claims del token, guards de rol (comercio no
  modera → 403; sin token → 401).
- `tests/test_ingest.py`: idempotencia por `wa_message_id`, clasificación
  video/oferta, **confiable → aprobado directo**, mensaje propio ignorado.
- `tests/test_comercio.py`: registro (slug único, email duplicado 409, password
  corta 400, plan pago marca pendiente), publicar (confiable directo vs moderación,
  tipo inválido 400, sin token 401).
- `tests/test_moderacion.py`: listar pendientes, aprobar/rechazar transiciones,
  estado inválido 400, inexistente 404.
- **Resultado: `pytest` → 25 passed.** Frontend `next build` sigue verde.

### Estado al cierre de la sesión

- Lógica de negocio del backend verificada por tests. Falta el paso que **requiere
  al usuario**: conectar un Supabase real (`db push` + claves) y probar el flujo
  completo en navegador. Luego publicar el repo.

## Sesión 4 — 2026-06-10

**Fase:** F1/F2 · Definición de modelo de producto
**Skills:** (brainstorm de producto + captura de decisión)

### Decisión de producto cerrada (ADR)

Escrito `architect-kb/decisions/2026-06-10-modelo-producto-bermejo.md`. Resumen:

- **No es marketplace: es capa de descubrimiento + conexión.** La transacción
  NUNCA pasa por la plataforma (es la vidriera, no la caja). El modelo de plata
  es suscripción por visibilidad, no comisión.
- **Videos:** solo link/embed; "subir a canal TikTok del sitio" = servicio aparte.
- **Comprador → vendedor: directo** a su WhatsApp con mensaje de atribución
  ("vi esto en Encontralo"). NADA central para atender.
- **Número central: solo saliente** (reporte diario automatizable). Un número
  central que *atienda* es inmanejable (depende de info que los vendedores no
  mantienen).
- **Venta/QR: fuera del sistema**, pura operación de WhatsApp.
- **Bot:** premium futuro, por vendedor, opcional.
- **Reporte diario:** vistas + clics (preguntas solo con bot premium).
- **Hot Sale/eventos** time-boxed con pin pulsante en el mapa = diferenciador.

### Cambios técnicos de esta sesión (previos al brainstorm)

- Dev server en **puerto 3003** (`next dev -p 3003`), levantado y verificado (200).
- **Icono de persona** para "Ingresar" en la barra superior (sitio + prototipo).
- **Captura de ubicación por WhatsApp**: si el vendedor comparte su ubicación,
  el webhook actualiza lat/lng del comercio (onboarding para gente con poca
  tecnología). +1 test (26 passed).

### Features nuevas registradas (candidatas)

- **F-010** Tracking de vistas/clics — sostiene el modelo de plata. (P0 del modelo)
- **F-011** Reporte diario por WhatsApp saliente — retención/prueba de valor. (P0)
- **F-012** Hot Sale / eventos time-boxed con pin pulsante en mapa. (P1)
- **F-013** Bot premium por vendedor. (P2, fase 2)
- **F-014** Servicio "subir a canal TikTok". (P2, operativo)

### Próximo paso

Construir **F-010 + F-011** (tracking + reporte diario): es la pieza que sostiene
la monetización.

## Sesión 5 — 2026-06-10

**Fase:** F2/F3 · Infra local + feature taxonomía
**Skills:** (build directo)

### Infra: stack local en Docker (patrón apops)

El dueño pidió correrlo en Docker como los otros proyectos. Se montó **Supabase
local** vía CLI (`supabase start`), patrón apops (no el Postgres plano de
mentorcomercial), porque Bermejo depende de Auth/RLS/Realtime de Supabase.

- `supabase/config.toml`: project_id `Bermejo`, **puertos 5442x** (API 54421,
  db 54422, studio 54423) para no pisar apops (5432x) ni mentorcomercial.
- `supabase start` + `db reset` → migraciones 0001–0005 aplicadas, 5 comercios /
  11 rubros / 2 cuentas / publicaciones sembradas.
- Claves: el CLI nuevo emite formato `sb_publishable/sb_secret` que las libs
  pinneadas NO aceptan → se usan las **legacy JWT** (`supabase status -o env`).
  Escritas en `frontend/.env.local` y `backend/.env`.
- **Verificado end-to-end contra Supabase real:** `/health` connected; login de
  comercio; publicar como confiable → `estado=aprobado` directo; aparece en
  `feed_publico`; la home (Next, :3003) muestra la publicación real.
- **Gotcha registrado:** `next dev`/`uvicorn` como procesos de fondo del agente
  mueren entre turnos y dejan el puerto ocupado (orphan node) → matar PID del
  3003 antes de relanzar. Supabase (Docker) sí persiste.

### F-015 — Mayorista/minorista + rubros

- Migración `0005_rubros_modalidad.sql`: `comercios.modalidad`
  (mayorista|minorista|ambos, default mayorista) + tabla `rubros` (extensible:
  importadora, moda, tecnología, **restaurante**, **servicios**, **gomería**,
  farmacia, hogar, belleza, mercado, otros) + `comercios.rubro_id`. RLS+GRANTs.
  Vista `feed_publico` ampliada con modalidad + rubro.
- Backend: `RegistroBody` toma `modalidad` + `rubro_slug`; validación; repo
  `get_rubro_id`. +2 tests (**28 passed**).
- Frontend: registro con selector de **modalidad** (segmented) + **rubro**
  (dropdown); perfil muestra la modalidad.

### URLs locales

- App: http://localhost:3003 · Studio (DB): http://localhost:54423 ·
  Backend: http://localhost:8000/health

## Sesión 6 — 2026-06-10

**Fase:** F2 · Dockerización completa (paridad con mentorcomercial/apops)

### Stack 100% en Docker

- `frontend/Dockerfile` (multi-stage prod, `next start -H 0.0.0.0 -p 3003`) +
  `.dockerignore` (front y back). `frontend/public/robots.txt` (la imagen prod
  copia `public/`, que no existía → build fallaba).
- `infra/docker-compose.yml` reescrito: **backend + frontend** (WAHA en profile
  `whatsapp`, opcional). `docker compose up -d --build` levanta todo.
- **Networking host↔contenedor resuelto:** Supabase corre en el host (CLI);
  los contenedores lo alcanzan por `host.docker.internal:54421`
  (`extra_hosts: host-gateway`). El navegador usa `localhost` vía `NEXT_PUBLIC_*`
  horneadas como build-args. `lib/supabase.ts` ahora usa `SUPABASE_INTERNAL_URL`
  en el lado servidor (SSR en contenedor) y la URL pública en el navegador.
  `app/page.tsx` → `dynamic = "force-dynamic"` (feed siempre fresco, sin fetch en
  build).
- **Gotchas resueltos:** (1) PyPI read-timeout en `pip`/`uv` → `PIP_DEFAULT_TIMEOUT`
  + `UV_HTTP_TIMEOUT` + `--retries 8`. (2) `COPY public` fallaba → crear `public/`.
- **Verificado:** `bermejo-backend` + `bermejo-frontend` Up; `/health` connected;
  login de comercio OK; home dockerizada muestra datos reales ("TEST en vivo").

### Manejo

`docker compose up -d --build` / `down` (app) · `npx supabase start` / `stop` (DB).
README actualizado con la sección Docker.

## Sesión 7 — 2026-06-10

**Fase:** F3 · Feature buscador (Fase 1)

### F-016 — Buscador con filtros + resultados en mapa (Fase 1 = capa L1)

- Migración `0006_busqueda.sql`: columnas `tsvector` generadas (español) en
  `comercios` y `publicaciones` + índices GIN + RPC `buscar_comercios(q, rubro,
  modalidad, zona, precio_min, precio_max)`. **SECURITY INVOKER** → respeta RLS
  (anon solo ve activos/aprobados). Aplicada con `supabase migration up` (sin
  perder datos).
- **Clave de diseño:** la relevancia sale también de lo que el comercio PUBLICA
  (join a publicaciones), así el que "vende de todo" aparece por su contenido
  real, no solo por su rubro declarado. Verificado: "iphone" encuentra
  Importadora ABC por su publicación (no por el rubro).
- Frontend `/buscar` (client): barra + filtros (rubro, zona, precio máx,
  modalidad segmented) con debounce, llamando `supabase.rpc` directo (anon).
  Toggle **lista / mapa**. Nav: link "Buscar" + icono → `/buscar`.
- `components/map-results.tsx`: mapa **Leaflet cargado desde CDN** (sin sumar
  dependencia npm ni rebuild de la imagen por la lib), tiles dark CartoDB, pins
  neón, popup con WhatsApp + Cómo llegar + Ver comercio. "Cómo llegar" usa
  lat/lng (capturadas por WhatsApp) o la dirección como fallback.
- **Verificado en Docker:** `/buscar` 200; RPC con anon devuelve resultados
  filtrados; build OK (ruta `/buscar` 5.1 kB).

### Pendiente (próximas capas del buscador)

- L2 semántica (pgvector + embeddings), L3 lenguaje natural ("Preguntale a
  Bermejo"), multi-rubro/etiquetas, y catálogo desde WhatsApp Business.

## Sesión 8 — 2026-06-10

**Fase:** F3 · Feature agente de campo (onboarding en la calle)

### Ficha mínima decidida (qué datos pedir)

Un amigo hace el recorrido físico. Ficha mínima (capturable en <1 min):
**nombre · celular/WhatsApp · rubro · mayorista/minorista · ubicación GPS ·
foto del local**. Segunda pasada: dirección, qué vende, horarios, redes,
catálogo WA, dueño. + consentimiento (verbal, registrado) y celular con código
de país. El esquema ya soportaba todos estos campos.

### F-017 — Modo agente de campo

- Migración `0007`: bucket de Storage **público** `comercios` para las fotos.
- Backend `app/api/campo.py`: `/auth/campo/login` (credencial de agente, rol
  `agente`) + `POST /campo/comercio` (multipart: campos + GPS + foto). La foto
  va a Storage con service_role; la URL pública se arma con `SUPABASE_PUBLIC_URL`
  (localhost) para que la vea el navegador, no con la interna del contenedor.
  El comercio entra `verificado=false`. `python-multipart` agregado.
  Util de slug movida a `app/core/text.py`. +5 tests (**33 passed**).
- Frontend `/campo` (móvil): login de agente + form con **"usar mi ubicación
  actual"** (geolocation) + **cámara** (`capture=environment`) + rubro/modalidad,
  consentimiento, contador de cargados, pantalla de éxito → "cargar otro".
- **Verificado en Docker end-to-end:** alta con GPS → aparece en el buscador;
  alta con foto → foto en Storage accesible (HTTP 200) con URL de navegador.

### Caveat operativo

`navigator.geolocation` requiere **HTTPS** en producción (en el celular del
amigo sobre la red). En `localhost` funciona; al deployar (HTTPS) también.
Fallback: cargar sin GPS y completar luego por la ubicación de WhatsApp.

### Credenciales

Agente de campo: `agente@bermejolive.com` / `campo1234` → **`/bermejo`**
(la ruta del frontend se renombró de `/campo` a `/bermejo`; los endpoints del
backend siguen siendo `/campo/*` y `/auth/campo/login`, son internos).

## Sesión 9 — 2026-06-11

**Fase:** F3 · Moderación de comercios + decisiones de ecosistema

### Decisiones de producto/ecosistema (documentadas)

`docs/modelo-comercial-y-ecosistema.md`: embudo de 3 pasadas, membresías (4 tiers),
add-ons, ideas, y análisis de `tienda` (amandaclothing) + BermejoOfertas. Hallazgos:
`tienda` mismo stack, ya tiene carrito→WhatsApp + auto-redes + B2B, pero es
**deploy-por-cliente** (no multi-tenant) y **auth solo email**. Recomendación:
vender tiendas por-vendedor con `tienda` tal cual; BermejoOfertas = el feed que
Bermejo ya tiene; login teléfono/OTP (`identidad-celular-progresiva`) pendiente.

### F-018 — Moderación de comercios del agente de campo

- Backend: `GET /moderacion/comercios?verificado=false`, `POST .../verificar`,
  `POST .../rechazar` (desactiva). Repo: `list_comercios_admin`,
  `set_comercio_verificado`, `desactivar_comercio`. +4 tests (**37 passed**).
- Frontend `/admin`: pestañas **Publicaciones / Comercios por verificar**; la
  segunda lista las altas del agente con modalidad, rubro, WhatsApp, GPS, foto, y
  botones **Verificar / Rechazar**.
- Verificado end-to-end: lista comercios `verificado=false` → verificar → pasa a
  `verificado=true`.

### Pendiente inmediato

Mapbox (esperando token `pk....` del dueño) para el mapa con buscador+filtros
estilo Google.
