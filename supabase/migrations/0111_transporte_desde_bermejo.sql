-- Las dos preguntas de transporte que faltaban: el viaje DESDE Bermejo.
-- Las anteriores contestaban cómo llegar; el que ya está acá pregunta cómo
-- se vuelve o cómo sigue a Tarija.
insert into saber_local (pregunta, respuesta, etiquetas, seccion, creado_por)
select v.pregunta, v.respuesta, v.etiquetas, 'transporte', 'inicial'
from (values
  ('¿Cómo voy de Bermejo a Tarija?',
   'Desde la terminal de Bermejo salen buses y trufis a Tarija varias veces por día (Trans Villa del Norte, Expreso El Bermejeño, entre otras). Son 208 km, entre 3 y 4 horas y media, y el pasaje ronda los 80 bolivianos más la tasa de terminal. Los fines de semana largos conviene sacar el pasaje con tiempo.',
   array['tarija','ir','viajar','bus','buses','trufi','terminal','salir','pasaje','desde bermejo']),
  ('¿Cómo vuelvo a Orán o a Salta?',
   'Cruzás a Aguas Blancas por el puente (las 24 horas, con migraciones y aduana) o en chalana (de día, cuando el río lo permite). Desde Aguas Blancas hay colectivos y remises a Orán, a unos 50 km; y desde Orán salen los micros a Salta (unas 4 horas) y a Jujuy. Al volver, la aduana argentina revisa el equipaje: tené los tickets a mano y acordate de la franquicia de 300 dólares por adulto.',
   array['oran','salta','jujuy','volver','regresar','vuelta','colectivo','remis','micro','aguas blancas'])
) as v(pregunta, respuesta, etiquetas)
where not exists (select 1 from saber_local s where s.pregunta = v.pregunta);
