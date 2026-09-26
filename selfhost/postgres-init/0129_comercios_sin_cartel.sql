-- LOS QUE NO TIENEN NOMBRE
--
-- 555 de 1.248 comercios se llaman «Comercio 437». No están mal cargados: en
-- Bermejo un puesto de galería no tiene cartel y el dueño no le puso nombre a
-- nada. El panel los marcaba «sin nombre» —un defecto que no se puede
-- arreglar— y el comprador veía una ficha llamada «Comercio 437», que no le
-- dice absolutamente nada.
--
-- Lo que SÍ tienen: 554 de esos 555 tienen `subcategoria` (lo que la IA vio en
-- la vidriera: «jean», «petshop», «ropa femenina»), los 555 tienen `calle`
-- (migración 0127) y 111 están dentro de una galería, 45 con número de puesto.
-- Con eso alcanza para llamarlos por lo único que importa: qué venden y dónde
-- están.
--
--     Comercio 437   →   Ropa femenina · Calle 23 de Marzo
--     Comercio 902   →   Valijas · Galería Nuevo Amanecer - pasillo Tarija, 55
--
-- Se arma en un TRIGGER y no en la aplicación a propósito. El nombre se usa en
-- la búsqueda, en la ficha, en el pin del mapa, en el texto que se precarga en
-- WhatsApp, en el título de la página y en el sitemap: armarlo en un lugar y
-- que el resto no se entere de nada es la única forma de que no queden tres
-- versiones distintas del mismo nombre. Y como `busqueda` es una columna
-- GENERADA sobre `nombre`, se reindexa sola.
--
-- Quedan 270 que comparten etiqueta con otro («Ropa · Avenida Petrolera» hay
-- varios). Es la verdad: son varios puestos de ropa en la Petrolera, y lo que
-- los distingue es la foto. Inventarles un número no los distinguiría mejor.

alter table comercios add column if not exists sin_cartel boolean not null default false;
comment on column comercios.sin_cartel is
  'El local no tiene cartel ni nombre propio. Entonces `nombre` lo arma el trigger con lo que vende y dónde está, y se mantiene solo. Escribirle un nombre de verdad lo apaga.';


create or replace function comercios_nombre_sin_cartel() returns trigger
language plpgsql as $$
declare
  base_txt  text;
  lugar_txt text;
  donde_txt text;
begin
  -- Un nombre en blanco no es un nombre vacío: es «no tiene». Así, borrar el
  -- campo en el panel alcanza para que se arme solo, y un alta puede venir sin
  -- nombre (el trigger corre ANTES del not null, así que la columna igual
  -- queda llena).
  if nullif(btrim(coalesce(new.nombre, '')), '') is null then
    new.sin_cartel := true;

  -- Si alguien le ESCRIBE un nombre, es que encontró el cartel: deja de ser
  -- derivado y no se vuelve a tocar. Va acá y no en la API para que valga por
  -- cualquier camino — el panel, la app de campo, una corrección a mano.
  elsif tg_op = 'UPDATE' and new.nombre is distinct from old.nombre then
    new.sin_cartel := false;
    return new;
  end if;

  if not coalesce(new.sin_cartel, false) then
    return new;
  end if;

  -- QUÉ VENDE. La subcategoría es lo específico («jean», «petshop»); el rubro
  -- es el paraguas y sirve de red cuando no hay subcategoría.
  base_txt := nullif(btrim(coalesce(new.subcategoria, '')), '');
  if base_txt is null then
    select btrim(regexp_replace(r.nombre, '^[^A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ]+', ''))
      into base_txt from rubros r where r.id = new.rubro_id;
    -- La clase de caracteres va escrita a mano y no como [:alnum:]: con la
    -- colación C, [:alnum:] es sólo ASCII y se comería la Ñ de un rubro que
    -- empezara con ella.
  end if;
  base_txt := coalesce(nullif(btrim(coalesce(base_txt, '')), ''), 'Comercio');
  base_txt := upper(substr(base_txt, 1, 1)) || substr(base_txt, 2);

  -- DÓNDE ESTÁ. Adentro de una galería, la galería y el puesto: así se
  -- pregunta y así se llega. Sobre la calle, la calle.
  select l.nombre into lugar_txt from lugares l where l.id = new.lugar_id;
  if lugar_txt is not null then
    donde_txt := lugar_txt || coalesce(', ' || nullif(btrim(coalesce(new.puesto, '')), ''), '');
  else
    donde_txt := nullif(btrim(coalesce(new.calle, '')), '');
  end if;

  new.nombre := base_txt || coalesce(' · ' || donde_txt, '');
  return new;
end $$;

drop trigger if exists trg_comercios_nombre_sin_cartel on comercios;
create trigger trg_comercios_nombre_sin_cartel
  before insert or update on comercios
  for each row execute function comercios_nombre_sin_cartel();


-- ------------------------------------------------------------------
-- Los que ya están: «Comercio», «Comercio 437», «Puesto 12», «Local 3».
-- El update dispara el trigger y les arma el nombre.
--
-- El `nombre` viejo no se pierde de vista: era «Comercio <n>» y no decía
-- nada, así que no hay nada que guardar.
update comercios
   set sin_cartel = true
 where sin_cartel = false
   and btrim(coalesce(nombre, '')) ~* '^(comercio|puesto|local|negocio|tienda)[[:space:]]*[0-9]*$';
