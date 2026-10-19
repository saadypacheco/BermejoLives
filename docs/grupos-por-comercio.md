# Comunidades y grupos por comercio: spec implementable (v2, 19/10/2026)

> **Estado:** spec para implementar. **Reemplaza la v1** (commit `88f9905`), que diseñaba un stock de grupos en blanco con links: el dueño cambió el diseño el 19/10. De la v1 sigue valiendo (y se trae acá): fotos 1-a-1 que no se pierden, el bug del número propio con código, alertas de posible cobro, revisión de altas, API de sólo lectura para el asistente, credencial del agente, textos sin el código, permisos y reglas de migración. Se eliminó todo lo del stock, las reservas y los links por grupo. Base: `main` en `88f9905` (el código no cambió desde `cc0989d`: las referencias `archivo:línea` valen). Lo que depende de WAHA o de WhatsApp está marcado **a verificar**. Donde dice «como la v1 §X», el detalle está en `git show 88f9905:docs/grupos-por-comercio.md`.
>
> **Para quién:** backend-dev y frontend-dev trabajan en paralelo dentro de cada entrega (§10) sin tocar los mismos archivos. qa-engineer verifica con los criterios de cada entrega. El dueño corre el **E0** antes de todo (§10.0).

## 0. En una pantalla

**Comercios.** Al terminar el alta, el agente le muestra al comerciante **el QR fijo de la comunidad de comercios de su ciudad** (el mismo que lleva impreso en su credencial y que va en el volante) y se va: el alta no espera nada. El comerciante entra cuando quiere. El **Registrador** (WAHA, admin de la comunidad, nunca escribe) ve la entrada; el sistema cruza ese número con el WhatsApp cargado en el alta y, si coincide, **ata número y comercio** y le deja al **Anfitrión** una tarea: crear a mano, desde el Samsung, el grupo del comercio, con nombre y descripción listos para copiar (**nunca el código**). Cuando el Registrador aparece en ese grupo con el comerciante adentro, el sistema lo **ata solo**. Si el número no coincide, va a la bandeja «Es de…».

**Compradores.** Un QR impreso a `uruku.bo/comunidad/bermejo` que **redirige** a la comunidad de compradores que tenga lugar (Compradores Bermejo 1, 2, …). El admin carga los links y ve los conteos (nunca públicos). El Registrador es admin de cada una y captura el número de quien entra (entrar = acepta avisos). Avisar = publicar a mano en el grupo de avisos de cada comunidad.

**Lo que decide todo es el E0 (~20 min, §10.0):** si WAHA 2026.8.2 NOWEB sólo ve un LID (identificador sin teléfono) de quien entra, el cruce automático no anda y entra el plan B (§4.5).

```mermaid
sequenceDiagram
  participant Ag as Agente
  participant C as Comerciante
  participant K as Comunidad de comercios (Bermejo)
  participant R as Registrador (WAHA, admin, sólo lee)
  participant B as Backend
  participant A as Anfitrión (Samsung)
  participant G as Grupo del comercio
  Ag->>B: alta + WhatsApp del local
  Ag->>C: le muestra el QR fijo de la comunidad y se va
  C->>K: escanea (cuando quiere) → uruku.bo/comunidad/bermejo/comercios → 302 → «Unirme»
  K-->>R: group.v2.participants (join)
  R->>B: webhook → ¿el número es el del alta?
  B-->>A: tarea «Crear el grupo de Ferretería Sol» (nombre y descripción para copiar)
  A->>G: crea el grupo: comerciante + Registrador
  G-->>R: group.v2.join (asunto, participantes)
  R->>B: asunto = el de la tarea y comerciante adentro → ata el grupo
  C->>G: foto + precio
  R->>B: publicación (confiable → aprobada; si no → cola)
```

## 1. Contexto

### 1.1 Lo que ya existe y se reusa

| Pieza | Dónde | Uso acá |
|---|---|---|
| Grupo atado → identifica todo lo que entra | `ingest.py:69-108`, `comercio_wa_grupos` (`0065`) | El grupo nuevo se ata por evento, no por código |
| Número propio en un grupo no publica | `ingest.py:513-529` | Igual; en E6 además tilda los avisos publicados |
| Remitente ajeno en un grupo → cola; confiable → aprobada, si no → cola | `ingest.py:635-646, 681-684` | Sin cambios |
| `@lid` → teléfono por `participantAlt` / `remoteJidAlt` | `models/whatsapp.py:7-29, 54-64` | Además se guarda el par LID↔número |
| El WhatsApp del alta ya identifica | `repository.py:409-421` (`comercio_numeros` y `comercios.whatsapp`) | El cruce de la comunidad usa lo mismo |
| El WhatsApp se carga **después** del alta | `publicar/page.tsx:1040-1048` (`CapturaWhatsapp`) | El QR de la comunidad va justo después |
| Leer participantes por WAHA | `wa_grupos.py:145-181` | Diagnóstico (E0) |
| Crear grupos / agregar por WAHA | `wa_grupos.py:51-142` | **No se usa** (`wa_solo_lectura`, `config.py:187`) |
| Comunidad de compradores: un link en `redes_sociales` (`0118`) y `/comunidad` informativa | `app/comunidad/page.tsx`, `components/unirme-comunidad.tsx` | `/comunidad` sigue; el botón pasa al redirector; el link viejo queda de respaldo |
| Canal de WhatsApp (`120363412598489616@newsletter`, del Registrador) | `numeros-whatsapp-uruku.md:79-86, 672-689` | «Sólo leer» y respaldo cuando todo está lleno |
| Cuenta del comprador con `CONFIRMAR` entrante | `api/usuario.py:41-115` | Número verificado + tilde explícito; se cruza con los miembros |
| `interes_plan` (agente) y `pagos` | `campo.py:665-689`, `comercio.py:1126-1158` | Alertas de cobro |
| Agentes = `usuarios_panel` rol `agente`; JWT 7 días + permisos | `0126`, `core/auth.py:36-62`, `core/permisos.py:21-43` | Credencial y asistente |

### 1.2 Lo que está roto o falta

| # | Problema | Evidencia |
|---|---|---|
| P1 | **Bug:** un número propio que escribe 1-a-1 con `URUKU-XXXX` queda autorizado para ese comercio | La guarda de propios sólo mira grupos (`ingest.py:513`); `_identificar_comercio` agrega el número (`ingest.py:140-157`) |
| P2 | Una foto de un número desconocido se pierde (no se copia; WAHA la borra) | Sólo se copia al publicar (`ingest.py:662-666`) |
| P3 | Un «hola» 1-a-1 de un número conocido crea una novedad pendiente | `ingest.py:596-600` |
| P4 | El volante manda a un grupo que muchas veces no existe | `volante/[slug]/page.tsx:93-98` |
| P5 | Soltar un grupo hace `DELETE` físico | `repository.py:496-499` |
| P6 | WAHA no manda eventos de grupo | `docker-compose.prod.yml:76`, `infra/docker-compose.yml:60` |
| P7 | El webhook descarta mudo todo evento que no sea mensaje o estado | `webhook.py:159` |
| P8 | El mensaje del agente invita a «responder para sumarse a un plan»: la plata se habla con el agente | `lib/ficha-whatsapp.ts:28` |
| P9 | No hay QR de cobro (se sacó el 6/10): ningún texto puede prometer «pagá por QR» | `comercio.py:1110-1113`, `limpieza-circuitos.md:73-75` |
| P10 | Un agente dado de baja usa la app hasta que vence su JWT (7 días) | `core/auth.py:171-173` |
| P11 | Los grupos «URUKU-NBDA» (Vidriería Pacheco) y «URUKU-P3FC» (Comercial Bazzi, slug `comercia-base`) muestran el código al comerciante | E0 del 19/10 |
| P12 | `/comunidad` tiene un solo link sin cupo, y dice «Tu número lo ven los del grupo» (falso para el grupo de avisos) | `app/comunidad/page.tsx:54`, `0118` |

### 1.3 WAHA: lo documentado y lo que hay que probar

- Prod: `{"version":"2026.8.2","engine":"NOWEB","tier":"CORE"}` (E0, 19/10).
- Eventos `group.v2.join` (nos agregaron: `group.subject`, `group.participants[]`), `group.v2.leave`, `group.v2.participants` (`type: join|leave|promote|demote`, `participants[]` con `id` y `role`) y `group.v2.update`: la doc los marca soportados en NOWEB. Los ejemplos traen `@c.us`; la doc no habla de comunidades (<https://waha.devlike.pro/docs/how-to/groups/>). **A verificar:** qué JID trae el evento cuando alguien entra a una comunidad (la comunidad «padre», su grupo de avisos o los dos) y si el `id` es número o LID.
- LID → número: `GET /api/{session}/lids/{lid}` → `{lid, pn}`; se puebla con «Get all groups» / «Refresh groups»; si no aparece es porque no está en contactos **o no somos admin del grupo**; en NOWEB la doc pide el *store* para chats/contactos (<https://waha.devlike.pro/docs/how-to/contacts/>). La sesión de prod no tiene store (`manual-operativo-whatsapp.md:216-219`) y activarlo exige re-vincular la tablet. **A verificar en E0.**
- Tope de una comunidad: guías no oficiales de 2026 dicen ~2.000 y otras 5.000 (<https://getkanal.com/blog/community-guide-whatsapp>). El diseño no depende del número: el cupo es un campo por comunidad (por defecto 1.800).

## 2. Decisiones

### 2.1 Del dueño (19/10/2026, no se discuten)

| # | Decisión |
|---|---|
| D1 | Anfitrión 75314737 (Tigo, humano, crea grupos y comunidades a mano). Registrador 64610187 (WAHA): **nunca escribe**, pero **sí puede ser admin** de comunidades y grupos. 67671888 = número público para personas. Marca 67991916 = API oficial (futuro) |
| D2 | Una **comunidad de comercios por ciudad**, con QR fijo impreso en la credencial y en el volante. El alta **termina sin esperar** |
| D3 | El Registrador es admin de la comunidad; el sistema cruza el número que entra con el del alta y los ata. Si no coincide → «Es de…» |
| D4 | El Anfitrión **crea a mano** el grupo del comercio (Anfitrión + comerciante + Registrador) con nombre y descripción que arma el sistema (nombre, encargado, ubicación, celular, ficha; **nunca el código**). El sistema lo ata solo al ver al Registrador y al comerciante adentro. De a pocos por día. Si la privacidad no deja agregarlo, invitación privada a mano |
| D5 | **Comunidades de compradores** con QR fijo → URL de URUKU que redirige a la comunidad con lugar; el admin carga links y ve conteos (nunca públicos); Registrador admin de cada una; entrar = acepta avisos; **falta la Política de privacidad**; avisar = publicar a mano en cada grupo de avisos |
| D7 | El agente **nunca cobra**; alertas de posible cobro en efectivo; toda alta se revisa; el asistente del dueño lee por API de sólo lectura. El **cobro mensual** (QR + recordatorios 1 día antes y a los 3, 6, 9, 12 y 15 días de vencido) queda **fuera**: siguiente spec |
| D8 | Credencial del agente: QR → `/agente/<token>` («Los agentes de URUKU nunca cobran»), con el QR de la comunidad de comercios en la misma credencial |

### 2.2 Técnicas

| # | Decisión | Elegida | Descartadas | Por qué | Qué la invalidaría |
|---|---|---|---|---|---|
| T1 | Cómo se entera el sistema de que el comerciante entró | Evento `group.v2.participants` (`join`) que ve el Registrador como admin | Leer participantes cada N minutos (miles de lecturas: patrón de automatización); pedirle un mensaje con código (vuelve el código y la espera); «Aprobar nuevos miembros» (trabajo manual por cada entrada) | Pasivo: WAHA no hace ninguna llamada | E0 muestra sólo LID sin traducción → §4.5 |
| T2 | Cruce número ↔ comercio | Un **único** comercio activo con ese número (`comercio_numeros` o `comercios.whatsapp`) → se ata. 0 o más de uno → «Es de…» | Atar al alta más reciente del agente (adivinanza) | Entrar con un número prueba que ese número es de quien entra; el alta prueba de qué comercio es | Muchos comercios compartiendo número (cadenas) |
| T3 | Cómo se ata el grupo del comercio | **Asunto exacto de una tarea abierta** (normalizado) + participante no propio adentro; el número se compara cuando se puede. Respaldos: el número coincide con una tarea abierta (asunto mal tipeado) → ata + tarea «renombrar»; primer mensaje del comerciante (trae `participantAlt`); a mano | Código adentro del grupo (D4; además el comerciante lo ve); WAHA crea el grupo (D1) | El nombre lo genera el sistema y sólo lo tipea el Anfitrión: es una firma sin código | NOWEB no emite `group.v2.join` → queda el respaldo por primer mensaje |
| T4 | Ritmo del Anfitrión | Cada tarea «crear grupo» nace con `due_on`: el primer día con menos de `WA_HOST_GROUPS_PER_DAY` (10). La pantalla muestra «Hoy» y «Próximos días» | Sin tope; tope duro que bloquea | Reparte solo, sin impedir adelantar una a mano | El dueño mide otro ritmo seguro |
| T5 | Redirector | Ruta de Next (`/comunidad/[ciudad]` para compradores y `/comunidad/[ciudad]/comercios` para comercios: el QR de la credencial y del volante también pasa por acá) → backend `resolve` → **302 `no-store`** a la comunidad abierta de menor número con `members_count < capacity` | QR directo al link de WhatsApp (se llena o se restablece el link → reimprimir todo); página intermedia con botón (un toque más) | Un QR impreso para siempre: llenarse o restablecer el link no obliga a reimprimir | Algún navegador no abre WhatsApp desde un 302 → página intermedia (QA de E2) |
| T7 | Conteo de miembros | Por eventos (+1 / −1, idempotente por miembro) + **corrección manual** del admin con lo que ve en el teléfono | Leer la lista cada N minutos (2.000 miembros por consulta); sólo manual | Barato y pasivo; el cupo por defecto (1.800) deja margen para el desvío | Eventos perdidos seguido → una lectura diaria única |
| T8 | Dónde viven los miembros | Tabla `wa_community_members` (comercios y compradores, como `wa_communities.audience`), **no** `usuarios` | Crear `usuarios` por cada entrada | `usuarios` es una cuenta con clave; mezclar crea cuentas sin clave. Se cruzan por teléfono | — |
| T10 | LID sin número | Mapa local `wa_lid_map` aprendido **gratis** de cada mensaje que trae los dos (`participantAlt`); consulta a WAHA `GET /lids/{lid}` sólo si E0 dice que sirve (`WA_LID_LOOKUP`, máx. 30/h) | Activar el *store* de NOWEB (re-vincular la tablet) | Sin costo ni riesgo; la consulta es lectura | — |
| T11 | Avisos | Los publica el Anfitrión a mano; el sistema arma el texto y **tilda solo** al ver el mensaje de un número propio en el grupo de avisos | WAHA publica (D1) | WAHA no escribe | — |
| T12 | Heredadas de la v1 sin cambios | Fotos de desconocidos en **disco privado** 30 días + «Es de…» (v1 T9); texto 1-a-1 sin foto no publica (T10); alertas en tabla + generador horario idempotente (T11); revisión de altas por trigger (T12); asistente = usuario rol `assistant` con `field_control.read` (T13); token de credencial aleatorio de 128 bits en claro (T14); página pública por el backend (T15); `require_agente` mira `activo` con caché de 60 s (T16) | Ver v1 | Ver v1 | Ver v1 |

### 2.3 Compradores: comunidades contra las alternativas

| Opción | ¿Da el número? | Límite | Cómo se avisa | Esfuerzo | Riesgo |
|---|---|---|---|---|---|
| **Comunidades + redirector** (D5) | Sí, **si E0 lo confirma** | ~2.000 c/u (no oficial) → se pasa a la siguiente | Pegar el aviso a mano en cada grupo de avisos | E2 + crear comunidades a mano | LID; un reporte masivo pega en el Anfitrión (creador) |
| Canal de WhatsApp (ya existe) | **No** (seguidores anónimos) | Sin límite práctico | Una sola publicación | Cero | Vive en el Registrador |
| Cuenta con `CONFIRMAR` (ya existe) | **Sí**, verificado + tilde explícito | Sin límite | Hoy ninguno (WAHA no escribe) | Cero | Más pasos para el comprador |
| Notificaciones web (PWA) | No | Sin límite | Push gratis, segmentable | M: `sw.js` no tiene manejador `push`, faltan claves VAPID y tabla de suscripciones | iPhone: sólo con la app instalada en inicio (iOS 16.4+) |

**Recomendación:** comunidades como canal principal (captan y avisan, decisión del dueño); el **canal** queda como «sólo quiero leer» y como destino cuando todas las comunidades están llenas; la **cuenta con `CONFIRMAR`** sigue siendo la captura con consentimiento explícito (es el plan B si E0 falla, Q2); las **notificaciones web** son la spec siguiente si los avisos por comunidad no alcanzan. Nada de esto le hace escribir a WAHA.

### 2.4 ¿Hace falta una app nativa? (D6)

- **Qué da:** ícono en la tienda, notificaciones nativas gratis (APNs/FCM), acceso a funciones del teléfono que la web no tiene.
- **Qué no da:** **el número**. Ni iOS ni Android le entregan a una app el número del teléfono; hace falta un login igual (SMS con costo por mensaje, o el `CONFIRMAR` por WhatsApp que ya existe).
- **Costos:** Apple Developer USD 99/año y Google Play USD 25 una vez (**verificar**), más dos plataformas para mantener (o un envoltorio tipo Capacitor), revisiones de tienda, y Apple puede rechazar una app que sólo envuelve un sitio (guía 4.2, **verificar**).
- **Lo que ya hay:** PWA instalable (`app/manifest.ts`, `public/sw.js`) + cuenta por WhatsApp (`api/usuario.py`). Push web: en Android sin instalar; en iPhone sólo instalada en la pantalla de inicio (iOS 16.4+).

**Recomendación: no hacer app nativa ahora.** Si se quiere estar en Google Play, empaquetar la PWA como TWA (cuesta los USD 25, sin código nativo; **verificar**). Se revisa si las métricas muestran que el push es el canal clave y los iPhone sin instalar son la mayoría, o si aparece una función que la web no puede dar.

### 2.5 Path dependence

Esta spec **vuelve a apoyarse en WAHA y en grupos/comunidades de WhatsApp**, el camino habitual del equipo (`2026-06-04-stack-bermejo`, que ya registró que WAHA no es oficial). La forma la decidió el dueño (D2-D5). Contraste:

1. **API oficial (Marca 67991916):** sin riesgo de baneo, pero la Groups API exige cuenta oficial y admite 8 participantes; no lee grupos existentes ni comunidades (`investigacion-costos-automatizacion.md:155`). No reemplaza esto.
2. **Web/PWA + cuenta por WhatsApp:** sin WhatsApp no oficial y sin límite, pero no tiene dónde publicar avisos hoy y el comerciante no la usa para mandar fotos.

**Consecuencia aceptada:** todo lo de comunidades y grupos vive en `app/services/wa_communities.py`, `wa_host_tasks.py` y `wa_events.py` y en las tablas `wa_*`. Las reglas de publicación siguen después de `mensajeria.normalizar_entrante` (`webhook.py:122-124`): el día del cambio a la API oficial se tira esto, no la ingesta.

## 3. Números y piezas de WhatsApp

| Número | Aparato | Qué hace acá |
|---|---|---|
| 75314737 Anfitrión | Samsung | Crea comunidades y grupos, es su dueño, agrega comerciantes, publica avisos. Usa `uruku.bo/admin?s=host-tasks` en el mismo Samsung para copiar textos |
| 64610187 Registrador | Tablet (WAHA) | **Admin** de cada comunidad; **admin** (recomendado) de cada grupo. Nunca escribe |
| 67671888 | — | Personas. No entra a grupos ni comunidades nuevos. Figura como «Dudas» |

| Pieza | Nombre | Ajustes (los dice la pantalla) |
|---|---|---|
| Comunidad de comercios | `URUKU Comercios · Bermejo` | Descripción §8; Registrador admin; sólo admins agregan grupos |
| Comunidad de compradores | `URUKU Compradores · Bermejo 1` (2, 3…) | Descripción con el consentimiento §8; Registrador admin |
| Grupo del comercio | El que arma la tarea (§8) | Anfitrión + comerciante + Registrador. *Editar info* y *Agregar participantes*: sólo admins. **Fuera** de la comunidad (en los grupos de una comunidad los miembros se ven entre sí) |

## 4. Flujos

### 4.1 Alta → comunidad de comercios → número atado (E2)

1. El agente termina el alta y carga el WhatsApp (como hoy). La pantalla muestra el QR fijo de la comunidad de su ciudad (se dibuja en el teléfono: anda sin señal). El agente se va.
2. El comerciante escanea cuando quiere → redirector → WhatsApp «Unirme».
3. `group.v2.participants join` en un JID de la comunidad → `wa_community_member_event` (idempotente) → se resuelve el número (§6.4).
4. Cruce (T2): un comercio → `match_status='matched'`, se autoriza el número (`comercio_numeros`, `created_by='wa-community:<id>'`) y, desde E3, nace la tarea «crear grupo» si el comercio no tiene grupo activo. Cero o varios → «Es de…», con el **candidato probable** (altas de esa ciudad en las 3 h previas sin entrada registrada) para confirmar con un toque. Si el WhatsApp se carga después de la entrada, un loop (10 min) vuelve a cruzar los miembros sin dueño.

### 4.2 Tarea del Anfitrión → grupo atado solo (E3)

Cuando el Registrador aparece en un grupo (`group.v2.join`):

| Paso | Condición | Resultado |
|---|---|---|
| 1 | El JID ya está atado o es de una comunidad | Guarda el asunto; si hay tarea «renombrar» y el asunto coincide → hecha |
| 2 | El asunto normalizado = `expected_subject_norm` de una tarea abierta y hay un participante no propio cuyo número es del comercio | **Ata** (`origen='host_task'`), tarea hecha (`done_via='event'`) |
| 3 | Igual que 2 pero el participante es un LID sin traducir | Ata con `verified=false`; el primer mensaje (`participantAlt`) lo confirma; si no coincide → tarea `phone_mismatch` |
| 4 | Asunto coincide y sólo hay números propios (no lo pudo agregar) | Tarea → `waiting_merchant` con el JID; se ata cuando llega su `participants join` |
| 5 | Asunto distinto pero un participante es el número de un comercio con tarea abierta | Ata + tarea `rename_group` |
| 6 | Nada coincide | Tarea `unbound_group`: «El Registrador entró a "X": ¿de qué comercio es?» |

**Sin eventos** (respaldo): un mensaje en un grupo sin atar, de un número que es de un comercio con tarea abierta, ata el grupo (`done_via='message'`) y sigue la ingesta normal (publica según `confiable`).

Si el comerciante no entra a la comunidad en `WA_HOST_NUDGE_AFTER_HOURS` (72 h): tarea `nudge_community` con el mensaje para mandarle el link desde el Samsung y el botón **«Crear el grupo igual»** (usa el WhatsApp del alta).

### 4.3 Comprador → redirector → comunidad con lugar (E2)

QR impreso `uruku.bo/comunidad/bermejo` → `route.ts` de Next → backend `resolve` → **302** a la comunidad abierta de menor número con lugar; si no hay ninguna cargada, al link viejo de `redes_sociales`; si no hay nada, a `/comunidad?ciudad=bermejo&lleno=1` (canal + cuenta).

- Una comunidad con `members_count ≥ capacity` se muestra «Llena» y no recibe.
- Cuando todas las abiertas de una ciudad pasan el 90 %, tarea `community_almost_full`: «Creá Compradores Bermejo 3 y cargá su link».
- Cada entrada a una comunidad de compradores crea su fila en `wa_community_members` (consentimiento = la entrada) y se cruza con `usuarios` por teléfono. **Sin Política de privacidad publicada no hay exportación** de esos números ni otro uso que la comunidad (Q1).

### 4.4 Avisar a todos (E6)

El admin escribe el aviso una vez (audiencia + ciudad) → la pantalla lista las comunidades destino → el Anfitrión lo pega en el grupo de avisos de cada una → cada una se tilda sola cuando el Registrador ve el mensaje del número propio en ese grupo (o a mano).

### 4.5 Plan B si sólo llega un LID

| Nivel | Cuándo | Qué hace el sistema |
|---|---|---|
| B0 | El participante llega como `591…@c.us` o trae el número al lado | Todo automático |
| B1 | Llega LID y `GET /api/default/lids/{lid}` devuelve `pn` | `WA_LID_LOOKUP=true`; se guarda en `wa_lid_map` |
| B2 | LID sin traducción, comunidad de comercios | «Es de…» con el candidato probable por ventana de tiempo (un toque); a las 72 h, «Crear el grupo igual» con el número del alta: el Anfitrión lo agrega por número y el **primer mensaje en su grupo** trae `participantAlt` → número verificado |
| B3 | LID sin traducción, compradores | Se cuentan y se avisa igual; **no se capturan números**. La captura pasa a la cuenta con `CONFIRMAR` (botón «Avisame por WhatsApp» en `/comunidad`). Decide el dueño: Q2 |

Un mismo miembro puede llegar primero como LID y después con número: se completa `phone` en su fila y, si ya había otra con ese número, queda una sola y se corrige el conteo.

## 5. Modelo de datos (SQL borrador)

Reglas para todas (AGENTS.md §5 y §7; KB `lesson-supabase-cloud-grants-explicitos-en-migration`, `pattern-supabase-rls-policy`, `pattern-soft-delete-activo-flag`):

- Desde **0159** (0156–0158 reservadas para otra rama). Archivo **idéntico byte a byte** en `supabase/migrations/` y `selfhost/postgres-init/`, con test por migración (como `test_admin_resumen_qa.py:398-409`). `begin; … commit;`, idempotente, `do $chk$` y `notify pgrst, 'reload schema';`.
- Tablas nuevas: RLS activo, `revoke all … from public, anon, authenticated`, `grant all … to service_role`. **Ninguna** es legible por anon. Funciones: `set search_path = public, pg_temp`, `revoke execute` de anon y authenticated, `grant execute` a `service_role`.
- Columna nueva en `comercios` → privada (regla 11) y a `PRIVADAS_EXTRA` (`test_comercios_columnas_publicas.py:36`).
- **Ninguna migración nueva puede contener la palabra que nombra al código del comercio** (ni en comentarios): la busca `test_ninguna_vista_ni_funcion_publica_expone_codigo` (`:396-410`).
- Identificadores en inglés, comentarios en español; baja lógica con `activo`.

### 0159 · `0159_wa_inbox_media_and_group_events.sql` (E1)

```sql
begin;
alter table public.wa_inbox add column if not exists media_path      text;          -- en WA_RECEIVED_DIR (disco PRIVADO)
alter table public.wa_inbox add column if not exists media_purged_at timestamptz;   -- se borró el archivo; la fila queda
alter table public.wa_inbox add column if not exists assigned_by     text;          -- quién dijo «es de…»
alter table public.wa_inbox add column if not exists assigned_at     timestamptz;
create index if not exists idx_wa_inbox_phone_sin_comercio on public.wa_inbox (phone, created_at desc) where resultado = 'sin_comercio';
create index if not exists idx_wa_inbox_jid_sin_comercio   on public.wa_inbox (wa_jid, created_at desc) where resultado = 'sin_comercio';
create index if not exists idx_wa_inbox_media_vigente on public.wa_inbox (created_at) where media_path is not null and media_purged_at is null;

-- Eventos de grupo de WAHA, crudos (como wa_inbox para los mensajes)
create table if not exists public.wa_group_events (
  id           uuid primary key default gen_random_uuid(),
  dedupe_key   text not null unique,   -- sha256(evento|grupo|tipo|participantes ordenados|timestamp)
  event        text not null,          -- group.v2.join | group.v2.leave | group.v2.participants | group.v2.update
  group_jid    text, change_type text,  -- join | leave | promote | demote
  participants jsonb, raw jsonb not null,
  result       text, reason text,       -- captured | community_member | merchant_matched | group_bound | task_waiting | unbound | ignored | error
  created_at   timestamptz not null default now()
);
create index if not exists idx_wa_group_events_group on public.wa_group_events (group_jid, created_at desc);

-- LID ↔ número, aprendido de los mensajes (participantAlt / remoteJidAlt) o de WAHA
create table if not exists public.wa_lid_map (
  lid           text primary key check (lid like '%@lid'),
  phone         text not null,                     -- E.164 sin '+'
  source        text not null check (source in ('message','event','waha_api','admin')),
  first_seen_at timestamptz not null default now(), last_seen_at timestamptz not null default now(),
  activo        boolean not null default true
);
create index if not exists idx_wa_lid_map_phone on public.wa_lid_map (phone) where activo;

alter table public.wa_group_events enable row level security; alter table public.wa_lid_map enable row level security;
revoke all on public.wa_group_events, public.wa_lid_map from public, anon, authenticated;
grant all on public.wa_group_events, public.wa_lid_map to service_role;
-- do $chk$: wa_inbox, wa_group_events y wa_lid_map no legibles por anon/authenticated
commit;
notify pgrst, 'reload schema';
```

### 0160 · `0160_wa_communities.sql` (E2)

```sql
begin;
create table if not exists public.wa_communities (
  id               uuid primary key default gen_random_uuid(),
  audience         text not null check (audience in ('merchants','buyers')),
  ciudad_id        uuid not null references public.ciudades(id),
  sequence         integer not null default 1 check (sequence >= 1),   -- Compradores Bermejo 1, 2…
  name             text not null,                                       -- como figura en WhatsApp
  invite_url       text check (invite_url ~ '^https://chat\.whatsapp\.com/[A-Za-z0-9]{20,24}$'),  -- PRIVADO
  invite_set_at    timestamptz, invite_set_by text,
  community_jid    text unique check (community_jid like '%@g.us'),     -- la comunidad
  announce_jid     text unique check (announce_jid  like '%@g.us'),     -- su grupo de avisos
  capacity         integer not null default 1800 check (capacity between 1 and 5000),
  members_count    integer not null default 0 check (members_count >= 0),   -- por eventos
  members_fixed_at timestamptz, members_fixed_by text,                  -- última corrección manual
  status           text not null default 'preparing' check (status in ('preparing','open','closed')),
  registrar_admin  boolean not null default false,
  redirect_count   integer not null default 0, last_redirect_at timestamptz,
  notes            text,
  activo           boolean not null default true,
  created_by       text not null,
  created_at       timestamptz not null default now(), updated_at timestamptz not null default now(),
  unique (audience, ciudad_id, sequence),
  constraint wa_communities_open_needs_link check (status <> 'open' or invite_url is not null)
);
create index if not exists idx_wa_communities_door on public.wa_communities (audience, ciudad_id, sequence) where activo and status = 'open';
-- trigger updated_at con set_updated_at() de la 0001

create table if not exists public.wa_community_members (
  id             uuid primary key default gen_random_uuid(),
  community_id   uuid not null references public.wa_communities(id),
  wa_id          text not null,            -- id del participante: número@c.us si se sabe, si no el LID
  phone          text, lid text,           -- phone en E.164 sin '+'
  comercio_id    uuid references public.comercios(id),   -- comunidad de comercios
  usuario_id     uuid references public.usuarios(id),    -- comprador con cuenta, si coincide
  match_status   text not null default 'pending'
                   check (match_status in ('pending','matched','unknown','ambiguous','not_applicable')),
  matched_by     text, matched_at timestamptz,           -- 'system' o email
  joined_at      timestamptz not null default now(), left_at timestamptz,
  consent_at     timestamptz not null default now(),     -- entrar = acepta avisos (D5)
  consent_source text not null default 'community_join',
  activo         boolean not null default true,          -- false = salió
  unique (community_id, wa_id),
  check (phone is not null or lid is not null)
);
create index if not exists idx_wa_cm_phone    on public.wa_community_members (phone) where phone is not null;
create index if not exists idx_wa_cm_comercio on public.wa_community_members (comercio_id) where comercio_id is not null;
create index if not exists idx_wa_cm_pending  on public.wa_community_members (match_status) where match_status in ('pending','unknown','ambiguous');

-- Elegir comunidad para el redirector y contar la redirección (una ida a la base)
create or replace function public.wa_community_resolve(p_audience text, p_ciudad_slug text)
returns table (community_id uuid, invite_url text)
language plpgsql set search_path = public, pg_temp as $fn$
-- la de menor sequence con activo, status 'open', esa audiencia y ciudad, y members_count < capacity;
-- si hay: redirect_count + 1, last_redirect_at = now(), y se devuelve
$fn$;

-- Entrada o salida de un miembro; mantiene members_count (idempotente)
create or replace function public.wa_community_member_event(
  p_community_id uuid, p_wa_id text, p_phone text, p_lid text, p_kind text)   -- p_kind: join | leave
returns jsonb language plpgsql set search_path = public, pg_temp as $fn$
-- join:  insert … on conflict (community_id, wa_id) do update (reactiva si activo = false; completa phone)
--        insertó o reactivó → members_count + 1 → 'joined' | 'rejoined'; si no → 'already'
--        si p_phone viene y otra fila ACTIVA de esa comunidad ya lo tiene (era LID) → queda una sola,
--        sin contar dos veces → 'merged'
-- leave: activo = false, left_at = now() → members_count - 1 (mín. 0) → 'left'; sin fila → 'unknown'
-- → {result, member_id, members_count, capacity}
$fn$;
-- revoke/grant de las dos funciones; RLS + revoke/grant de las dos tablas; do $chk$
commit;
notify pgrst, 'reload schema';
```

### 0161 · `0161_wa_host_tasks.sql` (E3)

```sql
begin;
-- comercio_wa_grupos pasa a baja lógica (hoy DELETE físico, repository.py:496-499)
alter table public.comercio_wa_grupos
  add column if not exists activo      boolean not null default true,
  add column if not exists released_at timestamptz,
  add column if not exists released_by text,
  add column if not exists subject     text,                           -- asunto actual (por evento)
  add column if not exists verified    boolean not null default true;  -- false = atado con LID sin confirmar
create index if not exists idx_wa_grupos_comercio_activo on public.comercio_wa_grupos (comercio_id) where activo;
-- 'origen' suma 'host_task' (no tiene check: 0065)

-- Quién atiende el comercio (para la descripción del grupo). PRIVADA (regla 11).
alter table public.comercios add column if not exists contact_name text;
comment on column public.comercios.contact_name is
  'Persona que atiende o dueño, como lo dijo en la visita. PRIVADA: va a la descripción del grupo, nunca al sitio.';

create table if not exists public.wa_host_tasks (
  id                    uuid primary key default gen_random_uuid(),
  kind                  text not null check (kind in ('create_group','rename_group','nudge_community',
                          'add_registrar','merchant_left','phone_mismatch','unbound_group','community_almost_full')),
  status                text not null default 'open' check (status in ('open','waiting_merchant','done','dismissed')),
  comercio_id           uuid references public.comercios(id),
  group_jid             text, community_id uuid references public.wa_communities(id),
  expected_subject      text,          -- nombre a copiar
  expected_subject_norm text,          -- minúsculas, sin tildes ni signos, espacios simples
  merchant_phone        text,          -- a quién agregar
  payload               jsonb not null default '{}'::jsonb,   -- textos y datos para la pantalla
  due_on                date not null default current_date,
  done_at               timestamptz, done_by text,
  done_via              text check (done_via in ('event','message','manual')),
  dismissed_reason      text,
  activo                boolean not null default true,
  created_by            text not null default 'system',
  created_at            timestamptz not null default now(), updated_at timestamptz not null default now()
);
create unique index if not exists wa_host_tasks_one_open_per_comercio on public.wa_host_tasks (kind, comercio_id) where activo and status in ('open','waiting_merchant') and comercio_id is not null;
create unique index if not exists wa_host_tasks_one_open_per_group    on public.wa_host_tasks (kind, group_jid)   where activo and status in ('open','waiting_merchant') and group_jid is not null;
create index if not exists idx_wa_host_tasks_subject on public.wa_host_tasks (expected_subject_norm) where activo and status in ('open','waiting_merchant');
create index if not exists idx_wa_host_tasks_due     on public.wa_host_tasks (due_on) where activo and status = 'open';
-- RLS + revoke/grant; do $chk$: anon no lee comercios.contact_name ni wa_host_tasks
commit;
notify pgrst, 'reload schema';
```

El generador (`nudge_community`, `community_almost_full`) corre en Python (`_host_tasks_loop`, cada hora). Es idempotente por los índices únicos parciales: PostgREST no hace `on_conflict` sobre índices parciales, así que se inserta y un `23505` se ignora.

### 0162 · `0162_field_control.sql` (E4) — igual que la v1, con dos cambios

Tablas `control_alerts` (`kind in ('unpaid_interest','cash_payment','charge_reported','revoked_credential_scanned')`, `unique(kind, source_ref)`, `status open|resolved|dismissed`, `activo`) y `signup_reviews` (`comercio_id` PK, `status pending|ok|flagged|charge_reported`, `checklist jsonb`, `activo`); trigger `after insert on comercios` que crea la revisión si `fuente = 'campo'`; backfill de las altas de campo de los **últimos 30 días**; función `control_generate_alerts(p_days)` (interés sin pago de más de `p_days` y menos de 90 días, auto-resuelve al llegar un pago no efectivo; pagos en efectivo de comercios de campo); rol `assistant` con permisos `array['field_control.read']`, `del_sistema = false`. RLS, revoke y grant como arriba. **Cambios contra la v1:** el `checklist` suma `community_joined` y `group_ready`; los textos de las alertas no prometen «pagá por QR» (P9).

### 0163 · `0163_agent_credentials.sql` (E5) — igual que la v1

`usuarios_panel.photo_url`; tabla `agent_credentials` (`usuario_id`, `token` único `check (length(token) >= 22)`, `activo` = vigente, `issued_by/at`, `revoked_by/at`, `revoke_reason`, `last_scan_at`, `scan_count`) con índice único parcial «una viva por agente». RLS, revoke de anon/authenticated, grant a `service_role`.

### 0164 · `0164_wa_broadcasts.sql` (E6)

Tablas `wa_broadcasts` (`id`, `audience` merchants|buyers, `ciudad_id`, `body` `check (length(body) between 1 and 4000)`, `created_by`, `created_at`, `activo`) y `wa_broadcast_posts` (`broadcast_id`, `community_id`, `posted_at`, `posted_via` `check in ('event','manual')`, `posted_by`, `unique (broadcast_id, community_id)`). RLS, revoke y grant como arriba.

## 6. Ingesta y eventos de WAHA

### 6.1 Configuración nueva (`backend/.env`, `core/config.py`)

```
WA_RECEIVED_DIR=/data/wa_received         # volumen propio, NUNCA bajo /data/fotos
WA_RECEIVED_RETENTION_DAYS=30
WA_EVENTS_ACT=false                       # E1 sólo guarda; E2 lo enciende
WA_LID_LOOKUP=false                       # plan B1: lo decide el E0
WA_LID_LOOKUP_MAX_PER_HOUR=30
WA_COMMUNITY_CAPACITY_DEFAULT=1800
WA_COMMUNITY_ALMOST_FULL=0.9
WA_HOST_GROUPS_PER_DAY=10
WA_HOST_NUDGE_AFTER_HOURS=72
CONTROL_UNPAID_INTEREST_DAYS=3
CONTROL_LOOP_SECONDS=3600
PRIVACY_POLICY_URL=                       # vacío = no hay política: no se exportan compradores (Q1)
```

`docker-compose.prod.yml` e `infra/docker-compose.yml` (servicio `waha`): `WHATSAPP_HOOK_EVENTS=message,message.any,session.status,group.v2.join,group.v2.leave,group.v2.participants,group.v2.update`. Servicio `backend`: volumen `wa_received:/data/wa_received`.

### 6.2 Cambios en `ingest.handle_message` (pseudocódigo)

```
… sin cambios hasta la bandeja (evento, fromMe, CONFIRMAR, clave filtrada, insert wa_inbox)
wa_identity.learn_from_message(payload)            # NUEVO E1: si trae LID y número → wa_lid_map
explorador (como hoy, ingest.py:510-511)
if es_grupo and es_numero_propio(phone):          # ingest.py:513
    if grupo es announce_jid de una comunidad:     # E6: tilda el aviso; E2: nunca ata
        wa_broadcasts.mark_posted_by_event(grupo); marcar ignorada «aviso en la comunidad»; return
    … como hoy (_atar_grupo_por_codigo_propio / «mensaje de un número de URUKU»)
if not es_grupo and es_numero_propio(phone):       # NUEVO E1 · arregla P1
    marcar ignorada «1-a-1 de un número de URUKU: no identifica ni publica»; return
if es_grupo:
    if grupo es de una comunidad:                  # NUEVO E2: una comunidad nunca se ata ni publica
        marcar ignorada «mensaje en una comunidad»; return
    comercio = _identificar_por_grupo(...)         # ingest.py:69-108 (sólo filas activo, E3)
    if comercio is None:
        comercio = wa_host_tasks.bind_by_first_message(grupo, phone)   # NUEVO E3, §4.2 respaldo
    if comercio is None:
        if has_media: media_path = wa_received.save(payload)           # NUEVO E1 (P2)
        marcar sin_comercio + media_path; return
    wa_host_tasks.verify_by_message(grupo, phone)  # E3: confirma un atado con LID (§4.2 paso 3)
else:
    comercio = _identificar_comercio(...)
    if comercio is None:
        if has_media: media_path = wa_received.save(payload)           # NUEVO E1 (P2)
        marcar sin_comercio + media_path; return
    if no hay media, ni precio, ni TikTok, ni ubicación:               # NUEVO E1 (P3)
        marcar ignorada «charla 1-a-1: el Registrador no contesta»; return
… resto igual (ubicación, plan, sólo código, cuota, confiable, foto, fusión, insert)
```

`wa_received.save` baja la media (`wa_media.descargar_media`, `wa_media.py:64`), la procesa (`imagenes.procesar_imagen`, `imagenes.py:68`) y la guarda en `WA_RECEIVED_DIR/{yyyy-mm}/{wa_message_id}.jpg`; nunca lanza. El reproceso («Es de…») reconstruye el evento desde `wa_inbox.raw` y copia la foto del disco privado. Loop diario de retención: borra archivos de más de 30 días y pone `media_purged_at`. Script único `app/scripts/clean_own_numbers.py` (`--dry-run` por defecto) para los `comercio_numeros` creados por el bug P1. Todo igual que la v1 §6.2.

### 6.3 Eventos: `webhook.py` → `wa_events.handle`

`webhook.py:132-159`: los cuatro `group.v2.*` van a `wa_events.handle(event, repo)` con `_con_reintento`; cualquier otro evento loguea `webhook.evento_ignorado` (P7). Cada evento se guarda crudo en `wa_group_events` (idempotente); si ya estaba, no se procesa. Con `WA_EVENTS_ACT=false` (E1) sólo se guarda y se aprende LID.

| Evento | Caso | Acción | Entrega |
|---|---|---|---|
| todos | — | Guardar crudo; aprender LID↔número si el participante trae los dos | E1 |
| `group.v2.participants` `join` | JID de una comunidad | `wa_community_member_event(join)` → comercios: cruce (§4.1); compradores: cruzar con `usuarios` | E2 |
| | Grupo con tarea `waiting_merchant` | §4.2 paso 4 | E3 |
| | Grupo atado, número ajeno | Informativo (la regla de remitente ajeno ya manda a la cola) | E3 |
| `group.v2.participants` `leave` | Comunidad | `member_event(leave)` | E2 |
| | Grupo atado: sale el comerciante / el Registrador (o `group.v2.leave`: lo sacaron) | Tarea `merchant_left` / `add_registrar`; en una comunidad, `registrar_admin=false` | E3 / E2 |
| `group.v2.participants` `promote`/`demote` | El Registrador en una comunidad | `registrar_admin` = true/false. `demote` → log de error `wa_community.registrar_no_admin` (deja de ver entradas) | E2 |
| `group.v2.join` (agregaron al Registrador) | JID de comunidad | `registrar_admin` según su rol | E2 |
| | JID nuevo | Reglas de atado §4.2 | E3 |
| `group.v2.update` | Grupo atado | Guarda `subject`; si hay `rename_group` y coincide → hecha | E3 |

Formas según la doc (**a verificar**: para eso se guarda `raw`):

```json
{"event": "group.v2.join", "session": "default", "payload": {
  "group": {"id": "120363yyyy@g.us", "subject": "URUKU · Ferretería Sol · Barrientos",
            "participants": [{"id": "59175314737@c.us", "role": "superadmin"},
                             {"id": "160138577080406@lid", "role": "participant"},
                             {"id": "59164610187@c.us", "role": "participant"}]},
  "timestamp": 1760881200, "_data": {}}}
```

### 6.4 Resolver un participante (`wa_identity.resolve`)

1. `…@c.us` / `…@s.whatsapp.net` → número. Si el objeto trae además un campo con el número (lo que muestre el E0: p. ej. `phoneNumber`/`pn`), se usa.
2. `…@lid` → `wa_lid_map` → si `WA_LID_LOOKUP`: `GET /api/default/lids/{lid}` (tope por hora; guarda con `source='waha_api'`) → si no, `None`.
3. «Propio» = número en `WA_NUMEROS_PROPIOS` **o** LID mapeado a uno de ellos (el Samsung ya llegó como LID el 11/9, `models/whatsapp.py:11-16`).

### 6.5 Autorizar el número del comerciante

`repo.authorize_phone_if_free(comercio_id, phone, label, by)` → `ok | already | owned_by_other` (como la v1 §6.4): inserta `comercio_numeros` (`verificado=true`, `identidad_origen='numero'`, `pattern-identidad-celular-progresiva`); si el número es de otro comercio activo **no mueve nada** (hoy el upsert lo mueve en silencio, `repository.py:573-576`) y lo manda a «Es de…»; nunca autoriza un número propio; al autorizar, reprocesa las `sin_comercio` de ese número de los últimos 30 días.

## 7. Endpoints

Errores con `HTTPException` en español; cuando el front decide, `detail = {"codigo": "<error>", "mensaje": "…"}` (es el código del **error**). Todo lo que devuelve un link de invitación o un token lleva `Cache-Control: no-store`. Teléfonos de terceros **enmascarados** (`+591 7•••• 456`) salvo lo indicado.

### 7.1 Permisos (`core/permisos.py`)

Se suman al `CATALOGO`: `("field_control", "Alertas de cobro y revisión de altas", "Plata")` y `("field_control.read", "Leer alertas, revisiones y conteos sin cambiar nada (asistente)", "Sistema")`. `es_del_panel` (`permisos.py:112`) excluye `field_control.read`.

| Qué | Permiso |
|---|---|
| Recepción / «Es de…», comunidades, tareas del Anfitrión, avisos | `whatsapp` |
| Teléfono completo: compradores / comerciante de una tarea (para agregarlo) | `datos` / `whatsapp` |
| Control de campo: escribir / leer | `field_control` / `field_control` o `field_control.read` |
| Resumen de comunidades y avisos (sin teléfonos) | `whatsapp` o `field_control.read` |
| Credenciales y fotos de agentes | `equipo` |
| App del agente | `comercios.cargar` (`require_agente`) |
| Redirector y credencial pública | sin autenticación (con límite por IP) |

### 7.2 E1 · Recepción (`app/api/reception.py`, nuevo)

| Método y ruta | Cuerpo | Respuesta |
|---|---|---|
| `GET /admin/whatsapp/inbox/{wa_message_id}/media` | — | `image/jpeg` del disco privado; 404 si no hay o se purgó |
| `GET /admin/whatsapp/unknown?days=30` | — | `{"items": [Unknown]}`; `kind`: `phone` (fotos 1-a-1), `group` (grupo sin atar); E2 suma `community_join` |
| `POST /admin/whatsapp/numbers/{phone}/assign` | `{"comercio_id", "label"}` | `{"numero", "reprocessed", "published", "ignored"}`; 409 `phone_owned_by_other`; 400 si es propio |

```json
{"kind": "community_join", "key": "member:<uuid>", "phone_masked": "+591 6•••• 123", "lid": null,
 "community": {"id": "uuid", "name": "URUKU Comercios · Bermejo"}, "at": "2026-10-19T10:42:00Z",
 "candidates": [{"comercio_id": "uuid", "nombre": "Kiosco Ana", "why": "alta de Carlos 10:15, sin entrada"}]}
```

### 7.3 E2 · Comunidades (`app/api/communities.py`, nuevo)

`Community`: `{"id", "audience", "ciudad": {"id","slug","nombre"}, "sequence", "name", "has_invite", "invite_url" (sólo con whatsapp), "community_jid", "announce_jid", "capacity", "members_count", "members_fixed_at", "is_full", "status", "registrar_admin", "redirect_count", "last_redirect_at", "door_url"}`. `door_url` = `{sitio}/comunidad/{slug}` o `{sitio}/comunidad/{slug}/comercios`.

| Método y ruta | Permiso | Cuerpo | Respuesta |
|---|---|---|---|
| `GET /admin/communities?audience=&ciudad=` | whatsapp | — | `{"items": [Community], "doors": [{"audience","ciudad","door_url","target_id"\|null,"almost_full": bool}]}` |
| `POST /admin/communities` | whatsapp | `{"audience","ciudad_id","name","invite_url"?,"capacity"?}` | `Community` (`sequence` = siguiente) |
| `PATCH /admin/communities/{id}` | whatsapp | `{"name"?,"invite_url"?,"capacity"?,"status"?,"members_count"?,"note"?}` | `Community`. Corregir el conteo exige `note` |
| `GET /admin/communities/unbound-jids` | whatsapp | — | `{"items": [{"group_jid","subject","first_seen_at","events": 4}]}` (de `wa_group_events`, sin atar a nada) |
| `POST /admin/communities/{id}/bind` | whatsapp | `{"community_jid"?,"announce_jid"?}` | `Community`; 409 si el JID ya es de otra cosa |
| `GET /admin/communities/{id}/members?state=active\|unmatched` | whatsapp (enmascarado) / datos (completo, sólo compradores) | — | `{"items": [{"id","phone"\|"phone_masked","lid","joined_at","left_at","match_status","comercio","has_account"}]}` |
| `POST /admin/communities/members/{member_id}/assign` | whatsapp | `{"comercio_id"}` \| `{"not_a_merchant": true}` | Miembro; autoriza el número si se sabe (§6.5) |
| `GET /admin/communities/summary` | whatsapp o field_control.read | — | Por ciudad y audiencia: comunidades, conteos, % de cupo, entradas de 7 días. **Sin teléfonos** |
| `GET /public/communities/resolve?audience=buyers\|merchants&ciudad=bermejo&ref=` | público, 60/min/IP | — | 200 `{"url": "https://chat.whatsapp.com/…"}`; 404 `{"codigo": "no_open_community"}`. **Nunca** devuelve conteos. Sin comunidades de compradores cargadas para la ciudad, devuelve el link viejo de `redes_sociales` (`comunidad`). `ref` sólo va al log `community.redirect` |
| `GET /campo/community-qr` | agente | — | `{"url": "{sitio}/comunidad/bermejo/comercios?ref=alta", "ciudad": "Bermejo", "available": true}` |

Se suma `/public/communities/` y `/public/agents/` (E5) al limitador (`main.py:236-280`), extendido a `GET` en esos prefijos. Loop `_communities_loop` (10 min): vuelve a cruzar miembros `pending/unknown` con teléfono (§4.1 paso 4).

### 7.4 E3 · Tareas del Anfitrión (`app/api/host_tasks.py`, nuevo)

```json
{"id": "uuid", "kind": "create_group", "status": "open", "due_on": "2026-10-19",
 "comercio": {"id": "uuid", "nombre": "Ferretería Sol", "slug": "ferreteria-sol", "ciudad": "Bermejo"},
 "since": "2026-10-19T10:42:00Z", "why": "entró a la comunidad hace 2 h",
 "merchant_phone": "59171234567", "contact_vcf_url": "/admin/host-tasks/<id>/contact.vcf",
 "name_text": "URUKU · Ferretería Sol · Barrientos",
 "description_text": "Ferretería Sol en URUKU\nEncargado/a: …",
 "steps": ["Guardá el contacto", "Nuevo grupo → «Ferretería Sol (URUKU)» + «URUKU Registrador»", "…"],
 "group_jid": null, "actions": ["done", "dismiss", "today"]}
```

| Método y ruta | Cuerpo | Respuesta |
|---|---|---|
| `GET /admin/host-tasks` | — | `{"today": [HostTask], "later": [HostTask], "done_today": 3, "per_day": 10, "by_kind": {…}}` |
| `POST /admin/host-tasks/{id}/done` | `{"group_jid"?}` | `HostTask`. Con JID ata el grupo a mano (`done_via='manual'`) |
| `POST /admin/host-tasks/{id}/dismiss` | `{"reason"}` | `HostTask` |
| `POST /admin/host-tasks/{id}/today` | — | `due_on` = hoy |
| `POST /admin/host-tasks/{id}/resolve-unbound` | `{"comercio_id"}` \| `{"not_ours": true}` | Ata el grupo o lo descarta |
| `GET /admin/host-tasks/{id}/contact.vcf` | — | `text/vcard` («Ferretería Sol (URUKU)», `+591…`) |
| `POST /admin/comercio/{id}/host-task` | `{"kind": "create_group"\|"rename_group"}` | `HostTask` (crear igual; renombrar un grupo viejo) |
| `GET /admin/comercio/{id}/grupos` (existe, `moderacion.py:1264`) | — | Sólo `activo`; cada item suma `subject`, `verified`; suma `"task"` abierta |
| `DELETE /admin/comercio/{id}/grupos/{jid}` (existe, `:1314`) | — | Baja lógica (P5) |
| `GET /campo/mis-comercios/{id}/whatsapp-status` | agente | `{"community": "joined"\|"not_yet", "group": "ready"\|"in_progress"\|"none"}` |
| `POST /campo/comercio` y `PATCH /campo/mis-comercios/{id}` (existen) | agente | Suman `contact_name` |

### 7.5 E4 · Control de campo (`app/api/field_control.py`, nuevo) — como la v1 §7.5

`GET /admin/field-control/summary`, `GET …/alerts`, `POST …/alerts/{id}/resolve` (nota obligatoria), `GET …/reviews`, `POST …/reviews/{comercio_id}` (`charge_reported` crea alerta `high`), `POST …/run`. Lectura con `field_control` o `field_control.read`; escritura sólo `field_control`. El `Review.facts` suma `"community": {"joined_at"}` y `"wa_group": {"status"}`. El guion de la llamada: «Hola, te escribo de URUKU. ¿Te visitó Carlos el 17/10? ¿Te pidió algún pago? En URUKU los agentes nunca cobran.» El asistente entra con un usuario rol `assistant` por `POST /auth/login` (JWT 7 días; credenciales en variables de entorno de la PC del dueño, nunca en un repo); cualquier `POST` le da 403. Loop `_field_control_loop` cada `CONTROL_LOOP_SECONDS`.

### 7.6 E5 · Credenciales (`app/api/agent_credentials.py`, nuevo) — como la v1 §7.6

`GET/POST /admin/agents/{usuario_id}/credential`, `POST …/credential/revoke` (`cut_access` pone `usuarios_panel.activo=false`), `POST …/photo` (nombre de archivo aleatorio), `GET /public/agents/{token}` (`valid|revoked|inactive`; 404 siempre igual; nunca email, teléfono, ids ni permisos; escanear una revocada crea `revoked_credential_scanned`, una por día) y `GET /campo/my-credential`, que suma `"community_url"` (el QR de la comunidad de comercios de su ciudad). `require_agente` (`core/auth.py:171`) consulta `activo` con caché de 60 s → 401 «Tu acceso fue dado de baja».

### 7.7 E6 · Avisos (`app/api/broadcasts.py`, nuevo)

| Método y ruta | Permiso | Cuerpo | Respuesta |
|---|---|---|---|
| `POST /admin/broadcasts` | whatsapp | `{"audience","ciudad_id","body"}` | `{"id","body","posts": [{"community_id","name","posted_at": null}]}` |
| `GET /admin/broadcasts?pending=true` | whatsapp o field_control.read | — | `{"items": [Broadcast]}` |
| `POST /admin/broadcasts/{id}/posts/{community_id}` | whatsapp | — | Tilda a mano |
| (automático, §4.4) | — | — | Mensaje de un número propio en el `announce_jid` → el aviso más reciente (48 h) de esa audiencia y ciudad sin tilde ahí → `posted_via='event'` |

## 8. Textos (`app/services/wa_group_texts.py`)

Funciones puras con tests. **Ninguna** devuelve el código vigente ni el anterior: cada salida pasa por `_sin_codigo_del_comercio(texto, comercio)` y un test lo prueba con un comercio cuyo nombre lo contiene. La URL del sitio sale de `settings.sitio_url` (`config.py:110`), nunca escrita a mano (QA usa otro dominio).

| Función | Ejemplo |
|---|---|
| `group_name(comercio, lugar, ciudad)` | `URUKU · Ferretería Sol · Barrientos` (referencia: `{lugar} {puesto}` si está en un mercado; si no, `direccion` hasta la primera coma). Máx. 60 caracteres; si choca con otra tarea abierta, suma `· 2` |
| `group_description(...)` | Bloque de abajo (≤ 1.000 caracteres; líneas sin dato se omiten) |
| `nudge_message(comercio, door_url)` | «Hola, soy de URUKU. Para terminar de sumar Ferretería Sol, entrá a la comunidad de comercios: {door_url}. Después te armamos tu grupo para mandar fotos. Los agentes de URUKU nunca cobran.» |
| `merchants_community_description(ciudad)` | «Comercios de URUKU en Bermejo. Por acá te avisamos novedades para tu negocio. Las fotos y ofertas van a tu grupo (el que tiene el nombre de tu negocio), no acá. Los agentes de URUKU nunca cobran. Dudas: WhatsApp 67 671 888.» |
| `buyers_community_description(ciudad)` | «Ofertas y novedades de los comercios de Bermejo, de URUKU. Al entrar aceptás recibir estos avisos. En el grupo de avisos tu número sólo lo ven los administradores. Te vas cuando quieras. Privacidad: {PRIVACY_POLICY_URL}» (sin URL, la línea no va: Q1) |

```
Ferretería Sol en URUKU
Encargado/a: Rosa Pacheco
Dónde: Av. Barrientos 345 · Bermejo
Celular: +591 71 234 567
Ficha: https://uruku.bo/comercios/ferreteria-sol

Mandá acá las fotos de tus productos y ofertas, con el precio si lo tenés. Salen en tu ficha.
Los agentes de URUKU nunca cobran. Si alguien te pide plata en nombre de URUKU, avisanos.
Dudas: WhatsApp 67 671 888 (te atiende una persona).
```

**Textos del frontend que cambian:**

| Dónde | Hoy | Pasa a | Entrega |
|---|---|---|---|
| Volante, pie (`volante/[slug]/page.tsx:93-98`) | «Mande la foto al grupo de WhatsApp URUKU · {nombre}» | «Le armamos un grupo de WhatsApp con el nombre de su negocio: ahí manda sus fotos con el precio. Para eso, entre a la comunidad de comercios con este QR.» + QR del redirector (`?ref=volante`) + «**Nuestros agentes nunca cobran.**» | E2 |
| Volante, contacto (`:107`) | «Dudas: WhatsApp +591 67671888» | «Dudas (lo atiende una persona): WhatsApp 67 671 888 · comercios@uruku.bo» | E2 |
| Mensaje del agente (`lib/ficha-whatsapp.ts:28`) | «Si querés sumarte a un plan, respondé este mensaje…» | «Para sumarte a un plan, escribile a URUKU al 67 671 888. Los agentes no cobran.» | E2 |
| `/comunidad` (`app/comunidad/page.tsx:54`) | «Tu número lo ven los del grupo…» | «En el grupo de avisos tu número sólo lo ven los administradores de URUKU. En los grupos de charla lo ven los de ese grupo. Al entrar aceptás recibir avisos; te vas cuando quieras.» El botón va a `/comunidad/{ciudad}`. Con `?lleno=1`: «Estamos abriendo una comunidad nueva. Mientras, seguí el canal o dejanos tu número para avisarte» (canal + cuenta) | E2 |
| `lib/contacto.ts:1-7` (comentario) | «la cara con comerciantes y compradores» | «contacto humano; las fotos van al grupo de cada comercio» | E2 |
| Guía de venta (`app/guia-venta/page.tsx:145`) | «manda la foto por WhatsApp al grupo» | Igual + «el grupo se lo armamos después de que entra a la comunidad» | E3 |

## 9. Pantallas

Íconos sólo de `components/ic.tsx` (`whatsapp`, `comunidad`, `aviso`, `gente`, `listo`, `reloj`, `usuario`…); clave nueva → catálogo + `npm run iconos`. Nunca un emoji.

### 9.1 Admin › Comunidades (`/admin?s=communities`, `whatsapp`, E2; pestaña Avisos en E6)

```
Comunidades de WhatsApp   [Comunidades] [Avisos]            Ciudad [Bermejo ▾]  [+ Nueva]
COMERCIOS · QR fijo uruku.bo/comunidad/bermejo/comercios                  [QR] [Imprimir]
 1 URUKU Comercios · Bermejo  Abierta    312 / 1.800  Registrador admin ✓  410 redirec. ⋯
   Link ✓ 19/10 · Comunidad ✓ · Avisos ✓ · Sin dueño: 3 entradas [Ver en «Es de…»]
COMPRADORES · QR fijo uruku.bo/comunidad/bermejo                   [QR] [Imprimir afiche]
 1 Compradores Bermejo 1      Llena      1.800 / 1.800                                 ⋯
 2 Compradores Bermejo 2      Abierta ←  1.244 / 1.800 (recibe a los nuevos)           ⋯
 3 Compradores Bermejo 3      Preparando sin link                       [Cargar link]
⋯ = Editar · Cambiar link · Atar JIDs · Corregir conteo (con nota) · Miembros · Cerrar
Atar JIDs → «Lo que vio el Registrador sin atar»: asunto · JID · visto [Es la comunidad] [Es su grupo de avisos]
Miembros (compradores, permiso datos): número · entró · salió · tiene cuenta
Afiche (A5): logo · «Ofertas de Bermejo en tu WhatsApp» · QR · «Al entrar aceptás recibir avisos de URUKU;
             te vas cuando quieras.» · Privacidad (cuando exista)
```

El conteo **nunca** se ve fuera del admin. El afiche y la tarjeta no lo muestran.

### 9.2 Admin › Tareas del Anfitrión (`/admin?s=host-tasks`, `whatsapp`, E3)

```
Para hacer en el Samsung · Hoy 3 de 10 · Próximos días 12
Crear grupo (7)
┌ Ferretería Sol · Bermejo · entró a la comunidad hace 2 h ─────────┐
│ 1 [Guardar contacto] +591 71 234 567                              │
│ 2 Nuevo grupo → «Ferretería Sol (URUKU)» + «URUKU Registrador»    │
│ 3 Nombre  URUKU · Ferretería Sol · Barrientos           [Copiar]  │
│ 4 Descripción  Ferretería Sol en URUKU…                 [Copiar]  │
│ 5 Ajustes: sólo admins · Registrador admin                        │
│ ¿No te deja agregarlo? Usá la invitación privada de WhatsApp.     │
│ ● Esperando ver el grupo… → ✓ Atado (se cierra sola)              │
│ [Ya está: pegar ID] [Mañana] [No va]                              │
└───────────────────────────────────────────────────────────────────┘
Renombrar (2) · Mandarle el link (4) · Registrador afuera (0)
Grupo sin atar «Ferre Sol» [Es de…] · Compradores Bermejo 2 al 91 % [Ir]
```

Se usa **en el Samsung**: una columna, botones de 44 px, «Copiar» al portapapeles. «Mandarle el link» (nudge): botón `wa.me/<número>?text=…` (sale del Samsung, `pattern-wa-me-link-sin-api`) + «Crear el grupo igual».

### 9.3 Admin › ficha del comercio › WhatsApp (E3)

Reemplaza los «3 pasos manuales con el código» (`admin/page.tsx:3522-3600`): `Comunidad: entró 19/10 ✓ / todavía no` · `Grupo: URUKU · Ferretería Sol (listo) / tarea abierta / sin grupo [Crear tarea]` · `[Pedir renombre]` para grupos viejos (NBDA, P3FC) · `Grupo existente: [pegá el ID] [Atar]` (como hoy) · `Encargado/a: [contact_name]` (privado).

### 9.4 Admin › Recepción › «Es de…» (E1; E2 suma entradas a la comunidad)

```
Sin dueño (30 días)
 Fotos 1-a-1   +591 7•••• 456 · 3 fotos [▣][▣][▣] «precio 120»        [Es de…]
 Entró a la comunidad de comercios · +591 6•••• 123 · hoy 10:42
   Probable: Kiosco Ana (alta de Carlos 10:15)   [Es Kiosco Ana] [Es de…] [No es comercio]
 Grupo sin atar · 120363…@g.us · 1 foto                                 [Es de…]
 «Es de…» → buscador de comercios → [Confirmar] → «Listo: se reprocesaron 3 mensajes.»
```

### 9.5 Control de campo y credenciales (E4, E5)

- **Admin › Control de campo** (`/admin?s=field-control`), como la v1 §9.5: alertas (alta / media / baja, «Resolver» con nota) y revisión de altas (más viejas primero) con hechos: consentimiento, interés, pagos, **comunidad** y **grupo**; checklist; «Escribirle por WhatsApp» con el guion.
- **Admin › Equipo › agente:** foto, credencial (vigente desde, escaneos), `[Ver e imprimir]` `[Reemitir]` `[Revocar… ☐ cortar acceso]`. Tarjeta A7: logo · foto · nombre · ciudad · QR a `/agente/<token>` («Escaneá para comprobar que soy agente») · QR de la comunidad de comercios («Para tu negocio: entrá a la comunidad») · «**Los agentes de URUKU nunca cobran.**»
- **App del agente › Mi credencial:** lo mismo que la tarjeta, con «Yo no cobro nada». Se guarda para verse sin señal.

### 9.6 App del agente: fin del alta (E2)

Va después del WhatsApp del local (`CapturaWhatsapp`) y antes de «Completar comercio» (`publicar/page.tsx:1040-1054`).

```
✓ ¡Ferretería Sol cargado!
[Clave del comercio — se ve una vez]        (como hoy)
[WhatsApp del local]                        (como hoy)
┌ Comunidad de comercios · Bermejo ─────────────────────────┐
│  ██ QR ██  Que lo escanee con la cámara y toque «Unirme».  │
│  ████████  No hace falta esperar. Cuando entre, le armamos │
│            su grupo para mandar fotos. Los agentes de      │
│            URUKU nunca cobran.                             │
└────────────────────────────────────────────────────────────┘
Sin WhatsApp cargado: «Cargá su WhatsApp: si no, no lo reconocemos cuando entre.»
Sin comunidad en la ciudad: «Todavía no hay comunidad en Tarija. Seguí: el admin le escribe.»
[Completar comercio]                        (como hoy)
```

El QR se dibuja en el teléfono (`qrcode`, ya es dependencia) con la URL fija: anda sin señal. En «Mis comercios» (E3): `Comunidad ✓ / todavía no · Grupo listo / en preparación`.

### 9.7 Páginas públicas

- `/comunidad/[ciudad]` y `/comunidad/[ciudad]/comercios` (`route.ts`, E2): sin pantalla; 302 `no-store`. Sin comunidad → `/comunidad?ciudad=…&lleno=1` (compradores) o `/contacto` (comercios).
- `/agente/[token]` (E5), como la v1 §9.9 con otro texto: foto, nombre, ciudad, «VIGENTE», reloj vivo, «**LOS AGENTES DE URUKU NUNCA COBRAN.** Si alguien te pide plata en nombre de URUKU, no pagues y avisanos: WhatsApp 67 671 888. Fijate que arriba diga uruku.bo.» Revocada: fondo rojo, «NO ES AGENTE DE URUKU». Inexistente: «Esta credencial no es de URUKU». `noindex`, `force-dynamic`, `no-store`.

## 10. Entregas

En serie: comparten `main.py`, `repository.py`, `tests/conftest.py` (`FakeRepo`), `secciones.ts` y `admin/page.tsx`. **Dentro de cada entrega, backend y frontend van en paralelo** con los archivos de su tarea (nunca el mismo archivo). Cada método nuevo del `Repo` va al Protocol, a `SupabaseRepo` y a `FakeRepo` (`test_repo_completo.py`). El front arranca con los contratos de §7. E4 y E5 no dependen de E3: si el dueño prioriza el control de cobros, pueden ir antes (E5 sí necesita E2 por el QR de la comunidad).

### 10.0 E0 · Prueba del dueño (operación, sin código, ~20 min)

**Objetivo:** saber si el Registrador ve el **número** de quien entra a una comunidad y a un grupo. Hace falta el Samsung, la tablet encendida y **un teléfono de prueba** que no sea de URUKU ni de un comercio cargado.

1. **Samsung:** WhatsApp › Comunidades › Nueva comunidad: `URUKU PRUEBA E0`, descripción «prueba, se borra hoy».
2. **Samsung:** en la comunidad › Agregar miembros › «URUKU Registrador» (64610187); si no aparece la opción, mandale el enlace de invitación a la tablet y aceptalo ahí (la tablet no escribe nada). Después › Miembros › Registrador › **Hacer admin de la comunidad**.
3. **Samsung:** Comunidad › Invitar mediante enlace › mostrar el QR. **Teléfono de prueba:** escanear › Unirse. Anotar la hora.
4. **Samsung:** Nuevo grupo `URUKU PRUEBA E0 grupo` con el teléfono de prueba y el Registrador. **Teléfono de prueba:** escribir en ese grupo `hola prueba e0`.
5. **VPS** (lectura; WAHA no manda nada):

```bash
cd /docker/uruku
docker compose -f docker-compose.prod.yml exec -T backend python - <<'EOF'
import json, httpx
from app.core.config import settings
B = settings.waha_base_url.rstrip("/")
H = {"X-Api-Key": settings.waha_api_key}
def get(p):
    r = httpx.get(B + p, headers=H, timeout=60); print(f"GET {p} -> {r.status_code}")
    try: return r.json()
    except Exception: print(r.text[:300]); return None
print("ME:", json.dumps(get("/api/sessions/default/me"), ensure_ascii=False))
grupos = get("/api/default/groups") or []
if isinstance(grupos, dict): grupos = [dict(v, id=k) if isinstance(v, dict) else v for k, v in grupos.items()]
for g in grupos:
    if "PRUEBA E0" not in json.dumps(g, ensure_ascii=False).upper(): continue
    print("=" * 70); print(json.dumps(g, ensure_ascii=False, indent=1)[:4000])
    gid = g.get("id") if isinstance(g.get("id"), str) else (g.get("id") or {}).get("_serialized")
    parts = get(f"/api/default/groups/{gid}/participants") or []
    print(json.dumps(parts, ensure_ascii=False, indent=1)[:3000])
    for p in parts if isinstance(parts, list) else []:
        pid = p.get("id") if isinstance(p, dict) else str(p)
        if isinstance(pid, str) and pid.endswith("@lid"):
            print("LID", pid, "->", json.dumps(get(f"/api/default/lids/{pid.split('@')[0]}")))
print("LIDS:", get("/api/default/lids/count"))
EOF
docker compose -f docker-compose.prod.yml exec -T postgres psql -U postgres -d postgres -c \
 "select created_at, phone, resultado, raw->'_data'->'key'->>'participant' as participant,
         raw->'_data'->'key'->>'participantAlt' as alt
    from wa_inbox where body ilike '%prueba e0%' order by created_at desc limit 5;"
```

6. **Qué mirar y qué hacer:**

| Resultado | Nivel (§4.5) | Qué hacer |
|---|---|---|
| El teléfono de prueba sale como `591…@c.us`, o con el número al lado, en la comunidad (padre o avisos) | B0 | Seguir así. Anotar qué JID lo lista (padre, avisos o los dos) |
| Sale `…@lid` y `lids/{lid}` devuelve `pn` | B1 | `WA_LID_LOOKUP=true` en E2 |
| Sale `…@lid` y `pn` es `null` | B2/B3 | Plan B; el dueño responde Q2 |
| La comunidad no aparece en `/groups` | — | Anotar; el Registrador quizá no está adentro: repetir el paso 2 |
| `wa_inbox`: `phone` = el de prueba y `alt` con número | — | Confirma el respaldo del grupo (§4.2) |

   Pegar la salida (sin el número de prueba) en `docs/handoff-*.md`, junto con el `ME:` (el LID propio del Registrador) y los LID del Samsung si aparecen.
7. **Limpieza:** Samsung › comunidad › Desactivar comunidad; salir del grupo y eliminarlo. Las filas de `wa_inbox` quedan (`sin_comercio`). Los **eventos** (si llegan, con qué JID y qué forma) se prueban al desplegar E1, que los suscribe y guarda crudos (criterio E1-11).
8. **Grupos viejos (P11):** ver si están atados:

```sql
select g.grupo_jid, g.nombre, g.origen, g.created_at, c.nombre, c.slug from comercio_wa_grupos g
  join comercios c on c.id = g.comercio_id where c.slug in ('vidrieria-pacheco', 'comercia-base');
```

   Si no están atados, el JID sale del script del paso 5 cambiando `PRUEBA E0` por `URUKU-NBDA` / `URUKU-P3FC`, y se atan desde la ficha (como hoy). En E3, «Pedir renombre» les arma el texto. El slug `comercia-base` parece un error de tipeo: corregirlo desde el admin si se puede, revisando antes si hay volantes impresos con ese slug.

### 10.1 E1 · Ingesta segura, fotos que no se pierden y captura de eventos (M)

**Backend:** `services/ingest.py` (§6.2: P1, P2, P3, aprender LID), `services/wa_received.py` (nuevo), `services/wa_media.py` (`media_path`), `services/wa_identity.py` (nuevo: mapa LID, `resolve`, «propio»), `services/wa_events.py` (nuevo: guardar crudo, sin actuar), `api/webhook.py` (eventos + log de ignorados), `api/reception.py` (nuevo, §7.2), `main.py` (routers + retención), `core/config.py`, `db/repository.py`, `tests/conftest.py`, `scripts/clean_own_numbers.py` (nuevo), `0159` en las dos carpetas, `docker-compose.prod.yml` e `infra/docker-compose.yml` (eventos y volumen), tests `test_ingest_seguro.py`, `test_reception.py`, `test_wa_events.py`.

**Frontend:** `components/bandeja-whatsapp.tsx` («Sin dueño», miniaturas por `fetch` autenticado → `blob:`, «Es de…»), `lib/reception.ts` (nuevo), `lib/api.ts` (sólo exportar `authFetch`).

**Criterios de aceptación:**
1. 1-a-1 desde un número propio con un `URUKU-XXXX` válido → `ignorada` «1-a-1 de un número de URUKU…»; no hay `comercio_numeros` ni publicación.
2. El explorador sigue publicando por código (regresión).
3. 1-a-1 de un número conocido con «hola, ¿cuánto sale el plan?» → `ignorada` «charla 1-a-1…». Con foto, precio, TikTok o ubicación → como hoy.
4. Foto 1-a-1 de número conocido: confiable → `aprobado`; no confiable → `pendiente`.
5. Foto de número desconocido → `sin_comercio` con `media_path`; el archivo está bajo `WA_RECEIVED_DIR` y no bajo `/data/fotos`; por `/fotos/…` da 404.
6. Miniatura: con `whatsapp` → 200; sin token → 401; agente → 403; purgada → 404.
7. «Es de…» autoriza el número (`created_by` = email), reprocesa las de 30 días con la foto local; número de otro comercio activo → 409 sin mover nada; número propio → 400.
8. Retención con `WA_RECEIVED_RETENTION_DAYS=0`: borra el archivo, pone `media_purged_at`, la fila queda.
9. `clean_own_numbers` sin `--apply` no cambia nada; con `--apply` pone `activo=false` (sin `DELETE`).
10. Un mensaje de grupo con `participant` LID y `participantAlt` crea/actualiza `wa_lid_map`.
11. Con los eventos suscriptos, el dueño repite los pasos 1-3 del E0: aparecen filas en `wa_group_events` (mismo evento dos veces = una fila). Se anota en el handoff qué JID y qué forma traen. **Si no llega ninguno, se anota y E1 igual se aprueba** (el respaldo por mensaje no depende de eventos).
12. Webhook con un evento desconocido → 200 y log `webhook.evento_ignorado`.
13. `0159` idéntica en las dos carpetas; anon sin acceso a las tablas nuevas. `cd backend && pytest -q` verde; `cd frontend && npm run lint && npm run build` sin errores.

### 10.2 E2 · Comunidades, redirector y QR del alta (M-L)

**Backend:** `0160`, `services/wa_communities.py` (nuevo: cruce, miembros, resolve, loop de recruce), `services/wa_events.py` (despacho a comunidades, `WA_EVENTS_ACT`), `services/ingest.py` (las comunidades nunca se atan ni publican), `api/communities.py` (nuevo, §7.3), `api/reception.py` (`kind community_join`), `main.py` (router, límite por IP, `_communities_loop`), `core/config.py`, `db/repository.py`, `tests/conftest.py`, tests `test_wa_communities.py`, `test_communities_api.py`.

**Frontend, F2a (admin):** `components/admin/secciones.ts` (sección `communities` «Comunidades», grupo «Contenido», permiso `whatsapp`), `app/admin/page.tsx` (render), `components/communities-panel.tsx` (nuevo), `components/community-poster.tsx` (nuevo, afiche), `lib/communities.ts` (nuevo), `components/bandeja-whatsapp.tsx` (entradas sin dueño con candidato).

**Frontend, F2b (público y agente):** `app/comunidad/[ciudad]/route.ts` y `app/comunidad/[ciudad]/comercios/route.ts` (nuevos), `middleware.ts` (sumar `/comunidad` y `/agente` a `PERMITIDAS`: en modo captura, como QA, hoy darían «Próximamente», `middleware.ts:5`), `app/comunidad/page.tsx`, `components/unirme-comunidad.tsx`, `components/merchant-community-qr.tsx` (nuevo), `app/publicar/page.tsx` (bloque §9.6), `lib/campo.ts` (`communityQr`), `app/volante/[slug]/page.tsx`, `lib/ficha-whatsapp.ts`, `lib/contacto.ts`.

**Criterios de aceptación:**
1. `resolve` devuelve la comunidad abierta de menor número con lugar; salta las llenas, las `preparing` y las `closed`; suma `redirect_count`; la respuesta **no** trae conteos (test de claves).
2. Sin comunidades de compradores cargadas en la ciudad → el link viejo de `redes_sociales`; sin nada → 404 y la ruta redirige a `/comunidad?ciudad=bermejo&lleno=1`.
3. `curl -sI https://<dominio>/comunidad/bermejo` → `302`, `Location: https://chat.whatsapp.com/…`, `Cache-Control: no-store`; también en QA con `NEXT_PUBLIC_MODO_CAPTURA=1` (no «Próximamente»).
4. `join` → `members_count` +1; el mismo dos veces → +1; `leave` → −1; volver → +1; mismo miembro por LID y después con número → una fila y el conteo bien.
5. Comunidad de comercios: número = WhatsApp de **un** comercio activo → `matched`, `comercio_numeros` con `created_by='wa-community:<id>'`; dos comercios → `ambiguous`; ninguno → `unknown`; los dos últimos en «Es de…» con candidato por ventana de tiempo. Comunidad de compradores: cada entrada con número crea su fila con `consent_at` y, si ese número tiene cuenta, `usuario_id`.
6. WhatsApp cargado después de la entrada → cruza en ≤ 10 min.
7. `demote` del Registrador → `registrar_admin=false` y log de error.
8. Un mensaje en un JID de comunidad nunca ata ni publica, aunque traiga un código.
9. Permisos: compradores con número completo sólo con `datos`; con `whatsapp` enmascarado; agente 403; sin token 401; `field_control.read` → `GET …/summary` 200, `POST` 403. El límite por IP corta `resolve` a 60/min.
10. App del agente en modo avión: el QR de su ciudad se ve; sin WhatsApp cargado, el aviso.
11. Volante con QR de la comunidad, «Nuestros agentes nunca cobran» y el 67 671 888 como «Dudas»; `mensajeFicha` no invita a responder para pagar. Ningún texto lleva el código (test).
12. QA manual: escanear el QR con Android (Chrome) y con iPhone (Safari) → abre WhatsApp en «Unirse a la comunidad». Si algún navegador se queda en la página de `chat.whatsapp.com`, anotarlo (T5).
13. `0160` idéntica; anon sin `select` ni `execute`. `pytest -q`; `npm run lint && npm run build`.

### 10.3 E3 · Grupo por comercio: tareas del Anfitrión y atado solo (M)

**Backend:** `0161`, `services/wa_host_tasks.py` (nuevo: tarea al cruzar, reglas §4.2, respaldo por mensaje, generador, `due_on`), `services/wa_group_texts.py` (nuevo, §8), `services/wa_events.py` (despacho a grupos), `services/wa_communities.py` (al cruzar → tarea), `services/ingest.py` (`bind_by_first_message`, `verify_by_message`, sólo grupos `activo`), `api/host_tasks.py` (nuevo, §7.4), `api/moderacion.py` (sólo `listar_grupos`, `soltar_grupo` y la allowlist de edición: `contact_name`), `api/campo.py` (`contact_name`, `whatsapp-status`), `db/repository.py` (`comercio_wa_grupos` con baja lógica: `get_comercio_por_grupo` filtra `activo`, `vincular` reactiva, `desvincular` sin `DELETE`), `main.py` (router + `_host_tasks_loop`), `tests/conftest.py`, `tests/test_comercios_columnas_publicas.py` (`contact_name` a `PRIVADAS_EXTRA`), tests `test_wa_host_tasks.py`, `test_wa_group_texts.py`.

**Frontend, F3a (admin):** `components/admin/secciones.ts` (`host-tasks` «Tareas del Anfitrión», permiso `whatsapp`), `app/admin/page.tsx` (render y bloque de la ficha §9.3), `components/host-tasks-panel.tsx` (nuevo, mobile-first), `lib/host-tasks.ts` (nuevo).

**Frontend, F3b (agente):** `components/ficha-agente.tsx` (estado comunidad / grupo), `components/completar-comercio.tsx` (`contact_name`), `lib/campo.ts` (`whatsappStatus`, `contact_name`), `app/guia-venta/page.tsx`.

**Criterios de aceptación:**
1. Un cruce en la comunidad crea `create_group` con textos; la 11.ª del día nace con `due_on` = mañana; «Hoy» las adelanta.
2. `group.v2.join` con asunto = el esperado (aunque cambien mayúsculas, tildes o espacios) y el número del comercio adentro → atado (`origen='host_task'`), tarea `done_via='event'`, `subject` guardado.
3. Igual con LID sin traducir → atado con `verified=false`; el primer mensaje con `participantAlt` del comercio lo verifica; otro número → `phone_mismatch`.
4. Asunto correcto sin el comerciante → `waiting_merchant`; su `participants join` → atado.
5. Asunto distinto con el número de un comercio con tarea → atado + `rename_group`.
6. Nada coincide → `unbound_group`; «Es de…» lo ata o lo descarta.
7. Sin eventos: el primer mensaje en un grupo sin atar, de un número con tarea abierta → atado y la foto sigue la regla de `confiable`.
8. `group.v2.update` con el asunto esperado cierra `rename_group`; «Pedir renombre» en Vidriería Pacheco crea `rename_group` con los textos.
9. Soltar un grupo → `activo=false`, sin `DELETE` (test sobre el fake y revisión del SQL de `repository.py`); la ingesta deja de identificar por él; atarlo de nuevo funciona.
10. Ningún `name_text`, `description_text` ni `nudge_message` contiene el código vigente ni el anterior (test con un comercio cuyo nombre lo incluye).
11. A las 72 h sin entrada → `nudge_community`; «Crear el grupo igual» lo pasa a `create_group`.
12. `contact.vcf` abre «Guardar contacto» en el Samsung (manual, **a verificar**).
13. `contact_name` no lo lee anon; aparece en la descripción.
14. Tareas usables a 360 px; «Copiar» copia el texto exacto. `pytest -q`; `npm run lint && npm run build`.

### 10.4 E4 · Alertas de cobro, revisión de altas y API del asistente (M)

**Backend:** `0162`, `core/permisos.py`, `api/field_control.py` (nuevo), `services/field_control.py` (nuevo: textos, guion, resumen), `main.py` (router + loop), `db/repository.py`, `tests/conftest.py`, `tests/test_field_control.py`.

**Frontend:** `components/admin/secciones.ts` (`field-control`, grupo «Campo»), `app/admin/page.tsx`, `components/field-control-panel.tsx` (nuevo), `lib/field-control.ts` (nuevo).

**Criterios** (los de la v1 E4): alta de campo → revisión `pending` por trigger (Postgres real) y con otra fuente no; interés de hace 4 días sin pagos → **una** `unpaid_interest` (correr dos veces no duplica) y un pago posterior no efectivo la resuelve sola; pago en efectivo → `cash_payment` baja; `charge_reported` → alerta alta; usuario `assistant`: `GET …/summary` 200, `POST …/resolve` 403, `GET /admin/resumen` 403, `GET /moderacion/publicaciones` 403; claves de `summary` estables (test de contrato); resolver sin nota → 400; los textos no dicen «pagá por QR»; `0162` idéntica y anon sin acceso; `pytest`, `lint`, `build`.

### 10.5 E5 · Credencial del agente (S-M)

**Backend:** `0163`, `api/agent_credentials.py` (nuevo), `core/auth.py` (`require_agente` con corte), `main.py` (router + límite), `db/repository.py`, `tests/conftest.py`, `tests/test_agent_credentials.py`.

**Frontend:** `app/agente/[token]/page.tsx` (nuevo), `components/agent-credential-card.tsx` (nuevo: tarjeta con los dos QR y vista de la app), `components/equipo-panel.tsx`, `app/publicar/page.tsx` (botón «Mi credencial» en la cabecera), `lib/campo.ts` (`miCredencial`), `lib/agent-credentials.ts` (nuevo).

**Criterios** (los de la v1 E5 más dos): token ≥ 22 caracteres, distinto de los ids; reemitir revoca la anterior; nunca dos vivas (Postgres real); la respuesta pública no trae email, teléfono, ids, roles ni permisos; token inexistente → 404 igual siempre; revocada escaneada → una alerta por día; `cut_access` → 401 en `/campo/*` en ≤ 60 s; «Mi credencial» se ve sin señal; la página dice «Los agentes de URUKU nunca cobran» y **no** promete pago por QR; la tarjeta A7 trae el QR de la comunidad de comercios de la ciudad del agente y los dos QR se leen desde otro celular; `0163` idéntica; `pytest`, `lint`, `build`.

### 10.6 E6 · Avisos a las comunidades (S)

**Backend:** `0164`, `api/broadcasts.py` (nuevo), `services/wa_broadcasts.py` (nuevo), `services/ingest.py` (tilde por evento), `main.py`, `db/repository.py`, `tests/conftest.py`, `tests/test_broadcasts.py`.

**Frontend:** `components/broadcasts-panel.tsx` (nuevo, pestaña «Avisos» de Comunidades), `lib/broadcasts.ts` (nuevo), `components/communities-panel.tsx` (sólo montar la pestaña).

**Criterios:** crear un aviso lista todas las comunidades abiertas o llenas de esa audiencia y ciudad; un mensaje del Samsung en el grupo de avisos tilda esa comunidad (`posted_via='event'`); tildar a mano funciona; un mensaje en otro grupo no tilda; `0164` idéntica; `pytest`, `lint`, `build`.

### 10.7 Fuera de esta spec

- **Cobro mensual** (siguiente spec): QR de cobro + recordatorios 1 día antes y a los 3, 6, 9, 12 y 15 días de vencido. **Recomendación: por la API oficial (Marca 67991916) con plantillas de utilidad, no por WhatsApp Web**: mandar automático a muchos números desde WAHA es exactamente lo que dispara el baneo (`numeros-whatsapp-uruku.md:735-757`). Precio por mensaje en Bolivia: verificar. Hasta entonces ningún texto promete «pagá por QR» (P9).
- Notificaciones web (§2.3); asistente con escritura (fase 2) o por Telegram (`2026-06-18-asistente-telegram-mentorcomercial`).
- tech-writer: `manual-operativo-whatsapp.md` §3.1 (el flujo con código queda sólo para grupos viejos), `numeros-whatsapp-uruku.md` (Registrador admin de comunidades; 67671888 fuera de grupos), `circuitos.md`, `manual-agente-de-campo.md` (QR de la comunidad, credencial, «no cobrás nunca»).

## 11. Riesgos

| # | Riesgo | Mitigación | Validación humana |
|---|---|---|---|
| R1 | **LID:** WhatsApp oculta números; si el Registrador sólo ve LID, no hay cruce ni captura | E0 antes de escribir código; plan B por niveles (§4.5); el grupo del comercio verifica el número igual | **Dueño:** correr el E0 y responder Q2 |
| R2 | **Baneo del Anfitrión** por crear muchos grupos | Grupos con un comerciante real que aceptó en la calle; tope diario (T4); nada en blanco ni en tanda | **Dueño:** confirmar el número por día la primera semana |
| R3 | **Reportes en la comunidad de compradores** pegan en su creador (Anfitrión) | Nadie es agregado (entran solos); descripción clara; avisos con frecuencia moderada; segundo admin humano | **Dueño:** frecuencia de avisos |
| R4 | **El Registrador es punto único**: está en todos los grupos y es admin de todas las comunidades; el 67671888 ya no está de respaldo en los grupos nuevos | Las comunidades sobreviven con el Anfitrión como dueño; si cae el Registrador, se re-vincula otro número y el Anfitrión lo agrega (tarea `add_registrar`) | **Dueño:** aceptar el riesgo por escrito |
| R5 | Tope real de una comunidad desconocido (2.000 o 5.000) | Cupo por comunidad, por defecto 1.800; aviso al 90 % | — |
| R6 | **Sin Política de privacidad** capturando números de compradores | Consentimiento en el afiche, la descripción y `/comunidad`; sin exportar ni otro uso hasta publicarla; teléfonos sólo con `datos` | **Dueño + legal:** Q1 |
| R7 | El link de la comunidad de comercios es alcanzable por cualquiera | Entradas sin cruce van a «Es de…» y se sacan a mano; en el grupo de avisos los miembros no se ven entre sí | — |
| R8 | El conteo por eventos se desvía (WAHA caído) | Corrección manual con nota; margen en el cupo | Mirar el conteo del teléfono una vez por semana |
| R9 | Sesión de WAHA pesada con miles de miembros y cientos de grupos (`whatsapp-arquitectura-y-escala.md:59-69`) | Todo aislado en `wa_*` (§2.5) | Revisar a los 300 grupos o 5.000 miembros |
| R10 | Heredados de la v1: el código se filtra en un texto; página falsa de credencial; foto del agente pública; comprobante de pago mandado al grupo | Una función filtra los textos (test); «fijate que diga uruku.bo» + reloj vivo; nombre de archivo aleatorio; los comercios de campo nacen no confiables (`campo.py:327`) → cola | **Dueño:** consentimiento de cada agente para su foto |

## 12. Preguntas abiertas (sólo las que bloquean)

| # | Pregunta | Qué bloquea | Si no hay respuesta |
|---|---|---|---|
| Q1 | ¿Quién redacta la **Política de privacidad** y cuándo se publica? | Imprimir el afiche de compradores y cualquier uso de esos números fuera de la comunidad | Se implementa E2; el afiche se imprime **sin** la línea de privacidad y no hay exportación. Recomendación: publicarla antes de imprimir |
| Q2 | Si el E0 da **LID sin traducción** (B3): ¿seguimos con comunidades de compradores sólo para avisar, o el QR de compradores pasa a la página «Avisame por WhatsApp» (cuenta con `CONFIRMAR`)? | El destino del QR de compradores y el criterio 5 de E2 para compradores | Comunidades sólo para avisos + botón «Dejanos tu número» en `/comunidad` |

## 13. KB aplicada

- `pattern-soft-delete-activo-flag`, `lesson-nunca-delete-fisico-siempre-soft`: `activo` en todo lo nuevo; `comercio_wa_grupos` deja el `DELETE` (P5).
- `lesson-supabase-cloud-grants-explicitos-en-migration`, `pattern-supabase-rls-policy`, `lesson-rls-sin-valvula-de-escape-escribible-por-la-app`: RLS, `revoke` y `grant` en cada migración; funciones sólo para `service_role`.
- `lesson-supabase-service-role-key-nunca-en-frontend`: el front nunca toca comunidades, tareas ni credenciales por PostgREST; el redirector pasa por el backend.
- `pattern-identidad-celular-progresiva`: el número que entra a la comunidad queda autorizado (`numero`, verificado por WhatsApp).
- `pattern-wa-me-link-sin-api`: «Mandarle el link» y «Escribirle» salen del Samsung, nunca de WAHA. `pattern-fire-and-forget-tracking`: el conteo de redirecciones no frena el 302.
- `2026-06-04-stack-bermejo`: WAHA no oficial; esta spec no le suma escrituras (sólo lecturas opcionales de LID).
- `2026-06-10-modelo-producto-bermejo`: el comerciante publica por WhatsApp con moderación; se mantiene.
