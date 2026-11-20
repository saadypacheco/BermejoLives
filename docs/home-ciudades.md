# Home de las ciudades (todas menos Bermejo) y Dax por ciudad

> Acordado con el dueño el 20/11/2026, con la maqueta navegable de Tarija como referencia.
> Bermejo conserva su home y su encabezado actuales.

## 1. Alcance

- **Regla para elegir el home:** el home nuevo sale cuando la ciudad elegida **no es Bermejo** (`slug !== "bermejo"`), que es la misma regla que usa hoy `app/page.tsx`. El encabezado nuevo (§3) sigue la misma regla.
- **Dax:** el panel nuevo (§8) vale para **todas** las ciudades, incluida Bermejo.
- **Fuera de alcance:**
  - que el buscador conteste preguntas como Dax (descartado por ahora);
  - la agenda de eventos (queda para cuando haya eventos);
  - el diseño con IA.
- **Reglas del producto que se mantienen:**
  - Ningún acceso, botón ni tarjeta lleva a un mapa vacío. Aparece solo si la ciudad tiene comercios de ese rubro (`rubrosDeCiudad` / `accesoConComercios`, en `lib/accesos-ciudad.ts`).
  - No se muestran cantidades de comercios al público. La única excepción es la línea real de «nuevos en 24 h».
  - Nada de emojis: todos los íconos salen de `components/ic.tsx`.
  - Nunca `select("*")` sobre `comercios`.

## 2. El home, de arriba a abajo (sin Bermejo)

| Orden | Bloque | Qué tiene |
|---|---|---|
| 1 | Encabezado (§3) | Logo, ciudad, clima y cuenta; los interruptores «Abiertos» y «Más cerca» con la cotización; buscador con micrófono; barra de rubros |
| 2 | Botones de intención (§4) | Una fila, con el mismo tamaño que los accesos de hoy |
| 3 | Línea de comercios nuevos | `lineaComerciosNuevos`, como hoy |
| 4 | Carrusel de productos (§5) | — |
| 5 | «Qué podés hacer en {ciudad}» (§6) | — |
| 6 | Carrusel de comercios (§7) | — |
| 7 | Ofertas y «Vencen hoy» | Solo si hay ofertas. Sin ofertas, la sección no aparece ni muestra aviso |
| 8 | Comercios destacados | Los planes pagos: el carrusel de hoy, sin cambios, solo si hay |
| 9 | Al pie | Novedades (si hay), Videos (`VideosUruku`), el WhatsApp de URUKU (`ContactoUruku`) y Ciudades |

**A la noche (19 a 24 h)**, el bloque 5 pasa arriba del 4.

**Salen del home de estas ciudades:**
- el hero «Todo {ciudad} en un solo lugar», con sus botones y los tres textos;
- la caja «Hoy en {ciudad}»;
- la banda `VisitaCiudad`, que la reemplaza el bloque 5;
- `TarjetaTurnoHoy`, porque la farmacia de turno pasa al panel de Farmacias;
- las secciones «Servicios útiles» y «Herramientas útiles»;
- la fila `AccesosCiudad`, que la reemplazan los botones de intención;
- el aviso «Todavía no hay ofertas».

## 3. El encabezado (sin Bermejo)

- **Fila 1:** logo · selector de ciudad · clima de la ciudad (§9) · cuenta.
- **Fila 2:** los interruptores **«Abiertos»** y **«Más cerca»** · la cotización.
  - La cotización muestra el dólar siempre. La moneda vecina solo aparece si `es_frontera`, como hoy.
- **Buscador:** con micrófono (`MicrofonoBusqueda`, el que ya existe) y la barra de rubros (`CatNav`), como hoy.

### Los interruptores «Abiertos» y «Más cerca»

- **Estado:** cada uno está prendido o apagado. Prendido se pinta de verde y lleva `aria-pressed="true"`.
- **Memoria:** se guardan en `sessionStorage` con la clave `uk-filtros-rapidos`, como `{ abiertos: boolean, cerca: boolean }`. Al abrir otra sesión del navegador arrancan apagados.
- **A qué se aplican:** a todo enlace al buscador o al mapa que se toque después (buscador, barra de rubros, botones de intención, «Qué podés hacer», «Ver todos»), sumando `abierto=1` y/o `cerca=1`. También ordenan y filtran el carrusel de comercios del home (§7).
- **«Más cerca»:** pide la ubicación la primera vez. Si la persona no la da, se apaga solo y aparece un aviso corto.
- **`/buscar` acepta `abierto=1`.** Es nuevo: un filtro que deja solo los comercios con `abiertoAhora(horario).estado === "abierto"` (lib/horario.ts), con el mismo criterio que usa `app/guia/page.tsx`. Además lleva un chip «Abiertos» junto al chip «Cerca» que ya existe. `cerca=1` ya funciona.

## 4. Los botones de intención

- **Tamaño:** el mismo que los accesos de hoy (`.uk-home-chips a`): `padding: 9px 14px`, letra de 14 px en 600, ícono de 18 px y radio `--uk-radius-sm`. Es una fila con desplazamiento horizontal.
- **Comportamiento:** cada botón abre un **panel que sube desde abajo** (la misma hoja de §8) con sus opciones. Cada opción lleva a `/buscar?rubro=…&vista=mapa`. Una opción aparece solo si la ciudad tiene comercios de ese rubro, y un botón sin opciones no aparece.

| Botón | Ícono | Opciones (rubro) |
|---|---|---|
| Negocios | `comprar` o el que corresponda | Los rubros **comerciales** de la ciudad que no son de comer ni de dormir, ordenados por nombre |
| Productos | — | Panel «Buscá por producto» con los productos más frecuentes de la ciudad (§5) como chips que llevan a `/buscar?q=…` |
| Servicios | — | Rubros de servicios: `taller-mecanico`, `peluqueria`, `servicio-tecnico`, `cerrajeria`, `lavadero`, `gomeria-servicio` y los que haya en la ciudad |
| Comer | `restaurantes` | `cafeteria`, `restaurantes`, `comida-rapida`, `panaderia` |
| Dormir | `hospedaje` | `hospedaje` («Hoteles y hostales») |
| Farmacias | `farmacia` | «De turno hoy», que va a `/{ciudad}/farmacias-de-turno` si la ciudad tiene turnos cargados, y «Todas las farmacias» (`farmacia`) |
| Bancos y cajeros | `cajeros` | `cajeros` («Cajeros y bancos») y `cambio` |

**Farmacias** y **Bancos y cajeros** están siempre, mientras la ciudad tenga ese rubro.

### Orden y resaltado según la hora

La hora es la de Bolivia (`ahoraEnBolivia()`) y la calcula el servidor. Nada se saca de la página: solo cambia el orden y cuál se resalta.

| Franja | Orden de los botones | Resaltado («cartel» dentro del botón) |
|---|---|---|
| 6 a 11 | Comer, Negocios, Productos, Servicios, Farmacias, Bancos, Dormir | Comer · «Desayunos» |
| 11 a 15 | Comer, Negocios, Productos, Servicios, Farmacias, Bancos, Dormir | Comer · «Almuerzos» |
| 15 a 19 | Negocios, Productos, Servicios, Comer, Farmacias, Bancos, Dormir | Negocios · «Abiertos» |
| 19 a 24 | Comer, Negocios, Productos, Dormir, Farmacias, Bancos, Servicios | Comer · «Cenar» |
| 0 a 6 | Farmacias, Bancos, Dormir, Comer, Negocios, Productos, Servicios | Farmacias · «De turno» |

El cartel va **adentro** del botón, a la derecha del nombre, como una pastilla chica verde. No agranda el botón.

## 5. Carrusel de productos

- **Título:** «Lo que se consigue en {ciudad}». Subtítulo: «Lo que se ve en la foto de cada local».
- **Con productos cargados:** si la ciudad tiene **4 o más** filas en `productos` (`activo`, con `foto_url`, de comercios activos y no suspendidos de esa ciudad), el carrusel muestra esos productos, los más nuevos primero.
  - Cada tarjeta lleva la foto, el nombre, el precio **solo si está cargado** y el nombre del comercio.
  - El enlace va a `/comercios/{slug}#ficha-encontrar`.
- **Sin productos cargados** (hoy, en todas las ciudades): las tarjetas se arman con los comercios de la ciudad que tengan foto (`portada_thumb_url`) y algo en `prod_obs_human` o `prod_det_ia`.
  - Cada tarjeta lleva la foto del local, los dos o tres primeros productos (con el mismo corte que `productosDe`/`productosDeFicha`) y el nombre del comercio.
  - El enlace va a la ficha, a `#ficha-encontrar`.
  - Se muestran hasta 12, mezclados.
- **Sin ninguna de las dos cosas**, el carrusel no aparece.
- **Productos frecuentes:** de los mismos textos se sacan los más repetidos de la ciudad, normalizados en minúscula y sin repetir, hasta 12. Alimentan el panel del botón «Productos».

## 6. «Qué podés hacer en {ciudad}»

- **Diseño:** un bloque oscuro con el título «Qué podés hacer en **{ciudad}**» y el subtítulo «Todo te lleva al mapa», con tarjetas de 2 columnas.
- **Tarjetas:** cada una aparece solo si la ciudad tiene datos.
  - Para visitar (`para-visitar`)
  - Boliches y karaoke (`nocturna`)
  - Dónde comer (`restaurantes`)
  - Plazas y parques (`para-visitar` con subcategoría Plaza o Parque)
- **Foto de cada tarjeta:** el `portada_thumb_url` de un comercio de ese rubro, si hay alguno. Si no, el ícono solo. Nunca una foto de otro rubro.
- **Si no queda ninguna tarjeta**, el bloque no aparece.

## 7. Carrusel de comercios

- **Rubros, título y subtítulo según la franja horaria:**

| Franja | Rubros | Título |
|---|---|---|
| 6 a 11 | `cafeteria`, `panaderia` | «Para desayunar» |
| 11 a 15 | `restaurantes`, `comida-rapida` | «Para almorzar» |
| 15 a 19 | comerciales que no son de comer | «Abiertos ahora» |
| 19 a 24 | `nocturna`, `restaurantes` | «Esta noche en {ciudad}» |
| 0 a 6 | `farmacia` | «Abiertas ahora» |

  - Si la ciudad no tiene comercios de esos rubros, se usan los comerciales con foto y el título pasa a ser «Comercios de {ciudad}».
- **Orden:** el mismo criterio de `ordenarCerca` (lib/orden-cerca.ts): primero los abiertos, después el plan estrella, después la distancia si hay ubicación.
  - Con «Abiertos» prendido, solo los abiertos.
  - Con «Más cerca» prendido, se ordena por distancia y cada tarjeta muestra los metros.
- **Tarjeta:** foto (`portada_thumb_url`, con `portada_pos`), el estado de `HorarioBadge`, el nombre y «rubro · ciudad» (o la distancia).
- **Cantidad:** hasta 12. «Ver todos» lleva al mapa con esos rubros.
- El carrusel es un componente cliente: necesita la ubicación y los interruptores.

## 8. Dax

### El panel (todas las ciudades)

- **Celular** (≤ 900 px): una hoja que **sube desde abajo** y ocupa el 64 % del alto, sobre un velo oscuro.
  - Arriba lleva una rayita para arrastrar y el encabezado: avatar, «Dax», «Tu guía en {ciudad}» y el botón **«× Cerrar»** a la derecha, con borde y la palabra escrita.
  - **Formas de cerrar:** «Cerrar», tocar el velo, tocar la rayita, `Escape` y el botón «atrás» del teléfono (con `history.pushState` al abrir y `popstate` al cerrar).
  - El campo para escribir queda abajo y no lo tapa el teclado: usar `visualViewport` o `dvh`.
- **Computadora:** un panel a la derecha con el mismo encabezado y «× Cerrar» arriba.
- **El botón flotante «Preguntame»** se esconde mientras el panel está abierto; la «×» del botón flotante desaparece. En las ciudades sin Bermejo, en el celular no hay botón flotante: Dax vive en la barra de abajo.
- **El evento `uk-abrir-ayuda`** se sigue usando para abrir el panel desde cualquier lado.
- **Respuestas con comercios:** se muestran como tarjeta con foto y el botón **«Ver comercios ›»** que lleva a la búsqueda. La lista actual de `fuentes` se mantiene.

### La barra de abajo (sin Bermejo)

- **Ítems:** Inicio · Mapa · **Dax** · Novedades · Guardados. Dax va al centro, con su cara en un círculo que sobresale, y abre el panel.
- **Bermejo:** su barra (Inicio, Mapa, Ofertas, Guía, Cambio) y su botón flotante quedan como están, pero el panel es el nuevo.

### Dax por ciudad

- **Saludo:** «¡Buen día!», «¡Hola!» o «¡Buenas noches!» según la franja, más «Soy Dax y conozco {ciudad}».
- **Sugerencias iniciales sin Bermejo, por franja.** Una sugerencia sale solo si la ciudad tiene el rubro correspondiente. Las mismas listas usan el panel (frontend) y las respuestas del backend:

| Franja | Sugerencias |
|---|---|
| 6 a 11 | «¿Dónde desayuno?», «Farmacia abierta cerca», «¿Qué visito hoy?» |
| 11 a 15 | «¿Dónde almuerzo?», «Busco zapatillas», «Cajero cerca» |
| 15 a 19 | «Busco zapatillas», «Necesito un servicio técnico», «¿Qué hago hoy?» |
| 19 a 24 | «Boliches abiertos esta noche», «¿Dónde ceno?», «Hotel para esta noche» |
| 0 a 6 | «Farmacia de turno», «Cajero cerca», «¿Dónde duermo?» |

- **Backend:** `SUGERENCIAS_INICIALES` (services/asistente.py) sigue igual para Bermejo y para las ciudades con guía. En las demás devuelve la lista de la franja. Nunca ofrece «el paso», la aduana ni los pesos en una ciudad sin frontera.
- **Cambio de ciudad con el panel abierto:** el panel agrega «Ahora te ayudo con {ciudad}» y las preguntas siguientes van con la ciudad nueva.
- **Admin:** en «Asistente › Saber local», el selector de ciudad lista **todas** las ciudades activas, no solo las de frontera.

## 9. Clima por ciudad

- **Migración `0201_clima_ciudades.sql`** (en `supabase/migrations/` y `selfhost/postgres-init/`), idempotente:
  - Tabla `clima_ciudades`:

    | Columna | Tipo |
    |---|---|
    | `ciudad_id` | uuid, primary key, references `ciudades` |
    | `temp_c` | numeric |
    | `descripcion` | text |
    | `actualizado_en` | timestamptz not null default `now()` |

  - RLS activo; lectura pública (`select` para anon y authenticated); escritura solo de `service_role`. GRANTs explícitos.
- **Backend:**
  - El loop de clima (main.py) también recorre las ciudades activas con `lat`/`lng`, cada 30 minutos.
  - Hace **una sola llamada** a Open-Meteo con todas las coordenadas (`latitude=a,b,…&longitude=…`), sin clave.
  - Si una ciudad falla, se saltea y se mantiene el dato anterior.
  - La fila `clima` id=1 de Bermejo, con su override manual, no cambia.
- **Frontend:**
  - `getClimaCiudad(ciudadId)` lee `clima_ciudades`.
  - Si el dato tiene más de 3 horas, no se muestra.
  - El ícono sale de `climaIcono(descripcion)`, sin emojis.

## 10. Criterios de aceptación

1. **Home sin Bermejo:** en Tarija aparece en el orden de §2. En Bermejo, el home y el encabezado no cambian.
2. **Sin bloques vacíos:**
   - ningún botón, opción, tarjeta ni bloque lleva a un rubro sin comercios en la ciudad;
   - sin ofertas no aparece la sección ni el aviso;
   - sin productos ni comercios con productos detectados no aparece el carrusel de productos.
3. **Interruptores:** prendidos se pintan de verde, se recuerdan en la sesión y suman `abierto=1` / `cerca=1` a los enlaces al buscador. `/buscar?abierto=1` muestra solo los abiertos.
4. **Botones según la hora:** el orden y el cartel cambian según la franja horaria de Bolivia, con el tamaño de los accesos actuales.
5. **Panel de Dax en el celular:** sube desde abajo con «× Cerrar» arriba, se cierra con el velo, con `Escape` y con el «atrás» del teléfono, y el botón flotante no se ve mientras está abierto.
6. **Dax en Tarija:** saluda según la hora, sugiere por franja y nunca menciona el paso ni la aduana.
7. **Clima en Tarija:** el encabezado muestra el clima de la ciudad. Si no hay dato o está viejo, no muestra nada.
8. **Admin:** el selector de saber local muestra todas las ciudades activas.
9. **Calidad:** `npm test` y `tsc --noEmit` sin errores; tests del backend en verde; tests nuevos para la lógica pura (franjas, orden, filtros, sugerencias, armado de tarjetas, clima por ciudad).

---

# Parte 2 (20/11/2026): fotos lindas, planes ilustrados, bodegas, aprobación en bloque y platos típicos

> Acordado con el dueño después de ver el home nuevo en QA y la maqueta
> `propuesta-fotos-planes-v2.png`. Los eventos de tarijaturismo.com quedan **afuera**: el último publicado es de
> agosto de 2026, así que no hay ninguno por venir.

## 11. Las fotos de los carruseles

- **Versión «tarjeta» de la portada:** 800 px de ancho, recortada a **4:3** según `portada_pos` (la misma regla del
  CSS `object-position: center X%`), pasada por `mejorar_gratis` (services/portada_diseno.py) y guardada en JPEG con
  calidad 80, como `/fotos/<slug>/card-<token>.jpg`.
  - Se arma al subir o cambiar la portada y al cambiar el encuadre.
  - El archivo anterior se suelta igual que en la portada de diseño.
- **Puntaje de calidad `portada_calidad`** (0 a 100), calculado al armar la tarjeta sobre la imagen ya mejorada:
  - colorido (métrica de Hasler-Süsstrunk), nitidez (varianza del laplaciano) y luz media sin extremos;
  - normalizado y documentado en el código. Sin IA.
- **Migración 0202:**
  - `comercios.portada_card_url text` y `comercios.portada_calidad smallint`, las dos **públicas** con grant por
    columna (regla 11);
  - suma las dos columnas a `buscar_comercios` si hace falta para que lleguen al front.
- **Relleno:** el comando `python -m app.services.fotos_tarjeta --todas [--ciudad <slug>] [--rehacer]` arma las
  tarjetas de los comercios que ya tienen portada. Va despacio, lee del disco y nunca borra la portada original.
- **En el front:**
  - los carruseles usan `portada_card_url` y, si no hay, `portada_thumb_url`;
  - si el comercio tiene portada de diseño, se usa esa;
  - el nombre y «rubro · ciudad/distancia» van **encima de la foto**, sobre un degradé oscuro;
  - el cartel «Abierto» va blanco, arriba a la izquierda;
  - en pantallas táctiles no hay flechas sobre las fotos (abajo van unos puntitos); en la compu, las flechas quedan
    fuera de la foto.
- **Orden de los carruseles:** primero los abiertos, después el plan estrella, después **`portada_calidad`
  descendente** y después la distancia si «Más cerca» está prendido.

## 12. «Qué podés hacer en {ciudad}»: planes ilustrados

- **Un catálogo fijo de ilustraciones SVG propias** en `components/ilustraciones/`, en el estilo de la maqueta
  (planos, colores de la marca, sin fotos de terceros ni IA):
  - vino, centro histórico, miradores, cascadas y ríos, noche, sabores, lagunas y montaña, parques, museos y
    mercados.
  - Cada ilustración tiene `aria-hidden`, con el título al lado.
- **Planes definidos en código** (`lib/planes-ciudad-pure.ts`). Cada plan tiene título, bajada, ilustración y
  destino. **Sale solo si la ciudad tiene datos para ese destino**: un plan sin datos no aparece y la ciudad no se
  configura a mano.

| Plan | Destino | Sale si |
|---|---|---|
| **La ruta del vino y el singani** (tarjeta grande, con el recorrido dibujado) | `/buscar?rubro=bodegas&vista=mapa` | la ciudad tiene `bodegas` |
| Centro histórico | `para-visitar` con sub Plaza, Iglesia o Patrimonio (la primera que haya) | alguna de esas |
| Miradores | `para-visitar` · Mirador | hay miradores |
| Parques | `para-visitar` · Parque | hay parques |
| Museos | `para-visitar` · Museo o Centro cultural | hay alguno |
| Cascadas y ríos | `para-visitar` · Excursión | hay excursiones |
| Lagunas y montaña | `para-visitar` · Área protegida | hay áreas protegidas |
| Noche {gentilicio} | `nocturna` | hay boliches |
| Sabores {gentilicio} | `/{ciudad}/sabores` (§15) | hay platos aprobados en la ciudad |

- **Gentilicios** en un mapa chico: tarija → chapaca, santa-cruz → cruceña, la-paz → paceña,
  cochabamba → cochabambina, oruro → orureña, sucre → sucrense, potosi → potosina, bermejo → bermejeña, y
  «de {ciudad}» para el resto («Noche de Trinidad»).
- **La tarjeta grande** es la del primer plan con datos, en este orden: ruta del vino, centro histórico, noche. El
  resto va en una grilla de 2 columnas, hasta 6.
- **Al final**, «Ver todos los planes en el mapa ›» a `/buscar?rubro=para-visitar&vista=mapa`, si hay.
- **El recorrido de la ruta del vino** es parte de la ilustración, no un mapa real. Las paradas dicen Viñedos,
  Bodegas y Singani, sin nombres de comercios.

## 13. Rubro «Bodegas y vinotecas»

- **Migración 0202:**
  - rubro `bodegas` («Bodegas y vinotecas»), comercial, con sus palabras para la clasificación (bodega, vinoteca,
    viñedo, singani artesanal, cata de vinos), sin pisar `bebidas`;
  - pasa a `bodegas` las filas de `comercios_importados` con `fuente='turismo'`, subcategoría `bodegas-y-vinotecas`
    y `estado='nuevo'`. Es idempotente.
- **Importador:** `RUBRO_POR_SUBCATEGORIA["bodegas-y-vinotecas"] = "bodegas"`.
- **Ícono:** se suma `bodegas` al catálogo de `ic.tsx` (copa de vino, Phosphor) y se corre `npm run iconos`.

## 14. Aprobar en bloque en Importados

- **Endpoint `POST /admin/importados/aprobar-lote`**, con el mismo permiso que aprobar de a uno. Cuerpo:
  `{ fuente, ciudad_id, solo_con_punto: true, simular: bool }`.
  - Aprueba **por el mismo camino que aprobar de a uno**, fila por fila, con el mismo rubro y las mismas
    validaciones.
  - Saltea las filas marcadas como repetidas, las que no tienen rubro y las que no tienen punto si
    `solo_con_punto`.
  - Devuelve `{ aprobados, salteados: { repetidos, sin_rubro, sin_punto, error } }`.
  - Con `simular: true` cuenta y no escribe nada.
  - Tope de 1000 filas por llamada. Deja registro con structlog.
- **En el panel:** en Importados, con un filtro de fuente puesto, aparece el botón «Aprobar en bloque».
  - Primero muestra el resultado de la simulación («Se aprueban N; se saltean …») y pide confirmar en la misma
    pantalla. Recién ahí aprueba.
  - Nada se publica sin que la persona confirme.

## 15. Platos típicos (Sabores {gentilicio})

- **Fuente:** las notas de gastronomía de tarijaturismo.com (categorías `platos`, `reposteria-tradicional` y
  `bebidas-tipicas`).
  - **No se copian sus textos ni sus fotos.** Se toma el nombre del plato y el enlace.
  - La IA escribe un texto **original**, de 2 a 3 frases en voseo, con los ingredientes y cómo se come. Recibe como
    datos el texto de la nota y la orden de no copiar frases ni inventar datos.
  - El texto de la nota no se guarda en la base.
- **Costo:** usa el cliente de Gemini del proyecto, detrás de `cost_switches`, con una fila nueva `gemini_gastronomia`
  apagada por defecto. Son unos 50 textos cortos; el comando informa cuántos pidió.
- **Migración 0202:** tabla `platos_tipicos`:

  | Columna | Tipo |
  |---|---|
  | `id` | uuid |
  | `ciudad_id` | → `ciudades` |
  | `tipo` | `plato`, `reposteria` o `bebida` |
  | `nombre` | text |
  | `descripcion` | text |
  | `fuente_url` | text |
  | `estado` | `pendiente`, `aprobado` o `rechazado` |
  | `activo` | boolean |
  | `created_at` / `updated_at` | timestamptz |

  - RLS: anon lee solo `estado='aprobado' and activo`.
  - service_role: select, insert y update. Sin delete (borrado lógico).
  - `unique (ciudad_id, nombre)`.
- **Comando:** `python -m app.services.importar_gastronomia --ciudad tarija [--simular]`. Deja todo como `pendiente`
  y no repite lo que ya existe.
- **Admin:** sección «Platos típicos»: lista por ciudad y estado; se puede editar nombre y texto, aprobar y rechazar.
- **Página `/{ciudad}/sabores`:**
  - Título «Sabores {gentilicio}».
  - Platos, repostería y bebidas, con el nombre, el texto y la ilustración del tipo (sin fotos).
  - Un botón «Dónde comer comida típica ›» a los restaurantes con subcategoría Boliviana / Regional / Criolla, o a
    `restaurantes` si no hay.
  - Fuente citada al pie: «Datos: Turismo de Tarija» con enlace.
  - SSG + ISR. Si la ciudad no tiene platos aprobados, 404.

## 16. Criterios de aceptación (parte 2)

1. **Fotos de los carruseles:** usan la versión tarjeta de 800 px mejorada; el nombre va encima de la foto; no hay
   flechas sobre las fotos en el celular; las de más calidad salen primero.
2. **Relleno de tarjetas:** el comando arma las tarjetas de las portadas existentes sin borrar ninguna original.
3. **Planes:** «Qué podés hacer» muestra planes ilustrados y cada uno aparece solo si hay datos. La ruta del vino
   sale en Tarija cuando hay bodegas aprobadas.
4. **Bodegas:** las 16 bodegas de turismo quedan con el rubro `bodegas` en Importados.
5. **Aprobación en bloque:** simula primero, pide confirmar y aprueba por el mismo camino que de a uno, salteando
   repetidos, sin rubro y sin punto.
6. **Platos típicos:**
   - quedan pendientes hasta que se aprueban;
   - `/tarija/sabores` muestra solo los aprobados;
   - ningún texto de tarijaturismo.com aparece copiado;
   - con el interruptor apagado, el comando no gasta.
7. **Calidad:** `tsc` limpio, `npm test` y pytest en verde, con tests nuevos para el puntaje de calidad, el recorte
   4:3, los planes por datos, los gentilicios, la aprobación en bloque y la escritura de platos con Gemini simulada.
