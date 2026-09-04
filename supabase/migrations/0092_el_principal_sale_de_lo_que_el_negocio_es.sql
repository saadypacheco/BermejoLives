-- El rubro principal sale de lo que el negocio ES, no de lo que además vende.
--
-- LO QUE SE VIO EN LA VISTA PREVIA
-- ===============================
-- El recálculo elegía el principal por el `orden` de la taxonomía, asumiendo
-- que estaba numerada de más específico a más general. No lo está: los rubros
-- creados después —hoja de coca, carnicería, kiosco, taxis— quedaron al final
-- de esa numeración, así que pierden contra los genéricos viejos. Resultado:
--
--   un kiosco     → principal "Bebidas"        (por la gaseosa)
--   un bazar      → principal "Electrodomésticos"
--   hoja de coca  → principal "Bebidas"
--   un cotillón   → principal "Óptica"         (por "anteojo de fiesta")
--   una pollería  → principal "Supermercado y alimentos"
--
-- Todos esos comercios TIENEN la respuesta escrita: la subcategoría dice
-- `kiosco`, `bazar`, `hoja de coca`, `cotillón`, `pollería`. Y el nombre, cuando
-- no es genérico, dice lo mismo.
--
-- LA REGLA
-- ========
-- El nombre y la subcategoría dicen lo que el negocio **es**. La lista de
-- productos dice lo que además **vende**. No valen lo mismo para elegir el
-- principal, y tratarlos igual es lo que produce las tablas de arriba.
--
-- Entonces se calculan dos veces las sugerencias:
--
--   `sugeridos`   sobre todo el texto → los rubros del comercio (secundarios
--                 incluidos: el kiosco que además vende gaseosa tiene que
--                 aparecer buscando gaseosa).
--   `identidad`   sobre nombre + subcategoría → de acá sale el PRINCIPAL.
--
-- `identidad` es siempre un subconjunto de `sugeridos`, así que no aparece
-- ningún rubro nuevo: sólo se decide cuál de los que ya salieron manda. Si viene
-- vacía —nombre genérico y sin subcategoría— se cae al orden de la taxonomía,
-- que es lo que había.
--
-- Esto no arregla las palabras que arrastran ("secador de calzado" dispara
-- calzado, "anteojo de fiesta" dispara óptica). Eso es diccionario y se corrige
-- palabra por palabra con la vista previa de alcance. Pero un rubro arrastrado
-- de secundario ensucia una búsqueda; de principal, cambia lo que el comercio
-- ES en la ficha, en el pin y en el filtro. La diferencia de daño es toda.

create or replace function rubros_a_revisar(p_estado text default 'dudosos',
                                            p_limite int default 100)
returns table (
  comercio_id uuid,
  codigo text,
  nombre text,
  texto text,
  principal text,
  principal_nombre text,
  sugeridos text[],
  ya_tiene text[],
  portada text,
  identidad text[]
)
language sql stable
as $$
  select
    c.id, c.codigo, c.nombre,
    t.texto,
    r.slug, r.nombre,
    s.sug,
    coalesce((
      select array_agg(r2.slug order by r2.slug)
        from comercio_rubros cr join rubros r2 on r2.id = cr.rubro_id
       where cr.comercio_id = c.id), '{}'),
    c.portada_thumb_url,
    i.ident
  from comercios c
  join rubros r on r.id = c.rubro_id
  cross join lateral (
    select concat_ws(' ', c.nombre, c.subcategoria, c.prod_det_ia,
                     c.prod_obs_human) as texto) t
  cross join lateral (select rubros_sugeridos(t.texto) as sug) s
  -- Lo que el negocio dice que ES. Sin los productos.
  cross join lateral (
    select rubros_sugeridos(concat_ws(' ', c.nombre, c.subcategoria)) as ident) i
 where c.activo
   and c.rubro_revisado_at is null
   and case p_estado
         when 'sin-datos' then cardinality(s.sug) = 0
         else cardinality(s.sug) > 0 and not (r.slug = any(s.sug))
       end
 order by cardinality(s.sug) desc, c.nombre
 limit p_limite;
$$;

grant execute on function rubros_a_revisar(text, int) to service_role;
