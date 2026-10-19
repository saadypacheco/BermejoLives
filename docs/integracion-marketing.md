# Integración con el sistema de marketing: API con API key, alcance por comercio e idempotencia

- **Fecha:** 2026-10-16 (decisiones del dueño del 2026-10-19 incorporadas)
- **Estado:** implementado en la rama `integracion-marketing` (todavía sin mergear). La decisión sobre `verificado`
  (más abajo) está **aprobada por el dueño el 2026-10-19**. Facebook e Instagram están **postergados** (ver
  «Convivencia con posteos manuales del equipo»).
- **Contrato de origen:** `marketing/docs/arquitectura.md` §8 y ADR 0003 del repo de marketing. Este documento es el
  ADR de Uruku que ese contrato pedía.
- **Migraciones:** 0156, 0157 y 0158, en `supabase/migrations/` y `selfhost/postgres-init/` (idénticas). Los
  números 0156–0158 están **reservados para esta rama**: `main` sigue desde la 0159.

## Contexto

El sistema de marketing toma las ofertas que los comercios mandan por WhatsApp, las enriquece (precio, vigencia,
texto), arma el post cuadrado y, con la aprobación de una persona **de marketing**, hace que Uruku las apruebe y las
difunda en Facebook e Instagram. Uruku sigue siendo dueño de la oferta y de la difusión: marketing **nunca** toca su
base (brief §9).

Lo que hacía falta y no existía (verificado en el código):

- Uruku no tenía autenticación máquina a máquina entrante. El panel usa JWT de persona con permisos
  (`core/auth.py`); darle a una máquina un usuario del panel era darle todos los comercios y una contraseña humana.
- Un comercio `confiable` publica **directo** (aprobado + difusión) en la ingesta, en «Mi comercio» y en la
  auto-aprobación de la IA. Con marketing en el medio eso son dos dueños de la aprobación.
- La difusión no aceptaba texto ni imagen propios, no guardaba el id del posteo ni su enlace, y no tenía un estado para
  «mandé y no sé si salió».
- `publicaciones` no tenía `updated_at`, así que no había cómo pedir «lo que cambió desde la última vez».
- `GRAPH_API_VERSION` estaba escrita a mano (`v20.0`, removida por Meta el 24/9/2026).

## Decisión

### 1. API key con alcance por comercio

`Authorization: Bearer uki_<key_id>.<secreto>`. En la base queda **sólo `sha256(secreto)`**
(`integracion_clientes`); el secreto se muestra una vez al emitir la clave. Cada clave tiene **scopes**
(`publications:read`, `publications:write`, `media:write`, `broadcast:send`) y, por su cliente, un **alcance**: los
comercios de `integracion_comercios`. Fuera del alcance todo es **404** (no 403: no se filtra la existencia). 401 igual
para clave inexistente, mal escrita, revocada o inactiva. Límite de **60 pedidos por minuto por clave**
(429 + `Retry-After`; en memoria: una instancia de API).

Una rotación crea una clave nueva del mismo cliente (`grupo_id`), con el mismo alcance y scopes, y deja las dos
activas hasta que se revoque la vieja.

### 2. Endpoints (`/v1/integration`)

| # | Ruta | Scope | Uso |
|---|---|---|---|
| E1 | `GET /me` | — | key_id, scopes, ids de los comercios del alcance, versión |
| E2 | `GET /merchants` | read | `id, slug, nombre, ciudad, plan, plan_tiene_redes, grupo_atado, activo, public_url, broadcast_footer{facebook,instagram}` |
| E3 | `GET /publications?cursor=&limit=&estado=` | read | cambios desde el cursor `(updated_at, id)` (opaco), `limit` 1–100 (50) |
| E4 | `GET /publications/{id}` | read | detalle con media y ETag (también en el header) |
| E5 | `PATCH /publications/{id}` | write | enriquecer contenido (sólo `pendiente`); no cambia el estado |
| E6 | `POST /media` (multipart `file`) | media | JPEG cuadrado; idempotente por sha256; se guarda sin recomprimir; ≤ 12 MB |
| E7 | `POST /publications/{id}/moderation` | write | `approve` / `reject` + difusión (texto, imagen, destinos) |
| E8 | `GET /publications/{id}/broadcasts` | read | filas de Facebook/Instagram |
| E9 | `POST /publications/{id}/broadcasts/send` | broadcast:send | envía las filas pendientes (Facebook/Instagram) |
| E10 | `POST /broadcasts/{fila_id}/verify` | read | relee el posteo en la Graph API y guarda `permalink` + `verificado_at` |

Errores: `{"error": {"code", "message", "details"}}`, mensajes en español. Códigos: `unauthorized` (401),
`scope_insuficiente` (403), `not_found` (404), `not_pending` / `not_approved` / `codigo_no_coincide` /
`comercio_de_baja` / `not_sent` / `verification_failed` / `idempotency_in_progress` (409), `etag_mismatch` (412),
`validation` / `idempotency_key_required` / `idempotency_key_reused` / `destino_no_habilitado_por_plan` /
`destino_no_configurado` / `media_not_found` (422), `if_match_required` (428), `rate_limited` (429),
`graph_unavailable` (502).

### 3. Idempotencia y concurrencia

- Toda escritura exige `Idempotency-Key` (≤ 128). Se guarda 7 días en `integracion_idempotencia`
  `(cliente, key) → (request_hash, status, response)`. Misma clave + mismo cuerpo ⇒ **la misma respuesta**, sin volver
  a aplicar; misma clave + otro cuerpo ⇒ `422 idempotency_key_reused`.
- **La búsqueda de idempotencia va ANTES de todo lo demás** (existencia, `If-Match`, estado): un reintento tras un
  timeout recibe la respuesta original y no un 412 provocado por su propio efecto (así lo da por hecho el cliente de
  marketing y su doble).
- La clave se **reclama** con un INSERT contra la clave primaria (resuelve la carrera entre dos pedidos iguales: el
  segundo recibe `409 idempotency_in_progress`); se guarda sólo la respuesta exitosa y un error libera la clave; una
  reclamación abandonada (> 2 min) se retoma.
- ETag = sha256 de título, descripción, precio, moneda, descuento, vigencia, tipo, imagen, estado y `activo`. Toda
  escritura sobre una publicación exige `If-Match` (428 si falta, 412 si cambió). Además el `UPDATE` es **condicional**
  (`estado = 'pendiente'` y el `updated_at` leído): si el comercio o un moderador la tocó entre la lectura y la
  escritura, no se aplica (412).

### 4. Comercio «gestionado»

Un comercio con una fila **activa** en `integracion_comercios` es gestionado. Es la marca (no se agregó ninguna
columna a `comercios`, regla 11). Efectos:

| Dónde | Efecto |
|---|---|
| `services/ingest.py` | la publicación queda **siempre `pendiente`**, sin `moderado_por` y **sin `difusion.encolar`**, aunque el comercio sea `confiable` |
| `services/ingest.py` (fusión foto + precio) | un gestionado sólo se junta con una publicación **pendiente**: no se le cambia por debajo una ya aprobada o rechazada |
| `services/revision_ia.py` | excluido de la auto-aprobación por IA (la IA sigue opinando) |
| `api/comercio.py` | editar, publicar o destacar desde «Mi comercio» no usa `confiable`: vuelve a `pendiente` |
| `api/moderacion.py` | aprobar desde el panel ⇒ **409**, salvo `override_gestionado: true` de un admin (permiso `equipo`) con motivo ≥ 10 caracteres; queda en `integracion_eventos` y en `motivo_moderacion` (`override-gestionado: …`). Rechazar o pedir cambios sí se puede |
| difusión | las filas pedidas por la integración (`solicitado_por`) **no las toma** el worker automático ni «enviar todo» del panel: sólo E9, para que nadie las mande dos veces |

**Falla cerrado:** si no se puede saber si un comercio es gestionado (la base no contesta, la tabla no existe),
se lo trata como gestionado: la publicación queda pendiente, que es siempre el estado seguro. Consecuencia de
despliegue: **aplicar las migraciones 0156–0158 antes que el código** (sin la 0157 el `INSERT` de la ingesta falla; sin
la 0156 los comercios `confiable` quedarían en moderación).

Tests de regresión (`tests/test_integracion_gestionado.py`): los comercios no gestionados siguen igual (confiable ⇒
aprobado + difusión; no confiable ⇒ pendiente; código ⇒ cola; duplicados; fusión; explorador; IA; «Mi comercio»;
panel) y que sacar a un comercio del alcance lo devuelve a su flujo de siempre.

### 5. Difusión (`services/difusion.py`)

- `difusion_cola` suma `texto_override`, `imagen_url_override`, `solicitado_por`, `external_post_id`,
  `ig_container_id`, `permalink`, `verificado_at` y el estado **`incierto`** (0158).
- Al enviar, el texto es el aprobado + el **pie estándar de Uruku** (comercio, ciudad y enlace con `?ref=fb|ig`), igual
  que `texto_de`; `E2.broadcast_footer` y `texto_final` de E7 salen de la misma función.
- `incierto` = «mandé y no sé si salió» (timeout, corte tras enviar, 5xx, respuesta que no es JSON). **Nunca se reintenta
  a ciegas:** primero se consulta a Meta. Facebook: se busca el posteo por su texto en los últimos de la página.
  Instagram: se consulta el `status_code` del contenedor guardado (`FINISHED` ⇒ se publica ese mismo; `PUBLISHED` ⇒
  se busca el posteo, no se republica; `IN_PROGRESS` ⇒ sigue incierto; `ERROR`/`EXPIRED` ⇒ se crea uno nuevo). El
  botón «reintentar» del panel hace lo mismo con una fila `incierto`.
- E9 reclama cada fila con un `UPDATE ... WHERE estado = 'pendiente'` (→ `incierto`) **antes** de llamar a Meta: dos
  pedidos a la vez no mandan la misma fila, y si el proceso muere a mitad de la llamada la fila queda `incierto`, que es
  lo único que de verdad se sabe.
- **WAHA sólo lee:** nada de esta API manda por WhatsApp. Los destinos de la integración son Facebook e Instagram (por
  la Graph API), **hoy sin uso**: están postergados y `DIFUSION_AUTO` sigue en `wa_canal` (ver «Convivencia con
  posteos manuales del equipo»).
- **Versión de Graph (`GRAPH_API_VERSION`, default `v26.0`):** todas las URLs (Facebook, Instagram, WhatsApp Cloud,
  estado de la sesión Cloud, descarga de media Cloud, OTP) salen de `settings.graph_base()`; ninguna versión quedó
  escrita a mano (hay un test que lo impide). La v20.0 se removió el 24/9/2026; la v26.0 salió el 29/7/2026 y no
  tiene cambios incompatibles documentados desde la v21 para `/photos`, `/feed`, `/{ig-user}/media`, `media_publish` ni
  `/{phone-id}/messages`. La respuesta de publicar **no** trae `permalink_url`: E10 lo pide con
  `GET /{post-id}?fields=permalink_url` (IG: `permalink`). El 27/10/2026 Meta apaga `date_format`, `GET /?ids=` y el
  ETag de Graph en todas las versiones: el código no usa ninguno (test).

### 6. Datos que NO salen por la API

Ningún teléfono, `wa_jid`, `raw` de WAHA, `wa_message_id`, `moderado_*`, ni el **código URUKU-XXXX** (el 409
`codigo_no_coincide` usa un mensaje propio, no el del panel, que trae los códigos), ni la **marca `verificado`**, ni
cuántos comercios hay fuera del alcance. El quién mandó el mensaje sale como `sender_role`
(`merchant | third_party | uruku_explorer`), que la ingesta ahora guarda en `publicaciones.remitente_rol` (0157):
`third_party` es otro participante del grupo o alguien que sólo conoce el código del local.

## Decisión aprobada (2026-10-19): el alcance lo arma el admin, `verificado` no se expone

El cliente de marketing hoy **sólo importa comercios con `verificado = true`** y espera ese campo en E2. Esta
implementación **no lo manda**, a propósito, y el dueño lo aprobó el 2026-10-19:

- `verificado` es un dato interno de Uruku (lo marca el equipo tras visitar el comercio). El público **no lo ve** hoy
  (no está en `feed_publico` ni en las columnas que se dan a anon). Sacarlo por una API cambia quién lo conoce, y un
  tercero pasaría a poder listar «qué comercios verifica Uruku» con sólo mirar qué cambia.
- Lo que necesita marketing no es el dato sino **el alcance**: «qué comercios me asignaron». Esa decisión es de Uruku
  (es dueño de los comercios y de la relación con ellos), y ya existe donde corresponde: `integracion_comercios`.
- Así el dueño controla el piloto con un endpoint de admin, sin exponer nada:
  - `GET  /admin/integracion/clientes` — las claves (nunca el hash).
  - `GET  /admin/integracion/clientes/{id}/comercios` — el alcance de un cliente.
  - `POST /admin/integracion/clientes/{id}/comercios` `{comercio_ids: [...]}` — agregar.
  - `DELETE /admin/integracion/clientes/{id}/comercios/{comercio_id}` — quitar (baja lógica).
  - `POST /admin/integracion/clientes/{id}/comercios/verificados[?simular=true]` — **agregar en bloque todos los
    comercios activos y verificados** que todavía no están (con `simular=true` sólo muestra a quiénes alcanzaría).
  Todo con el rol admin existente (`equipo`) y con rastro en `integracion_eventos`.
- **Un comercio que se verifica DESPUÉS de armado el alcance NO entra solo.** «Agregar verificados en bloque» es una
  foto del momento en que se aprieta: no hay ninguna regla que mantenga el alcance sincronizado con `verificado`.
  Para que un comercio recién verificado entre, el admin lo agrega a mano o vuelve a correr el bloque (es idempotente:
  suma sólo los que faltan). Es a propósito: entrar al alcance le quita al comercio el publicar directo, y eso lo
  decide una persona, no un efecto lateral de marcar `verificado`.
- Criterio de elegibilidad para marketing: **toma los comercios activos que aparecen en E2** (el alcance ya filtró
  quiénes). Lo que cambia del lado de marketing (su `sync.upsert_merchants` y su doble): **dejar de exigir
  `verificado`**. Hasta que eso cambie, **el cliente actual de marketing no importa ningún comercio** contra esta API
  (si Uruku no manda `verificado`, no importa nada; es el comportamiento seguro que su nota de implementación 5 ya
  prevé).
- Si en el futuro se quisiera exponerlo igual, es sumar una clave a E2: se decide acá y se ajusta una línea.

## Convivencia con posteos manuales del equipo

**Decisión del dueño (2026-10-19): Facebook e Instagram quedan postergados.** Hoy la página la maneja un equipo
humano. Hasta nuevo aviso **nada de Uruku publica en Facebook ni en Instagram**: `DIFUSION_AUTO` conserva su default
(`wa_canal`) y `facebook` / `instagram` no se agregan. E9 (enviar) y E10 (verificar) están implementados y probados con
dobles, pero **sin uso**: ningún cliente los llama mientras esto siga así.

Lo que el diseño ya garantiza para cuando convivan con los posteos manuales:

- **Filas separadas del worker.** Lo que pide la integración se encola en `difusion_cola` con `solicitado_por` y el
  worker de siempre (`difusion_pendientes`) **no las toma**: sólo las envía E9. Un proceso automático no puede mandar
  por su cuenta algo que pidió marketing, y la cola de la difusión tradicional no cambia.
- **`solicitado_por` en cada fila**: queda quién pidió cada posteo (rastro en la fila y en `integracion_eventos`).
- **Verificación por permalink (E10).** Después de publicar se relee el posteo con el token de Uruku y se guarda
  `permalink` + `verificado_at`; el enlace sale de Meta, no de lo que diga el cliente.
- **Nunca a ciegas:** el estado `incierto` obliga a consultar a Meta antes de reintentar.

Lo que **haría falta** cuando se active (no se implementó nada de esto):

- **No reenviar lo que el equipo ya posteó a mano.** Hoy Uruku sólo sabe lo que él mismo publicó. Si el equipo subió
  a mano la misma oferta, E9 la publicaría de nuevo. Hace falta una forma de decirle «esta oferta ya salió en tal
  red» antes de pedir E9, o que el equipo marque la oferta como ya publicada.
- **Registrar los posteos manuales** (red, enlace/id, oferta, quién y cuándo) como fila de `difusion_cola` en estado
  `enviado` con `external_post_id` / `permalink`, para que E8 y la reconciliación de marketing los vean y los
  consideren.
- **La búsqueda de un `incierto` en Facebook compara texto con los últimos posteos de la página**, que ahora incluirán
  los del equipo: una oferta idéntica posteada a mano podría confundirse con la propia. Con el registro de manuales de
  arriba (o buscando por el `external_post_id` guardado) el riesgo desaparece.
- Un acuerdo operativo para el cambio de manos: quién maneja la página y desde qué fecha, y el plan de cada comercio
  (el plan filtra los destinos como siempre).

## Alternativas consideradas

| Alternativa | Por qué no |
|---|---|
| Usuario «moderador» de servicio con el login del panel | contraseña humana en una máquina, ve todos los comercios, sin scopes ni alcance |
| Marketing lee/escribe por PostgREST con `service_role` | prohibido por el brief; saltea la lógica de moderación y de difusión |
| OAuth2 client credentials / mTLS | no hay emisor de tokens ni PKI; un solo consumidor: sobredimensionado. Se reconsidera con más consumidores |
| Webhooks Uruku → marketing en vez de polling | exigiría cola de eventos, reintentos salientes y firma; el polling de 60 s con cursor alcanza |
| Marca de «gestionado» como columna de `comercios` | rompería la regla 11 y mezclaría datos del comercio con una relación comercial; la tabla de alcance lo resuelve y se puede sacar sin migrar |
| Marketing publica directo en Meta con su token | duplica la difusión y reparte las credenciales de la página de Uruku (que siguen sólo en Uruku) |

## Emitir, rotar y revocar una API key

Las claves **no pasan por HTTP**: se manejan en el servidor, con el `.env` del backend (la `service_role`):

```bash
cd backend
python -m scripts.integracion_clave emitir --nombre "Marketing"        # imprime la clave UNA sola vez
python -m scripts.integracion_clave rotar  --key-id <key_id>          # clave nueva; la vieja SIGUE activa
python -m scripts.integracion_clave revocar --key-id <key_id>         # desde ya da 401
python -m scripts.integracion_clave listar                            # sin secretos
```

- La clave es `uki_<key_id>.<secreto>`. En la base queda `sha256(secreto)`; **si se pierde no se recupera, se rota**.
  Va al `.env` de marketing (`URUKU_API_KEY`), nunca a una base ni a un chat.
- Rotar sin cortar: `rotar` → poner la clave nueva en marketing → comprobar `GET /me` → `revocar` la vieja.
- Emitir, rotar y revocar quedan en `integracion_eventos` (sin secretos). Después de emitir, el admin agrega los
  comercios al alcance con los endpoints de arriba (o en bloque los verificados).
- Sin alcance, una clave válida ve `comercios: []` y no puede leer ni tocar nada.

## Consecuencias y riesgos

- **Núcleo productivo tocado** (`ingest.py`): medio-alto. Mitigado con los tests de regresión de arriba, el cambio
  acotado (una consulta por mensaje + `remitente_rol`) y la falla cerrada. Un comercio `confiable` que entra al alcance
  **pierde el publicar directo**: es el objetivo, pero conviene avisárselo al dueño del comercio.
- Rate limit, contadores y `last_used_at` son en memoria / por proceso: una sola instancia de API. Con réplicas hay que
  moverlos a la base.
- E9 envía de forma **síncrona** (una llamada a Meta por fila, hasta 30 s cada una). El cliente de marketing usa 20 s de
  timeout: si Meta tarda, el pedido se corta del lado de marketing pero la fila ya quedó reclamada; su reconciliación
  lee E8 y decide. Si en la práctica pasa seguido, E9 se pasa a «encola y responde» y marketing sondea E8.
- La búsqueda de un posteo `incierto` en Facebook/Instagram compara el comienzo del texto con los últimos posteos
  (la página por defecto de Graph). Una oferta con el mismo texto que otra reciente podría confundirse; el pie con el
  enlace del comercio lo vuelve poco probable. Si Meta no responde, la fila sigue `incierto` (nunca se asume).
- Una publicación anterior a la 0157 no tiene `remitente_rol`: la API lo deduce (explorador, panel, número conocido) y, si
  no alcanza, manda `null` (marketing lo ignora, que es lo seguro).
- `fusionada` (en el ejemplo del contrato) **no** se devuelve: Uruku no guarda cuáles publicaciones resultaron de juntar
  dos mensajes.
- El E2 `public_url` es `{SITIO_URL}/comercios/{slug}` (`https://uruku.bo/...`): el host de la verificación pública de
  marketing (`URUKU_MEDIA_ALLOWED_HOSTS`) tiene que incluir el del sitio, que no es el de la API.

## Recomendación (no aplicada): `feed_publico` y `vence_el`

La vista `feed_publico` **no filtra `vence_el`**: una oferta vencida sigue visible hasta que alguien la baje. Con
marketing cargando vigencias (E5 `vence_el`) el problema se nota más. **No se tocó**: cambia lo que ve el público y lo
decide el dueño. Recomendación: filtrar `vence_el is null or vence_el >= current_date` en la vista; es independiente
del piloto y reversible.

## Cómo se verificó

- `cd backend && pytest` (con `URUKU_PG_TEST_CONTAINER=<contenedor>` además corre los chequeos contra un Postgres real).
- Humo con el **cliente real** de marketing (`app/uruku/client.py`) contra este backend + PostgREST + Postgres reales
  (cadena `selfhost/postgres-init` completa): E1–E8, idempotencia, ETag, 401/404/409/412/422 y el 409 del panel. E9 y E10
  sólo con tests (la URL de Graph no se puede apuntar a un doble y no hay token de Meta de prueba).
- Migraciones 0156–0158: idénticas en las dos carpetas (`diff`), corren dos veces sin error y anon/authenticated no
  tienen ningún permiso sobre las tablas nuevas ni sobre las columnas nuevas de `publicaciones`.

## Pendiente

- Marketing: dejar de exigir `verificado` y tomar los comercios activos de E2 (decisión aprobada el 2026-10-19).
- Facebook/Instagram postergados: cuando se activen, resolver los puntos de «Convivencia con posteos manuales del
  equipo» antes de agregar los destinos a `DIFUSION_AUTO` o de llamar a E9.
- Decidir `feed_publico` / `vence_el`.
- Probar E9/E10 con la página y el Instagram reales de Uruku (H10) y un post de prueba, **cuando se active FB/IG**.
- Si hay más de una instancia de API: rate limit y `last_used_at` a la base.
