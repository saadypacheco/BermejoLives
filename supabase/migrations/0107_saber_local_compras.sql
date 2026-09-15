-- Saber local para el que viene a comprar a Bermejo.
--
-- Lo que un vecino le contaría a alguien que llega: cómo cruzar, con qué
-- pagar, a qué hora, cuánto se puede llevar de vuelta. Investigado el
-- 15/9/2026; las fuentes están en docs/saber-local-bermejo-compras.md. Se
-- carga acá para que entre con un comando en cualquier ambiente, y se edita
-- desde Admin › Ayuda: esto es el arranque, no la verdad.
--
-- Lo que ninguna fuente publica (nombres de calles y galerías, el precio de
-- la chalana hoy, dónde están los cambistas) NO está acá a propósito: eso lo
-- carga alguien de Bermejo, y el asistente lo va a pedir solo cuando la
-- gente lo pregunte y quede en "Sin respuesta".
--
-- Cada entrada entra una sola vez: si ya hay una con la misma pregunta, se
-- deja como está (puede haber sido corregida a mano).

insert into saber_local (pregunta, respuesta, etiquetas, creado_por)
select v.pregunta, v.respuesta, v.etiquetas, 'inicial'
from (values
  ('¿Cómo cruzo de Aguas Blancas a Bermejo?',
   'Hay dos formas. El puente internacional es el paso oficial: migraciones y aduana, atiende las 24 horas, y es el que conviene si volvés con compras. Las chalanas son botes de unas 8 personas que cruzan el río en un minuto: funcionan de día (más o menos de 7 a 18), se paga por persona en pesos, el chaleco es obligatorio, y no salen cuando el río está crecido (lluvias de diciembre a marzo). Los fines de semana largos hay filas de horas: si podés, vení en día de semana.',
   array['cruzar','cruce','puente','chalana','chalanas','aguas blancas','frontera','rio','pasar']),
  ('¿Qué documentos necesito para cruzar?',
   'DNI o pasaporte vigente. Menores que no viajan con los dos padres, con autorización. Del lado argentino, Migraciones en Aguas Blancas registra tu salida y te da un ticket; al volver te revisan el equipaje.',
   array['documentos','dni','pasaporte','menores','migraciones','autorizacion']),
  ('¿A qué hora abre el comercio en Bermejo?',
   'Temprano. La zona mayorista arranca desde las 5 de la mañana (la feria mayorista, incluso de madrugada) y muchos locales mayoristas empiezan a cerrar desde la 1 de la tarde. Los negocios de la avenida, que venden por unidad, siguen de tarde. Si venís a comprar por mayor, llegá con el sol.',
   array['hora','horario','abre','abren','temprano','madrugada','feria','mayorista','cierra','siesta']),
  ('¿Qué conviene comprar en Bermejo?',
   'Ropa y calzado (jeans, camperas, ropa infantil, zapatillas, ropa interior por docena), electrónica y electrodomésticos (celulares, TV, ventiladores, licuadoras), perfumería y cosmética, limpieza, juguetes y bazar. Neumáticos y repuestos también son mucho más baratos, pero la aduana argentina los restringe al volver. Mucho de lo que se vende llega de la Zona Franca de Iquique. Buscá el rubro en el mapa: uruku.bo/buscar',
   array['conviene','comprar','barato','que comprar','ropa','zapatillas','neumaticos','cubiertas','electro','celulares','ofertas']),
  ('¿Se compra por unidad o por docena?',
   'En las ferias y galerías mayoristas los precios son por docena o media docena, y por unidad sale bastante más. En la avenida venden por unidad. El truco de los que vienen seguido: venir en grupo y repartirse las docenas.',
   array['docena','unidad','por mayor','mayorista','precio','cantidad','revendedor']),
  ('¿Con qué moneda pago en Bermejo?',
   'Con pesos argentinos (la mayoría de los precios de la zona comercial están en pesos), bolivianos o dólares; muchos comercios aceptan transferencia y billeteras como Mercado Pago, y algunos te cambian la transferencia a efectivo en el acto. Consejo que repite todo el mundo: traer dólares rinde más que traer pesos. La cotización del día está arriba del sitio.',
   array['pagar','pago','moneda','pesos','dolares','bolivianos','mercado pago','transferencia','tarjeta','efectivo']),
  ('¿Dónde cambio plata en Bermejo?',
   'En las casas de cambio y con los cambistas de la zona del puente, el puerto de chalanas y el centro. Los cambistas suelen dar un poco más que las casas de cambio; contá bien y cambiá de a poco. El valor cambia durante el día y según dónde: mirá la cotización arriba del sitio y compará. Las casas de cambio, en el mapa: uruku.bo/buscar?rubro=cambio&vista=mapa',
   array['cambio','cambiar','cambista','cambistas','arbolito','dolar','dolares','pesos','cotizacion','plata']),
  ('¿Cuánto puedo llevar de vuelta a Argentina sin pagar?',
   'Por paso terrestre o fluvial, la franquicia de equipaje es de 300 dólares por adulto y 150 por menor de 16, y se puede sumar entre el grupo familiar; lo que pasa de eso paga el 50 %. Un celular, notebook o tablet por persona para uso personal no tiene límite de valor. Mercadería en cantidad comercial (docenas) no entra como equipaje, y las cubiertas están restringidas. Alimentos de origen animal o vegetal sin autorización de SENASA, no. Guardá los tickets.',
   array['aduana','franquicia','arca','afip','limite','volver','equipaje','impuestos','300 dolares','senasa']),
  ('¿Cuánto puedo traer a Bolivia sin pagar impuestos?',
   'Régimen de viajeros de la Aduana Nacional: artículos nuevos hasta 1.000 dólares sin impuestos; entre 1.000 y 2.000 se declaran y se paga sobre el excedente. Es para uso personal, no comercial. En el puerto de chalanas la Aduana atiende de 6 a 18.',
   array['aduana nacional','bolivia','viajeros','1000 dolares','impuestos','traer','ingresar']),
  ('¿Cómo llego a Bermejo desde Tarija?',
   'Son 208 km, entre 3 y 4 horas y media por carretera. Salen buses y trufis desde la terminal de Tarija (av. Víctor Paz Estenssoro), el pasaje ronda los 80 bolivianos más la tasa de terminal, con varias salidas por día (Trans Villa del Norte, Expreso El Bermejeño, entre otras).',
   array['tarija','llegar','bus','buses','trufi','combi','terminal','pasaje','viaje']),
  ('¿Cómo llego desde Salta u Orán?',
   'Desde Orán, Aguas Blancas queda a unos 50 km (colectivos y remises). Desde Salta y desde casi todo el norte argentino salen tours de compras que llegan hasta Aguas Blancas, y de ahí se cruza por el puente o en chalana.',
   array['salta','oran','aguas blancas','tour','tours','colectivo','remis','argentina','llegar']),
  ('¿Qué se puede hacer en Bermejo aparte de comprar?',
   'El balneario natural El Chorro (a unos 8 km, en la comunidad El Nueve), El Toro con sus cascadas y puente colgante, Santa Rosa y Barredero, pesca en los ríos Bermejo y Tarija, y la Reserva de Tariquía cerca. El clima es tropical: en verano hace mucho calor (enero ronda los 33°) y llueve sobre todo de diciembre a marzo; el invierno es suave. Restaurantes y hospedajes, en el mapa: uruku.bo/buscar?rubro=restaurantes y uruku.bo/buscar?rubro=hospedaje',
   array['turismo','pasear','chorro','balneario','toro','pesca','tariquia','clima','calor','lluvia','dormir','hotel','comer']),
  ('¿Cuándo es la fiesta de Bermejo?',
   'La fiesta grande es San Santiago, el 25 de julio, con misa, procesión y juegos tradicionales. Esos días hay más gente y algunos comercios cambian el horario.',
   array['fiesta','san santiago','santiago','25 de julio','feriado','aniversario','festividad']),
  ('¿Es seguro? ¿Algún consejo para el que viene por primera vez?',
   'Es una frontera con mucha gente y mucho efectivo, así que: plata repartida y no a la vista, contar el cambio, chaleco puesto en la chalana y no cruzar con el río crecido. Del lado argentino hay Policía, Gendarmería y Prefectura. Llegá temprano, comprá por docena si venís a revender, guardá los tickets para la aduana, y preguntá acá por cualquier local: te decimos horario, dirección y WhatsApp.',
   array['seguro','seguridad','consejo','consejos','primera vez','cuidado','robo','tips'])
) as v(pregunta, respuesta, etiquetas)
where not exists (select 1 from saber_local s where s.pregunta = v.pregunta);
