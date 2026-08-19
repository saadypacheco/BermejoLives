# Videos promocionales — URUKU + Reservalo

Dos videos verticales (9:16, ~35–45 s) para lanzamiento en Bermejo:

- **Video A — Comercios y servicios** → convencer al local de publicar en URUKU (gratis) y vender en la tienda.
- **Video B — Compradores** → que el vecino use URUKU para encontrar comercios y ofertas.

Cada escena está numerada igual que los PNG que genera
[`scripts/capturas-videos.mjs`](../scripts/capturas-videos.mjs), así el montaje es 1:1.

**Formato:** 1080×1920, 30 fps. **Tono:** cercano, bolivianísimo, energía de mercado.
**Paleta:** dorado URUKU + verde. **Música:** cumbia/andina moderna, upbeat, sin voz.
**Voz en off:** opcional (si no, los textos en pantalla cuentan la historia solos).

> Cómo se usan las dos opciones que pediste:
> 1. **Screenshots + guion** → corré el script de capturas, y montás las escenas con los textos y tiempos de las tablas de abajo (CapCut / Premier / lo que uses).
> 2. **Video con IA (texto→video)** → usá los *Prompts IA* de cada escena en tu herramienta (Runway, Pika, Sora, Kling, Veo). Los prompts describen el plano; encima ponés el screenshot real o el mockup como overlay.

---

## 🎬 Video A — Para comercios y servicios

**Gancho:** *"Que te encuentren."* · **Duración:** ~40 s · **CTA final:** `uruku.bo` + QR.

| # | Pantalla (PNG) | Texto en pantalla | Voz en off | Dur |
|---|---|---|---|---|
| A1 | `01-home` (mobile) | **¿Tenés un negocio en Bermejo?** | "¿Tenés un negocio en Bermejo?" | 3 s |
| A2 | `02-mapa` (zoom out → pines por rubro) | **Todos te buscan acá.** | "Tus clientes ya están buscando en el mapa." | 4 s |
| A3 | `02-mapa` (zoom a un pin destacado) | **Aparecé en el mapa. Gratis.** | "Publicá tu local gratis y aparecé al toque." | 4 s |
| A4 | `04-ficha` (scroll: fotos, horario) | **Tu ficha completa** · fotos, horarios, redes | "Con tu ficha: fotos, horarios, redes." | 5 s |
| A5 | `04-ficha` (sección ofertas + botón WhatsApp) | **Te escriben directo** 💬 | "Y te escriben directo por WhatsApp." | 4 s |
| A6 | `05-tienda` + `06-tienda-productos` | **Subí tus productos y vendé online** | "Subí tus productos a la tienda y vendé online." | 5 s |
| A7 | mockup de plan (destacado/pin grande) | **Destacate** · Bs 150 / 250 / 400 | "¿Querés destacar? Elegí tu plan." | 4 s |
| A8 | `01-home` + logo URUKU + QR | **Publicá gratis → uruku.bo** | "Publicá gratis en URUKU. Bermejo te espera." | 4 s |

**Prompts IA (texto→video), por escena:**
- **A1** — "Vertical shot, a small shop owner in a market stall in a Bolivian border town, warm morning light, looking at their phone, hopeful, cinematic, shallow depth of field."
- **A2** — "Animated city map filling with glowing colored pins by category, top-down, gold and green accents, smooth zoom-out, modern app aesthetic."
- **A3** — "Close-up of one map pin growing and glowing (a 'featured' badge), other pins soft-focus around it, premium feel."
- **A4** — "Hand scrolling a business profile on a phone: photos gallery, opening hours, social icons; clean UI, gold accents."
- **A5** — "Phone screen: a WhatsApp chat opening from a store profile, message bubble animating in, friendly."
- **A6** — "Product grid of an online store on a phone, items sliding in, 'add to store' motion, e-commerce clean look."
- **A7** — "Three subtle plan cards floating, one highlighted in gold, minimal, premium SaaS style."
- **A8** — "URUKU gold wordmark logo reveal on dark-to-light background with a QR code, uplifting, call-to-action energy."

---

## 🎬 Video B — Para compradores

**Gancho:** *"Todo Bermejo en un mapa."* · **Duración:** ~35 s · **CTA final:** `uruku.bo` + "Instalá la app".

| # | Pantalla (PNG) | Texto en pantalla | Voz en off | Dur |
|---|---|---|---|---|
| B1 | `01-home` (mobile) | **Todo Bermejo en un mapa** 🗺️ | "Todo Bermejo, en un solo lugar." | 3 s |
| B2 | `02-mapa` (pines de colores por rubro) | **Encontrá lo que buscás, cerca** | "Encontrá comercios y servicios cerca tuyo." | 4 s |
| B3 | `03-buscar` (chips: 🟢 Abierto ahora, rubros) | **Filtrá: abierto ahora, por rubro** | "Filtrá por rubro o mirá qué está abierto ahora." | 4 s |
| B4 | `01-home` (rail de ofertas) | **Ofertas del día** 🔥 | "Descubrí las ofertas del día." | 4 s |
| B5 | `04-ficha` (fotos + estrellas + WhatsApp/llegar) | **Fotos, horarios y contacto** | "Mirá fotos, horarios y escribí o llegá con un toque." | 5 s |
| B6 | `05-tienda` (productos) | **Comprá en la tienda** 🛍️ | "Y comprá online desde la tienda." | 4 s |
| B7 | `01-home` (menú instalar PWA) | **Instalala como app** 📲 | "Instalala como app, sin descargar nada." | 4 s |
| B8 | logo URUKU + QR | **Entrá → uruku.bo** | "URUKU. Entrá y descubrí Bermejo." | 3 s |

**Prompts IA (texto→video), por escena:**
- **B1** — "Vertical hero shot of a lively small Bolivian city (Bermejo) from above transitioning into a phone map UI, warm, inviting."
- **B2** — "Colorful map pins by category (food, clothing, pharmacy, services) appearing across a city map, playful, quick."
- **B3** — "Finger tapping filter chips on a phone ('Open now', category chips), map results updating live, snappy."
- **B4** — "Horizontal carousel of daily offer cards with discount badges sliding across a phone screen, energetic."
- **B5** — "Business profile on a phone: photo gallery swipe, star rating, WhatsApp and directions buttons highlighted."
- **B6** — "Online store product grid on a phone, tapping a product, smooth e-commerce motion."
- **B7** — "Phone showing 'Add to Home Screen' PWA install prompt, app icon popping onto the home screen."
- **B8** — "URUKU gold wordmark logo with QR code, warm gradient, friendly closing."

---

## ✅ Antes de grabar / capturar
1. **Deploy Reservalo + reset de `tienda_config`** (prod y QA) para que la tienda muestre su marca real (Reservalo). Ver [pendientes.md] y el SQL de reset.
2. Confirmá que hay **comercios con foto, horario y al menos 1 oferta** cargados (si no, las tomas A4/A5/B4/B5 quedan pobres).
3. Corré las capturas:
   ```bash
   npm i -D playwright && npx playwright install chromium
   BASE=https://uruku.bo SLUG=<slug-lindo> node scripts/capturas-videos.mjs
   ```
4. Las pantallas con login (panel del comercio "subir producto", admin de la tienda) grabalas a mano logueado — el script solo hace las públicas.

## Notas
- Mantené los textos en pantalla **cortos** (máx. 5–6 palabras) — se leen en 2–3 s.
- Cerrá **siempre** con el logo dorado + QR + `uruku.bo`.
- Reusá A6/B6 (tienda) para mostrar que URUKU y la tienda son **el mismo ecosistema**.
