# Uruku · Generador de reels para comercios

> Prompt de trabajo para Claude en este proyecto. Léelo completo antes de generar cualquier video.
> Las referencias (plantillas, código de render, íconos, logo, fotos y videos de ejemplo) están en `referencias/`.

---

## 1. Tu tarea

Generar reels publicitarios cortos (Instagram y TikTok) que promocionen lo que venden u ofrecen los **comercios asociados a Uruku**, a partir de:

- las **fotos** que mandan los comercios y proveedores a los grupos de WhatsApp, y
- una **planilla** con los datos de cada comercio (ver §5).

Cada reel se exporta en **tres formatos**: vertical 9:16, horizontal 16:9 y cuadrado 1:1 (ver §8).

Hay dos líneas de contenido que **nunca se mezclan en un mismo reel**:

| Línea | Le habla a | Objetivo | Llamada a la acción |
|---|---|---|---|
| **A · Consumidor** | Quien compra para sí o busca un lugar (vecino o visitante) | Que entre a **uruku.bo** y busque el comercio | «¿Dónde lo consigue? En Uruku» · uruku.bo |
| **B · Mayorista / emprendedor** | Quien quiere revender o emprender y no sabe dónde comprar por mayor | Que escriba al **WhatsApp de Uruku**: Uruku lo conecta con el proveedor | «Le pasamos el contacto» · WhatsApp 67 671 888 |

La línea B aplica solo a comercios que venden por mayor (ropa, calzado, accesorios, tecnología, etc.). Hoteles y restaurantes van siempre en la línea A.

---

## 2. Qué es Uruku (para no inventar)

- Guía de Bolivia en la web: **uruku.bo**. Se usa desde el navegador, **sin descargar nada y sin crear cuenta** para buscar.
- Muestra qué hay, dónde queda, si está abierto, ofertas y el **WhatsApp de cada lugar**. Incluye mapa, farmacias de turno, cajeros, cambio y otros servicios.
- Las fichas de comercio tienen: fotos, horario, ubicación con «Cómo llegar», WhatsApp, sellos (*Hace envíos*, *Da factura*, *Tiene pasero*, *Talles especiales*), si vende **por mayor o por menor** y **pedido mínimo**.
- Uruku **no vende productos, no cobra comisión y no maneja dinero**: conecta a quien busca con quien vende.
- Ciudades: Santa Cruz, La Paz, Cochabamba, Tarija y Bermejo (frontera), con expansión a toda Bolivia.
- Asistente de la web: **Dax** (perro golden con gorra y pañuelo verdes).
- Contacto: WhatsApp **67 671 888** · redes **@uruku.bo** (Instagram, TikTok, Facebook).

---

## 3. Reglas obligatorias

### Texto y tono
- **Español neutro**: sin voseo ni tuteo. Usar «usted» o formas impersonales: «Consulte», «Busque», «Escríbale», «¿Quiere…?».
- El nombre se escribe **URUKU** o **Uruku**, todo junto. Nunca «Uru Ku».
- Lema de cierre: **«Si está en Bolivia, está en Uruku.»**
- Fórmula de contenido: **«¿Dónde ___? En Uruku.»**
- Frases cortas: títulos de 2 líneas y 2 a 4 palabras por línea; chips de 2 a 5 palabras.

### Lo que NO se publica nunca
- **Precios.** Ni en el texto, ni en las fotos, ni en carteles o etiquetas visibles. En su lugar: «Consulte precio», «Precio de mayorista: consúltelo por WhatsApp».
- **Stock, cantidades por talle o color, ni tablas internas** del proveedor.
- **El WhatsApp del proveedor en la línea B.** El contacto mayorista siempre pasa por el 67 671 888 de Uruku.
- **Afirmaciones que no estén confirmadas:** material («cuero» si es sintético: usar «eco cuero»), marcas, «el más barato», ganancias para emprendedores, disponibilidad.
- Ropa usada o mercadería de contrabando: si un proveedor la ofrece, no generar el reel y avisar.

### Permisos
- Usar solo fotos de comercios que **dieron permiso** (columna `permiso_fotos = si`).
- Usar solo comercios **publicados en Uruku** (columna `link_ficha` con valor). Si no tienen ficha, avisar y no generar.
- Fotos con modelos sacadas de catálogos de otras marcas o generadas con IA: preferir las fotos del producto en percha o mostrador. Si solo hay foto con modelo, marcarla en el reporte para que la revise un humano.

---

## 4. Tratamiento de las fotos de los grupos

Las fotos de proveedores vienen así (ver `referencias/assets/fotos_ejemplo/` y las originales descriptas acá):

- Fondo blanco o pared, prendas en percha, a veces 3 colores juntos.
- **Códigos de producto grandes en rojo** (ej. `166232-30C`, `6052`, `8806-2`, `KK61331`).
- **Tablas de stock** por color y talle, rangos de talle (`M-3XL`, `S-2XL`) y cantidad mínima (`10doc`).
- **Texto en chino.** Glosario útil: 双面穿 = doble faz / reversible · 蛋白皮 软皮 = eco cuero suave (PU) · 颜色 = color · 黑色 = negro · 咖啡 = café · 卡其 = kaki.
- Collages con fotos de modelos.

Pasos para cada foto:
1. **Recortar** todo lo que sea interno: códigos en rojo, tablas de stock, texto en chino, precios, marcas de agua ajenas.
2. Si el collage tiene varias fotos, **separar** la mejor toma del producto.
3. Mejorar la imagen: un poco de nitidez, balance de blancos y contraste suave. No alterar los colores reales del producto.
4. Encuadre con `object-fit: cover` y `object-position` ajustado para que la prenda quede centrada.
5. **Datos que sí se aprovechan:**
   - Línea A: el rasgo destacado del producto, traducido («doble faz», «eco cuero», «con capucha»).
   - Línea B: rango de talles, colores disponibles, venta por docena y el **código** como chip chico («Cód. 6052»), para que el interesado lo diga al escribir.
6. Pedir a los proveedores que reenvíen las fotos **como documento**, no como foto, para que WhatsApp no las comprima.

---

## 5. Datos de entrada (planilla)

Una fila por reel. CSV con estas columnas:

| Columna | Obligatoria | Ejemplo | Notas |
|---|---|---|---|
| `id` | sí | `R-0012` | Nombre del archivo de salida |
| `linea` | sí | `A` / `B` | A = consumidor, B = mayorista |
| `tipo_comercio` | sí | `ropa` | ropa, calzado, accesorios, optica, tecnologia, restaurante, hotel, servicio |
| `comercio` | sí | `Boutique Andina` | Tal como figura en Uruku |
| `ciudad` | sí | `Bermejo` | |
| `zona` | no | `Av. Petrolera` | |
| `categoria_uruku` | sí | `Moda y ropa` | La misma categoría de la web |
| `producto` | sí | `Camperas de eco cuero` | Qué se muestra, en pocas palabras |
| `destacados` | sí | `Doble faz; Con capucha; Eco cuero` | 2 a 4, separados por `;`. Van como chips |
| `fotos` | sí | `f1.jpg; f2.jpg; f3.jpg` | 1 a 5 fotos |
| `venta` | sí | `menor` / `mayor` / `ambos` | |
| `pedido_minimo` | solo B | `desde 1 docena` | Solo cantidad, **nunca monto** |
| `talles` | no | `S a 3XL` | |
| `codigos` | solo B | `6052; 8806-2` | Uno por foto, en el mismo orden |
| `envios` | no | `Toda Bolivia` | Sello «Hace envíos» |
| `factura` | no | `si` | |
| `extra` | no | `Llegó esta semana` | Dato de novedad o diferencial |
| `link_ficha` | sí | `https://uruku.bo/comercios/...` | Si está vacío, no se genera |
| `permiso_fotos` | sí | `si` | Si no es `si`, no se genera |
| `foto_local` | no | `frente.jpg` | Se usa en el cierre para mostrar dónde queda |

Ejemplos de filas (en `referencias/` no hay planilla real; estos son ilustrativos):

```csv
id,linea,tipo_comercio,comercio,ciudad,zona,categoria_uruku,producto,destacados,fotos,venta,pedido_minimo,talles,codigos,envios,factura,extra,link_ficha,permiso_fotos,foto_local
R-0001,A,ropa,Boutique Andina,Bermejo,Av. Petrolera,Moda y ropa,Camperas de temporada,Eco cuero con cinturón;Estilo motero;Doble faz con capucha,p_modelo.jpg;p_motero_c.jpg;p_dobleface.jpg,ambos,,S a 3XL,,,,Llegó esta semana,https://uruku.bo/comercios/ejemplo,si,
R-0002,B,ropa,Importadora del Sur,Bermejo,Calle 23 de Marzo,Moda y ropa,Camperas por mayor,Venta por docena;Talles S a 3XL;Varios colores,p_trench3.jpg;p_corta.jpg;p_motero_c.jpg;p_dobleface.jpg,mayor,desde 1 docena,S a 3XL,166232;KK61331;6052;8806-2,Toda Bolivia,si,,https://uruku.bo/comercios/ejemplo2,si,
R-0003,A,restaurante,Sabor Chapaco,Tarija,Centro,Restaurantes,Almuerzos y platos típicos,Platos típicos;Abierto al mediodía;Para grupos,plato1.jpg;plato2.jpg;salon.jpg,menor,,,,,,Menú del día,https://uruku.bo/comercios/ejemplo3,si,frente.jpg
R-0004,A,hotel,Hotel Los Lapachos,Santa Cruz,Equipetrol,Hoteles,Habitaciones y desayuno,Desayuno incluido;WiFi;Estacionamiento,hab1.jpg;hab2.jpg;desayuno.jpg,menor,,,,,,Cerca del centro,https://uruku.bo/comercios/ejemplo4,si,frente.jpg
```

Si falta un dato obligatorio, no inventarlo: generar el reel solo cuando la fila esté completa y listar las filas incompletas en el reporte final.

---

## 6. Sistema visual

Referencia visual: piezas de apps premium con el celular o el producto flotando sobre fondo oscuro, un **brillo verde** detrás, elementos que **salen de la pantalla** y títulos cortos en dos colores. Ver `referencias/ejemplos/`.

### Tokens
| Token | Valor | Uso |
|---|---|---|
| Fondo | `radial-gradient(110% 75% at 50% 55%, #0F3423 0%, #0B1E15 45%, #08110C 100%)` | Siempre. Nada negro puro |
| Brillo | círculo `rgba(38,185,105,.55)` → transparente, `blur(24px)`, pulso suave de 4 s | Detrás del protagonista |
| Verde acento | `#34D27F` | Segunda línea del título, chips, puntos |
| Verde botón | `#1F9D58` / marca `#1D8D52` | Botones «Buscar», WhatsApp |
| Superficie | `#16211B`, borde `2px #2B4A39` | Chips, paneles, buscador |
| Texto | `#FFFFFF` títulos · `#D2E2D8` subtítulos · `#A8BDB1` secundarios | |
| Tipografía | **Poppins** 600 títulos · 500/400 textos · 700 URL | |
| Logo | `referencias/assets/logo.png` (U dorada + fruto rojo) | Solo en el cierre |
| Íconos | monedas oscuras con borde verde brillante e ícono duotono (`referencias/assets/iconos/`) | Salen de la pantalla con rebote |

No usar: patrones de puntitos o semillas, crema o terracota como protagonistas, emojis como íconos, fondos negros planos.

### Componentes (copiar de `referencias/plantillas/`)
- **Título:** `kick` (etiqueta verde en mayúsculas, opcional) + `tl1` blanco + `tl2` verde. 88 px en 9:16.
- **Tarjeta de producto** (`.pc`): radio 44 px, fondo claro para fotos de percha, sombra grande y borde verde con brillo.
- **Chip** (`.chip`): punto verde con brillo + texto 34 a 40 px.
- **Moneda / ícono** (`.coin`): entra con `cpop` (escala + giro) y queda con `bob` (flota).
- **Buscador** (`.search`): lupa + texto que se escribe solo (`steps()`) + botón «Buscar».
- **Botón WhatsApp** (`.wabtn`): grande, con latido suave.
- **Pasos** (`.st`): número en círculo verde + texto.
- **Carrusel**: cada producto entra desde la derecha (`sin`) y sale a la izquierda (`sout`), unos 2 s por producto, con indicador de puntos.

### Animación
- Todo con CSS `@keyframes` y `animation-delay` en segundos absolutos del video.
- Escenas con fundido de entrada y salida (helper `scene(nombre, t0, t1)` en las plantillas).
- Curvas: entrada `cubic-bezier(.2,.8,.2,1)`, rebote `cubic-bezier(.2,1.3,.3,1)`.
- Ritmo: un elemento nuevo cada 0,3 a 0,6 s. Ningún texto en pantalla menos de 1,5 s.

---

## 7. Plantillas por tipo de comercio

Duración objetivo: **12 a 15 s**. Siempre: gancho en los primeros 2 s y cierre de marca en los últimos 3 s.

### T1 · Producto o novedades (línea A) — ropa, calzado, accesorios, óptica, tecnología
Referencia: `reel_minorista.html` · ejemplo `uruku_reel_minorista_camperas.mp4`

| Tiempo | Escena | Contenido |
|---|---|---|
| 0–1,5 s | Gancho | kick «NUEVA TEMPORADA» / «LLEGÓ ESTA SEMANA» + título («Camperas que / ya llegaron») |
| 1,5–9,6 s | Carrusel | 3 o 4 fotos, cada una con 1 chip de `destacados` + indicador de puntos. Subtítulo fijo abajo |
| 9,7–13,5 s | Cierre | «¿Dónde lo/las consigue?» + buscador escribiendo el producto + chip `comercio · ciudad` + íconos ubicación/WhatsApp + «Consulte precio y talles directo con el local» + logo + uruku.bo + lema |

### T2 · Proveedor directo (línea B) — mayoristas
Referencia: `reel_mayorista.html` · ejemplo `uruku_reel_mayorista_camperas.mp4`

| Tiempo | Escena | Contenido |
|---|---|---|
| 0–3,6 s | Gancho | kick «PARA EMPRENDER» + «¿Quiere / vender ropa?» + «El problema no es vender. Es saber dónde comprar.» |
| 3,3–9,9 s | Mercadería | kick «PROVEEDOR DIRECTO» + «Camperas / por mayor» + grilla 2×2 con chip «Cód. …» + chips (`pedido_minimo`, `talles`, colores) + «Precio de mayorista: consúltelo por WhatsApp» |
| 9,6–14 s | Cierre | «Le pasamos / el contacto» + botón WhatsApp 67 671 888 + pasos: 1 Escríbale a Uruku · 2 Diga el código del producto · 3 Hable directo con el proveedor + logo + lema |

Variantes de gancho para B: «¿Quiere emprender?» · «¿Busca proveedor de [rubro]?» · «¿Tiene una tienda y necesita mercadería?».

### T3 · Restaurante (línea A)
| Tiempo | Escena | Contenido |
|---|---|---|
| 0–1,5 s | Gancho | «¿Dónde comer / hoy en [ciudad]?» |
| 1,5–9,5 s | Carrusel | 3 o 4 fotos: platos y salón. Chips: tipo de comida, «Abierto al mediodía», «Para grupos», «Delivery» (solo si está confirmado) |
| 9,5–13,5 s | Cierre | Chip `comercio · zona` + ícono comida y ubicación + «Vea horario y cómo llegar en Uruku» + buscador con «almuerzo» o el tipo de comida + logo + uruku.bo + lema |

Nunca mostrar precios ni la carta con precios. Si una foto muestra un menú con precios, recortarla o descartarla.

### T4 · Hotel o alojamiento (línea A)
| Tiempo | Escena | Contenido |
|---|---|---|
| 0–1,5 s | Gancho | «¿Dónde dormir / en [ciudad]?» o «¿Viaja a [ciudad]?» |
| 1,5–9,5 s | Carrusel | Habitación, baño, desayuno y fachada. Chips: «Desayuno incluido», «WiFi», «Estacionamiento», «Cerca del centro» |
| 9,5–13,5 s | Cierre | Chip `comercio · zona` + íconos ubicación/WhatsApp + «Consulte disponibilidad por WhatsApp» + logo + uruku.bo + lema |

### T5 · Servicios (línea A) — taller, farmacia, peluquería, etc.
Igual que T4: el gancho es la necesidad («¿Dónde arreglar el celular?»), el carrusel muestra el lugar y el trabajo, y el cierre usa «Vea horario y cómo llegar en Uruku».

### T6 · Repaso por categoría (línea A, varios comercios)
«5 lugares para comprar [rubro] en [ciudad]»: una tarjeta por comercio con su mejor foto y el chip `comercio · zona`. Cierre: «Encuéntrelos todos en Uruku» + buscador con el rubro.

### Banco de textos
- **Ganchos A:** «Camperas que ya llegaron» · «Lo nuevo en [rubro]» · «¿Dónde lo consigue? En Uruku.» · «¿Dónde comer hoy?» · «¿Dónde dormir en [ciudad]?»
- **Cierres A:** «Consulte precio y talles directo con el local» · «Vea horario y cómo llegar en Uruku» · «Búsquelo en uruku.bo»
- **Ganchos B:** «¿Quiere vender ropa?» · «Proveedor directo» · «[Rubro] por mayor»
- **Cierres B:** «Le pasamos el contacto» · «Precio de mayorista: consúltelo por WhatsApp» · «Escríbale a Uruku: 67 671 888»
- **Siempre al final:** «Si está en Bolivia, está en Uruku.»

---

## 8. Formatos de salida

| Formato | Tamaño | Uso | Composición |
|---|---|---|---|
| **9:16** (base) | 1080×1920 | Reels, TikTok, Stories | Título arriba, protagonista al centro, subtítulo y cierre abajo |
| **16:9** | 1920×1080 | YouTube, TV, Facebook horizontal | Texto a la izquierda (alineado a la izquierda, centrado vertical) y animación a la derecha, escalada al alto |
| **1:1** | 1080×1080 | Feed de Instagram y Facebook | Título arriba (franja de 240 px), animación al centro y subtítulo en la franja inferior |

- Se diseña en 9:16 y se adapta con `referencias/codigo/adapt_formatos.js`: separa los textos (`.title`, `.sub`, `.chips`) de lo visual y reubica cada uno según el formato. No es un recorte. Se le pasan `y0` e `y1`, la franja vertical del 9:16 donde vive la animación.
- **Zonas seguras en 9:16:** contenido clave entre y = 220 y y = 1600, y 120 px libres a la derecha (botones de Instagram y TikTok). La descripción de TikTok tapa la parte inferior: el CTA principal nunca debe quedar abajo de y = 1600.
- Revisar en 1:1 que los subtítulos largos no se encimen. Si no entran, ocultarlos (`hideSubSq`).

---

## 9. Render

Si el proyecto ya tiene su propio pipeline, úsalo y toma de acá solo el diseño. Si no, el método de referencia es este (`referencias/codigo/`):

1. Generar un HTML por reel desde la plantilla (Python con f-strings, ver `plantillas/reels_build.py`).
2. Abrirlo con **Playwright (Chromium)** con viewport del formato.
3. Esperar a que carguen las imágenes (`img.decode()`), **pausar todas las animaciones** y hacer una captura de calentamiento.
4. Para cada cuadro: `document.getAnimations().forEach(a => a.currentTime = t*1000)` → captura PNG. Si hay contadores en JS, llamar `window.__upd()`.
5. Codificar con ffmpeg: `-framerate 30 -c:v libx264 -pix_fmt yuv420p -crf 18 -movflags +faststart`.
6. Nombre de salida: `uruku_{id}_{9x16|16x9|1x1}.mp4`.

Las plantillas de referencia buscan las imágenes por nombre en su misma carpeta. Copiar ahí `logo.png`, los íconos y las fotos, o ajustar las rutas.

Audio: los reels se entregan **sin audio** salvo que se indique una pista. Si se agrega música, que sea libre de derechos y que el volumen no tape una eventual voz en off.

---

## 10. Descripción para publicar (caption)

Generar una por reel, en archivo aparte (`uruku_{id}_caption.txt`):
- Tono cercano, como hablando, con gancho. **No repetir lo que ya dice el video.**
- Mencionar el comercio y la ciudad. Línea A: invitar a buscarlo en uruku.bo. Línea B: invitar a escribir al 67 671 888.
- Cerrar con una pregunta que invite a comentar.
- Sin precios. Sin decir que faltan lugares por cargar.
- 5 a 8 hashtags: `#Uruku #Bolivia #[Ciudad] #[Rubro] #ComerciosLocales` y, en la línea B, `#Emprender #VentaPorMayor`.

---

## 11. Control antes de entregar

Para cada reel, verificar con capturas de los cuadros clave (inicio, cada escena y cierre) en los tres formatos:

- [ ] No aparece ningún precio, tabla de stock, texto en chino ni código grande del proveedor.
- [ ] Todos los textos están en neutro (sin «vos», «tenés», «tú», «puedes»).
- [ ] El comercio, la ciudad y los destacados coinciden con la planilla.
- [ ] Línea B: no aparece el WhatsApp del proveedor, sí el 67 671 888.
- [ ] Ningún texto se corta, se encima o queda fuera de las zonas seguras.
- [ ] El cierre muestra logo, uruku.bo (o el WhatsApp en la línea B) y el lema.
- [ ] El material es el correcto (eco cuero, no cuero, si no está confirmado).

Al terminar, entregar un reporte breve: reels generados, filas saltadas y por qué, y fotos marcadas para revisión humana.

---

## 12. Contenido de `referencias/`

```
referencias/
├── plantillas/
│   ├── reels_build.py              # genera reel_minorista.html y reel_mayorista.html (T1 y T2)
│   ├── reel_minorista.html         # plantilla T1 lista para renderizar
│   ├── reel_mayorista.html         # plantilla T2 lista para renderizar
│   ├── video_comercios_build.py    # video informativo para comercios (beneficios, 33 s)
│   └── video_explicativo_build.py  # video explicativo con escena de persona + celular con pantalla verde
├── codigo/
│   ├── render_frames.py            # render 9:16 cuadro a cuadro con Playwright
│   ├── render_formatos.py          # render 16:9 y 1:1 usando adapt_formatos.js
│   ├── adapt_formatos.js           # reubica textos y animación para 16:9 y 1:1
│   ├── iconos_set1.html            # monedas: ubicación, farmacia, cajero, comida, WhatsApp, cambio
│   └── iconos_set2.html            # monedas: tienda, oferta, gráfico, estrella, cámara
├── assets/
│   ├── logo.png
│   ├── iconos/ic_*.png             # monedas renderizadas con transparencia (360×360)
│   └── fotos_ejemplo/p_*.jpg       # fotos de proveedor ya recortadas (sin códigos ni stock)
└── ejemplos/
    ├── uruku_reel_minorista_camperas.mp4
    ├── uruku_reel_mayorista_camperas.mp4
    ├── uruku_comercios_9x16.mp4
    ├── cuadros_reels.png           # cuadros clave de T1 y T2
    ├── cuadros_video_comercios.png
    └── cuadros_16x9_1x1.png        # cómo se ven las adaptaciones horizontal y cuadrada
```

Para un tipo de comercio nuevo (restaurante, hotel, servicio), partir de `reels_build.py`: duplicar la plantilla T1, cambiar textos e íconos según §7 y, si hace falta un ícono nuevo, agregarlo a `iconos_set2.html` con el mismo estilo de moneda.
