# Estadísticas v2: brechas con la receta de PortalNoticias y spec de lo que se suma

> 5/11/2026 · Estado: **propuesta, falta el OK del dueño** (§7).
> Entrada: la receta F-007 de PortalNoticias («En Movimiento») y el código de `C:\repos\proyectosClaude\PortalNoticias`.
> KB aplicada: `pattern-fire-and-forget-tracking`, `pattern-supabase-rls-policy`, `lesson-supabase-cloud-grants-explicitos-en-migration`,
> `lesson-supabase-service-role-key-nunca-en-frontend`, `lesson-nunca-delete-fisico-siempre-soft` (excepción «logs con TTL»),
> `lesson-rls-sin-valvula-de-escape-escribible-por-la-app`, `lesson-ssg-isr-en-catalogo-no-ssr-puro`, ADR `2026-06-04-stack-bermejo`.

## 0. En seis líneas

1. URUKU ya mide **más y mejor que la receta en lo que le importa al negocio**: el embudo visita → ficha → contacto, por comercio, con el `?ref=` de los QR, la búsqueda que llevó al contacto, «¿te contestó?», las fuentes de IA y lo que ve el comerciante. Nada de eso existe en PortalNoticias.
2. Donde está **peor** es en la **integridad y la robustez**: cualquiera puede insertar visitas y contactos directo en PostgREST, `/visita`, `/lead` y `/busquedas/log` no tienen límite de pedidos ni filtro de bots, un F5 en la ficha suma otra «persona» para el comerciante y un `tipo` desconocido se cuenta como WhatsApp.
3. Se suma: blindaje (permisos, límites, bots, deduplicación), **un módulo único de medición**, eventos nuevos, orígenes canónicos, resumen por SQL, escritura en lote, retención con piso y **Umami opcional** (apagado salvo que el dueño lo prenda).
4. **No** se suma: GA4 (datos a Google y cartel de cookies sin una necesidad que lo pague), la CSP con nonce (rompe el ISR de las fichas), las tablas de agregados por día y el hash de IP+User-Agent (en Bolivia, el CGNAT de las operadoras junta a mucha gente en una sola IP y el hash se queda corto).
5. CSP **sí**, pero estática y sin nonce, primero en modo «sólo reportar».
6. Costo en plata: cero. Umami: entre 0,3 y 0,55 GB de RAM del VPS, sólo si se prende.

---

## 1. Lo que ya existe (inventario)

| Pieza | Dónde | Qué hace |
|---|---|---|
| Páginas vistas | `visitas` (0130) · `components/contador-visitas.tsx` → `registrarVisita` (`lib/campo.ts`) → `POST /visita` (`api/campo.py`) | Una fila por página: día en hora de Bolivia, ruta, sesión de pestaña (`sessionStorage`), `?ref=`/`utm_source`, host del referido, ciudad, `primera`. Sin IP, sin UA, sin cookies |
| Interacciones por comercio | `leads` (0011, 0114, 0120) · `vista-logger.tsx`, `wa-lead-link.tsx`, `lead-link.tsx`, `map-results.tsx`, `buscar-client.tsx`, `reservas` → `POST /lead` | `vista`, `whatsapp`, `telefono`, `email`, `web`, `mapa` (cómo llegar), `reserva`, con `origen` y `busqueda_id`; «¿te contestó?» |
| Búsquedas | `busquedas`, `busqueda_comercios` (0034, 0055) → `POST /busquedas/log` | Texto, resultados, qué comercios se mostraron |
| Errores y Web Vitals | `lib/observabilidad.ts` → `/errores`, `/metricas` | Observabilidad (con límite de pedidos) |
| Panel | `PanelVisitas` (en Monitoreo), `TabKpis`, `DemandaPanel` · `/admin/visitas`, `/admin/kpis`, `/admin/demanda` | Embudo, días, rutas, referidos, `?ref=`, fuentes de IA, más buscado, sin resultado |
| Comerciante | `/comercio/metricas` → «Mi comercio» (inicio y Estadísticas) + reporte mensual por WhatsApp (`subscriber_messages.py`) | Visitas y contactos 7/30 días, contactos por tipo, palabras con que lo encontraron |
| Interruptores de costo | `cost_switches` (0183) · `services/cost_switches.py` · `/admin/cost-switches` | Lo que cuesta se prende a propósito, con aviso de costo |

---

## 2. Brechas, punto por punto

Veredicto: **Mejor** = URUKU le gana a la receta · **Igual** · **Peor** = hay que arreglarlo · **N/A** = no aplica a URUKU.

| # | Tema (receta) | Receta | URUKU hoy | Veredicto | Qué hacemos |
|---|---|---|---|---|---|
| 1 | Medidores | Umami + GA4 + propios | Sólo propios | — | Propios = fuente de verdad. Umami opcional. GA4 no (§3.4) |
| 2 | Módulo único en el front | `lib/analytics.ts`, ningún componente habla con un proveedor | Cinco puntos de entrada (`contador-visitas`, `vista-logger`, `registrarLead`, `logBusqueda`, `observabilidad`), cada uno con su `fetch` | Peor | `lib/medicion.ts` (§4.3). `observabilidad.ts` queda aparte: es diagnóstico, no medición |
| 3 | Config sin redeploy | `site_settings.analytics` editable, URL del script editable | `cost_switches` ya existe | Mejor base | Interruptor nuevo `umami_stats`. La URL del script **no es editable**: sale de `DOMAIN`. Así desaparece la falla grave de la receta (§5 de ella: script ajeno cargado desde la config) |
| 4 | Consentimiento | Sólo para GA4 | No hay cartel (no hace falta: sin cookies) | Mejor | Se mantiene sin cartel: sin GA4 no hay nada que consentir |
| 5 | CSP | Con nonce, armada en el middleware | No hay CSP | Peor | CSP **estática sin nonce** (§3.5). El nonce obliga a renderizar cada página por pedido y las fichas son `force-static` + `revalidate` (regla 9 de AGENTS.md) |
| 6 | Eventos | radio, avisos, compartir, PWA, búsqueda sin texto | Contactos por comercio (mejor que la receta); faltan compartir, PWA, video, redes del comercio, canal de URUKU | Mejor en contactos, peor en el resto | Catálogo cerrado nuevo (§4.5) |
| 7 | Búsqueda | Nunca guarda el texto | Guarda el texto: es la base de «Demanda» | Mejor para el negocio, con riesgo | Se guarda, pero **enmascarando teléfonos y mails** al entrar |
| 8 | Transporte | `sendBeacon` con `text/plain`, `fetch keepalive` de respaldo | `fetch` con `application/json` (preflight CORS) | Peor | Copiar. El comentario de `observabilidad.ts` («sendBeacon se bloquea») vale sólo para `application/json`, no para `text/plain` |
| 9 | Respuestas | 204 siempre, 413 > 2 KB, 429, nunca 500 | 422 de Pydantic, sin tope de tamaño, `insert_lead` puede dar 500 | Peor | Copiar en `/collect` y `/lead` |
| 10 | Límite por IP | Ventana fija, O(1), tope de claves, IPv6 por /64 | `/visita`, `/lead`, `/busquedas/log` y `/lead/{id}/respondio` **sin límite**. El limitador de `main.py` barre todas las claves cuando pasa de 10.000 | Peor | `WindowRateLimiter` de PortalNoticias para los endpoints de medición, con topes pensados para CGNAT (§4.2) |
| 11 | Bots | Regex corta de UA; UA vacío = bot | Nada en el servidor (los que corren JS cuentan: Googlebot renderiza, Lighthouse, monitores) | Peor | Copiar la regex. No tocar los navegadores dentro de las apps (FBAV, Instagram, TikTok): son personas |
| 12 | `/admin` sin medir | Sólo `/admin` | `_RUTAS_INTERNAS`: `/admin`, `/contenido`, `/publicar`, `/campo`, `/mi-comercio` | Mejor | Mantener y cortar también en el front. **Nuevo:** no medir al equipo cuando navega el sitio público (§4.3) |
| 13 | Origin / `Sec-Fetch-Site` | Descarta lo que viene de otro sitio | No se mira | Peor | Copiar |
| 14 | Escritura directa a la base | — (no existe) | **`anon` tiene INSERT en `visitas` y `leads` por PostgREST**, que es público en `db.uruku.bo`. Cualquiera infla las visitas y los contactos de un comercio sin pasar por el backend | **Peor, grave** | Revocar (§4.1). El front no inserta directo en ningún lado (verificado) |
| 15 | Visitantes sin cookies | Hash diario de IP+UA en memoria | Sesión de pestaña en `sessionStorage` | Mejor para Bolivia | Mantener la sesión. Con CGNAT y el UA recortado de Chrome en Android, cientos de personas dan el mismo hash. Cambiar la etiqueta «Personas» por «Visitas (sesiones)» |
| 16 | Deduplicación | Una vista por lector por nota cada 30 min; un clic por aviso por día | Sólo evita repetir la misma ruta seguida. **La vista de ficha y los contactos no se deduplican**: un F5 suma otra «persona» en «Mi comercio» y en el reporte mensual | Peor, y es lo que se le vende al comerciante | Deduplicar por sesión + techo por IP en memoria (§4.2) |
| 17 | Validación de lo que llega | Ids validados contra la base | `tipo` desconocido **se convierte en `whatsapp`**; `comercio_id` inválido da 500 | Peor | Descartar lo desconocido (204); uuid validado |
| 18 | Topes de memoria | Todo con tope; si se llena, se cuenta de más | El limitador tiene tope | Igual | Todo lo nuevo en memoria lleva tope |
| 19 | Referidos canónicos | `google`, `facebook`, `whatsapp`; `android-app://` mapeado | Host crudo: `l.facebook.com`, `m.facebook.com`, `com.whatsapp`, `google.com.bo` y `google.com.ar` salen como filas distintas. Fuentes de IA sí canónicas (mejor que la receta) | Peor en general, mejor en IA | `classify_referrer` de PortalNoticias + paquetes que se usan acá + tipo `ai`, **al leer** (sirve también para el historial) |
| 20 | Escritura | Buffer en memoria, volcado cada 5 s | Un insert por página, del backend a `https://db.uruku.bo` (TLS y Traefik en cada visita), dentro del threadpool de toda la API | Peor ante un pico | Buffer + insert en lote por PostgREST cada 5 s (§4.2) |
| 21 | Modelo de datos | Sólo agregados por día | Filas crudas sin datos personales | Mejor para URUKU | Mantener filas: las preguntas de URUKU son de embudo por sesión, que un agregado no contesta (§3.2) |
| 22 | Resumen | SQL | Python baja hasta **50.000 filas de a 1.000** y corta en silencio (a 90 días se pasa con ~550 páginas/día) | Peor | Función SQL `site_metrics_summary` (§4.1). Misma línea que la memoria «pasar a SQL agrupado» |
| 23 | Dispositivo | mobile/tablet/desktop por visita | No se mide | Peor | Sumar `device` y `standalone` (app instalada o navegador) |
| 24 | Día en hora local | Sí | Sí (America/La_Paz) | Igual | — |
| 25 | Retención | 13 meses, `SECURITY DEFINER` con piso, la app sin DELETE | Ninguna; `service_role` tiene `grant all` | Peor | `purge_site_metrics` con piso de 13 meses + revocar DELETE (§4.1). Sólo `visitas` y `site_events`: `leads` y `busquedas` son historia del negocio |
| 26 | Test de privacidad | Columnas permitidas + volcado buscando IP/UA/query | Existe para `comercios` y `publicaciones`, no para la medición | Peor | `test_site_metrics_privacy.py` (§4.6) |
| 27 | Logs | uvicorn sin `/collect`; Traefik sin IP ni headers | uvicorn registra la IP de Traefik (sin `--proxy-headers`), no la del visitante. Traefik es compartido y su config está fuera del repo | A verificar | Filtro de access log en el backend; Traefik lo revisa el dueño (§7) |
| 28 | Panel | `/admin/estadisticas` | Monitoreo + KPIs + Demanda | Mejor (embudo) | Sumar a `PanelVisitas`: orígenes canónicos, dispositivos, app instalada, eventos, botón «Abrir Umami» |
| 29 | Comerciante | — (no existe) | «Mi comercio» + reporte mensual | Mejor | Sumar cómo llegar, compartieron, fueron a tus redes, de dónde llegaron (§4.3) |
| 30 | Avisos (impresiones, CTR) | Sí | URUKU no vende avisos | N/A | — |
| 31 | Umami | Sí | No | — | Opcional, detrás de un perfil de compose y del interruptor (§3.3, §4.4) |
| 32 | GA4 | Sí, con consentimiento | No | — | No (§3.4) |

---

## 3. Recomendación

### 3.1 Path dependence, declarado

Lo que recomiendo es lo de siempre de la casa: contadores propios en FastAPI + Postgres/PostgREST, con el front en Next.js. Y copiar la receta de PortalNoticias **también** es path dependence: es otro proyecto del mismo dueño, con otra forma (portal de noticias con SSR, sin comercios y sin embudo). Lo confirmo después de contrastarlo con:

| Alternativa | Qué daría | Por qué no es la base |
|---|---|---|
| **Umami como único medidor** (sin propios) | Tablero hecho, tiempo real, países | No sabe de comercios, búsquedas ni «¿te contestó?»; «Mi comercio» tendría que leer la base de Umami (acople a un esquema ajeno) |
| **Cloudflare Web Analytics** | Gratis, 0 RAM, sin cookies | Sin eventos propios ni UTM, 6 meses de historia, muestreado después de 7 días, datos en Cloudflare. Sirve como comparador si la RAM no alcanza para Umami |
| **GA4** | Gratis, demografía, Google Ads | Datos a Google, cookies, cartel, ~100 KB más en 3G (§3.4) |
| **Plausible CE / PostHog self-hosted** | Más análisis | Necesitan ClickHouse (Plausible ~1-2 GB de RAM; PostHog bastante más). Descartados frente a Umami |
| **Logs de Traefik + GoAccess** | Sin JS | Trabaja sobre IP y URL completa: va contra «sin datos personales» |

### 3.2 Decisiones

| Decisión | Elegida | Descartadas | Por qué | Qué la invalidaría |
|---|---|---|---|---|
| Fuente de verdad | Contadores propios (lo que ya existe, blindado) | Umami o GA4 como fuente | Son los números que ve y paga el comerciante; tienen que ser nuestros y explicables | — |
| Modelo | Filas crudas sin datos personales + resumen SQL + retención de 13 meses | Agregados por día (receta) | Las preguntas de URUKU son por sesión (vio el video → abrió la ficha → escribió). El volumen de hoy es chico | `visitas` > ~5 M filas o resumen > 2 s → sumar una tabla diaria con roll-up |
| Visitantes | Sesión de pestaña (ya existe) | Hash IP+UA (receta) | CGNAT de Entel, Tigo y Viva + UA recortado de Chrome → el hash junta a muchas personas en una | Que el dueño necesite «únicos por día»: ahí, un id diario al azar en `localStorage` |
| Deduplicación | Por sesión (cliente) + techo por IP con hash diario, en memoria | Sólo IP (sub-cuenta con CGNAT); sin deduplicar (hoy) | Un F5 no es una persona más; el techo por IP frena el inflado sin castigar al CGNAT | Más de un worker de uvicorn (cada proceso deduplicaría por su cuenta) |
| Escritura | Buffer en memoria, lote cada 5 s por PostgREST | Insert por pedido (hoy); cola persistida | Saca la base del camino de cada visita. Se aceptan ≤ 5 s de pérdida si el proceso muere | Contactos (`whatsapp`, `telefono`, `reserva`): siguen síncronos porque el id hace falta para «¿te contestó?» |
| Segundo medidor | **Umami self-hosted, apagado por defecto** (perfil `stats` + interruptor) | Cloudflare WA; ninguno | Datos en el VPS, como todo lo demás (Reservalo sin Supabase, tiles y fuentes propias). Da países (Argentina contra Bolivia, clave en la frontera), tiempo real y por hora | `available` < 2 GB en el VPS con Umami arriba → Cloudflare WA |
| GA4 | No | GA4 con consentimiento | §3.4 | Pauta paga en Google Ads que necesite conversiones o audiencias |
| CSP | Estática, sin nonce, `Report-Only` → enforce | Con nonce (receta); ninguna | El nonce rompe `force-static` + ISR de las fichas y la caché | Que las fichas pasen a SSR (no va a pasar: regla 9) |
| Config de Umami | Interruptor en `cost_switches` + `UMAMI_WEBSITE_ID` en `backend/.env`; URL fija `https://stats.<DOMAIN>/script.js` | Config editable en el panel (receta) | Cierra de raíz la falla «script ajeno con el nonce del sitio» | — |
| Retención | `purge_site_metrics(meses)` `SECURITY DEFINER`, piso 13 dentro de la función, `service_role` sin DELETE ni TRUNCATE en esas tablas | Purga desde Python con DELETE | El piso protege contra un error propio. Contra una clave `service_role` filtrada protege **sólo** porque se revoca el DELETE (con la clave igual se puede escribir basura: es la amenaza de fondo de un PostgREST público) | — |

### 3.3 Umami: cuánta RAM

No hay cifras oficiales de Umami; esto sale de reportes de terceros (fuentes al final).

| Componente | Reposo | Pico |
|---|---|---|
| Contenedor Umami v3 (Node), con `NODE_OPTIONS=--max-old-space-size=384` y `mem_limit: 512m` | 150-250 MB | 400-450 MB |
| Base `umami` en el Postgres existente, Prisma con `connection_limit=5` | 30-80 MB | ~100 MB |
| **Total** | **~0,2-0,35 GB** | **~0,5-0,55 GB** |

- **Prod** (KVM 4, 16 GB): hoy corren Traefik, Postgres, PostgREST, WAHA, frontend, backend con Whisper, tiles, reels (tope 1,5 GB) y todo Reservalo. Estimo que entra holgado, pero **es una estimación**: antes, `free -h` y `docker stats --no-stream`. Regla: se instala sólo si después queda `available` ≥ 2 GB.
- **QA** (KVM 2, 8 GB): sólo para probar los criterios y después `docker compose --profile stats stop umami`.
- Disco: sin purga automática conocida en Umami. Vigilar `pg_database_size('umami')` (~1-2 GB por año a 5.000 páginas/día).

### 3.4 GA4: no conviene hoy

- **Datos a Google y cookies** → hace falta el cartel de consentimiento, y URUKU hoy no lo necesita (0130 lo dice a propósito).
- **Peso:** gtag.js suma unos 100 KB y conexiones a otro dominio, justo lo que se sacó con las fuentes locales (20/10).
- **Cobertura:** el que rechaza no se mide; en la práctica, GA4 mide menos que los propios.
- **Lo que daría, ya lo da otra cosa gratis:** lo que se busca en Google lo da Search Console (sin script; O-3 de `visibilidad-buscadores-ia.md`), y países y tiempo real los da Umami.
- **Cuándo sí:** pauta en Google Ads que necesite conversiones. Si la pauta va a Facebook (lo más probable según `publicidad-uruku.md`), lo que se pediría es el Pixel de Meta, con el mismo problema de consentimiento. En los dos casos el módulo único deja enchufarlo en un solo archivo, reusando `ConsentBanner` y la parte GA4 de `analytics.ts` de PortalNoticias.

### 3.5 CSP: sin nonce, y cruzada con seguridad

- **Con nonce no se puede:** cada HTML pasa a ser distinto por pedido, y `/comercios/[slug]` (`force-static`, `revalidate=300`), `/que-es-uruku`, `/contacto` y `/manual` dejan de ser estáticas (`lesson-ssg-isr-en-catalogo-no-ssr-puro`). Además, `uruku-theme.tsx` mete un script en línea.
- **Lo que queda es `script-src 'self' 'unsafe-inline'`** + lista de hosts. Protege poco contra un XSS en línea, pero sí sirve para:
  - bloquear `<script src>` de hosts ajenos;
  - `frame-ancestors 'none'`: clickjacking de `/admin` y `/mi-comercio`;
  - `object-src 'none'`, `base-uri 'self'`, `form-action 'self'`;
  - `connect-src` acotado.
  Es un riesgo aceptado que **tiene que firmar `security-reviewer`**.
- **Inventario de orígenes a permitir:**
  - `unpkg.com` (Leaflet: script y CSS);
  - `api.<DOMAIN>` (API, fotos y videos);
  - `db.<DOMAIN>` (PostgREST);
  - `tiles.<DOMAIN>` y los `ciudades.tiles_url` (en `img-src` va `https:` porque cambian por ciudad);
  - `stats.<DOMAIN>` (sólo si Umami está prendido en el build).
  Va en `Report-Only` una semana justamente porque este inventario puede estar incompleto.
- **Cloudflare:** desde septiembre de 2025, en los sitios proxied del plan Free inyecta por defecto `static.cloudflareinsights.com/beacon.min.js`. Si `uruku.bo` está naranja, puede haber **un medidor no declarado** funcionando ahora (§7, tarea 3).

---

## 4. Spec de lo que se suma

### 4.1 Datos: migración `supabase/migrations/0185_site_metrics_v2.sql`

Idempotente, en una transacción, con bloque de comprobación al final (como la 0183), `notify pgrst, 'reload schema'`, y copiada por `selfhost/build-postgres-init.sh`. Columnas y tablas nuevas en inglés (AGENTS §6); `visitas` y `leads` conservan sus nombres.

```sql
-- 1. visitas: el navegador ya no escribe directo; sólo el backend (service_role)
alter table visitas add column if not exists device text check (device in ('mobile','tablet','desktop'));
alter table visitas add column if not exists standalone boolean not null default false;  -- abierta desde la app instalada
drop policy if exists visitas_insert_public on visitas;
revoke insert, select on visitas from anon, authenticated;
revoke update, delete, truncate on visitas from service_role;          -- sólo insert + select; borra la purga

-- 2. leads: ídem; conserva UPDATE (respondio)
alter table leads add column if not exists sesion  text check (char_length(sesion)  <= 40);
alter table leads add column if not exists detalle text check (char_length(detalle) <= 20); -- red ('instagram'…) o canal ('native'|'copy')
create index if not exists idx_leads_sesion on leads (sesion) where sesion is not null;
drop policy if exists leads_insert_public on leads;
revoke insert, select on leads from anon, authenticated;
revoke delete, truncate on leads from service_role;

-- 3. eventos del sitio (catálogo cerrado §4.5), mismas reglas que visitas
create table if not exists site_events (
  id         uuid primary key default gen_random_uuid(),
  day        date not null default ((now() at time zone 'America/La_Paz')::date),
  event      text not null check (event in ('share','pwa_install','video_play','video_network_click','uruku_whatsapp_click')),
  detail     text not null default '' check (char_length(detail) <= 40),
  path       text not null check (char_length(path) <= 200),
  session    text check (char_length(session) <= 40),
  city_slug  text check (char_length(city_slug) <= 40),
  created_at timestamptz not null default now()
);
create index if not exists idx_site_events_day     on site_events (day desc);
create index if not exists idx_site_events_session on site_events (session) where session is not null;
alter table site_events enable row level security;
revoke all on site_events from public, anon, authenticated;
grant select, insert on site_events to service_role;

-- 4. resumen (sin las 50.000 filas en Python): SECURITY INVOKER, sólo el backend
create or replace function site_metrics_summary(p_from date, p_to date, p_city text default null) returns jsonb
  language sql stable set search_path = public, pg_temp as $$ /* ver contrato abajo */ $$;
create or replace function comercio_origins(p_comercio uuid, p_from date) returns jsonb
  language sql stable set search_path = public, pg_temp as $$ /* referido/origen de las visitas cuya ruta es la ficha y primera=true */ $$;
revoke all on function site_metrics_summary(date,date,text), comercio_origins(uuid,date) from public, anon, authenticated;
grant execute on function site_metrics_summary(date,date,text), comercio_origins(uuid,date) to service_role;

-- 5. retención: único camino para borrar, con piso adentro
create or replace function purge_site_metrics(p_months int default 13) returns int
  language plpgsql security definer set search_path = public, pg_temp as $$
  -- if p_months is null or p_months < 13 then raise exception 'retención mínima: 13 meses';
  -- corte = (now() at time zone 'America/La_Paz' - p_months meses)::date
  -- delete from visitas where dia < corte; delete from site_events where day < corte; return filas borradas
$$;
revoke all on function purge_site_metrics(int) from public, anon, authenticated;
grant execute on function purge_site_metrics(int) to service_role;

-- 6. interruptor de Umami
alter table cost_switches drop constraint if exists cost_switches_key_check;
alter table cost_switches add constraint cost_switches_key_check check (key in ('gemini_content','umami_stats'));
```

**Contrato de `site_metrics_summary`** (jsonb):

- `totals`: `{pageviews, sessions, first_pages}`.
- `by_day`: todos los días del rango, con ceros.
- `top_paths`: las 15 primeras.
- `referrers_raw`: `[{referido, n}]`, top 300, de las páginas con `primera`. La canonicalización se hace en Python.
- `origins`: `?ref=`/`utm_source`.
- `devices`, `standalone_share`.
- `events`: `[{event, detail, n}]`.
- `funnel`: `{sessions, sessions_with_ficha, sessions_with_contact}`, cruzando `leads.sesion`. Sólo vale desde la 0184: antes los leads no traían sesión.
- `p_city` filtra por `ciudad_slug`/`city_slug`.

**Excepción a «nunca DELETE»:** `visitas` y `site_events` son telemetría sin valor por fila, que es la excepción «logs con TTL» de la lesson. Hay que escribirlo en AGENTS.md §7. `leads` y `busquedas` no se purgan nunca.

### 4.2 Backend

Servicio nuevo `backend/app/services/site_metrics.py` (reusa PortalNoticias, §5). Estado en memoria: **asume un solo worker de uvicorn** (es lo que corre hoy; dejarlo escrito en AGENTS.md).

| Endpoint | Cambio | Detalle |
|---|---|---|
| `POST /collect` (nuevo) | Página vista o evento | Body crudo ≤ 2 KB (`text/plain`), JSON `{t:'pv'\|'ev', path, session, device, standalone, ref?, referrer?, city?, event?, detail?}`. **204 siempre**; 413 si es grande; 429 si pasa el límite; nunca 500. Se descarta sin decir por qué: UA vacío o de bot, `Origin` que no es del sitio o `Sec-Fetch-Site: cross-site`, ruta interna (`_RUTAS_INTERNAS`), evento o `detail` fuera del catálogo, sesión mal formada. Va al buffer |
| `POST /visita` | Alias de compatibilidad | Las PWA instaladas tienen el bundle viejo en el service worker. Pasa por el mismo pipeline (con límite y filtro de bots). Se quita a los 60 días |
| `POST /lead` | Blindado | `tipo` fuera de la lista → `{ok:false}` sin guardar (**nunca** se convierte en `whatsapp`). Tipos nuevos: `compartir`, `red` (con `detalle`). Recibe `sesion`. `comercio_id` validado como uuid; un error de base da `{ok:false}`, no 500. Bots y Origin igual que `/collect`. Dedup (abajo). `vista`, `compartir` y `red` van al buffer; `whatsapp`, `telefono`, `reserva`, `mapa`, `email` y `web` se insertan síncronos y devuelven `id` |
| `POST /busquedas/log` | Blindado | Límite, bots y Origin. Enmascarar antes de guardar: secuencias de 6 o más dígitos → `#`, mails → `[mail]`. Tope de 100 caracteres |
| `POST /lead/{id}/respondio` | Límite | 30 por minuto por IP |
| `GET /public/measurement-config` (nuevo) | Config pública | `{internal: true, umami: {script_url, website_id} \| null}`. `umami` es null si el interruptor está apagado o falta `UMAMI_WEBSITE_ID` (uuid). `script_url` viene **fijo** de `UMAMI_SCRIPT_URL` (compose: `https://stats.${DOMAIN}/script.js`) y se revalida antes de exponerlo. `Cache-Control: public, max-age=300` |
| `GET /admin/visitas` | Reescrito sobre la RPC | Misma forma de respuesta y además: `referrers` (`[{kind:'search'\|'social'\|'whatsapp'\|'ai'\|'direct'\|'other', name, n}]`), `devices`, `standalone_share`, `events`, `funnel`, `umami_url` (si está configurado), `last_hit_at` (para detectar una caída silenciosa, el trade-off del pattern fire-and-forget). Permiso `datos`, `Cache-Control: no-store` |
| `GET /comercio/metricas` | Ampliado | `como_llegar_30d` (tipo `mapa`), `compartidos_30d`, `redes_30d` (por `detalle`), `origenes_30d` (canónicos + QR, de `comercio_origins`). Ya llegan deduplicados. Nunca números de otros comercios ni rankings |
| `POST /csp-report` (nuevo) | Reportes de CSP | Límite de 30 por minuto por IP; structlog `csp_violation` con directiva y host bloqueado, sin IP. Se puede apagar al pasar a enforce |
| `/admin/cost-switches` | Clave nueva | `umami_stats`: «Estadísticas con Umami». Costo: «Gratis en plata. Usa entre 0,3 y 0,5 GB de RAM del servidor y necesita el contenedor `umami` prendido». Apagado: «Siguen las estadísticas propias» |

**Límites, deduplicación y topes en memoria:**

| Estructura | Clave | Regla | Tope |
|---|---|---|---|
| Límite `/collect` | IP (IPv6 por /64), ventana fija de 1 min | 300/min (CGNAT: una IP pública = mucha gente) | 50.000 claves; lleno → se acepta y no se guarda |
| Límite `/lead` | ídem | 120/min | ídem |
| Límite `/busquedas/log` | ídem | 60/min | ídem |
| Dedup de vista | `(sesion, comercio)` | 1 cada 30 min | 200.000; lleno → se cuenta de más |
| Dedup de contacto | `(sesion, comercio, tipo)` | 1 por día; el repetido responde `{ok:true, id:<el del primero>, repetido:true}` (así «¿te contestó?» no pregunta dos veces) | ídem |
| Techo por IP | `blake2b(sal_del_día + IP)`, la IP nunca se guarda ni se loguea | ≤ 30 `vista` y ≤ 10 de cada contacto por comercio por día | ídem |
| Buffer | filas pendientes | Volcado cada 5 s y al apagar: un `insert` en lote por tabla (`visitas`, `site_events`, `leads`) por PostgREST. Si falla, se loguea `site_metrics_flush_failed` y se descarta el lote | 20.000 filas; llenas → `site_metrics_buffer_full` |

- La IP sale de `core/ip.ip_cliente` (último valor de `X-Forwarded-For`). **Si `api.uruku.bo` pasa a naranja** en Cloudflare, ese valor es la IP del borde de Cloudflare: habría que leer `CF-Connecting-IP` y validar los rangos de Cloudflare (riesgo abierto).
- Loops nuevos en el `lifespan` de `main.py`:
  - `_site_metrics_flush_loop` (cada 5 s);
  - `_site_metrics_retention_loop` (diario, 04:00 de Bolivia, `rpc('purge_site_metrics', {p_months: 13})`).
- Access log: un filtro de logging descarta las líneas de uvicorn de `/collect`, `/visita`, `/lead`, `/busquedas/log` y `/csp-report`. No sumar `--proxy-headers --forwarded-allow-ips '*'`.

### 4.3 Frontend

**`frontend/lib/medicion.ts`: el único punto de entrada.** Ningún componente llama a `fetch`, a Umami ni a `/lead` para medir.

| Función | Hace |
|---|---|
| `configurarMedicion()` | Lee `/public/measurement-config` (cache de 5 min en `sessionStorage`), encola lo que llegó antes y carga Umami si corresponde |
| `vistaDePagina(path)` | Ruta limpia (sin query ni hash); ignora la misma ruta dentro de 1 s; `referrer` sólo en la primera página de la carga; `device`, `standalone`, sesión y ciudad → `sendBeacon(text/plain)` a `/collect`, con `fetch keepalive credentials:'omit'` de respaldo. Umami: `umami.track({url, title})` |
| `evento(nombre, detail?)` | Catálogo §4.5 → `/collect` y Umami |
| `contacto(comercioId, tipo, {busquedaId, origen, nombre, detalle})` | Reemplaza `registrarLead`: `/lead` con `sesion`, devuelve el `id` (sigue alimentando `anotarContacto`) |
| `busqueda(q, n, ids)` | Reemplaza `logBusqueda` y devuelve `busqueda_id` |

Reglas del módulo:

- Todo en try/catch.
- Nunca mide las rutas internas: la lista sale de una constante compartida, igual a `_RUTAS_INTERNAS`.
- **No mide al equipo:**
  - si en `localStorage` está `bermejo_admin_token`, `bermejo_agente_token` o `bermejo_publicador_token`, no manda nada;
  - si está `bermejo_comercio_token`, no cuenta vistas ni contactos **de su propio comercio**.
- Umami se carga con:
  - `data-auto-track="false"`, `data-exclude-search="true"` y `data-domains="<host de prod>"`;
  - la `script_url` sólo si es exactamente `${NEXT_PUBLIC_STATS_ORIGIN}/script.js`;
  - si falla, se saca la etiqueta y reintenta en la próxima navegación (como en PortalNoticias).

**Cambios en llamadores:**

- `contador-visitas.tsx` → `vistaDePagina`.
- `vista-logger.tsx` → `contacto(…,'vista')`.
- `buscar-client.tsx`, `lead-link.tsx`, `wa-lead-link.tsx`, `map-results.tsx`, `app/reservas/page.tsx` → `contacto`.
- `registrarVisita`, `registrarLead` y `logBusqueda` salen de `lib/campo.ts`, que las reexporta un tiempo para no romper.

**Eventos nuevos:**

- `compartir-boton.tsx`: `comercioId?` → `contacto('compartir')` en la ficha o `evento('share')` en el resto; `detail` es `native` o `copy`.
- `install-prompt.tsx`: `pwa_install` con `shown`, `accepted`, `dismissed`, `installed` o `ios_hint`.
- `video-uruku-card.tsx`: `video_play` (id del video) al abrir y `video_network_click` en los enlaces a redes.
- Enlaces a redes en la ficha (`enlaceRed`): `contacto('red', {detalle})`.
- Enlaces al canal, la comunidad y el contacto de URUKU (`lib/contacto.ts`): `uruku_whatsapp_click`.

**Panel (`components/panel-visitas.tsx`), en voseo y con estilos en línea como hoy:**

- «Personas» pasa a ser «Visitas (sesiones)». Ayuda: «Una por pestaña abierta. No usamos cookies».
- «De dónde llegan»: Google, Facebook, WhatsApp, IA, Directo y Otros, con el detalle al tocar.
- «Desde la app instalada: N%» y celular/tablet/computadora.
- «Qué hicieron»: compartieron, instalaron la app, vieron un video, tocaron el canal.
- «Último dato recibido hace X min».
- Botón «Abrir Umami» si viene `umami_url`.
- La tarjeta «Servicios con costo» (la de `/contenido`) se reusa también en Monitoreo con `umami_stats`.
- Sin scroll horizontal a 375 px.

**«Mi comercio» (`EstadisticasView` y las tarjetas del inicio):**

- «Personas que vieron tu ficha». Nota: «Contamos una vez por persona cada media hora».
- «Te escribieron o llamaron».
- «Te pidieron cómo llegar».
- «Compartieron tu ficha».
- «Fueron a tus redes».
- «De dónde llegaron» (QR del volante o de la mesa, Google, Facebook, WhatsApp, directo).
- «Con qué palabras te encontraron» (ya existe).
- **Nunca** cantidades de otros comercios ni posiciones en un ranking.

**CSP (`frontend/next.config.mjs` → `headers()`), sin middleware ni nonce:**

```
default-src 'self'; script-src 'self' 'unsafe-inline' https://unpkg.com [STATS_ORIGIN/script.js];
style-src 'self' 'unsafe-inline' https://unpkg.com; img-src 'self' data: blob: https:;
connect-src 'self' https://api.<DOMAIN> https://db.<DOMAIN> [STATS_ORIGIN]; media-src 'self' https://api.<DOMAIN> blob:;
font-src 'self'; worker-src 'self'; manifest-src 'self'; frame-src 'none'; object-src 'none';
base-uri 'self'; form-action 'self'; frame-ancestors 'none'; report-uri https://api.<DOMAIN>/csp-report
```

- En las rutas internas, la misma política **sin** `STATS_ORIGIN`.
- Primero va como `Content-Security-Policy-Report-Only`; enforce después de 7 días sin violaciones sin explicar.
- Build args nuevos: `NEXT_PUBLIC_STATS_ORIGIN` (vacío = sin Umami en la CSP) y `NEXT_PUBLIC_API_URL` (ya existe).

### 4.4 Infra

**Servicio `umami` en `docker-compose.prod.yml`** (base: el de PortalNoticias):

| Campo | Valor |
|---|---|
| `profiles` | `["stats"]`: no arranca con el `up` de siempre; se levanta con `--profile stats` |
| `image` | `ghcr.io/umami-software/umami:3.4.1` (fija; verificar el tag el día del deploy) |
| `container_name` | `uruku-umami` (nombre único: la lección de WAHA y Reservalo con los alias compartidos) |
| `environment` | `DATABASE_URL=postgresql://umami:${UMAMI_DB_PASSWORD}@buscadonde-postgres:5432/umami?connection_limit=5` · `APP_SECRET` · `TWO_FACTOR_ENCRYPTION_KEY` (64 hex, no rotar después de activar 2FA) · `DISABLE_TELEMETRY=1` · `NODE_OPTIONS=--max-old-space-size=384` |
| Recursos y endurecimiento | `mem_limit: 512m`, `cpus: 0.5`, `cap_drop: [ALL]`, `no-new-privileges`, healthcheck `GET /api/heartbeat` |
| Redes | `[traefik, umami_db]`. `umami_db` (`internal: true`) es nueva; `postgres` pasa a `[internal, umami_db]`. Umami no ve backend, frontend ni WAHA |
| Router público (prioridad 100) | `Host(stats.${DOMAIN}) && (Path(/script.js) \|\| Path(/api/send))` |
| Router del tablero (prioridad 10) | Resto de `stats.${DOMAIN}`, con un middleware `ratelimit` de Traefik para el login. Login propio de Umami + 2FA. Sin grabación de sesiones ni enlaces públicos para compartir |
| Backend | `environment: UMAMI_SCRIPT_URL=https://stats.${DOMAIN}/script.js` (no en `.env`, para que no quede vieja) |

**Más infra:**

- **`selfhost/umami-init.sh` (nuevo, reusa `selfhost/deploy.sh` de PortalNoticias):**
  - lo corre `deploy-prod.sh` sólo si se pasa `--profile stats`;
  - la sesión SQL arranca con `set log_statement='none'; set log_min_duration_statement=-1; set log_min_error_statement='panic';`;
  - crea el rol `umami` (`nosuperuser nocreatedb nocreaterole nobypassrls`) y la base `umami owner umami`;
  - permisos: `revoke connect on database umami from public; grant connect on database umami to umami;`;
  - además `revoke connect on database postgres from public; grant connect on database postgres to authenticator;`. Es el único rol que se conecta (más `postgres`). **Probar en QA primero**: si PostgREST pierde el CONNECT, se cae el sitio;
  - espera a que Umami esté healthy y cambia `admin/umami` por `UMAMI_ADMIN_PASSWORD` (`POST /api/auth/login` + `POST /api/me/password`), sin imprimirla.
- **`selfhost/init_prod_env.py`:** genera `UMAMI_DB_PASSWORD`, `UMAMI_APP_SECRET`, `UMAMI_TWO_FACTOR_KEY` y `UMAMI_ADMIN_PASSWORD` si faltan.
- **`selfhost/backup.sh`:** si existe la base `umami`, `pg_dump -d umami` aparte.
- **Traefik (`/docker/traefik`, fuera del repo, compartido con Reservalo):** si el access log está prendido, `--accesslog.fields.names.ClientHost=drop`, `ClientAddr=drop`, `ClientPort=drop` y `--accesslog.fields.headers.defaultmode=drop`. Hoy, si está prendido, junta IP + `/buscar?q=…`. Dejarlo escrito en `docs/deploy-prod-nuevo-vps.md`.

### 4.5 Catálogo de eventos

| Evento | `detail` (conjunto cerrado) | Dónde va | Para qué |
|---|---|---|---|
| Contacto (`whatsapp`, `telefono`, `reserva`, `email`, `web`) | — | `leads` (ya existe) | Lo que vale para el comerciante |
| Cómo llegar | — | `leads.tipo='mapa'` (ya existe) | Intención de ir al local |
| Compartir una ficha | `native` \| `copy` | `leads.tipo='compartir'` | Boca a boca por comercio |
| Ir a las redes del comercio | `instagram` \| `facebook` \| `tiktok` \| `youtube` | `leads.tipo='red'` | Le dice al comerciante qué red le sirve |
| `share` (fuera de la ficha) | `native` \| `copy` | `site_events` | Difusión de URUKU |
| `pwa_install` | `shown` \| `accepted` \| `dismissed` \| `installed` \| `ios_hint` | `site_events` | Embudo de instalación |
| `video_play` | id del video (uuid) | `site_events` | Qué video de la home se mira; el título se une al leer |
| `video_network_click` | `tiktok` \| `instagram` \| `facebook` \| `youtube` | `site_events` | Si el video lleva a las redes de URUKU |
| `uruku_whatsapp_click` | `canal` \| `comunidad` \| `contacto` | `site_events` | Altas al canal y la comunidad |
| Búsqueda sin resultado | — | `busquedas.resultados=0` (ya existe) | Demanda; **no** se duplica como evento |

### 4.6 Criterios de aceptación

| CA | Criterio |
|---|---|
| CA-1 | Una visita a una ficha aparece en `visitas` y en `leads` (`vista`) dentro de los 10 s, y en Umami (si está prendido) dentro de 1 min |
| CA-2 | En la misma pestaña: F5 en la ficha dentro de 30 min no suma `vista`; dos toques a WhatsApp en el mismo día suman un contacto, el segundo responde con el mismo `id` y «¿te contestó?» pregunta una sola vez |
| CA-3 | `POST https://db.<DOMAIN>/rest/v1/visitas` (o `leads`) con la clave anon → 401/403 (42501) |
| CA-4 | Ninguna tabla de medición guarda IP, UA, cookie ni query string: test de columnas permitidas de `visitas`, `site_events` y `leads` + volcado buscando la IP, el UA y `?q=` del pedido de prueba (`backend/tests/test_site_metrics_privacy.py`) |
| CA-5 | Con el interruptor `umami_stats` apagado, el script deja de cargarse en ≤ 5 min sin redeploy. Prendido con el contenedor caído, el sitio funciona y no reintenta en cada render |
| CA-6 | Rutas internas y navegadores con token de admin, agente o publicador no mandan nada. El comerciante logueado no suma vistas a su propia ficha |
| CA-7 | CSP en `Report-Only` sin violaciones sin explicar en home, buscar, ficha, mapa, ofertas, guía, novedades, admin, mi-comercio y campo durante 7 días; después, enforce. Las tarjetas nuevas sin scroll horizontal a 375 px |
| CA-8 | UA `Googlebot`, `facebookexternalhit`, `HeadlessChrome`, `curl` o vacío → 204 y nada guardado. UA de Instagram, Facebook (FBAV) y TikTok in-app → se cuenta |
| CA-9 | El pedido 301 por minuto de una IP a `/collect` → 429; el 121 a `/lead` → 429. Body de 3 KB → 413. Nunca 500 (con la base caída: 204 y log) |
| CA-10 | Origen canónico: `android-app://com.whatsapp/` → WhatsApp; `l.`, `m.` y `lm.facebook.com` y `com.facebook.lite` → Facebook; `google.com.bo` y `google.com.ar` → Google; `chatgpt.com` → IA/ChatGPT; `com.zhiliaoapp.musically` → TikTok |
| CA-11 | `purge_site_metrics(1)` → error. `purge_site_metrics(13)` borra sólo lo de antes del corte. `service_role` no puede hacer `DELETE` en `visitas` (42501) |
| CA-12 | `/admin/visitas?dias=90` con 300.000 filas sembradas responde en < 1 s y no corta los totales |
| CA-13 | «Mi comercio» muestra cómo llegar, compartieron, redes y de dónde llegaron; ninguna cifra de otros comercios |
| CA-14 | Un cliente viejo que manda `POST /visita` con JSON sigue contando (60 días) |
| CA-15 | `POST /lead` con `tipo:"cualquiera"` no guarda nada (antes se contaba como WhatsApp) |
| CA-16 | Una búsqueda «71234567 zapatos» queda guardada como «# zapatos» |

---

## 5. Qué se reusa de PortalNoticias

| Archivo de origen | Qué se toma | Adaptación en URUKU |
|---|---|---|
| `backend/app/modules/stats/collect.py` | `is_bot` + `_BOT_RE`, `client_key`, `WindowRateLimiter`, `origin_allowed`, `normalize_path`, `normalize_domain`, `classify_referrer` + `_APPS`, `_SOCIAL`, `_SEARCH`, `_GOOGLE_RE`; el `_digest` con sal diaria; la idea de `StatsBuffer` | → `services/site_metrics.py`. Suma los paquetes `com.facebook.lite` y `com.zhiliaoapp.musically` y el tipo `ai` (vía `core/ai_sources.classify_ai_source`). **No** se toman `VisitTracker` (hash de visitantes) ni `write_batch` (SQL directo: URUKU escribe por PostgREST) |
| `backend/app/api/public/collect.py` | `_read_limited_body` (2 KB) y el flujo 204/413/429 | → `api/collect.py` |
| `backend/app/db/migrations/0092_f007_stats.sql` + `0093_f007_stats_hardening.sql` | Forma de `purge_stats` con el piso adentro | → `purge_site_metrics` sobre `visitas` y `site_events` |
| `frontend/lib/analytics.ts` | Cola hasta conocer la config, `sendInternal`, `loadUmami` con reintento, `detectDevice`, `cleanPath`, `externalReferrerDomain`, dedup de 1 s | → `lib/medicion.ts`, **sin** GA4, consentimiento ni avisos (≈ 200 de sus 444 líneas) |
| `frontend/lib/analytics-config.ts` | Validación de uuid, `originOf` | Simplificada: la URL del script es fija |
| `frontend/components/admin/StatsChart.tsx` | Gráfico SVG sin dependencias | Opcional, para reemplazar las barras de `PanelVisitas` |
| `selfhost/docker-compose.prod.yml` (servicio `umami`) | Bloque, dos routers, endurecimiento | Perfil `stats`, nombres y redes de URUKU |
| `selfhost/deploy.sh` (parte Umami) e `init_env.py` | Rol, base, logs silenciados, cambio de clave de fábrica, generación de secretos | → `selfhost/umami-init.sh` y `selfhost/init_prod_env.py` |
| **No se reusan** | `csp.ts` + `middleware.ts` (nonce), `ConsentBanner`, `MeasurementPreferences`, `summary.py`, tablas `stats_daily_*` | Ver §3 |

---

## 6. Reparto

Se puede paralelizar por capa. El orden de merge es: migración → backend → frontend (el front usa `/collect` y `measurement-config`). Umami es independiente y opcional.

| Rol | Entrega | Archivos |
|---|---|---|
| **backend-dev** | Migración 0184; `site_metrics.py` (límites, bots, dedup, buffer, canonicalización); `POST /collect`, alias `/visita`, `/lead`, `/busquedas/log` y `/lead/{id}/respondio` blindados; `GET /public/measurement-config`; `/admin/visitas` y `/comercio/metricas` sobre las RPC; `POST /csp-report`; loops de volcado y retención; filtro del access log; clave `umami_stats` en `cost_switches.CATALOGO`; tests (CA-2/3/4/8/9/10/11/12/14/15/16) | `supabase/migrations/0185_site_metrics_v2.sql`, `backend/app/services/site_metrics.py`, `backend/app/api/collect.py`, `backend/app/api/campo.py`, `backend/app/api/comercio.py`, `backend/app/api/moderacion.py`, `backend/app/db/repository.py`, `backend/app/services/cost_switches.py`, `backend/app/main.py`, `backend/tests/test_site_metrics*.py`; AGENTS.md §7 (excepción de retención, un solo worker) |
| **frontend-dev** | `lib/medicion.ts`; migrar los llamadores; eventos nuevos; `PanelVisitas`; «Mi comercio»; CSP `Report-Only` en `next.config.mjs`; e2e (CA-1/5/6/7/13) | `frontend/lib/medicion.ts`, `lib/campo.ts`, `components/contador-visitas.tsx`, `vista-logger.tsx`, `wa-lead-link.tsx`, `lead-link.tsx`, `map-results.tsx`, `buscar-client.tsx`, `compartir-boton.tsx`, `install-prompt.tsx`, `video-uruku-card.tsx`, `panel-visitas.tsx`, `app/mi-comercio/page.tsx`, `app/reservas/page.tsx`, `lib/api.ts`, `next.config.mjs` |
| **infra** (backend-dev o el dueño) | Servicio `umami` con perfil, red `umami_db`, `umami-init.sh`, secretos, backup, build arg `NEXT_PUBLIC_STATS_ORIGIN`, nota de Traefik | `docker-compose.prod.yml`, `selfhost/umami-init.sh`, `selfhost/init_prod_env.py`, `selfhost/backup.sh`, `scripts/deploy-prod.sh`, `docs/deploy-prod-nuevo-vps.md` |
| **security-reviewer** | Firmar la CSP sin nonce, el `revoke connect` y los permisos de la 0184 | — |

---

## 7. Lo que tiene que hacer el dueño

| # | Tarea | Cuándo |
|---|---|---|
| 1 | Aprobar esta propuesta, en especial: **los números del comerciante van a bajar** al deduplicar (F5 y doble toque dejan de sumar). Decidir si se avisa a los suscriptores | Antes de empezar |
| 2 | En prod y QA, correr `free -h` y `docker stats --no-stream` y pasar la salida. Con eso se decide Umami (regla: `available` ≥ 2 GB con Umami arriba) | Antes de Umami |
| 3 | En Cloudflare, ver si `uruku.bo` está en naranja y si **Web Analytics** tiene la inyección automática prendida (Analytics & Logs → Web Analytics). Recomiendo apagarla: es un medidor no declarado y la CSP lo va a reportar. Si Umami no entra en RAM, es la alternativa | Ya |
| 4 | DNS en Cloudflare: registro **A `stats.uruku.bo` → 179.198.126.170, DNS only (gris)**, como `api` y `db`, para que Let's Encrypt emita el certificado. Para probar en QA: `stats.encontralo.store` → 76.13.234.191 | Antes del deploy de Umami |
| 5 | Con Umami arriba: entrar a `https://stats.uruku.bo` con la clave de `UMAMI_ADMIN_PASSWORD` (gestor de contraseñas), **activar el 2FA**, crear el sitio «URUKU» (dominio `uruku.bo`), copiar el *website id* a `backend/.env` → `UMAMI_WEBSITE_ID`, reiniciar el backend y prender «Estadísticas con Umami» en Servicios con costo | Después del deploy |
| 6 | Revisar si el access log de Traefik (`/docker/traefik`) está prendido; si lo está, aplicar los `drop` de §4.4 (afecta también a Reservalo, para bien) | Cuando pueda |
| 7 | GA4: **nada**. Si algún día hay pauta en Google Ads, se retoma con la receta §7 | — |
| 8 | Search Console + Bing Webmaster (O-3 de `visibilidad-buscadores-ia.md`), si no está hecho: gratis, sin script ni cookies, y da lo que GA4 aportaría sobre Google | Cuando pueda |
| 9 | Confirmar 13 meses de retención para visitas y eventos (los contactos y las búsquedas no se borran nunca) | Antes de empezar |

---

## 8. Riesgos abiertos

| Riesgo | Validación |
|---|---|
| La deduplicación baja las cifras que el comerciante ya conoce y el reporte mensual | El dueño decide cómo comunicarlo (§7.1) |
| `revoke connect on database postgres from public` puede dejar a PostgREST sin conexión si hay otro rol que se conecta y no está inventariado | Probar en QA; volver atrás con `grant connect … to public` |
| CSP con `unsafe-inline`: protección parcial contra XSS | `security-reviewer` firma el riesgo aceptado |
| La estimación de RAM de Umami es de terceros, no medida en este VPS | §7.2 |
| La clave de fábrica `admin/umami` queda expuesta unos segundos entre que Umami arranca y se rota | Como en PortalNoticias; el script avisa si no pudo rotarla |
| Si `api.uruku.bo` pasa a naranja, la IP del límite pasa a ser la de Cloudflare | Leer `CF-Connecting-IP` validando rangos, si se cambia |
| El estado en memoria asume un solo worker de uvicorn | Escribirlo en AGENTS.md; si se suben workers, mover la dedup a Postgres |
| Con una clave `service_role` filtrada igual se puede escribir basura (PostgREST es público) | Amenaza de fondo, fuera de este alcance |

**Fuentes externas** (cifras de RAM y Cloudflare; no hay documentación oficial de sizing de Umami):
[Umami discussion #2715](https://github.com/umami-software/umami/discussions/2715) ·
[Use-Apify: Umami self-hosted](https://use-apify.com/docs/self-hosted/analytics/umami) ·
[BitDoze: Umami en Docker](https://www.bitdoze.com/umami-analytics-install/) ·
[Medium: memoria alta en Umami](https://medium.com/@javierleandroarancibia/how-i-safely-managed-high-memory-usage-in-umami-with-a-self-contained-fix-script-5fc839f5594e) ·
[Cloudflare Web Analytics: límites](https://developers.cloudflare.com/web-analytics/limits/) ·
[hostim.dev: inyección automática del beacon](https://hostim.dev/blog/cloudflare-beacon-injection/) ·
[Plausible vs Cloudflare WA (retención y muestreo)](https://plausible.io/vs-cloudflare-web-analytics)
