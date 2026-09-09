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
| Facebook | *(completar — la página existe)* | ❌ | *(completar)* |
| Canal de WhatsApp | *(completar)* | ❌ | Operativo `64610187` |

> **Facebook:** la página se creó y el enlace se perdió. Para recuperarlo:
> menú → Páginas en el celular, `facebook.com/pages/?category=your_pages` en la
> compu, o Meta Business Suite. Si no aparece, probablemente se creó desde otra
> cuenta personal — es el motivo más común de una página que "desaparece".

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

- [ ] Recuperar el enlace de la **página de Facebook** y cargarlo en
      `/contenido`.
- [ ] Cargar el **canal de WhatsApp** en `/contenido`. Está creado en el
      operativo (6/9); sin el enlace, la sección del home que le habla al
      comprador —"Enterate antes que nadie"— **no se dibuja**.
- [ ] Ponerle un **segundo administrador** al canal desde otra línea de URUKU.
- [ ] Completar en la tabla de arriba con qué cuenta se administra cada red.
- [ ] Buscar el mail de bienvenida de Facebook en la casilla de
      `admin@uruku.bo` y en la cuenta personal: es el camino más corto al
      enlace de la página perdida, y de paso dice **con qué cuenta se creó**.
