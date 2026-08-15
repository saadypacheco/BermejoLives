# Pendientes — URUKU (prod uruku.bo + QA encontralo.store)

> Lista viva de lo que queda por hacer. Prod ya está **vivo** (uruku.bo). Ver
> [estado-vps-prod-uruku.md](estado-vps-prod-uruku.md) y [deploy-prod-nuevo-vps.md](deploy-prod-nuevo-vps.md).
> La **tienda (Reservalo)** tiene su propio plan: [plan-tienda-reservalo.md](plan-tienda-reservalo.md).

## 🔴 Ahora / alta prioridad
- [x] **DNS flip (2026-08-14):** `uruku.bo` + `www` en **Proxied (naranja)**, SSL/TLS **Full (strict)**,
      Always-HTTPS **OFF** (renovación del cert). `api`/`db`/`waha`/`tienda`/`api.tienda`/`db.tienda`
      quedan **grises**. `tienda.*` se flipean cuando Reservalo esté en prod. Verificado: `server: cloudflare`, edge GRU.
- [x] **Record DNS `waha`** ya existe (gris) → Traefik le saca el cert solo.
- [ ] **Migrar el comercio** a prod (re-registro en `uruku.bo/autoregistro` + subir sus fotos).
- [ ] **Cargar contenido** en `uruku.bo/publicador`: cotización, clima y **redes sociales de URUKU**
      (sin URLs, la barra social no muestra íconos) + número real del **canal de WhatsApp**.

## 🟠 Redirects de los dominios secundarios
- [ ] `uruku.com.bo`, `urucu.bo`, `urucu.com.bo` → **301 a `uruku.bo`**. Agregarlos como zonas en
      Cloudflare + **Redirect Rules**, o A al VPS + router de redirect en Traefik.

## 🟡 Infra / hardening
- [ ] **Fijar la versión de Traefik** (hoy `traefik:latest` por compat con Docker 29). Ver la versión
      con `docker exec traefik traefik version` y pinearla en el compose.
- [~] **Backups** del Postgres: script listo (`selfhost/backup.sh`, dump+gzip+rotación 14 días).
      Falta en el VPS: copiar a `/docker/backup.sh`, `chmod +x`, y cron `0 3 * * *`. Probar restore.
- [ ] **SSH hardening**: agregar SSH key y desactivar login por password (key-only).
- [ ] **Monitoreo básico**: disco (en QA estaba al 66%), RAM, uptime. Uptime Kuma u similar.

## 🔒 Seguridad (rotación)
- [ ] Prod arrancó con **secretos nuevos** (init_prod_env) ✅. Pero los **viejos expuestos**
      (service_role, password de DB, etc.) siguen en **QA** → **rotarlos en QA** también.
- [x] `WEBHOOK_SECRET` seteado en prod (init_prod_env). Confirmar/rotar en QA.

## 🟢 QA (encontralo.store) — espejo de prod
- [ ] Aplicar en QA los mismos cambios de **Reservalo** cuando se hagan en prod
      (basePath `/tienda`, **sacar Supabase** — Auth/Storage/DB → disco de URUKU + self-host).
- [ ] Redeploy de **Reservalo de QA** a `encontralo.store/tienda`.
- [ ] Rotar los secretos expuestos (ver arriba).

## 🛍️ Tienda (Reservalo) — proyecto aparte
- [ ] Ver **[plan-tienda-reservalo.md](plan-tienda-reservalo.md)**: sacar Supabase de Reservalo
      (imágenes al disco de URUKU, auth por token de URUKU, base self-host), reservas/carrito.
      **Regla:** todo cambio que se haga en prod se replica en QA.

## 💡 Ideas para explorar (registrar, pensar después)
- **Moderación de contenido humana + IA.** Todo lo que envían comercios/creadores se revisa
  antes de publicar: **revisión humana** (panel, rol publicador/moderador) + **botón de
  revisión con IA** (Gemini, para volumen; asistido → automático por umbral). Construye sobre
  la cola de moderación y el Gemini que YA existen. Diseño en
  **[moderacion-ia-humana.md](moderacion-ia-humana.md)**.
- **Producción de contenido automatizada desde WhatsApp.** Que el comerciante mande
  **texto / audio / fotos / videos** por WhatsApp y todo se guarde en la base (como el
  proyecto **MentorComercial** en `C:\repos\proyectosClaude\MentorComercial`, donde ya se
  ingestaba y almacenaba ese material). A partir de eso, **generar contenido** para redes
  y publicaciones del sitio (posts, reels, descripciones de producto) — con IA:
  transcripción de audio (Whisper, ya está en URUKU), generación de texto, y armado de
  piezas. Reusa el bridge WAHA + el webhook de ingesta que ya existen. **Analizar
  factibilidad y esfuerzo.** Encaja con los planes: "publicar por WhatsApp" (Plan 2/3) y
  el marketplace de contenido para creadores. Ver [[monetizacion-planes-uruku]].

## ✅ Hecho
- [x] VPS prod (KVM4, Brasil), Docker + Traefik, DNS Cloudflare, URUKU desplegado y vivo (HTTPS OK).
- [x] Rediseño URUKU (shell, home, buscar, ficha, mapa, mi-negocio) + selector de ciudad.
- [x] Reservalo: código migrado a `/tienda` parametrizado por `DOMAIN` (falta sacar Supabase).
