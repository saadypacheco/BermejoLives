# Contrato de integración buscadonde ↔ ecommerce (marketplace)

> Documento de coordinación entre las DOS sesiones/repos:
> - **buscadonde** (`C:\repos\proyectosClaude\Bermejo`) — gestiona, clasifica con IA, factura.
> - **ecommerce** (`C:\repos\proyectosClaude\tienda`, instancia compartida) — almacena y muestra.
> Cada lado implementa SU parte respetando este contrato. v1. 2026-06-22.

## Identidad y auth
- **`vendedor_id` = `comercio_id` de buscadonde** (uuid). El mismo valor en ambos lados.
- **Auth servicio-a-servicio:** header `X-API-Key: <secret>`. Mismo valor en el `.env`
  de los dos (`TIENDA_API_SECRET` en buscadonde · `SERVICIO_API_SECRET` en ecommerce).
- La IA (visión + clasificación + precio) vive **en buscadonde**. El ecommerce recibe el
  producto **ya estructurado** (incluida la categoría) y solo almacena/muestra.

---

## Lo que construye el ECOMMERCE (otra sesión)

### 1. Migración
- Tabla **`vendedores`**: `id uuid pk` (= comercio_id), `nombre text`, `slug text unique`,
  `whatsapp text`, `activo bool default true`, `created_at`, `updated_at`.
- `productos.vendedor_id uuid references vendedores(id)` + índice.
- **`productos.moneda text not null default 'ARS'`** ⚠️ NUEVO — hoy la moneda es global
  (`tienda_config`); en el marketplace cada producto trae la suya (ARS/BOB). El
  storefront debe formatear el precio con la **moneda del producto**, no la global.
- **Producto simple:** permitir crear producto SIN variantes (la mayoría no tiene
  talle/color). Recomendado: **"disponible" sin control de stock** (la venta es por
  WhatsApp, no hay inventario real). No exigir talle/color. Los talles van en la
  descripción como texto.
- Categoría: el ecommerce recibe un **`categoria_slug`** (lo eligió la IA de buscadonde
  entre las categorías que devuelve `GET /api/servicio/categorias`) y lo resuelve a su
  `categoria_id`.

### 2. Router `/api/servicio` (todos exigen `X-API-Key`)
| Método | Ruta | Body | Devuelve |
|---|---|---|---|
| PUT | `/api/servicio/vendedores/{vendedor_id}` | `{nombre, slug, whatsapp, activo}` | vendedor |
| POST | `/api/servicio/vendedores/{vendedor_id}/productos` | **multipart**: `nombre, precio, moneda, categoria_slug, descripcion?` + `fotos` (1–3 archivos) | `{producto_id, url}` |
| PUT | `/api/servicio/productos/{producto_id}` | JSON: `{nombre?, precio?, moneda?, categoria_slug?, descripcion?, activo?}` | producto |
| DELETE | `/api/servicio/productos/{producto_id}` | — | `{ok:true}` (soft-delete `activo=false`) |
| GET | `/api/servicio/vendedores/{vendedor_id}/productos` | — | `[productos]` (para que buscadonde sincronice) |
| GET | `/api/servicio/categorias` | — | `[{slug, nombre}]` (para que la IA de buscadonde clasifique) |

- El ecommerce **sube las fotos** a su storage (`producto_imagenes`, máx 3 acá) y arma
  la `url` pública del producto (ej. `/v/{slug}#p{producto_id}`).
- `producto_id` es **int** (serial del ecommerce). buscadonde lo guarda como texto.

### 3. Storefront (lado comprador) — dominio **reservalo.com**
- `/v/{slug}` — catálogo del vendedor (reusa grid/buscador/filtros, filtrado por `vendedor_id`).
- Ficha de producto.
- **Carrito por-comercio** → WhatsApp a **`vendedores.whatsapp`** (NO el número global). D4.
- Carrito persistente sin login (ya existe: Zustand localStorage + checkout guest). D4.
- **Tagline en el sitio:** "Encontralo en el mapa. Reservalo en la tienda." (va en los DOS sitios).

---

## Lo que construye BUSCADONDE (esta sesión)
- `producto_ref` (✅ migración 0015 ya creada): índice + metadatos propios.
- **`TiendaClient`** (httpx) → llama `/api/servicio/*` con `X-API-Key`.
- **Servicio IA** (Gemini visión+texto): fotos + precio + desc(opc) → `{nombre,
  categoria_slug, descripcion}`. Requiere `GEMINI_API_KEY`.
- Endpoints (todos `require_comercio`):
  | Método | Ruta | Para |
  |---|---|---|
  | POST | `/comercio/productos/draft` | fotos+precio+desc → IA → borrador (preview, NO publica) |
  | POST | `/comercio/productos` | confirmar: upsert vendedor + crea producto en ecommerce + guarda `producto_ref` |
  | GET | `/comercio/productos` | lista (sincroniza `producto_ref` con la API) |
  | PUT/DELETE | `/comercio/productos/{ref_id}` | proxy a la API + actualiza `producto_ref` |
- Al crear el 1er producto de un comercio: primero `PUT vendedores/{id}` (nombre/slug/
  whatsapp del perfil), después el producto.
- Frontend: pestaña **Productos** en `/mi-comercio` → captura (1–3 fotos + precio +
  desc opcional) → **preview editable** → confirmar.

---

## Flujo end-to-end (v1)
1. Vendedor en `/mi-comercio` → "+ Producto" → 1–3 fotos + precio + desc opcional.
2. buscadonde `POST /comercio/productos/draft` → IA arma borrador → **preview editable**.
3. Vendedor confirma → buscadonde `PUT vendedores/{id}` + `POST .../productos` (multipart con fotos).
4. Ecommerce guarda producto (con `vendedor_id`, fotos, categoría) → devuelve `{producto_id, url}`.
5. buscadonde guarda `producto_ref` (tienda_producto_id, url, cargado_por, estado=publicado).
6. Comprador ve el producto en `reservalo.com/v/{slug}` → carrito → WhatsApp al vendedor.

## Pendiente de infra (D6)
Instancia nueva del ecommerce (Supabase + dominio `reservalo.com`) + seed +
`SERVICIO_API_SECRET`. Mientras tanto, buscadonde puede desarrollar contra un
`TiendaClient` stub.

---

## Búsqueda unificada: producto → comercios en el mapa → Reservalo (decisión del dueño)
**El mapa de comercios es el diferencial; Reservalo es la capa "reservá lo que viste".**
Cuando el usuario busca un **producto** en Encontralo, NO se muestran productos sueltos:
se muestran los **comercios (en el mapa) que tienen ese producto**. Tagline en acción.

**Flujo:**
1. Producto buscado en Encontralo → consulta la API de búsqueda de Reservalo →
   agrupa los resultados por `vendedor_id` → pinta esos comercios en el mapa/lista
   ("tiene N productos que coinciden").
2. Click en un comercio → `reservalo.store/productos?vendedor={comercio_id}&search={term}`
   (los productos de ESE local, filtrados por lo buscado).
3. Botón global "Ver todos los productos que coinciden" →
   `reservalo.store/productos?search={term}` (en todos los locales).

**Lo que Reservalo (otra sesión) tiene que exponer para esto:**
- ✅/⚪ `productos.vendedor_id` (= comercio_id) — multi-vendedor (ya en el contrato arriba).
- ⚪ **API pública de búsqueda**: `GET /api/productos/buscar?search=X` →
  `[{id, nombre, precio, moneda, imagen_url, vendedor_id, url}]`. La consume Encontralo.
- ⚪ **Filtro `vendedor`** en el storefront `/productos` (hoy soporta
  `categoria, talla, precio_min, precio_max, search`; falta `vendedor`).

**Encontralo (esta sesión) construye después:** el modo "Productos" del buscador deja de
redirigir directo y pasa a: llamar la API → agrupar por vendedor → mostrar comercios en
el mapa con el contexto del producto + los dos drill-downs a Reservalo.

> Mientras la integración multi-vendedor no esté viva, el modo Productos hace el
> hand-off simple actual (`/productos?search=`). Es un reemplazo de una línea cuando llegue.

### Navegación entre sitios (decisión: opción C — misma pestaña)
- **Encontralo → Reservalo**: el click en un comercio (o el modo Productos) navega
  **same-tab** a `reservalo.store/productos?vendedor={comercio_id}&search={term}&volver={url_busqueda_encontralo}`.
- **Volver al mapa**: el **botón atrás nativo** ya regresa a la búsqueda (la URL la tiene);
  además Reservalo muestra una **barra "← Volver al mapa de Encontralo"** usando `volver`.
- **Reservalo → Encontralo (el "cómo llegar")**: en la ficha de producto / header del local,
  Reservalo renderiza **"📍 Cómo llegar / Ver el local"** → `https://encontralo.store/comercios/{vendedor.slug}`
  (esa página ya tiene mapa + cómo llegar + WhatsApp) y **"💬 WhatsApp"** → `wa.me/{vendedor.whatsapp}`.
  Reservalo arma ambos links con el `slug` y `whatsapp` que ya guarda en `vendedores`.

**Modelo:** Encontralo = el DÓNDE (mapa, cómo llegar, contacto) · Reservalo = el QUÉ
(productos, reservar). Se cruzan en ambos sentidos.
