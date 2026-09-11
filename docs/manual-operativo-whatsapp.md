# Manual operativo — los teléfonos de URUKU

> Para quien tenga los aparatos en la mano. Qué hay que configurar en cada uno,
> qué no hay que hacer nunca, y qué hacer cuando algo se rompe. Versión del
> 11/9/2026.
>
> Si algo de acá no coincide con lo que ves en el aparato, gana el aparato —
> y avisá para corregir esto.

---

## 1. Los aparatos y sus roles

| Aparato | Número | Rol | En una frase |
|---|---|---|---|
| **Tablet** (chip físico Entel) | 64610187 | **Registrador** | Corre WAHA. Está en cada grupo y lleva lo que llega a la base. **Nunca escribe.** Es dueña del canal |
| **Samsung** (chip Tigo) | 75314737 | **Anfitrión** | Crea los grupos a mano, es admin de cada uno, habla con los comerciantes. **Nunca corre WAHA** |
| **iPhone** (eSIM Entel, activa) | 67991916 | **Marca** | El número público. Va a la API oficial de Meta. **No registrarle WhatsApp común** |
| iPhone (eSIM Entel, sin activar) | 68727584 | Respaldo | Está en los grupos callado. Reemplaza al Registrador si lo banean |
| iPhone (eSIM Entel, sin activar) | 68727944 | Explorador | Sale a fotografiar ofertas |
| iPhone (eSIM Entel, sin activar) | 72900149 | — | Reserva |

**La regla que ordena todo: la cuenta va con el número, no con el aparato.**
Cambiar de aparato es sacar el chip, ponerlo en otro, y verificar por SMS. Lo
que se pierde en el cambio está en la sección 6.

---

## 2. Configurar cada aparato

### 2.1 La tablet — Registrador (64610187)

Es la que corre WAHA. Su trabajo es **estar encendida, con red, y no hacer
nada más.**

- [ ] **Perfil de WhatsApp**: nombre `URUKU`, foto = el logo
      (`uruku.bo/logouruku.png`), info: `Ofertas y comercios de Bermejo · uruku.bo`.
      *Hecho el 11/9.*
- [ ] **PIN de verificación en dos pasos**: Ajustes → Cuenta → Verificación en
      dos pasos. Anotar el PIN en un lugar seguro. Correo de recuperación:
      `admin@uruku.bo`. Es lo que impide que alguien se quede con el número con
      un duplicado de chip, y lo que WhatsApp pide al cambiar de aparato.
- [ ] **Enchufada y con red, siempre.** El vínculo con WAHA muere si la tablet
      pasa ~14 días sin conectarse, y también se cae si se apaga mucho tiempo.
      Ayer se cayó sola. Ahorro de batería desactivado para WhatsApp.
- [ ] **Actualizaciones automáticas de WhatsApp** activadas. Una versión vieja
      falla al vincular.
- [ ] **Dispositivos vinculados**: tiene que haber UNO de WAHA. Si hay más de
      uno de WAHA, o cuatro en total, eliminar los que sobren.
- [ ] Nada más. No abrir chats, no contestar, no crear grupos desde acá. Todo
      lo que se escribe se escribe desde el Samsung.

**Lo que sí se hace desde la tablet, a mano:** publicar en el canal de
WhatsApp (es la dueña) y agregar administradores al canal.

### 2.2 El Samsung — Anfitrión (75314737)

Es la cara de URUKU con los comerciantes. Todo lo que se escribe, se escribe
desde acá.

- [ ] **Perfil de WhatsApp**: mismo nombre `URUKU`, mismo logo, misma info.
      El comerciante ve *"URUKU te añadió al grupo"* — si viera un nombre de
      persona, reporta como spam, y el reporte es lo que dispara el baneo.
- [ ] **PIN de dos pasos**, igual que la tablet.
- [ ] **Copia de seguridad en Google Drive**: Ajustes → Chats → Copia de
      seguridad, diaria. Acá viven las conversaciones con los comerciantes.
- [ ] **Segundo administrador del canal**: desde la tablet, canal → info →
      administradores → agregar el 75314737. Es lo que hace que el canal —con
      sus seguidores, lo único que no se rehace— sobreviva si se pierde la
      tablet.
- [ ] Guardar a la tablet en los contactos como `URUKU Registrador`.

### 2.3 El iPhone — Marca (67991916) y las eSIM sin activar

- [ ] **67991916: NO registrar WhatsApp.** Un número con WhatsApp común no se
      puede pasar a la API oficial sin darlo de baja. Es el único candidato
      limpio para ser el número de la marca. Se conecta a Meta cuando se haga el
      Plan B (sección 7).
- [ ] **Activar las tres eSIM** (68727584, 68727944, 72900149) con la
      operadora. Una línea inactiva no recibe el SMS de verificación.
- [ ] Después, registrar WhatsApp en el **Respaldo (68727584)** y el
      **Explorador (68727944)**. Son la segunda cuenta de WhatsApp del iPhone
      (WhatsApp permite dos).
- [ ] **Recuperar el 72900149**: puede que otra persona tenga la cuenta de
      WhatsApp de ese número. Registrarlo desde el iPhone lo saca de la cuenta
      anterior; si tiene PIN de dos pasos ajeno, son 7 días de espera.
- [ ] Todas las líneas **con crédito o uso**. La operadora recicla una línea
      inactiva, y con ella se va la cuenta de WhatsApp.

---

## 3. La operación de todos los días

### 3.1 Dar de alta un comercio en el canal de ofertas

Desde el **Samsung**:

1. Grupo nuevo: `URUKU · <nombre del local>`.
2. Agregar al comerciante y al **64610187** (la tablet).
3. Mandar adentro **`URUKU-XXXX`** — el código del local. Está en su ficha del
   admin y en el volante.

La tablet lo ve y ata el grupo al comercio. Desde ahí, todo lo que mande el
comerciante en ese grupo entra como oferta. En Admin › Negocios, la ficha del
comercio muestra el grupo atado.

**Antes de agregar al comerciante, avisarle**: *"te va a llegar una invitación
de URUKU a un grupo, es para que mandes tus ofertas"*. Un reporte evitado vale
más que cualquier cosa del código.

**Ritmo**: unos pocos grupos por día las primeras dos semanas. El número del
Samsung todavía no tiene historia, y cualquier reporte pesa más al principio.

### 3.2 Cuando llega una oferta

No hay que hacer nada en los teléfonos. Entra sola a **Admin › Publicaciones**,
ya revisada por la IA (lo dudoso arriba). Se aprueba o rechaza desde el panel.

### 3.3 Cuando un comercio llega al tope de su plan

**Admin › WhatsApp → "Hay que mirarlos"** muestra la oferta con el motivo
*"llegó al tope de N publicaciones · AVISARLE desde la tablet"*. El sistema no
le escribe solo (WAHA no escribe). Se le avisa desde el **Samsung**, en su
grupo, con las dos salidas:

> *Llegaste a las N publicaciones de tu plan. Las siguientes salen Bs 5, o
> pasás al plan Destacado y tenés 50 por mes. Avisanos y lo arreglamos.*

### 3.4 Publicar en el canal

Desde la **tablet** (es la dueña), a mano, **no más de cuatro por día**. Cada
publicación es una notificación en el teléfono de cada seguidor; con cincuenta
por día la gente lo silencia y no vuelve.

### 3.5 Lo que se mira cada mañana

**Admin › WhatsApp**, arriba de todo:

- 🟢 **WhatsApp conectado** — todo bien.
- 🔴 **WhatsApp caído** — no entra ninguna oferta. Ir a la sección 5.

---

## 4. Lo que no hay que hacer nunca

- **No mandar mensajes desde la tablet a nadie.** Ni "buen día", ni una
  respuesta. Todo lo que escriba en un grupo se descarta igual, pero es uso que
  WhatsApp mira.
- **No agregar gente a muchos grupos seguidos, ni crear muchos grupos en una
  tarde.** Es exactamente el patrón que dispara el baneo.
- **No poner WhatsApp común en el 67991916.**
- **No dejar la tablet apagada más de un par de días.**
- **No borrar el dispositivo vinculado de WAHA desde la tablet** sin avisar:
  es cortar la ingesta.
- **No pegar contraseñas, tokens ni PINs en ningún chat**, incluido éste.
- **No compartir el código `URUKU-XXXX` de un local con otro local.** Es lo
  que ata el grupo; con el código equivocado las ofertas van al comercio
  equivocado.

---

## 5. Contingencias — qué hacer cuando algo se rompe

### 5.1 🔴 El panel dice "WhatsApp caído"

**Qué pasa:** no entra ninguna oferta. Lo que manden mientras tanto **no se
recupera** después.

**Primero, la tablet:** ¿está encendida? ¿tiene red? ¿en *Dispositivos
vinculados* sigue apareciendo WAHA? Si desapareció, WhatsApp lo desvinculó y
hay que vincular de nuevo (5.2). Si sigue ahí, reiniciar la sesión:

```bash
cd /docker/uruku
docker compose -f docker-compose.prod.yml exec -T waha \
  sh -c 'wget -qO- --post-data="" --header="X-Api-Key: $WAHA_API_KEY" \
    http://localhost:3000/api/sessions/default/restart'
```

A los veinte segundos, el panel. Si sigue en rojo, los registros dicen por qué:

```bash
docker compose -f docker-compose.prod.yml logs --since 10m waha | grep -iE "error|fail|conflict|logged|401" | tail -15
```

- `conflict · device_removed` → desvinculado desde el teléfono. Ir a 5.2.
- `Connection Failure` justo después de vincular → WAHA quedó viejo. Ir a 5.3.

### 5.2 Volver a vincular WAHA (la tablet)

Sin usuario ni contraseña del panel de WAHA — con código:

```bash
cd /docker/uruku
docker compose -f docker-compose.prod.yml exec -T waha \
  sh -c 'wget -qO- --method=DELETE --header="X-Api-Key: $WAHA_API_KEY" \
    http://localhost:3000/api/sessions/default'
docker compose -f docker-compose.prod.yml exec -T waha \
  sh -c 'wget -qO- --post-data="{\"name\":\"default\",\"start\":true}" \
    --header="Content-Type: application/json" --header="X-Api-Key: $WAHA_API_KEY" \
    http://localhost:3000/api/sessions'
```

Diez segundos, y confirmar que dice `SCAN_QR_CODE`:

```bash
docker compose -f docker-compose.prod.yml exec -T waha \
  sh -c 'wget -qO- --header="X-Api-Key: $WAHA_API_KEY" http://localhost:3000/api/sessions'
```

En la tablet: WhatsApp → **Dispositivos vinculados → Vincular un dispositivo →
Vincular con número de teléfono**. Con esa pantalla abierta, pedir el código
**una sola vez** — cada pedido nuevo invalida el anterior:

```bash
docker compose -f docker-compose.prod.yml exec -T waha \
  sh -c 'wget -qO- --post-data="{\"phoneNumber\":\"59164610187\"}" \
    --header="Content-Type: application/json" --header="X-Api-Key: $WAHA_API_KEY" \
    http://localhost:3000/api/default/auth/request-code'
```

Tipear el código y esperar hasta un minuto. El panel tiene que pasar a 🟢.

**Si dice "no se pudo vincular":** en la tablet, *Dispositivos vinculados* —
si hay cuatro no entra uno más; si hay uno viejo de WAHA, eliminarlo. Y probar
5.3.

### 5.3 WAHA quedó viejo (WhatsApp cambió el protocolo)

```bash
cd /docker/uruku
docker compose -f docker-compose.prod.yml pull waha
docker compose -f docker-compose.prod.yml up -d waha
```

Un minuto, y volver a 5.2. El contenedor se reinicia; durante ese minuto no
entra nada. Es el mismo minuto que ya se perdió con la sesión caída.

### 5.4 Banearon la tablet (el Registrador)

**Qué pasa:** el número 64610187 deja de funcionar en WhatsApp, quizás para
siempre. Los grupos siguen existiendo — el Samsung es admin de todos. **El canal
sigue existiendo** sólo si el Samsung era administrador (sección 2.2). Si no, se
perdió con sus seguidores.

**Qué hacer:**

1. Elegir el reemplazo: el **Respaldo (68727584)**, que ya está en todos los
   grupos. Si no lo estaba, hay que agregarlo grupo por grupo desde el Samsung
   — de a pocos por día, no todos juntos.
2. Vincular WAHA al reemplazo (5.2, con su número en el pedido de código).
3. En `/docker/uruku/backend/.env`: `BOT_WHATSAPP_NUMERO=<el reemplazo>`, y
   levantar el backend.
4. Cambiar el perfil del reemplazo a `URUKU`.
5. Conseguir un Respaldo nuevo para los grupos, porque el que había ahora es
   el Registrador.

**Lo que NO se puede hacer:** apelar. WhatsApp no contesta. Y la prevención es
lo único que existe: la tablet sólo lee, y está en cada grupo con un respaldo
desde el primer día.

### 5.5 Banearon el Samsung (el Anfitrión)

Menos grave: la ingesta sigue (la tablet está en los grupos) y el canal es de
la tablet. Se pierde la capacidad de crear grupos nuevos y la administración de
los existentes.

1. Otro número pasa a ser Anfitrión — con perfil `URUKU`.
2. Los grupos existentes quedan sin admin de URUKU. **Por eso conviene que la
   tablet también sea admin de cada grupo** — al crearlo, promoverla.

### 5.6 Se rompió, se perdió o se robó un aparato

**La cuenta va con el número.** Chip sano: sacarlo, ponerlo en otro aparato,
instalar WhatsApp, verificar por SMS, PIN de dos pasos. Listo — mismos grupos,
mismo canal, misma condición de admin.

Después:

- Si era la **tablet**: vincular WAHA de nuevo (5.2). Registrar en un aparato
  nuevo desvincula todos los dispositivos.
- Si era el **Samsung**: restaurar la copia de Google Drive al instalar, para
  recuperar los chats.

**Chip perdido o roto:** duplicado en la operadora, mismo número. Con el PIN de
dos pasos puesto, nadie más puede hacer ese trámite y quedarse con la cuenta.

**Robado:** desde otro aparato, registrar el número (el PIN te lo permite a vos
y a nadie más). Eso cierra la sesión del aparato robado.

### 5.7 El Registrador muestra "Juan" u otro nombre

El perfil se cambió en la tablet pero WAHA muestra lo que tenía guardado. Se
actualiza al reconectar. Si no, 5.2.

### 5.8 Un comerciante manda ofertas y no aparecen

En orden:

1. **Admin › WhatsApp** — ¿🟢? Si no, 5.1.
2. **"Hay que mirarlos"** — ¿está ahí con motivo *"el grupo no está asociado a
   ningún comercio"*? El grupo no quedó atado: mandar el `URUKU-XXXX` adentro
   desde el Samsung.
3. ¿Motivo *"mensaje de un número de URUKU"*? Lo mandó alguien de URUKU, no el
   comerciante. Se descarta a propósito.
4. ¿Motivo *"llegó al tope"*? Sección 3.3.
5. ¿Aparece como **"Sin registrar"**? La ingesta se cortó a mitad de camino
   (la conexión con la base estaba muerta, pasa después de una hora sin
   mensajes). Debajo del mensaje hay un botón **Reprocesar**: lo vuelve a
   pasar por la ingesta como si acabara de llegar.
6. Si no aparece ni en "Todo": WAHA no lo recibió. Registros de WAHA (5.1).

---

## 6. Qué viaja y qué no al cambiar de aparato

| | Viaja con el número | Se pierde |
|---|---|---|
| Grupos, condición de admin | ✓ | |
| Canal (dueño y admins) | ✓ | |
| Historial de chats | | ✗ salvo copia en Google Drive |
| Dispositivos vinculados (WAHA) | | ✗ — hay que re-vincular |
| PIN de dos pasos | ✓ (te lo pide) | sin él, 7 días de espera |
| Perfil (nombre, foto) | ✓ | |

---

## 7. Plan B — la API oficial de Meta

Es a dónde va esto cuando el volumen lo pida: sin cliente no oficial, sin
dispositivo vinculado, sin regla de 14 días, sin baneo. **Ya está construido y
verificable desde el panel** — falta enchufarlo.

### 7.1 Lo que hay que saber antes

- **No tiene grupos.** Meta nunca los soportó en su API. El modelo de un grupo
  por comercio no migra: allá es chat uno a uno con cada comerciante. Los
  grupos de hoy no se transportan.
- **Recibir y contestar es gratis.** Se paga sólo por mensajes de marketing que
  inicia la empresa. Detalle en
  [whatsapp-arquitectura-y-escala.md](whatsapp-arquitectura-y-escala.md).
- **El número de la marca (67991916) es el candidato.** Un número con WhatsApp
  común no se puede pasar a la API sin darlo de baja: por eso no se le registra.

### 7.2 Probarlo con el número de prueba de Meta (media hora, sin tocar nada)

Meta regala un número de prueba: no se gasta ninguno nuestro.

1. `developers.facebook.com` → Crear app → *Otro* → **Negocio** → Agregar
   producto → **WhatsApp**.
2. Anotar: el **identificador del número** (`phone_number_id`), el **token
   temporal** (24 h) y la **clave secreta de la app** (Configuración → Básica).
   *No pegarlos en ningún chat.*
3. En *Para → Administrar lista*, registrar el 75314737 como destinatario de
   prueba.
4. En `/docker/uruku/backend/.env`:
   ```
   META_VERIFY_TOKEN=<una cadena que inventes>
   META_APP_SECRET=<la clave secreta>
   WHATSAPP_CLOUD_PHONE_ID=<el identificador>
   WHATSAPP_CLOUD_TOKEN=<el token>
   ```
   `WHATSAPP_PROVIDER` **se queda en `waha`**. Y levantar el backend.
5. En Meta, *WhatsApp → Configuración → Webhook*: URL
   `https://api.uruku.bo/ingest/webhook`, token de verificación el mismo del
   `.env`, **Verificar y guardar**. Después **suscribirse al campo `messages`**
   — sin esto la URL queda validada y no llega nunca nada.

### 7.3 Verificarlo — Admin › WhatsApp, tarjeta "Plan B"

Tres luces, y las tres tienen que estar:

1. **🟢 Token válido**, con el nombre y el número que Meta devuelve. Se
   comprueba solo, sin mandar nada. Si dice *"el token venció"*, rehacerlo en
   la consola (el temporal dura 24 h; para dejarlo fijo, un token de usuario de
   sistema).
2. **"Último mensaje recibido por la API oficial: hace N min"** — mandar un
   WhatsApp al número de prueba desde el Samsung y tiene que aparecer. Es la
   prueba de que **recibe**. Probar también **con una foto**: es el caso que no
   se puede dar por sentado.
3. **"Mandar un mensaje de prueba"** al 75314737 → llega al Samsung. Es la
   prueba de que **manda**. Va por Meta aunque el interruptor esté en WAHA.

Con las tres, el Plan B está probado y esperando.

### 7.4 El interruptor, el día que haga falta

```
WHATSAPP_PROVIDER=cloud_api
BOT_WHATSAPP_NUMERO=<el número de Meta>
```

Y levantar el backend. **Recibir por los dos lados sigue funcionando** — el
webhook acepta WAHA y Meta a la vez, así que el cambio no corta nada. Lo que
cambia es por dónde **sale** lo que se manda.

Para salir con un número propio (no el de prueba) hace falta la **verificación
del negocio en Meta**: trámite con documentación de la empresa, no plata.
Empezarlo ahora, aunque el cambio sea para dentro de meses.

---

## 8. Los comandos que más se usan

```bash
cd /docker/uruku

# Estado de la sesión de WAHA (o mirar Admin › WhatsApp)
docker compose -f docker-compose.prod.yml exec -T waha \
  sh -c 'wget -qO- --header="X-Api-Key: $WAHA_API_KEY" http://localhost:3000/api/sessions'

# Registros de WAHA, últimos 10 minutos
docker compose -f docker-compose.prod.yml logs --since 10m waha | tail -40

# Registros del backend: ¿qué pasó con las ofertas?
docker compose -f docker-compose.prod.yml logs --since 10m backend | grep -i "ingest\|wa_sesion"

# Versión en producción
curl -s https://uruku.bo/version

# Levantar después de tocar el .env
GIT_SHA=$(git rev-parse --short HEAD) APP_ENV=prod \
  docker compose -f docker-compose.prod.yml --env-file .env up -d --build backend
```
