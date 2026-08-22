-- Dos correcciones que salieron de medir la cobertura contra datos reales.
--
-- 1) EL ÍNDICE PERDIÓ EL UNACCENT
--
--    El informe mostró "sarten: 5 comercios lo tienen, 0 los encuentra". No era
--    un problema de vocabulario: la columna `busqueda` se construía con
--    to_tsvector('spanish', ...) mientras la consulta usa
--    websearch_to_tsquery('spanish_unaccent', ...). El índice guarda "sartén"
--    con tilde, la búsqueda pregunta por "sarten" sin ella, y no matchean nunca.
--
--    La 0035 lo tenía bien; la 0047 rehizo la columna con 'spanish' a secas al
--    agregar los campos nuevos, y la 0049 arrastró ese error. Afecta a TODA
--    palabra con tilde o ñ: sartén, riñonera, colchón, jabón, muñeca, bañador.
--    Es invisible en las pruebas porque la mayoría de los productos no llevan
--    tilde — justamente por eso hacía falta medir por producto y no por muestra.
--
-- 2) EL RANKING SE APLANABA
--
--    Buscar "ferretería" devolvía los comercios correctos pero TODOS con rank
--    0.350 exacto: el valor fijo del match por nombre de categoría. Como el
--    rank se calculaba con greatest(), esa señal gruesa —"pertenece al rubro"—
--    le ganaba a la señal precisa —"vende esto, dice la palabra"—, que en
--    ts_rank vale décimas. Con todos empatados el orden vuelve a ser
--    alfabético, y arriba aparecen "FedEx" y tres "Comercio" sin nombre.
--
--    Ahora las señales se SUMAN en vez de competir. Pertenecer al rubro pasa a
--    valer poco (0.15): desempata entre iguales, no decide. Y el texto se
--    escala, porque ts_rank sobre documentos cortos devuelve valores chicos que
--    de otro modo nunca superarían a una constante.

-- ── 1. Índice con unaccent ───────────────────────────────────────────────────
alter table comercios drop column if exists busqueda;

alter table comercios add column busqueda tsvector
  generated always as (
    to_tsvector('spanish_unaccent',
      coalesce(nombre, '')         || ' ' ||
      coalesce(descripcion, '')    || ' ' ||
      coalesce(prod_obs_human, '') || ' ' ||
      coalesce(prod_det_ia, '')    || ' ' ||
      coalesce(subcategoria, '')   || ' ' ||
      coalesce(sinonimos, '')      || ' ' ||
      coalesce(direccion, ''))
  ) stored;

create index if not exists idx_comercios_busqueda on comercios using gin (busqueda);


-- ── 2. Ranking por suma de señales ───────────────────────────────────────────
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
            else
              -- Las señales se suman: un comercio que además de pertenecer al
              -- rubro nombra el producto tiene que quedar por encima del que
              -- sólo pertenece al rubro.
              --
              -- ts_rank sobre textos cortos devuelve décimas; sin escalarlo
              -- nunca le ganaría a una constante y el orden lo decidirían los
              -- desempates.
              least(ts_rank(c.busqueda, websearch_to_tsquery('spanish_unaccent', q)) * 4, 1.0)
              + case when unaccent(lower(c.nombre)) like '%' || unaccent(lower(q)) || '%'
                     then 0.5 else 0 end
              -- Pertenecer al rubro es una señal GRUESA: desempata, no decide.
              -- Cuando valía 0.35 y competía por greatest(), aplastaba a todos
              -- en el mismo puntaje y el orden volvía a ser alfabético.
              + case when exists (
                  select 1 from comercio_rubros cr3 join rubros r4 on r4.id = cr3.rubro_id
                  where cr3.comercio_id = c.id
                    and unaccent(lower(r4.nombre)) like '%' || unaccent(lower(q)) || '%'
                ) then 0.15 else 0 end
              + similarity(lower(unaccent(c.nombre)), lower(unaccent(q))) * 0.3
              + similarity(lower(unaccent(coalesce(c.subcategoria, ''))), lower(unaccent(q))) * 0.25
            end)::real as rank,
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
        or exists (
          select 1 from comercio_rubros cr2 join rubros r3 on r3.id = cr2.rubro_id
          where cr2.comercio_id = c.id
            and unaccent(lower(r3.nombre)) like '%' || unaccent(lower(q)) || '%')
        or similarity(lower(unaccent(c.nombre)), lower(unaccent(q))) > 0.35
        or similarity(lower(unaccent(coalesce(c.subcategoria, ''))), lower(unaccent(q))) > 0.35
      )
    order by c.id
  )
  select * from base order by rank desc, nombre
  limit greatest(1, least(p_limit, 60)) offset greatest(0, p_offset);
$$;
grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int) to anon, authenticated;


-- ── 3. Forma canónica de un término, del lado de SQL ─────────────────────────
--
-- El diccionario guarda las claves normalizadas (minúsculas, sin tildes, cada
-- palabra en singular) porque las escribe Python. Cualquier consulta que quiera
-- preguntar "¿este término está en el diccionario?" tiene que normalizar igual,
-- o "remeras" va a figurar como faltante aunque "remera" esté cargada — y el
-- informe exagera el hueco justo donde uno confía en él.
create or replace function termino_normalizado(t text)
returns text
language sql stable
as $$
  select coalesce(string_agg(
    case
      when length(w) <= 3            then w
      when w like '%ces'             then left(w, -3) || 'z'
      when w like '%es' and length(w) > 4 then left(w, -2)
      when w like '%s'               then left(w, -1)
      else w
    end, ' ' order by ord), '')
  from unnest(string_to_array(
         regexp_replace(lower(unaccent(coalesce(t, ''))), '[^a-z0-9 ]+', ' ', 'g'),
         ' ')) with ordinality as u(w, ord)
  where w <> '';
$$;
grant execute on function termino_normalizado(text) to anon, authenticated, service_role;
