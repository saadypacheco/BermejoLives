# Pendientes — ecosistema buscadonde + tienda

> Backlog maestro de los **dos productos**. Actualizado 2026-06-21.
> - **buscadonde** (este repo): mapa/descubrimiento, en producción (modo captura).
> - **tienda** (`C:\repos\proyectosClaude\tienda`, ex-amandaclothing): motor de
>   e-commerce white-label, ~95% funcional, deploy-por-cliente.

---

## 🔴 0. CRÍTICO / Seguridad — hacer YA (los dos repos)
- [ ] **tienda:** sacar `backend/.env` del repo (está **commiteado** con
      `SERVICE_ROLE_KEY` + `TELEGRAM_BOT_TOKEN` reales) → mover a `.env.example`,
      agregar a `.gitignore`, **rotar** esos secretos.
- [ ] **tienda:** validar **rol admin** en 4 endpoints de productos
      (`productos.py` 313/343/382/410) — hoy cualquier usuario logueado
      crea/edita/borra productos.
- [ ] **buscadonde:** **rotar** `service_role` + password de la DB (pasaron por chat).
- [ ] **buscadonde:** confirmar `WEBHOOK_SECRET` seteado en prod (webhook fail-closed).

---

## 🧩 1. DECISIÓN ESTRATÉGICA — cómo se conectan los dos productos
La tienda es **deploy-por-cliente** (repo + Supabase + dominio por comercio, ~1-2 días
c/u). No escala a cientos de comercios de Bermejo. **A decidir:**
- **Opción A:** tienda = **add-on premium** (pocos comercios, tipo Amanda) +
  buscadonde tiene un **catálogo propio liviano** para la masa.
- **Opción B:** rehacer la tienda **multi-tenant** (una base, muchas tiendas).
- El botón **"Ver productos"** en la ficha de buscadonde depende de esto. Integración
  mínima ya posible: la tienda expone `GET /productos` público → buscadonde linkea
  con un campo **`tienda_url`** en el comercio.

---

## 2. buscadonde — Fase 2 (autoregistro + cobro)
*Esto es lo que habilita el modelo de negocio.*
- [ ] **Auth unificada + OTP por teléfono** (comercios/compradores/staff). *Desbloquea todo.*
- [ ] **Suscripción:** `paga_hasta` + **baja automática** (job) + **QR Bolivia**
      (arranque: comprobante por WhatsApp → extiende fecha).
- [ ] **Oferta primeros 100** ("pagás 1 mes, vale 2") + **rail de pago** funcionando.
- [ ] Panel **"Mi comercio"** (ver/editar/alta-baja) + campo `tienda_url` + **links libres**.
- [ ] **Inputs de descuento en alta/edición de ofertas** — capturar `descuento_pct`
      (1..99) y `vence_el` (fecha) al publicar/editar una oferta (panel y/o flujo
      WhatsApp). El modelo ya existe (migración `0020`, vista `feed_publico` y badges
      en la UI del home/buscar ya los muestran); falta el formulario de carga. Hoy se
      setean a mano en la DB.
- [ ] **Ficha del vendedor**: botón "Ver productos" (si tiene tienda) + botones a redes/páginas.
- [ ] Registro de **consentimiento** (hoy es solo checkbox).
- [ ] **Reclamar listado** ya cargado (por teléfono, sin duplicar).
- [ ] Confirmar nombre del rol **"Promotor"** (ex agente de campo).
- [ ] **Bug transcripción** "no se puede transcribir" → revisar `docker logs buscadonde-backend`.
- [ ] Clasificador IA de rubros sobre la nota "¿qué vende?".

## 3. buscadonde — Diferenciador / producto
- [ ] **Chat comprador** ("Preguntále a Bermejo", búsqueda en lenguaje natural).
- [ ] Asistente vendedor (redactar ofertas/captions con IA).
- [ ] **Reputación de dos lados** (cliente y comercio).
- [ ] **WAHA en prod** (publicar/recibir por WhatsApp vivo).
- [ ] **Distribución a compradores:** Canal de **WhatsApp** + redes propias + Telegram.
- [ ] **Multi-ciudad**: prender fronteras (Yacuiba, Villazón…).
- [ ] Videos vendedor → **canal TikTok** del sitio (curado).
- [ ] Abrir el público (sacar `MODO_CAPTURA`) cuando haya masa crítica.

## 4. buscadonde — Calidad / escala
- [ ] Tests integración + E2E + carga; CI. Observabilidad (Sentry, métricas).
- [ ] Cache/ISR/CDN; reemplazar contadores falsos.
- [ ] Supabase Pro (no pausar) + swap en el VPS.

---

## 5. tienda — para producción
- [ ] **MercadoPago:** token + webhook reales (o decidir que en Bermejo va **QR/WhatsApp**
      en vez de MP).
- [ ] **Gemini API key** real (hoy cae a FAQ hardcodeada).
- [ ] **Cron 02:00** de pre-cálculo de recomendaciones en el VPS.
- [ ] **Carrito sincronizado** para usuarios logueados (hoy solo localStorage).
- [ ] **Deploy backend CI/CD** al VPS (hoy es manual).
- [ ] Paginación de catálogo (>50 productos), SEO dinámico por producto.
- [ ] Renombrar/parametrizar lo que queda atado a "amandaclothing" (WA y pricing en
      `/software`, `.env` de ejemplo).

## 6. tienda — ya resuelto (no tocar)
B2C minorista + **B2B mayorista completo** (cuenta corriente, listas de precio,
reportes), chat Realtime + IA, motor de recomendaciones, panel admin completo,
white-label (`tienda_config` + wizard onboarding + `crear-tienda.sh`), 8 monedas.

---

## Orden sugerido para atacar
1. **Seguridad** (sección 0) — los dos repos, hoy.
2. **Decisión estratégica** (sección 1) — define el resto.
3. **buscadonde Fase 2** (sección 2) — habilita cobrar.
4. **tienda producción** (sección 5) — para el primer cliente real (Amanda).
