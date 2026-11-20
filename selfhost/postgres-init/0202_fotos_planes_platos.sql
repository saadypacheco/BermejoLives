-- 0202 · Fotos de tarjeta, bodegas y platos típicos (docs/home-ciudades.md, parte 2: §11, §13 y §15).
--
--  1. `comercios.portada_card_url` y `comercios.portada_calidad`: la versión «tarjeta» (800 x 600, 4:3, ya mejorada)
--     de la portada y su puntaje de calidad (0 a 100) para ordenar los carruseles. Las dos son PÚBLICAS (el sitio
--     las lee): regla 11 de AGENTS.md, una columna nueva de `comercios` nace privada para anon y se da por columna.
--  2. `buscar_comercios` devuelve además esas dos columnas (se borra y se vuelve a crear: cambia lo que devuelve;
--     todo lo demás es idéntico a la 0186, con los mismos permisos).
--  3. Rubro comercial `bodegas` («Bodegas y vinotecas») con sus palabras (sin tildes, como fija la 0097) y las
--     bodegas de la página de turismo que están sin revisar pasan a ese rubro (antes caían en `bebidas`).
--  4. Tabla `platos_tipicos` (§15): los platos, la repostería y las bebidas típicas de cada ciudad. Entran
--     `pendiente` y una persona los aprueba. RLS: el público sólo lee `estado = 'aprobado' and activo`; el backend
--     (service_role) lee, inserta y actualiza, sin DELETE (borrado lógico con `activo`).
--  5. Interruptor de costo `gemini_gastronomia` (apagado): escribir las descripciones con Gemini cuesta plata.
--
-- Sin borrado físico. Idempotente: se puede correr dos veces. Copia idéntica en supabase/migrations/ y
-- selfhost/postgres-init/.

begin;

-- ───────────────────────────────────────────── 1. las dos columnas de la tarjeta, públicas por columna
alter table public.comercios add column if not exists portada_card_url text;
alter table public.comercios add column if not exists portada_calidad smallint;
comment on column public.comercios.portada_card_url is
  'Versión tarjeta de la portada: 800 x 600 (4:3), recortada según portada_pos, mejorada y en JPEG. La usan los carruseles.';
comment on column public.comercios.portada_calidad is
  'Puntaje de la portada tarjeta, 0 a 100 (colorido, nitidez y luz media). Sin IA. Ordena los carruseles.';
grant select (portada_card_url) on public.comercios to anon, authenticated;
grant select (portada_calidad) on public.comercios to anon, authenticated;

-- ───────────────────────────────────────────── 2. buscar_comercios devuelve las dos columnas nuevas
-- Cambia el tipo de lo que devuelve: `create or replace` no alcanza, hay que borrarla. Mismos permisos que la 0186.
drop function if exists public.buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text);

create function public.buscar_comercios(
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
  total bigint,
  estrella boolean, plan_orden int,
  horario_estimado boolean,
  portada_card_url text, portada_calidad smallint
)
language sql stable
security definer
set search_path = public, pg_temp
as $$
  with entrada as (
    select
      (now() at time zone 'America/La_Paz')::date as hoy,      -- el «hoy» de Bolivia
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
            select 1 from comercio_rubros cr4 join rubros r5 on r5.id = cr4.rubro_id and r5.activo
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
                  select 1 from comercio_rubros cr3 join rubros r4 on r4.id = cr3.rubro_id and r4.activo
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
      coalesce(c.contacto_ok, 0) as contacto_ok, coalesce(c.contacto_no, 0) as contacto_no,
      coalesce(c.plan_cortesia, false) as plan_cortesia, c.paga_hasta,
      coalesce(c.suspendido, false) as suspendido, e.hoy,
      coalesce(c.horario_estimado, false) as horario_estimado,
      c.portada_card_url, c.portada_calidad
    from comercios c
    cross join entrada e
    left join rubros r on r.id = c.rubro_id and r.activo
    left join zonas z on z.id = c.zona_id and z.activo
    left join ciudades ci on ci.id = c.ciudad_id
    left join publicaciones p on p.comercio_id = c.id and p.estado = 'aprobado' and p.activo
    where c.activo
      and not coalesce(c.suspendido, false)
      and (p_rubro is null or exists (
        select 1 from comercio_rubros cr join rubros r2 on r2.id = cr.rubro_id and r2.activo
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
          select 1 from comercio_rubros cr2 join rubros r3 on r3.id = cr2.rubro_id and r3.activo
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
  ),
  -- El orden del plan se calcula SOLO para los que quedaron (no por cada fila de
  -- la unión con publicaciones), y `planes_orden()` se une UNA vez: el ranking de
  -- precios no se recalcula por comercio. «Al día» = cortesía, o paga_hasta de hoy
  -- (Bolivia) en adelante; suspendido = sin estrella, también la cortesía. Es la
  -- misma regla de `plan_orden_de`. Ningún precio sale de acá.
  con_plan as (
    select f.*,
           case when f.suspendido
                  or not (f.plan_cortesia or (f.paga_hasta is not null and f.paga_hasta >= f.hoy))
                then 0
                else coalesce(po.orden, 0)
           end as plan_orden
      from filtrados f
      left join public.planes_orden() po on po.slug = f.plan
  )
  select id, slug, nombre, descripcion, logo_url, portada_url, whatsapp, direccion,
         lat, lng, modalidad, rubro_slug, rubro_nombre, subcategoria, zona_nombre, rating, verificado,
         ofertas, rank, monedas_aceptadas, envios_internacionales, tiene_factura,
         horario, tiene_stock, ciudad_nombre, ciudad_pais,
         prod_obs_human, prod_det_ia,
         destacado, plan, portada_thumb_url, portada_pos,
         contacto_ok, contacto_no,
         count(*) over () as total,
         (plan_orden > 0) as estrella, plan_orden,
         horario_estimado, portada_card_url, portada_calidad
    from con_plan order by rank desc, plan_orden desc, principal desc, no_contesta asc, nombre, id
   -- Sin límite NO existe: 0, negativo o nulo = la página normal (24); el tope es 500
   -- (el mapa pide de a 500 con p_offset).
   limit greatest(1, least(case when coalesce(p_limit, 0) <= 0 then 24 else p_limit end, 500))
  offset greatest(0, p_offset);
$$;


revoke execute on function public.buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text) from public;
grant  execute on function public.buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text)
  to anon, authenticated, service_role;

-- ───────────────────────────────────────────── 3. el rubro «Bodegas y vinotecas»
insert into public.rubros (slug, nombre, icono, orden, comercial)
values ('bodegas', 'Bodegas y vinotecas', null, 64, true)
on conflict (slug) do update set nombre = excluded.nombre, comercial = true, activo = true;

-- Sin tildes ni ñ (0097): el texto se desacentúa antes de comparar, el patrón no. `bebidas` no se toca: sigue con
-- `vino`, `singani`, etc. Un término no puede estar en dos rubros (test_diccionario_rubros): acá van sólo los propios.
insert into public.rubro_palabras (rubro_slug, patron) values
  ('bodegas', '\m(bodega|vinoteca|vinedo|singani artesanal|cata de vinos)')
on conflict (rubro_slug, patron) do nothing;

-- Las bodegas de la página de turismo que todavía nadie revisó pasan de `bebidas` a `bodegas`. La subcategoría
-- (`bodegas-y-vinotecas`) está en `categoria` y en `tags.turismo.subcategoria`. Lo ya promovido o descartado no se toca.
update public.comercios_importados
   set rubro_slug = 'bodegas'
 where fuente = 'turismo'
   and estado = 'nuevo'
   and (categoria = 'bodegas-y-vinotecas' or tags #>> '{turismo,subcategoria}' = 'bodegas-y-vinotecas')
   and rubro_slug is distinct from 'bodegas';

-- ───────────────────────────────────────────── 4. platos típicos
create table if not exists public.platos_tipicos (
  id          uuid primary key default gen_random_uuid(),
  ciudad_id   uuid not null references public.ciudades(id),
  tipo        text not null check (tipo in ('plato', 'reposteria', 'bebida')),
  nombre      text not null,
  descripcion text,
  fuente_url  text,
  estado      text not null default 'pendiente' check (estado in ('pendiente', 'aprobado', 'rechazado')),
  activo      boolean not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  unique (ciudad_id, nombre)
);
comment on table public.platos_tipicos is
  'Platos, repostería y bebidas típicas de cada ciudad (/{ciudad}/sabores). Entran pendientes; una persona los aprueba.';
comment on column public.platos_tipicos.descripcion is
  'Texto ORIGINAL de 2 a 3 frases (escrito con IA a partir de datos, nunca copiado de la fuente).';
comment on column public.platos_tipicos.fuente_url is 'Enlace a la nota de origen (sólo el enlace; el texto de la nota no se guarda).';
comment on column public.platos_tipicos.activo is 'Borrado lógico: nunca se borra una fila.';

create index if not exists idx_platos_tipicos_ciudad_estado on public.platos_tipicos (ciudad_id, estado) where activo;

alter table public.platos_tipicos enable row level security;

drop policy if exists platos_tipicos_lectura_publica on public.platos_tipicos;
create policy platos_tipicos_lectura_publica on public.platos_tipicos
  for select to anon, authenticated
  using (estado = 'aprobado' and activo);

-- Los privilegios por defecto del esquema (0090) le dan todo a service_role: se le saca todo y se le da sólo lo que
-- usa el backend (leer, insertar y actualizar). Sin DELETE ni TRUNCATE.
revoke all on public.platos_tipicos from public, anon, authenticated, service_role;
grant select on public.platos_tipicos to anon, authenticated;
grant select, insert, update on public.platos_tipicos to service_role;

-- ───────────────────────────────────────────── 5. interruptor de costo
alter table public.cost_switches drop constraint if exists cost_switches_key_check;
alter table public.cost_switches
  add constraint cost_switches_key_check
  check (key in ('gemini_content', 'gemini_phone_scan', 'gemini_tarjetas', 'gemini_gastronomia'));

insert into public.cost_switches (key, enabled, updated_by)
values ('gemini_gastronomia', false, 'migracion 0202')
on conflict (key) do nothing;

-- ───────────────────────────────────────────── 6. comprobación (si algo falla, no queda nada)
do $chk$
declare
  v_rol text;
  v_col text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    foreach v_col in array array['portada_card_url', 'portada_calidad'] loop
      if not has_column_privilege(v_rol, 'public.comercios', v_col, 'select') then
        raise exception '0202: % no puede leer comercios.%', v_rol, v_col;
      end if;
    end loop;
    if not has_table_privilege(v_rol, 'public.platos_tipicos', 'select') then
      raise exception '0202: % no puede leer platos_tipicos', v_rol;
    end if;
    if has_table_privilege(v_rol, 'public.platos_tipicos', 'insert')
       or has_table_privilege(v_rol, 'public.platos_tipicos', 'update')
       or has_table_privilege(v_rol, 'public.platos_tipicos', 'delete') then
      raise exception '0202: % puede escribir en platos_tipicos y es sólo lectura', v_rol;
    end if;
    if not has_function_privilege(v_rol, 'public.buscar_comercios(text, text, text, text, numeric, numeric, text, int, int, text)', 'execute') then
      raise exception '0202: % no puede ejecutar buscar_comercios', v_rol;
    end if;
  end loop;
  if not has_table_privilege('service_role', 'public.platos_tipicos', 'select')
     or not has_table_privilege('service_role', 'public.platos_tipicos', 'insert')
     or not has_table_privilege('service_role', 'public.platos_tipicos', 'update') then
    raise exception '0202: service_role no puede leer, insertar y actualizar platos_tipicos';
  end if;
  if has_table_privilege('service_role', 'public.platos_tipicos', 'delete')
     or has_table_privilege('service_role', 'public.platos_tipicos', 'truncate') then
    raise exception '0202: service_role puede borrar o vaciar platos_tipicos y no tiene que poder';
  end if;
  if not (select relrowsecurity from pg_class where oid = 'public.platos_tipicos'::regclass) then
    raise exception '0202: platos_tipicos sin RLS';
  end if;
  if not exists (select 1 from public.rubros where slug = 'bodegas' and comercial and activo) then
    raise exception '0202: el rubro bodegas no quedó comercial y activo';
  end if;
  if not exists (select 1 from public.rubro_palabras where rubro_slug = 'bodegas') then
    raise exception '0202: faltan las palabras de bodegas';
  end if;
  if exists (select 1 from public.comercios_importados
              where fuente = 'turismo' and estado = 'nuevo' and categoria = 'bodegas-y-vinotecas'
                and rubro_slug is distinct from 'bodegas') then
    raise exception '0202: quedaron bodegas de turismo sin el rubro bodegas';
  end if;
  if not exists (select 1 from pg_constraint
                  where conname = 'cost_switches_key_check'
                    and conrelid = 'public.cost_switches'::regclass
                    and pg_get_constraintdef(oid) like '%gemini_gastronomia%') then
    raise exception '0202: el check de cost_switches no admite gemini_gastronomia';
  end if;
  if exists (select 1 from public.cost_switches where key = 'gemini_gastronomia' and enabled) then
    raise exception '0202: gemini_gastronomia tiene que nacer apagado';
  end if;
  -- buscar_comercios devuelve las columnas nuevas y sigue respetando el tope de filas
  perform portada_card_url, portada_calidad from public.buscar_comercios(p_limit => 1);
  if (select count(*) from public.buscar_comercios(p_limit => 0)) > 24 then
    raise exception '0202: buscar_comercios(p_limit=0) devolvió más de 24 filas';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
