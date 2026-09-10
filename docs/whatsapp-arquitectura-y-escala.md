# La capa de WhatsApp: cómo está, cómo debería estar, y qué pasa al crecer

> Escrito el 10/9 porque el diseño que estaba en la cabeza y el que está en el
> código **no son el mismo**, y la diferencia importa el día que banean una
> cuenta.

## Los tres trabajos, que hoy hace un solo número

En la capa de WhatsApp pasan tres cosas distintas, con riesgos muy distintos:

| Trabajo | Qué hace | Riesgo de baneo |
|---|---|---|
| **Crear grupos y agregar gente** | Arma el grupo de cada comercio | **Alto** — es la operación que WhatsApp castiga |
| **Escuchar y llevar a la base** | Recibe los mensajes y los guarda (WAHA) | **Bajo** — es pasivo |
| **El canal** | Publica las ofertas a los seguidores | Bajo, pero **es lo único irrecuperable** |

**Hoy los tres los hace el `64610187`.** Un baneo se lleva las tres cosas de una
vez: se pierde el vínculo con los grupos, se corta la ingesta y **desaparece el
canal con sus seguidores**, que es lo único que no se puede rehacer.

### El diseño correcto separa el primero de los otros dos

La idea de tener el creador de grupos aparte del número de WAHA es **la
correcta**, y por una razón concreta: el que crea grupos y agrega gente es el
que se expone, y no tiene por qué ser el mismo que sostiene la ingesta.

Cada grupo queda con tres números, como corresponde:

1. **El operativo** — creó el grupo. Es la cara con la que habla el comerciante.
2. **El comerciante.**
3. **El número de WAHA** — no habla; escucha y lleva a la base.

Más los **respaldos** adentro, que son los que toman el lugar de WAHA si lo
banean, sin tener que rehacer un solo grupo.

**Lo que hay que corregir de cómo lo estabas nombrando:** los respaldos (o
"testigos") **no llevan nada a la base**. Sólo la cuenta vinculada a WAHA lo
hace, y es una sola. Los respaldos están adentro para poder *tomar ese lugar* el
día del baneo. Por eso su cantidad **no cambia el rendimiento en nada**, y por
eso conviene que sean **dos, no más**: cada uno hay que agregarlo a todos los
grupos —que es la operación riesgosa— y cada uno es alguien más con acceso a las
fotos, precios y teléfonos de todos los comercios.

### Lo que cuesta separarlos, dicho con honestidad

Hoy **el grupo lo crea WAHA por API**, y de ahí sale gratis el vínculo grupo →
comercio: el identificador vuelve en la respuesta y se ata solo. Si el grupo lo
crea a mano otro teléfono, ese regalo se pierde: hay que volver a la
identificación por código (`URUKU-XXXX`), que ya existe y funciona, pero que
depende de que alguien mande el código adentro del grupo.

Son dos costos reales contra un beneficio real. **La recomendación**: separarlo
recién cuando el volumen lo justifique, y mientras tanto sacar del `64610187` lo
único que de verdad no se puede perder — **el canal**, poniéndole un segundo
administrador (dos minutos, ningún costo).

## Qué pasa al crecer: los números no cierran

La expectativa es 20.000 a 50.000 comercios. **Un teléfono no llega, y no por
poco.**

Mucho antes del baneo se rompe otra cosa: la aplicación y WAHA **sincronizan el
historial de todos los chats**. Con miles de grupos la sesión se vuelve lenta y
empieza a perder mensajes. El límite práctico está en cientos, tal vez un par de
miles con dolor. Nunca en veinte mil.

**Un operativo por ciudad es correcto y hay que hacerlo** —WAHA soporta varias
sesiones, una por número— pero no alcanza solo: 50.000 comercios entre diez
ciudades siguen siendo 5.000 grupos por teléfono.

### El plan por etapas

| Etapa | Comercios | Cómo |
|---|---|---|
| Hoy | hasta ~300 | WAHA + un grupo por comercio, todo en Bermejo |
| Segunda ciudad | ~1.000 | Una sesión de WAHA por ciudad |
| Crecimiento | miles | **Chat directo** en vez de grupo |
| Volumen real | 20.000+ | **API oficial de Meta** |

## La API oficial: lo que hay que saber ANTES de contar con ella

### No tiene grupos. Nunca los tuvo.

Meta jamás soportó grupos en su API de negocios. O sea que **el modelo de "un
grupo por comercio" no migra**: allá es conversación uno a uno con cada
comerciante.

No es mala noticia, pero cambia la planificación:

- La atribución por **número de remitente** ya existe y es más confiable que la
  del código.
- Un chat directo pesa muchísimo menos que un grupo en la sesión.
- No hay que agregar a nadie a nada — que es justo lo que dispara los baneos.
- Los respaldos dejan de tener sentido: **en la API oficial no hay cuenta que
  banear**.

**Y hay una consecuencia que conviene tener presente desde hoy: cada grupo que
se crea ahora es trabajo que no se transporta.** No es razón para no crearlos —
sirven hoy— pero sí para no invertir meses en un modelo que se va a dejar.

### Los costos

La estructura de precios de Meta, que es lo que importa para decidir:

- **Conversaciones que inicia el usuario ("de servicio"): gratis.** Te escriben
  y contestás, sin cargo. **Es exactamente el modelo de URUKU**: el comerciante
  manda la foto, el sistema responde.
- **Plantillas de utilidad** (avisos transaccionales: "llegaste a tu cuota"):
  gratis dentro de la ventana de atención abierta.
- **Plantillas de marketing** (vos iniciás para promocionar): **se pagan por
  mensaje**, con tarifa por país.

**No pongo acá el precio de Bolivia porque cambia y no lo voy a inventar.** Se
lee en la página de precios de Meta para desarrolladores, y hay que mirarlo
antes de presupuestar cualquier campaña.

**La conclusión práctica**: para recibir ofertas y contestarlas, la API oficial
sale prácticamente lo mismo que WAHA —nada— y sin riesgo de baneo. Lo que cuesta
plata es mandar promociones masivas, que es una decisión aparte.

Lo demás que cuesta no es plata sino trámite: **verificación del negocio en
Meta**, que pide documentación de la empresa.

## Lo que ya está listo para ese día (10/9)

La capa de mensajería está construida y probada, así que la migración es
configuración y no una reescritura:

- **`app/services/mensajeria.py`** — una sola puerta para mandar y recibir. El
  proveedor se elige con `WHATSAPP_PROVIDER=waha|cloud_api`.
- **Lo que entra por Meta se traduce a la forma de WAHA en la puerta**, así la
  ingesta —con todas las reglas de atribución, códigos, números propios,
  explorador y cuotas— queda intacta y con una sola implementación.
- **El webhook acepta las dos firmas**: `X-Webhook-Hmac` (WAHA, SHA-512) y
  `X-Hub-Signature-256` (Meta, con el App Secret). Son cabeceras, algoritmos y
  claves distintas.
- **El `GET` de verificación que Meta exige** para dar de alta la URL. Sin él no
  se puede ni configurar, y el error de la consola de Meta no dice que falta.
- **Las tandas de varios mensajes** se procesan una por una. Meta agrupa, y
  quedarse con el primero pierde el resto en silencio.
- **Las fotos de Meta** llegan como identificador, no como URL: se canjean con
  el token en dos llamadas.

Cubierto por `backend/tests/test_mensajeria_cloud.py`. Hoy no entra ni un
mensaje por Meta, así que esos tests son lo único que evita que esta traducción
se pudra sin que nadie se entere.

### Probar la API oficial de Meta con el número de prueba

> Media hora. No toca nada de lo que funciona hoy: WAHA sigue igual, y el
> número de prueba lo pone Meta —no se gasta ninguno de los nuestros.

#### Lo que hay que saber antes de empezar

- **El número de prueba sólo le puede escribir a 5 teléfonos**, que hay que
  registrar a mano. Para recibir no hay límite: cualquiera puede escribirle.
- **El token que muestra la pantalla dura 24 horas.** Para la prueba alcanza. Si
  después se quiere dejar andando, se cambia por uno de usuario de sistema.
- **No hace falta verificación del negocio** para probar. Eso recién se pide
  para salir a producción con un número propio.

#### 1. Crear la app (5 minutos)

1. `developers.facebook.com` → **Mis apps** → **Crear app**.
2. Cuando pregunta qué querés hacer, elegir **Otro** → tipo **Negocio**.
3. Nombre: `URUKU`. Se asocia a tu cuenta de Meta Business.
4. En el panel de la app: **Agregar producto** → **WhatsApp** → *Configurar*.

Meta arma sola una cuenta de WhatsApp Business de prueba y te da el número.

#### 2. Anotar los tres datos

En **WhatsApp → Configuración de la API**:

- **Identificador del número de teléfono** (`phone_number_id`) — un número
  largo. **No es el teléfono**, es su identificador interno.
- **Token de acceso temporal** — el de 24 horas.

En **Configuración → Básica** (del menú de la izquierda):

- **Clave secreta de la app** (App Secret) → botón *Mostrar*.

> No los pegues acá en el chat. Van directo al `.env` del servidor.

#### 3. Registrar tu teléfono como destinatario

En la misma pantalla de la API, en **Para**: *Administrar lista de números de
teléfono* → agregar tu número personal → llega un código → confirmarlo.

Sin esto el número de prueba no te puede contestar.

#### 4. Poner las variables en el servidor

En `/docker/uruku/backend/.env`:

```
META_VERIFY_TOKEN=uruku-prueba-2026        # la inventás vos, cualquier cadena
META_APP_SECRET=<la clave secreta de la app>
WHATSAPP_CLOUD_PHONE_ID=<el identificador del número>
WHATSAPP_CLOUD_TOKEN=<el token temporal>
```

**`WHATSAPP_PROVIDER` se queda en `waha`.** Esa variable sólo decide por dónde
*sale* lo que mandamos; recibir por los dos lados a la vez no rompe nada.

Y reiniciar el backend:

```bash
cd /docker/uruku
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=prod \
  docker compose -f docker-compose.prod.yml --env-file .env up -d --build backend
```

#### 5. Enganchar el webhook

De vuelta en **WhatsApp → Configuración** → sección *Webhook* → **Editar**:

- **URL de devolución de llamada**: `https://api.uruku.bo/ingest/webhook`
  ← con **`api.`**. `uruku.bo` es el sitio y ahí da 404.
- **Token de verificación**: el mismo `META_VERIFY_TOKEN` de arriba.
- **Verificar y guardar**.

Si dice que no pudo validar la URL: el backend no levantó con la variable nueva,
o el token no coincide. Se ve en el registro — busca `webhook.verificacion_rechazada`.

Después, **Administrar** → suscribirse al campo **`messages`**. Es el paso que
más se olvida: sin él la URL queda validada y **no llega nunca nada**.

#### 6. Probarlo

Escribile un WhatsApp al número de prueba desde tu teléfono. Dos cosas tienen
que pasar:

1. Aparece en **Admin › WhatsApp**, en la bandeja, igual que los de WAHA.
2. En el registro del backend:

```bash
docker compose -f docker-compose.prod.yml logs --tail 50 backend | grep -i "ingest\|webhook"
```

Probá también **mandando una foto con texto**: es el caso que de verdad importa,
porque en la API oficial la imagen no viene con URL sino con un identificador
que hay que canjear con el token. Si la foto queda guardada, la parte más
delicada de la traducción funciona.

#### 7. Medir lo que viniste a medir

Con eso andando ya se puede saber, con datos propios y no con estimaciones:

- **Cuánto tarda** un mensaje desde que se manda hasta que está en la base,
  comparado con WAHA.
- **Cuánto cobra Meta**: en el panel de la app, *Estadísticas* → conversaciones.
  Las que inicia el usuario tienen que aparecer en cero.
- **Si la foto entra bien**, que es lo único que no se puede dar por sentado.

#### Cuando termines la prueba

El token vence solo a las 24 horas y deja de entrar. Si querés cortar antes,
sacá `META_APP_SECRET` del `.env` y reiniciá: sin esa clave las firmas de Meta
no validan y el webhook las rechaza.

**No borres la app de Meta.** Sirve igual para el asistente 24/7 y para publicar
en Facebook e Instagram — es la misma app.
