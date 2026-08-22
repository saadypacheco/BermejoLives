-- Diccionario de sinónimos de productos: término → otras formas de decirlo.
--
-- Por qué una tabla y no un campo por comercio:
--
-- Entre los 161 comercios relevados no hay 161 vocabularios distintos, hay unos
-- pocos cientos de productos que se repiten. Pedirle sinónimos a la IA comercio
-- por comercio sería pagar la misma respuesta decenas de veces y quedarse con
-- "remera → polera" escrito distinto en cada fila.
--
-- Como diccionario se pide una sola vez, se corrige a mano cuando está mal
-- (igual que `rubro_palabras`, sin deploy), y sirve para los comercios que ya
-- están Y para los que se carguen mañana: al guardar un comercio nuevo se le
-- buscan los sinónimos de sus productos acá, sin gastar una llamada.
--
-- La columna `comercios.sinonimos` sigue existiendo y es la que entra al índice
-- de búsqueda; esta tabla es la FUENTE con la que se llena.

create table if not exists producto_sinonimos (
  termino    text primary key,          -- normalizado: minúsculas, sin tildes, singular
  sinonimos  text not null,             -- separados por coma
  origen     text not null default 'ia',-- 'ia' | 'manual'
  creado_at  timestamptz not null default now(),
  actualizado_at timestamptz not null default now()
);

comment on table producto_sinonimos is
  'Término → otras formas de nombrarlo, en vocabulario de la frontera '
  '(remera/polera/camiseta). Llena comercios.sinonimos, que es lo que se indexa.';
comment on column producto_sinonimos.origen is
  'manual gana sobre ia: una corrección a mano no se pisa en la próxima corrida.';

create index if not exists idx_prod_sin_origen on producto_sinonimos (origen);

alter table producto_sinonimos enable row level security;

drop policy if exists prod_sin_lectura on producto_sinonimos;
create policy prod_sin_lectura on producto_sinonimos for select using (true);

grant select on producto_sinonimos to anon, authenticated;
