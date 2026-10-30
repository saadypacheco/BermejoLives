# Credencial de los agentes y página de agentes

> **Estado:** spec para implementar (30/10/2026). Es la etapa **E5** de
> `docs/grupos-por-comercio.md` (§7.6, §9.5, §9.9 de la v1: `git show 88f9905:docs/grupos-por-comercio.md`),
> con los cambios de abajo. Si esta spec y aquélla dicen cosas distintas, **gana ésta**.

## 1. Qué pide el dueño

- Cada agente lleva una **credencial** impresa: dice URUKU, su **foto**, **nombre y apellido**, y un **QR**.
- Quien escanea el QR ve en `uruku.bo` que esa persona **es agente de URUKU** (o que ya no lo es).
- Una **página pública con todos los agentes** de URUKU.

## 2. Cambios respecto de E5 de la spec de grupos

| Tema | Spec de grupos | Acá |
|---|---|---|
| Ruta pública de la credencial | `/agente/<token>` | **`/agentes/<token>`** (cuelga de la lista) |
| Lista de agentes | no había | **`/agentes`** pública + `GET /public/agents` |
| Nombre | `nombre` | `nombre` + **`apellido`** (columna nueva en `usuarios_panel`) |
| QR de la comunidad de comercios en la tarjeta | sí | **no todavía**: la comunidad es E2 y no existe. La tarjeta deja el lugar armado para sumarlo después |
| Alerta al escanear una revocada | tabla de alertas (E4) | E4 no existe: **log** `credencial.revocada_escaneada` (warning) |
| «Mi credencial» en la app del agente | sí | **fuera de esta entrega** (pendiente) |
| Tamaño de la tarjeta | A7 | **CR80 vertical** (54 × 85,6 mm, la de las tarjetas de crédito: entra en cualquier portacredencial) |
| URL del QR | la arma el backend | la arma el **frontend**: `window.location.origin + "/agentes/" + token` (en QA sale encontralo.store, en prod uruku.bo) |

## 3. Datos — `selfhost/postgres-init/0163_agent_credentials.sql`

- `usuarios_panel`: `apellido text`, `photo_url text`, `publicacion_consentida_at timestamptz` (consentimiento para publicar foto y nombre).
- Tabla `agent_credentials`: `id uuid pk`, `usuario_id uuid not null references usuarios_panel(id)`,
  `token text not null unique check (length(token) >= 22)`, `activo boolean not null default true` (= vigente),
  `issued_by text`, `issued_at timestamptz default now()`, `revoked_by text`, `revoked_at timestamptz`,
  `revoke_reason text`, `last_scan_at timestamptz`, `scan_count int not null default 0`.
  Índice único parcial `(usuario_id) where activo` → nunca dos vivas por agente.
- RLS activo, `revoke all` a anon/authenticated, `grant` a `service_role`. Nada se lee por PostgREST: todo pasa por el backend.
- Token: `secrets.token_urlsafe(16)` (128 bits, 22 caracteres).
- Nunca DELETE: revocar = `activo=false` + `revoked_*`.

## 4. API (backend, router nuevo `app/api/agent_credentials.py`)

Contrato fijo: el frontend se arma contra esto en paralelo.

| Método y ruta | Permiso | Cuerpo | Respuesta |
|---|---|---|---|
| `GET /admin/agents/{usuario_id}/credential` | `equipo` | — | `{"credential": {"token","issued_at","scan_count","last_scan_at"} \| null, "photo_url": str\|null, "nombre": str\|null, "apellido": str\|null, "ciudad_nombre": str\|null, "activo": bool, "consentimiento_at": str\|null}` |
| `POST /admin/agents/{usuario_id}/credential` | `equipo` | `{"consiente": bool}` (opcional; sólo hace falta la primera vez) | Emite una nueva; si había una viva la revoca con `revoke_reason='reemitida'`. 400 (en español) si no tiene rol `agente` (o un rol con `comercios.cargar`), si no tiene **foto**, **nombre** o **apellido**, o si está inactivo. Si la persona no tiene consentimiento guardado y `consiente` no es `true` → 400 «Falta el consentimiento del agente para publicar su foto y su nombre»; si es `true` se guarda `usuarios_panel.publicacion_consentida_at = now()`. Emisión simultánea de otra persona → 409 «Otra persona acaba de emitir esta credencial. Recargá.». Devuelve lo mismo que el GET |
| `POST /admin/agents/{usuario_id}/credential/revoke` | `equipo` | `{"reason": str (obligatorio), "cut_access": bool}` | `{"ok": true}`. `cut_access` además pone `usuarios_panel.activo=false` |
| `POST /admin/agents/{usuario_id}/photo` | `equipo` | multipart `foto` (jpg/png/webp, ≤ 8 MB) | `{"photo_url": "<base pública>/fotos/agentes/<aleatorio>.jpg"}`. Se re-codifica a JPEG (máx. 800 px de lado, sin EXIF), nombre aleatorio (no el id), en `fotos_dir/agentes/`. La foto anterior no se borra del disco |
| `GET /public/agents` | público | — | `{"items": [{"nombre","apellido","ciudad_nombre","ciudad_slug","photo_url","desde"}]}`: sólo agentes **activos, que hoy siguen siendo agentes, con credencial vigente, foto y consentimiento**. `desde` es `AAAA-MM-DD` en hora de La Paz. Orden: ciudad, apellido, nombre. **Sin** token, id, email, teléfono, roles. `Cache-Control: public, max-age=60` |
| `GET /public/agents/{token}` | público | — | `{"status": "valid"\|"revoked"\|"inactive", "nombre","apellido","ciudad","photo_url","issued_at","checked_at"}`. `Cache-Control: no-store`. Suma `scan_count` y `last_scan_at`. Token inexistente → **404 `{"detail": "Esta credencial no es de URUKU"}`, siempre el mismo cuerpo** |

- `revoked` = la credencial se dio de baja; `inactive` = la credencial sigue viva pero el usuario está desactivado **o ya no es agente** (perdió el rol o el rol perdió `comercios.cargar`). Para los dos, la página pública dice «NO ES AGENTE DE URUKU».
- **Sin limitador** en `GET /public/agents` ni `/public/agents/*` (decisión de revisión): el backend sólo ve la IP del servidor de Next, así que un tope «por IP» sería un tope global que cualquiera agotaría para tirar todas las verificaciones de QR. El token tiene 128 bits y su forma se valida antes de ir a la base: no hay nada que enumerar. La lista se cachea 60 s.
- **Sacar el rol de agente revoca** la credencial vigente: `PUT /admin/equipo/{id}` con roles que ya no dan `comercios.cargar` la revoca con `revoke_reason='sin rol de agente'`. `PUT /admin/equipo` ya no toca `activo` si el pedido no lo trae (antes lo reactivaba); `POST` crea activo.
- Las fotos bajo `/fotos/agentes/` salen con `X-Robots-Tag: noindex`.
- `/admin/equipo` (GET, POST, PUT en `api/moderacion.py`): suman `apellido` (y el GET devuelve `apellido`, `photo_url` y `publicacion_consentida_at`). Nunca `password_hash`.
- **Corte de acceso (T16):** TODAS las dependencias del panel (`require_permiso`, `require_alguno`, `require_panel`, `require_admin/moderador/publicador`) y `require_agente` (`/campo/*`) miran el estado actual de la cuenta en `usuarios_panel` (`repo.get_acceso_usuario_panel(email)`, caché en memoria de 60 s). Cuenta desactivada → 401 «Tu acceso fue dado de baja». En `require_agente` además se exige que HOY tenga `comercios.cargar` según sus roles en la base (el JWT puede llevar permisos viejos hasta 7 días). `None` (la cuenta del `.env`, sin fila) → pasa y, en campo, loguea `auth.agente_sin_fila`. Si la base falla se respeta lo último que se sabía de la cuenta, aunque el caché esté vencido (una baja conocida no se reabre); sin estado previo se deja pasar.
- structlog: `credencial.emitida`, `credencial.revocada`, `credencial.revocada_escaneada` (warning, sin IP), `agente.foto_subida`, `agente.consentimiento_registrado`, `credencial.emision_fallida_tras_revocar` (error; la vigente de antes se reactiva). Los ids de usuario de los endpoints de admin son UUID (si no, 422).

## 5. Frontend

### 5.1 `/agentes` (pública)
- Título «Agentes de URUKU». Bajada: «Son las únicas personas que visitan comercios en nombre de URUKU. **Los agentes de URUKU nunca cobran**: los planes se pagan sólo por QR en uruku.bo/pagar.»
- Tarjetas por ciudad: foto, nombre y apellido, ciudad, «Agente desde <mes año>».
- **Nunca** cuántos son (regla del sitio: sin cifras al público).
- «¿Te visitó alguien que no está acá? Avisanos al WhatsApp» con `waUruku(...)` de `lib/contacto.ts`.
- Lee `GET /public/agents` en el servidor con `revalidate: 60`. Sin agentes: «Pronto vas a ver acá a los agentes de URUKU.»
- Link en el pie del sitio: «Agentes de URUKU». `middleware.ts`: sumar `/agentes` a `PERMITIDAS`.

### 5.2 `/agentes/[token]` (pública, la que abre el QR)
Como §9.9 de la v1 (con `nombre apellido`):
- **Vigente:** foto grande, nombre y apellido, «Agente de URUKU · <ciudad>», «✓ VIGENTE» en verde, «Comprobado hoy dd/mm · hh:mm:ss» con **reloj que corre** (inutiliza una captura vieja), «LOS AGENTES DE URUKU NUNCA COBRAN. Pagá sólo por QR a URUKU: uruku.bo/pagar», «¿Te pidieron plata? Avisanos al WhatsApp …», «Fijate que arriba diga uruku.bo», link «Ver todos los agentes».
- **revoked / inactive:** fondo rojo, «NO ES AGENTE DE URUKU. Esta credencial se dio de baja. No le pagues nada.», con foto y nombre para reconocerlo.
- **404:** «Esta credencial no es de URUKU.»
- `robots: noindex`, `dynamic = "force-dynamic"`, `fetch` con `cache: "no-store"`.
- Íconos sólo de `components/ic.tsx` (nada de emojis; el ✓ es `<Ic>`).

### 5.3 Admin › Equipo (`components/equipo-panel.tsx`)
Para cada usuario que carga comercios (mismo criterio que `agentesDe` en `components/admin/manuales-panel.tsx`):
- Campo **Apellido** junto a Nombre (alta y edición).
- Bloque **Credencial**: foto (miniatura + «Subir foto»), estado («Vigente desde dd/mm/aaaa · escaneada N veces» / «Sin credencial»), botones **[Emitir]** o **[Reemitir]**, **[Ver e imprimir]**, **[Revocar…]** (pide motivo y tilde «Cortarle también el acceso al panel»). Reemitir avisa que la tarjeta impresa vieja deja de valer.
- Errores del backend se muestran tal cual (vienen en español).
- Nada de `window.confirm` antes de abrir el selector de archivos (Chrome lo bloquea); confirmar inline.

### 5.4 Tarjeta para imprimir — `/admin/credencial/[usuarioId]`
- Página cliente (usa el JWT del admin), lee `GET /admin/agents/{id}/credential`. Sin credencial vigente → aviso y vuelta a Equipo.
- Tarjeta **CR80 vertical (54 × 85,6 mm)** con `@page`/`@media print`: logo y nombre URUKU arriba, foto, **nombre y apellido** grande, «Agente de URUKU · <ciudad>», QR a `${window.location.origin}/agentes/<token>` (negro sobre blanco, margen 1, corrección M, como el volante), «Escaneá para comprobar que soy agente», «**Los agentes de URUKU nunca cobran.**». Reverso en la misma hoja: «Si alguien te pide plata en nombre de URUKU, no pagues y avisanos», WhatsApp de URUKU y `uruku.bo/agentes`.
- Botón «Imprimir» (`window.print()`), oculto al imprimir. Dos copias por hoja A4 está bien.
- QR con la librería `qrcode` que ya está en `package.json`, importada dinámicamente (no sumarla al bundle del resto).
- Componente reutilizable `components/agent-credential-card.tsx` (para «Mi credencial» más adelante).
- Colores y tipografía del manual de identidad (`app/styles/`, clases existentes).

## 6. Criterios de terminado

1. Token ≥ 22 caracteres; reemitir revoca la anterior; nunca dos vivas (índice parcial).
2. Las respuestas públicas no traen email, teléfono, ids, roles, permisos ni (en la lista) el token.
3. Token inexistente → 404 con el mismo cuerpo siempre.
4. Revocar con `cut_access` → el agente recibe 401 en `/campo/*` en ≤ 60 s.
5. La lista sólo muestra activos con credencial vigente y foto; nunca un número de agentes.
6. Las páginas dicen «Los agentes de URUKU nunca cobran».
7. El QR impreso se lee desde otro celular y abre `/agentes/<token>`.
8. `pytest` verde, `npm run lint` y `npm run build` verdes.

## 7. Pendiente (no entra acá)
- QR de la comunidad de comercios en la tarjeta (cuando exista E2).
- «Mi credencial» en la app del agente (`GET /campo/my-credential`).
- **Dueño:** pedir el consentimiento de cada agente para publicar su foto y su nombre.
