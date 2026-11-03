-- 0182 · Textos del video con el diseño del kit (plantillas v2).
--
-- Spec técnica: docs/contenido-redes-tecnico.md §16.8.
--
--  1. content_pieces: los textos que se dibujan DENTRO del video (video_texts), quién los escribió
--     (video_texts_engine: 'gemini:<modelo>' | 'template' | 'human'), las objeciones del validador
--     (video_texts_checks; [] = en verde) y si la persona confirmó que las fotos marcadas están bien
--     (photo_flags_ok). Es null en las piezas v1 (template_version = 1).
--  2. content_piece_sources: la frase de cada foto (chip_text), las marcas que Gemini vio en ella
--     (photo_flags, p. ej. 'price_or_code_visible') y hacia dónde encuadrarla (focus_y, 0 a 1).
--
-- PERMISOS: no hay GRANT nuevo. La 0181 dejó las dos tablas sólo para service_role (RLS activo,
-- `revoke all ... from public, anon, authenticated` y `grant all ... to service_role` A NIVEL DE
-- TABLA, sin ningún grant por columnas). Una columna nueva hereda el permiso de la tabla, así que
-- nace privada para anon y authenticated. El bloque de comprobación de abajo lo verifica.
-- Sin borrado físico. Idempotente: se puede correr dos veces.

begin;

alter table public.content_pieces
  add column if not exists video_texts         jsonb,                          -- textos del video (job.json "texts"); null en v1
  add column if not exists video_texts_engine  text,                           -- 'gemini:<modelo>' | 'template' | 'human'
  add column if not exists video_texts_checks  jsonb not null default '[]'::jsonb,
  add column if not exists photo_flags_ok      boolean not null default false; -- «revisé las fotos marcadas»

alter table public.content_piece_sources
  add column if not exists chip_text   text check (chip_text is null or length(chip_text) <= 40),
  add column if not exists photo_flags text[] not null default '{}',           -- {'price_or_code_visible'}
  add column if not exists focus_y     real check (focus_y is null or focus_y between 0 and 1);

comment on column public.content_pieces.video_texts is
  'Textos que se dibujan dentro del video v2 (kick, títulos, subtítulo, búsqueda, cierre). Null en las piezas v1. Sólo el backend.';
comment on column public.content_pieces.video_texts_engine is
  'Quién escribió los textos del video: gemini:<modelo>, template (texto fijo) o human (los editó una persona).';
comment on column public.content_pieces.photo_flags_ok is
  'Una persona confirmó que las fotos marcadas (precio o código visible) están bien.';
comment on column public.content_piece_sources.chip_text is
  'La frase corta que se muestra sobre la foto en el video v2.';

-- Comprobación (si algo falla, no queda nada): ni anon ni authenticated ven las columnas nuevas y
-- service_role las escribe.
do $chk$
declare
  v_rol text;
  v_col text;
begin
  foreach v_rol in array array['anon', 'authenticated'] loop
    foreach v_col in array array['video_texts', 'video_texts_engine', 'video_texts_checks', 'photo_flags_ok'] loop
      if has_column_privilege(v_rol, 'public.content_pieces', v_col, 'select') then
        raise exception '0182: % puede leer content_pieces.%', v_rol, v_col;
      end if;
    end loop;
    foreach v_col in array array['chip_text', 'photo_flags', 'focus_y'] loop
      if has_column_privilege(v_rol, 'public.content_piece_sources', v_col, 'select') then
        raise exception '0182: % puede leer content_piece_sources.%', v_rol, v_col;
      end if;
    end loop;
  end loop;
  foreach v_col in array array['video_texts', 'video_texts_engine', 'video_texts_checks', 'photo_flags_ok'] loop
    if not has_column_privilege('service_role', 'public.content_pieces', v_col, 'update') then
      raise exception '0182: service_role no puede escribir content_pieces.%', v_col;
    end if;
  end loop;
  foreach v_col in array array['chip_text', 'photo_flags', 'focus_y'] loop
    if not has_column_privilege('service_role', 'public.content_piece_sources', v_col, 'update') then
      raise exception '0182: service_role no puede escribir content_piece_sources.%', v_col;
    end if;
  end loop;
end
$chk$;

commit;

-- PostgREST cachea el esquema y los permisos.
notify pgrst, 'reload schema';
