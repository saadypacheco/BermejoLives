-- LAS CUATRO CIUDADES DONDE VAN A TRABAJAR LOS AGENTES
--
-- Santa Cruz, Tarija, Cochabamba y La Paz. Tres ya estaban activas;
-- **Cochabamba no**, y eso no es un detalle cosmético.
--
-- Al dar de alta un comercio, la ciudad NO la decide el desplegable: la decide
-- el GPS, con `ciudad_mas_cercana` (backend/app/api/campo.py). Y esa función
-- sólo mira las ciudades ACTIVAS. Con Cochabamba apagada, la más cercana a
-- -17.39/-66.16 entre las activas es La Paz — así que cada comercio que
-- cargara el agente de Cochabamba se habría archivado en La Paz, sin un error,
-- sin un aviso y sin forma de notarlo hasta tener trescientos mal puestos.
--
-- Activarla ya no tiene el costo que tenía: el buscador dice la verdad cuando
-- una ciudad no tiene comercios cargados («URUKU todavía no tiene comercios en
-- Cochabamba») en vez de «probá con otra palabra». Antes de eso, activar una
-- ciudad vacía era prometer algo que no estaba.

update ciudades set activa = true where slug = 'cochabamba';

-- El orden del desplegable: Bermejo primero porque es donde está el catálogo,
-- después las cuatro por tamaño. Sin esto el orden lo decide el azar de la
-- carga y cambia cada vez que se toca una fila.
update ciudades set orden = 1 where slug = 'bermejo';
update ciudades set orden = 2 where slug = 'santa-cruz';
update ciudades set orden = 3 where slug = 'la-paz';
update ciudades set orden = 4 where slug = 'cochabamba';
update ciudades set orden = 5 where slug = 'tarija';

-- Ninguna de las cuatro es ciudad de frontera: no les corresponde la guía del
-- paso, ni la cotización del peso, ni el estado de las chalanas. Ya estaba así
-- (migración 0124), se deja explícito para que una carga futura no lo pise.
update ciudades set es_frontera = false, guia_activa = false
 where slug in ('santa-cruz', 'la-paz', 'cochabamba', 'tarija');

-- Verificación: las cinco tienen que quedar activas y CON COORDENADAS. Una
-- ciudad activa sin lat/lng es invisible para `ciudad_mas_cercana` —la saltea—
-- y vuelve el mismo problema por otro camino.
do $$
declare faltan text;
begin
  select string_agg(slug, ', ') into faltan
    from ciudades
   where activa and (lat is null or lng is null);
  if faltan is not null then
    raise exception 'Ciudades activas SIN coordenadas: %. El alta por GPS las ignora.', faltan;
  end if;
end $$;
