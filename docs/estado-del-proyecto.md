# Estado del proyecto — Encontralo / encontralo.store

> Inventario de **lo implementado** y **lo que falta**. Actualizado 2026-06-15 (post expansión estratégica).
> Docs hermanos: `analisis-factibilidad.md` (huecos/prioridades), modelo de negocio
> `modelo-comercial-y-ecosistema.md`, bitácora técnica `architect-journey.md`.

## 🌐 Producción (vivo)
- **App:** https://encontralo.store · **API:** https://api.encontralo.store ·
  **/software** (planes) · **/bermejo** (agente de campo) · **/admin** (moderación).
- **VPS Hostinger** KVM2 (2 vCPU, 8 GB RAM, 100 GB), Ubuntu 24.04, Brasil-Campinas,
  IP `76.13.234.191`. Traefik (red `traefik`, resolver `letsencrypt`) + HTTPS auto.
  Proyecto en `/docker/buscadonde`.
- **Supabase Cloud** (ref `lzknugpogpkcxjcpuqes`, us-west-2, plan NANO/Free —
  *se pausa por inactividad*). 10 migraciones aplicadas.
- **GitHub:** `saadypacheco/BermejoLives` (rama `main`).
- **Modo captura activo** (`NEXT_PUBLIC_MODO_CAPTURA=1`): el público ve
  "Próximamente"; solo `/bermejo`, `/admin`, `/publicar`, `/software` funcionan.
  Para abrir: `MODO_CAPTURA=0` en `.env` + rebuild frontend.

## ✅ Implementado y funcionando

### Base de datos (`supabase/migrations/` 0001–0011)
- `comercios` (WhatsApp, teléfono, email, redes, web, ubicación lat/lng, modalidad
  mayorista/minorista/ambos, plan, verificado, rating, ciudad, confiable).
  **Nuevos campos (0011):** `monedas_aceptadas[]`, `envios_internacionales`,
  `origen_importacion[]`, `pedido_minimo`, `tiene_factura`, `horario`, `tiene_stock`.
- `zonas` · `rubros` (**14**: +casa-de-cambio, transporte, hotel) ·
  `ciudades` (**22**: Bolivia 14 + Argentina 8, columna `pais`) ·
  `comercio_rubros` (N:M) · `productos` · `publicaciones` · `wa_inbox` ·
  `comercio_usuarios` · **`leads`** (clicks WA/tel/email por comercio).
- Bucket Storage `comercios`. RLS + GRANTs explícitos + soft-delete en todo.
- Búsqueda full-text español + RPC `buscar_comercios` (rubro/modalidad/zona/precio/
  ciudad, **paginado**, matchea cualquier rubro; devuelve campos fronterizos).

### Backend (FastAPI · 37 tests verdes)
- Auth JWT: admin, agente, comercio (login + registro + publicar).
- Ingesta WhatsApp idempotente (webhook WAHA, HMAC **fail-closed en prod**).
- Moderación: publicaciones (aprobar/rechazar/cambios) y comercios (verificar/rechazar).
- Alta de campo: foto (**validada + resize 1600px/JPEG70**) a Storage + GPS +
  multi-rubro + redes/email/video. Regla `confiable` → publica directo.
- **Transcripción de audio** ("¿qué vende?"): `faster-whisper` self-hosted (gratis,
  modelo "small", cache en volumen) o OpenAI Whisper si hay `OPENAI_API_KEY`.
- **Rate limiting** (20 POST/min por IP en `/auth/*`). CORS apex+www en prod.

### Frontend (Next.js 14)
- **Home**: mapa de Bolivia (Bermejo encendido → `/buscar?ciudad=bermejo`), feed
  Realtime, zonas, comercios destacados, fotos reales de Bermejo.
- **/buscar**: buscador + filtros (rubro/zona/precio/modalidad) + **lista o mapa**
  (Leaflet) + **"cargar más"** (paginado) + chip de ciudad fija.
- **/comercios/[slug]**: perfil (redes, ubicación, productos).
- **/publicar**: login/registro de comercio + chatbot para publicar.
- **/campo** (antes `/bermejo`, redirect activo): agente de campo — selector de
  **ciudad** (Bolivia + Argentina) · prefijo WA automático (+591/+54) · rubros como
  chips · **"¿qué vende?" por audio→texto** · mayor/menor · GPS · foto ·
  **info fronteriza**: monedas, envíos int., origen importación, factura, horario,
  stock · opcionales (dirección, redes, email, video) · consentimiento.
- **/admin**: moderación (publicaciones + comercios por verificar).
- **/software**: landing con planes (Presencia/Activo/Destacado/Premium) y add-ons.
- **middleware** de modo captura.

## ⚠️ Pendiente de resolver (arranque próxima sesión)
- **Bug: "no se puede transcribir".** Revisar: (1) que el backend se haya
  redeployado con faster-whisper (`git pull` + `up -d --build`); (2) que
  `OPENAI_API_KEY` esté **vacía** en `backend/.env` (si tiene valor inválido, toma
  el camino OpenAI y falla); (3) primera transcripción baja el modelo ~480 MB
  (puede tardar/timeout) → revisar `docker logs buscadonde-backend`.

## ⏳ Lo que falta (por prioridad)

### Fundacional — Fase 2 (autoregistro + cobro)
- [ ] **Auth unificada + OTP por teléfono** (comercios, compradores, staff, roles).
      *Hoy son 3 credenciales JWT sueltas; esto desbloquea todo lo demás.*
- [ ] **Suscripción**: `paga_hasta` + **baja automática** (job) + **QR Bolivia**
      (cuenta boliviana; arranque: comprobante por WhatsApp → extiende fecha).
- [ ] Registro de **consentimiento** (papel/digital, qué autorizó) — hoy es solo checkbox.
- [ ] Panel **"Mi comercio"** (ver / editar / alta-baja).
- [ ] **Reclamar listado** ya cargado (por teléfono, sin duplicar).
- [ ] **Clasificador IA de rubros** sobre la nota "¿qué vende?".

### Diferenciador
- [ ] **Chat inteligente comprador** ("Preguntale a Bermejo", búsqueda en lenguaje natural).
- [ ] Asistente vendedor (redactar ofertas/captions con IA).

### Producto / modelo
- [ ] **Reputación de dos lados** (confirmación mutua + OTP + score ponderado).
- [ ] **WAHA en prod** (publicar por WhatsApp vivo) + `WEBHOOK_SECRET`.
- [ ] **Tienda online** (motor `tienda`/amandaclothing) como add-on multi-tenant.
- [ ] **Multi-ciudad**: prender fronteras (Yacuiba, Villazón…) y ciudades.
- [ ] Videos: link/embed; **canal TikTok del sitio** (vendedor sube → se publica curado).
- [ ] **Distribución a compradores:** Canal de **WhatsApp** (seguir = suscribirse) +
      **redes propias** (IG/TikTok/FB) + **Telegram** auto-posteado. PWA por interés = después.

### Calidad / escala
- [ ] Tests integración + E2E + carga; CI.
- [ ] Observabilidad (logs + Sentry + métricas).
- [ ] Cache/ISR/CDN; feed denormalizado. Reemplazar contadores falsos.
- [ ] Plan Supabase Pro (no pausar) + 2 GB swap en el VPS.

## 🔑 Credenciales / operación (prod)
- **Agente** (`/bermejo`): email/clave = `AGENTE_EMAIL`/`AGENTE_PASSWORD` del
  `backend/.env` del VPS (el form viene precargado con `lobito@lobito.com`).
- **Moderación** (`/admin`): `ADMIN_EMAIL`/`ADMIN_PASSWORD` del `.env`.
- **Deploy:** `cd /docker/buscadonde && git pull && docker compose -f docker-compose.prod.yml --env-file .env up -d --build`
- **Cambiar credencial** (sin rebuild): editar `backend/.env` + `... up -d --force-recreate backend`.
- ⚠️ **Rotar** `service_role` y password de la DB (pasaron por chat). Migraciones
  contra cloud: usar el **Session pooler** (`aws-1-us-west-2.pooler.supabase.com`),
  no la conexión directa (IPv6).
