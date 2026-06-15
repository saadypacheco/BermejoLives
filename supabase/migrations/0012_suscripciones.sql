-- ============================================================
-- Bermejo Live Market · 0012_suscripciones
-- Sistema de suscripciones mensual con gracia de 5 días.
-- El admin registra el pago (comprobante QR por WhatsApp).
-- Comercios suspendidos quedan ocultos en búsquedas.
-- ============================================================

-- 1. Campos de suscripción en comercios
alter table comercios add column if not exists paga_hasta  date;
alter table comercios add column if not exists suspendido  boolean not null default false;

create index if not exists idx_comercios_suspendido on comercios (suspendido) where activo;
create index if not exists idx_comercios_paga_hasta on comercios (paga_hasta) where activo;

-- 2. Tabla de pagos registrados por el admin
create table if not exists pagos (
  id             uuid        primary key default gen_random_uuid(),
  comercio_id    uuid        not null references comercios(id) on delete cascade,
  monto          numeric(10,2) not null,
  moneda         text        not null default 'BOB',
  metodo         text        not null default 'qr-bolivia',  -- 'qr-bolivia' | 'efectivo' | 'transferencia'
  referencia     text,           -- número de comprobante / descripción
  periodo_desde  date        not null,
  periodo_hasta  date        not null,
  registrado_por text        not null,   -- email del admin
  notas          text,
  created_at     timestamptz not null default now()
);

create index if not exists idx_pagos_comercio on pagos (comercio_id);
create index if not exists idx_pagos_fecha    on pagos (created_at desc);

-- RLS: solo service_role lee y escribe pagos
grant all on pagos to service_role;
alter table pagos enable row level security;
drop policy if exists pagos_service_all on pagos;
create policy pagos_service_all on pagos
  for all to service_role using (true) with check (true);

-- 3. Actualizar buscar_comercios: excluir suspendidos
drop function if exists buscar_comercios(text, text, text, text, numeric, numeric, text, int, int);
create or replace function buscar_comercios(
  q                     text    default null,
  p_rubro               text    default null,
  p_modalidad           text    default null,
  p_zona                text    default null,
  p_precio_min          numeric default null,
  p_precio_max          numeric default null,
  p_ciudad              text    default null,
  p_limit               int     default 24,
  p_offset              int     default 0
)
returns table (
  id                    uuid,
  slug                  text,
  nombre                text,
  descripcion           text,
  logo_url              text,
  portada_url           text,
  whatsapp              text,
  direccion             text,
  lat                   double precision,
  lng                   double precision,
  modalidad             text,
  rubro_slug            text,
  rubro_nombre          text,
  zona_nombre           text,
  rating                numeric,
  verificado            boolean,
  ofertas               bigint,
  rank                  real,
  monedas_aceptadas     text[],
  envios_internacionales boolean,
  tiene_factura         boolean,
  horario               text,
  tiene_stock           boolean,
  ciudad_nombre         text,
  ciudad_pais           text
)
language sql stable
as $$
  with base as (
    select distinct on (c.id)
      c.id, c.slug, c.nombre, c.descripcion, c.logo_url, c.portada_url,
      c.whatsapp, c.direccion, c.lat, c.lng, c.modalidad,
      r.slug   as rubro_slug,   r.nombre as rubro_nombre,
      z.nombre as zona_nombre,
      c.rating, c.verificado,
      (select count(*) from publicaciones pp
         where pp.comercio_id = c.id and pp.estado = 'aprobado' and pp.activo) as ofertas,
      (case when q is null or q = '' then 1.0
            else ts_rank(c.busqueda, websearch_to_tsquery('spanish', q)) end)::real as rank,
      coalesce(c.monedas_aceptadas,      '{}')  as monedas_aceptadas,
      coalesce(c.envios_internacionales, false)  as envios_internacionales,
      coalesce(c.tiene_factura,          false)  as tiene_factura,
      c.horario,
      coalesce(c.tiene_stock,            true)   as tiene_stock,
      ci.nombre as ciudad_nombre,
      ci.pais   as ciudad_pais
    from comercios c
    left join rubros   r  on r.id  = c.rubro_id
    left join zonas    z  on z.id  = c.zona_id
    left join ciudades ci on ci.id = c.ciudad_id
    left join publicaciones p
      on p.comercio_id = c.id and p.estado = 'aprobado' and p.activo
    where c.activo
      and not coalesce(c.suspendido, false)          -- excluir suspendidos por falta de pago
      and (p_rubro is null or exists (
        select 1 from comercio_rubros cr join rubros r2 on r2.id = cr.rubro_id
        where cr.comercio_id = c.id and r2.slug = p_rubro))
      and (p_modalidad  is null or c.modalidad  = p_modalidad)
      and (p_zona       is null or z.slug       = p_zona)
      and (p_ciudad     is null or ci.slug      = p_ciudad)
      and (p_precio_min is null or p.precio    >= p_precio_min)
      and (p_precio_max is null or p.precio    <= p_precio_max)
      and (
        q is null or q = ''
        or c.busqueda @@ websearch_to_tsquery('spanish', q)
        or p.busqueda @@ websearch_to_tsquery('spanish', q)
      )
    order by c.id
  )
  select * from base order by rank desc, nombre
  limit greatest(1, least(p_limit, 60)) offset greatest(0, p_offset);
$$;

grant execute on function buscar_comercios(text, text, text, text, numeric, numeric, text, int, int)
  to anon, authenticated;
