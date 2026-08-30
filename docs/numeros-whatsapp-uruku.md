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

**Marca y operativo van separados** porque el primero recibe compradores todo el
día. Mezclarlo con cien grupos de comerciantes hace imposible atender los dos.

**El operativo captura y habla con el mismo número.** Se puede porque WhatsApp
marca como propios los mensajes del número vinculado, y la ingesta los descarta
(`payload.from_me`). Así una persona escribe "hola Juan, mandá las fotos acá" sin
que eso se convierta en una oferta.

**Los respaldos no mandan nada a la base** mientras no estén vinculados: WAHA
sólo captura a través de la cuenta que tiene vinculada. Están en los grupos por
una sola razón — que el día del baneo ya estén adentro.

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
