-- Banderas en el mapa, y las chalanas a un cuarto de su tamaño.
--
-- LAS BANDERAS
--
-- Bermejo es frontera: el puente cruza a Aguas Blancas y media ciudad compra de
-- los dos lados. Una bandera puesta en el paso dice eso mejor que un cartel.
--
-- `variante` en vez de un tipo por bandera ('bandera-ar', 'bandera-bo', …): son
-- todas el mismo adorno con distintos colores. Un tipo por cada una obligaría a
-- migrar la base cada vez que se agrega un departamento, y el editor tendría
-- veinte botones en vez de uno con una lista.
alter table mapa_adornos add column if not exists variante text;

alter table mapa_adornos drop constraint if exists mapa_adornos_tipo_check;
alter table mapa_adornos add constraint mapa_adornos_tipo_check
  check (tipo in ('chalana', 'lapacho', 'bandera'));

comment on column mapa_adornos.variante is
  'Sólo para tipo=bandera: cuál bandera (''ar'', ''bo'', …). Los colores viven '
  'en el frontend (lib/adornos.ts, BANDERAS); acá va sólo la clave.';

-- LAS CHALANAS
--
-- Se dibujaban a 64×40 y quedaban enormes al lado de un pin de comercio, que es
-- lo que el mapa existe para mostrar. Ahora se dibujan a 16×10.
--
-- El tamaño nuevo es el del DIBUJO, en el código. La columna `escala` sigue
-- siendo el ajuste fino por adorno y se deja como está: si alguien había puesto
-- una chalana en 1.5 para que se destaque, esa intención se conserva — sólo que
-- ahora 1.5 es sobre una base cuatro veces más chica.
