-- 0032: contenido editable de la home Inicio.
--   cotizaciones          → dólar/peso/boliviano, carga MANUAL (cambistas) desde el panel.
--   clima                 → open-meteo (backend) con override manual del admin.
--   videos_promocionales  → "Recorrimos Bermejo" (videos de zonas), carga admin/publicador.

-- Cotizaciones de la calle (cambistas). El admin/publicador edita `valor` a diario.
create table if not exists cotizaciones (
  clave          text primary key,        -- 'usd_bob' | 'ars_bob' | 'usd_ars' ...
  etiqueta       text not null,           -- 'Dólar', 'Peso argentino'
  detalle        text,                    -- '1 USD', 'cada 100 ARS'
  valor          numeric(14,4),
  unidad         text,                    -- 'Bs', 'ARS'
  orden          smallint not null default 0,
  actualizado_en timestamptz not null default now()
);

-- Clima de Bermejo. Lo actualiza open-meteo (backend); el admin puede corregirlo
-- (override) cuando no coincide con la realidad, y no se pisa hasta override_hasta.
create table if not exists clima (
  id             smallint primary key default 1,
  temp_c         numeric(4,1),
  descripcion    text,
  icono          text,                    -- emoji/código
  fuente         text default 'open-meteo',
  override_hasta timestamptz,
  actualizado_en timestamptz not null default now(),
  constraint clima_single_row check (id = 1)
);

-- Videos promocionales de zonas de Bermejo ("Recorrimos Bermejo"). Contenido propio.
create table if not exists videos_promocionales (
  id         uuid primary key default gen_random_uuid(),
  titulo     text,
  url        text not null,
  orden      smallint not null default 0,
  activo     boolean not null default true,
  created_at timestamptz not null default now()
);

-- RLS + lectura pública (la home los lee vía anon); escritura solo backend (service_role).
alter table cotizaciones          enable row level security;
alter table clima                 enable row level security;
alter table videos_promocionales  enable row level security;

grant all    on public.cotizaciones         to service_role;
grant all    on public.clima                to service_role;
grant all    on public.videos_promocionales to service_role;
grant select on public.cotizaciones         to anon, authenticated;
grant select on public.clima                to anon, authenticated;
grant select on public.videos_promocionales to anon, authenticated;

drop policy if exists cotizaciones_public_read on cotizaciones;
create policy cotizaciones_public_read on cotizaciones for select to anon, authenticated using (true);
drop policy if exists clima_public_read on clima;
create policy clima_public_read on clima for select to anon, authenticated using (true);
drop policy if exists videos_promo_public_read on videos_promocionales;
create policy videos_promo_public_read on videos_promocionales for select to anon, authenticated using (activo);

-- Seed: cotizaciones en 0 (el admin carga los valores reales) + fila única de clima.
insert into cotizaciones (clave, etiqueta, detalle, valor, unidad, orden) values
  ('usd_bob', 'Dólar',          '1 USD',      0, 'Bs',  1),
  ('ars_bob', 'Peso argentino', '100 ARS',    0, 'Bs',  2),
  ('usd_ars', 'Dólar',          '1 USD',      0, 'ARS', 3)
on conflict (clave) do nothing;

insert into clima (id) values (1) on conflict (id) do nothing;
