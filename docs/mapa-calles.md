# Mapa de calles recorridas — spec

> **Estado: implementada el 14/10/2026.**

## Lo que pidió el dueño (14/10)

Un mapa por ciudad con las calles que ya se recorrieron, para identificarlas rápido y que los
agentes sepan **dónde están** y **dónde falta**.

## Hoy

`comercios.calle` sale del GPS con `backend/scripts/calles-desde-osm.py` (Overpass → SQL); el
trazado de las calles **no** se guarda. «Calles y horarios» (admin, `AdminCalles`) agrupa por
nombre de calle, sin mapa.

## Modelo (migración 0152 `0152_calles_tramos.sql`, dos carpetas, idempotente)

- `calles_tramos`: `id uuid pk`, `ciudad_id uuid not null`, `osm_way_id bigint`,
  `nombre text` (null = sin nombre en OSM), `tipo text` (clase `highway`), `geom jsonb not null`
  (lista `[[lat,lng],…]`, 5 decimales), `longitud_m int`, `activo bool default true`,
  `created_at`. Único `(ciudad_id, osm_way_id)`.
- `calles_marcas`: `id`, `tramo_id uuid references calles_tramos`, `estado text check in
  ('recorrida','sin_comercios','pendiente')`, `nota text` (≤ 200), `actor text`, `created_at`.
  Vale la **última** marca de cada tramo.
- Ambas **privadas** (sin grant a anon ni authenticated): las lee el backend con service_role.

## Cómo se decide el estado de un tramo (backend, una función documentada)

- Se muestrea la línea cada 15 m. Un punto está **cubierto** si hay un comercio activo de la
  ciudad (con lat/lng) a ≤ 35 m. `cobertura` = % de puntos cubiertos.
- Automático: **recorrida** ≥ 60 % · **parcial** 15–60 % · **pendiente** < 15 %.
- La última **marca manual** gana: `recorrida`, `sin_comercios` (calle de casas, baldío) o
  `pendiente` (volver a abrirla).
- `ultimo`: la carga más reciente sobre el tramo (`capturado_en` o `created_at` del comercio) y
  quién (`cargado_por`; al agente se le muestra sólo la parte antes de la @).
- Se calcula en el servidor con índice espacial simple (grilla por celdas) y se guarda en caché
  por ciudad unos minutos; una marca o un alta invalida esa ciudad.

## Backend

- `POST /admin/calles/importar` `{ciudad}` (permiso `lugares`): baja las calles de OSM (Overpass,
  caja = extensión de los comercios de la ciudad + 400 m; reusar la lógica de
  `calles-desde-osm.py`), sólo `highway` en primary, secondary, tertiary, residential,
  unclassified, living_street, pedestrian (y sus `_link`); upsert por `osm_way_id`; responde
  `{tramos, km}`. Overpass caído → 502 con mensaje.
- `GET /admin/calles/mapa?ciudad=` (permiso `moderar`) y `GET /campo/calles` (agente, su
  ciudad) → `{tramos: [{id, nombre, tipo, geom, longitud_m, cobertura, estado, marca:
  {estado, nota, actor, created_at}|null, comercios, ultimo: {fecha, quien}|null}], resumen:
  {km_total, km_recorridos, km_sin_comercios, pct}}`.
- `POST /campo/calles/{id}/marca` y `POST /admin/calles/{id}/marca` `{estado, nota?}` (el agente
  sólo en tramos de su ciudad).

## Frontend

- **Admin › Calles y horarios**: pestaña **«Mapa»** (Leaflet, `lib/mapa-tiles.ts` /
  `loadLeaflet` de `lib/mapa-visual.ts`) con las calles pintadas: verde recorrida, ámbar
  parcial, rojo pendiente, gris «sin comercios»; leyenda con «X de Y km recorridos (Z %)»;
  tocar una calle → nombre, cobertura, comercios, último paso (fecha y quién) y botones de
  marca. Botón «Traer calles de OpenStreetMap» si la ciudad no tiene tramos.
- **App del agente** («Qué hay acá», `components/mapa-aca.tsx`): capa de calles con los mismos
  colores (interruptor «Calles»), y debajo **«Calles pendientes cerca»** (las más cercanas en
  rojo/ámbar, con distancia y nombre) para ir a la siguiente. Tocar una calle → marcarla. Sin
  señal: la última capa guardada en el celular.

## Criterios

1. El admin trae las calles de Bermejo y ve el mapa pintado con el % recorrido.
2. Una calle con comercios cargados a lo largo sale verde; una sin ninguno, roja.
3. El agente marca una calle «sin comercios» y queda gris para todos.
4. En la app del agente se ven las calles pintadas y las pendientes más cercanas.
5. Tests verdes, `tsc` y `next build` ok, sin emoji.

## Importar por cuadras (15/10/2026, migración 0153)

**Problema (medido en producción, Tarija):** cada tramo era una vía entera de OSM (1.536 tramos para
327,8 km; ~213 m de promedio, avenidas de más de 1 km). La cobertura se calculaba sobre la vía entera:
una avenida con 10 comercios en 2 cuadras quedaba «pendiente» completa.

**Cómo se parte** (`tramos_de_vias` en `backend/app/services/calles_mapa.py`):

1. **En las esquinas.** `out geom` trae `nodes` (ids) además de `geometry`. Un nodo que está en dos o más
   vías **importadas** es una esquina; cada vía se corta en sus esquinas interiores. Una vía filtrada
   (`footway`, `service`…) no hace esquina; una vía no hace esquina consigo misma (lazos).
2. **Por largo.** Una cuadra de más de 150 m (`CUADRA_MAX_M`) se parte en `ceil(largo / 150)` partes
   iguales, con los cortes interpolados sobre la línea (empalman sin hueco). Con los 5 decimales de la
   geometría una parte puede pasarse ~1 m de los 150.
3. Cada pedazo es un tramo: `calles_tramos.parte` (0, 1, 2… en el orden de la vía).

**Modelo (0153 `0153_calles_cuadras.sql`, dos carpetas, idempotente):** `parte int not null default 0`;
el único `(ciudad_id, osm_way_id)` pasa a `(ciudad_id, osm_way_id, parte)`.

**Reimportar:** upsert por `(ciudad_id, osm_way_id, parte)` (mismo id si la cuadra sigue). Los tramos de
la ciudad que no vinieron quedan `activo = false` (baja lógica): las marcas viejas apuntan a ids que ya no
se muestran. Si Overpass no devuelve ninguna vía o falla, no se da de baja nada. Respuesta `{tramos, km}`.

**Lectura:** `GET /admin/calles/mapa` y `GET /campo/calles` no cambian (hay más tramos y más cortos).

**Medido** con Overpass real sobre una caja de Tarija (3.666 vías, 915 km): 11.770 tramos, promedio 78 m,
máximo 150 m. Para una ciudad del tamaño de la de producción (327,8 km) salen ~**4.200 tramos**. Con
4.241 tramos y 1.300 comercios el cálculo tarda ~0,15 s (la caché lo guarda 5 minutos) y la respuesta pesa
~1,2 MB sin comprimir (~200 KB con gzip).

**Ojo al reimportar una ciudad ya importada:** el tramo `(vía, 0)` conserva su id, así que una marca que se
hizo sobre una vía entera queda sobre su **primera cuadra**; las demás cuadras salen sin marca.
