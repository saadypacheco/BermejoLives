-- Arreglo de la 0115: cuatro baños públicos se fueron a Bazar, Ropa,
-- Calzado y Kiosco.
--
-- La 0115 hacía dos cosas en este orden: (1) el principal pasa a ser lo
-- que dice la subcategoría, (2) a los baños se les borra la subcategoría
-- heredada ("ojota", "golosina"). Al revés hubiera estado bien: con (1)
-- primero, un "Baño público" con subcategoría "ojota" pasó a Calzado
-- antes de que (2) le borrara el "ojota". Quedaron cuatro así.
--
-- Un baño público es un baño público: principal `banos`, sin otros rubros,
-- sin subcategoría. Se identifica por el nombre, que es lo único fiable.

with banos as (
  select c.id, r.id as rubro_id
  from comercios c, rubros r
  where r.slug = 'banos' and c.activo
    and lower(unaccent(c.nombre)) ~ '\mbano(s)? publico(s)?\M'
)
update comercios c set rubro_id = b.rubro_id, subcategoria = null
from banos b where c.id = b.id;

delete from comercio_rubros cr
using comercios c, rubros r
where cr.comercio_id = c.id and c.activo
  and lower(unaccent(c.nombre)) ~ '\mbano(s)? publico(s)?\M'
  and cr.rubro_id <> c.rubro_id;

insert into comercio_rubros (comercio_id, rubro_id)
select c.id, c.rubro_id from comercios c
where c.activo and lower(unaccent(c.nombre)) ~ '\mbano(s)? publico(s)?\M'
on conflict do nothing;
