# Lugares para visitar desde la página de turismo (spec corta + diseño, 12/11/2026)

Pedido del dueño: traer de https://tarijaturismo.com (Alcaldía de Tarija) los lugares que **no son comercios**:
plazas, parques y miradores; museos y bibliotecas; centros culturales; atractivos dentro y fuera de la ciudad;
áreas protegidas. Es la segunda parte de `docs/importar-turismo.md` (que trae los negocios con teléfono).

## Qué trae la página (medido el 12/11)

| Categoría del sitio (WordPress) | Lugares | Datos con rótulo en la ficha |
|---|---|---|
| `plazas-parques-y-miradores` | 16 (6 plazas, 6 parques, 4 miradores) | dirección; horario en varios («Abierto 24 horas») |
| `museos-y-bibliotecas` | 6 | dirección, teléfono, horario, precio de entrada |
| `dentro-de-la-ciudad` | 9 (4 iglesias; 5 de patrimonio: casonas, cabildo, pasaje) | dirección; a veces teléfono u horario |
| `centros-culturales` | 11 | dirección, teléfono |
| `fuera-de-la-ciudad` | 10 (comunidades, represa, observatorio, Cañón del Pilaya) | dirección vaga («San Jacinto»); horario en algunos |
| `fuera-del-municipio` | 10 (San Lorenzo, Valle de la Concepción, Chaguaya, Tajzara…) | «A 76 km de Tarija…»; horario |
| Página `areas-protegidas` | 3 (Sama, Tariquía, Aguaragüe; El Cardón figura sólo como «potencial») | nada estructurado |
| **Total** | **65** | |

- Cada lugar tiene su propia ficha (`/plaza-uriondo/`) con bloques rotulados: **Dirección, Teléfono, Entrada, Horarios**,
  y además **Reseña / Presentación / Información** (texto con autor) y fotos.
- **No hay coordenadas.** El mapa embebido de cada ficha es `maps.google.com/maps?q=<nombre>, Tarija` (texto, no
  lat/lng). El único par de números del HTML (`-21.534641, -64.734265`) es el enlace del pie a la oficina de turismo
  y se repite en **todas** las páginas: un lector que «tome las coordenadas del link de Google» les daría ese mismo
  punto a los 65. Resolver el `q=` con Google es usar datos de Google, y eso está prohibido (0066).
- Hay casi repetidos dentro del mismo sitio: «Concejo Municipal» y «Patio del Cabildo»; «Casa de la Cultura» y
  «Biblioteca de la Casa de la Cultura». Los decide quien revisa.
- Los **~62 negocios de «Qué hacer»** (complejos turísticos, bodegas, diversión nocturna, gimnasios, balnearios,
  diversión en familia) los trae `importar_turismo` (rubro sugerido o `turismo`). Ese importador **deja afuera** las
  6 categorías de lugar de esta tabla, así que nada entra dos veces.
- **Decisiones del dueño (12/11):** la ficha queda en `/comercios/<slug>` y los lejanos entran bajo Tarija.

## Decisiones

| # | Decisión | Alternativas descartadas | Por qué | La invalidaría |
|---|---|---|---|---|
| 1 | **Viven en `comercios` con un rubro no comercial nuevo, `para-visitar`** (`rubros.comercial = false`, como `banos` o `emergencias`: 0083, 0113). **No van a `lugares`.** | a) `lugares` con tipos nuevos. b) Tabla nueva `atractivos`. | El buscador, el mapa público, la ficha con ISR, el sitemap, las páginas ciudad+rubro (`/tarija/para-visitar`), la galería que carga el agente e Importados → Promover ya existen para `comercios`. `lugares` es otra cosa: el **contenedor** de puestos (mercado o galería). No tiene slug, no tiene ficha y no aparece ni en el buscador ni en el mapa de `/buscar`. Con a) había que hacer todo eso nuevo, y además sacar los tipos nuevos de 5 lugares del código que hoy leen `lugares` sin filtrar (`elegir_lugar` en el autoregistro, `/campo/lugares`, el selector de mercado del alta, el asistente y el conteo de volúmenes). La 0113 ya deshizo una vez «lugares con tipo» para los puntos de la ciudad: «dos formas de cargar lo mismo es una que se mira y otra que se llena». b) suma lo mismo que a) y encima un ABM nuevo. | Que un lugar turístico tenga que **contener** puestos (una feria en una plaza): eso es una fila de `lugares`, que puede convivir con el punto. O que haga falta contenido editorial (circuitos, varios idiomas, galería curada por lugar): ahí sí, modelo propio. |
| 2 | **Un solo rubro; el tipo va en `subcategoria`**, con una lista fija: Plaza · Parque · Mirador · Museo · Biblioteca o archivo · Iglesia · Patrimonio · Centro cultural · Excursión · Área protegida. | Un rubro por tipo, más un rubro «paraguas» para el filtro. | El turista entiende un solo filtro y el mapa usa un solo ícono. No queda un rubro paraguas que se olvida en las cargas a mano. Además el nombre ya dice qué es cada uno («Museo San Roque»). | Más de ~100 por ciudad, o el pedido de filtrar por tipo: se parte en rubros con una migración que lee `subcategoria`. |
| 3 | **Sala de espera: `comercios_importados`** con `fuente = 'turismo'`, más dos columnas nuevas (`subcategoria`, `fuente_url`). El destino lo decide el rubro. | Tabla propia, o un `destino = 'lugar'`. | Como el destino ya es `comercios`, no hace falta destino. Si un centro cultural resulta ser un bar, quien revisa le cambia el rubro y se promueve como negocio. Es la misma pantalla y el mismo botón. | La decisión 1. |
| 4 | **Se lee la API REST pública de WordPress** del sitio: 1 pedido para las categorías y 6 para los posts (`per_page=100`). De cada post se toman los bloques rotulados y **el resto se descarta**. Si la API se cierra, se leen las 65 fichas en HTML. | Leer los listados (traen el texto cortado) y después cada ficha: 70 pedidos. | 7 pedidos en vez de 70. Los rótulos son los mismos que en la ficha. robots.txt lo permite. | Que cierren la API: queda el plan B en HTML. |
| 5 | **Ubicación con Nominatim** (`tarjetas.buscar_direccion`): primero por **nombre**, después por dirección. Caja de **15 km** para las categorías de la ciudad y de **120 km** para «fuera…» y las áreas protegidas. Siempre queda `aproximada`; si no aparece, `no_encontrada`. **Nunca Google.** | Las coordenadas de los enlaces de Google. | No hay coordenadas propias del lugar, y las de Google no se pueden usar. En OSM las plazas, iglesias y museos están por nombre, y «entre calles» no lo resuelve nadie. | — |
| 6 | **Los teléfonos van a `telefono` y nunca a `whatsapp`.** Se normalizan igual que en tarjetas. | Pasar los celulares a WhatsApp, como en tarjetas. | Es el número que la Alcaldía publica para **llamar**, y puede ser el celular personal de un empleado. Un WhatsApp en URUKU además genera leads. Quien revisa lo puede pasar a mano si lo confirma. | Que el lugar confirme que atiende por WhatsApp. |
| 7 | **Derechos: sólo datos y el enlace.** Se toman nombre, dirección, teléfono y horario. No se toman la reseña, la presentación, la información, el precio de entrada (cambia) ni las fotos. La descripción, si hace falta, la escribe el equipo en el **`comercios.descripcion` que ya existe** (hasta 300 caracteres). El enlace va en una columna nueva y pública, **`comercios.fuente_url`**. | Una columna nueva de descripción. Copiar la reseña. | Los textos y las fotos tienen autor. Con el enlace, el turista puede ir a la página oficial para el detalle. | — |
| 8 | **La ficha es la de siempre (`/comercios/[slug]`, ISR de 300 s), con variantes para los rubros no comerciales.** No se crea `/lugares/[slug]`. | Una ruta nueva con SSG/ISR, sitemap y JSON-LD propios. | Ya cumple §7.9 y ya está en el sitemap y en las migas. Las variantes son pocas (ver Pantalla). | Que el dueño no quiera «comercios» en la dirección de una plaza: se resuelve con un alias de ruta más adelante, sin tocar datos. |
| 9 | **Los lejanos se importan colgados de Tarija** (confirmado por el dueño). El **encuadre** del mapa sólo usa los pines a 30 km o menos del centro de la ciudad. | No importarlos. Crearles una ciudad. | El dueño los pidió («fuera de la ciudad», «áreas protegidas»). Sin ese corte, una excursión a 100 km aleja el mapa hasta que la ciudad entera queda en un solo cúmulo. | Que se decida no mostrarlos (pregunta 2). |
| 10 | **Se corre a mano, una sola vez**, con un módulo aparte (`importar_turismo_lugares`). | Agregarle una opción a `importar_turismo`. | Ese archivo lo está escribiendo otro dev en paralelo. Más adelante se pueden unir. | — |

Path dependence: no entra ninguna tecnología nueva, así que la elección es interna al modelo. Elegir «`lugares`» por el
nombre y elegir «rubro no comercial» por el precedente de los baños son dos inercias, y se compararon por lo que da
cada una (decisión 1).
KB aplicada: `nunca-delete-fisico-siempre-soft` / `soft-delete-activo-flag` (descartar sin borrar),
`supabase-cloud-grants-explicitos-en-migration` (permiso por columna para `fuente_url`), `ssg-isr-en-catalogo-no-ssr-puro`
(la ficha ISR que ya existe), `supabase-service-role-key-nunca-en-frontend` (el importador corre en el backend).

**Lo que NO cambia:** la tabla `lugares`, `services/lugares.py` (`elegir_lugar`), `/campo/lugares`, Admin › Lugares y el
selector de mercado del alta. Los lugares turísticos nunca entran ahí, así que la asignación automática no los puede tomar.

## Uso

```
docker exec buscadonde-backend python -m app.services.importar_turismo_lugares --ciudad tarija --dry-run
docker exec buscadonde-backend python -m app.services.importar_turismo_lugares --ciudad tarija
```

- `--dry-run` lee y lista sin escribir y sin llamar a Nominatim.
- La corrida real hace como máximo unas 130 consultas a Nominatim, a 1 por segundo y con caché.
- User-Agent `URUKU/1.0 (+https://uruku.bo)` y 1 pedido por segundo también contra el sitio.

**Cómo se arma cada fila de la sala de espera:**

- `fuente='turismo'`.
- `fuente_id`: `turismo:tarijaturismo.com:post:<id de WordPress>`. Las áreas usan
  `turismo:tarijaturismo.com:area:<slug>`, y los 3 nombres van fijos en el módulo, con la URL de esa página.
- `categoria`: el slug de la categoría del sitio. `rubro_slug='para-visitar'`.
- `subcategoria`: sale de la categoría y de la primera palabra del nombre:
  - Plaza/Plazuela → Plaza; Parque → Parque; Mirador → Mirador.
  - Museo → Museo; el resto de `museos-y-bibliotecas` → Biblioteca o archivo.
  - Iglesia/Capilla/Catedral → Iglesia; el resto de `dentro-de-la-ciudad` → Patrimonio.
  - `centros-culturales` → Centro cultural; las dos «fuera…» → Excursión; las áreas → Área protegida.
- `nombre`, `direccion` (hasta 200 caracteres), `telefono` y `horario` (el texto tal cual).
- `fuente_url`: el link del post. `website` queda **vacío**, porque la página de turismo no es la web del lugar.
- `tags = {wp_id, categorias}`, **sin el contenido**.
- Ubicación según la decisión 5.
- `duplicado_de`: un comercio activo de la ciudad con nombre parecido y, si hay punto, a 200 m o menos.
- Es idempotente: con `(fuente, fuente_id)` ya existente, la fila no se toca (ni el estado ni lo que corrigió una persona).

## Migración `0196_lugares_para_visitar.sql`

Va con copia idéntica en `selfhost/postgres-init/`, en una sola transacción, con comprobación y `notify pgrst`.

```sql
-- 1. El rubro no comercial (sin emoji: el dibujo sale de IcRubro).
insert into rubros (slug, nombre, icono, orden, comercial)
values ('para-visitar', 'Para visitar', null, 62, false)
on conflict (slug) do update set nombre = excluded.nombre, comercial = false, activo = true;

-- 2. Palabras: sólo las inequívocas. «plaza», «parque» e «iglesia» NO van, porque
--    clasificarían mal a «Comercial Plaza» o «Parque Industrial». El nombre igual se
--    encuentra por texto.
insert into rubro_palabras (rubro_slug, patron) values
  ('para-visitar', '\m(museo|mirador|centro cultural|area protegida|reserva biologica|parque nacional|lugares turisticos|que visitar)')
on conflict (rubro_slug, patron) do nothing;

-- 3. El enlace a la página de origen: público (regla 11, permiso por columna).
alter table public.comercios add column if not exists fuente_url text;
comment on column public.comercios.fuente_url is
  'Página de origen de los datos (p. ej. la ficha en tarijaturismo.com). Sólo el enlace: su texto y sus fotos no se copian.';
grant select (fuente_url) on public.comercios to anon, authenticated;

-- 4. La sala de espera: privada como siempre (sólo service_role).
alter table public.comercios_importados add column if not exists subcategoria text;
alter table public.comercios_importados add column if not exists fuente_url   text;
grant all on public.comercios_importados to service_role;

-- 5. Comprobación: para-visitar existe con comercial = false; anon puede leer
--    comercios.fuente_url (has_column_privilege) y NO puede leer comercios_importados.
```

## Contrato

Todo con el permiso `datos` (el de Importados). Las lecturas públicas siguen siendo por PostgREST con anon.

| Método y ruta | Entrada | Salida |
|---|---|---|
| `GET /admin/importados?fuente=turismo&rubro=para-visitar` | filtro nuevo `rubro` (slug exacto) | el de siempre; cada item suma `subcategoria` y `fuente_url` (`categoria` ya estaba) |
| `PATCH /admin/importados/{id}` | suma `subcategoria?` (de la lista fija; 400 si no está) y `horario?` | el Importado actualizado (sólo si está `nuevo`) |
| `POST /admin/importados/{id}/ubicar` | sin cambios | sin cambios (caja de 15 km; para los lejanos el punto se pone a mano) |
| `POST /admin/importados/{id}/promover` | el de siempre (`nombre?`, `rubro_slug?`, `whatsapp?`) | Si el rubro final es **no comercial**: copia `telefono` (y `whatsapp` sólo si viene en el body), `horario`, `direccion`, `subcategoria` y `fuente_url`, y llama a `repo.marcar_rubro_revisado` para que lo masivo no le cambie el rubro. Nunca sale verificado ni confiable; `cargado_por='import:turismo'`. Sin punto, 400 (como hoy). |
| `GET /campo/mis-comercios` | — | cada item suma `comercial: bool` (el del rubro principal) |
| Anon: `comercios` | `COLUMNAS_COMERCIO` suma `fuente_url` | — |

## Pantalla

**Admin › Importados** (sobre lo que deja `importar_turismo`):

- Filtro **Turismo › Para visitar** (`rubro=para-visitar`).
- La tarjeta de revisión muestra:
  - un sello «Para visitar · ‹subcategoría›», con la subcategoría en un desplegable editable;
  - el enlace «Ver en tarijaturismo.com»;
  - el horario editable;
  - el mapa chico **centrado en el punto**, aunque quede lejos de la ciudad;
  - para Excursión y Área protegida, el aviso «Poné el punto en la entrada o en el centro de visitantes».
- «Promover» y «Descartar» como siempre.
- La descripción propia se escribe después, en el editor de siempre (Negocios).

**Sitio público:**

- **Acceso «Para visitar»** en la fila de accesos (`AccesosCiudad`, en el home y en los resultados), que lleva a
  `/buscar?rubro=para-visitar&vista=mapa`.
  - Sólo aparece si existe el par (ciudad, `para-visitar`) en `city_category_pages()`, que el home ya lee.
  - Sin números.
  - `lib/servicios.ts` suma la búsqueda «qué visitar / lugares turísticos / museos / miradores» → ese rubro.
- **Mapa** (`map-results.tsx`):
  - Pin con ícono propio (`ic.tsx` + `npm run iconos`) y color de una familia nueva «Para visitar» (`mapa-visual.ts`).
  - El globo no muestra la modalidad ni WhatsApp: nombre, subcategoría, «Cómo llegar» y «Ver lugar».
  - El encuadre sólo usa los pines a 30 km o menos del centro de la ciudad.
- **Ficha** `/comercios/[slug]`, para rubros no comerciales:
  - En lugar de «Este local no tiene WhatsApp cargado» dice «Es un lugar público: fijate cómo llegar acá abajo».
  - El QR dice «El QR de este lugar».
  - Muestra la subcategoría bajo el nombre, la descripción propia si hay, el horario y «Llamar» si hay teléfono.
  - Si hay `fuente_url`, suma «Más información en la página de Turismo de Tarija».
  - JSON-LD `TouristAttraction` (`RUBRO_SCHEMA_TYPE` en `lib/seo.ts`).
  - Los cambios de texto les sirven también a los baños, que hoy muestran el texto de un local.
- **Home, «N nuevos en 24 h»:** no cuenta los rubros no comerciales. **Esto tiene que estar en producción antes de
  promover el primer lugar.**

**App del agente («Qué hay acá»):** los puntos no comerciales aparecen, para que nadie los vuelva a cargar, pero sin
sello de plan, sin «Le falta» y sin «Ofrecer».

## Criterios de terminado

1. El dry-run lista **65** lugares (16 + 6 + 9 + 11 + 20 + 3), cada uno con nombre y subcategoría, sin escribir nada y
   sin llamar a Nominatim.
2. Correrlo dos veces no crea filas y no pisa lo que se corrigió a mano.
3. Ninguna fila trae reseña, foto ni el contenido del post en `tags`. `website` queda vacío. **Ninguna fila sale con
   el punto `-21.534641, -64.734265`.** No se descarga ninguna imagen.
4. Cada fila queda `aproximada`, con el punto dentro de la caja usada (15 o 120 km), o `no_encontrada` sin punto.
   La corrida informa cuántas quedaron de cada una.
5. Promover un lugar crea el comercio con:
   - rubro `para-visitar`, subcategoría, horario y `fuente_url`;
   - el teléfono en `telefono` y `whatsapp` vacío;
   - `cargado_por='import:turismo'`, no verificado, no confiable y el rubro marcado como revisado.
6. La ficha pública de ese lugar no dice «Este local no tiene WhatsApp» ni «QR de este negocio», muestra el enlace a la
   fuente y su JSON-LD es `TouristAttraction`.
7. En Tarija, `/buscar?rubro=para-visitar&vista=mapa` muestra los pines con su ícono, y una excursión a 76 km no le
   cambia el encuadre a la ciudad.
8. El acceso «Para visitar» sale en Tarija y no en Bermejo.
9. Promover lugares no mueve «N nuevos en 24 h».
10. `/campo/lugares`, `elegir_lugar` y Admin › Lugares devuelven lo mismo que antes.
11. La comprobación de la 0196 pasa (anon lee `comercios.fuente_url` y no lee `comercios_importados`).
    `test_comercios_columnas_publicas.py`, `tsc` y `next build` en verde. Sin emojis.
    Los tests del parser usan **textos inventados** con los mismos rótulos, nunca el HTML del sitio.

## Reparto (dos devs en paralelo, sin compartir archivos)

**Requisito previo para los dos: que esté mergeado `importar_turismo`.** Toca los mismos puntos: el filtro `fuente`,
`promover_importado` y `importados-panel.tsx`.

| backend-dev | frontend-dev |
|---|---|
| `supabase/migrations/0196_lugares_para_visitar.sql` + la copia en `selfhost/postgres-init/` | `components/importados-panel.tsx` |
| `services/importar_turismo_lugares.py` (nuevo) + `tests/test_importar_turismo_lugares.py` | `app/comercios/[slug]/page.tsx`, `lib/ficha-data.ts` (rubro comercial, `fuente_url`), `lib/seo.ts` |
| `services/tarjetas.py`: `buscar_direccion(..., radio_km=RADIO_CIUDAD_KM)` (el radio entra en la clave de la caché) | `lib/data.ts` (`COLUMNAS_COMERCIO` + `fuente_url`; «nuevos en 24 h» sin los no comerciales) |
| `api/moderacion.py`: filtro `rubro` en el listado y `promover_importado` | `components/accesos-ciudad.tsx` y quienes lo usan (`app/page.tsx`, `/buscar`), `lib/servicios.ts` |
| `api/importados_tarjetas.py`: el PATCH suma `subcategoria` y `horario` | `components/map-results.tsx` (globo y encuadre) |
| `db/repository.py`: `list_importados(..., rubro)` | `components/ic.tsx` + `npm run iconos`, `lib/mapa-visual.ts` (color y familia) |
| `services/que_hay_aca.py`: `comercial` en cada item | `components/que-hay-aca.tsx`, `components/ficha-agente.tsx`, `lib/campo.ts` (tipo) |

**Orden del deploy:**

1. La 0196.
2. El backend.
3. El frontend (con el arreglo de «nuevos en 24 h»).
4. El importador en dry-run, después la corrida real.
5. La revisión y la promoción en el panel.
