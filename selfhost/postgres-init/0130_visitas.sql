-- CUÁNTA GENTE ENTRA AL SITIO
--
-- Hasta hoy URUKU contaba una sola cosa: la visita a la FICHA de un comercio
-- (`leads` con tipo 'vista'). Nadie contaba la home, el buscador, /ofertas,
-- /guia ni /planes. O sea: si alguien entra, busca «zapatillas», no encuentra
-- y se va, eso no existe en ningún lado. Y es justo lo que hace falta para
-- decidir qué contenido hacer y si conviene poner plata en publicidad.
--
-- SIN COOKIES Y SIN IP, a propósito. La «sesión» es un número al azar que vive
-- en la pestaña del navegador (sessionStorage) y se pierde al cerrarla: sirve
-- para no contar diez veces a la misma persona en una recorrida, y no para
-- seguir a nadie. No se guarda IP, ni user-agent, ni nada que identifique a
-- una persona. Por eso tampoco hace falta el cartelito de cookies.
--
-- El día se guarda en HORA DE BOLIVIA. El servidor corre en UTC y son cuatro
-- horas: sin esto, todo lo que pasa después de las 20:00 figura al día
-- siguiente, y los picos de la tarde —cuando cruzan a comprar— se parten en
-- dos días.

create table if not exists visitas (
  id          uuid primary key default gen_random_uuid(),
  dia         date not null default ((now() at time zone 'America/La_Paz')::date),
  ruta        text not null,
  sesion      text not null,
  --: El `?ref=` con el que llegó: un volante, una tarjeta de mesa, un enlace
  --: puesto en Instagram. Es lo que después dice si algo de eso trajo gente.
  origen      text,
  --: SÓLO EL HOST de donde vino (google.com, facebook.com, t.co). La URL
  --: entera puede llevar datos de la otra página y no hace falta para nada.
  referido    text,
  ciudad_slug text,
  --: true en la PRIMERA página de esa sesión. Sumarlo da «cuántas personas»
  --: sin tener que agrupar por sesión cada vez que se mira el panel.
  primera     boolean not null default false,
  created_at  timestamptz not null default now()
);

create index if not exists idx_visitas_dia    on visitas (dia desc);
create index if not exists idx_visitas_ruta   on visitas (ruta);
create index if not exists idx_visitas_sesion on visitas (sesion);

-- Cualquiera puede ANOTAR una visita (la anota el navegador del que entra);
-- leerlas, sólo el backend. Igual que `leads` desde la 0011.
grant select, insert on visitas to anon, authenticated;
grant all             on visitas to service_role;
alter table visitas enable row level security;

drop policy if exists visitas_insert_public on visitas;
create policy visitas_insert_public on visitas
  for insert to anon, authenticated with check (true);

drop policy if exists visitas_select_service on visitas;
create policy visitas_select_service on visitas
  for select to service_role using (true);
