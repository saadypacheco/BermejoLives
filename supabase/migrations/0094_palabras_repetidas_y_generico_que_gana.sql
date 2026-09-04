-- Palabras repetidas en el diccionario, y las que hacen ganar al genérico.
--
-- Salió de reconstruir el estado final de `rubro_palabras` aplicando las 93
-- migraciones en orden —contar por archivo miente, porque la 0061 y la 0062
-- BORRAN y reescriben— y buscar términos repetidos. Dos hallazgos distintos:
--
-- 1) LAS QUE ESTABAN DOS VECES EN EL MISMO RUBRO — cosmético
-- ==========================================================
-- `rubros_sugeridos` hace `array_agg(distinct ...)`, así que un término
-- repetido no duplica el rubro: no cambiaba nada, sólo se veía sucio en el
-- panel. Salvo una, que es un error de tipeo de verdad: la 0060 escribió
-- `licoreria|licoreria` dentro del mismo patrón.
--
-- Las otras seis son la misma historia repetida: una migración posterior
-- agregó un bloque de vocabulario nuevo y arrastró palabras que ya estaban.
-- Se sacan del bloque nuevo y quedan en el original.
--
-- 2) LAS QUE ESTABAN EN DOS RUBROS — ésta sí clasificaba doble
-- ============================================================
-- `carniceria` estaba en `alimentos` Y en `carniceria`; `gimnasio` en
-- `deportes` Y en `gimnasios`. El patrón es siempre el mismo: se creó el rubro
-- específico y la palabra se quedó también en el genérico viejo. Resultado: la
-- pollería queda en "Supermercado y alimentos" además de en "Carnicería", y el
-- genérico gana el principal por ser más antiguo en la taxonomía.
--
-- Es exactamente lo que se vio en la vista previa: un comercio cuyos productos
-- son "pollo al espiedo, cuarto de pollo, medio pollo, pollo entero" quedaba de
-- supermercado. Por eso `pollo` también sale de `alimentos`: es un producto que
-- nombra a la pollería, no al almacén. `carne` se queda —un almacén con
-- fiambrería la lista— y si arrastra se saca después, midiendo con la vista
-- previa de alcance.
--
-- Las que NO se tocan, porque el solapamiento es real y no un olvido:
--   alineacion, balanceo   gomería y taller mecánico hacen las dos cosas
--   cambio de aceite       gomería y taller también
--   feria americana        ropa usada y usados en general se pisan de verdad
--
-- Cada arreglo borra la fila entera y la reescribe: los patrones son
-- alternancias completas, no una fila por palabra. Las palabras agregadas desde
-- el panel viven en filas aparte y no se tocan.

-- ── 1) repetidas en el mismo rubro ───────────────────────────────────────────

-- El typo: la misma palabra dos veces en el mismo patrón.
delete from rubro_palabras where rubro_slug = 'bebidas' and patron like '%licoreria|licoreria%';
insert into rubro_palabras (rubro_slug, patron) values
  ('bebidas', '\m(licoreria|distribuidora de bebida|bebida alcoholica)')
on conflict do nothing;

-- `bisuteria` ya estaba en el patrón original de joyería.
delete from rubro_palabras where rubro_slug = 'joyeria' and patron like '%bijouterie%';
insert into rubro_palabras (rubro_slug, patron) values
  ('joyeria', '\m(bijouterie|fantasia fina)')
on conflict do nothing;

-- `comedor` ya estaba; queda la forma compuesta, que es la que agregaba algo.
delete from rubro_palabras where rubro_slug = 'restaurantes' and patron like '%comedor popular%';
insert into rubro_palabras (rubro_slug, patron) values
  ('restaurantes', '\m(comedor popular|pension de comida)')
on conflict do nothing;

-- `pelota` ya estaba en el patrón original de deportes.
delete from rubro_palabras where rubro_slug = 'deportes' and patron like '%articulo deportivo%';
insert into rubro_palabras (rubro_slug, patron) values
  ('deportes', '\m(articulo deportivo|articulos deportivos|indumentaria deportiva|suplemento deportivo|proteina en polvo|camiseta de futbol|botin de futbol)')
on conflict do nothing;

-- `encomienda`, `courier` y `paqueteria` ya estaban en el patrón original.
delete from rubro_palabras where rubro_slug = 'envios' and patron like '%fedex%';
insert into rubro_palabras (rubro_slug, patron) values
  ('envios', '\m(fedex|dhl|casilla postal|giro de dinero|mensajeria)')
on conflict do nothing;

-- ── 2) el genérico que se quedaba con la palabra del específico ──────────────

-- `carniceria` y `pollo` salen de alimentos: nombran a la carnicería y a la
-- pollería, que ya tienen su propio rubro desde la 0086.
delete from rubro_palabras where rubro_slug = 'alimentos' and patron like '%abarrote%';
insert into rubro_palabras (rubro_slug, patron) values
  ('alimentos', '\m(supermercado|almacen|abarrote|arroz|azucar|fideo|mercaderia|comestible|verduleria|fruta|verdura|carne|huevo|lacteo|queso|harina|conserva)')
on conflict do nothing;

-- `gimnasio` sale de deportes: tiene su rubro propio desde la 0086.
delete from rubro_palabras where rubro_slug = 'deportes' and patron like '%fitness%';
insert into rubro_palabras (rubro_slug, patron) values
  ('deportes', '\m(deporte|deportivo|fitness|futbol|suplemento)')
on conflict do nothing;
