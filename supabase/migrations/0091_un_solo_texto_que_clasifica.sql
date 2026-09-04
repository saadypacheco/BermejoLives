-- Un solo texto que clasifica, en todos lados.
--
-- LA CAUSA DE LOS 194 "MAL CLASIFICADOS"
-- ======================================
-- El alta y la revisión leían campos distintos, y nadie lo había notado porque
-- cada lado, por separado, hacía algo razonable.
--
--   Alta (`texto_para_rubros`)      nombre + prod_obs_human + prod_det_ia +
--                                   subcategoria + SINONIMOS + DESCRIPCION
--   Masivo (`_texto_de`)            prod_det_ia + subcategoria + nombre
--   SQL (esta migración, antes)     prod_det_ia + subcategoria + nombre
--
-- O sea: los rubros que un comercio TIENE se calcularon con un texto más ancho
-- y más sucio que el que después los juzga. Por eso la cola encontraba 194
-- comercios que no cierran — no estaban mal clasificados, estaban clasificados
-- con OTRA regla. Y por eso aparecen cosas como una carnicería en un taller de
-- motos: algo en la descripción o en los sinónimos disparó un rubro que el
-- diccionario, mirando sólo lo que vende, nunca habría elegido.
--
-- `sinonimos` y `descripcion` se van de la clasificación. Los sinónimos existen
-- para que el COMPRADOR encuentre —busca "polera" y aparece el que vende
-- remeras—; clasificar es otra pregunta. La descripción es prosa libre sobre el
-- local (la cuadra, los vecinos, cómo llegar) y cualquier sustantivo que caiga
-- ahí dispara un rubro que nadie pidió.
--
-- `prod_obs_human` —lo que anotó el agente parado en la vereda— entra en las
-- tres funciones SQL, que no lo miraban. Es de los mejores datos que hay: lo
-- escribió alguien que estaba viendo la vidriera.
--
-- Quedan los cuatro campos que nombran lo que vende, iguales en Python y en SQL.

create or replace function previsualizar_patron(p_patron text, p_rubro text default null)
returns table (
  comercio_id uuid,
  codigo text,
  nombre text,
  vende text,
  ya_lo_tiene boolean,
  otros_rubros text[]
)
language sql stable
as $$
  select
    c.id,
    c.codigo,
    c.nombre,
    left(coalesce(c.prod_det_ia, ''), 90),
    p_rubro is not null and exists (
      select 1 from comercio_rubros cr join rubros r on r.id = cr.rubro_id
       where cr.comercio_id = c.id and r.slug = p_rubro),
    coalesce((
      select array_agg(r2.slug order by r2.slug)
        from comercio_rubros cr2 join rubros r2 on r2.id = cr2.rubro_id
       where cr2.comercio_id = c.id
         and (p_rubro is null or r2.slug <> p_rubro)), '{}')
  from comercios c
 where c.activo
   and unaccent(lower(concat_ws(' ', c.nombre, c.subcategoria, c.prod_det_ia,
                                c.prod_obs_human))) ~ p_patron
 order by 5, c.nombre
 limit 200;
$$;

grant execute on function previsualizar_patron(text, text) to service_role;

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
  portada text
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
    c.portada_thumb_url
  from comercios c
  join rubros r on r.id = c.rubro_id
  cross join lateral (
    select concat_ws(' ', c.nombre, c.subcategoria, c.prod_det_ia,
                     c.prod_obs_human) as texto) t
  cross join lateral (select rubros_sugeridos(t.texto) as sug) s
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

create or replace function rubros_revision_resumen()
returns table (total bigint, revisados bigint, dudosos bigint, sin_datos bigint)
language sql stable
as $$
  with x as (
    select c.rubro_revisado_at, r.slug as principal, s.sug
      from comercios c
      join rubros r on r.id = c.rubro_id
      cross join lateral (
        select rubros_sugeridos(concat_ws(' ', c.nombre, c.subcategoria,
                                          c.prod_det_ia, c.prod_obs_human)) as sug) s
     where c.activo)
  select
    count(*),
    count(*) filter (where rubro_revisado_at is not null),
    count(*) filter (where rubro_revisado_at is null
                       and cardinality(sug) > 0 and not (principal = any(sug))),
    count(*) filter (where rubro_revisado_at is null and cardinality(sug) = 0)
  from x;
$$;

grant execute on function rubros_revision_resumen() to service_role;
