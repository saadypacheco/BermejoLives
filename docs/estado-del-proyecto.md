# Estado del proyecto — Encontralo / encontralo.store

> Inventario de **lo implementado** y **lo que falta**. Actualizado 2026-06-24.
> Ecosistema de **dos sitios**: **Encontralo** (mapa/descubrimiento, este repo) +
> **Reservalo** (tienda/productos, repo `tienda`). Tagline: *"Encontralo en el mapa.
> Reservalo en la tienda."*
> Docs clave: [[contrato-integracion]] (puente con Reservalo), [[marketplace-ecommerce]],
> [[mi-comercio]] (panel), [[migracion-encontralo-store]], [[pendientes]], [[circuitos]].

## 🌐 Producción (vivo)
- **Encontralo:** https://encontralo.store (+ www) · API https://api.encontralo.store ·
  **buscadonde.com** sigue sirviendo en paralelo (migración dual-dominio, cero downtime).
- **Reservalo (la tienda):** https://reservalo.store — **vivo**, buscador en `/productos?search=`.
- **VPS Hostinger** KVM2 (2 vCPU, 8 GB), Ubuntu 24.04, IP `76.13.234.191`. Traefik
  (red `traefik`, resolver `letsencrypt`) + HTTPS auto. Encontralo en `/docker/buscadonde`.
- **Supabase Cloud** (ref `lzknugpogpkcxjcpuqes`, us-west-2). **19 migraciones aplicadas**
  (0001–0019) + índice geo. *(El import OSM dejó ~44k comercios en la cloud.)*
- **GitHub:** `saadypacheco/BermejoLives` (rama `main`, último deploy `7563faf`).
- **Modo captura: OFF en prod** — el sitio público está abierto (home + /buscar funcionan).

## ✅ Implementado y funcionando

### Base de datos (`supabase/migrations/` 0001–0019)
- Núcleo: `comercios` (lat/lng, modalidad, plan, verificado, rating, ciudad, confiable,
  campos fronterizos 0011, campos comerciales 0014), `zonas`, `rubros`, `ciudades`
  (Bolivia+Argentina), `comercio_rubros`, `productos`, `publicaciones`, `wa_inbox`,
  `comercio_usuarios`, `leads`, `pagos`.
- **Nuevas (esta etapa):** `producto_ref` (0015, puente con Reservalo) ·
  `pagos.estado/comprobante_url` (0016, pago self-service) ·
  `publicaciones.costo/cobrado/producto_ref_id` (0017, destacado cobrable) ·
  `mensajes` (0018) · **índice geo** `idx_comercios_geo` (0019, query del mapa 1857ms→2ms).
- RLS + GRANTs + soft-delete. Full-text español + RPC `buscar_comercios` (paginado).

### Backend (FastAPI · **65 tests verdes**)
- **Auth JWT**: admin, agente, comercio.
- **Panel "Mi comercio"** (endpoints `require_comercio`): `GET/PUT /comercio/perfil`,
  `GET /comercio/suscripcion` (estado + cargos), `GET /comercio/metricas`,
  `POST /comercio/productos/draft` (IA clasifica) + `/comercio/productos` (crea vía
  TiendaClient + `producto_ref`) + GET/DELETE + `/{id}/destacar` (publicación con costo),
  `POST /comercio/pago` (comprobante QR → pendiente), `GET/POST /comercio/mensajes`.
- **Mensajería**: `POST /mensaje` (público, cliente→comercio), bandeja del comercio,
  `POST /admin/comercio/{id}/mensaje` (admin→comercio).
- **Admin**: moderación + suscripciones + `GET /admin/pagos/pendientes` +
  `/{id}/confirmar` (extiende paga_hasta + salda destacados).
- **TiendaClient** (`services/tienda_client.py`): cliente del ecommerce, modo **stub**
  si no hay `TIENDA_API_URL`. **Clasificador IA** (Gemini Flash, `services/clasificador.py`)
  con fallback gratis si no hay `GEMINI_API_KEY`.
- Alta de campo (foto resize + GPS + audio→texto), ingesta WhatsApp, rate limiting,
  **CORS multi-dominio** (varios dominios por coma).

### Frontend (Next.js 14) — rebrand **Encontralo**
- **Home** (`/`): rediseño buscador-first → buscador centrado con **toggle
  Negocios (mapa) | Productos (→ Reservalo)**, **mapa dark de Bermejo** con marcadores
  por categoría, Ofertas premium, Auspiciantes, Categorías. *(v2 con chips modernos:
  WIP sin commitear todavía.)*
- **/buscar**: resultados con **filtros tipo chips** (Categoría/Zona/Precio dropdown,
  Ofertas toggle, Productos→Reservalo), lista o mapa, paginado. *(v2 WIP.)*
- **/mi-comercio**: **dashboard del comercio** (sidebar + topbar + overview) → Perfil
  (vidriera editable), Productos (carga IA + destacado), Mensajes, Suscripción (pago QR
  self-service), Contactos/Estadísticas, Configuración.
- **/comercios/[slug]**: ficha (redes, ubicación, productos) + **form de mensaje del cliente**.
- **/admin**: moderación + suscripciones + **Pagos pendientes** + envío de mensajes.
- **/publicar /autoregistro**: relevamiento + login/registro de comercio.

### Integración Encontralo ↔ Reservalo
- **Toggle Productos** y chip "🛒 Productos" hacen **hand-off** a `reservalo.store/productos?search=`. ✅
- Diseño del **flujo inteligente** (buscar producto → comercios en el mapa → click →
  productos del local → volver / cómo llegar) cerrado en [[contrato-integracion]]
  (navegación **opción C**: misma pestaña + back nativo + barra "volver").
- `TiendaClient.list_productos(vendedor_id)` listo del lado Encontralo (stub).

## ⏳ Lo que falta (por prioridad)

### Rápido / activar
- [ ] **Commitear + deployar la Home/buscar v2** (chips, compactación) cuando cierres el look.
- [ ] **`GEMINI_API_KEY`** en `backend/.env` del VPS → la IA clasifica productos de verdad.
- [ ] **QR reales** en `frontend/public/` (`qr-bolivia.png`, `qr-argentina.png`).

### Integración Reservalo (otra sesión)
- [ ] Reservalo expone **un endpoint de productos con filtro `vendedor`** (+ `vendedor_id`
      en los resultados) → habilita el flujo inteligente producto→comercios.
- [ ] Reservalo: filtro `?vendedor=` en `/productos`, barra "← Volver al mapa", y en la
      ficha de producto "📍 Cómo llegar / Ver el local" → `encontralo.store/comercios/{slug}`.
- [ ] Setear `TIENDA_API_URL`/`SECRET` en Encontralo y reemplazar el stub.

### Seguridad / infra
- [ ] **Rotar** `service_role` + password de la DB (pasaron por chat) + confirmar `WEBHOOK_SECRET`.
- [ ] **Disco Hostinger**: limpiar caché/imágenes Docker (`docker builder prune -af` + `image prune -af`).
- [ ] Cutover: bajar buscadonde.com cuando quieras.

### Fase 2 (lo grande)
- [ ] **Auth unificada + OTP por teléfono** (hoy 3 credenciales sueltas).
- [ ] Baja automática por falta de pago (job sobre `paga_hasta`).
- [ ] Reputación de dos lados, multi-ciudad (prender fronteras), distribución (Canal WhatsApp).
- [ ] Tests integración/E2E + observabilidad. Supabase Pro (no pausar).

## 🔑 Credenciales / operación
- **Deploy Encontralo:** `cd /docker/buscadonde && git pull && docker compose -f docker-compose.prod.yml --env-file .env up -d --build`
- **Dominio:** `.env` raíz `DOMAIN=encontralo.store` + `DOMAIN_ALT=buscadonde.com`;
  `backend/.env` `FRONTEND_URL=https://encontralo.store,https://buscadonde.com`.
- **Migraciones a cloud:** Docker psql contra el **Session pooler** (ver `memory/project_db_connection.md`).
- **Dev local:** `supabase` local (Docker) + `npm run dev -p 3005` (front) + `uvicorn app.main:app --port 8010` (back);
  `frontend/.env.local` apunta a `:8010`.
- ⚠️ Codename interno `buscadonde` (paths `/docker/buscadonde`, contenedores) **sin renombrar** (cosmético, aparte).
