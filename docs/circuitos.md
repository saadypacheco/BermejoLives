# Circuitos de URUKU — cómo entran y publican (6/10/2026)

> Mapa de cómo funciona cada actor hoy: comprador, comerciante, agente de campo,
> explorador, moderador, admin. Se escribe después de la Limpieza de circuitos.
> Este documento reemplaza la versión del 15/6.

## Por actor

### Comprador / visitante

#### Cómo entra

**Celular + clave de 6 números**, siempre.

| Situación | Flujo |
|---|---|
| **Primera vez** | POST `/auth/usuario/solicitar-codigo` (celular) → genera código → muestra botón "Confirmar por WhatsApp" (`wa.me` con `CONFIRMAR-XXXXXX` precargado) → cuando llega el `CONFIRMAR` por webhook, frontend pollea `/auth/usuario/verificar` → se muestra la clave nueva, UNA sola vez → después entra con esta clave + celular |
| **Me olvidé la clave** | Toca "¿Te olvidaste?" → mismo flujo que primera vez |
| **Ingreso normal** | POST `/auth/usuario/ingresar` (celular + clave guardada) |

**Normalización:** se guarda en E.164 (`59170000001`). Si escribe `70000000` (sin 591) el frontend lo toma como Bolivia y lo manda normalizado.

**Seguridad:** 5 intentos fallidos en 15 minutos → bloquea ese número por 15 minutos. Mismo mensaje si el número no existe (no delata quién tiene cuenta).

#### Qué guarda la base

- `whatsapp`: número normalizado en E.164
- `clave_hash`: hash de 6 números (nunca plaintext)
- `verificado_en`: cuándo confirmó por WhatsApp (UNA sola vez, nunca se borra)
- `consentimiento_en`: cuándo aceptó recibir ofertas (tilde explícito, no por defecto)
- `ref`: el `?ref=` del QR o volante de dónde vino; vence a 30 días

#### Contacto: botones de la ficha

Cuando el comprador toca un botón, el contacto lleva el origen guardado en `?ref=`:

| Botón | A dónde | Qué | Qué se registra |
|---|---|---|---|
| "Llamar" | `wa.me/<numero>?text=...` | WhatsApp del comercio | Lead tipo `'whatsapp'` |
| Chatbot → "Preguntarle" | `wa.me/<numero>?text=Hola, te escribo...` | Igual + pregunta precargada | Lead tipo `'whatsapp'` |
| "Cómo llegar" | `wa.me/<numero>?text=Hola...` | Igual | Lead tipo `'mapa'` (contacto de ubicación) |
| Reserva (carrito) | `wa.me/<numero>` | Igual | Lead tipo `'reserva'` (contacto de compra) |
| Explorador (oferta) | `wa.me/67677803` | Explorador (hasta que comercio se suma) | Igual |

En todos: el `?ref=` viaja en el URL si existe.

---

### Comerciante — primera vez

#### Opción A: Autoregistro web (`/autoregistro`)

1. Formulario: nombre, WhatsApp, foto, GPS, modalidad, rubro
2. POST `/auth/comercio/registro`
3. **Se crea:**
   - Comercio: `confiable = false`, `plan = "gratis"`, `verificado = false`
   - Cuenta automáticamente
   - Clave de 6 números
4. **Se muestra:**
   - Pantalla: "Código de tu negocio"
   - Código `URUKU-XXXX` (para atar grupo o publicar 1 a 1 por WhatsApp)
   - Clave de 6 números: "Guardala, no se vuelve a mostrar"
5. **Se devuelve:** token de acceso
6. **Después:** puede publicar desde `/publicar` (chatbot) o atar un grupo

#### Opción B: Agente de campo (`/campo/comercio`)

1. Agente carga: nombre, WhatsApp, foto, GPS, modalidad, rubro
2. POST `/campo/comercio`
3. **Se crea:**
   - Comercio: `confiable = false`, `fuente = 'campo'`, `verificado = false`
   - Cuenta automáticamente (si falla, se recupera por WhatsApp después)
   - Clave de 6 números
4. **App del agente muestra la clave UNA vez** (para dictarla en mano, **nunca escrita**)
5. **Se devuelve:** código `URUKU-XXXX`
6. **El agente entrega al dueño:**
   - Código (para WhatsApp o grupo)
   - Clave (de palabra, nunca escrita)
   - Link: "Tu negocio ya está en URUKU"

#### La diferencia

| | Web | Campo |
|---|---|---|
| **Quién carga** | El dueño | Agente de URUKU |
| **Dónde** | Desde el teléfono, en casa | En la visita |
| **Foto** | El dueño saca | Agente saca |
| **Clave** | Se muestra en pantalla del dueño | Agente la dicta en mano; el dueño la escribe en su celular |
| **Código** | Se muestra en pantalla | Agente anota y se lo copia al dueño |

---

### Comerciante — acceso posterior

#### Si se olvidó la clave (primera vez y recuperación)

1. POST `/auth/comercio/recuperar` (celular)
2. Backend busca comercios activos con ese número
3. **Si hay cero:** error 404 ("No encontramos tu negocio")
4. **Si hay uno:** genera código, devuelve link `wa.me` con `CONFIRMAR-XXXXXX`
5. **Si hay varios:** error 409 con lista (id, nombre, dirección) para elegir
6. Comercio elige y POST `/auth/comercio/recuperar` con `comercio_id`
7. Se crea cuenta si faltaba (campo sin cuenta luego)
8. Muestra: "Confirmar por WhatsApp"
9. Frontend pollea `/auth/comercio/verificar` cada 2.5 segundos
10. Cuando llega `CONFIRMAR` por webhook: genera clave nueva, la muestra UNA vez
11. Después: entra con celular + esta clave

#### Ingreso normal (con clave guardada)

POST `/auth/comercio/ingresar` (celular + clave)

- Si el número tiene varias cuentas: prueba la clave contra todas, entra en la que coincide
- 5 intentos fallidos → bloqueo 15 minutos
- **No pide contraseña nueva;** la clave se gasta UNA vez (al crear o confirmar), después es "la" clave

---

### Publicación: cuatro caminos

#### **A. Grupo de WhatsApp (el estándar)**

**Presupuesto:** UN grupo por comercio, con el comerciante, Operativo (WAHA, sólo lectura), y Respaldos.

| Paso | Qué pasa |
|---|---|
| **Crear grupo** | Anfitrión (`75314737`) crea desde Samsung: `URUKU · {nombre local}` |
| **Agregar Operativo** | Anfitrión agrega `64610187` (Registrador; WAHA lo vincula aquí) |
| **Atar con código** | Anfitrión o comercio manda `URUKU-XXXX` adentro; `_atar_grupo_por_codigo_propio` lo ve y lo ata |
| **Comercio publica** | Manda foto + texto (o sólo foto) en el grupo |
| **Webhook** | WAHA recibe en `/ingest/webhook` |
| **Identificar** | `_identificar_por_grupo`: ¿grupo ya atado? → ese comercio |
| **Moderar** | Comercio `confiable = true` → directo (`'aprobado'`) · Comercio `confiable = false` → cola (`'pendiente'`) |
| **Si rechaza** | Foto queda en `wa_inbox` marcada rechazada; no se publica |

**Se rechaza (no crea nada):** mensajes del Operativo mismo, mensajes de números de URUKU (en `WA_NUMEROS_PROPIOS`), 1 a 1 sin código de número desconocido.

#### **B. Chat 1 a 1 con código**

El comercio manda WhatsApp al Registrador con `URUKU-XXXX` en el texto.

| Paso | Qué pasa |
|---|---|
| **Comercio manda** | `📷 URUKU-XXXX zapatilla urbana Bs 180` |
| **Webhook** | WAHA recibe |
| **Identificar** | `_identificar_comercio`: ¿grupo? (no) → ¿número conocido? (no, es 1 a 1) → ¿código en texto? → sí → busca comercio por código |
| **Autorizar número** | Se agrega `(numero, comercio)` con motivo "se identificó con código"; de ahora en adelante ese número publica directo (sin código) |
| **Atar JID** | Se vincula el JID de WhatsApp al comercio |
| **Moderar** | Comercio `confiable` → directo / no confiable → cola |

**Quién lo usa:** comercio sin grupo aún, o agente cuando el comercio todavía no se sumó.

#### **C. Desde la cuenta (`/comercio/publicar`)**

Comercio logueado publica desde el chatbot de Mi comercio.

| Paso | Qué pasa |
|---|---|
| **POST `/comercio/publicar`** | Título, descripción, foto, tipo (oferta/video/novedad) |
| **Cuota** | ¿Pasó su cuota mensual? → se cobra Bs 5 extra, se avisa, se publica |
| **Tope** | ¿Ya tiene 70 publicaciones? → se archiva la más vieja, se borra su foto del disco (si es de URUKU; URLs externas no se tocan) |
| **Moderar** | Comercio `confiable` → directo / no → cola |
| **Difusión** | Si aprobada: sale a Facebook, Instagram (con token), canal WhatsApp |

**Quién lo usa:** comercio en plan Destacado+ que quiere control.

#### **D. El explorador**

Número dedicado que sale a fotografiar ofertas de locales que no publican.

| Paso | Qué pasa |
|---|---|
| **Manda foto** | `📷 URUKU-AQXP zapatilla urbana Bs 180` desde `67677803` |
| **Webhook** | WAHA recibe |
| **Identificar** | Número es `WA_NUMEROS_EXPLORADOR` → parsea código → busca comercio |
| **Publicar a su nombre** | Foto en ficha del comercio real (no de "URUKU Ofertas" ficticio) |
| **SIEMPRE a moderación** | `identidad_origen = 'explorador'` → **nunca auto-aprueba**, incluso si comercio es confiable |
| **Contacto** | Mientras comercio NO se sumó: derivación va a `67677803` · Cuando se suma: se llena `contacto_whatsapp` con su número |

**Qué cambia cuando el comercio se suma:**
- Explorador sigue subiendo fotos (comercio no se entera)
- Derivaciones van al comercio (no al explorador)
- `vaciar_contacto_whatsapp_explorador` automático

---

### Moderador / Publicador

#### Admin › Publicaciones

| Estado | Significado |
|---|---|
| **Pendiente** | En cola, espera aprobación |
| **Aprobada** | Publicada (o aprobada) |
| **Rechazada** | Rechazó moderador |
| **Archivada** | Cumplió tope de 70, se archivó |

#### Acciones

| Acción | Qué pasa |
|---|---|
| **Aprobar** | Estado → `'aprobado'`, sale a difusión (Facebook, Instagram, canal) |
| **Rechazar** | Estado → `'rechazada'`, se descarta. Comercio **no se entera** (WAHA es sólo lectura) |
| **Cambios** | Edita: título, descripción, foto, precio |

#### Recepción

Admin › Recepción muestra:

| Campo | Qué significa |
|---|---|
| **Identidad origen** | De dónde se atribuyó: `'numero'` (conocido), `'codigo'` (en texto), `'desconocido'` (no se supo; **NO se creó nada**) |
| **Comercio** | A quién se atribuyó |
| **Tipo contacto** | Cómo llegó: `whatsapp`, `wa_inbox sin_comercio`, etc. |
| **Estado WAHA** | En vivo: ¿Operativo vinculado? Si dice "DISCONNECTED", no entra nada |

**Lo que cambió el 6/10:** Un número desconocido sin código ya NO crea comercio fantasma. Queda como `sin_comercio` y no hay nada que moderar.

---

### Admin

#### Comercios

- **Crear/editar:** datos (nombre, WhatsApp, rubro, foto, etc.)
- **Confiable:** tilde para que publique directo
- **Verificado:** se chequea número, dirección, existencia
- **Plan:** funciones (Básico, Destacado, Pro)
- **Suspender:** fuera del mapa, no publica
- **Grupo WhatsApp:** botón crear/atar

#### Planes

- **Publicaciones por mes:** cuántas gratis (Bs 5 después)
- **Publicaciones guardadas:** máximo que guarda (70 por defecto; NULL = sin tope)
- **Funciones:** chatbot (`asistente_24_7`), IA (`asistente_ia`)
- **Precio:** oculto al público, se edita aquí

#### Moderación

- Recepción (qué llegó, qué procesó, qué quedó sin comercio)
- Publicaciones en cola
- Cambios de número solicitados
- Reclamos

---

### Agente de campo

#### Alta de comercio

**Carga:** nombre, WhatsApp, teléfono, rubro, modalidad, dirección, GPS, foto, horario, factura, envíos.

**Resultado:**

- Comercio: `fuente = 'campo'`, `confiable = false`
- Cuenta creada (o recuperable por WhatsApp si falla)
- **Clave de 6 números** mostrada en app (para dictar; **nunca escrita**)
- **Código `URUKU-XXXX`** en la respuesta

**El agente entrega:**

- Código (para WhatsApp o grupo)
- Clave (sólo de palabra)
- Link: "Tu negocio ya está en URUKU"

**Nunca:**

- Clave escrita, en volante, en WhatsApp
- Código sí va en volante

---

## Tabla: quién escribe qué y quién ve

| Dato | Tabla | Quién escribe | Quién lee | Restricción |
|---|---|---|---|---|
| Número comprador | `usuarios` | Comprador (solicita código) | Comprador, Admin | Comprador ve sólo el suyo |
| Clave comprador | `usuarios` (hash) | Sistema (genera) | Sistema (login) | Nunca plaintext |
| Favoritos | `comercios_favoritos` | Comprador (guarda) | Comprador | Soft-delete |
| Número comercio | `comercios` | Admin, Agente, Comercio | Público (mapa, ficha), Admin | Normalizado |
| Clave comercio | `comercio_usuarios` (hash) | Sistema (genera al alta) | Sistema (login) | Nunca plaintext |
| Código `URUKU-XXXX` | `comercios` | Sistema (genera) | Público (ficha, discreto), Comercio (claro) | Nunca es contraseña |
| Publicación | `publicaciones` | Comercio, Agente, Explorador | Público si `aprobada`, Admin | Soft-delete `activo` |
| Foto publicación | Supabase Storage | Sistema (sube) | Público si aprobada | Se borra si archiva (tope) |
| Respuesta local | `saber_local` | Comercio (Mi comercio › Ayuda) | Chatbot de ese comercio (su `comercio_id`) | Nunca al público |
| Lead (contacto) | `leads` | Sistema (al contactar) | Admin › Compradores, Comercio | Registra `origen` (ref) |
| Número explorador | `publicaciones` (contacto_whatsapp) | Sistema | Público en derivación | Se cambia cuando comercio se suma |

---

## Lo que NO existe todavía

Avisarlo explícitamente: nadie lo promete.

| Qué | Por qué | Cuándo |
|---|---|---|
| **Avisos por WhatsApp** | WAHA sólo lectura; avisos quedan "AVISARLE" en Recepción | Cambio proveedor WhatsApp |
| **Notificaciones web** | No hay sistema | Fase siguiente |
| **QR + página de aterrizaje** | Página no existe aún | Fase siguiente |
| **Formulario de intereses** | No existe | Fase siguiente |
| **API oficial Meta** | Hoy WAHA + `wa.me` | Fase siguiente |
| **Telegram** | Opcional, fuera de alcance | Si el comercio lo elige |
| **Envío desde Admin** | Panel no escribe; lo hace una persona | Por diseño |

---

## Lo que viene (orden acordado)

1. **QR + aterrizaje:** captura número comprador sin que escriba
2. **Formulario de intereses:** "¿qué te interesa?" para segmentar
3. **Notificaciones web:** "Nuevo desde {comercio}"
4. **API oficial Meta:** respaldo de WAHA + envío de códigos
5. **Telegram:** si lo elige comercio

---

## Validación: orden de cada mensaje

Cuando llega un WhatsApp:

```
1. ¿"CONFIRMAR-XXXXXX"?
   → sí: login/recuperación, para
   → no: continúa

2. ¿Mensaje propio (WAHA/Admin)?
   → sí: ignora, para
   → no: continúa

3. ¿Número de URUKU (WA_NUMEROS_PROPIOS)?
   → sí: ignora, para
   → no: continúa

4. ¿Es grupo?
   → sí: ¿grupo atado? ese comercio / ¿código? ese comercio / no → sin_comercio, para
   → no: ¿número conocido? ese comercio / ¿código? ese comercio / no → sin_comercio, para

5. ¿Explorador (WA_NUMEROS_EXPLORADOR)?
   → sí: parsea código, publica, va a moderación siempre

6. Si identificó comercio: ¿confiable?
   → directo / no → cola
```

---

## Recuento: cinco roles, entrada por rol

| Rol | Entrada 1 | Entrada 2 | Entrada 3 |
|---|---|---|---|
| **Comprador** | Celular + clave | WhatsApp + confirmación | — |
| **Comerciante** | Celular + clave | WhatsApp + confirmación | Web (autoregistro) |
| **Agente** | Email + contraseña (panel) | — | — |
| **Publicador** | Email + contraseña (panel) | — | — |
| **Explorador** | Número WhatsApp (no web) | — | — |
