-- Bares, boliches y karaoke: no entraban en ningún rubro.
--
-- `restaurantes` es comer, `cafeteria` es café y postres, `bebidas` es comprar
-- para llevar. Salir de noche no es ninguna de las tres, y hoy un boliche caía
-- donde la IA lo empujara.
--
-- UN rubro y no cuatro. Boliche, karaoke, bar y peña responden a la misma
-- intención —salir— y separados quedarían de dos o tres comercios cada uno: un
-- chip que no refina nada. Qué es cada uno va en la subcategoría, igual que
-- "zapatilla urbana" dentro de calzado.

insert into rubros (slug, nombre, icono, orden, comercial) values
  ('nocturna', '🌙 Bares, boliches y karaoke', '🌙', 48, true)
on conflict (slug) do update set
  nombre = excluded.nombre, icono = excluded.icono,
  orden = excluded.orden, comercial = excluded.comercial, activo = true;

-- `bar` va cerrado con \m...\M —la palabra entera— porque suelto aparece dentro
-- de "barberia", "barraca" y "bariloche". Cerrado es seguro y agarra "cafe bar"
-- y "resto bar", que es lo que se quiere.
--
-- "disco" NO va: es también el disco de freno y el disco rígido. Va "discoteca".
insert into rubro_palabras (rubro_slug, patron) values
  ('nocturna', '\m(boliche|karaoke|discoteca|restobar|resto bar|cerveceria|pub\M|bar\M|peña|pena folklorica|night club|salon de fiesta|after office)')
on conflict (rubro_slug, patron) do nothing;
