-- Los planes viven en la base, no en el código.
--
-- POR QUÉ
-- =======
-- Hoy los planes están en tres lugares que no se hablan: un CHECK en
-- `comercios.plan` que sólo acepta gratis/pro/premium, un set en Python
-- (`_PLANES`), y la página de venta que ofrece Básico, Publica, Destacado y
-- Pro. Son dos vocabularios distintos para lo mismo, y ninguno de los dos
-- cuenta las publicaciones que promete.
--
-- Un precio, una cuota o el nombre de un plan cambian por razones comerciales
-- —una promoción, un competidor, una charla con un comerciante— y eso no puede
-- necesitar un programador y un deploy. Quien vende tiene que poder cambiarlo.
--
-- LAS FUNCIONES VAN EN JSONB A PROPÓSITO
-- ======================================
-- "Agregar una función más al plan Pro" no puede ser una migración. Con `jsonb`
-- se agrega una clave y listo. Lo que el código consulta por nombre —hoy
-- `asistente_24_7`— vive ahí, y una función que todavía no existe simplemente
-- no está en el objeto: `funcion(plan, "x")` devuelve falso, que es el
-- comportamiento seguro.

create table if not exists planes (
  slug                      text primary key,
  nombre                    text not null,
  orden                     int  not null default 0,
  precio_mes                numeric(10,2) not null default 0,
  moneda                    text not null default 'BOB',

  -- null = sin límite. Es distinto de 0, que sería "no puede publicar".
  publicaciones_mes         int,

  -- Lo que se cobra por pasarse. Va acá y no en el .env justamente porque va a
  -- cambiar: lo cambia quien vende, no quien hace deploy.
  precio_publicacion_extra  numeric(10,2) not null default 5,

  -- Si es false, al llegar al tope se corta y se ofrece subir de plan en vez
  -- de cobrar la extra. Los dos caminos son válidos y la decisión es comercial.
  permite_extras            boolean not null default true,

  funciones                 jsonb not null default '{}'::jsonb,
  descripcion               text,
  activo                    boolean not null default true,
  visible                   boolean not null default true,   -- si sale en la página de planes
  created_at                timestamptz not null default now(),
  updated_at                timestamptz not null default now()
);

-- Los planes que se venden hoy (docs/pendientes-uruku.md).
insert into planes (slug, nombre, orden, precio_mes, publicaciones_mes,
                    precio_publicacion_extra, funciones, descripcion, visible)
values
  ('gratis',   'Básico',    0,   0,  10, 5, '{}'::jsonb,
   'El primer mes. Después pasa a Publica.', true),
  ('publica',  'Publica',   1,  70,  15, 5, '{}'::jsonb,
   'Publicá tus ofertas todo el mes.', true),
  ('destacado','Destacado', 2, 140,  50, 5, '{"canal_wa": true}'::jsonb,
   'Más publicaciones y lugar en el canal de WhatsApp.', true),
  ('pro',      'Pro',       3, 400,  50, 5,
   '{"canal_wa": true, "asistente_24_7": true}'::jsonb,
   'Todo lo anterior más atención 24/7 de tu WhatsApp con IA.', true)
on conflict (slug) do nothing;

-- `premium` existe en datos viejos. Se conserva para no romper filas que ya lo
-- tienen, oculto de la página de venta. Borrarlo dejaría comercios apuntando a
-- un plan inexistente, que es peor que un plan de más.
insert into planes (slug, nombre, orden, precio_mes, publicaciones_mes, funciones, visible)
values ('premium', 'Premium (viejo)', 9, 140, 50,
        '{"canal_wa": true}'::jsonb, false)
on conflict (slug) do nothing;

-- El CHECK se va: era la razón por la que no se podía agregar un plan sin
-- migrar. Lo reemplaza la clave foránea, que dice lo mismo pero se actualiza
-- sola cuando se crea un plan nuevo.
--
-- SE BUSCA POR COLUMNA Y NO POR NOMBRE, A PROPÓSITO
-- =================================================
-- `drop constraint if exists comercios_plan_check` depende de que Postgres le
-- haya puesto ese nombre exacto. Si se llamara de otra forma, el DROP no
-- encuentra nada, no da error, y la migración termina "bien" dejando el candado
-- puesto: los planes nuevos se rechazarían al asignarlos, meses después, sin
-- que nada apunte a esta línea. Es la guarda que se lee como protección y no
-- protege.
--
-- Buscarlo por la columna que restringe lo encuentra se llame como se llame.
do $$
declare c record;
begin
  for c in
    select con.conname
      from pg_constraint con
      join pg_class      rel on rel.oid = con.conrelid
      join pg_namespace  nsp on nsp.oid = rel.relnamespace
      join pg_attribute  att on att.attrelid = rel.oid and att.attname = 'plan'
     where rel.relname = 'comercios'
       and nsp.nspname = 'public'
       and con.contype = 'c'
       and att.attnum = any (con.conkey)
  loop
    raise notice 'quitando el CHECK % de comercios.plan', c.conname;
    execute format('alter table public.comercios drop constraint %I', c.conname);
  end loop;
end $$;

-- Antes de atar la clave foránea: si algún comercio apunta a un plan que no
-- existe, el ALTER falla con un mensaje que no dice cuál. Mejor decirlo acá.
do $$
declare huerfanos text;
begin
  select string_agg(distinct coalesce(c.plan, '(nulo)'), ', ')
    into huerfanos
    from comercios c
    left join planes p on p.slug = c.plan
   where p.slug is null;

  if huerfanos is not null then
    raise exception 'Hay comercios con planes que no existen en la tabla planes: %. '
                    'Agregalos a planes o corregí esas filas antes de seguir.', huerfanos;
  end if;
end $$;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'comercios_plan_fkey') then
    alter table comercios
      add constraint comercios_plan_fkey foreign key (plan) references planes(slug);
  end if;
end $$;

-- ── Los cargos por publicación extra ────────────────────────────────────────
--
-- Un cargo que se calcula a mano se cobra dos veces o no se cobra nunca. Cada
-- publicación que se pasó del tope deja su fila, con el precio VIGENTE EN ESE
-- MOMENTO: si mañana la extra sale 7, lo ya generado sigue valiendo 5. Cobrar
-- retroactivo un precio que cambió después es cómo se pierde la confianza de un
-- comerciante.
create table if not exists cargos_extra (
  id             uuid primary key default gen_random_uuid(),
  comercio_id    uuid not null references comercios(id) on delete cascade,
  publicacion_id uuid references publicaciones(id) on delete set null,
  concepto       text not null default 'publicacion_extra',
  monto          numeric(10,2) not null,
  moneda         text not null default 'BOB',
  estado         text not null default 'pendiente'
                   check (estado in ('pendiente','cobrado','anulado')),
  cobrado_en     timestamptz,
  notas          text,
  created_at     timestamptz not null default now(),
  unique (publicacion_id)
);

create index if not exists idx_cargos_comercio on cargos_extra (comercio_id, estado);

alter table planes enable row level security;
alter table cargos_extra enable row level security;
grant all on public.planes to service_role;
grant all on public.cargos_extra to service_role;

-- Los planes SÍ son públicos: la página de venta los lee sin estar logueada.
grant select on public.planes to anon, authenticated;
drop policy if exists planes_public_read on planes;
create policy planes_public_read on planes
  for select to anon, authenticated using (activo);

-- Los cargos no: dicen cuánto debe cada comercio.
