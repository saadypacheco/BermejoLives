-- Revisión de seguridad del commit 01b5674 (clave automática): lo que quedó abierto.
--
-- Cinco cosas, todas en una transacción y con comprobación al final (si algo no
-- quedó como debe, no se aplica NADA). Idempotente: se puede correr dos veces.
--
-- 1. `publicaciones` LEGIBLE ENTERA POR ANON (ALTO).
--    Desde la 0002 anon y authenticated tenían `grant select on publicaciones` de TABLA
--    entera. La policy deja ver sólo las aprobadas y activas, pero de ésas se leía TODO
--    por la API (`publicaciones?select=*`):
--        raw               el crudo del bridge (con el número y el JID de quien escribió)
--        codigo_recibido   el código URUKU-XXXX con el que se identificó el remitente
--        identidad_origen  cómo se atribuyó (grupo, número, código, explorador)
--        moderado_por, motivo_moderacion   quién y por qué moderó
--        ia_*              el veredicto de la IA y su confianza
--        wa_message_id, costo, cobrado, producto_ref_id, terminos_ia, busqueda
--    Acá el grant pasa de tabla a COLUMNAS (como la 0145 con `comercios`): anon sólo lee
--    lo que ya muestra `feed_publico` más las columnas por las que el sitio filtra
--    (`estado`, `activo`, `descuento_pct`: ver `getVolumenes`/`getFiltrosDisponibles` en
--    frontend/lib/data.ts). `feed_publico` es una vista y corre con los permisos de su
--    dueño, igual que `buscar_comercios` (SECURITY DEFINER desde la 0143): no se rompen.
--    Una columna NUEVA de `publicaciones` nace PRIVADA; si el sitio la va a leer, su
--    migración tiene que dar `grant select (columna) ... to anon, authenticated`.
--    El backend (service_role) sigue con todo.
--
--    La ingesta deja de copiar el crudo a `publicaciones.raw`: nada del panel lo lee de
--    ahí (el reproceso lee `wa_inbox.raw`). Las filas viejas conservan su `raw`, ahora
--    cerrado a anon; no se borra nada.
--
-- 2. Los CÓDIGOS URUKU-XXXX DE TODOS LOS COMERCIOS SE REGENERAN (una sola vez).
--    Los viejos estuvieron impresos en volantes y en el PDF de grupos, y hasta la 0148 se
--    leían por la API: hay que darlos por conocidos. Se usa el mismo alfabeto y largo que
--    `app/core/codigo.py` (4 de `23456789ABCDEFGHJKMNPQRSTUVWXYZ`), con bytes de
--    `gen_random_uuid()` (aleatorio criptográfico), y sin colisiones: el nuevo no es el
--    código ni el anterior de ningún comercio. Los grupos y números ya atados NO dependen
--    del código (se resuelven por JID / número), así que siguen andando.
--    `comercios.codigo_anterior` (privada) guarda el viejo sólo para que al APROBAR una
--    publicación que entró con el código viejo (`identidad_origen = 'codigo'`) la
--    revalidación de `_validar_codigo_al_aprobar` no la bloquee. La ingesta nueva busca
--    por `codigo` vigente: el viejo ya no identifica a nadie. Elegido sobre reescribir
--    `publicaciones.codigo_recibido` porque no toca lo que el remitente escribió de verdad
--    (el panel lo muestra) y es una columna, no una pasada sobre una tabla grande.
--    Se regenera SÓLO la primera vez (cuando todavía no existe `codigo_anterior`): volver a
--    correr la migración no cambia otra vez los códigos.
--
-- 3. SESIONES QUE SOBREVIVEN AL CAMBIO DE CLAVE (MEDIO).
--    `comercio_usuarios.credenciales_version` sube cada vez que la clave se genera, se
--    anula o se recupera; el token de Mi comercio lleva la versión con la que entró y deja
--    de servir cuando la de la cuenta es mayor. `rotar_credenciales_comercio` hace el
--    cambio de clave y la suba de versión en UNA sentencia (atómico), sólo para el backend.
--
-- 4. AUDITORÍA DE LA CUENTA DEL COMERCIO (MEDIO).
--    `comercio_eventos` (privada): quién generó una clave y cuándo, y las claves que el
--    sistema anuló por haberse mandado por WhatsApp. Nunca guarda la clave.
--
-- 5. FUNCIONES DEL PANEL QUE ANON PODÍA EJECUTAR (ALTO).
--    `previsualizar_patron` y `rubros_a_revisar` devuelven `codigo` y las crea la 0087/0089
--    sin quitarle el EXECUTE a PUBLIC: cualquiera las llamaba por /rpc. Corren con los
--    permisos de quien llama, así que la 0148 las dejó fallando con 42501 al leer
--    `comercios.codigo`, pero la defensa no puede ser esa. Se les quita el EXECUTE a
--    public, anon y authenticated; el backend las llama con service_role.
--
-- Columnas NUEVAS de `comercios` (todas PRIVADAS, regla de la 0145):
--    codigo_anterior   el código de antes de esta migración (ver 2)
--    alta_uid          el id con que el celular del agente identifica un alta, para que
--                      un reintento de la cola offline no duplique el comercio. Índice
--                      único parcial (cargado_por, alta_uid).

begin;

-- ¿Es la primera vez que corre? (para regenerar los códigos UNA sola vez). Se decide antes
-- de crear `codigo_anterior`; queda como ajuste de la transacción.
select set_config(
  'uruku.regenerar_codigos_0149',
  case when exists (select 1 from information_schema.columns
                     where table_schema = 'public' and table_name = 'comercios'
                       and column_name = 'codigo_anterior')
       then 'no' else 'si' end,
  true);

-- ============================================================ 1. publicaciones por columnas
revoke select on public.publicaciones from anon, authenticated;

grant select (
  id, comercio_id, tipo, titulo, descripcion, precio, moneda, imagen_url, tiktok_url,
  estado, origen, activo, created_at, approved_at, descuento_pct, vence_el, contacto_whatsapp
) on public.publicaciones to anon, authenticated;

-- El backend (service_role) sigue con todo.
grant all on public.publicaciones to service_role;

-- ============================================================ 2. columnas nuevas de comercios
alter table public.comercios add column if not exists codigo_anterior text;
alter table public.comercios add column if not exists alta_uid text;

comment on column public.comercios.codigo_anterior is
  'Código URUKU-XXXX previo a la regeneración de la 0149 (privado). Sólo lo acepta la revalidación al aprobar publicaciones que entraron antes.';
comment on column public.comercios.alta_uid is
  'Id del alta generado en el celular del agente (privado). (cargado_por, alta_uid) es único: un reintento de la cola offline no duplica el comercio.';

create unique index if not exists idx_comercios_alta_uid
  on public.comercios (cargado_por, alta_uid) where alta_uid is not null;

-- Regenerar los códigos (sólo la primera vez).
do $reg$
declare
  v_alfabeto constant text := '23456789ABCDEFGHJKMNPQRSTUVWXYZ';
  v_c         record;
  v_nuevo     text;
  v_bytes     bytea;
  v_i         int;
  v_b         int;
  v_intentos  int;
begin
  if current_setting('uruku.regenerar_codigos_0149', true) is distinct from 'si' then
    return;
  end if;
  for v_c in select id, codigo from public.comercios where codigo is not null order by id loop
    v_intentos := 0;
    loop
      v_nuevo := '';
      while length(v_nuevo) < 4 loop
        v_bytes := decode(replace(gen_random_uuid()::text, '-', ''), 'hex');
        for v_i in 0..15 loop
          continue when v_i in (6, 8);                 -- bytes fijos del UUID v4 (versión y variante)
          exit when length(v_nuevo) >= 4;
          v_b := get_byte(v_bytes, v_i);
          continue when v_b >= 248;                    -- 248 = 8 * 31: sin sesgo hacia los primeros símbolos
          v_nuevo := v_nuevo || substr(v_alfabeto, (v_b % 31) + 1, 1);
        end loop;
      end loop;
      exit when not exists (select 1 from public.comercios x
                             where x.codigo = v_nuevo or x.codigo_anterior = v_nuevo);
      v_intentos := v_intentos + 1;
      if v_intentos > 200 then
        raise exception '0149: no se pudo generar un código único para el comercio %', v_c.id;
      end if;
    end loop;
    update public.comercios set codigo_anterior = v_c.codigo, codigo = v_nuevo where id = v_c.id;
  end loop;
end
$reg$;

-- ============================================================ 3. sesiones de Mi comercio
alter table public.comercio_usuarios
  add column if not exists credenciales_version int not null default 0;

comment on column public.comercio_usuarios.credenciales_version is
  'Sube cada vez que la clave se genera, se anula o se recupera. El token de Mi comercio lleva la versión con la que entró: si la de la cuenta es mayor, la sesión se cerró.';

-- Cambia (o anula, con p_clave_hash = null) la clave de esas cuentas y sube la versión.
create or replace function public.rotar_credenciales_comercio(p_ids uuid[], p_clave_hash text default null)
returns table (id uuid, credenciales_version int)
language sql
as $fn$
  update public.comercio_usuarios u
     set clave_hash = p_clave_hash,
         credenciales_version = u.credenciales_version + 1
   where u.id = any(p_ids)
  returning u.id, u.credenciales_version;
$fn$;

-- Sólo el backend. Las funciones nacen ejecutables por PUBLIC: se les quita.
revoke all on function public.rotar_credenciales_comercio(uuid[], text) from public, anon, authenticated;
grant execute on function public.rotar_credenciales_comercio(uuid[], text) to service_role;

-- ============================================================ 4. auditoría de la cuenta
create table if not exists public.comercio_eventos (
  id          uuid primary key default gen_random_uuid(),
  comercio_id uuid not null references public.comercios(id),
  tipo        text not null,
  actor       text not null,
  created_at  timestamptz not null default now()
);
create index if not exists idx_comercio_eventos_comercio
  on public.comercio_eventos (comercio_id, created_at desc);

comment on table public.comercio_eventos is
  'Auditoría de la cuenta de un comercio (privada, sólo el backend): clave_generada_por_admin, clave_anulada_por_whatsapp. Nunca guarda la clave.';

alter table public.comercio_eventos enable row level security;
revoke all on public.comercio_eventos from public, anon, authenticated;
grant all on public.comercio_eventos to service_role;

-- ============================================================ 5. funciones del panel
revoke execute on function public.previsualizar_patron(text, text) from public, anon, authenticated;
revoke execute on function public.rubros_a_revisar(text, integer) from public, anon, authenticated;
grant execute on function public.previsualizar_patron(text, text) to service_role;
grant execute on function public.rubros_a_revisar(text, integer) to service_role;

-- ============================================================ comprobación
-- Si algo no quedó como debe, se revierte todo.
do $chk$
declare
  v_rol  text;
  v_col  text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    -- publicaciones: las privadas cerradas, las del sitio abiertas.
    foreach v_col in array array['raw', 'codigo_recibido', 'identidad_origen', 'moderado_por',
                                 'moderado_at', 'motivo_moderacion', 'wa_message_id', 'costo',
                                 'cobrado', 'producto_ref_id', 'terminos_ia', 'ia_analizado_at',
                                 'ia_veredicto', 'ia_motivo', 'ia_confianza', 'ia_revisado_at',
                                 'busqueda'] loop
      if has_column_privilege(v_rol, 'public.publicaciones', v_col, 'select') then
        raise exception '0149: % todavía puede leer publicaciones.%', v_rol, v_col;
      end if;
    end loop;
    foreach v_col in array array['id', 'comercio_id', 'tipo', 'titulo', 'descripcion', 'precio',
                                 'moneda', 'imagen_url', 'tiktok_url', 'estado', 'origen', 'activo',
                                 'created_at', 'approved_at', 'descuento_pct', 'vence_el',
                                 'contacto_whatsapp'] loop
      if not has_column_privilege(v_rol, 'public.publicaciones', v_col, 'select') then
        raise exception '0149: % no puede leer publicaciones.%', v_rol, v_col;
      end if;
    end loop;
    -- comercios: las columnas nuevas son privadas.
    foreach v_col in array array['codigo', 'codigo_anterior', 'alta_uid'] loop
      if has_column_privilege(v_rol, 'public.comercios', v_col, 'select') then
        raise exception '0149: % puede leer comercios.%', v_rol, v_col;
      end if;
    end loop;
    -- La auditoría, las cuentas y la rotación de claves, sólo del backend.
    if has_table_privilege(v_rol, 'public.comercio_eventos', 'select') then
      raise exception '0149: % puede leer comercio_eventos', v_rol;
    end if;
    if has_column_privilege(v_rol, 'public.comercio_usuarios', 'credenciales_version', 'select') then
      raise exception '0149: % puede leer comercio_usuarios.credenciales_version', v_rol;
    end if;
    if has_function_privilege(v_rol, 'public.rotar_credenciales_comercio(uuid[], text)', 'execute')
       or has_function_privilege(v_rol, 'public.previsualizar_patron(text, text)', 'execute')
       or has_function_privilege(v_rol, 'public.rubros_a_revisar(text, integer)', 'execute') then
      raise exception '0149: % todavía puede ejecutar una función del panel', v_rol;
    end if;
  end loop;
  -- El backend sigue con todo.
  if not has_table_privilege('service_role', 'public.publicaciones', 'select')
     or not has_table_privilege('service_role', 'public.comercio_eventos', 'insert')
     or not has_function_privilege('service_role', 'public.rotar_credenciales_comercio(uuid[], text)', 'execute')
     or not has_function_privilege('service_role', 'public.previsualizar_patron(text, text)', 'execute')
     or not has_function_privilege('service_role', 'public.rubros_a_revisar(text, integer)', 'execute') then
    raise exception '0149: service_role perdió un permiso';
  end if;
  -- Códigos: válidos (4 símbolos del alfabeto), sin repetir, y distintos del anterior.
  if exists (select 1 from public.comercios
              where codigo is not null and codigo !~ '^[23456789ABCDEFGHJKMNPQRSTUVWXYZ]{4}$') then
    raise exception '0149: hay un código de comercio con formato inválido';
  end if;
  if exists (select 1 from public.comercios where codigo is not null and codigo = codigo_anterior) then
    raise exception '0149: un comercio conserva su código de antes';
  end if;
  if exists (select codigo from public.comercios where codigo is not null group by codigo having count(*) > 1) then
    raise exception '0149: hay códigos de comercio repetidos';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
