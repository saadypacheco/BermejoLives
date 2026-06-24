# Migración de dominio → encontralo.store

> Pasar producción de **buscadonde.com** a **encontralo.store** con **cero downtime**
> (Traefik sirve los dos en simultáneo durante la transición). Cuando confirmes que
> encontralo.store anda, se da de baja el viejo.

## Lo que ya quedó en el código (esta sesión)
- `docker-compose.prod.yml`: las reglas de Traefik aceptan `DOMAIN` **y** `DOMAIN_ALT`
  (FE: apex+www de ambos · BE: `api.` de ambos). Si `DOMAIN_ALT` no se setea, cae a `DOMAIN`.
- Backend CORS (`main.py`): `FRONTEND_URL` admite **varios dominios separados por coma**.
- Frontend ya rebrandeado (marca Encontralo, sin `buscadonde.com` en el bundle).

---

## Paso 1 · DNS (en el registrador de encontralo.store)
Apuntá a la IP del VPS (la misma que buscadonde.com, ej. **76.13.234.191** — confirmala):

| Tipo | Nombre | Valor |
|---|---|---|
| A | `@` | IP del VPS |
| A | `api` | IP del VPS |
| A (o CNAME) | `www` | IP del VPS (o CNAME a `encontralo.store`) |

Esperá a que propague (`nslookup encontralo.store` / `nslookup api.encontralo.store`).
**Importante:** `api.encontralo.store` debe resolver **antes** del deploy (Let's Encrypt
valida por HTTP para emitir el certificado).

## Paso 2 · Env del VPS (`/docker/buscadonde`)
En el **`.env`** raíz:
```
DOMAIN=encontralo.store
DOMAIN_ALT=buscadonde.com      # se sigue sirviendo durante la transición
```
En **`backend/.env`**:
```
FRONTEND_URL=https://encontralo.store,https://buscadonde.com
```

## Paso 3 · Deploy
```bash
cd /docker/buscadonde
git pull
docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```
Esto reconstruye el frontend con `NEXT_PUBLIC_API_URL=https://api.encontralo.store` y
Traefik pide los certificados de los hosts nuevos automáticamente.

## Paso 4 · Verificar
- https://encontralo.store (carga el sitio, candado OK)
- https://api.encontralo.store/health (responde)
- https://buscadonde.com sigue funcionando (transición)
- Probar login de comercio / admin desde encontralo.store (CORS OK).

## Paso 5 · Cutover final (cuando encontralo.store esté 100%)
Para dar de baja buscadonde.com:
1. `.env`: quitar `DOMAIN_ALT` (o dejarlo = `DOMAIN`).
2. `backend/.env`: `FRONTEND_URL=https://encontralo.store`.
3. Redeploy (paso 3).
4. (Opcional) Redirect 301 `buscadonde.com → encontralo.store` con un router Traefik,
   o dejar vencer el dominio viejo.

## Notas
- El **codename interno** `buscadonde` (paths `/docker/buscadonde`, contenedores
  `buscadonde-fe/-be`, repo GitHub) **no se renombra** todavía — es solo cosmético y va aparte.
- **Reservalo** (marketplace) tendrá su propio dominio/instancia (ver [[contrato-integracion]]).
