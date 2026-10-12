-- El código URUKU-XXXX del comercio, sólo para el equipo (docs/clave-automatica.md).
--
-- El código era público a propósito: estaba en la ficha, en el volante y en Mi
-- comercio, y servía para publicar desde cualquier número. Desde la clave
-- automática del comercio (celular + `PREFIJO-AZAR`) el código deja de ser cosa
-- del dueño: lo ve y lo dicta SÓLO el admin, y la ingesta de WhatsApp lo sigue
-- aceptando (el admin se lo pasa a quien haga falta).
--
-- Esto cierra la última puerta: la lectura pública en la base. La 0145 le dio a
-- anon y authenticated `select` por columnas, y `codigo` estaba en la lista (la
-- ficha pública lo pedía). Acá se le quita ese `select`:
--     comercios?select=codigo        como anon  ->  42501 (permission denied)
-- La 0145 NO se toca (ya está aplicada): esta migración la completa.
--
-- Lo que NO cambia:
--   · El backend (service_role) lo lee y lo escribe igual: admin e ingesta.
--   · El código se sigue generando en el alta (índice único de la 0044).
--   · Ni las vistas (`feed_publico`) ni las funciones públicas (`buscar_comercios`,
--     `plan_publico`, `plan_orden_de`) devuelven `codigo`: se revisó una por una.
--     Las funciones de revisión de rubros (`rubros_a_revisar`, `previsualizar_patron`)
--     sí lo devuelven, pero son del panel (el backend las llama con service_role) y
--     corren con los permisos de quien llama: tras esta migración, si anon las llamara,
--     fallarían con 42501 en vez de entregar el código.
--
-- IMPORTANTE PARA EL FRONTEND: ningún `select` con el cliente anon puede pedir
-- `codigo` (ni `comercios(codigo)` embebido). Sale de `COLUMNAS_COMERCIO`.
--
-- Todo en una transacción y con comprobación: si anon sigue pudiendo leerlo, no se
-- aplica nada. Idempotente: se puede correr dos veces.

begin;

revoke select (codigo) on public.comercios from anon, authenticated;

-- El resto de lo público tiene que seguir abierto (ficha, buscador, mapa).
do $chk$
declare
  v_rol text;
  v_col text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    if has_column_privilege(v_rol, 'public.comercios', 'codigo', 'select') then
      raise exception '0148: % todavía puede leer comercios.codigo', v_rol;
    end if;
    foreach v_col in array array['id', 'slug', 'nombre', 'activo', 'plan', 'suspendido', 'horario',
                                 'lat', 'lng', 'busqueda'] loop
      if not has_column_privilege(v_rol, 'public.comercios', v_col, 'select') then
        raise exception '0148: % no puede leer comercios.%', v_rol, v_col;
      end if;
    end loop;
  end loop;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
