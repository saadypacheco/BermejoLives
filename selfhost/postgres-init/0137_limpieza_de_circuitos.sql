-- Limpieza de circuitos (docs/limpieza-circuitos.md, aprobada el 6/10/2026).
--
-- Tres cosas de base de datos. Todo idempotente: se puede correr dos veces.
--
-- 1) EL COMPRADOR TIENE UNA SOLA IDENTIDAD, en `usuarios`, y ahora dice dos
--    cosas que antes no sabía decir:
--      verificado_en      cuándo probó que el número es suyo, porque NOS ESCRIBIÓ
--                         desde él (el «CONFIRMAR-XXXXXX» del webhook). El código
--                         temporal (`reset_code_confirmado_at`) se gasta al entrar;
--                         esta fecha no: es la prueba que queda.
--      consentimiento_en  cuándo TILDÓ «quiero recibir ofertas». Sólo con un tilde
--                         explícito Y DESPUÉS de verificar el número: el tilde se
--                         guarda como `consentimiento_pendiente` al pedir el código,
--                         y `consentimiento_en` se llena recién cuando el número
--                         queda verificado (si no, cualquiera marcaba el tilde con
--                         el número de otro). El `consentimiento_ofertas` que nacía en true
--                         no lo da nadie: se pensó antes de que el comprador
--                         pudiera decidir, así que no cuenta como consentimiento.
--    Por eso el default de `consentimiento_ofertas` pasa a false. Las filas que ya
--    existen NO se tocan (no hay forma de saber qué pasó con ellas): lo que vale
--    para avisar es `consentimiento_en`, no ese booleano.
--
--    Aparte, el backend ahora guarda `usuarios.whatsapp` normalizado (E.164:
--    59170000001). Las filas viejas sin el 591 siguen encontrándose (el backend
--    mira las dos formas); no se reescriben acá porque dos filas distintas
--    podrían colapsar en una y chocar con el `unique`.
--
-- 2) FAVORITOS CON SOFT-DELETE. Quitar un favorito borraba la fila; ahora la
--    apaga (`activo = false`), como todo lo demás. Volver a agregarlo la
--    reactiva (misma fila, por el unique usuario/comercio).
--
-- 3) EL COMERCIO CARGADO EN LA CALLE PUEDE ENTRAR A MI COMERCIO. El alta de campo
--    nunca creaba la fila de `comercio_usuarios`, y la recuperación por WhatsApp
--    busca justamente esa fila: ningún comercio de campo podía entrar jamás. El
--    alta de campo ya la crea (backend); acá se le crea a los que YA existen:
--    todo comercio activo sin cuenta activa. Sin email ni contraseña (0023): el
--    dueño pide el código por WhatsApp desde el número de su ficha. Los que no
--    tienen WhatsApp cargado quedan con la cuenta lista para cuando lo tengan.
--    Idempotente: el `not exists` la deja en cero filas la segunda vez.
--
-- 4) LA CLAVE DE 6 NÚMEROS (segunda ronda, 6/10/2026). Comerciante y comprador
--    entran con celular + una clave que genera URUKU. Sólo se guarda el HASH
--    (el mismo PBKDF2 de las contraseñas), en `comercio_usuarios` y `usuarios`:
--    NUNCA en `comercios`, que el sitio lee con la llave pública. Los intentos
--    fallidos y el bloqueo (5 intentos = 15 minutos) viven en la
--    tabla `clave_fallos` (ver 6). Ninguna de las columnas tiene policy ni grant
--    para el público.
--
-- 5) EL WHATSAPP DE LA FICHA, NORMALIZADO. «+591 7012-3456» en la ficha no
--    coincidía con quien entra escribiendo «70123456». El backend ahora guarda
--    el número en E.164; acá se normalizan los que ya están, SÓLO los que
--    validan como celular boliviano (8 dígitos que empiezan con 6 o 7, con o sin
--    591 adelante). Lo demás (argentinos, fijos, basura) no se toca.
--
-- 6. LOS INTENTOS FALLIDOS, ATÓMICOS (tercera ronda, seguridad). Antes el contador
--    eran dos columnas que se leían, se sumaban en Python y se escribían: dos
--    pedidos en paralelo contaban uno solo, y un ingreso correcto de OTRA cuenta
--    del mismo número lo ponía en cero (con un comercio propio colgado del número
--    de la víctima, el atacante probaba claves sin bloqueo nunca). Ahora cada
--    intento es una FILA de `clave_fallos` que se inserta ANTES de verificar la
--    clave, y el bloqueo se CALCULA contando filas por ventana (no se guarda):
--      5 fallos en 15 minutos  -> bloqueo (429) hasta que el más viejo salga;
--      10 fallos en 24 horas   -> la clave se anula (`clave_hash = null`);
--      20 fallos por IP en 1 h -> 429 para esa IP.
--    Un ingreso correcto NO borra fallos (sólo marca su propio intento como 'ok').
--    Una clave nueva obtenida por WhatsApp sí los deja 'obsoleto' (el dueño probó
--    que el número es suyo). La función los cuenta bajo un lock por número, así
--    que dos pedidos simultáneos no se pisan.
--
-- NADA se abre a anon. Las tres tablas siguen con RLS activo y sin policies
-- públicas: las lee y escribe sólo el backend (service_role).

-- ------------------------------------------------- 1. el comprador
alter table usuarios add column if not exists verificado_en timestamptz;
alter table usuarios add column if not exists consentimiento_en timestamptz;
alter table usuarios add column if not exists consentimiento_pendiente boolean not null default false;
alter table usuarios alter column consentimiento_ofertas set default false;

comment on column usuarios.verificado_en is
  'Cuándo confirmó por WhatsApp (mensaje entrante desde su número). No se borra al entrar.';
comment on column usuarios.consentimiento_en is
  'Cuándo tildó, de forma explícita, que quiere recibir ofertas. NULL = nunca dio consentimiento.';
comment on column usuarios.consentimiento_pendiente is
  'Tildó «quiero recibir ofertas» al pedir el código, pero todavía no verificó el número. Se vuelve consentimiento_en al confirmar por WhatsApp.';
comment on column usuarios.consentimiento_ofertas is
  'Obsoleto como prueba de consentimiento (nacía en true). Usar consentimiento_en.';

-- ------------------------------------------------- 2. favoritos con soft-delete
alter table favoritos add column if not exists activo boolean not null default true;
comment on column favoritos.activo is
  'false = el comprador lo quitó. Nunca se borra la fila.';
create index if not exists idx_favoritos_usuario_activo on favoritos (usuario_id) where activo;

-- ------------------------------------------------- 3. cuentas para los de campo
insert into comercio_usuarios (comercio_id, nombre)
select c.id, c.nombre
from comercios c
where c.activo
  and not exists (
    select 1 from comercio_usuarios u
    where u.comercio_id = c.id and u.activo
  );

-- ------------------------------------------------- 4. la clave de 6 números
alter table comercio_usuarios add column if not exists clave_hash text;
alter table usuarios add column if not exists clave_hash text;

comment on column comercio_usuarios.clave_hash is
  'Hash PBKDF2 de la clave de 6 números del comerciante. Nunca la clave en claro. NULL = todavía no tiene o se anuló por 10 fallos en 24 h.';
comment on column usuarios.clave_hash is
  'Hash PBKDF2 de la clave de 6 números del comprador. Nunca la clave en claro. NULL = todavía no tiene o se anuló por 10 fallos en 24 h.';

-- ------------------------------------------------- 5. WhatsApp de la ficha, normalizado
-- Se queda sólo con los dígitos; si son 8 y empiezan con 6 o 7 se antepone 591, y
-- si ya son 591 + 8 que empiezan con 6 o 7 se deja esa forma. El resto no se
-- toca. Idempotente: el `is distinct from` deja la segunda corrida en 0 filas.
update public.comercios c
set whatsapp = n.normalizado
from (
  select id,
         case
           when d ~ '^[67][0-9]{7}$'        then '591' || d
           when d ~ '^591[67][0-9]{7}$'     then d
           else null
         end as normalizado
  from (
    select id, regexp_replace(whatsapp, '[^0-9]', '', 'g') as d
    from public.comercios
    where whatsapp is not null
  ) x
) n
where c.id = n.id
  and n.normalizado is not null
  and c.whatsapp is distinct from n.normalizado;

-- ------------------------------------------------- 6. intentos fallidos, atómicos
-- Una fila por intento de ingreso con clave. `resultado`:
--   fallo      cuenta para los límites (es lo que queda si el pedido se corta antes
--              de verificar: el intento ya se registró);
--   ok         el ingreso fue correcto: no cuenta, y TAMPOCO borra los fallos previos;
--   bloqueado  se rechazó sin verificar la clave (ya estaba bloqueado): no cuenta;
--   obsoleto   fallo anterior a una clave nueva obtenida por WhatsApp: no cuenta para
--              el número, sí para la IP (un atacante no se «limpia» la IP).
-- `numero` va normalizado (E.164) para que «70123456» y «+591 7012-3456» sumen juntos.
-- `cuenta_ids` son las cuentas del número al momento del intento (auditoría); el
-- bloqueo es por NÚMERO, no por cuenta.
create table if not exists public.clave_fallos (
  id          uuid primary key default gen_random_uuid(),
  tabla       text not null check (tabla in ('comercio_usuarios', 'usuarios')),
  numero      text not null,
  cuenta_ids  uuid[] not null default '{}',
  ip          text not null default '?',
  resultado   text not null default 'fallo' check (resultado in ('fallo', 'ok', 'bloqueado', 'obsoleto')),
  created_at  timestamptz not null default now()
);
comment on table public.clave_fallos is
  'Un intento de ingreso con clave por fila. El bloqueo se calcula contando fallos por ventana; no se guarda.';
create index if not exists idx_clave_fallos_numero on public.clave_fallos (tabla, numero, created_at desc);
create index if not exists idx_clave_fallos_ip on public.clave_fallos (ip, created_at desc);

-- Inserta el intento y devuelve cuántos fallos hay (CONTANDO éste) en cada ventana,
-- en una sola transacción y bajo un lock por número y otro por IP: dos pedidos en
-- paralelo se ven entre sí. Siempre se toma primero el lock del número y después el
-- de la IP (mismo orden en todos: sin deadlock).
create or replace function public.registrar_intento_clave(
  p_tabla text, p_numero text, p_cuenta_ids uuid[], p_ip text
) returns table (intento_id uuid, fallos_15m integer, fallos_24h integer, fallos_ip_1h integer)
language plpgsql
set search_path = public
as $fn$
declare
  v_id uuid;
  v_ahora timestamptz := clock_timestamp();
begin
  perform pg_advisory_xact_lock(hashtextextended('clave:' || p_tabla || ':' || p_numero, 0));
  perform pg_advisory_xact_lock(hashtextextended('clave-ip:' || p_ip, 0));

  insert into public.clave_fallos (tabla, numero, cuenta_ids, ip, created_at)
  values (p_tabla, p_numero, coalesce(p_cuenta_ids, '{}'), p_ip, v_ahora)
  returning id into v_id;

  return query select
    v_id,
    (select count(*)::integer from public.clave_fallos f
      where f.tabla = p_tabla and f.numero = p_numero and f.resultado = 'fallo'
        and f.created_at > v_ahora - interval '15 minutes'),
    (select count(*)::integer from public.clave_fallos f
      where f.tabla = p_tabla and f.numero = p_numero and f.resultado = 'fallo'
        and f.created_at > v_ahora - interval '24 hours'),
    (select count(*)::integer from public.clave_fallos f
      where f.ip = p_ip and f.resultado in ('fallo', 'obsoleto')
        and f.created_at > v_ahora - interval '1 hour');
end
$fn$;

-- Sólo el backend. Las funciones nacen ejecutables por PUBLIC: se les quita.
revoke all on function public.registrar_intento_clave(text, text, uuid[], text) from public, anon, authenticated;
grant execute on function public.registrar_intento_clave(text, text, uuid[], text) to service_role;

-- ------------------------------------------------- permisos
-- Las cuatro, sólo para el backend. Se repite el GRANT por explícito (lección de
-- Supabase Cloud: sin GRANT, error 42501); las columnas nuevas heredan el de la
-- tabla. RLS ya está activo en las tres primeras desde sus migraciones de origen.
alter table usuarios enable row level security;
alter table favoritos enable row level security;
alter table comercio_usuarios enable row level security;
alter table clave_fallos enable row level security;
revoke all on public.clave_fallos from public, anon, authenticated;

grant all on public.usuarios to service_role;
grant all on public.favoritos to service_role;
grant all on public.comercio_usuarios to service_role;
grant all on public.clave_fallos to service_role;
