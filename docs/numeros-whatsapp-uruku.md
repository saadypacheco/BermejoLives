# Los números de WhatsApp de URUKU

> Quién es quién en los grupos, cómo se configura, y qué hacer el día que
> baneen el operativo. Escrito antes de necesitarlo a propósito: ese día no hay
> tiempo de razonarlo.

## La tabla definitiva (11/9/2026)

Decidida el 11/9, después de dos días de darle vueltas. **WAHA sólo lee.**

| Rol | Número | Operadora | Dónde | Qué hace |
|---|---|---|---|---|
| **Registrador** | 64610187 | Entel | Tablet (chip físico) | **Sólo** corre WAHA: está en cada grupo y lleva lo que llega a la base. No escribe nunca. Es dueño del canal, que se publica **a mano** desde acá |
| **Anfitrión** | 75314737 | Tigo | Samsung | Crea los grupos **a mano**, es admin de cada uno, es la cara de URUKU con el comerciante. **Nunca corre WAHA** |
| **Marca** | 67991916 | Entel | eSIM iPhone, activa | El público. Va a la API oficial de Meta. **No registrarle WhatsApp común** |
| **Respaldo** | 68727584 | Entel | eSIM, sin activar | Está en los grupos callado. Toma el lugar del Registrador el día del baneo |
| **Explorador** | 68727944 | Entel | eSIM, sin activar | Sale a fotografiar ofertas |
| *(reserva)* | 72900149 | Entel | eSIM, sin activar | — |

### Por qué este reparto es el correcto

El único número que corre un cliente no oficial —el Registrador— **sólo
escucha**. Es lo más inofensivo que existe para WhatsApp, y si igual lo banean
no se pierde nada que no se recupere re-vinculando a un Respaldo que ya está
adentro de los grupos.

Todo lo que se *escribe* lo escribe una persona con la app de verdad: crear un
grupo, agregar gente, avisarle a un comerciante (desde el Samsung), publicar en
el canal (desde la tablet, que es la dueña). Un humano haciendo un grupo por día
es uso normal, no automatización.

**Por qué quedó así y no al revés (decidido el 11/9):** WAHA ya estaba vinculado
a la tablet y funcionando; moverlo al Tigo era re-vincular a cambio de nada
todavía. El costo que se asume a sabiendas: el canal vive en el número que corre
WAHA. Se cubre con un **segundo administrador desde el Tigo**, y con que WAHA
en sólo lectura sea lo más inofensivo que existe para WhatsApp.

### Lo que eso apaga en el sistema

Una sola llave, `WA_SOLO_LECTURA` (puesta por defecto), cierra las cuatro cosas
que escribían por WAHA:

| Antes | Ahora |
|---|---|
| El panel creaba el grupo por API | Se crea desde la tablet; el panel muestra los tres pasos |
| El panel agregaba respaldos a todos los grupos | Se agregan desde la tablet |
| Lo aprobado salía solo al canal | Se publica en el canal desde la tablet; la cola no lo encola |
| El aviso de cuota lo mandaba el Registrador al grupo | Lo da el Anfitrión desde el Samsung; la bandeja marca "AVISARLE" |

Facebook e Instagram **no** pasan por WAHA, así que siguen automáticos cuando
tengan token.

### El flujo de un grupo nuevo, a mano

1. En el Samsung (Tigo): grupo nuevo `URUKU · <nombre del local>`.
2. Agregar al comerciante y al **64610187** (el Registrador, la tablet).
3. Mandar adentro **`URUKU-XXXX`** — el código del local, que está en su ficha
   del admin y en el volante.

Con el código adentro, el Registrador lo ve y ata el grupo al comercio. Desde
ahí, todo lo que mande el comerciante se atribuye solo. **El código lo puede
mandar el Anfitrión** — hasta el 11/9 se descartaba por venir de un número
propio, y el grupo quedaba sin comercio hasta que lo mandara el comerciante.

### El bloque para `backend/.env` — definitivo

```
WA_NUMEROS_PROPIOS=59164610187,59167991916,59168727944,59175314737,59168727584
WA_NUMEROS_GRUPO=
WA_NUMEROS_EXPLORADOR=59168727944
WA_CONTACTO_EXPLORADOR=
BOT_WHATSAPP_NUMERO=59164610187
WA_CANAL_ID=
```

- `BOT_WHATSAPP_NUMERO` es **el del Registrador** (la tablet): recibe los
  `CONFIRMAR-XXXXXX` del login y los procesa el webhook. Se muda con WAHA.
- `WA_NUMEROS_GRUPO` vacío: no se crean grupos desde el sistema.
- `WA_CANAL_ID` vacío: el canal se publica a mano. El identificador es
  `120363412598489616@newsletter` por si algún día se enciende.
- `WA_SOLO_LECTURA` no hace falta ponerlo: es el valor por defecto.

**WAHA se queda en la tablet**, donde ya está vinculado desde el 11/9.

### Cambiar de aparato: la cuenta va con el número, no con el aparato

Un chip se pasa a otro aparato, se instala WhatsApp, llega el SMS, y la cuenta
está ahí: mismos grupos, misma condición de administrador, mismo canal. Lo que
NO viaja:

- **El historial de chats**, sin copia de seguridad. Al Registrador no le
  importa (todo está en la base); al Anfitrión sí — activar la copia en Google
  Drive en el Samsung.
- **Los dispositivos vinculados.** Registrar en un aparato nuevo desvincula
  todos. Cambiar la tablet = volver a vincular WAHA, y lo que llegue en esa
  ventana se pierde.
- **El PIN de dos pasos**, que te lo pide al registrar de nuevo. Sin él, 7 días
  de espera.

Chip roto o perdido: duplicado en Entel del mismo número, y lo de arriba. Con
el PIN de dos pasos puesto, nadie puede hacer ese trámite por vos y quedarse
con la cuenta.

**Lo que hay que hacer ahora, que son minutos:** PIN de dos pasos en los dos
números con correo de recuperación (`admin@uruku.bo`), copia de seguridad en el
Samsung, y la línea de la tablet con crédito o uso — una línea inactiva se
recicla, y con ella se va la cuenta.

### Los dos que quedaron afuera, y por qué

**59172900149 — NO USAR TODAVÍA. Se va a recuperar.** El número está activo pero
**la cuenta de WhatsApp la tiene otra persona**: es reciclado y quien lo tuvo
antes sigue con la sesión. Figuraba como Respaldo 2 en la versión anterior de
esta tabla. Si se lo hubiera puesto en `WA_NUMEROS_GRUPO`, el sistema habría
metido a un desconocido dentro de cada grupo de comerciante — con acceso a las
fotos, los precios y los teléfonos de todos. Es el peor error posible de esta
lista y no habría dado ningún aviso. Cómo recuperarlo, más abajo.

**+5491154574097 (personal, Argentina).** Tiene WhatsApp pero **la línea no está
en el teléfono**: la sesión sigue viva porque WhatsApp no necesita el chip
después de registrarse. Sirve para el día a día y **no debe usarse para ningún
rol de URUKU**: el día que esa sesión se cierre —cambio de teléfono, reinstalar
la app— no hay forma de recuperarla sin la línea.

### Cómo se reparte en los aparatos

WhatsApp permite **dos cuentas en la misma app**, así que con lo que hay alcanza
para los cinco roles sin comprar nada:

| Aparato | App | Cuenta |
|---|---|---|
| **Tablet** (oficina) | WhatsApp · cuenta 1 | **Operativo** — vinculado a WAHA |
| **Tablet** | WhatsApp · cuenta 2 | **Marca** — atiende compradores |
| **iPhone personal** | WhatsApp · cuenta 1 | el personal (no es de URUKU) |
| **iPhone personal** | WhatsApp · cuenta 2 | **Explorador** — sale a la calle |
| **El otro celular** | WhatsApp | **Respaldo 1** |
| — | — | **Respaldo 2**: se registra una vez y se guarda |

La marca va en la tablet y no en el celular: recibe compradores todo el día y
conviene que esté donde hay alguien sentado. El explorador va en el iPhone
porque es el que sale a la calle.

> **El iPhone tiene un límite:** guarda muchas eSIM pero sólo puede tener **dos
> activas a la vez**. Para registrar cada número de Entel hay que activarlo,
> recibir el código, y recién ahí cambiar a la siguiente. Una vez registrada, la
> cuenta de WhatsApp sigue funcionando sin la línea puesta.

### Cómo dar de alta las cuentas que faltan (8/9)

**Estado real:** de los cinco roles, sólo el operativo tiene WhatsApp. Los cuatro
números de Entel están como líneas en el iPhone y **ninguno tiene cuenta**.

El obstáculo aparente es que las cuatro eSIM viven en el iPhone y ahí sólo
entran dos cuentas de WhatsApp. Pero no hace falta que la cuenta viva donde está
el chip:

> **El código de verificación llega por SMS a la línea, y se puede tipear en
> otro aparato.** O sea: se activa la eSIM en el iPhone, se empieza el registro
> en la tablet, llega el SMS al iPhone, y el código se escribe en la tablet. La
> cuenta queda en la tablet.

Con eso, los cinco roles entran en los tres aparatos que ya hay.

**El orden, uno por vez** (el iPhone sólo admite **dos eSIM activas a la vez**,
así que se activa la que toca y después se pasa a la siguiente):

1. **Marca → la tablet.** Activar Entel 2 (`67991916`) en el iPhone. En la
   tablet, agregar segunda cuenta de WhatsApp y registrar ese número. El SMS
   llega al iPhone; el código se escribe en la tablet.
2. **Explorador → el iPhone.** Activar Entel 3 (`68727944`). Agregar la segunda
   cuenta ahí mismo. Va en el iPhone porque es el que sale a la calle.
3. **Respaldo 1 → el otro celular.** Registrar WhatsApp con `75314737`, que ya
   tiene el chip puesto ahí.
4. **Respaldo 2 → el otro celular, segunda cuenta.** Activar Entel 4
   (`68727584`) en el iPhone y escribir el código en el otro celular.
5. **Respaldo 3** → el `72900149`, cuando se recupere (abajo).

**Los respaldos hay que registrarlos ANTES de crear el primer grupo.** El
sistema los agrega solo a cada grupo, y a un número sin cuenta de WhatsApp no lo
puede agregar — el grupo se crea igual, sin ellos, y eso no se descubre hasta el
día del baneo.

> **Por qué conviene que cada cuenta quede en un aparato y no rotando:** una
> cuenta de WhatsApp vive en un teléfono principal. Si se registra un número en
> un slot y después se usa ese mismo slot para otro, el primero **queda sin
> dispositivo** — sigue existiendo y sigue adentro de los grupos, pero WhatsApp
> da de baja las cuentas que pasan mucho tiempo sin conectarse. Un respaldo que
> se dio de baja solo es un respaldo que no está el día que hace falta.

### Recuperar el 59172900149

Se quiere de vuelta, y se puede: **la línea es de URUKU**, así que el código de
verificación llega a nuestro chip. Registrar el número en un teléfono propio
saca la sesión del que la tiene — es cómo funciona WhatsApp con los números
reciclados, y el que lo tenía sabe que el número ya no es suyo.

Los pasos, con la eSIM activa en un teléfono:

1. Instalar WhatsApp (o agregar la segunda cuenta) y registrar `+591 72900149`.
2. Llega el SMS con el código y se completa.

**Lo que puede frenarlo:** si el que la tiene le puso *verificación en dos
pasos*, WhatsApp va a pedir un PIN de 6 dígitos que no tenemos. Ahí hay que
pedir el restablecimiento y **esperar hasta 7 días**. No hay atajo, y por eso
conviene empezarlo ahora y no el día que haga falta.

Cuando esté recuperado entra como **Respaldo 3**. Los respaldos son lo único que
salva el día del baneo, y tener tres en vez de dos no cuesta nada: no hacen
nada, sólo están adentro de los grupos. Ese día se agrega a `WA_NUMEROS_PROPIOS`
y a `WA_NUMEROS_GRUPO` — pero **sólo después** de verificar que la cuenta es
nuestra, abriendo el chat y viendo que sea una sesión nueva y vacía.

### Se cayó tres días y nadie se enteró (10–11/9)

WhatsApp desvinculó la tablet el 10/9 a las 23:27 (`conflict · device_removed`)
y del lado de URUKU no hubo ni un error: el sitio andaba, el panel andaba, y
no entraba una sola oferta. Se descubrió por casualidad, pidiendo el estado de
la sesión por curiosidad.

Ahora **Admin › WhatsApp muestra el estado de la sesión en grande y primero**,
en vivo, y el backend deja un `ERROR` en los registros cada cinco minutos
mientras no esté `WORKING`. No la arregla —eso pide una persona con la tablet
en la mano— pero el problema existe desde el primer minuto.

**Re-vincular sin el panel de WAHA** (no hace falta usuario ni contraseña):

```bash
cd /docker/uruku
# 1. Borrar la sesión muerta y crearla limpia
docker compose -f docker-compose.prod.yml exec -T waha \
  sh -c 'wget -qO- --method=DELETE --header="X-Api-Key: $WAHA_API_KEY" \
    http://localhost:3000/api/sessions/default'
docker compose -f docker-compose.prod.yml exec -T waha \
  sh -c 'wget -qO- --post-data="{\"name\":\"default\",\"start\":true}" \
    --header="Content-Type: application/json" --header="X-Api-Key: $WAHA_API_KEY" \
    http://localhost:3000/api/sessions'

# 2. Esperar a que diga SCAN_QR_CODE
docker compose -f docker-compose.prod.yml exec -T waha \
  sh -c 'wget -qO- --header="X-Api-Key: $WAHA_API_KEY" http://localhost:3000/api/sessions'

# 3. Con la tablet YA en "Vincular con número de teléfono", pedir el código
#    UNA sola vez — cada pedido nuevo invalida el anterior
docker compose -f docker-compose.prod.yml exec -T waha \
  sh -c 'wget -qO- --post-data="{\"phoneNumber\":\"59164610187\"}" \
    --header="Content-Type: application/json" --header="X-Api-Key: $WAHA_API_KEY" \
    http://localhost:3000/api/default/auth/request-code'
```

Se tipea el código en la tablet y se espera hasta un minuto. Si dice "no se
pudo vincular", lo primero es mirar los registros de WAHA
(`logs --since 5m waha`) y **Dispositivos vinculados** en la tablet: si hay
cuatro, no entra uno más; si hay uno viejo de WAHA, eliminarlo.

**Lo que se manda mientras está caída no se recupera.** No hay que contar con
que WhatsApp reenvíe lo perdido al reconectar.

### El riesgo del operativo en la tablet

WAHA se conecta como **dispositivo vinculado**, igual que WhatsApp Web, y un
vinculado deja de funcionar si el aparato principal —acá, la tablet— pasa **unos
catorce días sin conectarse**.

La tablet tiene chip propio, así que no depende del wifi de la oficina: eso ya
cubre la mitad del problema. Lo que queda es que **no se apague** ni se quede sin
saldo de datos dos semanas.

Si pasa, el canal se corta solo: no avisa, no da error, y desde el panel se ve
igual que "no llegó nada". Que quede enchufada, y abrirle WhatsApp cada tanto.
En **Admin › WhatsApp** se nota porque los mensajes dejan de aparecer.

Es la misma clase de falla que venimos persiguiendo: nada se rompe, todo parece
bien, y no entra nada. En **Admin › WhatsApp** se nota porque los mensajes dejan
de aparecer.

### El bloque para `backend/.env` — definitivo

Va tal cual en `/docker/uruku/backend/.env` del VPS. Son dos bloques porque hoy
sólo dos de los cinco números tienen cuenta de WhatsApp, y esa diferencia cambia
una línea.

**Hoy (8/9/2026), lo que hay que dejar puesto:**

```
WA_NUMEROS_PROPIOS=59164610187,59167991916,59168727944,59175314737,59168727584
WA_NUMEROS_GRUPO=59175314737
WA_NUMEROS_EXPLORADOR=59168727944
WA_CONTACTO_EXPLORADOR=
BOT_WHATSAPP_NUMERO=59164610187
```

**Cuando las cuatro eSIM de Entel tengan WhatsApp**, cambian dos líneas:

```
WA_NUMEROS_GRUPO=59175314737,59168727584
WA_CONTACTO_EXPLORADOR=59168727944
```

Por qué las dos listas no dicen lo mismo, que es lo que hace falta entender para
no romper nada:

- **`WA_NUMEROS_PROPIOS`** es una guarda de lectura: dice de qué números NO hay
  que tomar el contenido como oferta del comerciante. Puede llevar números sin
  WhatsApp sin ninguna consecuencia — el día que lo tengan, ya está cubierto. Es
  gratis y hay que ponerlos todos desde ahora. Si un número de URUKU falta acá,
  cualquier cosa que escriba en un grupo se publica como oferta del local.
- **`WA_NUMEROS_GRUPO`** es una acción de escritura: a cada uno de esos números
  el sistema lo mete adentro de cada grupo que crea. Un número sin cuenta de
  WhatsApp no se puede agregar a nada, así que ponerlo ahí no protege — hace
  fallar la creación del grupo delante del comerciante. Por eso hoy va uno solo.
- **`WA_CONTACTO_EXPLORADOR`** vacío es seguro y correcto: las consultas van al
  comercio, como siempre. Ponerlo apuntando a un número sin WhatsApp sería peor
  que dejarlo vacío — publicaría un contacto que no contesta.

**59172900149 no aparece en ninguna línea**, a propósito: hasta que la cuenta de
WhatsApp no sea nuestra, ponerlo ahí mete a un desconocido en los grupos. Se
agrega el día que se recupere.

Después de tocar el archivo hay que reiniciar el backend, y el arranque avisa
cuáles números descartó por inválidos (`config.wa_numero_invalido`). Un
placeholder tipo `591XXXXXXXX` se normaliza a `591` y apaga la guarda sin dar
error, así que esa línea del log es la que confirma que quedó bien.

## Los roles

| Rol | Qué hace | ¿En los grupos? | ¿Vinculado a WAHA? |
|---|---|---|---|
| **Marca** | El del sitio y los enlaces. Recibe **compradores** | **No** | No |
| **Operativo** | Captura todo Y le habla a los comerciantes | Sí, en todos | **Sí** |
| **Respaldo 1** | Callado. Espera el día del baneo | Sí, en todos | No |
| **Respaldo 2** | Igual | Sí, en todos | No |
| **Explorador** *(pendiente)* | Sale a **buscar** ofertas | No | A definir |

**Marca y operativo van separados** porque el primero recibe compradores todo el
día. Mezclarlo con cien grupos de comerciantes hace imposible atender los dos.

**El operativo captura y habla con el mismo número.** Se puede porque WhatsApp
marca como propios los mensajes del número vinculado, y la ingesta los descarta
(`payload.from_me`). Así una persona escribe "hola Juan, mandá las fotos acá" sin
que eso se convierta en una oferta.

**Los respaldos no mandan nada a la base** mientras no estén vinculados: WAHA
sólo captura a través de la cuenta que tiene vinculada. Están en los grupos por
una sola razón — que el día del baneo ya estén adentro.

## El explorador

Un celular de URUKU que sale a la calle a **fotografiar ofertas** de locales que
todavía no publican. Resuelve el arranque en frío: hay 813 comercios cargados y
una sola publicación. Igual que el mapa se llenó caminando, el feed se llena
caminando.

### Cómo se publica

El explorador manda la foto **con el código del local en el texto**:

    📷  URUKU-AQP5 zapatilla urbana Bs 180

Y eso se publica **a nombre del comercio real**, no de un comercio ficticio de
URUKU. La diferencia no es cosmética: una oferta firmada por "URUKU Ofertas" no
tiene pin en el mapa, ni horario, ni "a 240 m" — le saca al comprador lo único
que esta plataforma tiene y las otras no. Y publicar la foto y el precio de un
local bajo otro nombre le deja el reclamo al comerciante el día que el precio
cambie.

Lo que sí cambia es **a quién le escribe el comprador**: mientras el comercio no
se haya sumado, la consulta va al número explorador. El día que se suma, se
vacía `contacto_whatsapp` de sus publicaciones y pasan a su WhatsApp. Sin
migrar nada.

En la pantalla, la oferta aparece **entre las del local, como cualquier otra**,
con una sola marca: `URUKU`. Alcanza para que el comprador sepa a quién le
escribe, sin un párrafo explicando de dónde salió la foto — que además le
restaría a la oferta en vez de sumarle.

Y deja el mejor argumento de venta que hay: llegar al local y decirle *"tenés 12
consultas esperándote"*.

### La regla que lo hace funcionar: el código gana

Para un comerciante, el grupo (o su número) manda y el código sólo se mira si no
hay nada atado. Es correcto: su celular es siempre el mismo local.

**Para el explorador es al revés.** Un mismo teléfono publica para cien locales
en una tarde, así que el código de cada mensaje decide, siempre. Sin esa rama,
la segunda foto y todas las siguientes se habrían publicado bajo el comercio de
la primera — sin ningún error a la vista.

Dos cosas que NO hace, a propósito:

- **Sin código válido no publica nada.** Adivinar sería poner la foto y el
  precio de un local en la ficha de otro.
- **No ata el número del explorador a ningún comercio.** Ese vínculo es
  justamente lo que rompería la siguiente publicación.

Todo lo del explorador entra **siempre a moderación**, aunque el comercio sea
confiable: URUKU está publicando el precio de un local que no lo pidió, y la
cola es donde una persona lo mira.

### Quién es quién (asignación real, 31/8/2026)

| Número | Operadora | Rol | Dónde vive |
|---|---|---|---|
| **64610187** | **Tigo** | **Operativo** — se vincula a WAHA | Celular aparte (no el personal). Acá vive el canal |
| **75314737** | Entel *(a confirmar)* | **Respaldo 1** | eSIM en el celular personal |
| **72900149** | Entel | **Respaldo 2** | Cajón, sin usar |

> **Corregido el 6/9.** La tabla tenía el operativo y el respaldo 1 cruzados:
> decía que el Tigo era el 75314737. El Tigo es el **64610187**, y es el que
> está en el celular aparte. Se anota el error y no sólo el dato correcto
> porque el número equivocado ya había viajado a tres documentos y a los
> comandos de emparejado de más abajo: un dato mal copiado se propaga, y lo que
> lo frena es dejar dicho cuál era el equivocado.
>
> La intención del diseño **no cambia**: operativo en Tigo y respaldos en
> Entel, para que un problema de red o de portabilidad de Entel no se lleve
> puesto al operativo y a su reemplazo el mismo día. Lo que estaba mal eran los
> dígitos, no la idea.
| *(a comprar)* | — | **Marca** | El número público del sitio |
| *(a comprar)* | — | **Explorador** | El celular que sale a la calle |

El operativo es de **otra operadora que los dos respaldos**, a propósito: un
problema de red o de portabilidad de Entel no se lleva puesto al operativo y a
su reemplazo el mismo día.

Los respaldos van al cajón y **no se usan para nada**. Un número que además
manda mensajes personales se parece más a lo que Meta banea, y el respaldo tiene
que estar sano justo el día que haga falta.

El chip del explorador va en el celular que va a la calle. Si eso significa
sacar el 72900149 de ahí, mejor: pasa al cajón, que es donde tiene que estar un
respaldo.

## La configuración del explorador

```
WA_NUMEROS_EXPLORADOR=591EXPLORADOR
WA_CONTACTO_EXPLORADOR=591EXPLORADOR
```

El primero es quién puede publicar así; el segundo, a qué número van las
consultas. Suelen ser el mismo, pero se separan por si algún día conviene que
atienda otro.

`WA_CONTACTO_EXPLORADOR` vacío es seguro: las consultas van al comercio, como
siempre. Nunca se manda al comprador a un número que no está escuchando.

El explorador va **también** en `WA_NUMEROS_PROPIOS`, para que siga siendo
inofensivo el día que alguien lo agregue al grupo de un comerciante. Por eso su
rama corre ANTES del descarte por número propio: si corriera después, sus fotos
se tirarían como "mensaje de un número de URUKU".

## La configuración

En `backend/.env`:

```
WA_NUMEROS_PROPIOS=591XXXXXXXX,591YYYYYYYY,591ZZZZZZZZ
```

**Van TODOS los números de URUKU, incluido el operativo que está vinculado.**

Parece redundante —el vinculado ya se ignora por `from_me`— y es justamente lo
que hace seguro el reemplazo: **cuando WAHA se vincule a un respaldo, el
operativo viejo deja de ser "propio" y pasa a ser un participante más.** Si no
estuviera en esta lista, sus mensajes en los grupos empezarían a convertirse en
ofertas. La lista se arma una vez y sobrevive a cualquier cambio.

El número de la marca no hace falta (no entra a grupos), pero ponerlo no cuesta
nada y cubre el día que alguien lo agregue "para consultar algo".

## El grupo lo arma el sistema

En **Admin › el comercio › Grupo de WhatsApp** hay un botón que crea el grupo y
lo deja atado. Reemplaza cinco pasos manuales por comercio: crear, nombrar,
agregar al comerciante, agregar los respaldos, y mandar `URUKU-XXXX` adentro
para que la ingesta sepa de quién es.

Y hay algo mejor que ahorrar tiempo: **como el grupo lo crea el sistema, el
identificador vuelve en la respuesta y se ata en el mismo acto.** No existe la
ventana en la que un grupo está creado y todavía no se sabe de quién es — que es
justo cuando el comerciante manda su primera oferta.

Los respaldos que se agregan salen de `WA_NUMEROS_GRUPO` en `backend/.env`:

```
WA_NUMEROS_GRUPO=591RESPALDO1,591RESPALDO2
```

El operativo no va acá: es quien crea el grupo, así que ya queda adentro y como
administrador.

Si WhatsApp crea el grupo pero no devuelve su identificador, el panel avisa y
pide atarlo a mano. **No se devuelve un éxito falso**: un grupo creado y sin
atar deja al comerciante mandando ofertas al vacío.

El camino del código `URUKU-XXXX` sigue funcionando, para grupos que ya existen.

## Checklist: cada número, dónde va

Se escribe junto porque el día de configurarlo son cinco números, cinco
variables y una sola vinculación, y estaban repartidos en cuatro secciones de
este documento.

| Rol | Se empareja con WAHA | En los grupos | Variables donde va |
|---|---|---|---|
| **Marca** | No | No | ninguna (es el número público; el canal se carga en Admin › Contenido) |
| **Operativo** | **SÍ, el único** | Sí | `WA_NUMEROS_PROPIOS`, `BOT_WHATSAPP_NUMERO` |
| **Respaldo 1** | No | Sí | `WA_NUMEROS_PROPIOS`, `WA_NUMEROS_GRUPO` |
| **Respaldo 2** | No | Sí | `WA_NUMEROS_PROPIOS`, `WA_NUMEROS_GRUPO` |
| **Explorador** | No | No | `WA_NUMEROS_PROPIOS`, `WA_NUMEROS_EXPLORADOR`, `WA_CONTACTO_EXPLORADOR` |

**WAHA maneja UNA sola cuenta.** No hay nada que emparejar para los otros
cuatro: los respaldos están en los grupos para el día del baneo, el explorador
manda desde su propio teléfono y llega como cualquier remitente, y la marca ni
siquiera entra a los grupos.

**Todos van en `WA_NUMEROS_PROPIOS`, incluido el operativo que ya está
vinculado.** Parece redundante y es lo que hace seguro el reemplazo: cuando WAHA
se vincule a un respaldo, el operativo viejo pasa a ser un participante más, y
si no estuviera en la lista sus mensajes en los grupos empezarían a publicarse
como ofertas del comerciante.

### El bloque para `backend/.env`

```
# Sin placeholders: 591XXXXXXXX se normaliza a "591" y apaga la guarda sin
# dar ningún error. El arranque avisa cuáles descartó (config.wa_numero_invalido).
WA_NUMEROS_PROPIOS=591OPERATIVO,591RESPALDO1,591RESPALDO2,591EXPLORADOR,591MARCA
WA_NUMEROS_GRUPO=591RESPALDO1,591RESPALDO2
WA_NUMEROS_EXPLORADOR=591EXPLORADOR
WA_CONTACTO_EXPLORADOR=591EXPLORADOR
BOT_WHATSAPP_NUMERO=591OPERATIVO
```

`WA_CONTACTO_EXPLORADOR` vacío es seguro: las consultas van al comercio.
`WA_NUMEROS_GRUPO` no lleva al operativo: es quien crea el grupo, así que ya
queda adentro y como administrador.

### Emparejar el operativo (una vez)

Antes de crear ningún grupo. Verificar primero que `comercio_wa_grupos` esté en
0: una vez que haya cien grupos, el número nuevo no está en ninguno y hay que
agregarlo a mano uno por uno.

```bash
cd /docker/uruku
# ¿Hay grupos ya creados? Tiene que decir 0.
docker compose -f docker-compose.prod.yml exec -T postgres   psql -U postgres -d postgres -c "select count(*) from comercio_wa_grupos;"

# 1. Estado de la sesión
docker exec buscadonde-waha sh -c  'curl -s -H "X-Api-Key: $WAHA_API_KEY" localhost:3000/api/sessions'

# 2. Si no existe, crearla
docker exec buscadonde-waha sh -c  'curl -s -X POST -H "X-Api-Key: $WAHA_API_KEY" -H "Content-Type: application/json"   -d "{\"name\":\"default\",\"start\":true}" localhost:3000/api/sessions'

# 3. Con la sesión en SCAN_QR_CODE, pedir el código para el OPERATIVO
docker exec buscadonde-waha sh -c  'curl -s -X POST -H "X-Api-Key: $WAHA_API_KEY" -H "Content-Type: application/json"   -d "{\"phoneNumber\":\"59164610187\"}" localhost:3000/api/default/auth/request-code'
```

El código de 8 dígitos se ingresa en el teléfono: WhatsApp › Dispositivos
vinculados › Vincular con número de teléfono.

### Antes de dar por hecho que anda

En **Admin › WhatsApp** tiene que decir cuántos números propios están
configurados. Si dice 0, el `.env` no se leyó o quedaron placeholders — y con 0
cada mensaje que escriba alguien de URUKU dentro de un grupo se publica como
oferta del comerciante. Después, mandar una foto de prueba a un grupo atado y
verla aparecer en esa misma pantalla.

## Probarlo con dos teléfonos, antes de tener los cinco números

No hacen falta los cinco para saber si el canal funciona. El par mínimo es
**operativo + alguien que haga de comerciante**, y ese alguien puede ser el
celular personal de quien lo está probando.

### La trampa: el número que hace de comerciante NO va en `WA_NUMEROS_PROPIOS`

Es el error que más caro sale porque no se ve como error. Si el número de prueba
está en esa lista, cada foto que mande al grupo se descarta con "mensaje de un
número de URUKU" y la ingesta parece rota estando perfecta. La lista es de los
números **nuestros**; el que actúa de comerciante es de ellos.

### El `.env` para la prueba

Con un solo número real, todo lo demás vacío. Vacío es un estado válido y
seguro; con placeholders no.

```
WA_NUMEROS_PROPIOS=59164610187      # sólo el operativo por ahora
WA_NUMEROS_GRUPO=                   # vacío: los respaldos todavía no tienen WhatsApp
WA_NUMEROS_EXPLORADOR=
WA_CONTACTO_EXPLORADOR=
BOT_WHATSAPP_NUMERO=59164610187
```

`WA_NUMEROS_GRUPO` vacío hace que el grupo se cree sólo con el comerciante. Es
lo correcto mientras los respaldos no existan: pedirle a WhatsApp que agregue un
número que no tiene cuenta es cómo se consigue un grupo a medio armar.

### La secuencia

1. **`comercio_wa_grupos` en 0.** Si ya hay grupos, emparejar otro número
   significa agregarlo a mano a cada uno.
2. **Emparejar el Tigo** con WAHA (comandos arriba).
3. **Cargar el `.env` y reiniciar el backend.**
4. **Admin › WhatsApp tiene que decir `números propios: 1`.** Si dice 0, el
   `.env` no se leyó: no seguir, porque todo lo que venga después va a mentir.
5. **Crear un comercio de prueba** en el panel, con el número personal como su
   WhatsApp. De prueba y no uno real: el alta del grupo usa ese número, y
   pisarle el suyo a un comerciante de verdad lo saca de sus propias consultas.
6. **Crear el grupo desde la ficha** (Admin › el comercio › Grupo de WhatsApp).
   El grupo tiene que quedar atado en el mismo acto; si el panel avisa que no
   pudo, atarlo a mano antes de seguir.
7. **Mandar una foto con texto desde el personal, dentro del grupo.**
8. **Mirar Admin › WhatsApp.** Tiene que aparecer como *Publicada · a la cola de
   moderación*, y la misma foto en Publicaciones.

### Las tres pruebas que confirman las guardas

Pasan más desapercibidas que la principal, y son las que evitan publicar cosas
que no son ofertas:

- **Escribir desde el propio Tigo en el grupo.** No tiene que publicar nada
  (`fromMe`). En la bandeja no aparece o aparece como *Ignorada*.
- **Chat 1-a-1 desde el personal al Tigo, con `URUKU-XXXX` en el texto.** Tiene
  que publicar para ESE comercio, aunque el número no sea suyo: es el camino que
  le permite publicar a un comercio sin número propio.
- **Chat 1-a-1 sin código, desde un número desconocido.** Tiene que quedar como
  *No se supo de quién es*. Que NO publique es el acierto: adivinar sería poner
  la foto de un local en la ficha de otro.

### Los respaldos: antes de crear los cien grupos, no después

La prueba se puede hacer sin ellos. La operación no: una cuenta baneada no puede
agregar a nadie, así que los respaldos tienen que estar adentro de los grupos
desde el primer día. Un chip en el cajón sin teléfono no tiene WhatsApp, y un
número sin WhatsApp no se puede agregar a un grupo.

El orden ideal sigue siendo: probar con dos → dar de alta los respaldos → recién
ahí crear los grupos de verdad. Pero ya no es una puerta que se cierra: si los
grupos se crearon antes, **Admin › WhatsApp → "Agregar un número a los grupos"**
recorre los que ya existen y mete al respaldo. Va de a tandas chicas a propósito
—agregar un número a cien grupos seguidos es el patrón que dispara el baneo, y
el baneado sería el operativo— así que son varias corridas a lo largo de días.
Los grupos donde el número ya está se saltean solos, así que repetir no cuesta
nada.

WhatsApp permite dos cuentas en la misma aplicación, así que una de las eSIM de
Entel puede ser el respaldo 1 en el mismo celular personal sin comprar nada.

## El canal vive en el operativo, y eso hay que cubrirlo

El canal se creó el 6/9 desde el **64610187**, que es el mismo número que se
vincula a WAHA y va a estar dentro de los cien grupos de comerciantes.

Para los seguidores no cambia nada: un canal **nunca muestra el número de quien
lo administra**. El problema es otro y es el mismo que motiva todo este
documento: **el día que baneen esa cuenta se van el canal y los grupos juntos.**
Es el número más expuesto que tenemos, y ahora también tiene encima lo único que
le habla al comprador.

Lo que se puede hacer, y conviene hacerlo con el canal en cero seguidores:
**agregarle un segundo administrador** desde otra línea de URUKU (canal → tocar
el nombre → Administradores → Agregar). No hay garantía de que un canal
sobreviva al baneo de su creador, pero es la única palanca disponible y no
cuesta nada ahora. Con mil seguidores, rehacerlo sí cuesta.

Mover el canal a otro número más adelante no es directo, así que la decisión
práctica es dejarlo donde está y sumarle el segundo admin.

## El día que baneen el operativo

**Lo que NO se puede hacer:** que el sistema agregue un número nuevo a los
grupos. Una cuenta baneada no puede agregar a nadie, ni leer, ni nada — y WAHA
sólo maneja la cuenta que tiene vinculada. Por eso los respaldos se ponen ANTES.

Los pasos, que no tocan ningún grupo:

```bash
# 1. Borrar la sesión muerta
docker exec buscadonde-waha sh -c \
 'curl -s -X DELETE -H "X-Api-Key: $WAHA_API_KEY" localhost:3000/api/sessions/default'

# 2. Crearla de nuevo
docker exec buscadonde-waha sh -c \
 'curl -s -X POST -H "X-Api-Key: $WAHA_API_KEY" -H "Content-Type: application/json" \
  -d "{\"name\":\"default\",\"start\":true}" localhost:3000/api/sessions'

# 3. Emparejar con el RESPALDO (esperar a que quede en SCAN_QR_CODE)
docker exec buscadonde-waha sh -c \
 'curl -s -X POST -H "X-Api-Key: $WAHA_API_KEY" -H "Content-Type: application/json" \
  -d "{\"phoneNumber\":\"591RESPALDO\"}" localhost:3000/api/default/auth/request-code'
```

Y en `backend/.env`, `BOT_WHATSAPP_NUMERO` pasa a ser el respaldo — es el número
que aparece en los enlaces de "mandá CONFIRMAR-XXXXXX".

**Lo que NO hay que tocar:** `WA_NUMEROS_PROPIOS` ya los tiene a todos, así que
queda igual. Y los grupos siguen intactos: el respaldo ya estaba adentro.

Después del cambio, conseguir un respaldo nuevo y **agregarlo a los grupos**,
para volver a tener dos. Ése es el trabajo manual que queda, y se hace con
tiempo en vez de con el canal caído.

## A quién banean, y por qué a ése

La pregunta natural es si el riesgo está en los respaldos, que serían "los que
pasan los datos". No: **los respaldos no pasan nada.** WAHA lee sólo a través de
la única cuenta que tiene vinculada. Los respaldos entran al grupo y se quedan
callados — no publican, no capturan, no escriben. Esa inactividad es lo que los
mantiene sanos.

**El único expuesto es el operativo**, y no por recibir. Recibir es pasivo y de
bajo riesgo: un teléfono en cien grupos leyendo no le llama la atención a nadie.
Lo que sí, en orden de peso:

**Agregar gente a grupos.** Es el disparador número uno, y es exactamente lo que
hace el botón de crear grupo: mete a un comerciante que no lo pidió. Un par de
"reportar spam" seguidos alcanzan. Por eso el perfil tiene que decir **URUKU**
con el logo y no "Juan": la gente reporta al desconocido, no a la marca que
acaba de aceptar por la calle.

**Estar vinculado a un cliente no oficial.** WAHA se conecta como dispositivo
vinculado, igual que WhatsApp Web, pero automatizado. No es la API oficial de
Meta y esa diferencia existe.

**Mandar mensajes automáticos a desconocidos.** Es el patrón clásico. Hoy el
envío de códigos `CONFIRMAR-XXXXXX` sale por ahí; el código ya soporta los dos
proveedores y se cambia con `WHATSAPP_PROVIDER`.

La conclusión práctica: **el baneo cae sobre el número que crea grupos y
escribe**, no sobre los que miran. Y como ése es también el que tiene el canal
de difusión, ese día se pierden las tres cosas juntas si no hay un segundo
administrador puesto antes.

## Cómo bajar la chance de que pase

- **El operativo no manda mensajes masivos.** Recibir es pasivo y de bajo
  riesgo; mandar automáticamente a desconocidos es el patrón que dispara el
  baneo. Por eso el envío de códigos conviene moverlo a la API oficial de Meta
  (el código ya soporta los dos proveedores, se cambia con `WHATSAPP_PROVIDER`).
- **Ninguno de estos números se usa para nada más.** Un número que además manda
  cadenas y mensajes personales se parece más a lo que Meta banea.
- **Los grupos son chicos y reales**: cuatro participantes, con un comerciante
  de verdad del otro lado.
