-- Una guía por frontera, no una sola guía.
--
-- Cada paso es distinto y la guía tiene que decir lo de ESE paso:
--
--   Bermejo     → Aguas Blancas (Argentina), puente y chalanas, pesos
--   Yacuiba     → Salvador Mazza / Pocitos (Argentina), pesos
--   Villazón    → La Quiaca (Argentina), puente peatonal, pesos
--   Desaguadero → Desaguadero (Perú), soles
--   Puerto Quijarro → Corumbá (Brasil), reales
--   Cobija      → Brasileia / Epitaciolândia (Brasil), reales
--
-- Lo que cambia por ciudad:
--   ciudades.pais_vecino / moneda_vecina / paso_nombre  — de qué frontera es
--   ciudades.guia_activa                                — si ya tiene la guía
--                                                          cargada (se prende
--                                                          cuando hay contenido)
--   saber_local.ciudad_id                                — ya existía: NULL =
--                                                          vale para todas
--   frontera_estado                                      — una fila por ciudad
--                                                          (era una sola, id=1)

-- ------------------------------------------------- 1. de qué frontera es cada ciudad
alter table ciudades add column if not exists pais_vecino   text;
alter table ciudades add column if not exists moneda_vecina text;   -- ARS | BRL | PEN
alter table ciudades add column if not exists paso_nombre   text;   -- "Aguas Blancas"
alter table ciudades add column if not exists guia_activa   boolean not null default false;
comment on column ciudades.guia_activa is
  'La guía de esta ciudad está cargada y se muestra (/guia, el menú, el estado del paso). Se prende cuando hay saber local propio, no antes: una guía vacía es peor que ninguna.';
comment on column ciudades.moneda_vecina is
  'Moneda del país vecino: ARS | BRL | PEN. Decide qué cotización se muestra arriba y en /cambio.';

update ciudades set pais_vecino = 'Argentina', moneda_vecina = 'ARS', paso_nombre = 'Aguas Blancas' where slug = 'bermejo';
update ciudades set pais_vecino = 'Argentina', moneda_vecina = 'ARS', paso_nombre = 'Salvador Mazza (Pocitos)' where slug = 'yacuiba';
update ciudades set pais_vecino = 'Argentina', moneda_vecina = 'ARS', paso_nombre = 'La Quiaca' where slug = 'villazon';
update ciudades set pais_vecino = 'Perú',      moneda_vecina = 'PEN', paso_nombre = 'Desaguadero (Perú)' where slug = 'desaguadero';
update ciudades set pais_vecino = 'Brasil',    moneda_vecina = 'BRL', paso_nombre = 'Corumbá' where slug = 'puerto-quijarro';
update ciudades set pais_vecino = 'Brasil',    moneda_vecina = 'BRL', paso_nombre = 'Brasileia / Epitaciolândia' where slug = 'cobija';
-- La guía cargada hoy es la de Bermejo.
update ciudades set guia_activa = true where slug = 'bermejo';

-- ------------------------------------------------- 2. el estado del paso, por ciudad
alter table frontera_estado drop constraint if exists frontera_estado_id_check;
alter table frontera_estado add column if not exists ciudad_id uuid references ciudades(id) on delete cascade;
update frontera_estado set ciudad_id = (select id from ciudades where slug = 'bermejo') where ciudad_id is null;
create unique index if not exists frontera_estado_ciudad on frontera_estado (ciudad_id);
-- El id dejaba de ser siempre 1: una fila por ciudad.
create sequence if not exists frontera_estado_id_seq;
select setval('frontera_estado_id_seq', greatest(coalesce((select max(id) from frontera_estado), 1), 1));
alter table frontera_estado alter column id set default nextval('frontera_estado_id_seq');
alter sequence frontera_estado_id_seq owned by frontera_estado.id;
-- No todas las fronteras tienen chalanas ni río: el que no las tenga deja el
-- campo en 'no_aplica' y no se muestra.
comment on column frontera_estado.chalanas is 'operando | limitadas | suspendidas | no_aplica (esta frontera no tiene chalanas)';
comment on column frontera_estado.rio is 'normal | crecido | no_aplica';

-- ------------------------------------------------- 3. el saber local, por ciudad
-- `ciudad_id` ya existía en la tabla (0106) sin usarse. NULL = vale para
-- todas las fronteras (aduana boliviana, cómo funciona URUKU); con ciudad,
-- es de esa ciudad. Lo cargado hasta hoy es de Bermejo.
update saber_local set ciudad_id = (select id from ciudades where slug = 'bermejo')
 where ciudad_id is null
   and (seccion in ('frontera', 'transporte', 'seguridad', 'comercios')
        or respuesta ilike '%Bermejo%' or respuesta ilike '%Aguas Blancas%' or respuesta ilike '%chalana%');
create index if not exists idx_saber_local_ciudad on saber_local (ciudad_id) where activo;

-- ------------------------------------------------- 4. la cotización de cada moneda vecina
-- El real y el sol, para cuando se carguen esas ciudades. Sin valor: el sitio
-- no muestra una cotización sin cargar.
insert into cotizaciones (clave, etiqueta, detalle, unidad, orden) values
  ('brl_bob', 'Real', '1 BRL', 'Bs', 4),
  ('pen_bob', 'Sol',  '1 PEN', 'Bs', 5)
on conflict (clave) do nothing;
