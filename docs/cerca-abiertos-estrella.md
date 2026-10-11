# Cerca de mí con abiertos, el orden por plan y la estrella — spec

> **Estado: aprobada el 10/10/2026, en implementación.**

## Decisiones del dueño (10/10)

1. **No hay botón «Abiertos ahora».** «Cerca de mí» muestra los cercanos y cada uno
   dice si está abierto: va implícito.
2. **Sin horario cargado = abierto** para el orden, hasta que se cargue el horario.
   Pero **no se muestra el sello «Abierto ahora»** en esos (mandar a alguien a una
   puerta cerrada le cuesta la confianza a URUKU).
3. **Orden con «Cerca de mí», en franjas:**
   1. Abiertos (incluye sin horario) antes que cerrados.
   2. Dentro de cada grupo, franjas de distancia: **hasta 300 m**, **hasta 1 km**,
      **más lejos**.
   3. Dentro de cada franja: primero los que tienen **estrella**, el plan más
      caro arriba; después por distancia, el más cercano primero.
4. **Estrella «Verificado por URUKU»** = el comercio tiene un **plan pago al día**
   (o de cortesía). En público se ve **sólo la estrella**; la tilde «verificado»
   que hoy pone el admin al chequear datos pasa a ser **interna** (deja de verse
   en la ficha y en los resultados).
5. **Plan de cortesía:** el admin puede poner a un comercio en un plan (el más
   alto, o el que elija) **sin vencimiento y sin cobro**, para personas que
   ayudan a URUKU. Tiene estrella, nunca vence y no aparece en cobros,
   suscripciones por vencer ni vencimientos.

## Definiciones

- **Plan pago**: un plan de la tabla `planes` con precio mayor a 0.
- **Al día**: `plan_cortesia = true`, o (`paga_hasta >= hoy de Bolivia` y no
  `suspendido`).
- **Estrella** = plan pago y al día.
- **Orden del plan** (`plan_orden`): entero, más alto = plan más caro; 0 = gratis
  o no al día. Se calcula del precio **sin exponer el precio al público** (los
  precios de los planes no se muestran: decisión del 4/10).

## Qué se construye

### Backend

- Migración **0143** (las dos carpetas, iguales, idempotente, `notify pgrst`):
  - `comercios.plan_cortesia boolean not null default false` + comentario.
  - `buscar_comercios` devuelve además `estrella boolean` y `plan_orden int`
    (sin cambiar los parámetros ni las columnas que ya devuelve). En la búsqueda
    normal (sin «Cerca de mí») el orden pasa a ser: relevancia, después
    `plan_orden` desc, después lo que ya había.
  - Una función pública para la ficha, `plan_publico(p_comercio uuid) returns
    table(estrella boolean, plan_orden int)`, ejecutable por anon, que no
    devuelve precios.
- **Admin › Suscripciones**: poder **asignar el plan** de un comercio y marcarlo
  **de cortesía**. `PUT /admin/comercio/{id}/plan` `{plan: slug, cortesia: bool}`
  (permiso `pagos`). Al confirmar un pago (`Confirmar 1 mes / 2 meses`), poder
  elegir el plan (hoy confirmar sólo extiende la fecha y el plan queda «gratis»).
- Los de cortesía **no cuentan** en `/admin/resumen` (suscripciones por vencer),
  ni en Suscripciones como vencidos, ni en vencimientos.

### Frontend

- **Buscador, «Cerca de mí»** (`components/buscar-client.tsx`): el orden de las
  decisiones 1–3. Cada resultado muestra su sello de horario (abierto/cerrado)
  si tiene horario; sin horario, nada.
- **Estrella** dorada «Verificado por URUKU» (ícono `estrella` de `<Ic>`, nunca
  emoji) junto al nombre: en la ficha, en cada resultado del buscador y en el
  globo del mapa. La tilde de verificado deja de verse en público.
- **Admin › Suscripciones**: elegir el plan de un comercio y el tilde «De
  cortesía (no paga, no vence)»; al confirmar un pago, elegir el plan.

## Criterios de aceptación

1. Con «Cerca de mí», un local con estrella a 250 m sale arriba de uno gratis a
   40 m (misma franja), y uno gratis a 50 m sale arriba de uno con estrella a
   3 km (otra franja). Los cerrados van al final.
2. Un local sin horario cuenta como abierto en el orden y no muestra sello.
3. Un comercio con plan pago al día, o de cortesía, muestra la estrella; uno con
   el pago vencido o suspendido, no. La tilde de verificado ya no se ve en público.
4. El admin pone a un comercio en el plan más alto de cortesía; tiene estrella,
   no vence y no aparece en cobros ni en vencimientos.
5. Ningún precio de plan llega al público.
6. Tests del backend en verde; `tsc` sin errores; sin emoji.
