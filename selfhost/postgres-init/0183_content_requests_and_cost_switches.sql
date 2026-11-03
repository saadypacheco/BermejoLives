-- 0183 · Pedir un video a mano (negocio o rubro) e interruptores de costo.
--
-- Spec técnica: docs/contenido-redes-tecnico.md §17.1.
--
--  1. cost_switches: una fila por servicio que cuesta plata (hoy sólo 'gemini_content'). Sin fila =
--     apagado. Sólo el backend: RLS activo, revoke a public/anon/authenticated y grant a service_role
--     (como la 0181).
--  2. content_pieces.origin: 'selector' (la semana automática) o 'pedido' (alguien lo pidió a mano).
--     Un pedido no cuenta cuota, no crea tareas y NO ocupa el lugar del calendario.
--  3. content_pieces.rubro_id: el rubro de un video «{Rubro} en {ciudad}» (pillar = 'rubro').
--  4. El pilar suma 'rubro': se reemplaza el check de la 0181 (`content_pieces_pillar_check`, el nombre
--     que Postgres le dio a la restricción de columna) y se exige rubro y ciudad en esas piezas.
--  5. uq_content_pieces_slot pasa a valer sólo para origin = 'selector' (mismo nombre: drop + create).
--
-- PERMISOS: las columnas nuevas de content_pieces heredan el permiso de la tabla (la 0181 la dejó sólo
-- para service_role, sin grants por columna): nacen privadas. El bloque de comprobación lo verifica.
-- Sin borrado físico de filas. Idempotente: se puede correr dos veces.

begin;

-- ───────────────────────────────────────────── 1. interruptores de costo
create table if not exists public.cost_switches (
  key         text primary key check (key in ('gemini_content')),
  enabled     boolean not null default false,
  updated_by  text not null,
  updated_at  timestamptz not null default now()
);

comment on table public.cost_switches is
  'Interruptores de lo que cuesta plata. Una fila por servicio; sin fila = apagado. Sólo el backend.';

alter table public.cost_switches enable row level security;
revoke all on public.cost_switches from public, anon, authenticated;
grant all on public.cost_switches to service_role;

-- ───────────────────────────────────────────── 2. pedidos y videos por rubro
alter table public.content_pieces
  add column if not exists origin   text not null default 'selector',   -- 'selector' | 'pedido'
  add column if not exists rubro_id uuid references public.rubros(id);  -- sólo pillar = 'rubro'

alter table public.content_pieces drop constraint if exists content_pieces_origin_check;
alter table public.content_pieces
  add constraint content_pieces_origin_check check (origin in ('selector', 'pedido'));

-- El pilar suma 'rubro'. Nombre real del check de la 0181: content_pieces_pillar_check.
alter table public.content_pieces drop constraint if exists content_pieces_pillar_check;
alter table public.content_pieces
  add constraint content_pieces_pillar_check check (pillar in ('comercio_del_dia', 'ofertas', 'rubro'));

-- Un video de rubro lleva siempre el rubro y la ciudad.
alter table public.content_pieces drop constraint if exists content_pieces_rubro_check;
alter table public.content_pieces
  add constraint content_pieces_rubro_check
  check (pillar <> 'rubro' or (rubro_id is not null and ciudad_id is not null));

-- Un lugar del calendario = una pieza viva DEL SELECTOR. Los pedidos a mano no ocupan lugar.
drop index if exists public.uq_content_pieces_slot;
create unique index uq_content_pieces_slot
  on public.content_pieces (scheduled_for, pillar)
  where activo and origin = 'selector' and status not in ('skipped', 'failed');

-- Para el tope de pedidos armándose (§17.3).
create index if not exists idx_content_pieces_pedido
  on public.content_pieces (status) where activo and origin = 'pedido';

comment on column public.content_pieces.origin is
  '''selector'' = la semana automática; ''pedido'' = alguien la pidió a mano (sin cuota, sin tareas, sin lugar fijo).';
comment on column public.content_pieces.rubro_id is
  'El rubro de un video «{Rubro} en {ciudad}» (pillar = ''rubro''). Null en las demás piezas.';

-- ───────────────────────────────────────────── comprobación (si algo falla, no queda nada)
do $chk$
declare
  v_rol text;
  v_col text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    if has_table_privilege(v_rol, 'public.cost_switches', 'select')
       or has_table_privilege(v_rol, 'public.cost_switches', 'insert')
       or has_table_privilege(v_rol, 'public.cost_switches', 'update')
       or has_table_privilege(v_rol, 'public.cost_switches', 'delete') then
      raise exception '0183: % tiene permisos sobre cost_switches', v_rol;
    end if;
    foreach v_col in array array['origin', 'rubro_id'] loop
      if has_column_privilege(v_rol, 'public.content_pieces', v_col, 'select') then
        raise exception '0183: % puede leer content_pieces.%', v_rol, v_col;
      end if;
    end loop;
  end loop;
  if not has_table_privilege('service_role', 'public.cost_switches', 'insert')
     or not has_table_privilege('service_role', 'public.cost_switches', 'update') then
    raise exception '0183: service_role no puede escribir cost_switches';
  end if;
  foreach v_col in array array['origin', 'rubro_id'] loop
    if not has_column_privilege('service_role', 'public.content_pieces', v_col, 'update') then
      raise exception '0183: service_role no puede escribir content_pieces.%', v_col;
    end if;
  end loop;
  if not exists (select 1 from pg_constraint
                  where conname = 'content_pieces_pillar_check'
                    and conrelid = 'public.content_pieces'::regclass
                    and pg_get_constraintdef(oid) like '%rubro%') then
    raise exception '0183: el check del pilar no admite ''rubro''';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
