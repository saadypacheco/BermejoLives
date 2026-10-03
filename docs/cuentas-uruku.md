# Las cuentas de URUKU

> Dónde está cada perfil de la marca. Escrito porque no estaba: las redes se
> cargaron en el sitio y no quedaron anotadas en ningún archivo, y el día que
> hizo falta recordar la página de Facebook no había dónde mirar. Es lo mismo
> que pasó con los teléfonos — ver
> [numeros-whatsapp-uruku.md](numeros-whatsapp-uruku.md).

## Dónde vive el dato "de verdad"

Lo que el sitio muestra sale de la tabla `redes_sociales`, y se edita en
**uruku.bo/contenido** (rol publicador). Este archivo es la copia legible: sirve
para saber **qué cuentas existen y con qué usuario se administran**, que es
justo lo que la base no guarda.

Una red con la URL vacía **no se dibuja** en el sitio. No deja hueco ni da
error, así que una cuenta que existe y no está cargada acá es una cuenta que no
existe para el visitante.

## Las cuentas

**Estado verificado el 3/10/2026**, abriendo cada enlace del sitio con un
navegador (no con `curl`: las redes le contestan cualquier cosa a un robot).

| Red | Usuario / URL | En el sitio | ¿La cuenta existe? | Mail o teléfono |
|---|---|---|---|---|
| Facebook | `facebook.com/uruku.bo/` | ✅ | **Sí**, con descripción cargada | **NO ANOTADO** (cuelga de un perfil personal) |
| TikTok | `@uruku.bo` | ✅ | **Sí, pero vacía**: 0 videos, 1 seguidor | **NO ANOTADO** |
| YouTube | `@Uruku-Bermejo` | ✅ | **Sí** | **NO ANOTADO** (cuenta de Google) |
| Instagram | `@uruku.bo` | ✅ | **NO.** Contesta «Profile no está disponible» | — |
| Canal de WhatsApp | — | ❌ sin enlace | Creado el 6/9 en el operativo | Registrador `64610187` |
| Comunidad de WhatsApp | — | ❌ sin enlace | — | — |

> **El sitio manda a un Instagram que no existe.** El ícono está en la barra
> superior de TODAS las pantallas, y quien lo toca cae en «Profile no está
> disponible». Es peor que no tener Instagram: una marca que se presenta con un
> enlace roto se lee como una marca abandonada.
>
> Se apaga en diez segundos: **uruku.bo/contenido → Redes sociales → vaciar el
> campo de Instagram**. Una red con la URL vacía no se dibuja. Volver a
> cargarlo el día que la cuenta exista.

> **El handle de YouTube nombra una ciudad** (`@Uruku-Bermejo`). Es lo mismo que
> sacamos del título del sitio y de la imagen de compartir: con cuatro ciudades
> arrancando, la marca no puede presentarse como la de un pueblo. YouTube deja
> cambiarlo (una vez cada 14 días). El resto de las redes ya usan `uruku.bo`
> parejo, que es como tiene que ser.

> Tres de las cuatro redes existen y están publicadas. Lo que falta en esas
> tres no es crearlas: es saber **con qué cuenta se entra a cada una**, que es
> exactamente el dato que la base no guarda y que este archivo venía pidiendo
> desde que se escribió.

## Cómo averiguar el mail/teléfono de cada una (2 minutos cada una)

Hay que hacerlo desde el teléfono donde la sesión siga abierta. **Hacelo antes
de entregarle nada a nadie**: si la sesión se cierra y no sabés el mail, la
cuenta se perdió — el handle `@uruku.bo` queda tomado y no se puede volver a
registrar.

| Red | Dónde mirar |
|---|---|
| **TikTok** | Perfil → ☰ → Configuración y privacidad → **Administrar cuenta**. Ahí salen el teléfono y el correo. |
| **Instagram** | Perfil → ☰ → **Centro de cuentas** → Datos personales → Información de contacto. |
| **YouTube** | El canal pertenece a una cuenta de Google: youtube.com → foto arriba a la derecha → el mail está ahí mismo. |
| **Facebook** | La página cuelga de un **perfil personal**. En Meta Business Suite → Configuración → **Personas**, figura quién es admin. |

Anotá cada uno en la tabla de arriba apenas lo veas.

> **Facebook:** apareció el 10/9. La URL es `https://www.facebook.com/uruku.bo/`
> — el mismo handle que TikTok e Instagram, que es como tiene que ser: una
> marca con tres nombres distintos no se busca, se pierde.

**Anotar quién la administra no es burocracia.** Una página de Facebook o un
canal de WhatsApp pertenecen a una cuenta personal, no a la empresa: el día que
esa persona no esté, o pierda el teléfono, la cuenta se va con ella. Es el mismo
riesgo que tiene el canal de WhatsApp por vivir en el operativo, y se cubre
igual — con un segundo administrador.

## Google Workspace

El dominio `uruku.bo` tiene Workspace contratado. Se administra en
`admin.google.com`.

| Qué | Valor |
|---|---|
| Cuenta principal (administrador) | `admin@uruku.bo` |
| A nombre de | Saady Horacio Pacheco Villarroel |
| Unidad organizativa | URUKU |
| Creada | 14/8/2026 |

**Alias de `admin@uruku.bo`** (vistos el 8/9/2026): `info@`, `contacto@`,
`comercios@`, `ventas@`. La pantalla seguía hacia abajo, así que puede haber
más — la lista completa está en Usuarios → el usuario → *Direcciones de correo
electrónico alternativas*.

**Un alias no es una casilla.** Es la trampa de esto y conviene tenerla clara
antes de repartir direcciones: el correo que llega a `ventas@uruku.bo` cae en la
bandeja de `admin@uruku.bo`, y **con el alias no se puede iniciar sesión**. Sirve
para publicar una dirección linda en el sitio o en Facebook; no sirve para
darle acceso a otra persona ni para separar bandejas. Eso necesita un usuario
de verdad, que sí cuesta licencia. Los alias son gratis y se pueden tener hasta
30.

**Ojo con los usuarios del panel de URUKU.** `admin@uruku.bo`,
`agente@uruku.bo` y `publicador@uruku.bo` aparecen en
[deploy-prod-nuevo-vps.md](deploy-prod-nuevo-vps.md) como usuarios del backend:
son **otra cosa**, no cuentas de Google. Comparten el nombre y nada más — el
backend los valida contra su propio `.env`, no contra Workspace. Cambiar la
contraseña en Google no cambia la del panel, y al revés tampoco.

## Qué falta

- [ ] **Apagar el enlace de Instagram** en `/contenido` hasta que la cuenta
      exista. Hoy el sitio manda a una pantalla de error desde todas sus
      pantallas.
- [ ] **Decidir qué pasa con Instagram.** Dos caminos, y conviene saber en cuál
      se está antes de perder una tarde:
      - Si el handle `uruku.bo` **está libre** al intentar registrarlo, la
        cuenta nunca llegó a existir o se borró: se crea de cero, con el mail de
        Workspace y doble factor desde el principio.
      - Si está **tomado**, la cuenta existe y está desactivada o inhabilitada:
        se recupera por instagram.com/accounts/login → «¿Olvidaste la
        contraseña?», probando los mails de Workspace y los teléfonos de URUKU.
        No se puede crear otra con ese nombre.
- [ ] **Cambiar el handle de YouTube** a uno sin ciudad.
- [ ] **Publicar algo en TikTok.** La cuenta existe y está en cero; un perfil
      vacío enlazado desde el sitio tiene el mismo problema que el enlace roto,
      más suave.
- [ ] Configurar la **difusión automática** a las redes. Los pasos y los
      tokens, en [difusion-redes.md](difusion-redes.md).
- [ ] Cargar el **canal de WhatsApp** en `/contenido`. Está creado en el
      operativo (6/9); sin el enlace, la sección del home que le habla al
      comprador —"Enterate antes que nadie"— **no se dibuja**.
- [ ] Ponerle un **segundo administrador** al canal desde otra línea de URUKU.
- [ ] Completar en la tabla de arriba con qué cuenta se administra cada red.
- [ ] Anotar **con qué cuenta personal** se administra la página de Facebook.
      El día que esa persona no esté, la página se va con ella.

---

# Entregarle las redes a quien va a hacer el contenido

> Escrito el 1/10/2026. El error que hay que no cometer: pasar usuario y
> contraseña por WhatsApp. Eso no es «dar acceso», es **regalar la cuenta** —
> queda en un chat para siempre, no se puede quitar sin cambiar la clave, y si
> la persona se va, se va con todo.
>
> Las cuatro redes tienen forma de sumar a alguien **como colaborador**, que se
> quita con un clic. Es más trabajo hoy y es la diferencia entre prestar una
> llave y entregar la casa.

## 1. Antes de entregar nada

- [ ] Completar la tabla de arriba: **el mail de cada red**. Si la sesión se
      cierra y nadie sabe el mail, la cuenta está perdida — y el handle
      `@uruku.bo` queda tomado, así que no se puede volver a registrar.
- [ ] Poner **doble factor** en las cuatro, con un teléfono de URUKU.
- [ ] Guardar los mails y las claves en un **gestor de contraseñas**
      (Bitwarden, 1Password). Nunca en un chat, nunca en este repo.

## 2. Cómo se suma a alguien, red por red

| Red | Cómo | Qué queda en su poder |
|---|---|---|
| **Facebook** | Meta Business Suite → Configuración → **Personas** → Agregar. Rol *Editor*. | Publicar. **No** puede sacar a nadie ni borrar la página. |
| **Instagram** | Hay que pasarla a **cuenta profesional** y vincularla a la página de Facebook. Desde ahí se maneja con el mismo permiso de arriba. | Ídem. |
| **TikTok** | No tiene roles. Se usa **TikTok Business Center** → Miembros, o se comparte la cuenta. | Si no hay Business Center, se comparte la clave: cambiarla el día que se vaya. |
| **YouTube** | El canal tiene que estar en una **cuenta de marca** para poder sumar administradores sin dar el Google. Si no lo está, se puede pasar. | Subir y editar videos. |

**Instagram y TikTok son los dos flojos.** Instagram se arregla pasándola a
profesional (hay que hacerlo igual para la difusión automática, ver
[difusion-redes.md](difusion-redes.md)). TikTok no tiene permisos finos: o
Business Center, o la clave.

## 3. El correo

**Un alias no sirve para esto.** `contenido@uruku.bo` como alias recibe mail en
la bandeja de `admin@uruku.bo` y **no puede iniciar sesión**. Para que la
persona tenga su propia bandeja hacen falta dos cosas, y hay que elegir:

| Opción | Costo | Cuándo conviene |
|---|---|---|
| **Usuario real** `contenido@uruku.bo` en Workspace | una licencia más | Si va a quedarse. Las cuentas que abra quedan a nombre de URUKU. |
| Su **mail personal** como colaborador | gratis | Para probar las primeras semanas. |

Lo que **no** hay que hacer nunca: darle `admin@uruku.bo`. Esa cuenta es dueña
del dominio, del Workspace y de todo lo demás.

## 4. El panel de URUKU

No se le da la clave de admin. Desde la **migración 0126** los permisos son por
rol y se arman desde el panel: **Admin → Equipo → Roles → crear rol**.

Para contenido alcanza con:

| Permiso | Para qué |
|---|---|
| `contenido` | Cotización, estado de la frontera, videos y redes |
| `difusion` | Publicar en las redes de URUKU |
| `datos` | *(opcional)* ver si lo que publica trae gente |

Y después **Admin → Equipo → crear usuario** con ese rol. Si se va, se desactiva
el usuario y listo: no hay ninguna clave que cambiar.

## 5. Lo que hay que entregarle además de los accesos

- El **guion de marca**: qué es URUKU y para quién (ver
  [estrategia-marca-uruku.md](estrategia-marca-uruku.md)).
- Que el handle es **`@uruku.bo` en las cuatro**, igual en todas. Una marca con
  tres nombres distintos no se busca: se pierde.
- El dato que nadie más tiene: **qué busca la gente en Bermejo**, en
  Admin → KPIs. Es de dónde salen los temas que a alguien le importan.
