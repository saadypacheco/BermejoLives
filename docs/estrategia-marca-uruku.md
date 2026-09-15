# La marca URUKU: de Bermejo a Bolivia

> Escrito el 14/9/2026. Completa a `publicidad-uruku.md` (que dice QUÉ publicar
> y en qué red, y sigue vigente) con lo que faltaba: **cómo se conoce la
> marca en la calle**, **cómo se sale de Bermejo**, y **qué se mira cada
> semana para saber si funciona**. No repite lo que ya está allá.

## La idea en una frase

URUKU no se hace conocida con publicidad: se hace conocida porque **está en el
lugar donde alguien tiene el celular en la mano y una pregunta** — en la mesa
del restaurante, en el mostrador, en el grupo de WhatsApp del barrio, en la
búsqueda de "dónde consigo". Cada una de esas apariciones lleva un QR o un
enlace con `?ref=`, así que **se puede contar** cuál trajo gente y cuál no.

Todo lo que sigue sale de eso.

## 1. Bermejo primero: puntos de presencia, no campañas

Lo que ya existe y hay que USAR, en el orden en que rinde:

| Pieza | Dónde queda | Qué hace por la marca | Cómo se mide |
|---|---|---|---|
| **Tarjeta de mesa** (`/volante/<slug>/mesa`) | Cada mesa de cada restaurante, bar, cafetería con plan o sin plan | El nombre URUKU frente a alguien sentado con tiempo. La carta que no se reimprime | `?ref=mesa-<slug>` en el QR (pendiente, ver §4) |
| **Volante** (`/volante/<slug>`) | El mostrador de cada local dado de alta | La prueba de que "está en URUKU" y el QR del local | `?ref=volante-<slug>` |
| **Grupo `URUKU · local`** | El WhatsApp del comerciante | El nombre URUKU en su pantalla todos los días; y su foto de oferta sale con la marca | Ofertas publicadas por grupo (ya está) |
| **Canal de ofertas** | El WhatsApp de los compradores | Lo que hace volver: ofertas de verdad, todos los días | Seguidores del canal; clics `?ref=canal` |
| **Uruku Ayuda** (el asistente) | El sitio y la PWA | Contesta lo que un vecino contestaría. Es lo que hace que alguien lo cuente | Preguntas por día, 👍/👎, sin respuesta (Admin › Ayuda) |
| **Las redes** (`@uruku.bo`) | Facebook primero, después TikTok/IG | Lo que dice `publicidad-uruku.md`: el comerciante comparte el posteo de SU local | Difusión (ya está) + `?ref=fb` / `?ref=ig` en los enlaces |

**La regla de la calle**: cada alta trae tres papeles — el volante, cuatro
tarjetas de mesa (o de mostrador) y el PDF en el grupo. Cuesta una hoja A4 y
media. Un local que no tiene el papel es un local que sólo existe en la base.

### Alianzas que en Bermejo valen más que un anuncio

- **Los que reciben al que llega**: terminal de buses, remises Bermejo–Tarija,
  hospedajes, la chalana y el puente. Una tarjeta "¿Qué hay en Bermejo? Escaneá"
  en cada uno. Es el momento exacto en que alguien necesita el directorio.
- **Los cambistas y casas de cambio**: por ahí pasa todo el que cruza. La
  cotización del día ya está en el sitio; ofrecerles la tarjeta con "el dólar
  de hoy y dónde comprar" es darles algo que a ellos les sirve.
- **Radios locales y el municipio**: no como pauta — como dato. "Lo más
  buscado en Bermejo esta semana" (Admin › Demanda) es una nota que una radio
  lee gratis, y el municipio tiene interés en que el comercio local se vea.
- **Los grupos de compra-venta de Facebook** que ya existen: no para publicar
  ofertas sueltas, para publicar **el informe** ("esta semana la gente buscó
  esto y no lo encontró") y el enlace al mapa. Es contenido que nadie más tiene.

## 2. La rutina semanal (una hora, con datos que ya se producen)

El contenido no se inventa: sale de la base. Cada lunes:

1. **Lo más buscado y lo que no se encontró** — Admin › Demanda. Un posteo
   ("esta semana buscaron X, Y, Z") + la frase de venta para los comerciantes
   del rubro que falta.
2. **Los comercios nuevos de la semana** — con su foto y su QR. Etiquetar al
   local: es él quien lo comparte.
3. **La mejor oferta de la semana** — del canal, con el enlace a la ficha.
4. **Una pregunta de Uruku Ayuda** que valga la pena contar ("nos preguntaron
   dónde cambiar dólares 40 veces; acá está la respuesta").

Los cuatro se pueden pre-armar con el mismo modelo que ya revisa
publicaciones: un **Agente Marketing** que cada lunes deja los cuatro
borradores en Admin › Difusión para aprobar con un clic. Es el siguiente paso
lógico de lo construido hoy y **no depende de nada externo** (§5).

## 3. Salir de Bermejo: una ciudad por vez, con el mismo molde

La tabla `ciudades` ya tiene veintidós ciudades cargadas y sólo Bermejo
encendida. Es la forma correcta: **una ciudad se enciende cuando tiene con qué,
no cuando alguien quiere**.

### El molde de una ciudad nueva

| Paso | Qué | Umbral para pasar al siguiente |
|---|---|---|
| 0. Elegir | Ciudad de frontera o de paso, chica, con comercio de mostrador. Igual que Bermejo | Yacuiba, Villazón, Desaguadero, Puerto Quijarro son las candidatas naturales: el mismo problema (dos monedas, gente de paso) |
| 1. Explorador | Un número Explorador (ver `numeros-whatsapp-uruku.md`) y una persona en la ciudad, con la app de campo | **200 comercios** con foto y qué venden, en 3-4 semanas |
| 2. Puntos de presencia | Volantes y tarjetas de mesa a los 200 | 50 locales con papel |
| 3. Grupos | Altas en el canal de ofertas, con el mismo Anfitrión | **20 locales publicando seguido** (el umbral de `publicidad-uruku.md`) |
| 4. Encender | `activa = true` en `ciudades`, canal de ofertas de esa ciudad, saber local de esa ciudad | Recién acá se anuncia al comprador |

Lo que hace que esto escale es que **nada de arriba es código nuevo**: la app de
campo, los grupos, el volante, la tarjeta, el asistente y el informe de demanda
ya funcionan por ciudad o son fáciles de acotar (el saber local tiene
`ciudad_id` desde hoy).

### Lo que sí hay que decidir antes de la segunda ciudad

- **El nombre de la cuenta por ciudad o una sola.** Recomendación: **una sola
  marca**, `@uruku.bo`, y ciudades como secciones ("URUKU Bermejo", "URUKU
  Yacuiba"). Cuatro cuentas por ciudad es el error de "repartirse en cuatro"
  multiplicado por ciudades.
- **Quién es el humano de cada ciudad.** El Explorador no puede ser el mismo
  que en Bermejo. Es un costo por ciudad, y es el único.
- **El canal de ofertas por ciudad.** Uno por ciudad, no uno nacional: nadie en
  Yacuiba quiere las ofertas de Bermejo.

## 4. Lo que falta para dejar de adivinar (y es chico)

1. **`?ref=` en los QR** del volante y la tarjeta (`ref=volante-<slug>`,
   `ref=mesa-<slug>`). `RefCapture` ya lo guarda; falta que los QR lo lleven y
   que el admin cuente llegadas por `ref`. Sin esto no se sabe si las tarjetas
   de mesa trajeron a alguien.
2. **Un panel de marca** en el admin: llegadas por `ref`, seguidores del canal,
   preguntas al asistente por día, comercios con papel. Cuatro números, una
   vez por semana.
3. **El saber local de cada ciudad**: la columna existe; falta que el admin la
   muestre cuando haya más de una ciudad.

## 5. Lo que se construyó hoy y cómo encaja

- **Uruku Ayuda** (`services/asistente.py`, Admin › Ayuda): el asistente del
  sitio, escalonado. Lo que no sabe queda anotado y se contesta una vez. Es el
  "dando información en base a experiencia registrada": la experiencia es la
  tabla `saber_local`, y crece con lo que la gente pregunta.
- **El asistente del comercio**: el mismo núcleo con los datos de un local,
  para el plan Empleado Digital. En la ficha, "Preguntale a <local>". Lo que no
  sabe se lo deja al dueño en Mi negocio › Mensajes.
- **Siguiente**: el Agente Marketing de §2 — borradores semanales desde los
  datos, a aprobar en Difusión. Con eso, la rutina de §2 es media hora.

## Lo que no hay que hacer

- Pauta paga antes de tener veinte locales publicando (está en
  `publicidad-uruku.md` y sigue valiendo).
- Abrir una ciudad "para que figure". Una ciudad vacía en el mapa es la prueba
  de que URUKU no sirve, mostrada a la gente de esa ciudad.
- Mandar mensajes a la base de 4.316 contactos desde los números de la marca.
  Ya está decidido: no.
- Contar seguidores como resultado. El resultado es **gente que llegó a una
  ficha y le escribió a un local**. Eso ya se mide (leads); lo demás es
  camino.
