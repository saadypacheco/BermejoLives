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
- Imagen **traefik:v3.1**, HTTP→HTTPS, certresolver **letsencrypt** (HTTP challenge),
  email `saadypacheco@gmail.com`. Contenedor **Up** con puertos 80/443.

## Estado / próximos pasos
- [x] Dominios + Cloudflare + nameservers
- [x] DNS records (gris)
- [x] VPS base (Docker + ufw)
- [x] Traefik
- [ ] **Stack URUKU**: clonar `BermejoLives` → `/docker/uruku`, `python3 selfhost/init_prod_env.py uruku.bo`
      (genera secretos NUEVOS + escribe `.env` y `backend/.env`), luego
      `docker compose -f docker-compose.prod.yml --env-file .env up -d --build`.
- [ ] Verificar HTTPS (requiere `uruku.bo` **Active** en Cloudflare).
- [ ] **Reservalo** en `/docker/reservalo` → `uruku.bo/tienda` (basePath `/tienda`,
      parametrizado por `DOMAIN`, misma PWA). Ver cambios pendientes del repo Reservalo.
- [ ] Migrar el único comercio (re-registro en `uruku.bo/autoregistro`).
- [ ] Cargar redes de URUKU en `uruku.bo/publicador`.
- [ ] Flip DNS a Proxied + Full (strict); redirect 301 de los 3 dominios secundarios.
- [ ] Redeploy de Reservalo en **QA** a `encontralo.store/tienda` (consistencia).

## Credenciales
Generadas por `init_prod_env.py` (guardadas en el gestor de contraseñas del dueño, **no**
en el repo): admin / agente / publicador / panel WAHA. Los secretos de máquina viven solo
en `/docker/uruku/.env` y `/docker/uruku/backend/.env` del VPS.
