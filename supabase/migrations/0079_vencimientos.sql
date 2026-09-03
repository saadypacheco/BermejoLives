-- Lo que se vence y no avisa hasta que ya pasó.
--
-- POR QUÉ UNA TABLA Y NO UNA NOTA EN UN PAPEL
-- ===========================================
--
-- Nada de esto falla despacio. El dominio no se degrada: un día deja de
-- resolver y el sitio entero desaparece, incluidos los enlaces que los
-- comerciantes mandaron por WhatsApp. El VPS no se pone lento: se apaga. Un
-- chip prepago sin recargar no avisa: la operadora se lo vende a otro, y el
-- número de respaldo que ibas a usar el día del baneo ya es de un desconocido.
--
-- Son cosas de las que uno se acuerda el día que se rompen. Por eso van a la
-- pantalla que se mira todos los días y no a la cabeza de nadie.
--
-- QUÉ NO VA ACÁ
-- =============
--
-- Los certificados TLS, porque los renueva Traefik solo y el sistema puede
-- MIRAR cuándo vencen sin que nadie los cargue. Cargar a mano un dato que se
-- puede medir es garantizar que algún día diga algo distinto de la realidad.
-- Van en /admin/certificados, medidos en vivo.

create table if not exists vencimientos (
  id          uuid primary key default gen_random_uuid(),
  nombre      text not null,
  tipo        text not null default 'otro'
                check (tipo in ('dominio','hosting','servicio','sim','plan','otro')),
  -- NULL a propósito: una fila sin fecha es "hay que averiguarla", y eso es
  -- información. Obligar la fecha llevaría a inventar una, que es peor que no
  -- tenerla porque deja de avisar creyendo que avisa.
  vence_el    date,
  -- Cuántos días antes empieza a molestar. Un dominio necesita más aire que un
  -- chip: renovarlo puede requerir plata, un trámite o esperar a alguien.
  aviso_dias  int not null default 30 check (aviso_dias between 1 and 365),
  proveedor   text,
  url         text,
  notas       text,
  activo      boolean not null default true,
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now()
);

create index if not exists idx_vencimientos_fecha on vencimientos (vence_el) where activo;

comment on table vencimientos is
  'Fechas que si se pasan tumban algo. Se miran desde Admin › Vencimientos.';
comment on column vencimientos.vence_el is
  'NULL = falta averiguarla. La fila igual aparece en el panel, marcada.';

alter table vencimientos enable row level security;
grant all on vencimientos to service_role;

-- Las que ya sabemos que existen, SIN fecha. Aparecen en el panel como "falta
-- la fecha" y eso es exactamente el estado real: nadie las anotó nunca.
-- Sembrarlas con una fecha inventada sería peor — el panel diría que está todo
-- bien hasta el día que algo se caiga.
insert into vencimientos (nombre, tipo, proveedor, aviso_dias, notas) values
  ('Dominio uruku.bo', 'dominio', 'NIC Bolivia', 60,
   'Si vence, el sitio entero desaparece: también los enlaces que los comercios ya mandaron por WhatsApp. Los .bo se renuevan con trámite, no con un clic.'),
  ('DNS de uruku.bo', 'servicio', 'Cloudflare', 30,
   'Plan gratuito. No vence solo, pero la cuenta sí se puede suspender por falta de uso o por cambio de términos.'),
  ('VPS de producción', 'hosting', 'Hostinger', 45,
   'srv1900330. Si se apaga se cae todo: sitio, base, WhatsApp y el caché de tiles.'),
  ('VPS de QA', 'hosting', 'Hostinger', 30,
   'srv1064770 (encontralo.store).'),
  ('Dominio encontralo.store', 'dominio', 'Hostinger', 45, 'QA.'),
  ('Chip operativo (WhatsApp)', 'sim', 'Tigo', 30,
   'El vinculado a WAHA. Prepago: sin recarga la operadora recicla el número y se pierde la sesión y los grupos.'),
  ('Chip respaldo 1', 'sim', 'Entel', 30,
   'En el cajón. Prepago sin usar: es JUSTO el que se recicla sin que nadie lo note, y se descubre el día del baneo.'),
  ('Chip respaldo 2', 'sim', 'Entel', 30, 'En el cajón. Mismo riesgo que el respaldo 1.')
-- `on conflict (nombre)` y no `on conflict do nothing` pelado: sin una columna
-- sobre la que colisionar, esa cláusula no protege nada y cada corrida vuelve a
-- insertar las ocho. Pasó: quedaron 16. El índice único lo crea la 0080; en una
-- base nueva las migraciones corren en orden, así que acá todavía no existe y
-- por eso esta línea queda tolerante.
on conflict do nothing;
