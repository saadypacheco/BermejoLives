# La secuencia completa cuando entran comercios nuevos (2026-09-03)

De la calle a la ficha publicada. Es lo que se repite en cada salida, así que
conviene tenerlo en un orden y no reconstruirlo de memoria cada vez.

**La regla que ordena todo: cada paso alimenta al siguiente, y saltearse uno no
da error — deja el resultado a medias con cara de terminado.** Analizar sin
haber resuelto los rubros nuevos manda esos comercios a "Otros"; aplicar el
diccionario sin haberlo mirado escribe lo que nadie revisó.

---

## 1. La calle — `/campo`

El agente saca **1 o 2 fotos**, toma la **ubicación** y, si puede, el
**WhatsApp**. Nada más: el nombre, el rubro, la descripción y los productos se
calculan después, a partir de las fotos.

Es a propósito. Elegir rubro de una lista de 50 en la vereda es inviable — se
cargan 80 locales en un día y todos terminan en "Otros". Lo que sí se puede
hacer parado en la puerta es sacar una foto.

Funciona **sin señal**: las altas se guardan en el teléfono y suben cuando hay
internet. Si el contador de pendientes no baja, ver la sección de fotos abajo.

> **Lo único que conviene anotar a mano en la calle:** el WhatsApp. Es el dato
> que la IA no puede sacar de una foto salvo que esté pintado en el cartel, y el
> que más caro sale después — un comercio sin contacto es una ficha que no lleva
> a ningún lado.

## 2. El análisis — Admin › Negocios › "Analizar pendientes"

Va de a 3 y en bucle desde el navegador, no en una sola llamada: cada análisis
tarda varios segundos y 200 seguidos superan cualquier timeout. Así además el
avance se ve y se puede cortar sin perder lo hecho.

De cada foto sale: **nombre del cartel**, descripción, **productos**,
**subcategoría**, **sinónimos** y los **rubros** que le corresponden.

Tres cosas que pasan acá y conviene saber:

- **Un rubro que la IA propone y no existe NO se pierde**: queda anotado en
  `rubros_propuestos`, que es lo que después se ve en Admin › Rubros. Ésa es la
  lista de qué categorías faltan, medida contra vidrieras reales.
- **Si un análisis falla, la tanda se corta.** No se marca ese comercio como
  analizado —el fallo puede ser transitorio— y se frena para no gastar la tanda
  contra un problema que ya se repite.
- **Confianza 0 no es un error**: el modelo miró y no reconoció nada (foto de
  noche, persiana cerrada). Se marca igual como analizado para que la tanda
  avance; si no, cada corrida volvería a tropezar con los mismos.

## 3. Los rubros nuevos — Admin › Rubros

**Este paso va ANTES de completar rubros, no después.** Si la IA vio tres
carnicerías y ese rubro no existe, completar sin crearlo primero las deja donde
estaban.

Arriba está la lista de lo que la IA pidió y no existe, por frecuencia. Cada
fila es **una de dos cosas**, y confundirlas es cómo se llega a rubros vacíos:

| | |
|---|---|
| **Un rubro que falta** | "carnicería" — 13 pedidos, ningún rubro lo cubre |
| **Otra forma de decir uno que existe** | "lubricentro" es neumáticos, "bijouterie" es joyería |

Al escribir las palabras, la pantalla dice **a cuántos comercios alcanzarían y
con qué otros rubros conviven**. Si los que alcanza son casi todos de un rubro
ajeno, la palabra está arrastrando y no clasificando. Ahí se corrige, no
después.

Regla del vocabulario, que costó varias vueltas aprender: **van las formas
compuestas, no el producto suelto.** "pollo" lo vende media comida rápida,
"detergente" cualquier almacén, "bar" está dentro de "barbería", "reja" aparece
en la descripción de una foto sacada a través de una reja.

## 4. Completar rubros — Admin › Rubros › "Analizar" y "Aplicar"

Las palabras nuevas **no reclasifican nada solas**. Esto le agrega a cada
comercio los rubros que sus productos sugieren y todavía no tiene.

**Mirá el detalle antes de aplicar.** No es adorno: es donde se ve que una
palabra metió veinte kioscos en comida rápida, y se ve ANTES de escribirlo.

Sólo SUMA rubros; nunca quita uno elegido a mano. Si alguno sobra se saca
después desde la ficha, de un toque.

Si dice que la lectura vino incompleta, **no apliques**: los comercios que
quedaron afuera se leen como si no tuvieran ningún rubro y el informe propone
agregarles de todo. Pasó — con 1000 de 2440 filas propuso 1295 rubros para
comercios que ya los tenían.

## 5. La pasada a mano — Admin › Negocios

Lo que ninguna IA puede resolver, con las flechas del modal y "Guardar y
siguiente" para no cerrar en cada uno:

- **Horario.** El dato que decide si alguien camina hasta el local. Filtro "Sin
  horario", presets de un toque, y "↩ Igual que el anterior" — viniendo de a
  uno, el anterior suele ser el vecino de la cuadra.
- **Nombre**, cuando el cartel no se leyó o dice sólo "Comercio".
- **WhatsApp**, el que faltó en la calle.
- **Rubros**, sacando el que sobre.
- **Redes**, si las tiene.

## 6. Verificar

Pasa de "pendiente" a "verificado". Es lo único que dice que una persona lo
miró.

---

## Después de cada tanda grande

**La auditoría del diccionario** (`supabase/auditar_diccionario.sql`) dice qué
patrón disparó cada propuesta y con qué fragmento de texto. La §9 lista los
sinónimos de varias palabras que arrastran a otro rubro.

**Admin › Catálogo** muestra las subcategorías de menor a mayor. Las de un solo
comercio son chips del buscador que no refinan nada, y casi siempre son la misma
cosa escrita de dos formas — se arreglan fusionando, no cargando más.

---

## Cuando algo no aparece

| Síntoma | Dónde mirar primero |
|---|---|
| Las altas del campo no suben | El service worker del teléfono: cerrar la app del todo y volver a abrirla |
| Un comercio no sale en el buscador | Que tenga rubro y que no esté en "Otros" |
| Un comercio no sale en el mapa | Que tenga lat/lng — se cargan en la calle, no después |
| Un rubro no filtra nada | Que tenga palabras en el diccionario: sin ellas nunca se asigna solo |
| El panel no muestra lo que acabo de migrar | `docker compose restart postgrest` — la caché de esquema |

## Lo que NO hay que hacer

- **Crear un rubro por cada nombre distinto que aparezca.** En agosto hubo que
  apagar 19 rubros vacíos. Un rubro sin comercios en la fila de chips promete
  algo que no hay.
- **Aplicar el completado sin mirar el detalle.**
- **Meter los sinónimos en la clasificación.** Existen para que el COMPRADOR
  encuentre; clasificar es otra pregunta y la respuesta está en `prod_det_ia`.
  Metidos ahí, "ciclismo indoor" hacía de un gimnasio una bicicletería.
