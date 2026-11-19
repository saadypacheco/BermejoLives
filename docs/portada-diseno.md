# Portada de diseño para la ficha pública

Pedido del dueño (19/11/2026): algunos comercios (no todos) tienen que mostrar en su ficha pública una portada
con diseño de publicidad, armada a partir de la foto del local. Se hace desde el panel, cuando se analiza el
comercio.

## Qué se arma

Una imagen apaisada de **1600 × 1000** (JPEG) con:

- la foto de portada del comercio recortada para llenar el cuadro (si tiene `portada_pos`, ese es el centro vertical);
- una franja abajo, oscura y degradada, con el **nombre del comercio** (Poppins Bold, hasta 2 renglones, achica
  la letra si no entra), y debajo el **rubro principal** y la **ciudad** (Poppins Medium);
- el logo blanco de URUKU chico, en una esquina.

Todo el texto sale de la base (`comercios`, `rubros`, `ciudades`): **ningún texto de la imagen lo escribe un
modelo de IA**. Sin emojis (la fuente no los tiene y el manual los prohíbe).

## Dos formas de armarla

| | Plantilla | Mejorar con IA |
|---|---|---|
| Qué hace | La foto tal cual + el diseño | Gemini mejora la foto (luz, nitidez, encuadre) y después se le pone el MISMO diseño |
| Costo | 0 (Pillow en el backend) | ~US$ 0,034 por imagen (`gemini-3.1-flash-lite-image`, precio del 19/11/2026) |
| Interruptor | — | `gemini_portada_diseno` en `cost_switches`, **apagado** por defecto |

El pedido a Gemini prohíbe agregar, quitar o cambiar objetos, carteles, productos o texto: sólo luz, color,
nitidez y encuadre. Igual una persona mira la propuesta antes de usarla.

## Flujo

1. En el panel (análisis del comercio) → «Armar portada de diseño» → **Plantilla (gratis)** o **Mejorar con IA**.
2. El backend arma la imagen, la guarda en el disco de fotos y la deja como **propuesta**
   (`comercios.portada_diseno_propuesta_url`, privada). El panel la muestra.
3. «Usar en la ficha» → pasa a `comercios.portada_diseno_url` (pública) y la propuesta queda vacía.
   «Descartar» → la propuesta queda vacía.
4. «Volver a la foto original» → `portada_diseno_url` queda vacía.
5. **Si cambia la foto de portada** (subir una nueva o elegir otra de la galería, desde cualquier perfil), las dos
   columnas de diseño quedan vacías: el diseño era de la foto anterior.

Nada se publica solo: la propuesta sólo la ve el panel.

## En la ficha pública

- Si hay `portada_diseno_url`, va en el lugar principal de la galería (sin `portada_pos`: la imagen ya viene
  encuadrada) y la foto original pasa a ser la primera miniatura de la galería, para que se siga viendo.
- Los listados, el buscador y el mapa siguen usando `portada_thumb_url` (la foto real): en una miniatura el texto
  no se lee.

## Datos (migración 0200)

- `comercios.portada_diseno_url text` → **pública** (`grant select (portada_diseno_url)` a anon y authenticated,
  regla 11) y en `COLUMNAS_COMERCIO`.
- `comercios.portada_diseno_propuesta_url text` → privada (en `PRIVADAS_EXTRA`).

## API (permiso `comercios.editar`)

| Método | Ruta | Qué hace |
|---|---|---|
| POST | `/admin/comercio/{id}/portada-diseno?ia=false` | Arma la propuesta. 400 sin foto de portada; 409 con `ia=true` y el interruptor apagado; 503 sin `GEMINI_API_KEY` |
| PUT | `/admin/comercio/{id}/portada-diseno` | Usa la propuesta en la ficha. 400 si no hay propuesta |
| DELETE | `/admin/comercio/{id}/portada-diseno/propuesta` | Descarta la propuesta |
| DELETE | `/admin/comercio/{id}/portada-diseno` | Vuelve a la foto original |

Las cuatro devuelven `{portada_diseno_url, portada_diseno_propuesta_url}`.
