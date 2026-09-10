# Que la oferta salga sola a las redes

> La oferta entra por el grupo de WhatsApp del comercio, se aprueba, y de ahí
> tiene que salir a las redes de URUKU sin que nadie copie y pegue. Copiar a
> mano a cuatro lugares es trabajo que se hace la primera semana y después no.

## Qué se puede automatizar y qué no

| Red | ¿Automático? | Por qué |
|---|---|---|
| **Canal de WhatsApp** | ✅ | Sale por WAHA, que ya está vinculado. No depende de nadie más. |
| **Facebook** | ✅ | API de Meta con el token de la página. |
| **Instagram** | ✅ | Misma API. Exige imagen y cuenta profesional vinculada a la página. |
| **TikTok** | ❌ | Su API de publicación pide una app auditada por TikTok y está pensada para video. |
| **YouTube** | ❌ | Sólo acepta video. |

**TikTok y YouTube se siguen subiendo a mano, y no es una limitación del
código.** Ponerlos en la lista para que fallen siempre en silencio sería peor
que no tenerlos: la cola diría "pendiente" para siempre y nadie sabría por qué.

## Cómo funciona

1. Llega la foto al grupo → la ingesta crea la publicación.
2. Queda **aprobada** — porque el comercio es confiable y publica directo, o
   porque un moderador la aprobó en el panel.
3. Ese momento **encola** la oferta para las tres redes. Encolar no manda nada
   y **nunca falla**: aprobar una oferta no puede romperse porque a Meta se le
   venció un token.
4. Los destinos marcados como automáticos salen solos. El resto espera un clic
   en **Admin › Difusión**.

Lo que sale lleva siempre el **nombre del comercio** y el **enlace a su ficha**.
Sin el nombre la oferta parece de URUKU y el comerciante no recibe nada de lo
que se le prometió; sin el enlace, quien la ve no tiene cómo llegar.

### Dos reglas que evitan el desastre

- **Sólo sale lo aprobado.** Una foto que nadie miró no puede aparecer en el
  muro de la marca: es un error que no se deshace, porque rechazarla después en
  el panel no la baja de Facebook.
- **Nada sale dos veces.** La cola tiene clave única por (publicación, red). Un
  reintento sobre algo que en realidad ya había salido —la llamada se cortó
  después de que el otro lado publicó— no duplica el posteo. Una oferta repetida
  en el mismo muro es de lo que más hace que la gente deje de seguir.

## Configurar cada destino

Todo va en `/docker/uruku/backend/.env`. **Un destino sin credencial no da
error: queda esperando en la cola**, y se manda el día que se configure.

### 1. Canal de WhatsApp — el más fácil y el que más rinde

El identificador del canal se le pregunta a WAHA:

```bash
curl -s -H "X-Api-Key: $WAHA_API_KEY" \
  http://localhost:3000/api/default/channels | head -40
```

Sale algo terminado en `@newsletter`. Ése es el valor:

```
WA_CANAL_ID=120363XXXXXXXXXXXX@newsletter
```

### 2. Facebook e Instagram — comparten token

Las dos salen por la misma API de Meta y usan **el token de la página**, no uno
personal. Son unos treinta minutos en la consola de Meta, una sola vez.

**Antes de empezar, dos requisitos que si faltan hacen fallar todo lo demás:**

- La cuenta de Instagram tiene que ser **profesional** (Empresa o Creador), no
  personal.
- Tiene que estar **vinculada a la página de Facebook** (Configuración de la
  página → Instagram → Conectar cuenta).

**Los pasos:**

1. `developers.facebook.com` → **Crear app** → tipo **Empresa**.
2. Abrir el **Explorador de la API Graph** (Herramientas → Graph API Explorer) y
   elegir la app recién creada.
3. Pedir permisos: `pages_show_list`, `pages_manage_posts`,
   `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`.
   Generar el token de usuario y aceptar en la ventana de Facebook.
4. **Convertirlo en uno largo** (el de la pantalla dura horas):
   ```
   GET /oauth/access_token?grant_type=fb_exchange_token
       &client_id=APP_ID&client_secret=APP_SECRET&fb_exchange_token=EL_TOKEN_CORTO
   ```
5. Con ese token largo, pedir las páginas:
   ```
   GET /me/accounts
   ```
   Devuelve el `id` de la página y su `access_token`. **Ese token de página no
   vence** mientras salga de un token de usuario largo — es el que va al `.env`.
6. El identificador de Instagram:
   ```
   GET /{ID_DE_LA_PAGINA}?fields=instagram_business_account
   ```

```
FACEBOOK_PAGE_ID=...
FACEBOOK_PAGE_TOKEN=...
INSTAGRAM_USER_ID=...
```

**El token se cae si cambiás la contraseña de Facebook** o si le sacás permisos
a la app. Cuando eso pase, la cola va a mostrar `HTTP 401` en el motivo: es la
señal de rehacer el paso 4.

### 3. Qué sale solo

```
DIFUSION_AUTO=wa_canal
```

Por defecto **sólo el canal de WhatsApp sale automático**, y es a propósito. Al
canal lo siguen personas que se anotaron para recibir ofertas: ahí una oferta
más es exactamente lo prometido. Un muro de Facebook con veinte ofertas por día
es cómo una página pierde alcance — el propio Facebook deja de mostrarla.

Cuando quieras que Facebook también salga solo:
`DIFUSION_AUTO=wa_canal,facebook`.

## Mirarlo: Admin › Difusión

Muestra cada envío, a qué red, con qué resultado y **el motivo del que falló**.
Un error invisible es una oferta que el comerciante espera ver y no aparece —
que es la forma más cara de perder a uno que ya había aceptado.

También muestra qué destinos están configurados. Sin eso, *"no se publica nada
en Facebook"* y *"se publica y falla"* se ven igual desde el panel, y se
arreglan de maneras opuestas: uno pegando un token, el otro leyendo el error.

## ¿Publicar en el canal puede hacer que baneen la cuenta?

Es la pregunta correcta, porque WAHA es automatización **no oficial** de
WhatsApp y todo lo que pase por ahí tiene algo de riesgo. Pero no todos los usos
son igual de riesgosos, y éste es de los más bajos.

**Por qué publicar en el canal es lo más seguro que hace WAHA acá:**

- **Los seguidores se anotaron.** Nadie recibe un mensaje que no pidió, y el
  disparador número uno del baneo es que la gente te reporte o te bloquee. En un
  canal eso casi no pasa: el que se cansa deja de seguirlo.
- **No abre conversaciones.** Un posteo al canal es una difusión, no cien chats
  nuevos con desconocidos — que es el patrón que WhatsApp persigue.
- **El volumen es bajo.** Unas pocas publicaciones por día.

**Lo que sí es riesgoso, y no es esto:** crear muchos grupos seguidos y agregar
números a muchos grupos seguidos. Esos dos sí disparan el baneo, y por eso el
botón de agregar respaldos va de a tandas chicas
([numeros-whatsapp-uruku.md](numeros-whatsapp-uruku.md)).

**Las ráfagas.** El único riesgo real del canal es publicar todo de golpe:
después de una tanda de moderación se aprueban veinte ofertas juntas, y veinte
publicaciones en cuatro segundos no se parecen a una persona con un teléfono. Va
resuelto en el código: el worker manda de a **5 por vuelta, con 20 segundos
entre cada una, cada 5 minutos**. Se regula sin tocar código:

```
DIFUSION_POR_TANDA=5
DIFUSION_PAUSA_SEG=20
DIFUSION_CADA_SEG=300
```

**El riesgo que sí hay que mirar no es el baneo: es la concentración.** El
operativo `64610187` es al mismo tiempo el vinculado a WAHA, el que está en
todos los grupos y **el dueño del canal**. Si cae, se caen las tres cosas
juntas. Publicar en el canal no mueve mucho esa aguja — pero la hace más cara.

Por eso hay una tarea que estaba anotada como deseable y ahora es necesaria:
**ponerle un segundo administrador al canal desde otra línea de URUKU**. Cuesta
dos minutos y es lo único que hace que el canal —con sus seguidores, que son lo
único que no se puede rehacer— sobreviva al día que baneen al operativo.

## Límites que conviene saber antes de chocarlos

- **Instagram: 50 publicaciones cada 24 horas.** Con el volumen de hoy sobra.
- **Instagram no publica sin imagen.** Una oferta que llegó sólo con texto se
  corta con ese motivo en vez de reintentarse contra un error que nunca va a
  cambiar.
- **La imagen tiene que estar en una URL pública.** Las nuestras lo están (las
  sirve el backend), pero si algún día las fotos pasan a un bucket privado, esto
  se rompe.
