# Arquitectura de repos — Encontralo + Reservalo

> Decisión tomada 2026-06-30. Fuente de verdad de cómo se organizan y deployan
> los dos productos.

## Decisión: repos SEPARADOS, workflow UNIFICADO

Se mantienen **dos repositorios independientes**:

| Producto | Repo local | GitHub | Containers | Dominio |
|---|---|---|---|---|
| **Encontralo** | `c:\repos\proyectosClaude\Bermejo` | `saadypacheco/BermejoLives` | `buscadonde-frontend` (3003) · `buscadonde-backend` (8000) | `encontralo.store` |
| **Reservalo** | `c:\repos\proyectosClaude\reservalo` | `saadypacheco/reservalo` | `reservalo-frontend` · `reservalo-backend` | `encontralo.store/reservalo` (+ `reservalo.store` → 301) |

> Reservalo es **white-label** (deploy por cliente), por eso vive en su propio repo.

### Por qué separados (no monorepo)
- **Reservalo es white-label y reusable**: se despliega *por cliente* (Amanda, etc.), no es exclusivo de Encontralo. Meterlo en el repo de Encontralo acoplaría un producto reusable a un solo consumidor y complicaría sus otros deploys.
- **Ciclos de vida independientes**, stacks distintos, historiales de git distintos.
- Menor *blast radius*: un commit malo en uno no rompe el otro.

> Cuándo cambiaría a monorepo: solo si Reservalo dejara de ser white-label y pasara a ser **exclusivo** de Encontralo. Ahí: un repo con carpetas `encontralo/` + `reservalo/` y un `docker-compose` que orquesta los 4 servicios.

## Cómo se trabaja "como una sola solución"

### 1) Una sola ventana de VS Code — multi-root workspace
Archivo `encontralo-reservalo.code-workspace` (en `c:\repos\proyectosClaude\`):
```json
{
  "folders": [
    { "name": "Encontralo (mapa)", "path": "Bermejo" },
    { "name": "Reservalo (tienda)", "path": "reservalo" }
  ],
  "settings": {}
}
```
Abrir ese archivo → las dos carpetas en una sola ventana.

### 2) Deploy junto — un comando en el VPS
Script `deploy-all.sh` (ver `scripts/deploy-all.sh` en este repo). Hace `git pull` + rebuild de los dos:
```bash
cd /docker/buscadonde && git pull && docker compose -f docker-compose.prod.yml --env-file .env up -d --build
cd /docker/reservalo  && git pull && docker compose -f docker-compose.prod.yml --env-file .env up -d --build
```
> Confirmar el path real de Reservalo en el VPS (se asume `/docker/reservalo`).

### 3) Contrato de integración = fuente de verdad única
La API/relación entre ambos (path `/reservalo`, endpoints de productos, CORS, links cruzados) se documenta en **`docs/contrato-integracion.md`** (en este repo).

## Infra (recordatorio)
- **Encontralo** lo sirve el container **`buscadonde-frontend`** (puerto 3003), router Traefik `buscadonde-fe` = catch-all de `encontralo.store` (Host con 4 dominios → prioridad ~112).
- **Reservalo** (`reservalo-frontend`) monta `encontralo.store/reservalo` con router Traefik **`priority=1000`** (para ganarle al catch-all) + `PathPrefix('/reservalo')`, y en su `next.config`: `basePath/assetPrefix: '/reservalo'` + `skipTrailingSlashRedirect: true`. `reservalo.store` → 301 a `encontralo.store/reservalo/`.
- Ambos containers deben estar en la red externa de Traefik (`traefik`).
- La **PWA de Encontralo** tiene `scope: "/"` → cubre `/reservalo` ⇒ **una sola instalación, mapa + tienda juntos**.
