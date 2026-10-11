# Fotos por plan, y tres pendientes de la estrella — spec

> **Estado: aprobada el 10/10/2026, en implementación.**

## A. Fotos del local según el plan

### El problema
La galería del comercio tiene un tope fijo de **10 fotos** (`_MAX_FOTOS` en
`api/campo.py`, `_GAL_MAX_FOTOS` en `api/comercio.py`, `_ADMIN_MAX_FOTOS` en
`api/moderacion.py`, `MAX_FOTOS` en `components/galeria-uploader.tsx`). El dueño
quiere que dependa del plan y que, al llegar al tope, el comercio elija.

### Qué se construye
1. **Tope por plan**, en la tabla `planes`, columna nueva `fotos_max int` (se
   edita en Admin › Planes). Valores iniciales: **gratis 50 · publica 100 ·
   destacado 300** (y premium, pro y empleado_ia 300).
2. **El tope de un comercio** = `fotos_max` de su plan si está al día (o es de
   cortesía); si no, el del plan gratis. Más las **fotos extra** que haya
   comprado (`comercios.fotos_extra int not null default 0`).
3. **Al llegar al tope**, subir otra foto devuelve **409** con
   `{"codigo":"tope_fotos","limite":N,"precio_extra":5,"moneda":"BOB","mas_vieja":{"id","url"}}`
   y la pantalla pregunta:
   - **«Pagar Bs 5 por una foto extra»** — sólo el **comerciante**. Se sube con
     `extra=pagar`: se registra un cargo extra de Bs 5 (los mismos cargos que el
     extra de publicaciones, que se cobran con el próximo pago), `fotos_extra`
     sube en 1 y la foto entra.
   - **«Borrar la foto más vieja»** — muestra esa foto (miniatura) antes de
     confirmar. Se sube con `reemplazar=<id>`: la foto nueva entra y recién
     después se borra la vieja (de la base y del disco).
   - **Cancelar**.
   El **agente** y el **admin** sólo ven «Borrar la más vieja» o «Cancelar»:
   no pueden comprometer plata del comercio.
4. El precio del extra sale de la configuración que ya existe para el extra de
   publicaciones (Bs 5); no se escribe un número nuevo en el código.
5. **Videos**: sin cambios (hasta 5).
6. Textos: Mi comercio («Y hasta 10 fotos…») y la galería muestran el tope real
   («23/50»). El manual del comerciante (`content/manuales/comercio.md`, «Tus
   fotos y videos») lo explica sin números fijos: «según tu plan».

Migración **0144** (`0144_fotos_por_plan.sql`, las dos carpetas iguales,
idempotente, `notify pgrst`). `fotos_max` no es secreto, pero va con el mismo
cuidado de grants que `planes` (0134): el público no lee precios.

## B. Los tres pendientes de la estrella (0143 todavía no se desplegó: se corrige ahí)

1. **Velocidad de la búsqueda.** `plan_orden_de` se ejecuta por fila y en cada
   llamada recalcula el `dense_rank` de `planes`. Reemplazar por una función
   `planes_orden()` (SECURITY DEFINER, `search_path` fijo, devuelve `(slug,
   orden)` sin precios) unida **una vez** en `buscar_comercios`, con el «al día»
   resuelto en línea. `plan_publico` puede seguir usando una función por
   comercio. Mismo resultado, mismos tests.
2. **El horario estimado en el buscador.** `buscar_comercios` devuelve además
   `horario_estimado boolean`, y los sellos del buscador pasan `estimado` a
   `HorarioBadge` («Suele estar abierto», como la ficha).
3. **Datos que el público no tiene por qué ver.** Hoy `comercios` tiene
   `grant select` de tabla entera para anon (0002): cualquiera ve
   `plan_cortesia`, `paga_hasta`, y también `cargado_por` (el correo del agente)
   y `capturado_en` (con qué hora y dónde anduvo cada agente). Migración **0145**:
   quitar el grant de tabla a anon y dar `grant select (columnas)` con todas las
   columnas que el sitio público usa, **menos** `plan_cortesia`, `paga_hasta`,
   `cargado_por`, `capturado_en`. **Antes**, todo `select("*")` o `select` sin
   columnas sobre `comercios` desde el frontend con anon pasa a columnas
   explícitas (con `*`, PostgREST falla si falta permiso en una sola columna).
   Revisar también vistas y funciones que lean esas columnas para anon.

## Criterios de aceptación
1. Un comercio gratis sube hasta 50 fotos; uno con publica al día, 100; con
   destacado, 300. Con el pago vencido vuelve al tope gratis (las que ya tiene no
   se borran; sólo no puede subir más).
2. En el tope, el comerciante ve las tres opciones; pagar registra un cargo de
   Bs 5 y la foto entra; borrar muestra la miniatura de la más vieja y, al
   confirmar, entra la nueva y se borra la vieja (base y disco).
3. El agente y el admin no ven la opción de pagar.
4. La búsqueda devuelve lo mismo que antes y más rápido; el buscador dice «Suele
   estar abierto» en los horarios estimados.
5. Como anon: `comercios?select=plan_cortesia` da error de permiso; la ficha, el
   buscador, el mapa, las ofertas y la guía siguen andando.
6. Tests verdes, `tsc` sin errores, sin emoji, sin precios al público.
