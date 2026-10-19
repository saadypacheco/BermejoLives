-- difusion_cola: lo que necesita la integración para difundir con el texto/imagen que aprobó
-- marketing y para saber, con certeza, qué salió y dónde.
--
--   texto_override      Texto que aprobó la persona (el pie con comercio y enlace lo agrega Uruku).
--   imagen_url_override Imagen que aprobó la persona (el JPEG cuadrado subido por E6).
--   solicitado_por      Quién pidió la difusión ('integracion:marketing:<usuario>'). Las filas con
--                       este dato las envía SÓLO la integración (E9): el worker automático y el
--                       botón "enviar todo" del panel no las toman, para que nadie las mande dos veces.
--   external_post_id    Id del posteo en Meta (post_id de Facebook / id del media de Instagram).
--   ig_container_id     Contenedor de Instagram. Si "publicar" falla o se corta, el reintento
--                       consulta su status_code ANTES de crear otro (crear otro = duplicar el post).
--   permalink           Enlace al posteo, leído de Graph por E10 (la publicación no lo devuelve).
--   verificado_at       Cuándo E10 confirmó en Graph que el posteo existe.
--   estado 'incierto'   Se mandó y no sabemos si salió (timeout, corte tras enviar). No se
--                       reintenta a ciegas: primero se consulta a Meta.
--
-- difusion_cola sigue sin permisos para anon/authenticated (operación interna).
-- Idempotente. Una transacción, con comprobación al final.

begin;

alter table public.difusion_cola add column if not exists texto_override text;
alter table public.difusion_cola add column if not exists imagen_url_override text;
alter table public.difusion_cola add column if not exists solicitado_por text;
alter table public.difusion_cola add column if not exists external_post_id text;
alter table public.difusion_cola add column if not exists ig_container_id text;
alter table public.difusion_cola add column if not exists permalink text;
alter table public.difusion_cola add column if not exists verificado_at timestamptz;

alter table public.difusion_cola drop constraint if exists difusion_cola_texto_override_largo;
alter table public.difusion_cola add constraint difusion_cola_texto_override_largo
  check (texto_override is null or char_length(texto_override) <= 2000);

alter table public.difusion_cola drop constraint if exists difusion_cola_estado_check;
alter table public.difusion_cola add constraint difusion_cola_estado_check
  check (estado in ('pendiente', 'enviado', 'error', 'omitido', 'incierto'));

create index if not exists idx_difusion_cola_solicitado_por
  on public.difusion_cola (publicacion_id) where solicitado_por is not null;

comment on column public.difusion_cola.texto_override is 'Texto aprobado por la integración (Uruku le agrega su pie estándar al enviar).';
comment on column public.difusion_cola.imagen_url_override is 'Imagen aprobada por la integración (subida por E6).';
comment on column public.difusion_cola.solicitado_por is 'integracion:<sistema>:<usuario>. Sólo la integración (E9) envía estas filas.';
comment on column public.difusion_cola.external_post_id is 'Id del posteo en Meta.';
comment on column public.difusion_cola.ig_container_id is 'Contenedor de Instagram; se consulta antes de reintentar.';
comment on column public.difusion_cola.permalink is 'Enlace al posteo (lo lee E10 de Graph).';
comment on column public.difusion_cola.verificado_at is 'Cuándo E10 confirmó el posteo en Graph.';

-- ============================================================ comprobación
do $chk$
declare
  v_rol text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    if has_table_privilege(v_rol, 'public.difusion_cola', 'select')
       or has_table_privilege(v_rol, 'public.difusion_cola', 'insert')
       or has_table_privilege(v_rol, 'public.difusion_cola', 'update') then
      raise exception '0158: % tiene permisos sobre difusion_cola', v_rol;
    end if;
  end loop;
  if not has_table_privilege('service_role', 'public.difusion_cola', 'update') then
    raise exception '0158: service_role no puede escribir difusion_cola';
  end if;
  if not exists (select 1 from pg_constraint where conrelid = 'public.difusion_cola'::regclass
                 and conname = 'difusion_cola_estado_check'
                 and pg_get_constraintdef(oid) like '%incierto%') then
    raise exception '0158: el estado incierto no quedó permitido';
  end if;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
