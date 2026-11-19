# Vigía de fuentes — revisar las páginas todos los días (spec)

> Estado: **propuesta** (16/11). Reemplaza las corridas a mano de `importar_turismo` y `ubicar_direccion`.

## Problema

Hoy cada fuente se importa **una vez**, a mano, desde la consola del servidor:

- `importar_turismo` lee las páginas y **saltea** lo que ya existe: no se entera de un teléfono nuevo, un horario
  cambiado ni un negocio que cerró.
- `ubicar_direccion` vuelve a preguntarle todo a Nominatim en cada corrida (~700 pedidos). El 16/11, después de
  cuatro corridas, dejó de contestar.
- Nadie se entera de un negocio nuevo en la página de turismo hasta que alguien vuelve a correr el comando.

## Qué hace

Una vuelta por día (de madrugada, hora de Bolivia), sola, por cada fuente y ciudad:

1. **Lee la fuente** con cortesía: un pedido por segundo, el mismo `User-Agent` de siempre, respeta `robots.txt`.
   Si la página no cambió desde ayer (misma huella del HTML), no la vuelve a procesar.
2. **Compara con lo de ayer**, negocio por negocio:
   | Qué pasó | Qué deja |
   |---|---|
   | Negocio que no estaba | Un importado `nuevo` (cola de revisión, como hoy) |
   | Cambió un dato (teléfono, dirección, horario, web, rubro) | Un **cambio pendiente**: campo, antes, después |
   | No aparece **3 días seguidos** | Marca «ya no figura en la fuente» (posible cierre) para revisar |
   | Igual que ayer | Sólo actualiza «visto por última vez» |
3. **Ubica sólo lo nuevo o lo que cambió de dirección**, con un **caché permanente** de Nominatim: unos pocos
   pedidos por día en vez de cientos por corrida.
4. **Deja un resumen** de la corrida en el panel.

**Nunca publica ni pisa nada solo.** Un cambio en un negocio ya promovido aparece como propuesta en el panel:
«La página de turismo cambió el teléfono de X: *aplicar* / *ignorar*». El dato del comercio (lo cargó él o el
equipo) puede ser más nuevo que el de la página.

## Fuentes

Catálogo revisado el 16/11, leyendo las condiciones de uso de cada sitio. Solo entran fuentes que permiten
leerlas y guardarlas.

| Fuente | Licencia | Cada cuánto cambia | Cómo se lee | Qué trae |
|---|---|---|---|---|
| `overture` (Overture Maps Places) | CDLA-Permissive 2.0 / Apache 2.0 / CC0 por fila: uso comercial permitido | Mensual | GeoParquet público en S3, filtrado por la caja de cada ciudad (DuckDB) | Nombre, categoría, punto, teléfono, web, redes, dirección, `confidence`. **Sin horario.** Medido: ~290 lugares en Bermejo y ~3.800 en Tarija (OSM: 68 en Bermejo) |
| `osm` (OpenStreetMap) | ODbL: atribución y share-alike | Diario | **Una** consulta Overpass por ciudad | Punto exacto, horario, web |
| `turismo` (tarijaturismo.com) | Sin licencia, `robots.txt` abierto: zona gris leve; solo datos y enlace | Sin fecha | Las 7 páginas de lista (`SITIOS`) | Nombre, dirección, teléfonos, rubro |
| Fichas de «Qué hacer» | Ídem | Ídem | Solo la ficha de un negocio nuevo o cambiado | Horario y dirección completa |
| `anh` (estaciones de servicio) | Sin términos ni `robots.txt` | Sin fecha | HTML por departamento, una vez por semana | Razón social, dirección, teléfono, combustibles (sin punto: se ubica) |

**Pedir por escrito antes de automatizar:**
- **SEPREC**, Directorio de Unidades Económicas: es la fuente más completa, pero no tiene descarga ni términos publicados.
- **Viceministerio de Turismo (SIRETUR)**: solo se puede consultar con usuario.
- **Alcaldías**: hay que pedirles sus listas. Ya está pendiente la nota a la Secretaría de Turismo de Tarija.

**Prohibidas, porque sus condiciones lo dicen por escrito:**
- **No se pueden leer automáticamente:** TripAdvisor, Booking, Airbnb, Expedia, Hostelworld, PedidosYa, Facebook, Instagram y TikTok.
- **Prohíben copiar o redistribuir:** los directorios Amarillas.bo, BoliviaEmpresas, BoliviaYP y Bolivia en Tus Manos.
- **Tienen API pero no dejan guardar los datos:** Google, TripAdvisor, Foursquare, Mapbox y HERE.
- **Única vía legal para estas fuentes:** el enlace que da el propio comercio.

**Overture se lee una vez por mes.** Una release nueva cada mes. El vigía mira todos los días si hay release nueva y, si
la hay, la procesa. Entra solo con `confidence` ≥ 0.5 y siempre a la cola de revisión, nunca publicado. Casi
todo viene de las páginas de negocios de Meta: puede haber cerrados (`operating_status` viene vacío en Bolivia).

**Agregar una fuente = un lector nuevo.** Cada fuente tiene una función que devuelve la misma `Entrada`
(nombre, dirección, teléfonos, enlace, horario…). El resto (comparar, cambios, ubicar, resumen) es común.

**OSM ayuda a ubicar sin Nominatim.** El paso «por nombre» del ubicador primero busca el nombre entre los
negocios de OSM de la ciudad que ya se trajeron. Sólo si no está, le pregunta a Nominatim.

## Modelo de datos (migración nueva)

- `comercios_importados`, columnas nuevas:
  - `huella`: hash de los campos comparables;
  - `visto_at`: última vez que la fuente lo mostró;
  - `ausente_desde`: primera corrida en que faltó; se borra si vuelve.
- `importados_cambios`: `importado_id`, `comercio_id` (si ya fue promovido), `campo`, `antes`, `despues`,
  `detectado_at`, `estado` (`pendiente` / `aplicado` / `ignorado`), `revisado_por`, `revisado_at`.
  Sólo borrado lógico.
- `geocache`: `consulta` normalizada, `ciudad_id`, `rango_minimo`, `largo_maximo_m`, `resultado` (jsonb, también
  «no encontrado»), `consultado_at`. Vale 90 días; los «no encontrado», 7 días.
- `vigia_corridas`: `fuente`, `ciudad_id`, `inicio`, `fin`, `leidas`, `nuevas`, `cambiadas`, `ausentes`,
  `pedidos_nominatim`, `error`.

Todas con RLS activo y sin acceso para `anon`. Sólo las usa el backend con `service_role`. Los GRANT van
explícitos en la migración.

## Cómo corre

- Un loop más en el `lifespan` del backend, como los otros diarios (AGENTS.md §7.13: un solo worker). Arranca a
  las 04:00 de Bolivia.
- **Apagado por defecto**: se enciende con `VIGIA_FUENTES_ACTIVO=1` en `backend/.env`. Costo cero: sólo usa
  servicios gratuitos.
- También a mano: `python -m app.services.vigia --ciudad tarija [--fuente turismo] [--dry-run]`.
- Si una fuente falla (página caída, HTML cambiado: «0 negocios leídos» cuando ayer había 340), la corrida queda
  con `error` y **no marca a nadie como ausente**. Así un cambio del sitio no se confunde con cierres masivos.

## Clave del negocio (ojo)

Hoy `fuente_id` de turismo es `nombre|dirección`: si cambia la dirección, parece un negocio nuevo y el viejo «ya
no figura». La comparación junta esos dos casos por nombre, dentro de la misma corrida, y los registra como **un
cambio de dirección**.

## Panel

Sección «Novedades de fuentes» en Importados:

- el resumen de la última corrida por fuente;
- la lista de cambios pendientes, con «aplicar» o «ignorar»;
- la lista de «ya no figura».

## Límites (no cambian)

- Sólo datos y el enlace a la fuente: no se copian textos ni fotos.
- Nada de Google.
- No se manda ningún mensaje a los comercios.
- Nominatim: un pedido por segundo y siempre a través del caché.

### Overture: cómo se corre

```bash
docker exec buscadonde-backend python -m app.services.importar_overture --ciudad tarija --dry-run
docker exec buscadonde-backend python -m app.services.importar_overture --ciudad tarija
```

- **Radio por ciudad** (`RADIOS`): Santa Cruz 12 km, Cochabamba 9, La Paz 8 (no llega al centro de El Alto),
  Tarija 7, Oruro 6, Bermejo 4. Se cambia con `--radio-km`.
- **Qué entra:** `confidence` >= 0.5, con nombre, sin estar cerrado. No entran templos, escuelas, oficinas
  públicas, plazas ni accidentes geográficos (`NO_COMERCIO`). Volver a correrlo no duplica nada.
- **Redes:** Facebook, Instagram y TikTok van a `tags.overture.redes_por_red`. Al promover pasan a
  `facebook_url`, `instagram_url` y `tiktok_url`. El sitio web solo toma dominios reales.
- **Medido en Tarija el 16/11:**
  - 2.290 leídos y 1.931 que entran;
  - 1.580 con WhatsApp y 1.840 con dirección;
  - 760 sin rubro: se elige en el panel.
- **Hecho (17/11):** la atribución está en los términos, §1 («fuentes de datos abiertos»: OpenStreetMap y Overture Maps Foundation, con sus licencias).
  antes de publicar comercios de esta fuente. La licencia lo pide al compartir los datos.

### ANH: cómo se corre

Estaciones de servicio de la Agencia Nacional de Hidrocarburos (`fuente='anh'`), por departamento. Entran a
Importados como `estado='nuevo'`; nada se publica solo.

```bash
docker exec buscadonde-backend python -m app.services.importar_anh --departamento tarija --dry-run
docker exec buscadonde-backend python -m app.services.importar_anh --departamento tarija
```

- **Fuente:** `https://www.anh.gob.bo/w2019/contenido.php?s=40&R=<actividad>&D=<departamento>` (el sitio redirige a
  `/w2026/`; se sigue sólo dentro de `www.anh.gob.bo`). `R=1` es combustibles líquidos en estación de servicio y `R=2`
  GNV: la misma estación aparece en las dos y se une en una fila. Dos pedidos por departamento, con 2 s de pausa y
  un User-Agent genérico (`URUKU-importador/1.0`).
- **Departamentos (`D=`)**, tal como los enlaza la propia página: 1 Chuquisaca, 2 La Paz, 3 Cochabamba, 4 Oruro,
  5 Potosí, 6 Tarija, 7 Santa Cruz, 8 Beni, 9 Pando. `--departamento` acepta el slug (`santa-cruz`, `potosi`).
- **Ciudad:** la ANH no trae municipio (la columna «Ubicación» repite el departamento). Se asigna por el municipio
  que abre la dirección (`YACUIBA, AVDA…`) y, si no, por el punto dentro del radio de la ciudad (los de `RADIOS` de
  Overture). Lo que no cae en una ciudad de la tabla `ciudades` se cuenta como `fuera_de_ciudad`: no se inventa una.
- **Punto:** la página sí trae uno por estación (`setMark`). Entra como `ubicacion='aproximada'`, a confirmar. Con
  `--sin-punto` se ignora y la fila sale sin punto, para el ubicador (`python -m app.services.ubicar_direccion
  --ciudad tarija`, que también levanta las de `anh`; `--rehacer` no les toca el punto que trajo la ANH).
- **Rubro:** `estacion-servicio` (migración 0076). Teléfonos: los fijos vienen con 7 dígitos y se les antepone el
  código de área del departamento; un celular va a `whatsapp`, un fijo a `telefono`.
- **Repetidos:** por teléfono o por nombre parecido (cerca, o en la misma ciudad si no hay punto): se marca
  `duplicado_de`. Volver a correrlo no duplica: la `fuente_id` es `anh:<departamento>:<código de licencia>` (sin el
  «LIC09/2026», que cambia en cada renovación).
- **Promover:** como una tarjeta (el teléfono y la dirección que quedaron revisados), pero una estación **no** se
  promueve sin punto.
- Si la ANH cambia el diseño de la página (no hay tabla o faltan columnas) el comando sale con error 1 y no carga nada.

### Aduana: cómo se corre

Oficinas de la Aduana Nacional (fronteras, aeropuertos, aduanas interiores, gerencias regionales; `fuente='aduana'`),
todo el país en una corrida. Entran a Importados como `estado='nuevo'`; nada se publica solo.

```bash
docker exec buscadonde-backend python -m app.services.importar_aduana --dry-run
docker exec buscadonde-backend python -m app.services.importar_aduana
```

- **Antes del primer deploy: correr la migración 0199** (`0199_rubro_aduana.sql`: el rubro NO comercial `aduana`) con
  `--sql`, como las demás. Sin ella el comando funciona, pero las filas quedan sin rubro y la persona lo tiene que
  elegir a mano. La clave de ícono que necesita el frontend (`IcRubro`) es `aduana`.
- **Fuente** (el `robots.txt` sólo bloquea `/admin`, `/search` y el login): `https://www.aduana.gob.bo/pagina-de-direcciones`
  (4 páginas, `?page=N`: nombre, dirección, teléfono y el punto del mapa) y `https://www.aduana.gob.bo/horariosAduana`
  (una tabla por gerencia: oficina, lugar de atención y horarios). Cinco pedidos con 2 s de pausa y un User-Agent
  genérico (`URUKU-importador/1.0`). Sólo se toman los datos y el enlace de origen: ningún texto de la página se copia.
- **Qué se guarda:** nombre de la oficina, dirección, teléfono, **horario** (una línea: `Lugar: lunes a viernes 8:30 a
  16:30; sábado… · Otro lugar: …`; el detalle por lugar queda en `tags.aduana.horarios`), tipo en `subcategoria`
  (Frontera, Interior, Aeropuerto, Postal, Zona franca, Gerencia regional…) y el enlace en `fuente_url`. Las oficinas
  que sólo figuran en la página de horarios (sin dirección) no entran: el resumen dice cuántas son.
- **Ciudad:** la que nombra la oficina («Aduana Frontera Bermejo») o es el primer o el último tramo de su dirección
  (un «Carretera a Oruro» es un camino, no la localidad); si no, la que contiene su punto. Lo que no cae en una ciudad
  de la tabla `ciudades` se cuenta como `fuera_de_ciudad`: no se inventa una (Tambo Quemado, Pisiga, Patacamaya…).
  Un nombre que el punto contradice (Cañada Oruro está en el Chaco, no en Oruro) tampoco vale.
- **Punto:** el de la Aduana (el marcador de OpenStreetMap de cada tarjeta) entra como `aproximada`, a confirmar, sólo
  si queda a menos de 25 km de su ciudad. Algunas oficinas copian el punto de otra: ese punto no decide la ciudad.
  Con `--sin-punto` se ignora; las que quedan sin punto las levanta el ubicador
  (`python -m app.services.ubicar_direccion --ciudad X`, que también toma `aduana`; `--rehacer` no les toca el que
  trajo la Aduana).
- **Teléfonos:** siempre a `telefono`, nunca a `whatsapp` (es el número para llamar). Se descartan el fax y los
  internos; un fijo de 7 dígitos lleva el código de área que escribe la página o el del departamento.
- **Repetidos:** por teléfono o por nombre parecido en la misma ciudad (`duplicado_de`). Volver a correrlo no
  duplica: la `fuente_id` es `aduana:<nombre de la oficina>`.
- **Promover:** como un lugar no comercial (`para-visitar`, docs/lugares-turismo.md): sin plan, sin WhatsApp (sólo si la
  persona lo escribe), `confiable = false`, el rubro queda como revisado y se copian horario, subcategoría y enlace.
- Si la Aduana cambia el diseño (no hay tarjetas o falta la tabla de horarios) el comando sale con error 1 y no carga nada.

## Fases

1. **Hecha.** `geocache` (migración 0198), usado por todo `buscar_direccion` cuando recibe `repo`. Guarda la respuesta
   cruda: los filtros se aplican después. Si la tabla no está, ubica igual sin caché.
2. **Hecha.** Lector de **Overture** por ciudad (el salto grande de datos), con dependencia nueva `duckdb`: es la única forma
   razonable de leer GeoParquet de S3 por caja sin bajar el mundo entero. Entra como fuente `overture` a Importados,
   marcando repetidos contra comercios y OSM.
3. Vigía común: comparar, cambios, ausentes, corridas, comando a mano y loop apagado. Primero para `turismo`
   y `overture`.
4. Panel «Novedades de fuentes».
5. OSM diario, y el paso «por nombre» contra los datos locales (OSM y Overture) antes que Nominatim.
6. Fichas de «Qué hacer» (horario) y ANH.
