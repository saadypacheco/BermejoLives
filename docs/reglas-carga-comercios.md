# Reglas de carga de comercios + cómo capturar rápido en el campo

> Calidad de datos > algoritmo. Estas reglas definen QUÉ se carga y CÓMO, para que la
> clasificación y el buscador (ver [buscador-ia.md](buscador-ia.md)) funcionen bien y barato.
> Aplica a `/autoregistro` (dueño), `/publicador`, y sobre todo al **agente de campo**
> (que recorre Bermejo cargando locales — ahí la velocidad importa).

> **DECISIÓN (2026-08-16): sin taxonomías por ahora.** Se descarta la meta-clasificación
> por sub-rubros/atributos (Parte 2, Opción C). Se va con lo simple: **rubro(s) de lista
> cerrada + "qué vende" en texto/voz libre**, y la IA clasifica/embebe. La Parte 2 queda
> como evaluación registrada por si se retoma. Reglas de calidad (Parte 1) siguen vigentes.

## Parte 1 · Reglas de calidad (qué debe cumplir cada ficha)

**Obligatorios (sin esto no se publica):**
- **Nombre**: real, sin MAYÚSCULAS totales ni emojis. Normalizar (trim + Título).
- **Rubro(s)**: de la **lista oficial cerrada** (no texto libre). Mínimo 1, se permiten varios.
- **WhatsApp**: dígitos + código de país (`591…`). Anti-duplicado por WhatsApp.
- **Ubicación**: pin (lat/lng) o dirección. Sin esto no aparece en el mapa.

**Formato / normalización (automático al guardar):**
- WhatsApp/teléfono → solo dígitos + país. URLs de redes → absolutas (ya se hace).
- **Horario**: formato consistente (`Lun a Sáb 9–13 · 16–20`) → alimenta "Abierto/Cerrado".

**Fotos:** mínimo 1 portada real (no logo genérico, no captura).

**Flujo:** confiables publican directo; el resto pasa por moderación (humana o botón IA).

---

## Parte 2 · El dilema: rápido en el campo vs. texto rico para la IA

El agente que recorre no puede escribir un párrafo por local (lento). Pero el buscador
semántico necesita texto rico. Hay que resolver esta tensión. **Opciones a evaluar:**

| Opción | Cómo carga el agente | Velocidad | Riqueza p/ IA | Costo | Filtros (facetas) |
|---|---|---|---|---|---|
| **A · Solo texto libre** | Escribe "qué vende" | Lenta (tipeo) | Alta | $0 | Débiles |
| **B · Solo voz** | Dicta "qué vende" → Whisper transcribe | **Rápida** (hablar) | Alta | bajo (transcripción) | Débiles |
| **C · Taxonomía / tags** (la "tabla" meta-clasif.) | Toca rubro → chips de sub-rubro/atributos | **Muy rápida** (taps) | Media (vocabulario finito) | **$0** | **Fuertes** |
| **D · Foto + visión IA** | Saca foto de la vidriera/cartel → IA extrae productos | Muy rápida (1 foto) | Alta | medio (visión) | Medias |

### La "meta-clasificación tipo tabla" (Opción C) — cómo sería
Una **taxonomía en 3 niveles**, toda por selección (sin escribir):
1. **Rubro** (lista cerrada): Ropa, Farmacia, Electrónica, Ferretería, Mercado…
2. **Sub-rubro / tipo** (depende del rubro): Ropa → {mujer, hombre, niños, deportiva, calzado};
   Electrónica → {celulares, computación, audio, accesorios}; Farmacia → {medicamentos, perfumería, bebé}.
3. **Atributos transversales** (chips): `delivery`, `acepta QR`, `mayorista`, `reparación`,
   `factura`, `24hs`, `envíos a Argentina`.

- **Pro:** velocidad máxima en el campo, **consistencia total**, **$0**, y habilita **filtros/facetas**
  potentes ("farmacias con delivery", "mayoristas que hacen factura").
- **Contra:** vocabulario finito → no captura el long tail ("repuestos de moto Honda", "torta personalizada").

### ¿Sirve la taxonomía? Sí, pero NO sola
- Cubre el **80% común** + los **filtros** con costo cero y carga rapidísima.
- El **20% long tail** y la **búsqueda semántica** ("algo para la alergia") necesitan igual
  un poco de **texto/voz libre**.
- → No es "taxonomía O texto"; es **taxonomía + un texto corto opcional**.

---

## Recomendación: híbrido C + B (con D como atajo)
Flujo de alta del **agente de campo**, optimizado para velocidad:
1. **Nombre + WhatsApp + pin** (obligatorio, rápido).
2. **Rubro(s)** de lista cerrada (tap) → aparecen los **sub-rubros y atributos** relevantes (tap).
   *(Esto es la meta-clasificación tipo tabla — lo más rápido y ya deja la ficha usable + filtrable.)*
3. **"Qué vende" opcional por VOZ** (Whisper): 1 nota de voz de 10s → transcripción → alimenta
   clasificación + embedding. Para el long tail y el semántico.
4. **1 foto** de la vidriera (y opcional: visión IA para autocompletar productos del cartel).

Así: la **taxonomía** da velocidad + consistencia + facetas ($0), y el **texto/voz corto** da la
riqueza para el buscador inteligente. La IA (clasificar/embeber) corre **una vez por local**, no por búsqueda.

### Qué alimenta cada cosa
- **Filtros del mapa/buscador** ← taxonomía (rubro/sub-rubro/atributos). Instantáneo, $0.
- **Búsqueda por texto (full-text)** ← nombre + "qué vende" + rubros. Ya existe.
- **Búsqueda semántica (fase 2)** ← embedding de {nombre + qué vende + taxonomía}. Barato, 1 vez.

## Modelo de datos (implicaría)
- `rubros` = lista cerrada (tabla), **multi** por comercio (`comercio_rubros`).
- `sub_rubros` y `atributos` = tablas de taxonomía + relación M:N con comercio.
- `que_vende` = texto libre corto (de voz o tecleado).
- (Fase 2) `embedding` (pgvector) generado de todo lo anterior.

## A definir (siguiente paso)
- La **taxonomía concreta** por rubro (sub-rubros + atributos) para Bermejo — empezar por los
  rubros top (Ropa, Electrónica, Mercado, Farmacia, Ferretería) y crecer.
- Si el agente carga por voz, reusar el Whisper que ya está en URUKU + la idea de ingesta WhatsApp.
