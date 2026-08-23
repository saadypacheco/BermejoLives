-- Las imágenes del sitio, por ciudad.
--
-- Cambiar de ciudad en el selector ya cambia los textos y el centro del mapa,
-- pero el fondo del hero seguía siendo una foto de Bermejo. Elegir "Santa Cruz"
-- y ver el río Bermejo detrás del título no es un detalle estético: contradice
-- lo único que el usuario acaba de decir.
--
-- Van en la base y no en el código por la misma razón que los adornos del mapa:
-- abrir una ciudad nueva no puede depender de un deploy. Se sube la foto, se
-- pega la URL, y listo.
--
-- Ambas son NULL por defecto y el frontend cae a las imágenes actuales. Una
-- ciudad sin foto propia se ve como hasta ahora en vez de romperse, y eso
-- importa porque hoy sólo Bermejo tiene material.

alter table ciudades add column if not exists hero_url text;
alter table ciudades add column if not exists foto_url text;

comment on column ciudades.hero_url is
  'Fondo del hero de la home (panorámica de la ciudad). NULL = usa la imagen '
  'por defecto del frontend.';
comment on column ciudades.foto_url is
  'Foto secundaria (panel "Descubrí más"). NULL = usa la imagen por defecto.';

-- Bermejo con lo que ya venía usando el frontend, para que su portada siga
-- saliendo de la base como las demás y no de una constante.
update ciudades
   set hero_url = coalesce(hero_url, '/bermejo-ciudad4.png'),
       foto_url = coalesce(foto_url, '/Bermejo-plaza.png')
 where slug = 'bermejo';
