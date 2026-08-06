# Estrategia: captación de comercios + contenido + dominio (2026-06-30)

> Documento de discusión. Prioridad #1: **cerrar la página del agente de campo**
> (`/publicar`) para empezar a llenar el mapa. Todo lo demás (home para
> compradores, ficha rica) viene después.

## 1. Prioridad — cerrar la página del agente de campo (`/publicar`)

Objetivo: dejar el flujo de carga **listo para producción** y salir a recorrer
comercios. Qué falta para "cerrarla":

### 1.1 Performance de la foto (🔴 crítico — diagnóstico hecho)
Causa raíz: **no hay compresión del lado del navegador**. El celular sube la
foto full-res (backend acepta hasta 15 MB) y recién el backend la reduce a
1600px/JPEG82. Con internet malo, subir 5-10 MB tarda un montón.
- **Fix A (upload):** comprimir/resize en el navegador con `<canvas>` antes del
  POST (target ~1600px lado largo, JPEG ~0.8). Una foto de 6 MB → ~250 KB.
  Aplica a `/publicar`, al re-subir foto (`/campo/mis-comercios/{id}/foto`) y a
  la foto de "Mi comercio". *Es el arreglo de mayor impacto.*
- **Fix B (serve):** generar un **thumbnail ~400px** para tarjetas/mapa (hoy se
  sirve el 1600px para todo) + `Cache-Control` largo en las fotos estáticas.
- Backend ya resize/reorienta bien (`services/imagenes.py`), no se toca eso.

### 1.2 Subida de video (1 o más por comercio)
Hoy solo se guarda un **link externo** (`video_url`/`tiktok_url`), no se puede
**subir un archivo**. Se necesita subir video propio — es el **material crudo**
para el contenido de los próximos 6 meses (ver sección 2).
Decisiones a tomar:
- **Dónde viven los videos:** disco del backend (mismo patrón que fotos) es lo
  más simple, pero los videos pesan. Definir **límite de tamaño/duración**
  (ej. 60 s, 50 MB) y si se comprime server-side.
- **Subida con internet malo:** el video no se puede comprimir en el navegador
  fácil como la foto. Mitigaciones: cap de duración, **barra de progreso**,
  reintento, y sugerir wifi para el video. Que **no bloquee** el alta (la foto
  y los datos se guardan aunque el video falle/quede pendiente).
- **Múltiples videos:** tabla `comercio_videos` (mismo patrón que se usará para
  la galería multi-foto de la ficha).
- **Uso:** material para redes (sección 2) y, opcional, reproductor en la ficha.

### 1.3 Robustez del flujo
- **Progreso + reintento** en subidas (foto y video) — hoy es "todo o nada".
- Confirmar el **flujo end-to-end** en prod: la transcripción de audio (`¿qué
  vende?`) puede estar rota si `OPENAI_API_KEY` es placeholder (ver pendientes
  §0) — que el fallback a texto manual ande siempre.
- Feedback claro de error (no un genérico).

## 2. Video → contenido con IA para las redes de Encontralo

Idea: el agente graba, la **IA genera el contenido** para las redes de
Encontralo (TikTok / IG / FB / YouTube Shorts).

- **Captura:** el video se sube en el alta (§1.2) junto con la metadata del
  comercio (nombre, rubro, oferta, **URL de la ficha** `encontralo.store/comercios/{slug}`, y un **QR** a esa ficha).
- **Pipeline de contenido (fase aparte, no bloquea el alta):** a partir del
  video + metadata, la IA arma **caption + hook + hashtags + CTA a la ficha**.
  Puede ser un workflow/script separado (no dentro de la app), corriendo sobre
  la cola de videos subidos.
- **El video siempre lleva a la ficha** (CTA + link en bio + QR). Ese es el
  puente redes → Encontralo.

## 3. El flywheel de crecimiento (estrategia del usuario)

```
Visitás un comercio → grabás video 30-60s → publicás en TikTok/IG/FB/YT Shorts
      → el video dirige a la ficha en Encontralo
      → el usuario descubre otros negocios y ofertas
      → más comercios quieren aparecer (ven que genera visitas)
      → más material para publicar → repetís
```

Qué **habilita** cada paso (y qué falta):
- "grabás video" → **§1.2 subida de video**.
- "dirige a la ficha" → ficha atractiva + **cross-discovery** ("otros negocios
  cerca / ofertas") — se conecta con los cambios de home y el rediseño de ficha.
- "más comercios quieren aparecer porque ven visitas" → **panel de métricas
  para el comercio** (contactos/visitas reales). Ya es pendiente §2.6 del
  backlog; es el **argumento de venta más fuerte** y conviene construirlo
  temprano.

## 4. Dominio — `.store` vs `.com.bo` / `.com.ar`

- El nombre **Encontralo** está bien; el riesgo es el TLD **`.store`**
  (memorabilidad: la gente no lo recuerda / lo escribe como `.com`).
- **Recomendación:** registrar **`encontralo.com.bo`** y **`encontralo.com.ar`**
  (y `encontralo.com` si está libre), y servirlos todos al mismo sitio. La
  infra ya soporta **multi-host** (Traefik: `Host(A) || Host(B) || ...` + un
  `DOMAIN_ALT`), así que sumar dominios es: registrar → DNS al IP del VPS →
  agregar al rule de Traefik + certresolver. Bajo esfuerzo, alto retorno.
- **Caveat de registro:** `.com.bo` y `.com.ar` piden trámite/presencia local
  (NIC Bolivia / NIC Argentina) — no es compra instantánea como un `.com`.
- **⚠️ Secuencia crítica (no obvio):** **decidir el dominio primario ANTES de
  la campaña de instalaciones pagas.** La PWA se instala **por origen
  (dominio)**: si arrancás a pagar agentes por instalar sobre `encontralo.store`
  y después migrás a `encontralo.com.bo`, esas instalaciones quedan atadas a un
  origen que vas a abandonar (o hay que re-instalar). Esto conecta directo con
  el pendiente "agentes + incentivo por instalación": **primero el dominio
  final, después la campaña.**

## Orden sugerido
1. **Foto: compresión client-side (§1.1 Fix A)** — arreglo rápido y crítico,
   destraba el dolor del agente ya.
2. **Subida de video (§1.2)** — decidir storage/límites y construir.
3. **Robustez de subidas + confirmar flujo end-to-end (§1.3)**.
4. **Definir dominio final (§4)** antes de escalar captación.
5. Recién ahí: home para compradores + rediseño de ficha (flywheel §3).
