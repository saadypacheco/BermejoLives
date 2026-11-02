# Investigación: publicar en redes de URUKU y aparecer en buscadores de IA

> Fecha de consulta de todas las fuentes: **2026-11-02**. Las reglas de las plataformas cambian seguido: re-verificar antes de construir.
> Niveles: **confirmado** (doc oficial) / **probable** (fuente secundaria o doc oficial ambigua) / **no encontrado**.
> Cuando una fuente oficial se cita a través de una herramienta de lectura que resume la página, lo marqué igual como confirmado solo si la cita es textual.

## 0. Resumen de una línea por red

| Red | ¿API oficial sirve para un negocio chico sin auditoría? | Confianza |
|---|---|---|
| TikTok | **No para publicar en público.** Sin auditoría todo queda privado (`SELF_ONLY`), y TikTok rechazó apps de «uso personal/interno». Sí sirve la vía *Upload* (borrador en el inbox, el humano toca «Publicar»). | confirmado (privado) / probable (rechazo de uso interno: reporte de un dev) |
| Instagram (Reels + carruseles) | **Sí**, con cuenta profesional y app propia en modo desarrollo (Standard Access, vos como admin/rol). | confirmado (requisitos) / probable (que no pida App Review en cuenta propia) |
| Facebook Page (Reels) | **Sí**, mismas condiciones que Instagram. | confirmado (requisitos) / probable (sin App Review) |
| YouTube Shorts | **Sí**, la doc actual dice que ya no se fuerza privado en proyectos sin verificar. Cuota: 100 subidas/día. | confirmado (doc actual) con contradicción histórica, ver 1.4 |
| Canal de WhatsApp | **No hay API oficial** para publicar. | probable (no aparece en docs de Meta; lo afirman solo proveedores) |

---

## 1. APIs oficiales de publicación

### 1.1 Versión actual de Graph API

| Versión | Lanzada | Vence |
|---|---|---|
| v26.0 | 2026-07-29 | sin fecha (TBD) |
| v25.0 | 2026-02-18 | 2028-07-29 |
| v24.0 | 2025-10-08 | 2028-02-18 |
| v21.0 | 2024-10-02 | 2027-01-21 |
| v20.0 | 2024-05-21 | **2026-09-24 (ya vencida hoy)** |

Fuente: https://developers.facebook.com/docs/graph-api/changelog/versions/ (visto 2026-11-02). **Confirmado**: v26.0 es la actual; v20.0 ya no se puede usar. Recomendación: fijar `v26.0` en el código.

### 1.2 TikTok Content Posting API

| Tema | Hallazgo | Fuente (visto 2026-11-02) | Confianza |
|---|---|---|---|
| Direct Post | Publica directo al perfil. Scope `video.publish`. | https://developers.tiktok.com/doc/content-posting-api-get-started | confirmado |
| Upload (borrador) | Guarda el contenido como **borrador en el inbox** del usuario; el usuario abre la notificación y lo termina/publica en la app. Scope `video.upload`. Videos: `/v2/post/publish/inbox/video/init/`. Fotos: `/v2/post/publish/content/init/` (con `PULL_FROM_URL` la URL debe ser de un dominio verificado). | https://developers.tiktok.com/doc/content-posting-api-get-started-upload-content | confirmado |
| Cliente sin auditar | «All content posted by unaudited clients will be restricted to private viewing mode». Solo `SELF_ONLY`; hasta 5 usuarios en 24 h; las cuentas deben estar en privado al momento de postear. | https://developers.tiktok.com/doc/content-sharing-guidelines | confirmado |
| Tope diario | ~**15 posts por día por creador** (compartido entre todos los clientes API; «puede variar»). Además hay un tope de creadores activos por cliente según lo declarado en la auditoría. | misma página de guidelines | confirmado |
| Auditoría | Se pide en https://developers.tiktok.com/application/content-posting-api. **TikTok no publica plazo.** | guidelines | confirmado (que existe) / **no encontrado** (plazo oficial) |
| Plazo estimado | Acceso al producto: días; auditoría: «semanas» (estimaciones de terceros: 2-6 semanas). | https://bundle.social/blog/tiktok-api-approval (2026-08-04, vendor con interés comercial) | probable |
| Los posts hechos antes de auditar | Quedan privados aun después de aprobar; hay que recrearlos. | bundle.social (misma fuente) | probable |
| UX obligatorio de Direct Post | El usuario debe consentir antes del upload; preview del contenido; selector de privacidad **sin valor por defecto**; interacciones (comentarios, dúo, stitch) apagadas por defecto; declaración de Music Usage Confirmation antes del botón publicar. Es decir, el flujo asume una **persona al frente de una pantalla**, no un cron. | https://developers.tiktok.com/doc/content-sharing-guidelines | confirmado |
| Uso personal/interno | La guideline dice que el cliente debe apuntar a «a wide audience, not limited to internal groups/private use». Un dev reporta (2026-10-13) que TikTok le rechazó la auditoría con: «Applications intended for personal use or internal company use are not eligible for approval», citando «Not acceptable: A utility tool to help upload contents to the account(s) you or your team manages». | guideline: https://developers.tiktok.com/doc/content-sharing-guidelines ; rechazo: https://github.com/gitroomhq/postiz-app/issues/2297 (issue del 2026-10-20, **relato de segunda mano**) | frase de «wide audience» confirmada; el rechazo textual es probable |

**Conclusión TikTok:** una app propia de URUKU para postear solo en la cuenta de URUKU **probablemente no pasa la auditoría**, así que quedaría en privado. La vía *Upload* (borrador) no tiene la restricción de visibilidad descrita, pero igual exige que la app tenga aprobado el scope `video.upload` y que una persona toque «Publicar» en el celular.

### 1.3 Instagram (Graph API, content publishing)

| Tema | Hallazgo | Fuente (visto 2026-11-02) | Confianza |
|---|---|---|---|
| Cuenta | Hace falta **cuenta profesional** de Instagram. | https://developers.facebook.com/docs/instagram-platform/content-publishing | confirmado |
| Página de Facebook | Con *Facebook Login* se necesita la Página vinculada (rol `MANAGE` o `CREATE_CONTENT`) y permisos `instagram_basic`, `instagram_content_publish`, `pages_read_engagement`. Con *Instagram Login* (token de usuario de Instagram, permisos `instagram_business_basic` + `instagram_business_content_publish`) la doc no exige Página. Si la Página exige Page Publishing Authorization (PPA), no se publica hasta completarla. | https://developers.facebook.com/docs/instagram-platform/content-publishing ; https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media | confirmado |
| Límite 24 h | **100 posts publicados por API en 24 h móviles** (carrusel = 1). Chequeo: `GET /<IG_ID>/content_publishing_limit`. | content-publishing | confirmado |
| Contradicción | La misma página dice en la sección de carruseles «limited to 50 published posts within a 24-hour period». Meta no lo reconcilia. Para URUKU (1-3 posts/día) es irrelevante. | content-publishing | confirmado (la contradicción) |
| Contenedores | 400 contenedores por 24 h; expiran a las 24 h. | ig-user/media (referencia) | confirmado |
| Reels, video | MP4/MOV, H.264 o HEVC, AAC (≤48 kHz), 23-60 fps, ancho máx. 1920 px, bitrate de video ≤25 Mbps, **3 s a 15 min**, **≤300 MB**, 9:16 recomendado (acepta 0.01:1 a 10:1). Los Reels **no pueden ir dentro de carruseles**. Portada JPEG ≤8 MB. | ig-user/media (referencia) | confirmado |
| Carrusel | Hasta **20** ítems (imágenes/videos). Imágenes **solo JPEG**; se recortan al aspecto de la primera (1:1 por defecto). | content-publishing | confirmado |
| Imagen de feed | JPEG, ≤8 MB, sRGB, aspecto entre 4:5 y 1.91:1, ancho 320-1440 px. | ig-user/media | confirmado |
| Media | Debe estar en un **servidor público** al momento de publicar (el API la descarga por URL). | content-publishing | confirmado |
| Música | El etiquetado de música solo funciona con audio original; no se puede elegir música de la biblioteca de Instagram por API. | ig-user/media | confirmado |
| Acceso | *Standard Access* se aprueba automáticamente y sirve para usuarios con rol en la app (admin/dev/tester): no requiere App Review. | https://developers.facebook.com/docs/graph-api/overview/access-levels | confirmado (regla) / probable (que aplique sin fricción en la práctica para publicar en la cuenta propia) |
| Token | Token largo de Instagram Login: 60 días, renovable (≥24 h de edad, no vencido). Si se deja vencer, no se renueva más. | https://developers.facebook.com/docs/instagram-platform/instagram-api-with-instagram-login/business-login | confirmado |

### 1.4 Facebook Pages (Reels y video)

| Tema | Hallazgo | Fuente (visto 2026-11-02) | Confianza |
|---|---|---|---|
| Permisos | Token de Página de un usuario con tarea `CREATE_CONTENT`; permisos `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`. | https://developers.facebook.com/docs/video-api/guides/reels-publishing | confirmado |
| Flujo | 3 pasos: `POST /{page-id}/video_reels` con `upload_phase=start` → subir el archivo a `rupload.facebook.com` → `upload_phase=finish` con `video_state=PUBLISHED`. | misma | confirmado |
| Límite | **30 posts publicados por API en 24 h móviles.** | misma | confirmado |
| Specs | MP4, 9:16, 1080x1920 recomendado (mín. 540x960), 24-60 fps fijos, **3 a 90 s** (60 s si va a historia de la Página), H.264/H.265, AAC LC estéreo 48 kHz ≥128 kbps. Tamaño máx.: no especificado en la página. | misma | confirmado |
| Programación | Soportada por API: `video_state=SCHEDULED` + `scheduled_publish_time` (más de 10 min y dentro de 29 días). Un blog de terceros dice lo contrario (que Meta no soporta programar Reels); **la doc oficial prevalece**. | misma ; contradicción: https://bundle.social/blog/facebook-posting-api (2026-08-04) | confirmado (oficial) |
| robots.txt | La API **rechaza archivos alojados en sitios que bloquean por robots.txt** (hay que permitir `facebookexternalhit/1.1`) y URLs de la CDN de Meta. Ojo si el video se sirve desde `uruku.bo`. | misma | confirmado |
| Acceso | Un blog dice que Standard Access sirve solo en Páginas de tu propia cuenta de desarrollador y que producción pide Advanced. Para una Página propia alcanza Standard (ver tabla de acceso arriba). | https://bundle.social/blog/facebook-posting-api | probable |

### 1.5 YouTube Shorts (Data API v3)

| Tema | Hallazgo | Fuente (visto 2026-11-02) | Confianza |
|---|---|---|---|
| Costo de `videos.insert` | **1 unidad en su propio «bucket» de subidas, límite por defecto 100 llamadas/día.** No consume las 10.000 unidades diarias del resto de métodos. Antes: ~1.600 unidades; bajó a ~100 el 2025-12-04; desde 2026-06-01 tiene bucket propio. | https://developers.google.com/youtube/v3/determine_quota_cost ; https://developers.google.com/youtube/v3/revision_history ; https://developers.google.com/youtube/v3/docs/videos/insert | confirmado |
| ¿Proyectos sin verificar quedan privados? | **Contradicción.** (a) Regla de 2020-07-28: videos subidos desde proyectos API *sin verificar* creados después de esa fecha quedaban privados hasta pasar una auditoría de cumplimiento; guías de terceros de 2026 todavía la repiten. (b) La doc actual de `videos.insert` y del recurso `videos` dice textualmente: «Videos uploaded from unverified API projects are not restricted to private viewing mode.» No encontré una entrada en el historial de revisiones que anuncie el cambio. **Más confiable: la doc oficial actual**, pero con una laguna (sin changelog). Hay que **probarlo** con una subida real y leer `privacyStatus`. | doc actual: https://developers.google.com/youtube/v3/docs/videos/insert ; resumen secundario (2026-10-31): https://dev.to/aipredictions_dev/youtube-now-counts-uploads-in-their-own-bucket-100-a-day-one-unit-each-29gm | confirmado (texto actual) / sin confirmar en la práctica |
| Shorts | La doc de `videos.insert` no menciona Shorts: no hay endpoint distinto, se sube un video vertical normal. (La regla de duración/etiqueta de Shorts **no la verifiqué**.) | https://developers.google.com/youtube/v3/docs/videos/insert | no encontrado |
| Tamaño | Máx. 256 GB por archivo. | misma | confirmado |
| OAuth | Con la pantalla de consentimiento en estado «Testing», el refresh token **vence a los 7 días** (hay que re-autorizar cada semana). Para evitarlo hay que pasar la app a «In production» (con scope sensible puede mostrar pantalla de «app no verificada»). | https://developers.google.com/identity/protocols/oauth2#expiration | confirmado |

### 1.6 Canales de WhatsApp

- **No encontré ninguna API oficial de Meta para crear canales ni publicar actualizaciones.** La ayuda oficial describe publicar solo desde la app (admins crean/editan/borran actualizaciones; hasta 16 admins adicionales): https://faq.whatsapp.com/549900560675125 (resultado de búsqueda; no abrí el artículo completo). **Probable** que no exista.
- Proveedores de terceros (Whapi.Cloud, Whinself) ofrecen endpoints para publicar en canales y afirman que la Cloud API oficial «no tiene funciones de canales»: https://whapi.cloud/how-to-automate-whatsapp-channels-api . Estos servicios operan sobre una sesión vinculada tipo WhatsApp Web, no sobre la API oficial: **no oficial, con riesgo de baja del número** (el propio vendedor menciona el riesgo de «perder acceso»). Para URUKU, además, el criterio ya registrado es usar WAHA solo para leer (ver `AGENTS.md` regla 7).

---

## 2. Programar en lote (humano) y herramientas de terceros

### 2.1 Nativas

| Herramienta | Hasta cuándo se puede programar | Fuente (visto 2026-11-02) | Confianza |
|---|---|---|---|
| Meta Business Suite (FB + IG) | **~75 días** hacia adelante según guías de terceros; no encontré el número en la ayuda oficial de Meta. Una página de ayuda de Meta menciona que con un plan «Meta One» se puede programar hasta 365 días. Mínimo ~10-20 min según la fuente. | https://postiz.com/blog/can-you-schedule-facebook-posts ; https://socialbee.com/blog/meta-planner-30-day-post-scheduling-restriction/ ; https://www.meta.com/help/subscriptions/1978812524283985/ | probable |
| TikTok (programador web) | **De 15 min a 10 días** antes de publicar. Para el escritorio hace falta **cuenta Business** («You'll need a Business Account in order to access desktop scheduling»). Hay blogs que dicen 30 días o sin tope: contradicen a TikTok; **prevalece la fuente de TikTok**, que no trae fecha de publicación. | https://ads.tiktok.com/business/en-US/blog/introducing-video-scheduler-now-you-can-plan-tiktoks-in-advance | confirmado (fuente oficial sin fecha) |
| YouTube Studio | Se programa en el paso «Visibilidad» de la subida: «Programar» fecha/hora/zona. Shorts usa el mismo flujo. El video debe seguir privado para cambiar la hora. No hallé el máximo de anticipación en la ayuda oficial. | https://sproutsocial.com/insights/how-to-schedule-youtube-shorts/ (secundaria) | probable |

### 2.2 Herramientas de terceros (el plan más barato que cubre TikTok + IG + FB + YouTube)

| Herramienta | Plan más barato que cubre las 4 | Precio (USD, visto 2026-11-02; cambia) | TikTok: ¿directo o notificación? | Fuente |
|---|---|---|---|---|
| **Metricool** | **Free**: 1 marca, todas las redes salvo LinkedIn y X, **20 posts programados/mes**. Sin límite en Starter. | Free USD 0. Starter desde USD 20/mes (anual) o 25 (mensual) por 5 marcas (no hace falta para una sola marca). | **Ambos**: auto-publicación o notificación (sin auto-publicación, avisa y vos terminás en la app). Posts por API no admiten ubicación visible. | https://metricool.com/pricing/ ; https://help.metricool.com/schedule-and-post-on-tiktok-bkepi |
| **Buffer** | **Free**: hasta 3 canales, 10 posts en cola por canal. Con 4 canales (TikTok, IG, FB, YouTube) hay que pasar a **Essentials: USD 5/canal/mes** (USD 60/canal/año) → **~USD 20/mes por las 4**. | USD 0 / 5 por canal | TikTok (perfiles business): publicación **automática** + recordatorios. IG: auto para cuentas business/creator. YouTube: Shorts con publicación automática. | https://buffer.com/pricing |
| **Later** | Starter: 1 set social (8 perfiles, uno por red), 30 posts por perfil. Sin plan gratis (prueba 14 días). | **USD 18,75/mes facturado anual** | No pude abrir su ayuda (403); no verificado. | https://later.com/pricing/ |

**Más barato real para URUKU:** Metricool Free (USD 0, hasta 20 posts/mes entre todas las redes: con 1 post/día no alcanza, con 20/mes sí) o Buffer Essentials (~USD 20/mes, sin tope práctico). Ambos usan las APIs oficiales *de sus propias apps ya auditadas*, por eso pueden publicar TikTok directo sin el problema de «privado» que tendría una app propia. **Probable** (inferencia: Buffer y Metricool lo dicen en sus páginas; no verifiqué el estado de auditoría de cada uno).

---

## 3. Automatizar el navegador (Playwright/Selenium) sobre TikTok/Instagram

| Tema | Hallazgo | Fuente (visto 2026-11-02) | Confianza |
|---|---|---|---|
| TikTok ToS (actualizado 2025-12-01) | Prohíbe «use automated scripts to collect information from or otherwise interact with the Services» y «bypass any measures we may use to prevent or restrict access». Un script que sube videos por el sitio es «interactuar» con automatización: **está prohibido por los términos**. | https://www.tiktok.com/legal/page/row/terms-of-service/en | confirmado |
| Facebook ToS (vigente 2025-01-01) | «No puedes acceder a datos desde nuestros Productos ni recopilarlos usando medios automatizados (sin nuestro permiso previo)». Esta cláusula habla de **acceder a/recopilar datos**; no dice expresamente «subir contenido». | https://www.facebook.com/terms | confirmado (texto); interpretación sobre subir contenido: mía |
| Instagram ToU | La cláusula equivalente («attempt to create accounts or access or collect information in unauthorized ways... automated means without our express permission») figura en la versión de enero 2025 según fuentes secundarias; **no pude leer la página oficial** (renderizado por JavaScript). | https://help.instagram.com/581066165581870 (no legible por la herramienta) | probable |
| Detección y bajas | Solo blogs de proveedores de scraping/automatización: dicen que Instagram detecta fingerprints por defecto de Selenium/Puppeteer y que aparecen mensajes tipo «We suspect automated behavior on your account». **No encontré evidencia de una causa documentada de baja por subir con Playwright**, ni una declaración de Meta/TikTok sobre ello. Para TikTok: ningún reporte específico de Selenium/Playwright. | p. ej. https://pixelscan.net/blog/instagram-disabled-due-to-data-scraping/ ; https://dev.to/anadil_khalil_b75a8464d97/tiktok-bot-complete-guide-to-automation-safety-growth-strategies-a3g | anecdótico (probable el riesgo, no medido) |
| Riesgo práctico | Se arriesga **la cuenta oficial de la marca** (sin recurso real de apelación si la bajan) a cambio de ahorrar unos minutos por día. Además, el flujo se rompe cada vez que cambia el HTML. | — | opinión fundada en lo anterior |

**Veredicto:** en TikTok es una violación explícita de los términos; en Meta es zona gris en el texto pero con enforcement activo. **No lo recomiendo** para las cuentas oficiales.

---

## 4. Generación de video 9:16 y música

### 4.1 Herramientas

| Opción | Licencia | ¿Sirve para una empresa chica? | Fuente (visto 2026-11-02) | Confianza |
|---|---|---|---|---|
| **ffmpeg** (CLI) | LGPL 2.1+, con partes opcionales GPL 2+ (si se activan, GPL aplica a todo). Sin licencia comercial alternativa. La checklist está pensada para *enlazar* librerías; usar el binario como programa externo no tiene reglas separadas en esa página. Aviso de patentes (H.264) para productos comerciales. | Sí, generando videos propios. No redistribuir ffmpeg dentro de un producto sin revisar. | https://ffmpeg.org/legal.html | confirmado (texto); lectura legal no es asesoramiento |
| **MoviePy** | MIT. | Sí. Usa ffmpeg por debajo. | https://github.com/Zulko/moviepy/blob/master/LICENCE.txt | confirmado |
| **Remotion** | Licencia gratis para: individuos, **empresas con fines de lucro de hasta 3 empleados**, ONG y evaluación. Empresas más grandes necesitan licencia paga. Precios en remotion.pro: «Automators» USD 0,01 por render con mínimo USD 100/mes; «Creators» USD 25/mes por asiento. | Si URUKU tiene ≤3 empleados, gratis (el dueño debe confirmarlo contando a todos los que cuenten como empleados). Si crece, USD 100/mes mínimo para renders automáticos. | https://github.com/remotion-dev/remotion/blob/main/LICENSE.md ; https://www.remotion.pro/license | confirmado (condiciones); precios son de una lectura resumida |

**Para slideshow 9:16 con texto** alcanza ffmpeg/MoviePy (sin riesgo de licencia). Remotion da mejores animaciones de texto en React, pero agrega condición de licencia.

### 4.2 Música

| Tema | Hallazgo | Fuente (visto 2026-11-02) | Confianza |
|---|---|---|---|
| TikTok y música propia por API | En Direct Post el usuario tiene que ver la declaración «By posting, you agree to TikTok's Music Usage Confirmation». Esa confirmación dice que el video no tiene música con copyright o que tenés todas las licencias pagas. | https://developers.tiktok.com/doc/content-sharing-guidelines ; https://www.tiktok.com/legal/page/global/music-usage-confirmation/en | confirmado |
| Cuentas business | TikTok recomienda usar solo la **Commercial Music Library (CML)** para contenido comercial. | https://support.tiktok.com/en/business-and-creator/creator-and-business-accounts/commercial-use-of-music-on-tiktok | confirmado |
| CML por API | **No encontré** un parámetro oficial en la Content Posting API para elegir un track de la CML. Un proveedor dice que el audio en tendencia no está disponible por API y que se usa CML en la app o audio con licencia ya mezclado en el archivo. Metricool documenta que un video posteado por API puede publicarse **sin sonido** si TikTok lo valida después. | proveedores: https://bundle.social/tiktok-commercial-music-library ; https://help.metricool.com/why-was-my-tiktok-video-posted-without-sound-ao9cw | no encontrado (oficial) / probable (resto) |
| Instagram | Por API la música de la biblioteca no se puede elegir; solo etiquetar audio original. | https://developers.facebook.com/documentation/instagram-platform/instagram-graph-api/reference/ig-user/media | confirmado |
| Música libre de derechos | **Pixabay Content License** (música incluida): uso gratis, sin atribución, modificar permitido; prohíbe vender el contenido tal cual, uso engañoso/ilegal y usar el contenido como marca. Los derechos de terceros siguen siendo responsabilidad tuya. No habla de Content ID. | https://pixabay.com/service/license-summary/ | confirmado (resumen de licencia) |
| YouTube Audio Library | La licencia es **por pista**; la ayuda oficial se centra en uso dentro de YouTube; algunas pistas piden atribución (CC-BY). La protección contra reclamos no viaja a TikTok/Instagram. | resumen secundario: https://usethirdchair.com/blog/can-you-use-youtube-audio-library-music-on-instagram | probable |
| Música de CapCut | Su licencia «Commercial Sounds» se limita a CapCut/TikTok/TikTok for Business: no sirve para subir a YouTube/IG. | resumen en la búsqueda; no abrí la licencia | probable |

**Práctica segura:** música con licencia comercial explícita (guardar prueba de descarga y la licencia de cada pista) mezclada en el archivo; o publicar sin música y que el humano agregue sonido de la CML al finalizar en la app (en TikTok vía borrador).

---

## 5. Aparecer en ChatGPT, Perplexity y Google AI Overviews

### 5.1 Crawlers de OpenAI

Fuente única de este bloque: https://developers.openai.com/api/docs/bots (visto 2026-11-02). **Confirmado.**

| Bot | Para qué sirve | robots.txt |
|---|---|---|
| **OAI-SearchBot** | Mostrar sitios en las funciones de búsqueda de ChatGPT. | Permitirlo = poder aparecer. Si lo bloqueás, no aparecés en respuestas de ChatGPT search (solo como link de navegación). Tarda ~24 h en ajustarse tras cambiar robots.txt. IPs: https://openai.com/searchbot.json |
| **GPTBot** | Rastrea contenido que puede usarse para **entrenar** modelos. | Bloquearlo = «no usar para entrenamiento». **No afecta** la aparición en búsqueda. |
| **ChatGPT-User** | Acciones iniciadas por un usuario (visita una página para responder, GPT Actions). No rastrea de forma automática. | Las reglas de robots.txt **pueden no aplicar** (lo inicia un humano). No determina si salís en búsqueda. |

Las tres configuraciones son independientes: se puede permitir `OAI-SearchBot` y bloquear `GPTBot`.

### 5.2 ¿Depende de Bing?

- **Confirmado:** OpenAI dijo en el lanzamiento (2024) que ChatGPT search usa «third-party search providers» y contenido de socios, **sin nombrar a Bing** en ese anuncio; la ayuda de OpenAI para Enterprise/Edu sí dice que puede compartir consultas desagregadas con **Bing**. Resultado de búsqueda sobre https://help.openai.com/en/articles/10093903-chatgpt-search-for-enterprise-and-edu ; no pude abrir la página directamente (403). Nivel: **probable**.
- **Probable (blogs de SEO):** el mix es Bing + índice propio de OpenAI (OAI-SearchBot); la proporción no es pública. https://geotoolbox.ai/blog/how-chatgpt-search-works
- **Consecuencia práctica:** estar bien indexado en Bing y no bloquear a OAI-SearchBot son condiciones razonables, sin garantía.

### 5.3 Bing Webmaster Tools + IndexNow

| Tema | Hallazgo | Fuente | Confianza |
|---|---|---|---|
| IndexNow | Protocolo para avisar a buscadores cuando una URL se crea/actualiza/borra. Se prueba propiedad con un archivo `{key}.txt` en la raíz; hasta 10.000 URLs por POST. Respuesta 200 = recibido, **no** = indexado. | https://www.indexnow.org/documentation (visto 2026-11-02) | confirmado |
| Quién lo soporta | Microsoft Bing, Naver, Seznam.cz, Yandex, Yep; lo que se envía a uno se comparte con los demás. **Google no aparece** como participante. | https://www.indexnow.org/faq (resultado de búsqueda) | confirmado (participantes); «Google no» es por ausencia de la lista |
| Cada buscador decide | Enviar la URL no obliga a indexarla. | indexnow.org/faq | confirmado |
| Vínculo IndexNow→ChatGPT | Se infiere (ChatGPT usa Bing); **no hay confirmación oficial de OpenAI o Microsoft**. | — | no encontrado |

### 5.4 `utm_source=chatgpt.com`

OpenAI: «ChatGPT automatically includes the UTM parameter `utm_source=chatgpt.com` in referral URLs», lo que permite medir el tráfico en tus analíticas; quienes permiten a OAI-SearchBot pueden hacer ese seguimiento. Fuente: FAQ para publishers https://help.openai.com/en/articles/12627856 (la cita sale del resultado de búsqueda; la página dio 403 al abrirla). **Confirmado** (OpenAI lo agrega a los links **salientes de ChatGPT hacia tu sitio**; no hay que ponerlo vos en tus links). Para URUKU: en las analíticas, filtrar por `utm_source=chatgpt.com`.

### 5.5 Perplexity y Google AI Overviews

| Sistema | Hallazgo | Fuente (visto 2026-11-02) | Confianza |
|---|---|---|---|
| PerplexityBot | Sirve para mostrar y enlazar sitios en los resultados de Perplexity; «no se usa para entrenar modelos». Permitirlo en robots.txt y sus rangos de IP. | https://docs.perplexity.ai/guides/bots | confirmado |
| Perplexity-User | Lo dispara una persona al hacer una pregunta; en general **ignora robots.txt**; no rastrea ni recolecta para entrenamiento. | misma | confirmado |
| Google AI Overviews / AI Mode | La página debe estar **indexada y ser elegible para mostrar snippet**. «No special schema.org structured data» necesario; no hay «requisitos adicionales» ni optimizaciones especiales. Si usás datos estructurados, deben coincidir con el texto visible. **La inclusión no está garantizada.** Controles: `nosnippet`, `data-nosnippet`, `max-snippet`, `noindex`. | https://developers.google.com/search/docs/appearance/ai-features | confirmado |

**Qué hacer en la práctica (sin prometer nada):** robots.txt permitiendo `OAI-SearchBot` y `PerplexityBot`; sitemap; páginas de comercio server-rendered (hoy la ficha es `force-dynamic`; pasarla a ISR es la tarea FA de `visibilidad-buscadores-ia.md`); registrar `uruku.bo` en Bing Webmaster Tools y Google Search Console; IndexNow al publicar/aprobar; JSON-LD `LocalBusiness` correcto (ayuda a la coherencia, no es requisito de Google); contenido textual claro (nombre, rubro, zona, horario).

---

## 6. Qué conviene

1. **Pipeline del agente en la PC, que prepara pero no publica**: genera videos 9:16 (ffmpeg o MoviePy) e imágenes JPEG, con textos y pies de foto, en una carpeta por día/lote (`/lote-AAAA-MM-DD/`) con un `manifest.json` (archivo, texto, hashtags, fecha sugerida). Música solo con licencia comercial guardada, o sin música.
2. **Instagram + Facebook: API oficial con app propia en modo desarrollo** (vos como admin; Standard Access) es la única automatización que realmente funciona para un negocio chico y sin auditoría. Alternativa más simple: **Meta Business Suite** programando el lote a mano (~75 días de anticipación según terceros).
3. **TikTok: no usar API propia para publicar en público** (sin auditoría = privado; el rechazo por «uso interno» es probable). Opciones: (a) **programador web de TikTok** (cuenta Business, hasta 10 días); (b) un **scheduler de terceros ya auditado** (Metricool Free o Buffer ~USD 20/mes) que publica directo o avisa para terminar en la app.
4. **YouTube Shorts: API oficial viable** (100 subidas/día de cupo), pero primero probar con una subida real que no quede privada, y pasar el proyecto a «In production» para que el token no venza a los 7 días. Si no, YouTube Studio programado.
5. **No hacer** automatización de navegador sobre TikTok/Instagram (prohibido en los términos de TikTok; riesgo para la cuenta oficial) ni publicar en el canal de WhatsApp por APIs no oficiales.
6. **Búsqueda con IA:** lo anterior de 5.5. Medirlo con `utm_source=chatgpt.com` y Search Console/Bing Webmaster.

## 7. A verificar por el dueño (requiere acceso a cuentas)

| # | Qué | Dónde |
|---|---|---|
| 1 | Que la cuenta de Instagram sea **profesional** (Business o Creator) y esté vinculada a la Página de Facebook de URUKU; y si la Página pide **Page Publishing Authorization**. | Instagram › Configuración › Cuenta; Página › Configuración |
| 2 | Que la cuenta de TikTok sea **Business** y mirar si aparece el botón «Programar» en la subida web, y el máximo real de días. | tiktok.com/upload |
| 3 | Crear una app en developers.facebook.com con vos como admin y comprobar que publicar un Reel de prueba en la cuenta propia funciona **sin App Review** (modo desarrollo). | developers.facebook.com › Mis apps |
| 4 | Cuántas personas cuentan como «empleados» de URUKU (≤3 permite Remotion gratis). | decisión interna |
| 5 | Crear proyecto en Google Cloud con YouTube Data API v3, subir un video de prueba por API y leer `status.privacyStatus`; ver la cuota en la consola. | console.cloud.google.com |
| 6 | Qué plazo máximo de programación muestran hoy Meta Business Suite y YouTube Studio en las cuentas reales. | Meta Business Suite › Planner; YouTube Studio › Subir |
| 7 | Si el plan Free de Metricool (20 posts/mes) alcanza o si conviene Buffer Essentials; ver precio vigente en moneda local. | metricool.com/pricing , buffer.com/pricing |
| 8 | Registrar `uruku.bo` en Bing Webmaster Tools y Google Search Console (y la clave IndexNow), y revisar el `robots.txt` productivo. | webmaster.bing.com ; search.google.com/search-console |
| 9 | Si el contenido incluye fotos/nombres de comercios: confirmar el permiso de cada comercio para usar su imagen en las redes de URUKU (no es tema de plataforma, es de relación con el comercio). | acuerdo con comercios |

## 8. Lo que no pude confirmar

- Plazo oficial de la auditoría de TikTok (no publicado) y si aceptan apps de «solo mi cuenta» (solo el relato de un dev del 2026-10-20).
- Tope de anticipación oficial de Meta Business Suite y de YouTube Studio (solo terceros).
- Texto oficial de los ToU de Instagram (página no legible por herramienta) y ayuda de WhatsApp Channels completa.
- Que una subida real por la API de YouTube desde un proyecto sin verificar no quede privada (la doc lo dice; falta prueba).
- Parámetro oficial para usar la Commercial Music Library desde la Content Posting API.
- Estado de auditoría de Buffer/Metricool/Later en TikTok y precios de Later fuera de USD anual; página de ayuda de Later (403).
- Vínculo exacto Bing→ChatGPT search y efecto de IndexNow sobre ChatGPT.
