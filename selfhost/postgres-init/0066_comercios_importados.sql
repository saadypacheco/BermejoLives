-- Comercios traídos de fuentes externas, en su propia tabla.
--
-- POR QUÉ NO ENTRAN DIRECTO A `comercios`
-- ======================================
--
-- Un comercio de URUKU es un local que alguien caminó: tiene foto de la
-- vidriera, rubro deducido de lo que se ve, y muchas veces el WhatsApp del
-- dueño. Un registro importado tiene nombre, punto en el mapa y poco más.
--
-- Medido contra Overpass el 2026-08-26, sobre 19.861 negocios de las cinco
-- ciudades: **91 tienen foto** (0,5%) y **212 tienen WhatsApp** (1%). Teléfono,
-- el 9%. Si eso entrara al mapa mezclado con lo relevado, el comprador tocaría
-- pines que no llevan a ningún lado y dejaría de confiar en los que sí — el
-- mismo daño que hacía un rubro de más, multiplicado por miles.
--
-- Así que viven acá, se revisan en el panel, y **pasan al mapa de a uno**.
-- Mientras tanto sirven para lo que mejor sirven: decirle al equipo de campo
-- qué negocios existen y todavía no están cargados.
--
-- SOBRE LA LICENCIA
-- =================
--
-- `fuente` no es decoración. OpenStreetMap es ODbL: se puede usar y
-- redistribuir CON ATRIBUCIÓN. Google Places, HERE y Mapbox prohíben almacenar
-- sus datos y mostrarlos fuera de su mapa — en cualquier plan, pagando o no —
-- así que de esas fuentes no puede entrar nada acá. Guardar de dónde salió cada
-- registro es lo que permite responder eso después sin adivinar.

create table if not exists comercios_importados (
  id          uuid primary key default gen_random_uuid(),
  fuente      text not null default 'osm',       -- 'osm' | (futuras)
  fuente_id   text not null,                     -- 'node/1234567' — para no traer dos veces lo mismo
  ciudad_id   uuid references ciudades(id) on delete set null,

  nombre      text,
  categoria   text,                              -- el tag crudo: shop=bakery, amenity=pharmacy
  rubro_slug  text,                              -- traducido a la taxonomía de URUKU (puede ser null)
  lat         double precision,
  lng         double precision,

  telefono    text,
  whatsapp    text,
  website     text,
  horario     text,
  direccion   text,
  tags        jsonb,                             -- todo lo que vino, sin recortar

  -- 'nuevo' → sin revisar · 'promovido' → ya es un comercio de URUKU
  -- 'descartado' → mirado y no sirve (cerrado, duplicado, fuera de rubro)
  estado      text not null default 'nuevo'
              check (estado in ('nuevo', 'promovido', 'descartado')),
  comercio_id uuid references comercios(id) on delete set null,

  -- Un candidato a que YA esté cargado: mismo nombre parecido y a menos de
  -- 120 m. Sin esto el equipo de campo revisa doscientas fichas que ya tiene.
  duplicado_de uuid references comercios(id) on delete set null,

  motivo      text,                              -- por qué se descartó
  importado_at timestamptz not null default now(),
  revisado_por text,
  revisado_at  timestamptz,

  -- La clave del asunto: reimportar la misma ciudad no duplica ni pisa lo que
  -- ya se revisó. El importador hace upsert sobre esto y no toca `estado`.
  unique (fuente, fuente_id)
);

create index if not exists idx_importados_estado  on comercios_importados(estado);
create index if not exists idx_importados_ciudad  on comercios_importados(ciudad_id, estado);
create index if not exists idx_importados_nombre  on comercios_importados(lower(nombre));

alter table comercios_importados enable row level security;
grant all on public.comercios_importados to service_role;
-- Sin grant a anon: esto NO es contenido público hasta que alguien lo promueva.
-- Un registro importado sin revisar puede estar cerrado hace dos años.
