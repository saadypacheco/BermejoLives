-- Adornos del mapa: chalanas y lapachos, puestos a mano donde corresponde.
--
-- Bermejo tiene tres cosas que no tiene ninguna otra ciudad del directorio: las
-- chalanas que cruzan el río hacia Argentina, los lapachos floreciendo en las
-- calles, y el uruku que le da el nombre a la marca. Dibujarlas hace que el
-- mapa se reconozca como Bermejo y no como cualquier grilla de calles.
--
-- POR QUÉ EN LA BASE Y NO EN EL CÓDIGO
--
-- Dónde va cada adorno no es una decisión técnica: hay que conocer la ciudad.
-- Una chalana sobre tierra firme se lee como un error, y un lapacho encima de
-- una cuadra llena de locales tapa justo lo que el mapa existe para mostrar.
-- Quien sabe eso es quien camina Bermejo, no quien escribe el código — así que
-- se marcan haciendo clic en el mapa y se corrigen sin deploy.
--
-- LA REGLA QUE MANDA: el mapa existe para mostrar comercios. Los adornos se
-- dibujan en un panel propio, por debajo de los pines, sin capturar clics y
-- apagados cuando se mira de lejos. Si alguna vez compiten con un local por la
-- atención, el adorno es lo que sobra.

create table if not exists mapa_adornos (
  id         uuid primary key default gen_random_uuid(),
  ciudad_id  uuid references ciudades(id) on delete cascade,
  tipo       text not null check (tipo in ('chalana', 'lapacho')),
  lat        double precision not null,
  lng        double precision not null,
  -- Grados. Las chalanas quedan mejor si no están todas alineadas; los
  -- lapachos no lo usan.
  giro       double precision not null default 0,
  -- 1 = tamaño base. Variarlo evita el efecto de estampilla repetida.
  escala     double precision not null default 1,
  activo     boolean not null default true,
  creado_at  timestamptz not null default now()
);

comment on table mapa_adornos is
  'Chalanas y lapachos dibujados en el mapa. Pura decoración: no son comercios, '
  'no se buscan y no reciben clics. Se ubican desde el admin haciendo clic.';

create index if not exists idx_mapa_adornos_ciudad
  on mapa_adornos (ciudad_id) where activo;

alter table mapa_adornos enable row level security;

drop policy if exists mapa_adornos_lectura on mapa_adornos;
create policy mapa_adornos_lectura on mapa_adornos for select using (activo);

-- El backend escribe con service_role. Sin este grant la tabla existe, psql la
-- lee, y el backend recibe un permiso denegado que desde afuera parece "la
-- tabla no existe" — el error que ya nos costó dos vueltas con producto_sinonimos.
grant all    on public.mapa_adornos to service_role;
grant select on public.mapa_adornos to anon, authenticated;
