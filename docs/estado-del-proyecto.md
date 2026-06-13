# Estado del proyecto — Bermejo Live Market / buscadonde.com

> Inventario de **lo implementado** y **lo que falta**. Actualizado 2026-06-13.
> Detalle de huecos y prioridades en `analisis-factibilidad.md`. Modelo de
> negocio en `modelo-comercial-y-ecosistema.md`. Bitácora técnica en
> `architect-journey.md`.

## ✅ Implementado y funcionando

### Infra / deploy
- Monorepo **Next.js 14 + FastAPI + Supabase**, todo en Docker.
- **Producción viva** en `buscadonde.com` (VPS Hostinger + Traefik + HTTPS).
- **Supabase Cloud** con las 8 migraciones aplicadas.
- Repo en GitHub `saadypacheco/BermejoLives`.
- **Modo captura**: el sitio público muestra "Próximamente"; solo `/bermejo`,
  `/admin`, `/publicar`, `/software` están activos.

### Base de datos (`supabase/migrations/` 0001–0008)
- `comercios` (con todos los datos: WhatsApp, teléfono, redes, web, ubicación,
  modalidad mayorista/minorista, plan, verificado, rating, ciudad).
- `zonas`, `rubros` (11), `ciudades` (14, Bolivia — Bermejo activa).
- `productos`, `publicaciones` (feed + moderación), `wa_inbox`.
- `comercio_usuarios` (cuentas de comercio), bucket de Storage `comercios`.
- Búsqueda full-text en español + RPC `buscar_comercios` (rubro/modalidad/zona/
  precio/ciudad). RLS + GRANTs + soft-delete en todo.

### Backend (FastAPI, 37 tests verdes)
- Ingesta WhatsApp idempotente (webhook WAHA) → publicación pendiente.
- Auth JWT: admin, agente de campo, comercio (login + registro + publicar).
- Moderación: publicaciones (aprobar/rechazar/cambios) y **comercios**
  (verificar/rechazar).
- Alta de campo (foto a Storage + GPS). Captura de ubicación por WhatsApp.
- Regla `confiable` → publica directo; si no, a moderación.

### Frontend (Next.js)
- **Home**: hero con **mapa de Bolivia** (Bermejo encendido), feed en vivo
  (Realtime), zonas, comercios destacados.
- **/buscar**: buscador + filtros + resultados en **lista o mapa** (Leaflet),
  filtro por ciudad.
- **/comercios/[slug]**: perfil con redes, ubicación, productos.
- **/publicar**: login/registro de comercio + **chatbot** para publicar.
- **/bermejo**: agente de campo (login + GPS + cámara).
- **/admin**: moderación (publicaciones + comercios por verificar).
- **/software**: landing del producto con planes y add-ons.
- Diseño dark premium; fotos reales de Bermejo.

## ⏳ Lo que falta (por prioridad)

### Inmediato — seguridad y escala básica
- [ ] Limpiar **cuentas/datos demo** en prod + `WEBHOOK_SECRET` + rotar secretos.
- [ ] **Paginación** en feed y búsqueda.
- [ ] Validación + **resize** de fotos al subir.
- [ ] **Rate limiting** (login, webhook, búsqueda).

### Fundacional — Fase 2 (autoregistro + cobro)
- [ ] **Auth unificada + OTP por teléfono** (comercios, compradores, staff).
      *Desbloquea todo lo demás.*
- [ ] **Suscripción**: `paga_hasta` + **baja automática** + **QR Bolivia**
      (arranque: comprobante por WhatsApp → extiende fecha).
- [ ] Registro de **consentimiento** (papel/digital, qué autorizó).
- [ ] Panel **"Mi comercio"** (ver / editar / alta-baja).
- [ ] **Reclamar listado** ya cargado (por teléfono, sin duplicar).

### Diferenciador
- [ ] **Chat inteligente comprador** ("Preguntale a Bermejo", búsqueda NL).
- [ ] Asistente vendedor (redactar ofertas/captions con IA).

### Producto / modelo (cuando aplique)
- [ ] **Reputación de dos lados** (confirmación mutua, OTP, score ponderado).
- [ ] **Videos**: modelo link/embed (auto-subir a TikTok descartado); canal del
      sitio curado y manual.
- [ ] **WAHA en prod** para que "publicar por WhatsApp" esté vivo.
- [ ] **Tienda online** (motor `tienda`/amandaclothing) como add-on multi-tenant.
- [ ] **Multi-ciudad**: prender fronteras (Yacuiba, Villazón…) y ciudades.

### Calidad / escala (continuo)
- [ ] Tests de **integración + E2E + carga**; CI.
- [ ] **Observabilidad** (logs + Sentry + métricas + alertas).
- [ ] **Cache/ISR/CDN** para páginas públicas; feed denormalizado.
- [ ] Reemplazar **contadores falsos** por reales.

## Credenciales (prod)
- Agente de campo: `agente@buscadonde.com` → `/bermejo`
- Moderación: `admin@buscadonde.com` → `/admin`
- (las del `.env` del VPS)
