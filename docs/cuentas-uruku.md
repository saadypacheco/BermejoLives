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

| Red | Usuario / URL | Cargada en /contenido | Quién la administra |
|---|---|---|---|
| TikTok | `@uruku.bo` | ✅ | *(completar)* |
| Instagram | `@uruku.bo` | ✅ | *(completar)* |
| YouTube | `@Uruku-Bermejo` | ✅ | *(completar)* |
| Facebook | `facebook.com/uruku.bo` | ❌ | *(completar)* |
| Canal de WhatsApp | *(completar)* | ❌ | Operativo `64610187` |

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

- [ ] Cargar la **página de Facebook** en `/contenido`. La URL ya está
      (arriba); falta pegarla, y sin eso el ícono no se dibuja en el sitio.
- [ ] Configurar la **difusión automática** a las redes. Los pasos y los
      tokens, en [difusion-redes.md](difusion-redes.md).
- [ ] Cargar el **canal de WhatsApp** en `/contenido`. Está creado en el
      operativo (6/9); sin el enlace, la sección del home que le habla al
      comprador —"Enterate antes que nadie"— **no se dibuja**.
- [ ] Ponerle un **segundo administrador** al canal desde otra línea de URUKU.
- [ ] Completar en la tabla de arriba con qué cuenta se administra cada red.
- [ ] Anotar **con qué cuenta personal** se administra la página de Facebook.
      El día que esa persona no esté, la página se va con ella.
