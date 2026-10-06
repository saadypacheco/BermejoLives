# Limpieza de circuitos — spec

> **Estado: implementada el 6/10/2026, sin desplegar.** Ver «Estado al cierre» al final. Va antes del QR de
> captación de compradores, que se apoya en lo que esto arregla.

## Por qué

El 5/10 se mapearon todos los canales y circuitos contra el código. Salieron
caminos duplicados, datos del mismo tipo en varias tablas y textos que
prometen cosas que no pasan. Antes de sumar un canal más (el QR que captura el
número del comprador), se limpia lo que ese canal va a usar.

## Decisiones del usuario (6/10/2026)

- **Limpieza primero, después el QR.**
- **El plan gratis publica sin límite de meses durante el arranque.** Se cambia
  en Admin › Planes (campo «Meses que puede publicar», vacío = siempre). No es
  código.
- **Los compradores del QR los atiende la Marca (67991916) con la API oficial
  de WhatsApp.** Cambia la decisión del ADR 2026-06-10 («el número central
  sólo envía»). Se implementa en la fase del QR, no acá.
- **Productos de Reservalo y «Destacar» se esconden de Mi comercio** hasta que
  Reservalo vuelva a ser parte de la oferta. No se borra nada.

## Qué se arregla

### Backend

1. **Sin comercios fantasma.** Hoy, cualquiera que le escribe 1 a 1 al
   Registrador sin código crea un comercio apagado («Comercio 1234») y una
   publicación pendiente (`services/ingest.py` ~143,
   `repository.upsert_comercio_by_jid`). Un mensaje 1 a 1 de un número
   desconocido, sin código, queda en `wa_inbox` como `sin_comercio` con un
   motivo claro, y no crea ni comercio ni publicación. No cambia: los
   `CONFIRMAR-XXXXXX`, el explorador, los números propios, el código
   `URUKU-XXXX` ni los grupos ya atados.
2. **Una sola identidad del comprador, en `usuarios`.**
   - El número se normaliza (E.164, con `core/telefono.py`) al pedir el
     código, al verificar y al confirmar por el webhook. Hoy quien escribe su
     número sin el 591 nunca confirma.
   - Columnas nuevas: `verificado_en` (se llena cuando confirma por WhatsApp; ya
     no se borra la marca al confirmar) y `consentimiento_en` (sólo con un tilde
     explícito; el `consentimiento_ofertas` que hoy nace en true no cuenta como
     consentimiento).
   - Lo mismo para la recuperación de cuenta del comercio
     (`/auth/comercio/recuperar`).
3. **La atribución del QR llega al contacto.** `POST /lead` acepta y guarda el
   `origen` (el `?ref=`) en los leads de WhatsApp, mapa y reserva. El panel
   «Llegadas» muestra las llegadas desde `visitas.origen` y los contactos desde
   `leads.origen`. Hoy los enlaces `?ref=grupo-…` nunca aparecen ahí.
4. **El comercio cargado en la calle puede entrar a Mi comercio.** Se le crea
   la cuenta en el alta de campo (como ya pasa al pagar, `asegurar_comercio_usuario`)
   y una migración se la crea a los que ya existen. Entra pidiendo el código por
   WhatsApp desde el número de su ficha. Si el número no corresponde a ningún
   negocio, el error lo dice en vez de dejar la pantalla esperando.
5. **El autoregistro le devuelve su código `URUKU-XXXX`**, para que pueda atar
   un grupo o publicar 1 a 1.
6. **La aprobación automática por IA nunca aplica a lo del explorador**: eso va
   siempre a moderación humana.
7. **Código y textos muertos:**
   - Se retira `POST /mensaje` (el formulario viejo, sin pantalla, abierto al
     público). La tabla y lo que ya entró quedan.
   - Se borra `enviar_codigo_otp` sin uso.
   - La firma «Encontralo» de los mensajes del admin pasa a «URUKU».
   - El asistente deja de prometer «registralo y te creamos el grupo».
8. **Favoritos con soft-delete.** Hoy quitar un favorito borra la fila.

### Frontend

1. **Mi comercio con una sola forma de publicar.** Se esconden Productos
   (Reservalo) y «Destacar». «Publicar» y «Nueva oferta» llevan al mismo lugar
   (el chatbot de `/autoregistro`).
2. **El pago sin datos falsos.** Se sacan las imágenes de QR que no existen y el
   monto por defecto de 30.000 pesos argentinos. En su lugar, un «Consultá el
   monto y cómo pagar» por el WhatsApp de URUKU (`lib/contacto.ts`). La subida
   del comprobante queda.
3. **Sin promesas rotas:**
   - «te avisamos de ofertas» (perfil, ingreso del comprador) sale hasta que
     exista el canal;
   - `/reclamos` no promete una respuesta automática;
   - «Sumar mi negocio» lleva a `/autoregistro`, no al login del agente.
4. **El `?ref=` viaja en los contactos:** los botones de WhatsApp, mapa y
   reserva mandan el origen guardado.
5. **Código muerto fuera:** `live-feed.tsx`, `mobile-home.tsx`,
   `home-map.tsx`, `search-hero.tsx`, lo que no se usa de `nav.tsx` y
   `dejarMensaje`.
6. **Autoregistro:** al terminar, muestra el código `URUKU-XXXX` y para qué
   sirve.
7. **El comerciante entra con su WhatsApp desde «Tengo un negocio».** Hoy
   Ingresar → «Tengo un negocio» abre `/mi-comercio`, que sólo pide email y
   contraseña (casi ningún comercio los tiene), y el ingreso por WhatsApp está
   escondido en `/autoregistro`. Mi comercio ofrece primero «Entrar con tu
   WhatsApp»; email y contraseña quedan como segunda opción. Después de
   confirmar entra directo, sin que se le pida una contraseña nueva (el backend
   la acepta opcional y gasta el código igual: sirve una sola vez). El enlace
   «Creala acá» avisa que, si el negocio ya está en el mapa, no lo cree de
   nuevo: así no se duplican comercios. Agregado el 6/10 a pedido del usuario.

### Documentación (al final)

- Reescribir `docs/circuitos.md` y `AGENTS.md` §3-4 con el mapa actualizado.

## Criterios de aceptación

1. Un mensaje 1 a 1 sin código desde un número desconocido no crea comercio ni
   publicación, y queda en Recepción como «sin comercio».
2. Un comprador que escribe «70000001» y confirma por WhatsApp queda con
   `verificado_en`, y su número guardado es `59170000001`.
3. Un contacto por WhatsApp de alguien que llegó con `?ref=volante-x` queda con
   `origen = volante-x`, y aparece en Llegadas.
4. Un comercio cargado por el agente puede entrar a Mi comercio con el código
   por WhatsApp desde su número.
5. Una foto del explorador nunca se aprueba sola.
6. Mi comercio no muestra Productos, Destacar, QR de pago ni montos en pesos
   argentinos.
7. `POST /mensaje` ya no existe.
8. Tests del backend en verde y `tsc` sin errores.

## Fuera de alcance

- El QR, la página de aterrizaje, el formulario de intereses y la API oficial
  (fase siguiente).
- El carrito de Reservalo (vive en otro repo).
- Medir el botón «Llamar» de la ficha.
- El texto del volante impreso («mande la foto al grupo»).

## Segunda ronda (6/10/2026): clave de 6 números y hallazgos de QA y revisión

### Decisiones del usuario

- **Se entra con celular + una clave secreta de 6 números**, comerciante y
  comprador. El código `URUKU-XXXX` NO sirve como clave: hoy cualquiera lee
  el código y el WhatsApp de todos los comercios desde la base pública, y el
  código está impreso en el volante y se manda en el grupo.
- **El WhatsApp (CONFIRMAR) queda para la primera vez y para «me olvidé la
  clave».** Así entrar no depende de WAHA.
- **El código del comercio sigue visible**, pero presentado de forma que sólo
  el comerciante entienda qué es: en la ficha pública como una referencia
  discreta («Ref. KPXN»), sin decir para qué sirve; en Mi comercio, claro y con
  su explicación, para que lo encuentre si se lo olvida. Con la clave, el código
  ya no da acceso a nada: sólo sirve para publicar, y eso va a moderación.

### La clave

- URUKU la genera: 6 números al azar. Se guarda sólo el hash (como las
  contraseñas). Nunca va en el volante ni en un WhatsApp.
- **Comerciante:** la recibe en la visita (la app del agente la muestra UNA vez
  al dar de alta el comercio, para dársela en mano) o al entrar por WhatsApp si
  todavía no tenía. Desde Mi comercio puede generar una nueva.
- **Comprador:** la primera vez confirma por WhatsApp y ahí se le muestra su
  clave. Después entra con celular + clave.
- **Protección:** 5 intentos fallidos por número bloquean 15 minutos.
- **Si el número tiene varios comercios**, la clave identifica cuál: al
  generarla se garantiza que no se repita entre los comercios de ese número.

### Arreglos de QA y revisión

1. **Normalizar el número al guardarlo** en la ficha (alta de campo,
   autoregistro, importados, edición del comerciante y del admin) y una
   migración que normalice los que ya están, sólo los que validan. Hoy
   «+591 7012-3456» en la ficha no matchea con «70123456».
2. **Número compartido por varios comercios:** nunca se elige uno en silencio.
   La recuperación por WhatsApp devuelve la lista (nombre y dirección) para que
   la persona elija, y el código queda atado a esa cuenta. Orden determinista
   en toda búsqueda por número. Los números de URUKU nunca abren una cuenta.
3. **Fantasmas viejos:** la identificación 1 a 1 por número sólo considera
   comercios activos; los fantasmas ya creados dejan de juntar publicaciones.
4. **CONFIRMAR dice para qué es:** el mensaje precargado aclara «para entrar a
   Mi comercio de URUKU» (contra el engaño de pasarle el enlace a un dueño).
5. **El polling de la confirmación se corta a los 15 minutos** con «el código
   venció, pedí otro».
6. **La IA:** el comercio/publicación es obligatorio al decidir la
   auto-aprobación, y también mira `identidad_origen == 'explorador'`.
7. **El `?ref` guardado vence a los 30 días.** `/lead` y `/visita` limpian el
   ref con la misma regla. La paginación de visitas tiene orden total.
8. **Restos:** «Encontralo» en las plantillas de WhatsApp y en el prompt del
   clasificador → URUKU; `/planes` no menciona QR de pago; el select de pago no
   ofrece QR de Bolivia/Argentina; el `uruku_ref` del comprador viejo sin 591
   se normaliza al verificar; el test inestable
   `test_las_respuestas_vienen_las_ultimas_primero_y_se_paginan`.

### Criterios de aceptación (segunda ronda)

9. Un comercio de campo con la ficha «+591 7012-3456» entra con «70123456».
10. Celular + clave correcta entra; clave incorrecta 5 veces bloquea 15 minutos.
11. Un número con dos comercios: la clave de cada uno abre el suyo, y la
    recuperación por WhatsApp pide elegir.
12. La clave nunca aparece en el volante, en la ficha pública ni en un log.
13. El comprador recibe su clave al confirmar por WhatsApp y después entra sin
    WhatsApp.

## Tercera ronda (6/10/2026): seguridad del ingreso con clave

La revisión de seguridad bloqueó el deploy. Lo mínimo antes de desplegar:

1. **Un ingreso correcto nunca resetea el contador de fallos de un número.**
   Ventana deslizante: 5 fallos en 15 minutos bloquean 15 minutos; 10 fallos
   en 24 horas ANULAN la clave y hay que volver a entrar por WhatsApp. El
   contador se incrementa de forma atómica en la base ANTES de verificar la
   clave. Hoy, quien cuelga un comercio propio del número de la víctima entra
   con su clave, resetea el contador de todas las cuentas de ese número y
   prueba claves de la víctima sin bloqueo nunca.
2. **No se puede colgar un comercio de un número que ya usa otro comercio
   activo.** El autoregistro con un número ya registrado contesta 409 («Ese
   número ya tiene un negocio en URUKU: entrá con tu WhatsApp»). De paso evita
   duplicados.
3. **El WhatsApp de la ficha no se edita desde Mi comercio.** Se cambia con la
   solicitud de cambio de número (la aprueba el admin). Hoy, quien entra
   indebidamente cambia el número y la cuenta queda suya para siempre.
4. **La clave nunca se guarda en el navegador.** `clave_inicial` viaja sólo en
   la raíz de la respuesta, no dentro de `comercio`, y el autoregistro se la
   muestra al dueño una vez.
5. **Límite de fallos por IP, con la IP real** (el último valor de
   `X-Forwarded-For`, el que agrega el proxy, no el primero, que lo inventa el
   cliente).
6. Además, porque son baratos: `Cache-Control: no-store` en toda respuesta con
   una clave; el consentimiento del comprador recién cuenta cuando confirma el
   número; `POST /comercio/clave` limitado a 3 por hora; los ingresos se
   registran con `comercio_id`, método e IP (nunca la clave).

Para una ronda siguiente (anotado, no bloquea): cerrar las sesiones abiertas al
cambiar la clave; exigir el texto exacto del CONFIRMAR con el nombre del
comercio y rechazar reenviados; que la clave que da el agente sea provisional;
un identificador por pedido en `estado`/`verificar`; pepper en el hash.

### Criterios de aceptación (tercera ronda)

14. Con un comercio propio en el número de la víctima, 12 claves malas
    bloquean, aunque entre con la suya en el medio.
15. 10 fallos en 24 horas anulan la clave: sólo se entra por WhatsApp.
16. El autoregistro con un número que ya tiene negocio da 409.
17. `PUT /comercio/perfil` no cambia el WhatsApp.
18. Ninguna clave queda en localStorage.

## Estado al cierre (6/10/2026)

**Verificado:**
- 1380 tests del backend en verde y `tsc` sin errores.
- La migración 0137 se corrió contra un Postgres 17 con todas las migraciones:
  pasa sin errores tres veces seguidas; normaliza «+591 7012-3456» a
  `59170123456` y no toca fijos ni números argentinos; el backfill no duplica
  cuentas; el contador de intentos cuenta por número y por IP; el público
  recibe «permission denied» en la función, en `clave_fallos`, en las cuentas,
  en `saber_local.creado_por` y en `planes.precio_mes`.
- Las dos pruebas de concepto de la revisión de seguridad ya no funcionan en lo
  que bloqueaba el deploy: colgar un comercio del número de la víctima para
  resetearle el contador, cambiar el WhatsApp desde Mi comercio, y que un agente
  cambie el WhatsApp de un comercio ya cargado.
- Todo cambio del WhatsApp de un comercio que ya existe (edición del admin,
  aprobación de «Cambié de número») rechaza un número que es de otro comercio
  activo y anula la clave. El agente completa un número vacío, no lo cambia.

**Sin verificar:** nada se abrió en un navegador ni contra el WhatsApp real.

**Riesgo encontrado al probar, ajeno a este cambio:** un servidor nuevo no se
puede armar desde cero con `selfhost/postgres-init`. Fallan en un Postgres 17
vacío la 0049 (`unaccent` en un índice: «functions in index expression must be
marked IMMUTABLE»), la 0069, la 0070 y la 0092 (dependen de lo que no se creó).
Producción anda porque su base es anterior.

**Para la ronda siguiente** (revisados y aceptados para después):
- Cualquiera puede anular la clave de un comercio con 10 intentos (los números
  son públicos). Afecta la disponibilidad, no da acceso. Alertar sobre la tasa
  de anulaciones y, más adelante, bloquear 24 horas en vez de anular.
- Pedir un código pisa el pendiente sin límite por número: sumado a lo
  anterior, deja al dueño afuera. No pisar un código vigente.
- Cerrar las sesiones abiertas al cambiar la clave (el JWT dura 7 días).
- El CONFIRMAR acepta cualquier texto y mensajes reenviados.
- `GET /recuperar/estado` sin límite; el polling del comprador choca con el
  límite de `/auth/*`.
- La clave que da el agente no es provisional.
- `clave_fallos` sin política de retención (número + IP).
- Si `api.uruku.bo` pasa a estar detrás del proxy de Cloudflare, la IP real
  sale de `CF-Connecting-IP`, no de `X-Forwarded-For`.
