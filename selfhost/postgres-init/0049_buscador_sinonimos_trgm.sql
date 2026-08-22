-- Tres capas del buscador, sobre lo que ya se está recolectando de las fotos.
--
-- 1) NORMALIZACIÓN — `subcategoria_norm`
--    Los datos reales mostraron el problema: "mochilas y bolsos" (2) y "bolsos y
--    mochilas" (2) son lo mismo contado por separado, igual que "juguetería" (7)
--    y "juguetes" (4). Sin normalizar, la subcategoría se fragmenta y ninguna
--    variante llega al umbral para justificar un filtro.
--
-- 2) SINÓNIMOS — `sinonimos`
--    Bermejo es frontera: el comprador argentino escribe "remera" y el boliviano
--    "polera". El FTS en español hace stemming (zapatilla ↔ zapatillas) pero no
--    sabe que son la misma prenda. Los sinónimos los va a escribir la IA mirando
--    las vidrieras, con el vocabulario real del lugar, y se guardan en una
--    columna que entra al índice: buscar "polera" encuentra al que vende
--    "remeras" sin tocar la consulta.
--
-- 3) TOLERANCIA A ERRORES — pg_trgm
--    En un celular los errores de tipeo son constantes. Hoy "ferreteria" con una
--    letra de más devuelve cero. Con trigramas, se parece lo suficiente.

alter table comercios add column if not exists sinonimos text;
alter table comercios add column if not exists subcategoria_norm text;

comment on column comercios.sinonimos is
  'Otras formas de nombrar lo que vende, en vocabulario local (remera/polera/'
  'camiseta). Las propone la IA al analizar las fotos. Entra al índice de '
  'búsqueda: buscar el sinónimo encuentra el comercio.';
comment on column comercios.subcategoria_norm is
  'subcategoria normalizada (minúsculas, sin tildes, singular, términos '
  'ordenados) para agrupar variantes. La escribe la aplicación.';

create index if not exists idx_comercios_subcat_norm
  on comercios (subcategoria_norm) where subcategoria_norm is not null;

-- Los sinónimos entran a la búsqueda como un campo más.
alter table comercios drop column if exists busqueda;

alter table comercios add column busqueda tsvector
  generated always as (
    to_tsvector('spanish',
      coalesce(nombre, '')         || ' ' ||
      coalesce(descripcion, '')    || ' ' ||
      coalesce(prod_obs_human, '') || ' ' ||
      coalesce(prod_det_ia, '')    || ' ' ||
      coalesce(subcategoria, '')   || ' ' ||
      coalesce(sinonimos, '')      || ' ' ||
      coalesce(direccion, ''))
  ) stored;

create index if not exists idx_comercios_busqueda on comercios using gin (busqueda);


-- ── Tolerancia a errores de tipeo ────────────────────────────────────────────
create extension if not exists pg_trgm;

create index if not exists idx_comercios_nombre_trgm
  on comercios using gin (lower(unaccent(nombre)) gin_trgm_ops);
create index if not exists idx_comercios_subcat_trgm
  on comercios using gin (lower(unaccent(coalesce(subcategoria, ''))) gin_trgm_ops);


-- ── Buscador: suma sinónimos y similitud por trigramas ───────────────────────
create or replace function buscar_comercios(
  q text default null, p_rubro text default null, p_modalidad text default null,
  p_zona text default null, p_precio_min numeric default null, p_precio_max numeric default null,
  p_ciudad text default null, p_limit int default 24, p_offset int default 0
)
returns table (
  id uuid, slug text, nombre text, descripcion text, logo_url text, portada_url text,
  whatsapp text, direccion text, lat double precision, lng double precision, modalidad text,
  rubro_slug text, rubro_nombre text, zona_nombre text, rating numeric, verificado boolean,
  ofertas bigint, rank real, monedas_aceptadas text[], envios_internacionales boolean,
  tiene_factura boolean, horario text, tiene_stock boolean, ciudad_nombre text, ciudad_pais text
)
language sql stable
as $$
  with base as (
    select distinct on (c.id)
      c.id, c.slug, c.nombre, c.descripcion, c.logo_url, c.portada_url,
      c.whatsapp, c.direccion, c.lat, c.lng, c.modalidad,
      r.slug as rubro_slug, r.nombre as rubro_nombre, z.nombre as zona_nombre,
      c.rating, c.verificado,
      (select count(*) from publicaciones pp
         where pp.comercio_id = c.id and pp.estado = 'aprobado' and pp.activo) as ofertas,
      (case when q is null or q = '' then 1.0
            else greatest(
              ts_rank(c.busqueda, websearch_to_tsquery('spanish_unaccent', q)),
              case when unaccent(lower(c.nombre)) like '%' || unaccent(lower(q)) || '%' then 0.4 else 0 end,
              -- Match por NOMBRE DE CATEGORÍA. Antes valía 0: buscar "ferretería"
              -- traía las ferreterías correctas, pero todas con rank 0.00, así
              -- que el orden quedaba alfabético y arriba salían "FedEx" y tres
              -- "Comercio" sin nombre. Encontrarlos no alcanza si quedan sextos.
              case when exists (
                select 1 from comercio_rubros cr3 join rubros r4 on r4.id = cr3.rubro_id
                where cr3.comercio_id = c.id
                  and unaccent(lower(r4.nombre)) like '%' || unaccent(lower(q)) || '%'
              ) then 0.35 else 0 end,
              -- La similitud entra al ranking con peso bajo: un match por
              -- parecido nunca debe ganarle a uno exacto, pero sí tiene que
              -- aparecer cuando no hay nada mejor.
              (similarity(lower(unaccent(c.nombre)), lower(unaccent(q))) * 0.3)::real,
              (similarity(lower(unaccent(coalesce(c.subcategoria, ''))), lower(unaccent(q))) * 0.25)::real
            ) end)::real as rank,
      coalesce(c.monedas_aceptadas, '{}') as monedas_aceptadas,
      coalesce(c.envios_internacionales, false) as envios_internacionales,
      coalesce(c.tiene_factura, false) as tiene_factura,
      c.horario, coalesce(c.tiene_stock, true) as tiene_stock,
      ci.nombre as ciudad_nombre, ci.pais as ciudad_pais
    from comercios c
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
      and (p_zona is null or z.slug = p_zona)
      and (p_ciudad is null or ci.slug = p_ciudad)
      and (p_precio_min is null or p.precio >= p_precio_min)
      and (p_precio_max is null or p.precio <= p_precio_max)
      and (
        q is null or q = ''
        or c.busqueda @@ websearch_to_tsquery('spanish_unaccent', q)
        or p.busqueda @@ websearch_to_tsquery('spanish_unaccent', q)
        or unaccent(lower(c.nombre)) like '%' || unaccent(lower(q)) || '%'
        or exists (                                    -- matchea por NOMBRE DE CATEGORÍA (todas)
          select 1 from comercio_rubros cr2 join rubros r3 on r3.id = cr2.rubro_id
          where cr2.comercio_id = c.id
            and unaccent(lower(r3.nombre)) like '%' || unaccent(lower(q)) || '%')
        -- Errores de tipeo: "ferreteia", "jugeteria". Umbral 0.35 — más bajo
        -- empieza a traer cualquier cosa.
        or similarity(lower(unaccent(c.nombre)), lower(unaccent(q))) > 0.35
        or similarity(lower(unaccent(coalesce(c.subcategoria, ''))), lower(unaccent(q))) > 0.35
      )
    order by c.id
  )
  select * from base order by rank desc, nombre
  limit greatest(1, least(p_limit, 60)) offset greatest(0, p_offset);
$$;
grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int) to anon, authenticated;
