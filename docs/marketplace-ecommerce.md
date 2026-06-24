# Marketplace multi-vendedor — diseño (pensar antes de codear)

> "El ecommerce de buscadonde" = UNA instancia de la tienda en modo **marketplace
> multi-vendedor** (`reservalo.com`). Muchos comercios, un catálogo
> compartido, separados por `vendedor_id`. La tienda **per-cliente** (Amanda) sigue
> aparte como tenant aislado premium — mismo motor, otro deploy.
> Estado: 🧠 en discusión, sin código.

## Multi-tenant vs multi-vendedor (para que no se mezcle)
- **Multi-tenant** = tiendas **aisladas** (cada marca su data/dominio). Ya existe:
  deploy-por-cliente (Amanda). Un tenant no ve al otro.
- **Multi-vendedor (marketplace)** = **una** tienda con productos de **muchos
  vendedores** en un catálogo común. Es lo nuevo, para la masa de Bermejo.
- Conviven ambos. Mismo código, dos modos de deploy.

## Cómo se conectan (confirmado)
- Comercio carga producto **desde buscadonde** → buscadonde llama a la **API de
  servicio** de la tienda → producto creado con `vendedor_id` = `comercio_id`.
- buscadonde guarda solo la **referencia** en `producto_ref` (id en la tienda, url,
  quién lo cargó, fechas, link al destacado pago).
- **Corrección clave al análisis:** el `vendedor_id` viaja **por request** (buscadonde
  representa a CIENTOS de comercios), NO fijo en la config de la tienda.

## Decisiones (cerradas por el dueño 2026-06-22)

### D1 ✅ Identidad del vendedor en el ecommerce
Tabla nueva **`vendedores`** (`id` = `comercio_id` de buscadonde, `nombre`, `slug`,
`whatsapp`, `activo`). buscadonde la **sincroniza** (upsert) al cargar el 1er producto.
El comercio **NO necesita cuenta** en el ecommerce. `whatsapp` = a dónde va el carrito.

### D2 ✅ Productos simples, variantes opcionales — carga lo más simple posible
Son **mayoristas** y suelen decir "tengo **todas las talles**". Entonces:
- Producto **simple por defecto**: nombre, precio, 1–3 fotos, descripción. Sin talle/color.
- Opcional: marcar **"todas las talles"** o cargar **variantes** (talle/color) solo
  si el vendedor quiere (ropa/calzado).
- El stock del ecommerce vive en `variantes`: para el producto simple creamos **una
  variante "única"** por detrás (o stock a nivel producto), transparente para el vendedor.

### D3 ⚠️ Unificar taxonomía — UNA sola, fuente en buscadonde
Hoy hay **dos** y son **ejes distintos**: `rubros` clasifican el **negocio**
(importadora, gastronomía…); `categorias` del ecommerce clasifican el **producto**.
Plan: **una taxonomía canónica en buscadonde**.
- **MVP (simple):** la categoría del producto = el **rubro del comercio**, heredada
  automáticamente. El vendedor **no elige categoría** → carga mínima. El ecommerce
  recibe esa categoría por la API.
- **Después:** subcategorías de producto más finas si hace falta. (Tarea de diseño aparte.)

### D4 ✅ Carrito por-comercio, sin login (guest)
Carrito por comercio → WhatsApp al `whatsapp` del vendedor. Para que **no se vacíe**,
el comprador **no necesita loguearse**: el ecommerce ya **persiste el carrito en
localStorage** (Zustand) y soporta **checkout guest** (nombre + teléfono). Reusamos eso.

### D5 ✅ Gestión 100% desde buscadonde, con carga innovadora (NO el editor del ecommerce)
El dueño **descarta** el editor tradicional del ecommerce ("carga tradicional, quiero
algo mucho más simple"). El vendedor **se loguea solo en buscadonde** → su **dashboard**
muestra todo lo suyo (perfil, suscripción, contactos, **productos**). El ecommerce
**NO** tiene login de vendedor: es **almacén + vidriera** para el comprador.
- ✔️ Se cae el handoff/SSO/"modo vendedor" del ecommerce → arquitectura más simple.
- ✔️ El ecommerce solo expone: **API de servicio** (alta/edición de productos),
  **storefront `/v/{slug}`** y, opcional, un **clasificador** (categorizar texto libre).

### Carga de producto v1 (desde buscadonde) — definida por el dueño
Sin formulario tradicional. **Flujo exacto:**
1. El vendedor saca **1 a 3 fotos** (máx 3).
2. Escribe **título**, **descripción** (puede indicar **talles** como texto libre) y **precio**.
3. La **IA** hace **una sola cosa**: **inferir la categoría** a partir del título +
   descripción (TEXTO, sin visión) → elige **una de las categorías del ecommerce**.
   El vendedor no elige categoría.
4. **Preview** = la tarjeta tal cual la verá el comprador (fotos, título, precio,
   descripción, categoría inferida). El vendedor **corrige cualquier campo** ahí mismo.
5. **Confirmar → publicar:** API de servicio → `productos` del ecommerce + `producto_ref`.

- **Talles v1:** van en la **descripción** (texto), NO como variantes estructuradas.
- La IA (clasificación de texto, Gemini Flash) vive en **buscadonde** y elige de la
  **lista de categorías del ecommerce** (buscadonde la trae por `GET /api/servicio/categorias`).
  Con fallback gratis (categoría = rubro del comercio) si no hay key.
- v2: voz, variantes estructuradas, lista de precios → N productos (masiva).

### D6 ✅ Infra — instancia nueva
Levantar instancia NUEVA del ecommerce (Supabase + dominio `reservalo.com`).

### D7 ✅ Seguridad
API de servicio con **X-API-Key**; arreglar la auth de los endpoints de productos
(y sacar el `.env` commiteado) antes de exponer la instancia.

> *Nota: "tienda" = el ecommerce (marketplace).*

## Alcance etapa 1 (elegido: marketplace mínimo usable)
1. Tienda: tabla `vendedores` + `vendedor_id` en `productos` + API de servicio
   (`/api/servicio/vendedores/{id}/productos`, X-API-Key, vendedor_id por path).
2. Tienda: catálogo/ficha por vendedor + carrito→WhatsApp del vendedor (D4) + storefront `/v/{slug}` (D5).
3. buscadonde: `TiendaClient` + endpoints `/comercio/productos` + pestaña Productos
   (1–3 fotos) que sincroniza `producto_ref`.
4. Infra: instancia compartida nueva (D6).

## Lo que NO hacemos ahora
Checkout multi-vendedor (varios vendedores en un carrito), pagos online en el
marketplace, variantes complejas por defecto.
