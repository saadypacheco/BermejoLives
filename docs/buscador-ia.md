# Buscador inteligente + clasificación de comercios — opciones y costos

> Objetivo: que cada local guarde **texto libre** (qué vende) y se **clasifique** en rubros,
> y que el **buscador entienda intención** ("algo para la tos" → farmacias), sin disparar
> los costos. Análisis para decidir; no implementado aún.

## Punto de partida (lo que YA existe)
- **Clasificación IA (Gemini)** en `backend/app/services/clasificador.py`:
  - `generar_texto_comercio(nombre, que_vende, rubros)` → descripción + **rubro inferido**.
  - `sugerir_rubros(descripcion, rubros)` → 1–3 rubros de un texto.
  - Graceful: sin `GEMINI_API_KEY` cae a fallback (no rompe).
- **Buscador full-text** (migración `0035_busqueda_unaccent`): columna `tsvector` generada
  (`spanish_unaccent`, stemming), índice GIN, RPC `buscar_comercios`. Matchea nombre +
  descripción + dirección + **nombre de rubro** + substring. Acento-insensible. Costo **$0**.
- **Analítica de búsqueda**: tabla `busqueda_comercios` (qué se busca → qué local se toca).

Conclusión: no partimos de cero. Lo que falta es (a) **datos** (texto rico por local + rubros
consistentes) y (b) **subir el escalón** del buscador de keyword a semántico, **solo si hace falta**.

---

## Parte 1 · Guardar texto + clasificar

**Modelo de datos sugerido** (por comercio):
- `descripcion` (ya existe) + un campo **`que_vende` / palabras clave** (texto libre del dueño).
- **rubros múltiples** (un local puede ser "ferretería + electrodomésticos"): tabla
  `comercio_rubros` (si no existe ya) en vez de un solo rubro.
- (Fase 2) `embedding vector` para búsqueda semántica (ver Parte 2).

**Opciones de clasificación:**
| Opción | Qué hace | Costo | Cuándo |
|---|---|---|---|
| **0 · Ya está** | Gemini en el alta (`generar_texto_comercio`) | ~1 llamada Gemini por alta (fracción de centavo) | Ahora: asegurar que se use SIEMPRE |
| **1 · Reproceso batch** | Reclasificar los comercios existentes con los rubros nuevos | N llamadas Gemini **una sola vez** (5–10k comercios = pocos USD) | Al fijar la lista oficial de rubros |
| **2 · Multi-rubro + confianza** | Gemini devuelve varios rubros con score | Igual que 0/1 | Cuando importe el filtrado fino |
| **Fallback $0** | Diccionario palabra→rubro (reglas) | Gratis, pero manual y frágil | Si no hay API key |

**Recomendación:** usar lo que ya existe en todas las altas + un **script de reproceso** una vez.
Costo casi nulo. Lo caro sería llamar a la IA por **búsqueda**, no por **alta** — evitarlo.

---

## Parte 2 · Buscador: 4 niveles (de barato a caro)

| Nivel | Qué es | Entiende | Costo infra | Costo por búsqueda | Veredicto |
|---|---|---|---|---|---|
| **0 · Full-text (HOY)** | `tsvector` unaccent + rubro + substring | palabras exactas/raíz ("vidri", "farmacia") | $0 (self-host) | $0 | Ya cubre ~70–80% |
| **1 · Full-text + sinónimos + typos** | Diccionario de sinónimos ("celu→celular", "remedio→farmacia") + `pg_trgm` (tolera errores de tipeo) | sinónimos y errores comunes | $0 (extensión Postgres) | $0 | **Mejor ROI. Recomendado ya** |
| **2 · Semántico (embeddings + pgvector)** | Cada local → un vector (de su texto); la query → un vector; se ordena por similitud | **intención/sinónimos automático** ("algo para la tos" → farmacias) | pgvector = gratis (extensión). Generar embeddings = **1 vez por local** (centavos) | Embeber la query: fracción de centavo, o **$0** con modelo local | **Fase 2. El salto "IA" real** |
| **3 · LLM interpreta la query** | Un LLM lee la búsqueda y arma la intención/categorías | intención compleja ("regalo para mi mamá") | — | **1 llamada LLM POR búsqueda** → caro y lento a escala | **Solo como fallback** cuando no hay resultados |

### La clave de costos
- **Costo por-local (una vez) = barato.** Clasificar y embeber 5–10k comercios una sola vez
  cuesta unos pocos USD y no se repite (solo al editar el local).
- **Costo por-búsqueda = peligroso.** Si cada búsqueda llama a un LLM (Nivel 3), a 1.000
  búsquedas/día eso sí pesa. Por eso el "cerebro" va en los **datos** (embeddings de los
  locales), no en cada consulta.
- **pgvector** corre en el **mismo Postgres self-host** → sin costo de infra nuevo.
- Los **embeddings de la query** se pueden generar con un **modelo local** en el VPS
  (ej. multilingual MiniLM) → **$0 por búsqueda**; o con la API de Gemini (centavos por millón).

### Números de referencia (orden de magnitud)
- Clasificar 5.000 comercios con Gemini Flash: **~pocos USD, una vez**.
- Embeber 5.000 comercios: **~centavos, una vez** (y al editar).
- Búsqueda semántica con embeddings: **~$0 corriente** si la query se embebe local o se cachea.
- LLM por cada búsqueda: **evitar como default** (ahí está el gasto que escala).

---

## Recomendación faseada
1. **Ahora (casi $0):**
   - Campo `que_vende`/palabras clave por local + **rubros múltiples**.
   - Usar la clasificación Gemini existente en **todas las altas** + **reproceso batch** una vez.
   - Subir el buscador a **Nivel 1**: sinónimos (diccionario curado a mano, corto) + `pg_trgm` (typos).
   - Esto cubre la enorme mayoría con costo casi nulo.
2. **Fase 2 (costo bajo, es el salto "IA"):** **embeddings + pgvector** para búsqueda semántica.
   Híbrido: full-text primero, semántico para reordenar / cuando el full-text trae poco.
   Embeddings de la query con modelo local → $0 por búsqueda.
3. **Fase 3 (opcional):** LLM interpretando la query **solo como fallback** cuando no hay
   resultados (raro), nunca en cada búsqueda.

## Riesgos / a tener en cuenta
- **Calidad de datos > algoritmo**: sin buen texto por local, ni la IA ayuda. Priorizar que el
  dueño escriba "qué vende" (o generarlo por WhatsApp — ver idea de ingesta desde WhatsApp).
- **Rubros consistentes**: definir la lista oficial (alineada a las categorías de la home) antes
  de reprocesar, para no clasificar dos veces.
- **Latencia**: full-text y pgvector son milisegundos; LLM-por-query agrega segundos → mala UX.
- **Presupuesto Bermejo**: mantener el costo **por-local (una vez)**, no por-búsqueda.

Relacionado: idea de **producción de contenido desde WhatsApp** (el dueño manda audio/fotos →
se transcribe y se arma el texto del local) — encaja perfecto como fuente del texto a clasificar.
