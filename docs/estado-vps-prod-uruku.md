# Bitácora · Montaje del VPS de producción (uruku.bo)

> Registro de lo que se fue haciendo para levantar **producción** en un VPS nuevo.
> Guía paso a paso: [deploy-prod-nuevo-vps.md](deploy-prod-nuevo-vps.md). Decisión de
> arquitectura: rebrand a URUKU, prod = VPS nuevo, QA = VPS actual (encontralo.store).

## Ambientes

| Ambiente | VPS | Plan | IP | Dominio |
|---|---|---|---|---|
| **PROD** | `srv1900330` (nuevo) | KVM 4 | `179.198.126.170` | `uruku.bo` |
| **QA** | `srv1064770` (existente) | KVM 2 | `76.13.234.191` | `encontralo.store` |

## Dominios (NIC.bo)
Registrados hasta **12/08/2027**: `uruku.bo` (principal), `uruku.com.bo`, `urucu.bo`,
`urucu.com.bo`. Los 3 secundarios → **301 a uruku.bo** (protección anti-typo).

## DNS (Cloudflare, plan Free)
- `uruku.bo` agregado a Cloudflare. Nameservers asignados: **`cortney.ns.cloudflare.com`**
  y **`watson.ns.cloudflare.com`**, cargados en NIC.bo (Administración DNS).
- Registros A → `179.198.126.170`: `@`, `www`, `api`, `db`, `tienda`, `api.tienda`.
- **Bootstrap:** todos en **DNS only (gris)** para que Let's Encrypt emita los certs por
  HTTP directo. **Después** del deploy, flip de `@`/`www`/`tienda` a **Proxied (naranja)**
  + SSL/TLS **Full (strict)**; `api`/`db`/`api.tienda` **quedan grises** (no cachear API/DB).

## VPS base (srv1900330)
- SO: **Ubuntu 24.04 LTS**.
- **Docker 29.7.2** + **Compose v5.4.0** (instalados con `get.docker.com`).
- Firewall **ufw**: 22/80/443 abiertos.
- Malware scanner (Monarx) activado en la compra (feature gratis de Hostinger).
- Acceso: terminal del navegador de Hostinger (root). Root password guardada aparte.

## Traefik (reverse proxy compartido)
- Carpeta `/docker/traefik`, red externa `traefik` creada, `acme.json` (chmod 600).
- Imagen **`traefik:latest`** (⚠️ v3.1 falla con Docker 29: `client version 1.24 is too old`
  → no ve contenedores → no emite certs; se resolvió actualizando la imagen).
- HTTP→HTTPS, certresolver **letsencrypt** (HTTP challenge), email `saadypacheco@gmail.com`.

## Estado / próximos pasos
- [x] Dominios + Cloudflare + nameservers
- [x] DNS records (gris)
- [x] VPS base (Docker + ufw)
- [x] Traefik (imagen actualizada por compat con Docker 29)
- [x] **Stack URUKU DESPLEGADO Y VIVO** (2026-08-13): `uruku.bo` 200, `api.uruku.bo/health`
      ok+connected, `db.uruku.bo` responde. HTTPS válido. Base vacía (aún sin comercios).
- [ ] DNS de `waha.uruku.bo` (faltaba → único cert que erraba; WhatsApp bridge, opcional).
- [x] **Reservalo DESPLEGADO** (2026-08-16) en `/docker/reservalo` → `uruku.bo/tienda`,
      **self-host completo, sin Supabase Cloud** (base propia Postgres+PostgREST, auth por
      token de URUKU, storage a disco). `api.tienda`/`db.tienda` con cert OK. Esquema completo
      (26 tablas). Integración URUKU→tienda conectada (`TIENDA_API_*` en el backend de URUKU).
      Fix clave del init: se excluyó `012_agente_bot.sql` (dependía del chat retirado y
      abortaba las migraciones 013+). Ver [deploy-prod-nuevo-vps.md](deploy-prod-nuevo-vps.md) Paso 5.
- [ ] Migrar el único comercio (re-registro en `uruku.bo/autoregistro`).
- [ ] Cargar redes de URUKU en `uruku.bo/contenido`.
- [ ] Flip DNS a Proxied + Full (strict); redirect 301 de los 3 dominios secundarios.
- [ ] Redeploy de Reservalo en **QA** a `encontralo.store/tienda` (consistencia).

## Credenciales
Generadas por `init_prod_env.py` (guardadas en el gestor de contraseñas del dueño, **no**
en el repo): admin / agente / publicador / panel WAHA. Los secretos de máquina viven solo
en `/docker/uruku/.env` y `/docker/uruku/backend/.env` del VPS.
