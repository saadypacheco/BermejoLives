# Pendientes — URUKU (prod uruku.bo + QA encontralo.store)

> Lista viva de lo que queda por hacer. Prod ya está **vivo** (uruku.bo). Ver
> [estado-vps-prod-uruku.md](estado-vps-prod-uruku.md) y [deploy-prod-nuevo-vps.md](deploy-prod-nuevo-vps.md).
> La **tienda (Reservalo)** tiene su propio plan: [plan-tienda-reservalo.md](plan-tienda-reservalo.md).

## 🔴 Ahora / alta prioridad
- [ ] **DNS: flip a Proxied + SSL Full (strict).** Hoy los records están en **gris (DNS only)**
      para el bootstrap de certificados. Pasar `@`, `www`, `tienda` a **Proxied (naranja)** y en
      Cloudflare **SSL/TLS → Full (strict)**. Dejar `api`, `db`, `api.tienda` en **gris** (no cachear
      API/base). Beneficio: CDN, DDoS, IP de origen oculta.
- [ ] **Record DNS `waha`** (A → 179.198.126.170, gris) — hoy Traefik erra el cert de `waha.uruku.bo`
      porque falta el registro. Alternativa: sacarle el label de Traefik si no se expone el panel.
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

## ✅ Hecho
- [x] VPS prod (KVM4, Brasil), Docker + Traefik, DNS Cloudflare, URUKU desplegado y vivo (HTTPS OK).
- [x] Rediseño URUKU (shell, home, buscar, ficha, mapa, mi-negocio) + selector de ciudad.
- [x] Reservalo: código migrado a `/tienda` parametrizado por `DOMAIN` (falta sacar Supabase).
