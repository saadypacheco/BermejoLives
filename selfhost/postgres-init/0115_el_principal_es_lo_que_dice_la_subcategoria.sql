-- El rubro principal es lo que dice la subcategoría, cuando lo dice claro.
--
-- Cruzando subcategoría contra rubro principal en los 1.000 activos
-- (17/9/2026): 13 carnicerías con principal "Supermercado y alimentos", 8
-- kioscos y 5 "hoja de coca" con principal "Bebidas", 5 peluquerías con
-- "Perfumería y belleza", 5 electrodomésticos con "Bazar", y Rústico
-- —subcategoría "restaurante"— con principal "Bazar y cocina". Todos
-- tienen el rubro correcto entre sus rubros; lo que falló fue elegir cuál
-- manda (la 0092 lo explica: el genérico viejo le gana al específico nuevo).
--
-- LA REGLA, estrecha a propósito: si la subcategoría sola —sin el nombre ni
-- los productos— dispara UN solo rubro del diccionario, y ese rubro ya es
-- uno de los del comercio, y no es el principal, pasa a ser el principal.
-- Un solo rubro: si la subcategoría dispara dos, no se decide acá sino en
-- Admin › Rubros, como hasta ahora. Y nunca se agrega un rubro nuevo.
--
-- Corre como postgres: `rubros_sugeridos` lee `rubro_palabras`, que anon no
-- ve, así que desde afuera parece que devuelve vacío y no es así.

with sugerido as (
  select c.id as comercio_id, r.id as rubro_id, r.slug
  from comercios c
  cross join lateral (select rubros_sugeridos(c.subcategoria) as sug) s
  join rubros r on r.slug = s.sug[1]
  where c.activo
    and c.subcategoria is not null and btrim(c.subcategoria) <> ''
    and array_length(s.sug, 1) = 1
    and r.id <> c.rubro_id
    and exists (select 1 from comercio_rubros cr where cr.comercio_id = c.id and cr.rubro_id = r.id)
)
update comercios c set rubro_id = s.rubro_id
from sugerido s
where c.id = s.comercio_id;

-- Subcategorías sin rubro en el diccionario, que igual dicen lo que el
-- negocio es. Una vidriería es lo más cercano a ferretería y construcción.
update comercios c set rubro_id = r.id
from rubros r
where r.slug = 'ferreteria' and c.activo
  and lower(unaccent(coalesce(c.subcategoria, ''))) ~ '\mvidrier'
  and c.rubro_id <> r.id
  and exists (select 1 from rubros ro where ro.id = c.rubro_id and ro.slug in ('alimentos', 'otros', 'bazar'));
insert into comercio_rubros (comercio_id, rubro_id)
select c.id, c.rubro_id from comercios c
where c.activo and lower(unaccent(coalesce(c.subcategoria, ''))) ~ '\mvidrier'
on conflict do nothing;

-- Los baños públicos cargados desde campo arrastraron la subcategoría del
-- comercio anterior del formulario ("ojota", "ropa de bebé", "polirrubro").
-- Un baño no tiene subcategoría.
update comercios c set subcategoria = null
from rubros r
where r.id = c.rubro_id and r.slug in ('banos', 'estacionamiento', 'cajeros', 'wifi')
  and c.subcategoria is not null
  and lower(unaccent(c.subcategoria)) !~ '\m(bano|sanitario|estacionamiento|cochera|cajero|wifi)';
