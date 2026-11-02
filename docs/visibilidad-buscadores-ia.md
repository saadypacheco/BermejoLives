# Visibilidad en buscadores y asistentes de IA — spec

> **Estado:** propuesta para aprobar · **Fecha:** 2026-11-02 · **Rol:** architect
> **Entradas:** `AGENTS.md`, `docs/handoff-2026-10-03.md`, `docs/cuentas-uruku.md`,
> `docs/investigacion-redes-y-busqueda-ia.md` §5 (researcher), código en `main` (`4ca9d81`),
> sitio en vivo y PostgREST público (`db.uruku.bo`, clave anon) consultados el 2/11.
> **KB aplicada:** `2026-06-04-stack-bermejo`, `lesson-ssg-isr-en-catalogo-no-ssr-puro`,
> `pattern-fire-and-forget-tracking`, `lesson-supabase-cloud-grants-explicitos-en-migration`,
> `pattern-supabase-rls-policy`, `pattern-soft-delete-activo-flag`,
> `lesson-supabase-service-role-key-nunca-en-frontend`.
>
> Las cifras de esta spec son **internas** (calidad de datos). Ninguna va al sitio: la
> regla «nunca mostrar cifras de comercios al público» sigue valiendo para todo lo que
> se construya acá, incluido el JSON-LD.

---

## 0. Expectativa honesta

**Nadie puede garantizar que una IA muestre a URUKU primero.** La respuesta cambia según el
asistente, el modelo, si busca en la web o no, desde dónde pregunta la persona, cómo lo
escribe y el día. Lo que sí se puede es **subir la probabilidad** con cinco palancas, en
este orden de peso:

1. **Acceso:** que ningún robot de búsqueda o de asistente quede bloqueado (hoy hay
   bloqueos, §1.1).
2. **Indexación:** estar bien indexado en Google y en Bing (ChatGPT y Copilot se apoyan en
   Bing; Gemini y AI Overviews en el índice de Google).
3. **Contenido que responde:** páginas estables, con texto en el HTML, que contestan
   directo la pregunta que la gente hace («dónde comprar X en Bermejo»), con fecha visible.
4. **Entidad coherente:** el mismo nombre, la misma frase y los mismos datos de contacto en
   el sitio, el JSON-LD y cada perfil externo; y menciones de terceros que lo confirmen.
5. **Frescura:** datos con fecha. Un «cotización hoy» de hace 8 días es peor que no
   decir nada, porque la IA lo repite con el nombre de URUKU.

El objetivo medible no es «primer puesto»: es **(a)** que URUKU aparezca citado en las
preguntas del panel mensual (§3.11) y **(b)** que crezcan las visitas que llegan desde
asistentes (`ai_sources`, §3.11).

---

## 1. Estado actual (hallazgos)

### 1.1 Acceso de los robots — hay dos capas de bloqueo en Cloudflare

`uruku.bo` está detrás de Cloudflare (`Server: cloudflare`, `CF-RAY`). Cloudflare hace dos
cosas que el código no controla:

- **robots.txt gestionado:** antepone su bloque al nuestro. El `robots.txt` servido
  empieza con `Content-Signal: search=yes,ai-train=no` y `Disallow: /` para GPTBot,
  ClaudeBot, Google-Extended, Applebot-Extended, meta-externalagent, Amazonbot, CCBot,
  Bytespider, GoogleOther, Google-CloudVertexBot y otros. Después viene lo de
  `frontend/app/robots.ts:27`.
- **Bloqueo de «AI bots» a nivel WAF:** con `curl -A` el 2/11, **GPTBot, ClaudeBot,
  Amazonbot, CCBot y Bytespider reciben `403 Your request was blocked.`** en `/`, en una
  ficha y en `/sitemap.xml`.

Matriz completa en §3.4. Resumen: los robots de **búsqueda** y los que disparan
**usuarios** (OAI-SearchBot, ChatGPT-User, Googlebot, bingbot, Claude-SearchBot,
Claude-User, PerplexityBot, Perplexity-User, Applebot, DuckAssistBot, meta-externalfetcher,
MistralAI-User) **responden 200**. Lo bloqueado es entrenamiento y, por robots.txt,
**Google-Extended** —que según Google también controla el *grounding* de la app Gemini—
y **meta-externalagent** (Meta AI, que está adentro de WhatsApp).

Nota: `docs/investigacion-redes-y-busqueda-ia.md` §5.5 dice «ya hay SSG+ISR» en las
fichas. **No es así:** la ficha es `force-dynamic` (ver 1.5).

### 1.2 robots.ts y sitemap.ts

| Hallazgo | Evidencia |
|---|---|
| robots de prod correcto pero sin grupos por robot; Cloudflare lo pisa para los bots de IA | `frontend/app/robots.ts:26-28`; robots.txt en vivo |
| El sitemap trae las 10 páginas fijas y todas las fichas activas (5.951 URLs, 1 MB) | `frontend/app/sitemap.ts:20-34`, `:39-47`; `curl https://uruku.bo/sitemap.xml` |
| `lastModified` usa `created_at`, **existe `updated_at` con trigger** | `sitemap.ts:40,44`; trigger `supabase/migrations/0001_init.sql:150-161`; `updated_at` ya es pública (`frontend/lib/data.ts:42`) |
| Mete `/buscar` y `/buscar?vista=mapa`, que son pantallas 100 % de cliente (el HTML inicial no tiene ni un enlace a una ficha) | `sitemap.ts:22-23`; `curl /buscar?rubro=farmacia` → 0 enlaces a `/comercios/` |
| Faltan: páginas por ciudad, por ciudad+rubro (no existen), `/novedades/uruku/[id]`, `/agentes`, `/que-es-uruku` (está en `noindex`) | `sitemap.ts`; `app/que-es-uruku/page.tsx:14` |
| Entran fichas vacías: 3.128 de 5.951 fichas activas son rubro «otros», sin subcategoría, sin descripción y sin productos (Santa Cruz 312/313, La Paz 1.598, Tarija 1.207, Bermejo 11). 699 se llaman literalmente «Otros (a clasificar)» | consulta a PostgREST 2/11 |
| `www.uruku.bo` responde **200** con el mismo sitio (no redirige a `uruku.bo`) → host duplicado | `curl -I https://www.uruku.bo/` |

### 1.3 Metadata por página

| Página | Hallazgo | Evidencia |
|---|---|---|
| Todas | La plantilla del layout agrega ` · Uruku` y las páginas ya traen `— URUKU` / `\| URUKU` → «X — URUKU · Uruku» | `app/layout.tsx:45`; `comercios/[slug]/page.tsx:38`; `guia/page.tsx:22`; `cambio/page.tsx:16`; `ofertas`, `novedades`, `comunidad` |
| Ficha | Título con nombre + rubro + ciudad (bien), pero muestra «Otros (a clasificar)» cuando el rubro es `otros`: «Marck lucky — Otros (a clasificar) en Tarija \| URUKU · Uruku» | `comercios/[slug]/page.tsx:37-38`; muestreo de 14 fichas |
| Ficha | Descripción promete «WhatsApp y ofertas» siempre; 160 de 5.951 tienen WhatsApp | `page.tsx:41` |
| Ficha | `canonical` y `og:image` (portada) sí; `og:image` sin tamaño ni `alt`; portadas de 100–325 kB (límite práctico de WhatsApp ~300 kB) | `page.tsx:42-49`; `curl -I` a portadas |
| Home, guía, cambio, ofertas, novedades, comunidad, agentes | **Sin `canonical`** (con el `www` duplicado, importa) | `curl` + grep `rel="canonical"` |
| `/cambio` | Título fijo «Cotización en Bermejo **hoy**»; la cotización en la base es del **25/10** (8 días) | `cambio/page.tsx:16`; tabla `cotizaciones.actualizado_en` |
| `/que-es-uruku` | La página que contesta «¿qué es URUKU?» está en `noindex, nofollow` y su texto habla sólo de Bermejo | `app/que-es-uruku/page.tsx:12-14`; `content/manuales/uruku.md:3` |
| `/buscar` | Sin metadata propia; resultados sólo en cliente | `app/buscar/page.tsx` |

### 1.4 Datos estructurados

No hay ni un `application/ld+json` en el sitio (grep en `frontend/` y en el HTML en vivo).
Existe `comercios.rating` (default 0) en las columnas públicas (`lib/data.ts:41`): **no se
usa nunca** en JSON-LD (no hay reseñas reales).

### 1.5 HTML server-side de la ficha

- La ficha es `export const dynamic = "force-dynamic"` (`comercios/[slug]/page.tsx:27`)
  porque el marco lee la ciudad de una cookie (`components/uruku-shell.tsx:51-53` →
  `lib/ciudad-server.ts:16`). Respuesta: `Cache-Control: private, no-cache, no-store`,
  `cf-cache-status: DYNAMIC`. Contradice AGENTS.md regla 9 y
  `lesson-ssg-isr-en-catalogo-no-ssr-puro`.
- **El encabezado dice «Bermejo» y muestra pesos argentinos en fichas de La Paz o Tarija**:
  el robot no manda cookie y el marco cae en la ciudad de respaldo. Un asistente que lee
  la ficha de una óptica de La Paz ve «Bermejo» arriba.
- Texto visible real: ~1.300 caracteres, de los cuales ~1.000 son encabezado y pie. Lo
  propio del local: nombre (h1), rubro, descripción y fichas de «lo que vende» si existen
  (`page.tsx:209-217`), calle si no hay dirección (`page.tsx:336-341`). **La ciudad no
  aparece en el cuerpo.** No hay migas de pan.
- El sello «De turno ahora» se calcula en el servidor con `new Date()` (`page.tsx:80,99`):
  si la ficha pasa a ISR, ese cálculo tiene que ir al cliente.

### 1.6 URLs estables por ciudad y por rubro

- No existen. `/bermejo` es un redirect viejo a `/publicar` (`app/bermejo/page.tsx:2`,
  307); `/santa-cruz` y `/bermejo/farmacias` dan 404.
- Lo único por rubro es `/buscar?rubro=…`, que es cliente puro (1.2).
- La home enlaza 8 fichas. Las ~6.000 fichas se descubren sólo por el sitemap.
- Ciudades activas en la base: bermejo, santa-cruz, la-paz, cochabamba, tarija.
  Cochabamba no tiene comercios. Pares ciudad×rubro (sin «otros») con ≥ 5 comercios: 125;
  con ≥ 1: 170.

### 1.7 «Qué podés encontrar acá»

- `comercios.productos` nació en `0046_comercio_productos.sql:13` y la `0047` la renombró
  a `prod_obs_human` (lo que vio una persona) + `prod_det_ia` (lo que leyó la IA de la
  foto) + `subcategoria`. Las tres alimentan el índice `busqueda`.
- `0074_productos_en_resultados.sql` hace que `buscar_comercios` devuelva
  `prod_obs_human`/`prod_det_ia`.
- La ficha ya los muestra como fichas sin título (`page.tsx:53-62,105,213-217`, tope 12).
- `producto_ref` (catálogo Reservalo) existe en `lib/data.ts:766` pero **no se usa** en
  ninguna página.
- Cobertura: 1.542 comercios con algo de «lo que vende»; 1.263 con descripción.

### 1.8 Otros datos que condicionan el diseño

| Dato | Valor | Consecuencia |
|---|---|---|
| `horario` cargado | 313, de los cuales 249 son `horario_estimado` (horario típico de la zona) | `openingHoursSpecification` sólo para los 64 no estimados |
| `whatsapp` / `telefono` | 160 / 28 | `telephone` casi nunca; la descripción no promete WhatsApp |
| Redes del comercio (`instagram_url`, …) | 0 | `sameAs` del comercio vacío por ahora; se implementa igual |
| `direccion` / `calle` / `lat` | 27 / 1.245 / 5.941 | `geo` siempre; `streetAddress` = `direccion` o `calle` |
| `monedas_aceptadas` | 0 | `paymentAccepted` sólo si existe |
| Redes de URUKU (`redes_sociales`) | TikTok `@uruku.bo`, Instagram `@uruku.bo` (**perfil caído**), Facebook URL, YouTube `@Uruku-Bermejo` | `sameAs` necesita URLs absolutas y sin Instagram hasta que vuelva |
| Saber local | `backend/data/saber_local/bermejo.json`: 75 preguntas reales (38 `verificado: true`). En la tabla pública `saber_local` hay 22 | El contenido «que responde» ya existe; falta cargarlo verificado |
| Cotización / estado del paso | Última carga 25/10 | Ver regla de frescura §3.8 |

### 1.9 Medición

- `visitas` (`0130_visitas.sql`) ya guarda `origen` = `?ref=` o `?utm_source=`
  (`components/contador-visitas.tsx:93`) y `referido` = host de donde vino, en la primera
  página de la sesión (`:50-58,94`). El backend limpia con `limpiar_ref`
  (`backend/app/core/text.py:21-29`): `chatgpt.com` sobrevive. **El dato ya se está
  juntando.**
- Falta: agruparlo. `resumen_visitas` muestra sólo los 8 orígenes y 8 referidos más
  frecuentes (`backend/app/db/repository.py:3988-4007`); un asistente con pocas visitas no
  aparece.
- La vista de ficha (`leads` tipo `vista`) lee sólo `?ref=`, no `utm_source`
  (`components/vista-logger.tsx:13`).
- ChatGPT agrega `utm_source=chatgpt.com` a los enlaces que cita (researcher §5.4), pero
  hay reportes de octubre 2026 de clics sin UTM ni referrer → se subcuenta.

---

## 2. Decisiones

**Path dependence:** todo esto se resuelve dentro del stack de siempre (Next.js 14 App
Router + FastAPI + PostgREST, `2026-06-04-stack-bermejo`). Se contrastó con dos
alternativas reales antes de confirmarlo (D-1).

| # | Decisión | Alternativas descartadas | Por qué | Qué la invalidaría |
|---|---|---|---|---|
| D-1 | **Páginas nuevas en el mismo Next.js, SSG + ISR** (`revalidate`, `generateStaticParams` vacío = render a pedido y caché) | (a) Micrositio estático aparte (Astro) leyendo PostgREST: otro deploy y el sistema de diseño duplicado. (b) Servicio de prerender (Prerender.io/Rendertron) para `/buscar`: pago, más infra, y sigue sin dar URLs estables por rubro | Reusa marco, datos y deploy; el equipo ya lo opera. ISR evita pegarle a la base en cada visita de robot | Que el marco no pueda dejar de leer la cookie (entonces todo queda dinámico y hay que medir carga en el VPS) |
| D-2 | **Robots: permitir explícitamente a todos los de búsqueda, usuario y asistente, incluidos los de entrenamiento** (GPTBot, ClaudeBot, Google-Extended, Applebot-Extended, meta-externalagent, Amazonbot, CCBot). Bloquear Bytespider y la lista de scrapers. Las reglas viven en `robots.ts` (versionado) y se apaga el robots gestionado de Cloudflare | (a) Dejar a Cloudflare como está: Gemini app y Meta AI quedan sin poder usar el sitio. (b) Permitir sólo búsqueda: lo que el modelo «sabe» sin buscar no incluye a URUKU | El objetivo del dueño es «cualquier IA». Google-Extended controla el grounding de Gemini; meta-externalagent alimenta a Meta AI (WhatsApp). Los datos ya son públicos a propósito | **Decisión del dueño** (reuso de datos de comercios por terceros, incluido Common Crawl). Si se rechaza el entrenamiento, se mantiene permitido todo lo de búsqueda/usuario y Google-Extended + meta-externalagent como mínimo |
| D-3 | **Rutas `/{ciudad}` y `/{ciudad}/{rubro}`** con el slug de rubro actual (`/bermejo/farmacia`, `/la-paz/ropa`) | (a) `/ciudad/{ciudad}/{rubro}`: más larga, sin ventaja. (b) Slugs en plural nuevos (`/bermejo/farmacias`): columna nueva + redirecciones; la palabra en la URL pesa poco | Corta, legible, coincide con «una dirección por ciudad» del handoff. El slug de rubro ya es estable (`/buscar?rubro=`, íconos) | Si el dueño quiere plurales: columna `rubros.public_slug` + 301 desde el slug actual |
| D-4 | **`noindex, follow` en páginas pobres**: par ciudad+rubro con < 5 comercios; ciudad sin ningún par indexable; ficha «vacía» (rubro `otros` y sin subcategoría, descripción ni productos, o nombre «… a clasificar»). Par/ciudad inexistente o inactivo → **404** | Indexar todo: miles de páginas casi iguales («Otros (a clasificar) en Santa Cruz») bajan la calidad percibida del sitio y gastan rastreo | Google y Bing evalúan el sitio entero; mejor 1.600 fichas buenas que 6.000 con 3.000 vacías | Que el dueño quiera que todo comercio aparezca buscando su nombre (riesgo R-3). La ficha vacía se vuelve indexable sola cuando se clasifica |
| D-5 | El umbral (5) y el «indexable» de los pares **viven en SQL** (`city_category_pages()`); la regla de ficha vacía vive en TS (`lib/seo.ts`) y la usan ficha y sitemap | Contar en Next paginando `comercio_rubros` (ya hay 5.951 comercios; la memoria del proyecto dice pasar a SQL agrupado a los 5.000). Exponer el número por API | Una sola fuente de verdad por regla. La función devuelve un booleano, no el número | Si hace falta umbral por ciudad: parámetro en una tabla de config, no en el front |
| D-6 | **Ficha a ISR** (`revalidate = 300`) con el marco recibiendo la ciudad del comercio (`fixedCity`) en vez de la cookie | Seguir dinámica: cada robot = 6 consultas a la base; y el encabezado sigue diciendo «Bermejo» en La Paz | AGENTS.md regla 9; ciudad correcta para robots y personas | Que el equipo no tolere 5 min de demora tras editar en el panel → P2 revalidación a pedido |
| D-7 | **Sin hreflang** es-AR/es-BO | Duplicar páginas por país con hreflang | Hay una sola versión de cada página y un solo idioma; hreflang sirve para versiones alternativas de la misma página. Para el público argentino se escribe contenido para él (§3.9) y se nombran sus lugares | Que se hagan versiones distintas por país (precios en ARS, otro texto) de las mismas páginas |
| D-8 | `/que-es-uruku` pasa a ser **la página «Acerca de / Prensa»** indexable (misma URL, texto multi-ciudad) | URL nueva `/acerca`: se pierde la dirección que ya se le dio a medios | La URL ya circula desde el 7/10 | — |
| D-9 | **IndexNow por «pull»**: un loop del backend cada 15 min mira `comercios.updated_at` y `publicaciones.approved_at` y avisa | Enganchar el aviso en cada punto que edita un comercio (5 llamadas a `update_comercio`) | Un solo lugar, no se olvida ningún camino; mismo patrón que los loops de `backend/app/main.py:179-198` | Si se necesita aviso instantáneo |
| D-10 | URLs públicas en español (`/comprar-en-bermejo`) aunque los identificadores van en inglés | URL en inglés | Es contenido para personas y para la búsqueda en español; igual que `/ofertas`, `/guia` | — |

---

## 3. Diseño

### 3.1 Reglas de indexación (un solo módulo: `frontend/lib/seo.ts`)

```text
isBusinessThin(c) =
     (c.rubro_slug in (null, 'otros'))
 and blank(c.subcategoria) and blank(c.descripcion)
 and blank(c.prod_obs_human) and blank(c.prod_det_ia)
  or c.nombre matches /a clasificar/i

isBusinessIndexable(c) = c.activo and not c.suspendido and not isBusinessThin(c)

Par ciudad+rubro:  no existe / ciudad inactiva / rubro 'otros' o inactivo -> 404
                   existe y indexable=false                                -> 200 + noindex,follow
                   existe y indexable=true                                 -> 200 + index
Ciudad:            inactiva o inexistente -> 404
                   activa sin ningún par indexable -> 200 + noindex,follow
```

Ningún número de comercios se muestra (ni «12 farmacias», ni `numberOfItems` en ItemList).

### 3.2 Contrato SQL (migración)

`supabase/migrations/0180_city_category_pages.sql` (espejada en
`selfhost/postgres-init/`; implementada, firma abajo):

```sql
-- Los pares ciudad+rubro que tienen comercios, y si alcanzan para indexarse.
-- Devuelve un booleano y no el conteo: el número no sale al público (regla de producto).
create or replace function city_category_pages()
returns table (
  city_slug text, city_name text, region text,        -- region = ciudades.departamento
  category_slug text, category_name text,
  indexable boolean,                                  -- count(distinct comercio) >= 5
  last_modified timestamptz                           -- max(comercios.updated_at) del par
)
language sql stable security invoker set search_path = public
as $$
  -- comercios activos y no suspendidos (mismo filtro que buscar_comercios, 0143)
  -- rubro por comercio_rubros (incluye el principal, 0113); rubros.activo; slug <> 'otros'
  -- ciudades.activa
  -- having count(distinct c.id) >= 1
$$;
comment on function city_category_pages() is '…';
grant execute on function city_category_pages() to anon, authenticated, service_role;
notify pgrst, 'reload schema';
```

- `security invoker`: corre con RLS de anon (`comercios_public_read using (activo)`,
  `pattern-supabase-rls-policy`). GRANT explícito
  (`lesson-supabase-cloud-grants-explicitos-en-migration`).
- No toca columnas de `comercios`: no afecta `test_comercios_columnas_publicas.py`.
- Test nuevo `backend/tests/test_city_category_pages_sql.py`: la migración tiene
  `security invoker`, `grant execute … to anon` y no devuelve ninguna columna llamada
  `count`/`n`/`total`.

### 3.3 Rutas nuevas

**`app/[city]/page.tsx`** — `/bermejo`, `/la-paz`, …

- `revalidate = 3600`, `dynamicParams = true`, `generateStaticParams = () => []` (sin
  base en el build: el deploy ya se cayó una vez por depender de red al compilar,
  `app/layout.tsx:26-28`).
- Lee `getCiudades()` y `getCityCategoryPages()`; 404 según 3.1.
- Contenido (server): h1 «Comercios de {Ciudad}, {Departamento}»; la frase canónica (3.10)
  adaptada a la ciudad; lista de rubros con comercios (enlaces a `/{city}/{category}`,
  sólo nombres); enlaces a guía (si `guia_activa`), cambio (si `es_frontera`), farmacias de
  turno, ofertas y novedades.
- Metadata: título «Comercios de {Ciudad} ({Departamento}): qué venden y dónde quedan»
  (la plantilla agrega « · Uruku»), canonical `https://uruku.bo/{city}`, `robots` por 3.1.
- JSON-LD: `BreadcrumbList` + `CollectionPage` con `ItemList` de las URLs de rubro
  indexables.
- Marco con `fixedCity`.
- P2: esta misma URL pasa a ser la home de la ciudad (pendiente grande del handoff), sin
  redirecciones.

**`app/[city]/[category]/page.tsx`** — `/bermejo/ropa`, `/tarija/farmacia`, …

- Mismo régimen ISR. 404/noindex por 3.1 con `city_category_pages()`.
- Lista: `buscarComercios({ ciudad, rubro }, 500, 0)` (RPC con columnas explícitas: cumple
  la regla 11, nunca `select("*")`) + una consulta `comercios.select("id, calle,
  horario_estimado").in("id", ids)` (columnas de `COLUMNAS_COMERCIO`).
- Contenido answer-first, armado sólo con datos:
  - h1 «{Rubro} en {Ciudad}».
  - Primer párrafo: «En {Ciudad}, los locales de {rubro} están sobre {calle1}, {calle2} y
    {calle3}. Entre lo que venden: {6 productos más repetidos}. Tocá cada uno para ver
    dónde queda y cómo llegar.» Cada frase aparece sólo si hay dato (calles con ≥ 3
    locales; productos de `prod_obs_human`/`prod_det_ia`).
  - Lista `<ul>`: nombre (enlace a la ficha) · subcategoría · calle/dirección · «vende: …»
    (5) · «Tiene WhatsApp» si tiene. Miniatura en los primeros 24.
  - Al pie: otros rubros de la ciudad; el mismo rubro en otras ciudades (sólo indexables).
- Metadata: título «{Rubro} en {Ciudad}: dónde quedan y qué vende cada local»;
  descripción con los productos más repetidos; canonical; `robots` por 3.1.
- JSON-LD: `BreadcrumbList` + `ItemList` (`ListItem` con `position`, `url`, `name`; tope
  100; sin `numberOfItems`).

**Conflictos de rutas:** las rutas estáticas de Next ganan a `[city]`. Hay que **borrar
`app/bermejo/page.tsx`** (redirect viejo de la herramienta de campo, hoy `/publicar`) y
sacar `"/bermejo"` de `PERMITIDAS` en `frontend/middleware.ts:5`. En el `matcher`
(`middleware.ts:22`) excluir también `sitemap.xml`, `llms.txt` y `*.txt` (clave IndexNow).

### 3.4 Acceso de robots: matriz y `robots.ts`

Verificado con `curl -A` el 2/11 contra `/`, una ficha y `/sitemap.xml` (las tres dieron
el mismo código).

| Agente | Producto que alimenta | Tipo | robots.txt hoy | HTTP hoy | Recomendado |
|---|---|---|---|---|---|
| OAI-SearchBot | ChatGPT search | búsqueda | permitido (`*`) | 200 | Allow explícito |
| GPTBot | Entrenamiento de modelos OpenAI | entrenamiento | Disallow (CF) | **403** | Allow (D-2) |
| ChatGPT-User | Visita pedida por un usuario de ChatGPT | usuario | `*` | 200 | Allow |
| Googlebot | Google Search, AI Overviews, AI Mode | búsqueda | `*` | 200 | Allow |
| Google-Extended (token, sin UA propio) | Entrenamiento de Gemini **y grounding en la app Gemini / Vertex**; no afecta Search | control | Disallow (CF) | n/a | **Allow** (D-2) |
| GoogleOther / Google-CloudVertexBot | I+D de Google / agentes de Vertex pedidos por dueños de sitios | genérico | Disallow (CF) | 200 | Sin regla propia (cae en `*`) |
| bingbot | Bing, Copilot y (probable) ChatGPT search | búsqueda | `*` | 200 | Allow |
| ClaudeBot | Entrenamiento de Anthropic | entrenamiento | Disallow (CF) | **403** | Allow (D-2) |
| Claude-SearchBot | Búsqueda de Claude | búsqueda | `*` | 200 | Allow |
| Claude-User | Visita pedida por un usuario de Claude | usuario | `*` | 200 | Allow |
| PerplexityBot | Índice y respuestas de Perplexity (no entrena) | búsqueda | `*` | 200 | Allow |
| Perplexity-User | Visita pedida por un usuario | usuario | `*` | 200 | Allow |
| Applebot | Siri, Spotlight, Safari | búsqueda | `*` | 200 | Allow |
| Applebot-Extended (token) | Entrenamiento de Apple Intelligence | control | Disallow (CF) | n/a | Allow (D-2) |
| meta-externalagent | Meta AI (WhatsApp, Instagram, Facebook): indexación y entrenamiento | entrenamiento/índice | **Disallow (CF)** | 200 | **Allow** (D-2) — Meta AI vive adentro de WhatsApp |
| meta-externalfetcher | Meta AI pidiendo una página por un usuario | usuario | `*` | 200 | Allow |
| facebookexternalhit / WhatsApp | Vista previa de enlaces | preview | `*` | 200 | Allow (no tocar) |
| Amazonbot | Alexa / Rufus, entrenamiento | mixto | Disallow (CF) | **403** | Allow (prioridad baja) |
| DuckAssistBot | Respuestas con IA de DuckDuckGo | búsqueda | `*` | 200 | Allow |
| MistralAI-User | Le Chat pidiendo una página | usuario | `*` | 200 | Allow |
| CCBot | Common Crawl: dataset abierto con el que entrenan muchos modelos | entrenamiento | Disallow (CF) | **403** | Allow (D-2; es el de más reuso por terceros) |
| Bytespider | ByteDance (Doubao) | entrenamiento | Disallow (CF) | 403 | **Mantener bloqueado** (rastreo agresivo, sin valor en BO/AR) |
| Diffbot, omgili, SemrushBot-SWA y resto de la lista de CF | scrapers / SEO | — | Disallow (CF) | — | Mantener bloqueados |

`robots.ts` en prod (QA sigue igual: `Disallow: /` + `X-Robots-Tag`,
`next.config.mjs:42-58`):

```text
rules:
  1) userAgent: [OAI-SearchBot, GPTBot, ChatGPT-User, Googlebot, Google-Extended, Bingbot,
                 ClaudeBot, Claude-SearchBot, Claude-User, PerplexityBot, Perplexity-User,
                 Applebot, Applebot-Extended, meta-externalagent, meta-externalfetcher,
                 Amazonbot, DuckAssistBot, CCBot, MistralAI-User]
     allow: /     disallow: PRIVATE_PATHS
  2) userAgent: [Bytespider, Diffbot, omgili, SemrushBot-SWA, …]   disallow: /
  3) userAgent: *   allow: /   disallow: PRIVATE_PATHS
PRIVATE_PATHS = /admin, /contenido, /publicar, /campo, /mi-comercio, /volante/
sitemap: https://uruku.bo/sitemap.xml
```

Ojo: un robot que coincide con un grupo con nombre **ignora** el grupo `*`; por eso cada
grupo repite `PRIVATE_PATHS`. Y **cambiar `robots.ts` no alcanza**: si Cloudflare sigue
anteponiendo su bloque, GPTBot queda con `Disallow: /` y `Allow: /` del mismo largo, y el
WAF lo sigue cortando con 403. Va junto con la tarea del dueño O-2.

### 3.5 Ficha del comercio

Cambios en `app/comercios/[slug]/page.tsx`:

1. **ISR**: fuera `force-dynamic` (`:27`), `revalidate = 300`, `generateStaticParams = []`.
   El marco recibe `fixedCity` (la ciudad del comercio) y **no llama a `cookies()`**. El
   sello de turno de farmacia pasa a un componente cliente (`components/pharmacy-duty-badge.tsx`)
   que recibe los turnos y decide «ahora» en el navegador. `HorarioBadge` ya es cliente.
2. **Encabezado con la ciudad del comercio** (sale de 1).
3. **Título**: `{nombre} — {qué} en {Ciudad}` (sin sufijo: lo pone la plantilla).
   `qué = subcategoria || rubro_nombre` si el rubro no es `otros`; se omite si el nombre ya
   lo contiene. Nunca «Otros (a clasificar)».
4. **Descripción**: `descripcion` (cortada en palabra, ≤ 155) + « En {calle}, {Ciudad}.»;
   si no hay, «{Nombre} en {Ciudad}: vende {productos}.»; si no hay nada, «{Nombre},
   {qué} en {Ciudad} ({Departamento}). Ubicación en el mapa y cómo llegar.». «WhatsApp»
   sólo si tiene.
5. **Texto visible nuevo (server)**:
   - Migas: `URUKU › {Ciudad} › {Rubro} › {Nombre}` (enlaces a `/{city}` y
     `/{city}/{category}` sólo si el par existe).
   - Línea bajo el h1: «{qué} en {Ciudad}, {Departamento}».
   - Sección **`<h2>Qué podés encontrar acá</h2>`** reemplaza las fichas sin título:
     `prod_obs_human` primero, después `prod_det_ia`, sin repetidos (sin tildes ni
     mayúsculas), tope 20. Sin datos, la sección no está.
   - «Dónde queda»: `{calle o dirección}, {Ciudad}`.
6. **`robots`**: `noindex, follow` si `!isBusinessIndexable(c)`.
7. **JSON-LD**: `LocalBusiness` (3.6) + `BreadcrumbList`.
8. P1: `opengraph-image.tsx` 1200×630 (portada + nombre + rubro + ciudad, < 300 kB) con
   `next/og` (viene con Next, sin dependencia nueva); `og:image:alt`.
9. P1: bloque «Más {rubro} en {Ciudad}» (enlace a la página del rubro + hasta 6 fichas
   del mismo par).

### 3.6 JSON-LD

Componente `components/json-ld.tsx` (server): serializa con
`JSON.stringify(data).replace(/</g, "\\u003c")`. **Obligatorio**: los nombres los cargan
agentes y la IA; sin el escape, un nombre con `</script>` inyecta HTML.

Reglas comunes: sólo datos reales y visibles en la página (Google pide que coincidan con
el texto); nunca `aggregateRating`, `review`, `rating`, `priceRange`, ni horario estimado;
URLs absolutas `https://uruku.bo/…`.

**Home (`/`)** — `Organization` + `WebSite`:

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://uruku.bo/#organization",
      "name": "URUKU",
      "alternateName": ["Uruku", "uruku.bo"],
      "url": "https://uruku.bo/",
      "logo": { "@type": "ImageObject", "url": "https://uruku.bo/logouruku.png" },
      "description": "<ONE_LINER de 3.10>",
      "slogan": "Antes de cruzar, Uruku.",
      "areaServed": [{ "@type": "City", "name": "Bermejo",
                       "containedInPlace": { "@type": "AdministrativeArea", "name": "Tarija, Bolivia" } }],
      "contactPoint": { "@type": "ContactPoint", "telephone": "+59167671888",
                        "contactType": "customer support", "availableLanguage": "es" },
      "email": "info@uruku.bo",
      "sameAs": ["https://www.facebook.com/uruku.bo/", "https://www.tiktok.com/@uruku.bo",
                 "https://www.youtube.com/@<handle-nuevo>"]
    },
    {
      "@type": "WebSite",
      "@id": "https://uruku.bo/#website",
      "url": "https://uruku.bo/", "name": "URUKU", "inLanguage": "es",
      "publisher": { "@id": "https://uruku.bo/#organization" },
      "potentialAction": { "@type": "SearchAction",
        "target": { "@type": "EntryPoint", "urlTemplate": "https://uruku.bo/buscar?q={search_term_string}" },
        "query-input": "required name=search_term_string" }
    }
  ]
}
```

- `areaServed`: ciudades con al menos un par indexable (no Cochabamba mientras esté vacía).
- `sameAs`: `getRedes()` normalizado (los handles `@uruku.bo` a URL; `enlaceRed` en
  `lib/catalogo.ts:89` no conoce YouTube: sumarlo) **+** `ENTITY_PROFILES` en
  `lib/marca.ts` (Wikidata, Google Business, Bing Places, Apple: vacío hasta que existan).
  Instagram afuera mientras el perfil diga «no disponible».
- `SearchAction`: Google retiró la caja de búsqueda en resultados (2024); se deja porque
  no cuesta nada y otros lo leen. `/buscar?q=` ya funciona (`components/buscar-client.tsx:264`).
- `slogan`: el tagline de frontera sólo si el dueño lo aprueba como slogan de la marca
  entera (hoy cambia por ciudad, `lib/marca.ts:32`); si no, omitirlo.

**Ficha** — tipo según el rubro principal (`RUBRO_SCHEMA_TYPE` en `lib/seo.ts`; sin
mapeo o `otros` → `LocalBusiness`):

| Rubro | @type | Rubro | @type |
|---|---|---|---|
| ropa, lenceria, ropa-americana | ClothingStore | farmacia | Pharmacy |
| calzado, calzado-usado | ShoeStore | optica | Optician |
| joyeria | JewelryStore | peluqueria | HairSalon |
| celulares | MobilePhoneStore | belleza | HealthAndBeautyBusiness |
| computacion | ComputerStore | gimnasios | ExerciseGym |
| electronica, electrodomesticos | ElectronicsStore | restaurantes | Restaurant |
| bazar, hogar, blanqueria | HomeGoodsStore | comida-rapida | FastFoodRestaurant |
| muebles | FurnitureStore | cafeteria | CafeOrCoffeeShop |
| ferreteria | HardwareStore | panaderia | Bakery |
| repuestos-autos | AutoPartsStore | hospedaje | LodgingBusiness |
| neumaticos | TireShop | nocturna | NightClub |
| motos | MotorcycleDealer | taller-mecanico, gomeria-servicio | AutoRepair |
| bicicletas | BikeStore | estacion-servicio | GasStation |
| alimentos | GroceryStore | cambio | FinancialService |
| kiosco | ConvenienceStore | cajeros | AutomatedTeller |
| mascotas | PetStore | cerrajeria | Locksmith |
| jugueteria | ToyStore | carpinteria, herreria | HomeAndConstructionBusiness |
| deportes | SportingGoodsStore | emergencias | EmergencyService |
| floreria | Florist | banos | PublicToilet |
| bolsos, marroquineria, bebidas, bebes, regaleria, usados, agro, coca, limpieza, telas, carniceria | Store | estacionamiento | ParkingFacility |
| lavadero (auto o ropa: ambiguo), salones (ambiguo), envios, taxis, wifi, alquiler, servicio-tecnico, funeraria, otros | LocalBusiness | | |

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "HomeGoodsStore",
      "@id": "https://uruku.bo/comercios/galeria-cortez#business",
      "name": "Galería cortez",
      "url": "https://uruku.bo/comercios/galeria-cortez",
      "image": ["https://api.uruku.bo/fotos/galeria-cortez/<archivo>.jpg"],
      "description": "Comercio dedicado a la venta de blanquería y textiles para el hogar…",
      "keywords": "frazada, almohada, cobertor, acolchado, toalla, alfombra",
      "address": { "@type": "PostalAddress", "streetAddress": "Avenida Petrolera",
                   "addressLocality": "Bermejo", "addressRegion": "Tarija", "addressCountry": "BO" },
      "geo": { "@type": "GeoCoordinates", "latitude": -22.7361, "longitude": -64.3433 }
    },
    { "@type": "BreadcrumbList", "itemListElement": [
      { "@type": "ListItem", "position": 1, "name": "URUKU", "item": "https://uruku.bo/" },
      { "@type": "ListItem", "position": 2, "name": "Bermejo", "item": "https://uruku.bo/bermejo" },
      { "@type": "ListItem", "position": 3, "name": "Blanquería", "item": "https://uruku.bo/bermejo/blanqueria" },
      { "@type": "ListItem", "position": 4, "name": "Galería cortez" } ] }
  ]
}
```

Campos condicionales (sólo si hay dato): `telephone` (`+{whatsapp}` o `telefono`),
`openingHoursSpecification` (sólo `horario_estimado = false` y si el parser entiende todo
el texto: exportar `parseOpeningHours()` desde `lib/horario.ts:44-81`, mismo parser que
`abiertoAhora`), `sameAs` (redes del comercio vía `enlaceRed`), `paymentAccepted`
(`monedas_aceptadas`). Prohibidos: `rating` (columna pública con default 0), estrella del
plan, «Responde».

**Otras páginas:** `BreadcrumbList` en todas las nuevas; `ItemList` en ciudad/rubro;
`FAQPage` en `/guia`, `/comprar-en-bermejo` y `/que-es-uruku` con las reglas de 3.8;
`AboutPage` (con el mismo nodo `Organization`) en `/que-es-uruku`; P2 `NewsArticle` en
`/novedades/uruku/[id]` y `makesOffer` con las publicaciones que tienen precio.

### 3.7 Sitemap

`app/sitemap.ts`:

- `lastModified` = `updated_at` (fichas) y `last_modified` de `city_category_pages()`
  (pares).
- Fichas: sólo `isBusinessIndexable` (pide `slug, updated_at, rubro_id, subcategoria,
  descripcion, prod_obs_human, prod_det_ia, nombre, suspendido`; todas en
  `COLUMNAS_COMERCIO`).
- Suma: `/{city}` y `/{city}/{category}` indexables, `/novedades/uruku/{id}`, `/agentes`,
  `/que-es-uruku`, `/comprar-en-bermejo` (cuando exista).
- Saca: `/buscar`, `/buscar?vista=mapa`.
- `/buscar` pasa a `robots: { index: false, follow: true }` (y con parámetros también).
- P2: partir por ciudad cuando haya Search Console para ver cobertura por ciudad.

### 3.8 Contenido que contesta («answer-first»)

Regla: **cada pregunta tiene una sola página dueña**; las demás enlazan. La primera frase
bajo cada h2/h3-pregunta es la respuesta directa (≤ 50 palabras); el detalle va después.
Cada bloque con dato cambiante muestra la fecha («Actualizado el 25/10»).

| Pregunta | Página dueña | Fuente del dato |
|---|---|---|
| ¿Dónde comprar {producto} en Bermejo? | `/bermejo/{rubro}` (y `/buscar?q=`) | comercios |
| ¿Qué conviene comprar en Bermejo? ¿Cómo pago? ¿Me lo mandan a Orán/Salta/Jujuy? | `/comprar-en-bermejo` | saber local `compras`, `pagos` |
| ¿Cómo cruzo de Aguas Blancas a Bermejo? ¿Horario del puente / chalanas? ¿Documentos? ¿Franquicia? | `/guia` (`#frontera`, `#documentos`, `#aduana`) | saber local `frontera` + `frontera_estado` con fecha |
| ¿Cuánto me dan por mis pesos hoy en Bermejo? | `/cambio` | `cotizaciones` con fecha |
| ¿Qué farmacia está de turno hoy en Bermejo? | `/farmacias-de-turno` (P1: `/{city}/farmacias-de-turno`) | `turnos_farmacia` |
| ¿Qué es URUKU? ¿Es confiable? ¿Cobran los agentes? | `/que-es-uruku` (+ `/agentes`) | texto del dueño + saber local `uruku` |

- **FAQPage sólo donde la página ES preguntas y respuestas visibles** (los `<details>` de
  `/guia`, `app/guia/page.tsx:56`, cuentan: el texto está en el HTML). Cada pregunta se
  marca en **una** página: `/guia` = secciones que no son `comercios`/`general`;
  `/comprar-en-bermejo` = sección `comercios`; `/que-es-uruku` = `general` (las de URUKU).
  Google dejó de mostrar el resultado enriquecido de FAQ para la mayoría de los sitios
  (2023); se marca igual porque es barato y ordena la lectura, no por el resultado.
- **Sólo saber verificado.** El JSON tiene 37 de 75 entradas sin verificar (17 de
  frontera). Lo no verificado no se publica (es lo que ya hace el cargador,
  `backend/app/scripts/cargar_saber_local.py:14`).
- **Frescura**: `/cambio` y `/comprar-en-bermejo` dicen «hoy» en el título sólo si
  `cotizaciones.actualizado_en` < 36 h; si no, «Cotización del peso en Bermejo» y la
  fecha visible. Igual con el estado del paso.

**`/comprar-en-bermejo`** (P1, `app/comprar-en-bermejo/page.tsx`, ISR 3600, marco con
`fixedCity = bermejo`). Para quien viene de Aguas Blancas, Orán, Salta, Jujuy o Tucumán.
Secciones, cada una una pregunta:

1. ¿Qué conviene comprar en Bermejo? → respuesta + enlaces a `/bermejo/{rubro}`
   indexables (ropa, calzado, electrónica, electrodomésticos…).
2. ¿Cómo cruzo desde Aguas Blancas? → 2 líneas + estado del paso con fecha → `/guia#frontera`.
3. ¿Qué documentos necesito? → resumen → `/guia#documentos`.
4. ¿Cuánto me dan por mis pesos? → valor ARS con fecha (regla de frescura) → `/cambio`.
5. ¿Cómo pago? (pesos, bolivianos, dólares, QR).
6. ¿Me lo mandan a Orán, Salta o Jujuy?
7. ¿Cuánto puedo pasar sin pagar? → resumen → `/guia#aduana`.
8. Encargos y guardería de URUKU: qué es, sin precios (memoria del proyecto: precios
   después). Texto aprobado por el dueño.
9. Ofertas de hoy en Bermejo (4 del feed).

Metadata: título «Comprar en Bermejo desde Argentina: qué conviene, cómo cruzar y cómo
pagar»; descripción que nombra Aguas Blancas, Orán, Salta y Jujuy; canonical;
`openGraph.locale = "es_BO"`, `alternateLocale = ["es_AR"]`. Enlazada desde la home (en
Bermejo), `/guia`, `/cambio`, `/que-es-uruku` y el pie.

### 3.9 Posicionamiento Bolivia–Argentina

- **Sin hreflang** (D-7).
- El dominio `.bo` le dice a Google «Bolivia»; para aparecer en `google.com.ar` cuenta
  el contenido escrito para el comprador argentino (3.8) y que lo citen sitios argentinos
  (medios de Orán/Salta, O-9).
- ARS: ya está en `/cambio` y en el marco cuando la ciudad es frontera. P2: «≈ $ X» en
  pesos al lado de los precios en Bs en `/comprar-en-bermejo` y ofertas de Bermejo, sólo
  si la cotización tiene < 36 h.
- Vocabulario: nombrar lugares concretos (Aguas Blancas, Orán, Salta, Jujuy, Tucumán) en
  texto visible; no repetirlos en listas para «rellenar» (es spam).

### 3.10 Entidad y marca

**Frase canónica** (para aprobar, O-5). Se usa idéntica en todos lados:

- **Nombre:** URUKU (en texto y datos estructurados; «Uruku» queda como `alternateName` y
  en la plantilla de títulos, que sigue el manual).
- **Descriptor (≤ 60):** «Guía de comercios de Bermejo y Bolivia»
- **Una línea (≤ 160):** «URUKU es la guía de comercios de Bermejo y Bolivia: qué vende
  cada local, dónde queda y cómo llegar, con ofertas y el cambio del día.»
- **Variante para Argentina:** «…y lo que necesitás saber para cruzar a comprar desde
  Aguas Blancas.»

Dónde va: `Organization.description`, meta description de la home sin ciudad
(`lib/marca.ts:58-63`, hoy «Los comercios de tu ciudad…»), primer párrafo de
`/que-es-uruku`, `llms.txt`, bios de Facebook, TikTok, YouTube, Instagram, perfil de
WhatsApp Business del 67 671 888, Google Business, Bing Places, Apple Business Connect,
Wikidata.

**NAP** (mismo en todos lados): URUKU · +591 67671888 · https://uruku.bo · info@uruku.bo ·
Bermejo, Tarija, Bolivia (dirección postal sólo si es real).

**`/que-es-uruku` como Acerca de / Prensa** (P0 código, texto del dueño): indexable,
título «Qué es URUKU — guía de comercios de Bermejo y Bolivia», `AboutPage` +
`Organization` + `FAQPage` (sección `general`). Hechos citables, sin cifras de comercios:
qué es (la frase canónica), quién lo hace (persona o razón social: **dato del dueño**,
hoy no está en el repo), desde cuándo (lanzamiento 28/9/2026), en qué ciudades, cómo
funciona (agentes que recorren, comercios que publican por WhatsApp, moderación), qué
**no** hace (no vende ni media pagos entre comprador y comercio; los agentes nunca
cobran → `/agentes`), contacto, enlaces a redes y a un kit de prensa (logo +
`og-image.png`). El `.md` hoy es sólo Bermejo (`content/manuales/uruku.md:3`): reescribirlo
multi-ciudad.

**`llms.txt`** (P1, `app/llms.txt/route.ts`, `text/plain`, revalidate 86400). Valor
incierto: ningún asistente grande confirmó que lo lea; cuesta una tarde. Contenido:

```markdown
# URUKU
> URUKU es la guía de comercios de Bermejo y Bolivia: qué vende cada local, dónde queda y cómo llegar, con ofertas y el cambio del día.

Ciudades: Bermejo (Tarija), La Paz, Tarija, Santa Cruz.   <- sólo las que tienen páginas indexables
Contacto: WhatsApp +591 67671888 · info@uruku.bo

## Páginas clave
- [Qué es URUKU](https://uruku.bo/que-es-uruku): quién lo hace, cómo funciona, contacto
- [Comprar en Bermejo desde Argentina](https://uruku.bo/comprar-en-bermejo)
- [Guía para venir a Bermejo](https://uruku.bo/guia): paso fronterizo, documentos, aduana
- [Cotización del peso y el dólar en Bermejo](https://uruku.bo/cambio)
- [Farmacias de turno](https://uruku.bo/farmacias-de-turno)
- [Comercios de Bermejo](https://uruku.bo/bermejo)

## Rubros por ciudad
- [Ropa en Bermejo](https://uruku.bo/bermejo/ropa)   <- generado: pares indexables

## Lo que URUKU no hace
- No vende ni cobra por los comercios ni media pagos. Los agentes de URUKU nunca cobran.
```

### 3.11 Medición

**En el sitio (backend, P1):**

- `backend/app/core/ai_sources.py`: `AI_SOURCES = { "chatgpt": ["chatgpt.com",
  "chat.openai.com"], "perplexity": ["perplexity.ai"], "gemini": ["gemini.google.com",
  "bard.google.com"], "copilot": ["copilot.microsoft.com", "copilot.com"], "claude":
  ["claude.ai"], "meta_ai": ["meta.ai"], "deepseek": ["chat.deepseek.com"], "grok":
  ["grok.com"], "mistral": ["chat.mistral.ai"] }` y `classify_ai_source(origen, referido)`
  (sufijo de host; `origen` primero).
- `resumen_visitas` (`repository.py:3954`) suma `ai_sources: [{source, visits, people,
  business_views, top_routes[3]}]` sobre las mismas filas que ya trae (sin consultas
  nuevas). `business_views` = rutas `/comercios/…`.
- `components/vista-logger.tsx:13`: `ref ?? utm_source`.
- `components/panel-visitas.tsx`: bloque «Desde asistentes de IA» (es el panel del admin:
  ahí sí van números).
- Límites que el panel tiene que decir en una línea: AI Overviews y AI Mode llegan como
  `google.com` (indistinguibles de Google normal); ChatGPT a veces no manda UTM ni
  referrer y cae como «directo».

**Panel de preguntas mensual (dueño, ~1 h).** Primer lunes de cada mes, en ventana
privada, sin sesión. ChatGPT (con búsqueda), Gemini, Meta AI (en WhatsApp) y Perplexity
todos los meses; Copilot, Claude y Google (AI Overview/AI Mode) cada tres meses. **Correr
la primera vez antes de desplegar nada** (línea de base). Planilla con columnas: `fecha ·
asistente · pregunta# · resultado (ausente / mencionado / primera opción) · URL citada ·
otros sitios citados · nota`.

1. ¿Hay una guía de comercios de Bermejo, Bolivia?
2. ¿Dónde compro zapatillas en Bermejo?
3. ¿Qué conviene comprar en Bermejo?
4. ¿Cómo cruzo de Aguas Blancas a Bermejo?
5. ¿Qué documentos necesito para cruzar a Bermejo desde Argentina?
6. ¿Cuánto está el peso argentino en Bermejo hoy?
7. ¿Qué farmacia está de turno hoy en Bermejo?
8. ¿A qué hora abre el paso fronterizo Aguas Blancas–Bermejo?
9. ¿Dónde compro electrodomésticos en Bermejo?
10. ¿Dónde cambio pesos por bolivianos en Bermejo?
11. ¿Hay comercios de Bermejo que manden mercadería a Orán o Salta?
12. ¿Cuánto puedo pasar por la aduana volviendo de Bermejo?
13. ¿Qué es URUKU? (y «uruku.bo»)
14. ¿URUKU es confiable? ¿Los agentes de URUKU cobran?
15. ¿Dónde compro ropa al por mayor en Bermejo?
16. ¿Dónde hay cajeros en Bermejo?
17. Vivo en Salta: ¿me conviene ir a comprar a Bermejo?
18. ¿Qué farmacias hay en Tarija? (expansión)
19. ¿Dónde hay ópticas en La Paz? (expansión)
20. ¿Qué app o página uso para encontrar comercios en Bolivia?

### 3.12 IndexNow (backend, P1)

- Clave: 32 hex al azar (`python -c "import secrets;print(secrets.token_hex(16))"`); es
  pública por diseño del protocolo, pero **no se commitea**. Backend (`backend/.env`):
  `INDEXNOW_KEY=<clave>` y `APP_ENV=prod`; el sitio sale de `SITIO_URL` (ya existe,
  default `https://uruku.bo`). Sólo corre con `APP_ENV=prod` **y** clave válida; sin una
  de las dos el loop no arranca (log `indexnow_apagado`).
- **Cómo se sirve la clave** (`https://uruku.bo/<clave>.txt`, contenido = la clave, sin
  salto de línea): archivo creado **en el deploy**, antes del build del frontend, en el
  VPS de prod: `printf %s "$INDEXNOW_KEY" > frontend/public/$INDEXNOW_KEY.txt`
  (Next sirve `public/` tal cual; el `Dockerfile` ya copia `public/`). Agregar a
  `.gitignore` el patrón `frontend/public/????????????????????????????????.txt`. Requisito
  del frontend: `middleware.ts` no debe interceptar `*.txt` (FB1 ya lo excluye del
  `matcher`; hasta entonces, en modo captura `/<clave>.txt` caería en «Próximamente»).
  Verificar: `curl https://uruku.bo/<clave>.txt` devuelve la clave.
- `backend/app/services/indexnow.py`: `submit(urls)` → `POST https://api.indexnow.org/indexnow`
  `{host, key, keyLocation, urlList}` (≤ 10.000) con `httpx` (ya es dependencia,
  `pyproject.toml:12`); structlog `indexnow_submitted` / `indexnow_failed`; nunca lanza
  (`pattern-fire-and-forget-tracking`).
- `_indexnow_loop` en `app/main.py` (cada 15 min): fichas con `updated_at` o una
  publicación aprobada desde la última corrida (cursor en memoria; al arrancar, ahora −
  1 h: repetir es inocuo). Una vez por día suma `/`, `/cambio`, `/farmacias-de-turno`.
- 200 = recibido, no indexado. Alcanza a Bing (y Yandex, Naver, Seznam, Yep); **Google
  no participa**.

---

## 4. Tareas

Orden: **Paso 0** (fundaciones) y **M1** en paralelo → después FA, FB1, FB2, B1, B2 en
paralelo (archivos distintos). Ningún archivo lo tocan dos tareas.

### P0

| ID | Capa | Qué | Archivos | Criterio de terminado | Esfuerzo |
|---|---|---|---|---|---|
| F0 | frontend | Fundaciones: reglas de indexación, mapa rubro→schema, armadores de JSON-LD, componente con escape, marco sin cookie, parser de horario exportado, lectores de datos | nuevos `lib/seo.ts`, `components/json-ld.tsx`; `components/uruku-shell.tsx` (prop `fixedCity`; con ella no llama a `ciudadActual()`), `lib/horario.ts` (exportar `parseOpeningHours`, `abiertoAhora` igual), `lib/data.ts` (`getCityCategoryPages()` → `[]` si la RPC falla; `getBusinessesForSitemap()`), `lib/catalogo.ts` (YouTube en `enlaceRed`), `lib/marca.ts` (`ONE_LINER`, `ENTITY_PROFILES`) | Tests unitarios: `isBusinessThin` con los 4 casos de 3.1; todo `@type` del mapa está en una lista blanca de tipos de schema.org; nombre `</script><b>` sale escapado; `parseOpeningHours("Lun-Sáb 8:00-12:00 y 14:30-20:00")` da 6 días × 2 rangos y `abiertoAhora` no cambia sus tests | M |
| M1 | migración | `city_category_pages()` | `supabase/migrations/0180_city_category_pages.sql` (+ espejo en `selfhost/postgres-init/`), `backend/tests/test_city_category_pages_sql.py` | `curl -X POST https://db.uruku.bo/rpc/city_category_pages` con anon devuelve pares de las 5 ciudades activas, sin `otros`, sin ninguna columna de conteo; test verde | S |
| FA | frontend | Ficha: ISR, ciudad correcta, texto visible, título/descr., noindex de vacías, LocalBusiness + BreadcrumbList, sello de turno en cliente | `app/comercios/[slug]/page.tsx`, nuevo `components/pharmacy-duty-badge.tsx` | `next build` lista `/comercios/[slug]` como ISR (no λ); respuesta con `s-maxage`; `curl` a una ficha de La Paz: el HTML dice «La Paz» y no «Bermejo», trae `<h2>Qué podés encontrar acá` (si hay datos), las migas y 1 `application/ld+json` válido en validator.schema.org y Rich Results Test; ficha «Otros (a clasificar)» → `noindex`; título sin «URUKU · Uruku» | M |
| FB1 | frontend | Rutas por ciudad y ciudad+rubro | nuevos `app/[city]/page.tsx`, `app/[city]/[category]/page.tsx`; borrar `app/bermejo/page.tsx`; `middleware.ts` (fuera `/bermejo` de `PERMITIDAS`, `matcher` excluye `sitemap.xml|llms.txt|*.txt`) | `/bermejo` 200 con lista de rubros; `/bermejo/ropa` 200 indexable con lista server-side de fichas; `/cochabamba` 200 `noindex`; `/yacuiba` y `/bermejo/otros` 404; `grep -E "[0-9]+ (comercios|locales|negocios)"` sobre el HTML = 0; segunda carga servida de caché | M |
| FB2 | frontend | robots por robot, sitemap, `/buscar` noindex, JSON-LD de la home, canonical y títulos | `app/robots.ts`, `app/sitemap.ts`, `app/buscar/page.tsx` (metadata), `app/page.tsx` (JSON-LD + canonical + bloque «Ciudades» con enlaces a `/{city}` indexables), `app/guia/page.tsx`, `app/ofertas/page.tsx`, `app/novedades/page.tsx`, `app/cambio/page.tsx` (título «hoy» con frescura), `app/comunidad/page.tsx`, `app/agentes/page.tsx`, `app/novedades/uruku/[id]/page.tsx` | `robots.txt` (con O-2 hecho) tiene los 3 grupos de 3.4; sitemap sin `/buscar`, con pares y `lastmod` = `updated_at`, sin fichas vacías; canonical en todas las indexables (en `/ofertas` y `/novedades`, sin query salvo `rubro`); ningún `<title>` con la marca dos veces | M |
| FC | frontend | `/que-es-uruku` indexable como Acerca de / Prensa | `app/que-es-uruku/page.tsx`, `content/manuales/uruku.md` (texto del dueño) | `index, follow`; `AboutPage` + `Organization`; el texto nombra todas las ciudades activas y dice quién lo hace; en el sitemap | S (+ texto) |

### P1

| ID | Capa | Qué | Archivos | Criterio | Esf. |
|---|---|---|---|---|---|
| B1 | backend | `ai_sources` en el resumen de visitas | nuevo `app/core/ai_sources.py`; `app/db/repository.py` (`resumen_visitas`); `tests/conftest.py` (fake `resumen_visitas`); test nuevo | Visita con `origen=chatgpt.com` y otra con `referido=perplexity.ai` aparecen en `ai_sources` con su fuente; claves existentes intactas | S |
| B2 | backend | IndexNow | nuevo `app/services/indexnow.py`; `app/main.py` (loop); `app/core/config.py` (settings); `frontend/public/{key}.txt` | Con `APP_ENV=prod`, editar una ficha → log `indexnow_submitted` con esa URL en ≤ 15 min; Bing Webmaster muestra URLs recibidas; sin `INDEXNOW_KEY` el loop no arranca | S |
| FD | frontend | Panel y vista de ficha con IA | `components/panel-visitas.tsx`, `components/vista-logger.tsx` | Bloque «Desde asistentes de IA» con la nota de límites; `leads.origen=chatgpt.com` al entrar a una ficha con `?utm_source=chatgpt.com` | S |
| FE | frontend | `/comprar-en-bermejo` | nuevo `app/comprar-en-bermejo/page.tsx` | 3.8 completo; `FAQPage` sólo con preguntas de sección `comercios`; enlazada desde home, guía, cambio, acerca; ninguna pregunta marcada en dos páginas | M |
| FF | frontend | FAQPage en `/guia` y fechas visibles | `app/guia/page.tsx` | `FAQPage` con exactamente las preguntas visibles de las secciones que le tocan; «Revisado el …» por sección | S |
| FG | frontend | `llms.txt` | nuevo `app/llms.txt/route.ts` | `curl https://uruku.bo/llms.txt` → 200 `text/plain`, sólo páginas indexables | S |
| FH | frontend | Imagen de vista previa por ficha | nuevo `app/comercios/[slug]/opengraph-image.tsx` | 1200×630, < 300 kB, nombre + rubro + ciudad; Sharing Debugger de Facebook la toma | M |
| FI | frontend | Enlaces internos: «Más {rubro} en {Ciudad}» en la ficha; «Ciudades» en el pie | `app/comercios/[slug]/page.tsx` (después de FA), `components/uruku-shell.tsx` (después de F0) | Cada ficha indexable enlaza a su página de rubro; el pie enlaza las ciudades indexables | S |
| FJ | frontend | Farmacias de turno por ciudad | nuevo `app/[city]/farmacias-de-turno/page.tsx`; `/farmacias-de-turno` canonical a `/bermejo/farmacias-de-turno` | Sólo ciudades con turnos; el resto 404 | M |

### P2

| ID | Qué | Esf. |
|---|---|---|
| P2-1 | `/{city}` como home de la ciudad (cuerpo de la home con la ciudad de la URL; pendiente grande del handoff) | L |
| P2-2 | Revalidación a pedido: el loop de B2 llama a un `app/api/revalidate/route.ts` con secreto tras cada edición | S |
| P2-3 | `makesOffer` con publicaciones con precio; `NewsArticle` en novedades de URUKU | S |
| P2-4 | «≈ $ X» en pesos junto a precios en Bs (con regla de frescura) | S |
| P2-5 | Sitemap partido por ciudad | S |
| P2-6 | `containedInPlace` del mercado/galería (`lugares`) en el JSON-LD | S |

---

## 5. Tareas del dueño (fuera del código)

| # | Prioridad | Qué | Dónde / cómo |
|---|---|---|---|
| O-1 | P0 | `www.uruku.bo` → **301** a `https://uruku.bo` (con ruta) | Cloudflare › Rules › Redirect Rules |
| O-2 | P0 | Decidir D-2 y aplicarla en Cloudflare: **apagar el robots.txt gestionado** y, en el control de bots de IA, **permitir** los de la matriz (o al menos Google-Extended, meta-externalagent y todo lo de búsqueda). Mismo día que se despliega FB2 | Cloudflare › AI Crawl Control / Security › Bots (los nombres del panel pueden variar). Verificar con el script de §7 |
| O-3 | P0 | Google Search Console (propiedad de dominio por TXT en Cloudflare) y Bing Webmaster Tools (importar desde GSC); enviar `sitemap.xml` en los dos | search.google.com/search-console · bing.com/webmasters |
| O-4 | P0 | **Correr el panel de preguntas por primera vez** (línea de base) antes del deploy | §3.11 |
| O-5 | P0 | Aprobar la frase canónica (3.10) y pegarla en las bios de Facebook, TikTok, YouTube y el perfil de WhatsApp Business | cada red |
| O-6 | P0 | Instagram: recuperarlo o sacarlo de `/contenido` (handoff 3/10). Cambiar el handle de YouTube `@Uruku-Bermejo` por uno sin ciudad | `/contenido`; YouTube Studio |
| O-7 | P0 | Texto de `/que-es-uruku`: quién lo hace (persona o empresa) y la versión multi-ciudad | `content/manuales/uruku.md` |
| O-8 | P0 | Cotización y estado del paso con fecha de hoy (la última es del 25/10). Si no se puede a diario, aceptar que los títulos dejen de decir «hoy» | `/contenido` |
| O-9 | P1 | **Menciones en medios.** El diario/radio del dueño es un canal directo: nota de presentación de URUKU con la frase canónica y enlace a `uruku.bo`; una nota semanal «estado del paso y cotización» que cite a URUKU con enlace. Sumar medios de Tarija y de Orán/Salta. El medio propio **no cuenta como fuente independiente** para Wikidata; enlaces normales en notas, no en el pie de todo el sitio (Google lo trata como esquema de enlaces) | redacción |
| O-10 | P1 | Google Business Profile de URUKU. **Elegibilidad a verificar**: Google pide atención en persona en una dirección o servicio en el domicilio del cliente; un negocio sólo online no entra. Si la guardería de compras tiene local, ese es el domicilio; si no, área de servicio (agentes). Nunca una dirección inventada | business.google.com |
| O-11 | P1 | Bing Places (importa desde Google Business) y Apple Business Connect (mismas condiciones) | bingplaces.com · businessconnect.apple.com |
| O-12 | P1 | Revisar y verificar las 37 preguntas sin verificar del saber local; cargar con `python -m app.scripts.cargar_saber_local bermejo` | `backend/data/saber_local/bermejo.json` |
| O-13 | P1 | Que los agentes pidan a los comercios poner «Encontranos en URUKU: uruku.bo/comercios/{slug}» en su Facebook/WhatsApp Business | operativo |
| O-14 | P1 | Clasificar comercios «otros» (3.405 hoy): es la palanca que más fichas vuelve indexables | panel / loop de revisión IA |
| O-15 | P2 | Wikidata: crear el ítem **recién cuando haya ≥ 2 notas de medios independientes**; sin eso lo borran por notoriedad. Datos: instancia de «sitio web» / «directorio», país Bolivia, sitio oficial, fecha de inicio, ubicación Bermejo. Nunca ítems de comercios. Wikipedia: no por ahora | wikidata.org |
| O-16 | P2 | Una vez por mes, mirar en Cloudflare los eventos de seguridad: ningún bot verificado de búsqueda bloqueado | Cloudflare › Security › Events |

---

## 6. Riesgos

| # | Riesgo | Mitigación / validación humana |
|---|---|---|
| R-1 | No hay garantía de posición en ningún asistente; las respuestas cambian por persona y por día | Medir con el panel (O-4) y `ai_sources`; comparar contra la línea de base, no contra «primer puesto» |
| R-2 | Permitir robots de entrenamiento (D-2) es irreversible para lo ya rastreado y facilita que terceros (Common Crawl) armen un directorio con los datos de URUKU. `consentimiento_dueno` es NULL en la mayoría (0155) | **Decisión del dueño** (O-2). Mínimo aceptable si dice que no: Google-Extended + meta-externalagent + búsqueda/usuario |
| R-3 | `noindex` de 3.128 fichas vacías: un dueño que busque su local por nombre en Google puede no encontrarlo | La ficha se vuelve indexable sola al clasificarse (O-14); validar el criterio con el dueño |
| R-4 | ISR: lo editado en el panel tarda hasta 5 min en verse | Aceptado; P2-2 si molesta. Turnos de farmacia calculados en el cliente para no mostrar el turno vencido |
| R-5 | Datos viejos con «hoy» (cotización y paso del 25/10): la IA los repite con el nombre de URUKU | Regla de frescura (3.8) + O-8 |
| R-6 | Apagar el robots gestionado de Cloudflare deja de sumar solo los bots nuevos a la lista de bloqueo | Es la intención (los nuevos caen en `*`); el WAF sigue frenando bots maliciosos; O-16 |
| R-7 | `.bo` orienta a Bolivia; en `google.com.ar` cuesta más | Contenido para el comprador argentino (FE) + menciones en medios argentinos (O-9) |
| R-8 | `utm_source=chatgpt.com` y el referrer no siempre llegan (reportes de octubre 2026); AI Overviews no se distingue de Google | Decirlo en el panel; usar Search Console para Google |
| R-9 | Una ciudad futura con slug igual a una ruta fija (`mapa`, `guia`) queda tapada por la ruta | Revisar al dar de alta ciudades; los slugs actuales no chocan |
| R-10 | El JSON-LD sin escape abre XSS con nombres cargados por agentes/IA | Criterio de F0 (test con `</script>`) |
| R-11 | Google Business para URUKU puede no ser elegible | O-10: validar antes; no inventar dirección |
| R-12 | El tagline de frontera como `slogan` de la marca entera contradice `lib/marca.ts` (cambia por ciudad) | El dueño decide; por defecto se omite |

---

## 7. Cómo verificar

```bash
# Matriz de robots (todos 200 salvo Bytespider y scrapers) — después de O-2 + FB2
for ua in OAI-SearchBot GPTBot ChatGPT-User Googlebot bingbot ClaudeBot Claude-SearchBot \
          Claude-User PerplexityBot Perplexity-User Applebot meta-externalagent \
          meta-externalfetcher Amazonbot DuckAssistBot CCBot MistralAI-User Bytespider; do
  printf "%-22s %s\n" "$ua" "$(curl -s -o /dev/null -w '%{http_code}' -A "Mozilla/5.0 (compatible; $ua/1.0)" https://uruku.bo/)"
done
curl -s https://uruku.bo/robots.txt | head -20          # sin el bloque «Cloudflare Managed»
curl -sI https://www.uruku.bo/ | grep -i location        # 301 a https://uruku.bo/

# Ficha: ciudad correcta, texto propio, JSON-LD, caché
curl -s https://uruku.bo/comercios/optica-briangie | grep -c 'application/ld+json'      # 1
curl -s https://uruku.bo/comercios/optica-briangie | grep -o 'La Paz' | head -1
curl -sI https://uruku.bo/comercios/optica-briangie | grep -i cache-control              # s-maxage

# Páginas nuevas y reglas
curl -s -o /dev/null -w '%{http_code}\n' https://uruku.bo/bermejo/ropa                  # 200
curl -s https://uruku.bo/cochabamba | grep -o 'noindex'                                 # noindex
curl -s -o /dev/null -w '%{http_code}\n' https://uruku.bo/bermejo/otros                 # 404
curl -s https://uruku.bo/sitemap.xml | grep -c '/buscar'                                # 0
```

Además: validator.schema.org y Rich Results Test de Google sobre la home, una ficha con
horario no estimado, una ficha sin datos de contacto, `/bermejo/ropa` y `/guia`.
