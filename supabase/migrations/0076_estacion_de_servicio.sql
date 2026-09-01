-- Faltaba el rubro de las estaciones de servicio.
--
-- Con 42 rubros no había ninguno para un surtidor: caían en "Otros (a
-- clasificar)" o en "Repuestos para autos", que es otra cosa. Y en Bermejo no
-- es un rubro menor — es frontera, el precio del combustible es la mitad del
-- motivo por el que la gente cruza, y cuando escasea "quién tiene diesel" es
-- literalmente lo que se pregunta en la calle.

insert into rubros (slug, nombre, icono, orden) values
  ('estacion-servicio', '⛽ Estación de servicio', '⛽', 43)
on conflict (slug) do update set
  nombre = excluded.nombre,
  icono  = excluded.icono,
  orden  = excluded.orden,
  activo = true;

-- UN rubro, no cuatro. Qué despacha cada estación (gasolina, diesel, GNV) va en
-- `subcategoria`, que es el mismo mecanismo que distingue "zapatilla urbana" de
-- "calzado": ya se busca por texto y ya arma los chips de refinamiento. Un
-- rubro por combustible habría partido en cuatro un rubro que en el mapa tiene
-- que verse como uno solo.
insert into rubro_palabras (rubro_slug, patron) values
  ('estacion-servicio',
   '\m(surtidor|gasolinera|estacion de servicio|ypfb|gasolina|combustible|gnv|gas natural vehicular|expendio de combustible)')
on conflict (rubro_slug, patron) do nothing;

-- LO QUE A PROPÓSITO NO ESTÁ EN EL PATRÓN
--
-- `diesel` — es también una marca de ropa, y en una ciudad que vive de la ropa
-- importada aparece en la descripción de cualquier local de jeans. Metida acá,
-- convertía tiendas de ropa en estaciones de servicio. Igual se encuentra al
-- buscarla: la búsqueda mira `subcategoria` y `descripcion`, así que una
-- estación cuya subcategoría diga "diesel" sale igual. El diccionario sólo
-- decide el rubro automático, no qué se puede buscar.
--
-- `gas` a secas — en Bolivia es la garrafa de GLP domiciliaria, y una
-- distribuidora de garrafas no es una estación de servicio. `gnv` sí va: es
-- inequívocamente vehicular.
--
-- `nafta` — es argentino. Del lado boliviano se dice gasolina, y "nafta" en una
-- descripción escrita acá es más probable que venga de otra cosa.
