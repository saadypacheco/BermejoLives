-- «¿Te contestó?»: la única señal que hay de si un comercio atiende.
--
-- El comprador toca el WhatsApp de un local y la conversación sigue en el
-- teléfono del comerciante, donde URUKU no ve nada. Lo que sí se puede es
-- preguntarle al comprador, un rato después, si le contestaron. Con eso:
--
--   · leads.respondio        la respuesta (sí / no) atada al contacto.
--   · comercios.contacto_ok  cuántos dijeron que sí, en los últimos 90 días.
--   · comercios.contacto_no  cuántos dijeron que no.
--
-- Y en la búsqueda: los que responden llevan un «✓ Responde», y los que no
-- contestan nunca (cinco «no» y ningún «sí») bajan al final de su rubro,
-- sin desaparecer. En el panel, la lista de «no contestan» para que el
-- Anfitrión los llame: casi siempre es un número viejo o un teléfono
-- apagado, no mala voluntad.

alter table leads add column if not exists respondio boolean;
alter table leads add column if not exists respondio_en timestamptz;
comment on column leads.respondio is
  '¿Le contestaron al comprador? true / false; NULL = no se sabe (no se preguntó o no respondió la pregunta).';

alter table comercios add column if not exists contacto_ok int not null default 0;
alter table comercios add column if not exists contacto_no int not null default 0;
comment on column comercios.contacto_ok is 'Contactos por WhatsApp de los últimos 90 días en los que el comprador dijo que SÍ le contestaron. Lo recalcula el backend.';
comment on column comercios.contacto_no is 'Ídem, los que dijeron que NO.';

-- ------------------------------------------------- buscar_comercios
-- Devuelve dos columnas más (contacto_ok, contacto_no), así que cambia el
-- tipo de retorno y hay que tirar la función antes de crearla. Mismo cuerpo
-- que la 0113 más el orden: los que no contestan, al final de su rubro.
drop function if exists buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text);

create function buscar_comercios(
  q text default null, p_rubro text default null, p_modalidad text default null,
  p_zona text default null, p_precio_min numeric default null, p_precio_max numeric default null,
  p_ciudad text default null, p_limit int default 24, p_offset int default 0,
  p_subcategoria text default null
)
returns table (
  id uuid, slug text, nombre text, descripcion text, logo_url text, portada_url text,
  whatsapp text, direccion text, lat double precision, lng double precision, modalidad text,
  rubro_slug text, rubro_nombre text, subcategoria text, zona_nombre text, rating numeric, verificado boolean,
  ofertas bigint, rank real, monedas_aceptadas text[], envios_internacionales boolean,
  tiene_factura boolean, horario text, tiene_stock boolean, ciudad_nombre text, ciudad_pais text,
  prod_obs_human text, prod_det_ia text,
  destacado boolean, plan text, portada_thumb_url text, portada_pos smallint,
  contacto_ok int, contacto_no int,
  total bigint
)
language sql stable
as $$
  with entrada as (
    select
      lower(unaccent(coalesce(q, ''))) as texto,
      '\m' || regexp_replace(lower(unaccent(coalesce(q, ''))),
                             '([.^$*+?()\[\]{}|\\-])', '\\\1', 'g') as inicio_palabra,
      websearch_to_tsquery('spanish_unaccent', coalesce(q, '')) as tsq_todas,
      websearch_to_tsquery('spanish_unaccent',
        regexp_replace(btrim(coalesce(q, '')), '\s+', ' or ', 'g')) as tsq_alguna
  ),
  base as (
    select distinct on (c.id)
      c.id, c.slug, c.nombre, c.descripcion, c.logo_url, c.portada_url,
      c.whatsapp, c.direccion, c.lat, c.lng, c.modalidad,
      r.slug as rubro_slug, r.nombre as rubro_nombre, c.subcategoria, z.nombre as zona_nombre,
      c.rating, c.verificado,
      (select count(*) from publicaciones pp
         where pp.comercio_id = c.id and pp.estado = 'aprobado' and pp.activo) as ofertas,
      coalesce(
      q is null or q = ''
       or c.busqueda @@ e.tsq_todas
       or p.busqueda @@ e.tsq_todas
       or lower(unaccent(c.nombre)) ~ e.inicio_palabra
       or exists (
            select 1 from comercio_rubros cr4 join rubros r5 on r5.id = cr4.rubro_id
             where cr4.comercio_id = c.id
               and (to_tsvector('spanish_unaccent', r5.nombre) @@ e.tsq_todas
                    or lower(unaccent(r5.nombre)) ~ e.inicio_palabra))
       or similarity(lower(unaccent(c.nombre)), e.texto) > 0.35
       or similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) > 0.35
      , false) as fuerte,
      (case when q is null or q = '' then 1.0
            else
              least(ts_rank(c.busqueda, e.tsq_todas) * 4, 1.0)
              + least(ts_rank(c.busqueda, e.tsq_alguna) * 1.5, 0.4)
              + case when lower(unaccent(c.nombre)) ~ e.inicio_palabra then 0.5 else 0 end
              + case when exists (
                  select 1 from comercio_rubros cr3 join rubros r4 on r4.id = cr3.rubro_id
                  where cr3.comercio_id = c.id
                    and (to_tsvector('spanish_unaccent', r4.nombre) @@ e.tsq_todas
                         or lower(unaccent(r4.nombre)) ~ e.inicio_palabra)
                ) then 0.35 else 0 end
              + similarity(lower(unaccent(c.nombre)), e.texto) * 0.3
              + similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) * 0.25
            end)::real as rank,
      (p_rubro is not null and r.slug = p_rubro) as principal,
      -- Cinco «no me contestó» y ningún «sí»: va al final, no desaparece.
      (coalesce(c.contacto_no, 0) >= 5 and coalesce(c.contacto_ok, 0) = 0) as no_contesta,
      coalesce(c.monedas_aceptadas, '{}') as monedas_aceptadas,
      coalesce(c.envios_internacionales, false) as envios_internacionales,
      coalesce(c.tiene_factura, false) as tiene_factura,
      c.horario, coalesce(c.tiene_stock, true) as tiene_stock,
      ci.nombre as ciudad_nombre, ci.pais as ciudad_pais,
      c.prod_obs_human, c.prod_det_ia,
      coalesce(c.destacado, false) as destacado, coalesce(c.plan, 'gratis') as plan,
      c.portada_thumb_url, c.portada_pos,
      coalesce(c.contacto_ok, 0) as contacto_ok, coalesce(c.contacto_no, 0) as contacto_no
    from comercios c
    cross join entrada e
    left join rubros r on r.id = c.rubro_id
    left join zonas z on z.id = c.zona_id
    left join ciudades ci on ci.id = c.ciudad_id
    left join publicaciones p on p.comercio_id = c.id and p.estado = 'aprobado' and p.activo
    where c.activo
      and not coalesce(c.suspendido, false)
      and (p_rubro is null or exists (
        select 1 from comercio_rubros cr join rubros r2 on r2.id = cr.rubro_id
        where cr.comercio_id = c.id and r2.slug = p_rubro))
      and (p_modalidad is null or c.modalidad = p_modalidad)
      and (p_subcategoria is null
           or strip(to_tsvector('spanish_unaccent', coalesce(c.subcategoria, '')))
              = strip(to_tsvector('spanish_unaccent', p_subcategoria)))
      and (p_zona is null or z.slug = p_zona)
      and (p_ciudad is null or ci.slug = p_ciudad)
      and (p_precio_min is null or p.precio is null or p.precio >= p_precio_min)
      and (p_precio_max is null or p.precio is null or p.precio <= p_precio_max)
      and (
        q is null or q = ''
        or c.busqueda @@ e.tsq_alguna
        or p.busqueda @@ e.tsq_alguna
        or lower(unaccent(c.nombre)) ~ e.inicio_palabra
        or exists (
          select 1 from comercio_rubros cr2 join rubros r3 on r3.id = cr2.rubro_id
          where cr2.comercio_id = c.id
            and (to_tsvector('spanish_unaccent', r3.nombre) @@ e.tsq_todas
                 or lower(unaccent(r3.nombre)) ~ e.inicio_palabra))
        or similarity(lower(unaccent(c.nombre)), e.texto) > 0.35
        or similarity(lower(unaccent(coalesce(c.subcategoria, ''))), e.texto) > 0.35
      )
    order by c.id, fuerte desc, rank desc
  ),
  medidos as (
    select b.*, sum(case when b.fuerte then 1 else 0 end) over () as n_fuertes from base b
  ),
  filtrados as (
    select * from medidos where coalesce(n_fuertes, 0) < 5 or fuerte
  )
  select id, slug, nombre, descripcion, logo_url, portada_url, whatsapp, direccion,
         lat, lng, modalidad, rubro_slug, rubro_nombre, subcategoria, zona_nombre, rating, verificado,
         ofertas, rank, monedas_aceptadas, envios_internacionales, tiene_factura,
         horario, tiene_stock, ciudad_nombre, ciudad_pais,
         prod_obs_human, prod_det_ia,
         destacado, plan, portada_thumb_url, portada_pos,
         contacto_ok, contacto_no,
         count(*) over () as total
    from filtrados order by rank desc, principal desc, no_contesta asc, nombre, id
   limit case when p_limit <= 0 then null else greatest(1, least(p_limit, 500)) end
  offset greatest(0, p_offset);
$$;

grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text)
  to anon, authenticated, service_role;
