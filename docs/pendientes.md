# Pendientes — ecosistema Encontralo + Reservalo + tienda

> Backlog maestro. Actualizado 2026-07-07 (antes: 2026-06-21 — mucho de lo que
> decía "pendiente" ya se hizo; ver sección 2bis para el detalle de lo nuevo).
> - **Encontralo** (este repo, ex-buscadonde): mapa/descubrimiento, en producción.
> - **Reservalo** (`C:\repos\proyectosClaude\reservalo`): catálogo multi-vendor
>   + reservas, vive bajo `encontralo.store/reservalo`, en producción.
> - **tienda** (`C:\repos\proyectosClaude\tienda`, ex-amandaclothing): motor de
>   e-commerce white-label, ~95% funcional, deploy-por-cliente. *(No tocado en
>   la sesión del 2026-07-07 — su estado abajo puede estar desactualizado.)*

---

## 🔴 0. CRÍTICO / Seguridad — hacer YA
- [ ] **Encontralo:** WAHA (bridge de WhatsApp) **no está desplegado en
      producción** — no aparece en `docker-compose.prod.yml`. Sin esto, ningún
      código de verificación por WhatsApp llega a destino: ni el login de
      comprador (celular+código, nuevo) ni la recuperación de cuenta de
      comercio. Ver `backend/app/services/whatsapp_client.py`.
- [x] **Encontralo:** VPS `.env`/`backend/.env` tenían `ADMIN_EMAIL`/
      `ADMIN_PASSWORD`/`JWT_SECRET` duplicados — limpiado 2026-07-10 (self-host):
      `.env` raíz solo tiene lo que usa `docker-compose.prod.yml`
      (DOMAIN/DOMAIN_ALT/POSTGRES_PASSWORD/AUTHENTICATOR_PASSWORD/
      PGRST_JWT_SECRET/NEXT_PUBLIC_SUPABASE_*), y `ADMIN_EMAIL`/
      `ADMIN_PASSWORD`/`AGENTE_EMAIL`/`AGENTE_PASSWORD`/`JWT_SECRET` viven
      solo en `backend/.env` (único archivo que el backend realmente lee).
- [x] **Encontralo:** migró la base a Postgres+PostgREST self-hosted en el
      VPS (2026-07-09) — ya no depende de Supabase Cloud (Oregon). Pendiente
      **rotar** el `service_role`/password de la DB **vieja** de Supabase
      Cloud (ya no se usa, pero la clave real quedó expuesta en pantalla
      compartida en esta sesión — rotarla en el dashboard aunque no se use más).
- [ ] **Encontralo:** confirmar `WEBHOOK_SECRET` seteado en prod (webhook fail-closed).
- [ ] **Encontralo:** `OPENAI_API_KEY` en `backend/.env` tiene un valor
      placeholder (`sk-...`, no una key real) — revisar si el código cae bien
      a faster-whisper self-hosted con esto, o si intenta pegarle a la API de
      OpenAI y falla (podría ser la causa del "bug transcripción" ya anotado
      en la sección 2).
- [ ] **tienda:** sacar `backend/.env` del repo (está **commiteado** con
      `SERVICE_ROLE_KEY` + `TELEGRAM_BOT_TOKEN` reales) → mover a `.env.example`,
      agregar a `.gitignore`, **rotar** esos secretos.
- [ ] **tienda:** validar **rol admin** en 4 endpoints de productos
      (`productos.py` 313/343/382/410) — hoy cualquier usuario logueado
      crea/edita/borra productos.

---

## ✅ 2bis. Hecho en la sesión del 2026-07-01 al 2026-07-07 (no estaba anotado)
- **Cuenta de comprador (celular + código WhatsApp, sin contraseña)**: tabla
  `usuarios`/`favoritos`, guardar comercios favoritos, páginas `/guardados` y
  `/perfil`. Esto era justo lo que pedía "Auth unificada + OTP" más abajo,
  aunque solo del lado Encontralo — Reservalo sigue con su propio login
  separado (Supabase Auth), no unificado.
- **Agente de campo**: listado de "mis comercios" registrados + editar/dar de
  baja (lógica) los propios, mensaje de geolocalización con instrucciones
  específicas de iOS.
- **Mi Comercio**: ahora muestra y permite editar foto, ubicación (GPS) y
  categoría — antes faltaban los tres.
- **Reservalo**: rediseño de `/productos` (distancia real al vendedor, botón
  de WhatsApp/cómo llegar en cada producto), categorías con conteo real (se
  ocultan las que no tienen productos).
- **Bug del mapa**: la flecha pin→tarjeta se desalineaba porque Leaflet
  cacheaba un tamaño de contenedor viejo — arreglado con `ResizeObserver`.
- Bottom nav: "Inicio" → "Mapa"; "Guardados"/"Perfil" apuntaban por error al
  login de comercio, ahora van a las páginas de comprador.

---

## 🧩 1. DECISIÓN ESTRATÉGICA — cómo se conectan los productos
*Parcialmente resuelto:* **Reservalo** (repo separado, deployado bajo
`encontralo.store/reservalo`) terminó siendo el catálogo multi-vendor
compartido — parece construido sobre el motor de "tienda"/Amanda Clothing
(su frontend todavía tiene clases `amanda-*` sin renombrar del todo), pero
ahora es multi-tenant (`vendedores`, no un deploy por cliente) y ya está
integrado con Encontralo vía `producto_ref` (Encontralo linkea directo a la
ficha del producto en Reservalo). No confirmado si esto reemplaza del todo
la necesidad de "tienda" como add-on premium aparte — revisar si sigue
teniendo sentido mantener los dos.
- El botón **"Ver productos"** en la ficha de Encontralo ya funciona así (no
  quedó como `tienda_url` genérico, quedó atado específicamente a Reservalo).

---

## 2. Encontralo — Fase 2 (autoregistro + cobro)
*Esto es lo que habilita el modelo de negocio.*
- [ ] **🔴 Urgente — Agentes de captación de usuarios + incentivo por instalación.**
      Hoy solo existe un agente de campo hardcodeado (`AGENTE_EMAIL`/
      `AGENTE_PASSWORD` en `.env`) para cargar *comercios*. Se necesita un rol
      distinto (o el mismo, a definir) para gente que sale a conseguir que
      **usuarios finales instalen la PWA**, con pago:
        - **200 (moneda a definir)** por cada instalación conseguida.
        - **+500** si ese usuario sigue teniendo la app instalada 1 semana
          después (requiere algún check-in / reapertura pasados 7 días, no
          solo el evento de instalación).
        - **Anti-fraude:** un mismo número de celular no puede contarse dos
          veces (ni para el mismo agente ni entre agentes) si ya se había
          instalado antes — hay que decidir qué identifica "la misma
          instalación" (¿número de WhatsApp verificado vía el login de
          comprador ya existente? ¿algo del dispositivo?).
      Piezas que ya existen y sirven de base: el evento `appinstalled` del
      `InstallPrompt` (frontend/components/install-prompt.tsx, agregado
      2026-07-07) y la cuenta de comprador por celular+OTP (sirve para atar
      la instalación a un número real, no a un dispositivo anónimo). Falta
      todo lo demás: atribución instalación→agente, tabla de pagos/comisiones,
      el check-in de "7 días después", y el panel para que el agente vea lo
      que le corresponde cobrar.
- [ ] **Subir video del comercio** (2026-07-10): un dueño de negocio real
      (Vidriería Pacheco, primer comercio cargado en producción) tenía un
      video del local y no había dónde subirlo — hoy solo se puede linkear
      un video YA alojado afuera (`tiktok_url`/`video_url` como link
      externo), no subir un archivo propio. Alcance: guardar el archivo
      (mismo patrón que las fotos — disco + servido por el backend, pero
      los videos pesan más, hay que pensar límite de tamaño/duración y si
      conviene comprimir server-side), UI de subida en el alta/edición del
      agente, y reproductor en la ficha del comercio.
- [ ] **Revisar el menú de navegación desktop** (2026-07-10) — el usuario lo
      marcó como "raro" sin precisar qué exactamente; falta volver con
      detalle (¿qué opciones sobran/faltan del nav "Inicio · Ofertas · Mapa ·
      Negocios · Categorías"?). Ver también: la página de detalle de
      comercio no tenía botón "volver" cerca del encabezado (solo al final
      de todo el scroll) — corregido 2026-07-10, agregado uno arriba también.
- [ ] **Pasar agentes de campo de 1 cuenta hardcodeada a una tabla** —
      se van a sumar ~10 agentes más. Hoy `AGENTE_EMAIL`/`AGENTE_PASSWORD`
      en `.env` es una sola cuenta compartida; necesita ser una tabla
      `agentes` con alta/baja individual (mismo patrón que ya existe para
      `comercio_usuarios`). Bloquea al punto anterior (no se puede atribuir
      "qué agente consiguió qué instalación" con una cuenta compartida).
- [ ] **Configuración dinámica desde el panel admin** (2026-07-09, todavía sin
      diseñar): sacar de `.env` y pasar a una tabla editable desde el
      dashboard — arrancando por `OPENAI_API_KEY`/`GEMINI_API_KEY`, con la
      idea de poder **cambiar de proveedor** (ej. Whisper vs. otro STT,
      Gemini vs. otro LLM) sin redeploy. Alcance real, no es solo "mover a
      una tabla":
        - Las keys no pueden guardarse en texto plano en la base — encriptar
          en reposo (o como mínimo, mismo nivel de protección que hoy en
          `.env`, que ya tuvo una fuga por git en el pasado, ver sección 0).
        - El código que llama a estos servicios (`services/clasificador.py`,
          la transcripción de audio) hoy asume un proveedor fijo — para que
          "cambiar de proveedor" sea real, necesita una capa de abstracción,
          no solo leer la key de otro lado.
        - Mismo criterio aplicaría a `ADMIN_EMAIL`/`ADMIN_PASSWORD` — pasar
          de credencial única en `.env` a cuentas admin en tabla (posible
          mismo esfuerzo que la tabla de agentes de arriba, evaluar si
          conviene unificarlos en un solo trabajo).
      **No bloquea el lanzamiento** — para el deploy del self-host (2026-07-09)
      estas 4 variables se quedan en `backend/.env` tal cual, funcionando.
- [x] **Auth + OTP por teléfono para compradores** (celular + código
      WhatsApp, sin contraseña) — hecho 2026-07-07, solo del lado Encontralo.
      Reservalo sigue con su propio login separado (Supabase Auth) — no están
      unificados entre sí.
- [ ] **Intereses del comprador, para avisar solo lo que le sirve**
      (2026-07-10): al registrarse, UNA sola pregunta corta ("¿qué te
      interesa que te avisemos?"), texto libre — tiene que ser rápido, no
      cansar al comprador con un formulario. Guardar **los dos** valores:
        - el texto tal cual lo escribió la persona (`interes_texto`), y
        - las categorías/rubros que la IA deriva de ese texto
          (`interes_rubros`, mismo patrón que `sugerir_rubros` ya usa para
          clasificar comercios).
      El texto crudo se guarda igual aunque la IA falle/no esté disponible
      (fallback gratis, mismo criterio que el resto del clasificador). Sirve
      para, cuando entra una oferta nueva, decidir a qué compradores
      avisarle — depende de WAHA en prod (sección 0) para que el aviso
      llegue de verdad.
- [ ] **Suscripción:** `paga_hasta` + **baja automática** (job) + **QR Bolivia**
      (arranque: comprobante por WhatsApp → extiende fecha).
- [ ] **Oferta primeros 100** ("pagás 1 mes, vale 2") + **rail de pago** funcionando.
- [x] Panel **"Mi comercio"** (ver/editar) — foto, ubicación (GPS) y
      categoría ahora editables (antes faltaban). *Falta:* alta/baja del
      comercio desde el propio panel (hoy la baja es solo por admin), y
      "links libres" sin especificar qué son.
- [x] **Descuento en alta/edición de ofertas** — `descuento_pct` (1..99) + `vence_el`
      en alta (chatbot `/autoregistro`) y en **edición** (panel "Mi comercio" → "Mis
      ofertas": editar/eliminar). Backend: `PATCH/DELETE /comercio/publicaciones/{id}`
      (scoped al dueño, re-moderación si no es confiable). Migración `0020` + badges en
      home/buscar. _Falta:_ subir foto desde el panel (hoy es link de imagen).
- [x] **Ficha del vendedor**: botón "Ver productos" — hecho vía integración
      con Reservalo (`producto_ref`), no vía `tienda_url` genérico como
      estaba planteado. *Falta:* botones a redes/páginas propias del comercio
      en esa misma ficha (hoy están en la sección "Redes y web" de Mi Comercio,
      no confirmado si se muestran en la ficha pública).
- [ ] Registro de **consentimiento** (hoy es solo checkbox) — la cuenta de
      comprador nueva sí guarda `consentimiento_ofertas`, pero el checkbox de
      alta de comercio (agente de campo / autoregistro) sigue siendo solo eso.
- [ ] **Reclamar listado** ya cargado (por teléfono, sin duplicar) — no
      confundir con "Comentarios y sugerencias" (ex-reclamos) de la ficha del
      comercio, que es otra cosa (feedback/soporte, no reclamar un negocio
      importado de OSM sin dueño).
- [ ] Confirmar nombre del rol **"Promotor"** (ex agente de campo).
- [ ] **Bug transcripción** "no se puede transcribir" → revisar `docker logs bermejo-backend`.
- [x] Clasificador IA de rubros sobre la nota "¿qué vende?" — `sugerir_rubros`,
      usado en `/publicar` y `/autoregistro`.

## 3. Encontralo — Diferenciador / producto
- [ ] **Chat comprador** ("Preguntále a Bermejo", búsqueda en lenguaje natural).
- [ ] Asistente vendedor (redactar ofertas/captions con IA).
- [ ] **Reputación de dos lados** (cliente y comercio).
- [ ] **WAHA en prod** — ver sección 0 (🔴 crítico, bloquea el login de
      comprador y la recuperación de cuentas de comercio, no es solo un
      "diferenciador").
- [ ] **Distribución a compradores:** Canal de **WhatsApp** + redes propias + Telegram.
- [ ] **Multi-ciudad**: prender fronteras (Yacuiba, Villazón…).
- [ ] Videos vendedor → **canal TikTok** del sitio (curado).
- [ ] Abrir el público (sacar `MODO_CAPTURA`) cuando haya masa crítica.

## 4. Encontralo — Calidad / escala
- [ ] Tests integración + E2E + carga; CI. Observabilidad (Sentry, métricas).
- [ ] Cache/ISR/CDN; reemplazar contadores falsos.
- [ ] Supabase Pro (no pausar) + swap en el VPS.

---

## 5. tienda — para producción
> ⚠️ **Sospecha sin confirmar (2026-07-07):** esta sección puede describir un
> estado anterior de lo que hoy es **Reservalo** (su frontend todavía tiene
> clases `amanda-*` sin renombrar, y tiene motor de recomendaciones + carrito
> + `.github/workflows/deploy.yml` con **CI/CD automático ya funcionando** —
> lo vi correr esta sesión). Si "tienda" y "Reservalo" son el mismo código en
> distintos momentos, la línea de "Deploy backend CI/CD (hoy es manual)" de
> abajo ya está resuelta. No confirmé el resto de esta lista (MercadoPago,
> Gemini key, cron, carrito) contra el Reservalo actual — revisar antes de
> asumir que sigue pendiente tal cual.
- [ ] **MercadoPago:** token + webhook reales (o decidir que en Bermejo va **QR/WhatsApp**
      en vez de MP).
- [ ] **Gemini API key** real (hoy cae a FAQ hardcodeada).
- [ ] **Cron 02:00** de pre-cálculo de recomendaciones en el VPS.
- [ ] **Carrito sincronizado** para usuarios logueados (hoy solo localStorage).
- [x] **Deploy backend CI/CD** al VPS — si esto es Reservalo, ya está: push a
      `main` dispara build + push de imágenes + deploy por SSH automático.
- [ ] Paginación de catálogo (>50 productos), SEO dinámico por producto.
- [ ] Renombrar/parametrizar lo que queda atado a "amandaclothing" (WA y pricing en
      `/software`, `.env` de ejemplo) — confirmado que sigue así en Reservalo
      (clases `amanda-*` en el CSS, tema por defecto "Amanda Clothing").

## 6. tienda — ya resuelto (no tocar)
B2C minorista + **B2B mayorista completo** (cuenta corriente, listas de precio,
reportes), chat Realtime + IA, motor de recomendaciones, panel admin completo,
white-label (`tienda_config` + wizard onboarding + `crear-tienda.sh`), 8 monedas.

---

## Orden sugerido para atacar
1. **WAHA en prod** (sección 0) — sin esto, el login de comprador y la
   recuperación de cuentas de comercio que ya están deployadas no sirven.
2. **Seguridad** (sección 0, resto) — rotar credenciales, limpiar `.env` del VPS.
3. **Confirmar la sospecha de la sección 5** (¿"tienda" == Reservalo?) antes
   de seguir tratándolas como dos backlogs separados.
4. **Encontralo Fase 2** (sección 2) — lo que queda: suscripción/cobro.
