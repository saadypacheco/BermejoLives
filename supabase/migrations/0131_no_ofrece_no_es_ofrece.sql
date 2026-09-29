-- «NO OFRECE ALQUILER DE EQUIPOS» NO ES UN ALQUILER
--
-- Asomarlux vende iluminación y sonido para eventos. Su descripción termina
-- diciendo «No ofrece alquiler de equipos» — o sea, aclara exactamente lo que
-- NO hace. La clasificación automática encontró la palabra «alquiler», ignoró
-- el «no» de adelante, y lo mandó a 🏠 Alquileres.
--
-- El problema no es el rubro alquiler ni ese comercio: es que el match mira
-- palabras sueltas. La misma frase en cualquier otro rubro hace lo mismo — «no
-- vendemos celulares» clasifica como celulares, «no hacemos delivery» como
-- delivery. Y es una frase que los comerciantes escriben todo el tiempo,
-- porque aclarar lo que uno no hace ahorra consultas.
--
-- Así que antes de buscar palabras se sacan los pedazos negados. Sólo cuando
-- la negación va pegada a un verbo de ofrecer: «no ofrece», «no vendemos»,
-- «no tienen». Eso deja afuera «no sólo vendemos ropa, también zapatos», que
-- es una negación que NO niega el rubro — y borrarla perdería la señal buena.

create or replace function texto_sin_negaciones(p_texto text)
returns text
language sql immutable as $$
  -- Del «no <verbo>» hasta el fin de la oración (o 80 caracteres, lo que
  -- venga primero). El corte por puntuación es lo que evita comerse la frase
  -- siguiente, que suele ser la que sí dice de qué es el local.
  select regexp_replace(
           coalesce(p_texto, ''),
           '\mno\s+(se\s+)?(ofrece|ofrecemos|ofrecen|hace|hacemos|hacen|vende|vendemos|venden|'
           || 'tiene|tenemos|tienen|trabaja|trabajamos|trabajan|maneja|manejamos|manejan|'
           || 'alquila|alquilamos|alquilan|realiza|realizamos|realizan|dispone|disponemos|'
           || 'cuenta|contamos|contamos con|acepta|aceptamos|aceptan)\M[^.;]{0,80}',
           ' ', 'gi');
$$;

comment on function texto_sin_negaciones(text) is
  'Saca los pedazos negados de un texto antes de buscarle palabras clave. «No ofrece alquiler de equipos» no puede clasificar como Alquileres.';

grant execute on function texto_sin_negaciones(text) to anon, authenticated, service_role;


create or replace function rubros_sugeridos(p_texto text)
returns text[]
language sql stable as $$
  select coalesce(array_agg(distinct rp.rubro_slug), '{}')
    from rubro_palabras rp
   where p_texto is not null
     and unaccent(lower(texto_sin_negaciones(p_texto))) ~ rp.patron;
$$;

grant execute on function rubros_sugeridos(text) to anon, authenticated, service_role;
