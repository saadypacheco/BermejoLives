# Moderación de contenido — humana + IA

> Todo lo que **envía** un comercio/creador se revisa **antes de publicarse**. Dos vías
> que conviven: **revisión humana** (una persona en un panel) y **revisión con IA** (un
> botón, para cuando el volumen es demasiado). Idea del dueño (2026-08-15).

## Qué YA existe (construir encima de esto)
- **Cola de moderación** (`backend/app/api/moderacion.py`): lista `pendientes` y permite
  **aprobar / rechazar / pedir cambios**. Hoy protegida por `require_admin`.
- **`confiable`**: comercio confiable publica directo (`estado='aprobado'`); no confiable
  → va a la cola (`estado='pendiente'`).
- **Reclamos**: cola de comentarios/quejas con responder.
- **IA (Gemini)** en `backend/app/services/clasificador.py` (`clasificar`, `generar_texto_comercio`,
  `sugerir_rubros`). El mismo cliente sirve para **moderar** (nueva función `moderar()`).

## Qué se agrega
### 1. Revisión humana ampliada
- El panel de moderación accesible también al **publicador** (o un rol nuevo `moderador`),
  no solo admin. Aprobar / rechazar / editar por ítem, con motivo.

### 2. Revisión con IA (botón) — para volumen
- Servicio `moderar_ia(contenido)` con Gemini → devuelve `{veredicto: aprobar|rechazar|dudoso,
  motivo, confianza}`.
- **Modo asistido** (recomendado al inicio): la IA **pre-clasifica**, el humano confirma con 1
  clic. Botón **"Revisar con IA"** por ítem y **"Revisar pendientes con IA"** (lote).
- **Modo automático** (cuando el volumen crezca): la IA aprueba/rechaza sola **arriba de un
  umbral de confianza**; los `dudoso` caen a revisión humana. Toggle de config.

### 3. Qué se revisa (a confirmar)
Alta de comercio (autoregistro), **ofertas/publicaciones**, **productos de la tienda**,
**fotos/videos**, y **reclamos**. Nota: el **comprador** que se registra por WhatsApp **no**
necesita revisión de contenido (es un usuario); si en el futuro sube **reseñas/comentarios**,
eso sí entra a la cola.

## Qué chequea la IA
Contenido inapropiado/ofensivo, spam, datos falsos, calidad mínima (foto/título legibles),
**categoría correcta**, coherencia precio/producto. Devuelve **motivo** para que el humano
entienda por qué (no una caja negra).

## Cómo encaja (esfuerzo)
- **Backend**: ampliar acceso de `moderacion.py` a publicador/moderador + `moderar()` en el
  servicio de IA + endpoints `POST /moderacion/{id}/ia` y `POST /moderacion/ia/lote`.
- **Frontend**: en el panel, botón "Revisar con IA" (ítem y lote) + badge del veredicto de IA
  + config de umbral/modo. Reusa la cola que ya existe.
- **Config**: `GEMINI_API_KEY` (ya contemplado), umbral de auto-aprobación, modo asistido/automático.

## A definir con el dueño
1. **Qué tipos** entran a la cola (todos los de arriba, o un subconjunto).
2. **Quién modera**: el **publicador** alcanza, o creamos un rol **`moderador`** aparte.
3. **IA**: arranca en **asistido** (IA sugiere, humano confirma) y pasa a **automático** cuando
   el volumen lo pida — ¿ok ese orden?
