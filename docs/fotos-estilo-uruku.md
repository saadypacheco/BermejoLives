# Fotos con estilo URUKU (portada y galería)

Pedido del dueño (21/11/2026). Amplía `docs/portada-diseno.md`; si se contradicen, manda este doc. Un botón **«Fotos»** en
cada fila de Admin › Comercios (permiso `comercios.editar`) abre una ventana con la portada y la galería del negocio; cada
foto se transforma a **un solo estilo URUKU**, el de los videos de `docs/reels-kit/`. Tres caminos (gratis, Gemini pago,
ChatGPT a mano) y **todos terminan en una propuesta privada** que una persona aprueba con «Usar en la ficha». Nada se publica solo.

## 0. Decisiones

| Decisión | Alternativas descartadas | Por qué | Qué la invalida |
|---|---|---|---|
| La plantilla se dibuja con **Pillow en el backend** (como hoy) | El contenedor `reels` (Chromium + el HTML del kit); canvas en el navegador | Ya existe, tarda ~0,1 s y tiene tests. `reels` puede estar apagado y es pesado para una imagen fija. El canvas no deja el archivo en el servidor. *Path dependence:* es lo de siempre, contrastado con las dos | Que el dueño quiera los componentes del kit idénticos al píxel, o que `reels` quede siempre prendido |
| **Galería sin textos de la base**: tarjeta + fondo URUKU + logo + `uruku.bo` | Franja con nombre/rubro/ciudad; chip con el nombre | La ficha ya muestra el nombre, y en la miniatura de la grilla el texto no se lee. Sólo vence si cambia la foto | Que las fotos se compartan sueltas en redes y el dueño quiera el nombre adentro (sumarlo es reversible) |
| Propuesta de galería privada **por columnas** en `comercio_fotos` (revoke de tabla + grant por columna) | Tabla aparte de propuestas; la propuesta sólo en el registro | Es el espejo de la 0145/0200; queda un solo lugar. El front ya pide columnas explícitas | Que algo con anon necesite `select=*` sobre `comercio_fotos` |
| La IA **sólo toca la foto**; textos y logo los pone siempre la plantilla | La IA arma la pieza entera | Lo decidió el dueño: así quedan todos iguales y ningún texto lo escribe un modelo | — |
| Modelo y costo en **settings vacíos por defecto** (sin ellos la IA no se ofrece) | Fijar un modelo en el código | Los ID cambian (2.5 Flash Image se cerró el 2/10/2026) y no hay que inventar precios | — |
| `photo_style_uses`: **sólo insert**, nunca se borra; el tope se cuenta en la base y dentro del lock | Contador en memoria | Si el proceso se reinicia, un contador en memoria vuelve a cero (regla 13). El registro es historia de costos | — |
| **Un solo lock** para portada, galería y los tres caminos (Gemini lo retiene hasta 60 s) | Cola + worker de fondo | Con 20 por día no se justifica otra pieza | Más de unas decenas por día, o subir `--workers` |
| La foto de origen se lee **del disco local o, sólo si hay bases listadas, por HTTPS** (QA lee de producción, §8.1) | Copiar el disco de prod a QA; reescribir las URLs en la base de QA | No hay que copiar 6000 fotos ni tocar datos. En producción el setting queda vacío y no hay red | Que QA tenga su propia copia de las fotos (el setting se vacía) |

KB aplicada: `lesson-supabase-cloud-grants-explicitos-en-migration`, `pattern-supabase-rls-policy`,
`lesson-supabase-service-role-key-nunca-en-frontend`, `lesson-nunca-delete-fisico-siempre-soft` (el registro no se borra),
`lesson-fotos-resize-1600px-jpeg-70-antes-de-subir`, `lesson-ssg-isr-en-catalogo-no-ssr-puro` (la ficha ve el cambio al revalidar).

## 1. El estilo (uno solo, para todos)

Tokens del kit (`reels-kit/prompt.md` §6) y del manual (pp. 22-28). Poppins sin emojis. El dorado va sólo en el logo, nunca en
textos. El logo va sin sombras ni efectos. **Ni la mejora ni la IA tiñen la foto**: los colores del producto no se tocan y
el verde lo pone la plantilla.

| Token | Valor |
|---|---|
| Fondo / franja | `#0F3423` → `#0B1E15` → `#08110C` (nunca negro puro) |
| Brillo | `rgba(38,185,105,.55)` desenfocado (galería) · `.30` (portada) |
| Acento | `#34D27F` (kick, ciudad, borde de la tarjeta) |
| Texto | `#FFFFFF` títulos · `#D2E2D8` secundario |
| Logo | `uruku-horizontal-color.png` (copia de `reels-kit/referencias/assets/logo.png`, 1738×563, versión «color · modo oscuro»). **Siempre abajo a la derecha** |

**Portada: 1600 × 1000 JPEG q85** (como hoy; la ficha la muestra entera)
```
+--------------------------------------------------------------+
|                    foto (cover, portada_pos)                  |
|                                                              |
|   ░░░░░░░░ franja #08110C, alfa 0 (y=420) → 235 (y=1000) ░░░   |
|  [ FERRETERÍA ]  <- kick: píldora #34D27F, Bold 30, mayúsc.    |
|  Ferretería El Sur          <- nombre Bold blanco 104→56,      |
|  de Bermejo                    ≤2 renglones                    |
|  Bermejo   <- ciudad SemiBold 46 #34D27F     [URUKU logo 300]  |
+--------------------------------------------------------------+
```
- Zona de texto: x 80..1188 (1108 px = 1600 − 80 − 300 − 64 − 48). El bloque se ancla abajo en y = 936.
- Logo: ancho 300 (alto ~97), en x 1236..1536, y 839..936 (margen 64). **Ningún texto pasa de x 1188**, así que el logo nunca lo pisa.
- Brillo `.30` (radio 420, desenfoque 80) centrado en (380, 900), detrás del texto. Se saca el velo de arriba y no lleva marco.
- Sin rubro no va kick; sin ciudad no va la última línea. Los cortes con «…» son los de hoy (nombre ≤ 120, kick ≤ 28 caracteres).

**Galería: 1080 × 1350 (4:5, el «-post» del KIT) JPEG q85 + miniatura 480 × 600 q74**
```
+------------------------------------+
|  fondo radial + brillo detrás       |
|  +------------------------------+  |
|  |  foto cover centrada          |  |  tarjeta 920×1150 (4:5) en (80,56)
|  |  radio 44, borde 3px #34D27F  |  |  + halo (borde desenfocado 18 px,
|  |  con halo                     |  |    alfa .45)
|  +------------------------------+  |
|  uruku.bo (Bold 40)  [URUKU 260]   |  pie y 1206..1350; logo en x 740..1000
+------------------------------------+
```

## 2. Los tres caminos

```
GRATIS   leer_foto_origen (§8.1) → recortar al formato → mejorar_gratis (Pillow) → plantilla → guardar → PROPUESTA
GEMINI   leer_foto_origen → ¿disponible? ¿tope? → recortar al formato y achicar a ≤1536 px → Gemini (prompt fijo, sin texto, timeout)
         → validar la imagen que vuelve → recortar al formato → plantilla → guardar → PROPUESTA (+ registro con costo)
CHATGPT  «Copiar instrucción» + «Descargar la foto» → la persona usa ChatGPT por su cuenta → «Subir imagen hecha afuera»
         → validar y normalizar (sin EXIF, alfa sobre blanco) → recortar al formato → plantilla → PROPUESTA (+ aviso)
PROPUESTA → «Usar en la ficha» (PUT, pasa a pública) | «Descartar» ;  en la ficha → «Volver a la original»
```
- **Gemini**: el pedido lleva `PROMPT` + la foto inline. Se piden `responseModalities: ["IMAGE"]` y `imageConfig.aspectRatio`
  (`"3:2"` la portada, `"4:5"` la galería), y se lee la primera `inline_data`/`inlineData` de la respuesta. **Antes de
  implementar se verifican en ai.google.dev:** el ID del modelo, el precio por imagen, si se cobra la imagen de entrada y los
  nombres de esos campos. Según el doc del 19/10/2026 (`investigacion-costos-automatizacion.md`), el candidato es Gemini 3.1
  Flash Lite Image a ~US$ 0,0336 por imagen 1K. **No tiene nivel gratis**: la clave tiene que tener facturación activa.
- **Verificado en la doc oficial (21/11/2026)**, antes de escribir la llamada. Fuentes: `ai.google.dev/gemini-api/docs/models`,
  `/docs/image-generation`, `/docs/pricing` y `/docs/models/gemini-3.1-flash-lite-image` (Google las redirige a
  `aistudio.google.com/docs/...`).
  - **Modelo**: `gemini-3.1-flash-lite-image` (Nano Banana 2 Lite), estado «Stable»; la página del modelo dice «última
    actualización: junio de 2026». Los demás: `gemini-3.1-flash-image` (US$ 0,067 por imagen 1K), `gemini-nano-banana-2.1`
    («New»; US$ 0,0336 1K pero entrada a US$ 1,50 por millón de tokens) y `gemini-3-pro-image` (US$ 0,134). **`gemini-2.5-flash-image`
    está deprecado y se apaga el 15/3/2027**: no usarlo. El setting `GEMINI_IMAGE_MODEL` queda vacío; para activar la IA en QA:
    `GEMINI_IMAGE_MODEL=gemini-3.1-flash-lite-image` y `GEMINI_IMAGE_COST_USD=0.034`.
  - **Precio** (pricing, tarifa Standard): **US$ 0,0336 por imagen de salida 1K** (el 1K es el único tamaño útil: el modelo sólo
    admite 512 y 1K) **más** la entrada a US$ 0,25 por millón de tokens (texto, imagen o video). La foto de entrada se cobra como
    tokens de entrada (estimado: unos pocos miles de tokens, menos de US$ 0,001): despreciable frente a la imagen, por eso el costo registrado es el de
    la imagen sola. **Ningún modelo de imagen tiene nivel gratis** (la clave necesita facturación). Batch cuesta la mitad, pero no
    sirve para un botón que espera la respuesta.
  - **Campos**: `generateContent` (`v1beta`) sigue documentado y no está marcado como retirado. `generationConfig.responseModalities`
    y `generationConfig.imageConfig.aspectRatio` (+ `imageSize`, con «K» mayúscula) se llaman así. Las proporciones del modelo
    incluyen **`3:2` y `4:5`**. La foto de entrada va en `contents[].parts[].inline_data` (`mime_type`, `data` en base64); la salida
    vuelve en `candidates[].content.parts[]` como `inlineData` (REST/JS) o `inline_data` (Python): el código lee las dos.
  - **Dudas que sólo el primer pedido real resuelve**: (1) la doc de ejemplo usa `responseModalities: ["IMAGE"]` solo, pero la
    página del modelo no lo afirma y una página de Vertex pide `["TEXT","IMAGE"]`; si Gemini contesta 400, se cambia en
    `fotos_estilo_gemini.armar_pedido` (el código ignora las partes de texto). (2) Google documenta ahora una API nueva
    (`/v1beta/interactions`, con `response_format.aspect_ratio`) como la principal; `generateContent` sigue vigente, y toda la
    llamada está en `fotos_estilo_gemini.py` para migrarla sin tocar nada más.
- **ChatGPT**: no se automatiza. No hay API gratis y no se automatiza una cuenta personal. La instrucción es el mismo prompt.
  Toda propuesta `gemini` o `external` muestra el aviso «Revisá que la imagen no traiga texto, precios ni cambios en los productos o
  el letrero antes de usarla».
- **Prompt fijo y versionado** en `backend/app/services/fotos_estilo_prompt.py` (`PROMPT_VERSION = "fotos-estilo-v1"`). El
  prompt nunca lleva datos del comercio. Texto v1 (inglés: los modelos de imagen respetan mejor el «sin texto» en inglés):
  > Edit the attached photo into a clean, premium advertising photo. Keep it REAL: same place, same products, same shapes,
  > same product colors, same number of items; do not invent, add or remove products; do not alter faces. Natural, even,
  > slightly warm light; recover shadows; vivid but true colors; no heavy filters, no HDR, no stock-photo look. Remove price
  > tags, price numbers, product codes, stock tables, watermarks and stickers added on top. Do NOT write any text, letters,
  > numbers or logos; leave the store's own sign exactly as it is. Keep the bottom quarter free of key details. One photo,
  > no borders, no frames.
  > COVER: storefront or shop interior; straighten vertical lines; tidy loose clutter in front; aspect 3:2.
  > GALLERY: product photo; center the main product on a clean light catalogue background with a soft shadow; aspect 4:5.

## 3. Vencimiento y ficha pública

- **Portada**: igual que hoy (`diseno_vencido`): vence si cambian la foto, el nombre, el rubro o la ciudad.
- **Galería** (no lleva textos de la base): vence **sólo si cambia la foto**. Hay dos casos:
  (a) `update_foto_comercio` con un `url` distinto (el intercambio de `portada.usar_de_galeria`): el repositorio vacía las tres
  columnas de diseño (`diseno_foto_vencido`) y quien llama suelta los archivos (el agente no borra);
  (b) se borra la fila (`borrar_foto`, que incluye el reemplazo en el tope): `borrar_archivos` suelta también los `diseno-*`.
  La original nunca se borra por un diseño.
- **Ficha**: en «Fotos del local», si una foto tiene `diseno_url`, la grilla muestra `diseno_thumb_url` y la ampliada `diseno_url`.
  La portada de diseño sigue como hoy. **Listados, buscador, mapa, carrusel de la home, videos y el análisis con IA siguen con la
  foto real** (`url`).
- Las portadas ya aprobadas con el estilo viejo (logo arriba) quedan como están hasta que alguien las rearme.

## 4. Datos (migración 0203)

`0203_fotos_estilo_uruku.sql`, idéntica en `supabase/migrations/` y `selfhost/postgres-init/`. En transacción, idempotente,
sin borrado físico, con `notify pgrst, 'reload schema'`.
```sql
alter table public.comercio_fotos add column if not exists diseno_url text;           -- pública
alter table public.comercio_fotos add column if not exists diseno_thumb_url text;     -- pública
alter table public.comercio_fotos add column if not exists diseno_propuesta_url text; -- PRIVADA
revoke select on public.comercio_fotos from anon, authenticated;
grant select (id, comercio_id, url, thumb_url, orden, created_at, diseno_url, diseno_thumb_url)
  on public.comercio_fotos to anon, authenticated;
grant all on public.comercio_fotos to service_role;

create table if not exists public.photo_style_uses (
  id uuid primary key default gen_random_uuid(),
  comercio_id uuid not null references public.comercios(id),
  foto_id uuid,                                  -- null = portada; sin FK (comercio_fotos borra físico)
  target text not null check (target in ('cover','gallery')),
  method text not null check (method in ('free','gemini','external')),
  model text, prompt_version text,
  cost_usd numeric(8,4) not null default 0,
  result text not null check (result in ('ok','error','timeout')),
  error text,                                    -- pasado por sin_secretos, ≤ 300 caracteres
  result_url text, actor text not null,          -- email de quien apretó
  created_at timestamptz not null default now());
create index if not exists idx_photo_style_uses_dia on public.photo_style_uses (method, created_at);
create index if not exists idx_photo_style_uses_comercio on public.photo_style_uses (comercio_id, created_at);
alter table public.photo_style_uses enable row level security;
revoke all on public.photo_style_uses from public, anon, authenticated;
grant select, insert on public.photo_style_uses to service_role;               -- sin update ni delete
-- cost_switches_key_check suma 'gemini_fotos'; insert ('gemini_fotos', false, 'migracion 0203') on conflict do nothing
```
Comprobación final (`do $chk$`, como la 0200/0187):
- anon/authenticated **no** tienen `select` de tabla sobre `comercio_fotos`, sí sobre las 8 columnas públicas y no sobre `diseno_propuesta_url`.
- **Toda** columna de `comercio_fotos` (`information_schema.columns`) está en la lista pública o en la privada: si aparece una nueva, la migración falla.
- RLS sigue prendida. Como anon, `count(id)` es igual a las fotos de comercios activos.
- `photo_style_uses`: RLS prendida, anon/authenticated sin ningún privilegio, service_role con `select` + `insert` y sin `update`/`delete`.
- El check admite `gemini_fotos` y la fila nace en `enabled = false`.

## 5. API

Permiso `comercios.editar` salvo que se diga otra cosa. Los errores van en español en `detail` y el front los muestra tal cual.

| Método | Ruta | Body | 200 |
|---|---|---|---|
| GET | `/admin/comercio/{id}/fotos-estilo` | — | `PhotoStyleState` |
| POST | `/admin/comercio/{id}/portada-diseno` *(existe)* | `{"method":"free"\|"gemini"}`; sin body = `free` | `CoverDesign` |
| POST | `/admin/comercio/{id}/portada-diseno/externa` | multipart `foto` | `CoverDesign` |
| PUT · DELETE `/propuesta` · DELETE | `/admin/comercio/{id}/portada-diseno` *(existen, sin cambios)* | — | `CoverDesign` |
| POST | `/admin/comercio/{id}/fotos/{foto_id}/diseno` | `{"method":"free"\|"gemini"}` | `GalleryItem` |
| POST | `/admin/comercio/{id}/fotos/{foto_id}/diseno/externa` | multipart `foto` | `GalleryItem` |
| PUT | `/admin/comercio/{id}/fotos/{foto_id}/diseno` (usar en la ficha) | — | `GalleryItem` |
| DELETE | `/admin/comercio/{id}/fotos/{foto_id}/diseno/propuesta` (descartar) | — | `GalleryItem` |
| DELETE | `/admin/comercio/{id}/fotos/{foto_id}/diseno` (volver a la original) | — | `GalleryItem` |
| GET | `/admin/fotos-estilo/usos?desde=AAAA-MM-DD&hasta=AAAA-MM-DD` (permiso `pagos`) | — | `UsesSummary` |

Errores: **400** sin foto, muy chica o angosta, imagen inválida o PUT sin propuesta · **403** sin permiso · **404** el comercio o
la foto no existen o la foto es de otro comercio · **409** «Ya se está armando otra foto, probá en unos segundos», o la foto/los
datos cambiaron mientras se armaba (se borra el archivo nuevo) · **413** > 15 MB · **429** «Se llegó al tope de N fotos con IA
por hoy» · **502** Gemini falló, no devolvió imagen o no se pudo guardar · **503** «Fotos con IA no disponible: <motivo>»
(interruptor apagado o falta la clave, el modelo o el costo) · **504** Gemini no contestó a tiempo.

## 6. Contrato JSON (lo que comparten backend y frontend)

```ts
type Method = "free" | "gemini" | "external";
type CoverDesign = { portada_diseno_url: string | null; portada_diseno_propuesta_url: string | null;
                     proposal_method: Method | null };               // se suma a las dos claves de hoy
type GalleryItem = { foto_id: string; photo_url: string; thumb_url: string | null;
                     design_url: string | null; design_thumb_url: string | null;
                     proposal_url: string | null; proposal_method: Method | null };
type PhotoStyleState = {
  comercio: { id: string; nombre: string; slug: string };
  cover: { photo_url: string | null; design_url: string | null; proposal_url: string | null; proposal_method: Method | null };
  gallery: GalleryItem[];                                              // en el orden de la galería
  gemini: { available: boolean; reason: string | null;                 // reason en español, para mostrar
            cost_usd: number; used_today: number; daily_cap: number;   // cost_usd = estimado por imagen
            merchant_uses: number; merchant_cost_usd: number };        // lo gastado con IA en ESTE comercio
  instructions: { version: string; cover: string; gallery: string };  // texto para ChatGPT
};
type UsesSummary = { desde: string; hasta: string; images: number; cost_usd: number;
  by_merchant: { comercio_id: string; nombre: string; images: number; cost_usd: number }[] };
```
`proposal_method` sale de la última fila de `photo_style_uses` cuyo `result_url` es esa propuesta (`null` si no hay ninguna).
Archivos: `<slug>/diseno-<token>.jpg` y, en galería, `<slug>/diseno-<token>-t.jpg`. La miniatura se arma junto con la propuesta
y el PUT copia la URL derivada a `diseno_thumb_url`.

## 7. Pantalla: ventana «Fotos»

Hoja inferior (como `video-negocio-modal.tsx`), montada con `Portal`. Escape cierra.
```
+-- [foto] Fotos de Ferretería El Sur ------------------------------ [Cerrar] --+
| Lo armás, lo mirás y recién con «Usar en la ficha» se publica.               |
| Listados, buscador y mapa siguen con la foto real.                           |
| IA: ≈ US$ 0,034 por foto · hoy 3 de 20 · este negocio: 2 (≈ US$ 0,07)        |
|     (si no está disponible: el motivo en ámbar y el botón «Con IA» apagado)   |
| PORTADA  [original 160] [en la ficha 160 | «sin diseño»] [propuesta 320]     |
|  [Gratis] [Con IA ≈ US$ 0,034] [Copiar instrucción para ChatGPT]             |
|  [Descargar la foto] [Subir imagen hecha afuera]                             |
|  Propuesta (hecha con IA | afuera: «Revisá que no traiga texto…»)            |
|  [Usar en la ficha] [Descartar]        en la ficha: [Volver a la original]   |
| GALERÍA (12)                                                                 |
|  [thumb · Original] [thumb · Con diseño] [thumb · Propuesta lista] ...       |
|  tocar una → se despliega abajo la misma botonera que la portada             |
+------------------------------------------------------------------------------+
```
- «Con IA» pide confirmación en el mismo botón («Confirmar ≈ US$ 0,034»). Mientras corre, todos los botones de transformar
  quedan quietos y se ve «Puede tardar hasta un minuto». Después de un `gemini` se vuelve a pedir el GET para actualizar el contador.
- La galería se pinta con miniaturas lazy (puede haber hasta 300 fotos). Los íconos salen de `Ic`: `foto`, `ia`, `copiar`, `descargar`, `subir`.
- El bloque viejo `PortadaDisenoBloque` del modal de edición queda como está: llama al mismo POST sin body y sale con el estilo nuevo.

## 8. Límites (un solo worker)

- **Un lock** `fotos_estilo._TRANSFORMAR` (reemplaza a `portada_diseno._RENDER`) para todo. Espera 5 s y si no, 409. Todo corre en `run_in_threadpool`.
- **Recortar antes de escalar** siempre (`resize(box=)`). A Gemini va ≤ 1536 px del lado mayor en JPEG q85. Se valida lo que
  vuelve con los topes de `_abrir`: JPEG/PNG/WEBP, ≤ 40 MP, ≤ 20 MB decodificado.
- **Timeout** de Gemini: `GEMINI_IMAGE_TIMEOUT_SEG` (60). **Tope**: `GEMINI_FOTOS_TOPE_DIARIO` (20) llamadas `gemini` desde las
  00:00 de Bolivia (`cargas.hoy_bolivia`), contadas dentro del lock. Cuentan también las que fallaron.
- **Registro**: toda llamada a Gemini se registra en un `finally` (ok, error o timeout). `cost_usd` = el setting si hubo imagen o
  timeout, 0 si Gemini contestó con error. `free` y `external` se registran sólo cuando salen bien, con costo 0.
- **Externa**: ≤ 15 MB, lado menor ≥ 512 px, proporción ≤ 4:1. Se recodifica a JPEG sin EXIF.
- Disponibilidad de la IA = interruptor `gemini_fotos` prendido + `GEMINI_API_KEY` + `GEMINI_IMAGE_MODEL` + `GEMINI_IMAGE_COST_USD > 0`.
  Los errores pasan por `gemini.sin_secretos()`.

### 8.1 Leer la foto de origen (y el caso de QA)

**El problema.** La base de QA es una copia de la de producción. De las 6090 portadas activas, 6089 apuntan a
`https://api.uruku.bo/fotos/<slug>/<archivo>.jpg`, pero esos archivos están en el disco de **producción**, y QA tiene
`FOTOS_PUBLIC_BASE_URL=https://api.encontralo.store/fotos`. Entonces `_ruta_en_disco` devuelve None y la portada de diseño de hoy falla en QA
con «No se pudo leer la foto de portada desde el servidor». En producción las URLs coinciden y anda.

**La solución: un helper compartido** `leer_foto_origen(url, slug=None) -> bytes | None` en `app/services/fotos_origen.py`. Lo usan
`portada_diseno.leer_portada` y los tres caminos, en portada y en galería. Nadie más lee la foto de origen por su cuenta.
1. **Disco local primero**: `_ruta_en_disco(url, slug)` + `is_file` + tamaño ≤ `MAX_BYTES_FOTO` (8 MB). Es lo de hoy.
2. **Si no está en el disco**, y sólo si el setting `FOTOS_LECTURA_REMOTA_BASES` tiene algo (bases separadas por comas; vacío por
   defecto, **producción no lo usa**; en QA vale `https://api.uruku.bo/fotos`), se descarga **por HTTPS** siempre que la URL:
   - empiece **exactamente** con una de esas bases (se normalizan con `/` al final; las que no son `https://` se ignoran y se avisa en el log al arrancar);
   - pase **la misma validación estricta** que `_ruta_en_disco`: dos tramos `<slug>/<archivo>.jpg`, sin `?`, `#`, `%`, `\`, NUL, `.` ni `..`,
     y con `slug` la carpeta tiene que ser ese slug. La validación se saca a una función pura (`ruta_relativa_canonica(url, base)`) que usan
     las dos, para que no se separen nunca. Para leer se llama **sin** `slug`, como hoy `leer_portada`: un comercio renombrado
     deja sus fotos en la carpeta del slug viejo.
3. La descarga usa `httpx` con **timeout corto** (conexión 3 s, total 10 s) y **sin seguir redirecciones**
   (`follow_redirects=False`: un 3xx da None). Sólo acepta 200. Corta en `MAX_BYTES_FOTO` (si `Content-Length` pasa el tope, ni la
   baja; si no viene, lee en streaming y corta en tope + 1). El resultado es `bytes`, y Pillow lo valida después igual que una foto local.
4. **Sólo sirve para LEER la foto de origen.** Lo que se arma se guarda en el disco local, como siempre. Nunca se escribe ni se
   borra nada remoto. Se lee **fuera del lock**: una descarga lenta no frena a nadie. Se registra el evento
   `fotos.lectura_remota` con host, resultado y bytes (sin la URL completa).

## 9. Reparto (dos devs en paralelo; el contrato es §5 y §6)

**BACKEND** (no toca `frontend/`)
1. `supabase/migrations/0203_fotos_estilo_uruku.sql` + la copia idéntica en `selfhost/postgres-init/` (§4).
2. `app/core/config.py`: `gemini_image_model: str = ""`, `gemini_image_cost_usd: float = 0.0`, `gemini_fotos_tope_diario: int = 20`,
   `gemini_image_timeout_seg: int = 60`. Sumarlos a `backend/.env.example`, sin valores reales.
3. `app/core/gemini.py`: `url_generar_imagen()`, con el modelo `gemini_image_model`, las mismas cabeceras y sin clave en la URL.
4. `app/services/cost_switches.py`: `GEMINI_FOTOS = "gemini_fotos"` en `CATALOGO` (label «Fotos con IA (Gemini)», costo
   «aprox. US$ 0,03-0,04 por imagen, tope 20 por día, sin nivel gratis», off_means «quedan la plantilla gratis y ChatGPT a mano»).
5. Nuevos: `app/services/fotos_estilo_prompt.py` (versión + prompts §2), `app/services/fotos_estilo_gemini.py`
   (`reestilizar(jpeg, target) -> bytes`, con `GeminiNoDisponible`/`GeminiFallo`/`GeminiTimeout`) y `app/services/fotos_estilo.py`
   (lock, `plantilla_portada`, `plantilla_galeria`, miniatura, disponibilidad, tope, registro, `estado()` para el GET).
6. `app/services/portada_diseno.py`: estilo nuevo (§1), logo abajo a la derecha, sin velo arriba, lock movido a `fotos_estilo`.
   Copiar `docs/reels-kit/referencias/assets/logo.png` a `app/assets/content/uruku-horizontal-color.png`.
7. `app/db/repository.py` (el Protocol y la implementación) y el FakeRepo de `tests/conftest.py`: `registrar_uso_foto_estilo`,
   `contar_usos_gemini_desde`, `usos_foto_estilo(comercio_id)`, `resumen_usos_foto_estilo(desde, hasta)`, y `diseno_foto_vencido`
   dentro de `update_foto_comercio`.
8. `app/services/fotos_galeria.py` (`borrar_archivos` suelta los `diseno-*` de la fila) y `app/services/portada.py`
   (`usar_de_galeria` suelta el diseño de la fila intercambiada, salvo `conservar_archivos`).
8b. Lectura de la foto de origen (§8.1). Nuevo `app/services/fotos_origen.py` con `leer_foto_origen` y `ruta_relativa_canonica`.
   En `fotos_galeria._ruta_en_disco`, usar la función pura. En `config.py`, `fotos_lectura_remota_bases: str = ""` y
   `fotos_lectura_remota_bases_list()`. `portada_diseno.leer_portada` delega en el helper. Sumar la variable a `.env.example`
   (vacía) y avisar en `docs/deploy-qa.md` que en QA va `https://api.uruku.bo/fotos`.
9. Endpoints: los de portada siguen en `app/api/moderacion.py` (POST con `method`, más `/externa`). Lo nuevo va en
   `app/api/fotos_estilo.py`, registrado en `main.py`.
10. Tests:
    - `test_fotos_estilo_plantillas.py`: tamaños, logo abajo a la derecha, la caja del logo no se cruza con el texto aunque el
      nombre tenga 120 caracteres, galería sin texto de la base, franja verde y no negra.
    - `test_fotos_estilo_endpoints.py`: cada ruta, cada código de §5, 409 por el lock, tope 429, timeout 504 con su fila en el
      registro, la clave nunca aparece en `detail` ni en el registro, el payload a Gemini no lleva el nombre del comercio.
    - `test_fotos_estilo_vencimiento.py`: el intercambio y el borrado de la foto; el agente no borra.
    - `test_0203_fotos_estilo.py`: copias idénticas, grants, privilegios, check del interruptor, sin delete.
    - `test_comercio_fotos_columnas_publicas.py`: como el de `comercios`; ningún select del front con `*` ni con columnas privadas.
    - `test_fotos_estilo_prompt.py`: el sha256 del prompt va atado a `PROMPT_VERSION`.
    - `test_fotos_origen.py` (con `httpx.MockTransport`): base no listada → None; ruta con `..` (y con `%2e`, `?`, `\`, tres
      tramos o algo que no es `.jpg`) → None; redirección → no la sigue y da None; `http://` en el setting → se ignora; pasa
      `MAX_BYTES_FOTO` → None; está en el disco → no hay red; setting vacío → nunca hay red; 200 válido → los bytes. Y que
      la portada de diseño anda con una portada de otra base listada (el caso QA).
    - Actualizar en `test_portada_diseno.py` el test del logo «arriba a la derecha».

**FRONTEND** (no toca `backend/` ni las migraciones)
1. Nuevos: `lib/fotos-estilo.ts` (los tipos de §6 y una función por ruta de §5, con `authFetch`; las multipart con
   `FormData` campo `foto`) y `lib/fotos-estilo-pure.ts` (`textoCosto(0.0336) → "≈ US$ 0,034"`, `estadoFoto(item)`,
   `avisoPropuesta(method)`, `puedeIA(gemini)`).
2. Nuevo: `components/admin/fotos-estilo-modal.tsx` (§7). Copiar al portapapeles con `navigator.clipboard.writeText` y avisar
   «Copiado».
3. `app/admin/page.tsx`: botón `mbtn` «Fotos» (`<Ic n="foto" />`) al lado de «Video», visible con `puedeEditar`. Estado
   `fotosDe`, montado con `Portal` como `VideoNegocioModal`.
4. Ficha: `lib/data-pure.ts` (`GaleriaFoto` suma `diseno_url?` y `diseno_thumb_url?`), `lib/data.ts` (`getGaleriaComercio` pide
   también esas dos columnas; `getFotosDeComercios` no cambia) y `lib/portada-diseno.ts` (`fotosDeFicha` cambia `url`/`thumb_url`
   por las de diseño **después** de buscar la portada original por su `url` real).
5. Tests (`node --test`): `tests/fotos-estilo.test.ts` (las funciones puras) y casos nuevos en `tests/portada-diseno.test.ts`
   (galería con diseño; la original no se duplica).

Para probar sin backend, el front puede simular el GET con el JSON de §6. **Terminado** = los tests de las dos partes pasan, la
0203 corre dos veces sin error, con el interruptor apagado la ventana muestra el motivo y deja usar Gratis y ChatGPT, y en QA
(con `FOTOS_LECTURA_REMOTA_BASES` puesto) la portada de diseño se arma con una portada de `api.uruku.bo`.

## 10. Para confirmar con el dueño

1. **Galería sin nombre** (sólo la tarjeta, el logo y `uruku.bo`): ¿le va así, o quiere el nombre adentro?
2. **¿La clave de Gemini tiene facturación?** Sin facturación el camino IA no anda (los modelos de imagen no tienen nivel gratis).
3. **¿Se le cobra al comercio** que pide la versión con IA? El registro ya da lo gastado por comercio (`/usos`); cobrar queda fuera de esta spec.
4. **¿La ficha avisa «Foto mejorada con IA»** en las que pasaron por Gemini o ChatGPT? Hoy no se avisa.
5. El prompt de portada es conservador (no cambia la fachada ni el letrero). El análisis previo desaconsejaba la IA en las fotos
   del local: el dueño ya lo decidió, así que lo que queda como resguardo es la revisión humana.
