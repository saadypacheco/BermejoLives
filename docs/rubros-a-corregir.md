# Rubros mal clasificados — lista abierta

> Cuaderno de campo. Se anota lo que se ve en **Admin › Negocios**, con el
> código, y después se corrige en tandas. No se corrige de a uno: la mayoría de
> estos casos son el mismo problema repetido, y arreglarlos uno por uno es
> pagar 888 veces un arreglo que se hace una.

## Antes de agregar un caso, leer esto

El panel muestra **un solo rubro por comercio**: el *principal*
(`comercios.rubro_id`), que es lo que sale en la ficha, en el color del pin y
en el filtro. Los demás rubros del comercio viven en otra tabla
(`comercio_rubros`) y **no se ven en esa lista** — pero sí los usa el buscador.

Por eso "está mal clasificado" puede querer decir tres cosas distintas, y cada
una se arregla diferente:

| Qué pasa | Cómo se ve | Cómo se arregla |
|---|---|---|
| **A. El principal quedó viejo** | El rubro correcto ya lo tiene, pero el panel muestra otro | Recalcular el principal. No llama a la IA, no inventa nada |
| **B. El rubro correcto no lo tiene** | Ni el panel ni el buscador lo encuentran | Palabra al diccionario + aplicar |
| **C. El rubro no existe** | No hay ninguno que le quede | Crear el rubro, después B |

**Casi todo lo que se ve es A**, y es importante saberlo: A no es un error del
clasificador, es que **el principal nunca se vuelve a calcular**. Se fija en el
alta y ahí queda. `reparar_rubro_principal.py` sólo toca a los que están en
"otros" — si el principal es un rubro de verdad, aunque sea el equivocado, lo
saltea. Y `Completar rubros` sólo **agrega** rubros: nunca saca el que está mal
ni cambia el principal.

Consecuencia: los rubros creados después (carnicería, hoja de coca, taxis,
funeraria…) no llegan a los comercios que se cargaron antes.

## Casos anotados

### 2026-09-04 — primera tanda

| # | Comercio | Código | Muestra | Tenía que ser | Tipo |
|---|---|---|---|---|---|
| 1 | Hotel Reina | `URUKU-AVJ2` | Blanquería y textil de hogar | Hospedaje | A |
| 2 | Ropa americana | `URUKU-SZNT` | Bolsos y accesorios | Ropa americana | A |
| 3 | SNACK POLLOS PREMIUM | `URUKU-NENJ` | Supermercado y alimentos | Comida rápida / restaurante | A |
| 4 | Taller de motos | — | Supermercado y alimentos | Motos y accesorios, o taller de motos | A o C |
| 5 | Carnicería La Estrella | — | Alimentos | Carnicería | A |
| 6 | kiosko | `URUKU-PDFK` | Supermercado y alimentos | Kiosco y golosinas | A |
| 7 | Coca machucada | — | Bebidas | Hoja de coca | A |

**Los 7 tienen rubro creado y palabra en el diccionario.** Verificado en las
migraciones: `hospedaje` con el patrón `hotel|hospedaje|alojamiento|…` (0045),
`ropa-americana` (0042 y 0061), `carniceria` (0086), `coca` con `coca machucada`
(0082), `kiosco` con `kiosko|kiosquito|…` (0059).

O sea: **el diccionario de hoy los clasificaría bien a todos.** Lo que está mal
no es lo que sabe el sistema, es que a estos comercios nadie se los volvió a
preguntar. Eso es una corrida, no 888 correcciones a mano.

El único dudoso es el 4: hay `taller-mecanico` (0083) pero no uno de motos.
Decidir si las motos entran ahí o son rubro propio — en Bermejo la moto es
transporte de todos los días, así que probablemente sea rubro propio.

## La herramienta, y cómo se usa

**Admin › Revisar rubros.** Trae sólo los que no cierran: el rubro que muestra
la ficha contra lo que el diccionario deduciría hoy del texto del comercio. Los
que ya coinciden no aparecen — de 1080 activos, 851 coinciden.

Cada fila muestra **el texto que se clasificó**, que es lo que explica el error.
"Hotel Reina" cayó en blanquería porque la foto describía sábanas y toallas; sin
ver eso, la corrección es a ciegas y el caso vuelve mañana.

Tres formas de resolver, de más rápida a más lenta:

- **✓ Está bien** — no cambia el rubro, pero marca el comercio como revisado por
  una persona y lo saca de la cola para siempre.
- **→ Hospedaje** (el sugerido) — un toque: lo pone de principal, conserva los
  rubros que ya tenía, y lo marca revisado.
- **Es otro…** — elegís cualquier rubro, y opcionalmente escribís **la palabra
  que lo hubiera clasificado bien**. Eso es lo único que hace que la corrección
  sirva para el próximo: el clasificador es un diccionario, y "aprender" es
  escribir en él. Una corrección arregla un comercio; una palabra arregla todos
  los que vengan.

Si dudás del alcance de una palabra, agregala desde **Rubros → vista previa**,
que cuenta a cuántos comercios llega **antes** de guardarla.

La pestaña **Sin datos** son los 33 que no producen ninguna sugerencia. No les
falta clasificación: les falta texto, o falta el rubro. Van aparte para no
diluir la cola con casos que no se resuelven con un clic.

Todo veredicto queda anotado en `rubro_correcciones` con el texto congelado. Con
eso se mide si el diccionario mejora, qué rubros se confunden entre sí, y contra
qué textos probar una palabra nueva.

## Lo que no hay que perder

**No existe ninguna marca de "esto lo corrigió una persona".** Las +200
correcciones a mano no se distinguen de las automáticas. Cualquier recálculo
masivo aplicado a ciegas las pisa.

**Resuelto el 2026-09-04:** `comercios.rubro_revisado_at` marca lo que miró una
persona, y la cola saltea lo marcado. Falta que lo saltee también el completado
masivo (`rubros_auto.analizar`) — hoy sólo agrega rubros, así que no pisa nada,
pero el día que exista un recálculo del principal esa guarda tiene que estar
puesta ANTES.

Las +200 correcciones anteriores a la marca siguen sin distinguirse: quedaron
sin `rubro_revisado_at`, así que van a aparecer en la cola. No es grave —
aparecen sólo si el diccionario las contradice, y confirmarlas es un toque.
