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

## Cómo se arma

**Plantilla, gratis (Pillow en el backend).** La foto pasa primero por una **mejora automática de luz, color y
nitidez, sin IA** (suave: autocontraste mezclado con la foto, sube el brillo sólo si la foto es oscura, color
+12 %, nitidez +30 %; una foto ya clara no se toca) y después se le pone el diseño. Costo: 0.

## Flujo

1. En el panel (análisis del comercio) → «Armar portada de diseño».
2. El backend arma la imagen, la guarda en el disco de fotos y la deja como **propuesta**
   (`comercios.portada_diseno_propuesta_url`, privada). El panel la muestra.
3. «Usar en la ficha» → pasa a `comercios.portada_diseno_url` (pública) y la propuesta queda vacía.
   «Descartar» → la propuesta queda vacía.
4. «Volver a la foto original» → `portada_diseno_url` queda vacía.
5. **Si cambia la foto de portada** (subir una nueva o elegir otra de la galería, desde cualquier perfil), las dos
   columnas de diseño quedan vacías: el diseño era de la foto anterior.
6. **Si cambia el nombre, el rubro principal o la ciudad** del comercio (desde el panel, Mi comercio, el agente, la
   IA que clasifica, el rubro automático o lo que completa un importado), las dos columnas también quedan vacías:
   el diseño tiene esos textos dibujados y quedó vencido. Guardar el mismo valor no vence nada. Lo hace el
   repositorio (`diseno_vencido`), así que ningún camino se lo salta. Los archivos del disco se sueltan salvo
   cuando el que cambia es el **agente** (que no borra nada: `docs/portada-y-permisos.md`).

Nada se publica solo: la propuesta no se muestra en la ficha hasta que una persona aprieta «Usar en la ficha».

**Privacidad de la propuesta.** «Privada» quiere decir que la columna `portada_diseno_propuesta_url` no se da a anon
(ni la lee el sitio público) y que las respuestas al agente y a Mi comercio no la traen. El **archivo**, en cambio, se
sirve por `/fotos/<slug>/diseno-<token>.jpg` como cualquier foto, sin login: lo protege sólo que el nombre lleva 64 bits
al azar y no se lista en ningún lado. Quien tenga el link lo ve.

## Límites (el backend corre con un solo worker)

- La foto de portada se **recorta antes de escalar**: la salida es siempre 1600 × 1000 y no hay intermedios enormes.
- Se rechaza (400) una portada con el lado menor < 200 px o de proporción mayor a 4:1: «La foto de portada es muy
  chica o muy angosta para armar el diseño».
- `portada_pos` se aplica como el CSS `object-position: center <pos>%`: el recorte arranca en `pos %` del tramo que
  sobra (no queda centrado en `pos`). Sin `pos`, el centro.
- El nombre se corta a 120 caracteres antes de dibujarlo; en el alta anónima, Mi comercio y el panel el nombre admite
  hasta 200.
- Se arma de a **una** portada por vez: si hay otra en curso, 409 «Ya se está armando otra portada, probá en unos
  segundos».
- Si mientras se armaba cambió la foto de portada (o el nombre, rubro, ciudad o recorte), el POST devuelve 409 y el
  archivo recién creado se borra.

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
| POST | `/admin/comercio/{id}/portada-diseno` | Arma la propuesta. 400 sin foto de portada, o si es muy chica o angosta; 409 si hay otra en curso o la foto cambió mientras se armaba |
| PUT | `/admin/comercio/{id}/portada-diseno` | Usa la propuesta en la ficha. 400 si no hay propuesta |
| DELETE | `/admin/comercio/{id}/portada-diseno/propuesta` | Descarta la propuesta |
| DELETE | `/admin/comercio/{id}/portada-diseno` | Vuelve a la foto original |

Las cuatro devuelven `{portada_diseno_url, portada_diseno_propuesta_url}`.

Mejorar con IA (Gemini, ~US$ 0,034 por imagen) quedó afuera el 19/11/2026 por costo: son decenas de miles de comercios. Si se retoma, va detrás de un interruptor de `cost_switches` apagado.
