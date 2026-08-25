# Clasificación por IA — qué hace, qué salió mal y el prompt vigente

> Documento vivo. Cada vez que se toque el prompt de `backend/app/services/vision.py`,
> **se actualiza la copia de acá abajo** y se anota qué se cambió y por qué.
>
> Última actualización: **2026-08-25** · 270 comercios activos, los 270
> analizados. La tercera salida (67 comercios del 24/8) fue la primera con el
> prompt completo: ver §2.7.

---

## 1. Qué hace la IA hoy

Mira **1 a 3 fotos** de la fachada o la vidriera y devuelve, en un solo JSON:

| Campo | Para qué sirve |
|---|---|
| `nombre_cartel` | El nombre del local, leído del cartel. **Sólo se escribe si el comercio no tiene un nombre real** — lo que tipeó una persona nunca se pisa |
| `productos` | Lo que se ve. Es la base del buscador y del control de calidad de los rubros |
| `descripcion` | Una o dos frases. Se regenera en cada análisis |
| `subcategoria` | El tipo específico de negocio |
| `sinonimos` | Producto → otras formas de decirlo. Alimentan el diccionario compartido |
| `rubro_slugs` | Las categorías. Varias por comercio |
| `categoria_sugerida` | Un rubro que falta en la taxonomía |
| `confianza` | Cuánto de lo dicho está realmente visible |

**Lo que nunca toca:** `prod_obs_human` (lo que escribió el agente en la calle) y el
nombre cuando ya hay uno de verdad.

---

## 2. Lo que salió mal — clasificación de rubros

Medido el **2026-08-23** cruzando los rubros asignados contra los productos que la
misma IA escribió (`supabase/verificar_rubros.sql`). El diccionario
`rubro_palabras` dice qué palabra corresponde a qué rubro; si ningún producto del
comercio sugiere el rubro que tiene, es un candidato a error.

### 2.1 El patrón: rubros amplios usados como cajón de sastre

No fueron errores sueltos. **Dos rubros concentraban el problema:**

| Rubro | Asignado a | Sin respaldo | % |
|---|---|---|---|
| 🛒 Supermercado y alimentos | 25 | **22** | **88%** |
| 🛏️ Hogar, blanco y decoración | 25 | **15** | **60%** |
| 🧸 Juguetería, librería y escolar | 25 | 8 | 32% |
| 🔌 Electrodomésticos | 29 | 9 | 31% |
| 👶 Bebés y niños | 20 | 7 | 35% |

Casos concretos: una **lencería** clasificada como "Supermercado y alimentos". Una
**juguetería** también. En "Hogar" cayeron locales que venden ollas, sartenes y
termos — eso es **Bazar y cocina**.

**Causa:** la IA sumaba un rubro amplio *encima* del específico que ya había
elegido bien. Un rubro de más no es un dato extra: es un local apareciendo en una
búsqueda que no le corresponde. El comprador filtra por "alimentos", recibe una
lencería, y deja de confiar en el filtro — más caro que no encontrar nada.

**Corregido en el prompt** (ver §4, regla de `rubro_slugs`) el 2026-08-23.

**Y ya está limpio en los datos.** Verificado el 24/8 comparando contra el
informe: `alimentos` pasó de 25 asignaciones (22 sin respaldo) a **4**, y `hogar`
de 25 (15 sin respaldo) a **10** — y **ningún otro rubro perdió una sola
asignación**. El total bajó de 542 a 507: exactamente los dos cajones de sastre.

Esa verificación importó por algo más: confirmó que `set_comercio_rubros()`, que
REEMPLAZA el conjunto entero, no se había llevado puesta clasificación buena.

### 2.2 El falso positivo: los servicios

Cuatro rubros aparecen al **100% sin respaldo** y **no están mal**:

| Rubro | Asignado a | Sin respaldo |
|---|---|---|
| 💱 Cambio de moneda | 5 | 5 |
| 🍽️ Restaurantes | 2 | 2 |
| 💈 Peluquería y barbería | 1 | 1 |
| Gomería / Repuestos | 1 | 1 |

Un **servicio no tiene mercadería en la vidriera**, así que por construcción nunca
va a tener respaldo en los productos. Ese 100% es un defecto de la verificación,
no de la clasificación.

De hecho "Cambio de moneda" en una tienda de ropa **probablemente esté bien**:
Bermejo es frontera y la IA leyó el cartel de compra y venta de pesos. Por eso
`limpiar_rubros.py` **excluye los rubros de servicio** aunque se los pasen a mano.

### 2.3 Lo que sí funcionó

- **Multi-rubro:** promedio **2,69 rubros por comercio** (43 con uno, 61 con dos,
  51 con tres). Era el motivo de existir de `comercio_rubros` y anda.
- **Subcategorías:** cero desacuerdos con su rubro (sección 6 del informe, 0 filas).
- **Cobertura:** sólo **1 comercio de 203** quedó sin ningún rubro real.
- **Rubros faltantes:** 78 repartidos (regalería 21, deportes 12, ferretería 10).
  No ensucian búsquedas, dejan al local afuera de un filtro. Se completan con
  `backend/scripts/completar_rubros.py`.

### 2.4 La taxonomía: cuatro rubros que faltaban y 19 que sobraban

Revisado el **2026-08-24** cruzando tres fuentes que coincidieron: la revisión a
mano de los comercios, lo que la IA venía pidiendo en `categoria_sugerida`, y las
subcategorías que ella misma escribió.

**Creados** (migración 0057), cada uno con sus palabras en `rubro_palabras` — sin
eso `rubros_sugeridos()` nunca los devuelve y quedan como filtros vacíos:

| Nuevo | Antes caían en |
|---|---|
| 🧳 Marroquinería y equipaje | `bolsos` — valija y cartera son lo mismo sólo si uno no viaja |
| 🍬 Kiosco y golosinas | `alimentos`, junto a los supermercados |
| 🩲 Lencería, medias y ropa interior | `ropa` (110 comercios: un filtro que no filtra) |
| 🛏️ Blanquería y textil de hogar | `hogar`, mezclado con muebles y decoración |

**NO se crearon** aunque estaban propuestos, porque ya existen con otro nombre:
"Bazar y Electrohogar" son `bazar` + `electrodomesticos` (dos rubros, no uno),
"Cotillón" es `regaleria`, "Herramientas" es `ferreteria`, "Ropa Deportiva" es
`ropa` + `deportes`. **Un rubro que duplica a otro es peor que no tenerlo:** el
comprador no sabe cuál tocar y los locales se reparten entre los dos.

**Apagados**: los 19 rubros sin comercios no eran categorías faltantes sino
basura del modelo anterior a URUKU — ocho son **ciudades argentinas** usadas como
rubro (`la-quiaca`, `oran`, `jujuy`, `salta`…) y el resto duplica rubros
vigentes. Se desactivan, no se borran, y sólo los que no tienen ni un comercio.

### 2.5 Correcciones del diccionario

| Fecha | Cambio | Por qué |
|---|---|---|
| 24/8 | Sacar `papas fritas` y `snack` de `kiosco` | Pertenecen a comida rápida. Metían a las rotiserías en kiosco. Acertó una vez —Sandwich dioni ES un kiosco— y por la razón equivocada, que es lo que hace que nadie lo revise |
| 24/8 | `sanguche`, `sanguchería`, `sandwichería` → comida rápida | Es como se escribe acá; el patrón sólo tenía "sandwich" |
| 24/8 | `quiosco`, `kiosquito`, `kioskito`, `kiosquería` → kiosco | "El Kiosquito de Ana" no clasificaba, y ése es el caso más frecuente |
| 24/8 | Rubro `bebidas` renombrado a **"Bebidas y licorería"** | `licor` ya clasificaba, pero buscar "licorería" no devolvía la categoría: el buscador matchea contra el NOMBRE del rubro y ese nombre no la nombraba |

**El mapa de kioscos vale por sí solo**: son los comercios más repartidos, los
que están abiertos cuando no hay nada más, y los que alguien busca parado en la
vereda.

### 2.6 Historial de cambios del prompt

| Fecha | Cambio | Por qué |
|---|---|---|
| 2026-08-22 | `categoria_sugerida` | El prompt obligaba a elegir de la lista, así que `rubros_propuestos` estaba vacío y parecía que no faltaban rubros |
| 2026-08-22 | `sinonimos` como objeto producto→palabras | Como lista suelta no se podía saber a qué producto pertenecía cada palabra, y no alimentaba el diccionario compartido |
| 2026-08-22 | `subcategoria` en singular y sin "X y Y" | "bolsos y mochilas" y "mochilas y bolsos" se contaban como dos categorías |
| 2026-08-23 | `nombre_cartel` | El nombre es el único dato que no se deduce de nada más. 100 de 203 comercios sin nombre |
| 2026-08-23 | Regla contra rubros amplios redundantes | El problema de §2.1 |

El prompt **no cambió desde el 2026-08-23**.

### 2.7 El prompt completo, medido: la tercera salida

Los 67 comercios del 24/8 fueron los primeros analizados con el prompt entero, y
el resultado se puede comparar contra las dos tandas anteriores:

| | Antes | Tercera salida |
|---|---|---|
| Sin nombre real | ~100 de 203 | **3 de 67** |
| Fotos sin mercadería detectada | — | **0** |
| Comercios en "Otros" | — | **0** (36 rubros repartidos) |
| Términos nuevos con sinónimos | — | 253 de 258 |

**`nombre_cartel` era el cambio que más valía y se confirmó.** El nombre es el
único dato que no se deduce de nada más: sin él hay que volver caminando hasta el
local. Pasó de faltar en la mitad de la base a faltar en tres locales.

Lo que NO resolvió: **ocho comercios quedaron llamados "Zapatillas Americanas"**,
nueve "Kiosko", y hay "Ropa", "Licoreria", "Muebleria". La regla está escrita en
el prompt —si lo que se ve es un rubro y no un nombre, va vacío— y aun así
entraron. Es peor que el nombre vacío: parece un dato bueno, así que nadie
vuelve a revisarlo, y en la lista de resultados los ocho son indistinguibles.

Y quedó a la vista un pendiente que no es de la IA: **43 de los 67 sin
WhatsApp**. La ficha existe y no lleva a ningún lado.

### 2.8 El diccionario de rubros: dos errores de fondo (2026-08-25)

Medido con `supabase/auditar_diccionario.sql`, que muestra **qué patrón** disparó
cada propuesta de `completar_rubros.py` y **con qué fragmento de texto**. El
script decía a quién y qué rubro, pero no por qué — y un patrón es una alternancia
de veinte términos, así que corregir el diccionario sin eso era adivinar.

**(a) Partir un rubro es MOVER el vocabulario, no copiarlo.** La 0057 creó
`lenceria`, `marroquineria` y `blanqueria` para descongestionar `ropa` (110
comercios), `bolsos` y `hogar` — pero no les sacó esas palabras a los rubros
padres. El patrón de `hogar` seguía siendo, palabra por palabra, el de
`blanqueria`. Cada blanquería disparaba hogar y cada marroquinería disparaba
bolsos: los rubros nuevos no descongestionaron, **duplicaron**. Corregido en la
**0061**, que además arregló `calza` (matcheaba "calzado" por falta de cierre de
palabra) y sumó `fedex`/`dhl` a `envios` — el único courier de la base figuraba
como marroquinería, por "morral".

**(b) Una palabra que también es adjetivo no alcanza para clasificar.** Con el
fragmento al lado de lo que el comercio vende, los errores se leen solos:

| Comercio | Le agregaba | Por | Vende |
|---|---|---|---|
| Perfumería Arabia | ferretería | `led` | perfume… **aro de luz** |
| Comercio 5G57 | ferretería + juguetería | `pintura`, `lapiz` | **pintura** de uñas, **lápiz** labial |
| MAREN IMPORTADORA | ferretería | `construccion` | bloques **de construcción** |
| Comercio W24Q | motos | `casco` | **casco** de soldar |
| Farmacia popular | blanquería | `toalla` | **toallita** higiénica |

`led` no nombra una ferretería: es el adjetivo de "aro de luz LED", y todo local
de accesorios de celular tiene uno — cuatro de las nueve propuestas de ferretería
salían de ahí. Corregido en la **0062**: o la palabra va acompañada ("foco led",
"material de construcción", "casco de moto"), o se la cierra con `\M`.

**Lo que queda pendiente antes de aplicar nada**, en
[pendientes-uruku.md](pendientes-uruku.md): medir cuánto ruido mete el blob de
sinónimos al clasificar, y el umbral de ≥4 palabras para los rubros de
especialización. **`completar_rubros.py` sigue sin aplicarse**: el diccionario
está corregido pero no movió un solo rubro de un solo comercio.

**Cómo no volver a caer:** `rubro_palabras` no lo lee el sitio —ni el buscador,
ni el mapa, ni las fichas—, sólo los informes y `completar_rubros.py`. Eso lo
hace barato de corregir, y también explica por qué estos dos errores convivieron
meses sin que nadie los notara: no rompen nada hasta que alguien corre el script.

---

## 3. Cómo verificar (sin gastar tokens)

```bash
cd /docker/uruku
# ¿los rubros coinciden con los productos?
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d postgres -f - < supabase/verificar_rubros.sql

# ¿el buscador encuentra lo que se cargó?
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d postgres -f - < supabase/cobertura_buscador.sql

# ¿qué trajo la última salida al campo?
docker compose -f docker-compose.prod.yml exec -T postgres \
  psql -U postgres -d postgres -f - < supabase/novedades.sql
```

**Cómo NO leerlo:** `rubro_palabras` es un diccionario escrito a mano y está
incompleto. "Sin respaldo" **no prueba** que el rubro esté mal — puede faltar la
palabra. Si un rubro aparece entero en la lista, sospechá del diccionario antes
que de la IA.

---

## 4. El prompt vigente

> Copia literal de `backend/app/services/vision.py` → `_prompt()`, al 2026-08-23.
> **Si se cambia el código, se cambia acá.**

```
Sos un relevador de comercios en Bermejo, Bolivia — una ciudad de frontera.
Mirás fotos de la fachada o la vidriera de un local y decís qué vende.

Devolvé SOLO un JSON, sin markdown, con esta forma exacta:
{
  "nombre_cartel": "lo que dice el cartel del local, tal cual está escrito",
  "productos": "lista de 4 a 8 productos separados por coma, en singular y en la palabra que usaría un cliente",
  "descripcion": "una o dos frases sobre el negocio, en español rioplatense, sin adjetivos publicitarios",
  "subcategoria": "el tipo específico de negocio en 1 o 2 palabras (ej: peluches, celulares, ropa de bebé)",
  "sinonimos": {"producto": "otra forma, otra forma mas"},
  "rubro_slugs": ["slug1", "slug2"],
  "categoria_sugerida": "",
  "confianza": 0.0
}

Reglas:
- `rubro_slugs`: SOLO slugs de la lista de abajo. Todos los que apliquen — un local
  que vende neumáticos y también zapatillas lleva los dos. Si no podés determinar
  ninguno, devolvé [].
  Cada rubro tiene que corresponder a algo que se VE en la foto. No agregues uno
  amplio "por las dudas" encima de otro más específico que ya lo cubre: un local
  de ollas y sartenes es "bazar", NO "bazar" + "hogar"; una lencería es "moda",
  NO "moda" + "alimentos". Un rubro de más no es un dato extra, es un local
  apareciendo en una búsqueda que no le corresponde — el comprador filtra por
  esa categoría y recibe algo que no tiene nada que ver.
  Entre dos rubros que se solapan, elegí el más específico y dejá el otro.
- `categoria_sugerida`: si el negocio NO encaja bien en ninguno de los rubros de
  la lista, o si merecería una categoría más específica que la que elegiste,
  escribí acá el nombre que le pondrías (2 o 3 palabras, en singular). Si la
  lista lo cubre bien, dejalo vacío. Es para detectar qué categorías le faltan
  al sistema, así que no fuerces: sugerí sólo cuando de verdad falta algo.
- `nombre_cartel`: leé el cartel, la marquesina o la vidriera y transcribí el
  NOMBRE del negocio tal cual está escrito, respetando mayúsculas y
  abreviaturas. Es el dato que no se puede deducir de ninguna otra forma: si no
  está acá, hay que volver caminando hasta el local a copiarlo.
  Poné "" si no se lee, si dudás, o si lo que ves es un rubro y no un nombre
  ("ROPA", "BAZAR", "MODA Y ROPA" son lo que vende, no cómo se llama).
  Un nombre inventado es peor que ninguno: queda escrito como si fuera cierto y
  nadie vuelve a revisarlo. Ante la duda, vacío.
- `productos`: SOLO lo que se ve en las fotos. No completes con lo que "suele"
  vender un negocio así.
- `sinonimos`: Bermejo es frontera con Argentina, y cada producto se llama
  distinto de un lado y del otro. Es un OBJETO: una clave por cada producto que
  pusiste, y como valor las otras palabras con las que un comprador podría
  buscarlo — el término argentino, el boliviano, el genérico y el de marca si se
  usa como genérico.
  Ejemplo: {"remera": "polera, camiseta", "campera": "casaca, chamarra"}
  Va producto por producto y no una lista suelta porque estos sinónimos se
  guardan en un diccionario compartido: lo que aprendas de ESTA vidriera va a
  hacer que se encuentren todos los demás locales que venden lo mismo. Una lista
  sin saber a qué producto pertenece cada palabra no sirve para eso.
  Sólo palabras que nombren LA MISMA COSA: "remera" y "ropa" no son sinónimos,
  uno es la categoría del otro. Un sinónimo de más manda al comprador a un local
  que no tiene lo que busca, y eso es peor que no encontrar nada.
  Si un producto no tiene otra forma de decirse, no lo incluyas.
- `subcategoria`: en SINGULAR y con la palabra más común. Si se te ocurren dos
  términos unidos ("bolsos y mochilas"), elegí uno solo y mandá el otro en
  `sinonimos` — dos comercios iguales con la subcategoría escrita al revés
  quedan contados como categorías distintas y ninguna sirve de filtro.
- `confianza`: 0.0 a 1.0. Cuánto de lo que decís está realmente visible.
  Si la persiana está cerrada, hay poca luz, o sólo se ve un cartel sin
  mercadería, la confianza es BAJA (menos de 0.4) aunque el cartel diga el rubro.
  Preferí admitir que no ves a completar con lo probable.
- Si las fotos no muestran un comercio, devolvé confianza 0 y listas vacías.

Rubros disponibles:
{lista de los 54 rubros con su slug}
```

### Un segundo prompt: el diccionario de sinónimos

`backend/app/services/sinonimos.py` → `_prompt()`. **Sin imágenes** (por eso
cuesta centavos) y sobre el vocabulario agregado, no comercio por comercio.
Pide, para cada término, las otras palabras con las que alguien podría buscarlo
—argentino, boliviano, genérico y marca usada como genérico— con un máximo de 6
y la regla de que sólo valen palabras que nombren **la misma cosa**.

### Un tercero: revisión de la taxonomía

`backend/app/services/taxonomia.py` → `_prompt()`. Una sola llamada de texto
sobre el vocabulario agregado de todos los rubros. Devuelve propuestas de
`crear / dividir / fusionar / eliminar / renombrar`, con la evidencia que las
justifica. **No escribe nada:** cambiar la taxonomía reordena el mapa, los
filtros y las búsquedas de todos los comercios a la vez.

---

## 5. Costos medidos

| Operación | Costo | Notas |
|---|---|---|
| Análisis por fotos (1 comercio) | ~$0,003 | Modelo `gemini-flash-latest` |
| Los 203 comercios | ~$0,60 | |
| La tercera salida (67) | ~$0,20 | |
| Diccionario de sinónimos (697 términos) | centavos | Sin imágenes, 16 llamadas |
| Ampliarlo a 847 términos | centavos | **2 llamadas**: sólo pregunta lo que falta |
| Auditar el diccionario de rubros | **$0** | `auditar_diccionario.sql`, texto contra texto |
| Revisión de taxonomía | centavos | 1 llamada |
| Verificar rubros / cobertura / novedades | **$0** | SQL contra lo ya cargado |

La regla que salió de esto: **si el dato ya está escrito, no se le vuelve a
preguntar al modelo.** Los sinónimos, la verificación de rubros y los informes se
resuelven con texto contra texto.
