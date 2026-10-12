# Novedades de URUKU — spec

> **Estado: implementada el 12/10/2026.**

## Qué pidió el dueño (12/10)

La sección del inicio «Novedades de los comercios» pasa a ser **«Novedades»** y muestra
también novedades **de URUKU** (p. ej. «URUKU fue auspiciante del Festival del Lapacho»),
con video y fotos.

## Modelo (migración 0150 `0150_novedades_uruku.sql`, dos carpetas, idempotente)

Tabla `novedades_uruku`:
`id uuid pk default gen_random_uuid()`, `ciudad_id uuid null references ciudades` (null =
todas), `titulo text not null` (≤ 120), `texto text` (≤ 2000), `fecha date not null default
(now() at time zone 'America/La_Paz')::date`, `portada_url text`, `portada_thumb_url text`,
`fotos jsonb not null default '[]'` (lista de `{url, thumb_url}`, máx 12), `video_url text`,
`video_poster_url text`, `enlace_url text`, `destacada boolean not null default false`,
`activo boolean not null default true`, `created_by text`, `created_at timestamptz default now()`,
`updated_at timestamptz default now()`. Comentarios en español. RLS: anon/authenticated leen
sólo `activo`; **grant select por columnas** (todas menos `created_by`); service_role todo.
Soft-delete (`activo=false`), nunca DELETE físico.

## Backend (`backend/app/api/contenido.py`, permiso `contenido`, como los videos promo)

- `GET /contenido/novedades` (todas, también inactivas) · `POST /contenido/novedades` JSON
  `{titulo, texto?, fecha?, ciudad_slug?, enlace_url?, destacada?}` → la novedad ·
  `PATCH /contenido/novedades/{id}` (mismos campos + `activo`) · `DELETE` = baja lógica.
- `POST /contenido/novedades/{id}/portada` multipart `foto` (≤ 15 MB, pasa por
  `services/imagenes.py`: JPG + miniatura) → `{portada_url, portada_thumb_url}`.
- `POST /contenido/novedades/{id}/fotos` multipart `foto` → agrega a `fotos` (máx 12; 409 si
  pasa) · `DELETE /contenido/novedades/{id}/fotos?url=` la saca (y borra el archivo).
- `POST /contenido/novedades/{id}/video` multipart `video` (mp4/webm/mov, ≤ 100 MB, mismo
  manejo que `subir_video_promo`) y opcional `poster` (imagen) → `{video_url, video_poster_url}`.
- Archivos en el disco del backend bajo `uruku/novedades/<id>/`. Topes en
  `core/limite_cuerpo.py` (15 MB fotos, 100 MB video) y en `tests/test_ficha_destacados_seguridad.py`.
- `enlace_url` validado como http(s) (`services/enlaces.py`).

## Frontend

- **Lectura pública** (`lib/data.ts`, anon, columnas explícitas): `getNovedadesUruku(ciudadId,
  limit)` → activas de esa ciudad o de todas, `destacada` primero y después `fecha` desc.
- **Inicio** (`app/page.tsx`): la sección de novedades se llama **«Novedades»** (subtítulo
  «De URUKU y de los comercios de {ciudad}»). Primero las de URUKU (tarjeta con etiqueta
  **URUKU**, portada o póster del video con ícono de play, título y fecha), después las de
  los comercios. Si hay ofertas, «Ofertas destacadas» sigue igual y «Novedades» va como
  sección aparte. Sin ninguna, no se muestra.
- **`/novedades`**: arriba las de URUKU, después las de comercios (como hoy).
- **Detalle `/novedades/uruku/[id]`** (ISR, `revalidate`): título, fecha, texto, video con
  `<video controls playsInline preload="metadata" poster>`, fotos en grilla tipo vidriera
  (reusar el estilo de `components/galeria-tienda.tsx`), enlace si hay. Metadatos OG con la
  portada para compartir por WhatsApp. Icono `<Ic>`, nunca emoji.
- **Admin** (sección de contenido del publicador, donde están los videos promo): «Novedades de
  URUKU»: lista (activas e inactivas), crear/editar (título, texto, fecha, ciudad o todas,
  enlace, destacada), subir portada, fotos (varias a la vez) y video con progreso, dar de baja.

## Criterios

1. El publicador crea «URUKU auspició el Festival del Lapacho» con portada, 4 fotos y un video;
   aparece primero en «Novedades» del inicio y en `/novedades`, con su página de detalle.
2. Una novedad de otra ciudad no aparece en Bermejo; una «de todas» sí.
3. Dada de baja, desaparece. Anon no lee `created_by` ni las inactivas.
4. Tests verdes, `tsc` y `next build` ok, sin emoji.
