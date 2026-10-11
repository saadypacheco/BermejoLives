-- Columnas de `comercios` que el público NO tiene por qué ver (docs/fotos-por-plan.md, parte B).
--
-- Desde la 0002, anon y authenticated tienen `grant select on comercios` de TABLA
-- ENTERA: cualquiera podía pedir por la API
--     comercios?select=plan_cortesia,paga_hasta,cargado_por,capturado_en
-- y ver quién tiene el plan de cortesía, hasta cuándo paga cada local, el correo
-- del agente que lo cargó y con qué hora y dónde anduvo cada agente.
--
-- Acá el grant pasa de tabla a COLUMNAS: se quita el de tabla y se da `select`
-- sólo sobre las columnas que el sitio público usa. Quedan privadas:
--     plan_cortesia   (0143)  si el comercio está en cortesía
--     paga_hasta      (0012)  hasta cuándo pagó
--     cargado_por     (0013)  correo del agente que lo cargó
--     capturado_en    (0138)  hora del celular al cargarlo
--     fotos_extra     (0144)  fotos extra compradas (el sitio público no la usa)
--     wa_jid                  grupo de WhatsApp atado al comercio (ingesta)
--     rubro_revisado_por      quién del equipo revisó el rubro
-- La estrella y el orden por plan los siguen dando `plan_publico()` y
-- `buscar_comercios()` (SECURITY DEFINER, 0143), sin exponer esos datos.
--
-- IMPORTANTE PARA EL QUE SIGUE
-- ============================
-- 1. Con este grant, una columna NUEVA de `comercios` nace PRIVADA para anon. Si el
--    sitio público la va a leer, la migración que la crea tiene que agregar
--    `grant select (columna) on public.comercios to anon, authenticated;`.
-- 2. En el frontend, con el cliente anon, NUNCA `select("*")` sobre `comercios`
--    (ni `comercios(*)` embebido): PostgREST expande `*` a todas las columnas y
--    falla entero con 42501 si falta permiso en UNA. Siempre columnas explícitas
--    (ver `COLUMNAS_COMERCIO` en frontend/lib/data.ts).
-- 3. El backend usa service_role: no cambia nada para él.
--
-- Las vistas (feed_publico) corren con los permisos de su dueño, y las funciones
-- que leían las columnas privadas (`buscar_comercios`, `plan_publico`,
-- `plan_orden_de`) son SECURITY DEFINER desde la 0143: no se rompen.
--
-- Todo en una transacción: si algo falla (una columna que no existe, un permiso
-- que no quedó como debe), no se aplica NADA y el grant de tabla sigue como estaba.
-- Idempotente: se puede correr dos veces.

begin;

revoke select on public.comercios from anon, authenticated;

grant select (
  id, slug, nombre, descripcion, logo_url, portada_url, whatsapp, telefono, email, tiktok_url,
  facebook_url, instagram_url, sitio_web, zona_id, direccion, lat, lng, como_llegar, plan,
  verificado, rating, destacado, activo, created_at, updated_at, confiable, modalidad,
  rubro_id, ciudad_id, monedas_aceptadas, envios_internacionales, origen_importacion,
  pedido_minimo, tiene_factura, horario, tiene_stock, suspendido, fuente, marca, sucursal,
  tipo_cocina, tiene_atm, estrellas, combustibles, internet_access, especialidad, operador,
  portada_thumb_url, acepta_reservas, lugar_id, puesto, codigo, prod_obs_human, prod_det_ia,
  subcategoria, ia_analizado_at, sinonimos, subcategoria_norm, busqueda, rubro_revisado_at,
  portada_pos, contacto_ok, contacto_no, calle, horario_estimado,
  sin_cartel, canal_wa_url, catalogo_url, tiene_pasero, talles_especiales
) on public.comercios to anon, authenticated;

-- El backend (service_role) sigue con todo.
grant all on public.comercios to service_role;

-- Comprobación: las privadas cerradas; las que usan la ficha, el buscador y el mapa abiertas.
do $chk$
declare
  v_rol text;
  v_col text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    foreach v_col in array array['plan_cortesia', 'paga_hasta', 'cargado_por', 'capturado_en', 'fotos_extra', 'wa_jid', 'rubro_revisado_por'] loop
      if exists (select 1 from information_schema.columns
                  where table_schema = 'public' and table_name = 'comercios' and column_name = v_col)
         and has_column_privilege(v_rol, 'public.comercios', v_col, 'select') then
        raise exception '0145: % todavía puede leer comercios.%', v_rol, v_col;
      end if;
    end loop;
    foreach v_col in array array['id', 'slug', 'nombre', 'activo', 'plan', 'suspendido', 'horario',
                                 'horario_estimado', 'lat', 'lng', 'busqueda'] loop
      if not has_column_privilege(v_rol, 'public.comercios', v_col, 'select') then
        raise exception '0145: % no puede leer comercios.%', v_rol, v_col;
      end if;
    end loop;
  end loop;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
