# Análisis de factibilidad, inconsistencias y viabilidad

> Revisión crítica de todo el proyecto (2026-06-13). Honesto: qué es viable, qué
> no, qué falta para una plataforma seria que aspira a millones de usuarios.

## 1. Video a TikTok automático — NO es viable como "auto-subir"

**La pregunta:** ¿el sitio puede subir solo el video a un canal de TikTok? ¿Cómo
verifica que sea permitido (comercio/oferta)? ¿Cómo se administra?

**Realidad técnica:**
- La **TikTok Content Posting API** existe pero está **muy restringida**: requiere
  app aprobada por TikTok, y solo podés postear a cuentas que **autorizaron tu app
  por OAuth**. Sin auditoría, solo permite **borradores privados**. No es un
  "firehose" para subir cientos de videos a un canal.
- Si juntás los videos de todos en **TU canal central**, te convertís en
  **publicador** → cargás con: moderación, **ToS de TikTok** (si un video viola las
  normas, penalizan TU canal), **copyright de la música**, y **rate limits**
  (no podés postear cientos/día).
- **Verificar automáticamente** que un video es "de comercio y permitido" **no es
  confiable**: lo más cercano es un clasificador de visión (IA, con costo y sin
  garantía) + moderación humana. Igual la **responsabilidad legal queda en vos**.

**Decisión recomendada (firme):**
- **Modelo link/embed = el viable y por defecto.** El comercio publica en SU PROPIO
  TikTok/Instagram y vos **guardás + embebés el link**. **No sos publicador** → sin
  liability de canal, sin rate limits, sin OAuth por cuenta. Escala.
- **"Subir a nuestro canal" = servicio manual, curado y premium** (un humano elige
  videos destacados y los sube como jugada de marketing), **NO** automático para
  todos. Volumen chico, controlado.
- **Moderación del link** (caption + miniatura) en la cola que ya existe, + botón
  de **reportar** + (a escala) **pre-chequeo con IA** del texto/imagen.

## 2. Mobile-first (90%+ celular) — chat + formulario

- Reducir fricción es **crítico**. Ofrecer **las dos vías**:
  - **Chat guiado** (ya existe el patrón en `/publicar`): pide de a una cosa, sube
    foto a Storage sobre la marcha. Ideal para el no-técnico.
  - **Formulario** para el que quiere cargar todo de una.
- Es factible y reusa lo construido.

## 3. Chat inteligente (diferenciador) — qué SÍ puede ofrecer

- **Comprador — "Preguntale a Bermejo":** búsqueda en **lenguaje natural** ("dónde
  compro zapatillas al por mayor cerca del centro") → entiende intención → devuelve
  comercios. **Este es el diferenciador real** (capa L2/L3 del buscador).
- **Vendedor — asistente:** ayuda a **redactar la oferta**, sugiere precio,
  genera caption/hashtags, mejor horario para publicar.
- Stack: Gemini/LiteLLM (como `tienda`). **Costo controlado:** modelo barato +
  cache + reglas primero. Honestidad: cada interacción IA cuesta; medir $/uso.

---

## 4. Inconsistencias y huecos detectados (auditoría)

### 🔴 Seguridad (resolver antes de abrir al público)
1. **Cuentas demo VIVAS en producción.** Las migraciones sembraron comercios y
   **cuentas demo** (`abc@bermejolive.com` / `comercio1234`, etc.) en la base
   cloud. `/publicar` está habilitado en modo captura → **cualquiera entra con esas
   credenciales conocidas**. **Acción inmediata:** correr la limpieza
   (`delete from comercio_usuarios; delete from comercios where wa_jid like '%@c.us'`).
2. **Webhook de WhatsApp sin secreto en prod.** `WEBHOOK_SECRET` vacío →
   `/ingest/webhook` (público en `api.encontralo.store`) **acepta cualquier POST** →
   inyecta publicaciones pendientes (spam de cola). Setear `WEBHOOK_SECRET` y/o no
   exponer `/ingest` hasta desplegar WAHA.
3. **Sin rate limiting** en login, búsqueda, webhook, publicar → brute-force y
   abuso. Agregar (Traefik o middleware).
4. **Upload de fotos sin validación:** acepta cualquier archivo, sin límite de
   tamaño ni verificación de que sea imagen ni **resize** (lección KB
   `fotos-resize-1600px-jpeg-70`). A escala = costo de Storage + vector de ataque.
5. **Rotar secretos** que pasaron por chat (service_role, DB pass).

### 🟡 Inconsistencias modelo ↔ lo desplegado
6. **La feature estrella (publicar por WhatsApp) NO está viva en prod.** WAHA está
   en un `profile` (no desplegado), sin webhook secret. Hoy solo funciona el alta
   por `/bermejo` y la publicación por panel.
7. **Auth fragmentada:** 3 sistemas JWT custom (admin, agente, comercio) con el
   mismo secreto, + credenciales fijas en `.env`. **No hay cuentas de comprador**
   ni **OTP por teléfono**. Esto **bloquea** Fase 2 (autoregistro), reputación y
   suscripción. **Item arquitectónico mayor: unificar auth + phone OTP.**
8. **Consentimiento:** hoy es un checkbox, **no se guarda registro**. El modelo lo
   exige (papel/digital, qué autorizó, fecha).
9. **Suscripción/pagos:** no existe `paga_hasta`, ni job de baja automática, ni
   integración QR Bolivia. Todo el modelo de cobro está sin construir.
10. **Multi-ciudad:** `ciudad` se hardcodea a Bermejo en altas. La visión Bolivia
    necesita elegir ciudad.

### 🟠 Escalabilidad (para millones)
11. **Sin paginación** en feed ni búsqueda (traen hasta 200 sin paginar) → se rompe
    con volumen. **Barato de arreglar ahora.**
12. **Home `force-dynamic`** consulta en cada request → a escala necesita
    **cache/ISR/CDN** + un feed **denormalizado** (no joins en caliente).
13. **Tests:** 37 unitarios del backend (buena lógica), pero **sin tests de
    integración, E2E, ni de carga**. Falta CI. Para millones: tests de integración
    contra DB real, E2E del flujo, y **pruebas de carga** del buscador/feed.
14. **Observabilidad:** sin métricas, sin tracking de errores (Sentry), sin alertas.
15. **Infra:** 1 contenedor de cada uno; Supabase micro. Escalar = réplicas + LB +
    upgrade de plan (más adelante).
16. **Contadores falsos** (usuarios conectados, etc.) — cosméticos, reemplazar por
    reales o quitar antes de abrir.

---

## 5. Qué se necesita para hacerlo viable (priorizado)

**Inmediato (esta semana, barato, alto impacto):**
- [ ] Limpiar cuentas/datos demo en prod + rotar secretos + `WEBHOOK_SECRET`.
- [ ] Paginación en feed y búsqueda.
- [ ] Validación + resize de fotos al subir.

**Fundacional para Fase 2 (antes del autoregistro):**
- [ ] **Auth unificada + OTP por teléfono** (comercios, compradores, staff, roles).
- [ ] Registro de **consentimiento** (tabla + flujo).
- [ ] **Suscripción**: `paga_hasta` + job de baja automática + QR Bolivia
      (arranque manual: comprobante por WhatsApp → extiende fecha).
- [ ] Panel **"Mi comercio"** (ver/editar/alta-baja).
- [ ] Rate limiting + reportar/flag.

**Diferenciador:**
- [ ] **Chat inteligente comprador** ("Preguntale a Bermejo", NL search L2/L3).
- [ ] Asistente vendedor (redactar ofertas/captions).

**Calidad/escala (continuo):**
- [ ] Tests de integración + E2E + carga; CI.
- [ ] Observabilidad (logs estructurados + Sentry + métricas).
- [ ] Cache/ISR/CDN para páginas públicas; feed denormalizado.

## 6. Veredicto

- La **base es sólida** (stack correcto, RLS, soft-delete, lógica testeada, deploy
  prod andando). **No hay que reescribir.**
- Pero **lo desplegado es un MVP de captura**, no la plataforma del modelo: faltan
  **auth real, pagos, consentimiento, paginación y hardening de seguridad** antes
  de abrir al público.
- El **video a TikTok automático no va**: link/embed por defecto, canal central
  curado y manual.
- Lo más urgente y barato: **seguridad (cuentas demo, webhook, rate limit)** y
  **paginación**. Lo más estratégico: **auth+OTP unificada** (desbloquea todo el
  resto) y el **chat inteligente** como diferenciador.
