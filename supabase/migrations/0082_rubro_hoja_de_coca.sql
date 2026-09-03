-- Rubro propio para la hoja de coca.
--
-- Son 11 comercios y estaban repartidos en tres rubros —7 en alimentos, 3 en
-- bebidas, 1 en kiosco— así que no aparecían juntos en ningún filtro. Es más de
-- lo que tienen florería (9), óptica (9) o motos (8), que sí tienen el suyo.
--
-- Y no es una categoría cualquiera acá: en Bermejo se vende legalmente, la
-- gente la busca por su nombre, y ya hay dos búsquedas registradas escritas
-- "hoaja de coca" — mal, pero buscando exactamente esto. Es la única señal de
-- demanda real que dio el sitio hasta ahora.

insert into rubros (slug, nombre, icono, orden) values
  ('coca', '🌿 Hoja de coca', '🌿', 44)
on conflict (slug) do update set
  nombre = excluded.nombre, icono = excluded.icono,
  orden = excluded.orden, activo = true;

-- OJO CON LA PALABRA "COCA" SOLA: no va, y es el punto más delicado de esta
-- migración. `\mcoca` matchea "coca cola", y en un kiosco que vende gaseosa eso
-- convertiría media ciudad en vendedores de hoja de coca. Van sólo las formas
-- que no son ambiguas.
--
-- "cocal" cierra con \M porque es la palabra entera (el sembrado de coca); sin
-- eso también agarraría "cocaleros", que es otra cosa.
insert into rubro_palabras (rubro_slug, patron) values
  ('coca', '\m(hoja de coca|hojas de coca|coca machucada|coqueo|acullico|akulliku|cocal\M|te de coca)')
on conflict (rubro_slug, patron) do nothing;

-- Se AGREGA el rubro a los que ya venden, sin sacarles ninguno: un local que
-- vende hoja de coca y gaseosa es de los dos rubros de verdad.
insert into comercio_rubros (comercio_id, rubro_id)
select c.id, (select id from rubros where slug = 'coca')
  from comercios c
 where c.activo
   and (c.prod_det_ia ilike '%hoja de coca%'
        or c.prod_det_ia ilike '%coca machucada%'
        or c.subcategoria ilike '%coqueo%')
on conflict do nothing;

-- Unificar las subcategorías que son la misma cosa escrita de siete formas:
-- coca, cocal, coca machucada, coqueo, hoja de coca. Siete etiquetas para lo
-- mismo son siete chips del buscador que no refinan nada y parten el grupo en
-- pedazos de uno.
--
-- `kiosco` y `herboristería` NO se tocan: ésas describen locales que además son
-- otra cosa, y pisarlas perdería información que nadie escribió dos veces.
update comercios
   set subcategoria = 'hoja de coca'
 where activo
   and lower(unaccent(coalesce(subcategoria, ''))) in
       ('coca', 'cocal', 'coca machucada', 'coqueo', 'hoja de coca', 'hojas de coca');
