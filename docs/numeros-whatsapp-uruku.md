# Los números de WhatsApp de URUKU

> Quién es quién en los grupos, cómo se configura, y qué hacer el día que
> baneen el testigo. Escrito antes de necesitarlo a propósito: ese día no hay
> tiempo de razonarlo.

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
| **75314737** | Tigo | **Operativo** — vinculado a WAHA | Teléfono fijo en la oficina, cargado |
| **64610187** | Entel | **Respaldo 1** | Cajón, sin usar |
| **72900149** | Entel | **Respaldo 2** | Cajón, sin usar |
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

## Cómo bajar la chance de que pase

- **El operativo no manda mensajes masivos.** Recibir es pasivo y de bajo
  riesgo; mandar automáticamente a desconocidos es el patrón que dispara el
  baneo. Por eso el envío de códigos conviene moverlo a la API oficial de Meta
  (el código ya soporta los dos proveedores, se cambia con `WHATSAPP_PROVIDER`).
- **Ninguno de estos números se usa para nada más.** Un número que además manda
  cadenas y mensajes personales se parece más a lo que Meta banea.
- **Los grupos son chicos y reales**: cuatro participantes, con un comerciante
  de verdad del otro lado.
