-- La guía del que viene a Bermejo (/guia) y lo que necesita de la base.
--
-- 1. El saber local tiene SECCIÓN: aduana, documentos, frontera, comercios,
--    transporte, seguridad, conectividad. La página /guia agrupa por eso, y
--    el asistente contesta lo mismo: una sola fuente, editable en el admin.
-- 2. El estado de la frontera de hoy (puente, chalanas, río), que alguien
--    carga desde /contenido. No hay ninguna fuente automática para esto y
--    es lo primero que pregunta el que está por cruzar.
-- 3. Un historial de cotizaciones, para poder decir "hoy te dan más que en
--    los últimos días" (el aviso de cambio favorable).
-- 4. Lugares de servicio en el mapa: baños, estacionamientos, cajeros,
--    wifi. Van en la tabla `lugares` que ya existe, con tipos nuevos.

-- ---------------------------------------------------------------- 1. sección
alter table saber_local add column if not exists seccion text;
create index if not exists idx_saber_local_seccion on saber_local (seccion) where activo;

update saber_local set seccion = 'aduana'       where seccion is null and pregunta in ('¿Cuánto puedo llevar de vuelta a Argentina sin pagar?', '¿Cuánto puedo traer a Bolivia sin pagar impuestos?');
update saber_local set seccion = 'documentos'   where seccion is null and pregunta in ('¿Qué documentos necesito para cruzar?');
update saber_local set seccion = 'frontera'     where seccion is null and pregunta in ('¿Cómo cruzo de Aguas Blancas a Bermejo?', '¿Cómo cruzo a Argentina?');
update saber_local set seccion = 'comercios'    where seccion is null and pregunta in ('¿A qué hora abre el comercio en Bermejo?', '¿Qué conviene comprar en Bermejo?', '¿Se compra por unidad o por docena?', '¿Con qué moneda pago en Bermejo?', '¿Dónde cambio plata en Bermejo?', '¿Dónde cambio dólares o pesos?');
update saber_local set seccion = 'transporte'   where seccion is null and pregunta in ('¿Cómo llego a Bermejo desde Tarija?', '¿Cómo llego desde Salta u Orán?');
update saber_local set seccion = 'seguridad'    where seccion is null and pregunta in ('¿Es seguro? ¿Algún consejo para el que viene por primera vez?');
update saber_local set seccion = 'general'      where seccion is null;

-- La guía lee el saber local directo de la base, sin pasar por el backend:
-- es contenido público (el asistente ya se lo dice a cualquiera). Sólo lo
-- activo, y sólo lectura. Lo que la gente pregunta (asistente_conversaciones)
-- sigue siendo privado.
grant select on public.saber_local to anon, authenticated;
drop policy if exists saber_local_public_read on saber_local;
create policy saber_local_public_read on saber_local for select to anon, authenticated using (activo);

insert into saber_local (pregunta, respuesta, etiquetas, seccion, creado_por)
select v.pregunta, v.respuesta, v.etiquetas, v.seccion, 'inicial'
from (values
  ('¿Qué NO se puede pasar por la aduana?',
   'Al volver a Argentina: mercadería en cantidad comercial (docenas) no entra como equipaje; cubiertas, restringidas; alimentos de origen animal o vegetal sin autorización de SENASA, no (embutidos, lácteos, frutas, semillas); armas, y nada que no puedas mostrar con ticket si te lo piden. Lo demás entra dentro de la franquicia: 300 dólares por adulto, 150 por menor, el excedente paga el 50 %.',
   array['aduana','no se puede','prohibido','senasa','cubiertas','alimentos','pasar','entrar','franquicia'], 'aduana'),
  ('¿A quién llamo en una emergencia en Bermejo?',
   'Policía: 110. Bomberos: 119. Ambulancia (emergencias médicas): 168. Son números nacionales de Bolivia y funcionan desde cualquier celular. Del lado argentino, en Aguas Blancas hay Gendarmería y Prefectura en el puerto de chalanas.',
   array['emergencia','emergencias','policia','bomberos','ambulancia','110','119','168','telefono','urgencia','hospital'], 'seguridad'),
  ('¿Cómo tengo internet en Bermejo? ¿Compro un chip?',
   'Los chips prepagos de Entel y Tigo se compran en sus agencias y en muchos kioscos, cuestan entre 20 y 50 Bs, y los paquetes de datos arrancan cerca de 30 Bs. Por ley el chip se registra con tu documento (pasaporte o DNI) y el IMEI del teléfono: en una agencia oficial es un trámite de 15 a 30 minutos. Entel tiene la mejor cobertura fuera de la ciudad. La eSIM todavía no es común acá: si tu teléfono la admite, preguntá en la agencia. Muchos comercios y restaurantes tienen wifi: pedí la clave.',
   array['internet','chip','sim','esim','entel','tigo','datos','wifi','celular','señal'], 'conectividad'),
  ('¿Hacen envíos a Argentina?',
   'Muchos mayoristas de Bermejo mandan la mercadería a Argentina por encomienda o transportes que cruzan seguido, sobre todo a Orán, Salta y Jujuy. Cada comercio tiene su forma y su precio: preguntá por WhatsApp antes de comprar. Lo que viaja por encomienda paga los mismos impuestos de aduana que si lo llevaras vos.',
   array['envio','envios','encomienda','mandar','despacho','transporte','argentina','entrega'], 'comercios')
) as v(pregunta, respuesta, etiquetas, seccion)
where not exists (select 1 from saber_local s where s.pregunta = v.pregunta);

-- ------------------------------------------------------- 2. la frontera hoy
create table if not exists frontera_estado (
  id             int primary key default 1 check (id = 1),
  puente         text not null default 'normal',      -- normal | demoras | cerrado
  chalanas       text not null default 'operando',    -- operando | suspendidas
  rio            text not null default 'normal',      -- normal | crecido
  nota           text,                                -- "filas de 2 horas por el feriado", etc.
  actualizado_en timestamptz not null default now(),
  actualizado_por text
);
insert into frontera_estado (id) values (1) on conflict (id) do nothing;
alter table frontera_estado enable row level security;
grant all on public.frontera_estado to service_role;
grant select on public.frontera_estado to anon, authenticated;
drop policy if exists frontera_estado_public_read on frontera_estado;
create policy frontera_estado_public_read on frontera_estado for select to anon, authenticated using (true);

-- ------------------------------------------------- 3. historial de cotización
create table if not exists cotizaciones_historial (
  id            bigserial primary key,
  clave         text not null,
  valor         numeric(14,4) not null,
  registrado_en timestamptz not null default now()
);
create index if not exists idx_cot_hist_clave on cotizaciones_historial (clave, registrado_en desc);
alter table cotizaciones_historial enable row level security;
grant all on public.cotizaciones_historial to service_role;
grant select on public.cotizaciones_historial to anon, authenticated;
drop policy if exists cot_hist_public_read on cotizaciones_historial;
create policy cot_hist_public_read on cotizaciones_historial for select to anon, authenticated using (true);
-- El punto de partida: lo que hay hoy.
insert into cotizaciones_historial (clave, valor, registrado_en)
select clave, valor, actualizado_en from cotizaciones where valor is not null and valor > 0
  and not exists (select 1 from cotizaciones_historial limit 1);

-- ------------------------------------------------- 4. lugares de servicio
-- `lugares.tipo` era mercado | galeria | paseo | shopping | otro. Se suman los
-- de servicio; el mapa y la guía los muestran por tipo. Se cargan desde
-- Admin › Lugares con su ubicación.
comment on column lugares.tipo is
  'mercado | galeria | paseo | shopping | otro | baño | estacionamiento | cajero | wifi | terminal | migraciones';
