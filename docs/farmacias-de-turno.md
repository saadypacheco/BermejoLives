# Farmacias de turno — spec

> **Estado: implementada el 15/10/2026.**

## Lo que pidió el dueño (15/10)

Llevar a URUKU el rol de turnos de las farmacias de Bermejo (19 farmacias, 4/10 al 12/12/2026)
y mostrar **en el mapa** qué farmacias están de turno. Los horarios de atención de cada una
se cargan después.

## Regla del turno

En Bolivia el turno farmacéutico dura **24 horas: de las 08:00 del día indicado a las 08:00
del día siguiente** (DS 25235, reglamento de la Ley del Medicamento, art. 74), con atención
continua. Ej.: turno del 15/10 → 15/10 08:00 a 16/10 08:00 (hora de Bolivia, UTC−4).

## Datos

`backend/data/turnos_farmacia/bermejo-2026-10-04_2026-12-12.json` (armado desde el rol):
- 19 farmacias. **7 ya estaban** en URUKU (van con su `slug`): Amanecer, Ángeles (Los
  Ángeles), Copacabana, Corazón de Jesús, Popular, San Ramón, Señor de Mayo. **12 faltaban**:
  van con `lat/lng` calculados desde la dirección cruzando calles de OpenStreetMap
  (`ubicacion_aproximada: true`; error de cruce 4-7 m, «Calle Madrid» = «Calle Real Madrid»
  en OSM; Dorado es ambigua en la fuente).
- Teléfonos **tal como en la fuente**, sin prefijos ni suponer WhatsApp: `celular` y `fijo`.
  `nota_interna` = dudas de la fuente (no se publican).
- 70 días, 140 turnos (2 farmacias por día).

## Modelo (migración 0154 `0154_turnos_farmacia.sql`, dos carpetas, idempotente)

- `turnos_farmacia`: `id`, `comercio_id uuid not null references comercios`, `fecha date not
  null`, `inicio timestamptz not null`, `fin timestamptz not null`, `fuente text`, `activo bool
  default true`, `created_at`; único `(comercio_id, fecha)`. **Lectura pública** (anon) de
  `id, comercio_id, fecha, inicio, fin` donde `activo`.
- `comercios.ubicacion_aproximada boolean not null default false` — **privada** (regla 11).
- `comercios.nota_interna text` si no existe algo equivalente — privada.

## Backend

- `services/turnos_farmacia.py` `importar(repo, data)`: idempotente.
  - Con `slug`: completa `telefono` (celular, si no hay fijo; si están los dos, el celular) y
    `direccion` **sólo si están vacíos**; no pisa nada cargado.
  - Sin `slug`: busca una farmacia ya creada por una importación anterior (mismo nombre de ficha,
    ciudad, rubro `farmacia`); si no hay, la crea con `repo.crear_comercio` (código, slug,
    rubro `farmacia`, ciudad, `fuente='turnos'`, `lat/lng`, `ubicacion_aproximada`, teléfono,
    dirección, `nota_interna`).
  - Turnos: upsert por `(comercio_id, fecha)` con `inicio = fecha 08:00 America/La_Paz` y
    `fin = inicio + 24 h`.
  - Devuelve `{creadas, actualizadas, turnos}`.
- `POST /admin/farmacias/turnos/importar` (permiso `lugares`) con el JSON en el cuerpo, y un
  comando `python -m app.scripts.importar_turnos_farmacia <archivo>` para correrlo en el contenedor.
- El agente (`/campo/mis-comercios`) recibe `ubicacion_aproximada` y, al re-tomar el GPS de ese
  comercio en «Completar», pasa a `false`.

## Frontend (lectura pública con anon)

- `lib/data.ts`: `getTurnosFarmacia(ciudadId, desde, hasta)` → turnos con la farmacia
  (`comercios(id, slug, nombre, direccion, telefono, whatsapp, lat, lng, portada_thumb_url)`).
  «De turno ahora» = `inicio <= ahora < fin`.
- **Página `/farmacias-de-turno`** (ISR corta, p. ej. `revalidate = 300`): arriba las dos
  **de turno ahora** con «hasta mañana 08:00», botón **Llamar** (`tel:`) y **Cómo llegar**; un
  mapa con sus dos pines; debajo **los próximos 7 días** (fecha → dos farmacias); nota «El turno
  va de 08:00 a 08:00 del día siguiente (DS 25235, art. 74)».
- **Mapa público** (`components/map-results.tsx` y donde se dibujen pines de comercios): las
  farmacias de turno ahora con un pin destacado (`<Ic>` cruz/farmacia, color propio) y en su
  globo «De turno ahora · hasta mañana 08:00».
- **Ficha** de una farmacia: si está de turno, sello verde «De turno ahora · hasta mañana
  08:00 · atiende las 24 h»; si no, «Próximos turnos: 22/10, 2/11, …» (los próximos 4).
- **Inicio y Guía**: tarjeta «Farmacias de turno hoy: Ángeles y San Miguel → Ver» (sólo en
  ciudades con turnos cargados).
- **Agente** (`ficha-agente.tsx` / «Qué hay acá»): si `ubicacion_aproximada`, aviso «Ubicación
  aproximada: confirmala tomando el GPS en la puerta».
- Íconos con `<Ic>`, nunca emoji.

## Criterios

1. Importar el JSON crea 12 farmacias nuevas en Bermejo, completa las 7 existentes sin pisar
   datos y carga 140 turnos; correrlo dos veces no duplica nada.
2. El 15/10 a las 10:00 (Bolivia) «de turno ahora» son Ángeles y San Miguel; el 16/10 a las
   07:59 siguen siendo ellas; a las 08:00 pasan a Señor de Mayo y Santa Isabel.
3. `/farmacias-de-turno`, el mapa, la ficha y el inicio lo muestran; anon no lee
   `ubicacion_aproximada` ni `nota_interna`.
4. Tests verdes, `tsc` y `next build` ok, sin emoji.
