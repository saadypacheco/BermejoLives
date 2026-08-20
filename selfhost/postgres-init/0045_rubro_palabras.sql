-- Diccionario palabra → rubro, para clasificar comercios a partir de lo que el
-- agente escribió en la descripción durante el recorrido.
--
-- Por qué existe: en la calle elegir rubros de una lista de 42 es inviable — se
-- cargan 84 locales en un día y el rubro termina siendo "Otros" en todos. Lo que
-- SÍ se puede hacer es describir lo que se ve en el negocio. Este diccionario
-- convierte esa descripción en rubros después, sin volver al campo.
--
-- Es una TABLA y no código a propósito: las palabras que usa la gente cambian y
-- son locales ("chinelas", "salteñas", "fardo"). Agregar una fila es más barato
-- que un deploy.
--
-- MULTI-RUBRO: un local puede vender neumáticos, zapatillas y televisores. La
-- función devuelve TODOS los rubros que matchean, no el primero — así aparece en
-- las tres búsquedas. comercio_rubros es N-a-N y buscar_comercios ya matchea por
-- cualquiera de ellos.

create table if not exists rubro_palabras (
  rubro_slug text not null references rubros(slug) on delete cascade,
  patron     text not null,          -- regex, en minúsculas y SIN acentos
  primary key (rubro_slug, patron)
);

alter table rubro_palabras enable row level security;
grant all    on public.rubro_palabras to service_role;
grant select on public.rubro_palabras to anon, authenticated;

-- Los patrones se comparan contra unaccent(lower(nombre || ' ' || descripcion)),
-- así que van sin tildes. \m y \M son inicio/fin de palabra en Postgres.
insert into rubro_palabras (rubro_slug, patron) values
  ('ropa',              '\m(ropa|vestido|pantalon|camisa|remera|polera|buzo|campera|jean|blusa|pollera|falda|short|chomba|calza|indumentaria|moda|boutique|lenceria|pijama|bombacha|corpi|uniforme)'),
  ('calzado',           '\m(zapato|zapatilla|calzado|sandalia|botin|bota|ojota|chinela|mocasin|championes)'),
  ('bolsos',            '\m(bolso|mochila|cartera|valija|maleta|billetera|morral|riñonera|rinonera)'),
  ('joyeria',           '\m(joya|joyeria|reloj|anillo|collar|aro|pulsera|bijou|bisuteria|alhaja)'),
  ('belleza',           '\m(perfume|perfumeria|cosmetic|maquillaje|shampoo|belleza|esmalte|tintura|crema facial|labial)'),
  ('optica',            '\m(optica|anteojo|gafas|lente de|lentes)'),
  ('celulares',         '\m(celular|celulares|smartphone|cell|funda|cargador|chip|telefonia|movil)'),
  ('computacion',       '\m(computadora|computacion|notebook|laptop|impresora|informatica|cartucho|toner|pc\M)'),
  ('electronica',       '\m(televisor|televisores|\mtv\M|parlante|audio|sonido|auricular|electronica|equipo de musica|dvd)'),
  ('electrodomesticos', '\m(heladera|refrigerador|microondas|licuadora|lavarropas|ventilador|electrodomestico|freezer|termotanque|batidora)'),
  ('bazar',             '\m(bazar|olla|sarten|vajilla|plato|taza|cubierto|utensilio|tupper|termo|cristaleria|cacerola)'),
  ('hogar',             '\m(sabana|toalla|colcha|cortina|almohada|mantel|decoracion|acolchado|frazada|blanqueria)'),
  ('muebles',           '\m(mueble|colchon|sillon|ropero|placard|comoda|somier)'),
  ('ferreteria',        '\m(ferreteria|herramienta|tornillo|clavo|pintura|cemento|caño|cano|electricidad|cable|foco|luces|iluminacion|lampara|led\M|construccion|taladro|martillo|alambre|sanitario|griferia|pvc)'),
  ('repuestos-autos',   '\m(repuesto|filtro|bateria|amortiguador|automotor|autoparte)'),
  ('neumaticos',        '\m(neumatico|cubierta|llanta|lubricante|aceite de motor)'),
  ('motos',             '\m(moto|motos|motocicleta|casco)'),
  ('bicicletas',        '\m(bicicleta|bici|ciclismo|rodado)'),
  ('alimentos',         '\m(supermercado|almacen|abarrote|arroz|azucar|fideo|mercaderia|comestible|verduleria|carniceria|fruta|verdura|pollo|carne|huevo|lacteo|queso|harina|conserva)'),
  ('bebidas',           '\m(bebida|gaseosa|cerveza|vino|jugo|licor|whisky|refresco)'),
  ('farmacia',          '\m(farmacia|medicamento|remedio|pastilla|botica|analgesico)'),
  ('mascotas',          '\m(mascota|veterinaria|balanceado|alimento para perro|alimento para gato)'),
  ('restaurantes',      '\m(restaurante|almuerzo|menu del dia|parrilla|pension|comedor|churrasco)'),
  ('comida-rapida',     '\m(hamburguesa|salteña|saltena|empanada|pizza|lomito|rotiseria|sandwich|choripan|papas fritas|pollo frito|broaster)'),
  ('cafeteria',         '\m(cafeteria|heladeria|helado|postre|torta|batido|licuado|cafe\M)'),
  ('panaderia',         '\m(panaderia|\mpan\M|factura|masita|reposteria|bizcocho|facturas)'),
  ('cambio',            '\m(cambio de moneda|casa de cambio|divisa|cambista|arbolito)'),
  ('envios',            '\m(encomienda|courier|paqueteria|flete|envios)'),
  ('peluqueria',        '\m(peluqueria|barberia|corte de pelo|salon de belleza|manicura|pedicura|uñas|unas esculpidas)'),
  ('lavadero',          '\m(lavadero|lavanderia|lavado de ropa|lavado de auto)'),
  ('gomeria-servicio',  '\m(gomeria|vulcanizadora|parche|alineacion|balanceo)'),
  ('cerrajeria',        '\m(cerrajeria|cerradura|copia de llave)'),
  ('hospedaje',         '\m(hotel|hospedaje|alojamiento|residencial|hostal|alojamos)'),
  ('jugueteria',        '\m(juguete|jugueteria|libreria|escolar|cuaderno|lapiz|utiles|papeleria|\mtoy)'),
  ('bebes',             '\m(bebe|bebes|pañal|panal|cochecito|mamadera|chupete)'),
  ('deportes',          '\m(deporte|deportivo|gimnasio|fitness|pelota|futbol|suplemento)'),
  ('regaleria',         '\m(regalo|regaleria|cotillon|globo|souvenir|piñata|pinata|adorno)'),
  ('ropa-americana',    '\m(ropa americana|americana|fardo|ropa usada)'),
  ('calzado-usado',     '\m(zapatilla americana|calzado usado)'),
  ('usados',            '\m(usado|usados|segunda mano|feria americana)'),
  ('floreria',          '\m(floreria|\mflor|ramo|maceta|vivero|planta ornamental)')
on conflict (rubro_slug, patron) do nothing;


-- Devuelve TODOS los rubros que matchean un texto libre. Multi-rubro por diseño:
-- un local con neumáticos, zapatillas y televisores tiene que aparecer en las
-- tres búsquedas, no sólo en la primera que matcheó.
create or replace function rubros_sugeridos(p_texto text)
returns text[]
language sql stable as $$
  select coalesce(array_agg(distinct rp.rubro_slug), '{}')
    from rubro_palabras rp
   where p_texto is not null
     and unaccent(lower(p_texto)) ~ rp.patron;
$$;

grant execute on function rubros_sugeridos(text) to anon, authenticated, service_role;
