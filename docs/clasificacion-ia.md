# Clasificación por IA — qué hace, qué salió mal y el prompt vigente

> Documento vivo. Cada vez que se toque el prompt de `backend/app/services/vision.py`,
> **se actualiza la copia de acá abajo** y se anota qué se cambió y por qué.
>
> Última actualización: **2026-08-23** · 203 comercios relevados · 202 analizados.

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
**Lo ya cargado** se limpia con `backend/scripts/limpiar_rubros.py`.

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

### 2.4 Historial de cambios del prompt

| Fecha | Cambio | Por qué |
|---|---|---|
| 2026-08-22 | `categoria_sugerida` | El prompt obligaba a elegir de la lista, así que `rubros_propuestos` estaba vacío y parecía que no faltaban rubros |
| 2026-08-22 | `sinonimos` como objeto producto→palabras | Como lista suelta no se podía saber a qué producto pertenecía cada palabra, y no alimentaba el diccionario compartido |
| 2026-08-22 | `subcategoria` en singular y sin "X y Y" | "bolsos y mochilas" y "mochilas y bolsos" se contaban como dos categorías |
| 2026-08-23 | `nombre_cartel` | El nombre es el único dato que no se deduce de nada más. 100 de 203 comercios sin nombre |
| 2026-08-23 | Regla contra rubros amplios redundantes | El problema de §2.1 |

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
| Diccionario de sinónimos (697 términos) | centavos | Sin imágenes, 16 llamadas |
| Revisión de taxonomía | centavos | 1 llamada |
| Verificar rubros / cobertura / novedades | **$0** | SQL contra lo ya cargado |

La regla que salió de esto: **si el dato ya está escrito, no se le vuelve a
preguntar al modelo.** Los sinónimos, la verificación de rubros y los informes se
resuelven con texto contra texto.
