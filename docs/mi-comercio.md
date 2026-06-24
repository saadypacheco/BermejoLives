# Panel "Mi comercio" — diseño

> El dueño del comercio entra a `/mi-comercio` y tiene **todo**: paga, edita,
> ve quién lo miró y qué dijeron sus clientes, recibe mensajes y carga ofertas.
> Spec del dueño (2026-06-21). Estado: 🟢 listo · 🟡 en build · ⚪ pendiente.

## Pestañas del panel
1. **Perfil** 🟡 — editar nombre, descripción, logo, WhatsApp/teléfono, email,
   **redes** (FB/IG/TikTok/web), **links libres** a otras páginas, dirección/horario,
   monedas. (Lo que el cliente ve en su ficha.)
2. **Suscripción** 🟡 — estado (`paga_hasta`, días restantes, suspendido/activo) +
   **pagar por QR** (sube comprobante → admin lo confirma → extiende fecha) +
   **resumen de cargos** (suscripción + publicaciones destacadas acumuladas).
3. **Contactos / Métricas** 🟡 — cuántos lo miraron / lo contactaron (de `leads`:
   WhatsApp, teléfono, email, web), por día/semana.
4. **Mensajes** ⚪ — bandeja de mensajes **del admin → comercio** y **del cliente →
   comercio** (por si el cliente cambió de celular y no lo ubican). El comercio
   responde desde acá.
5. **Productos / Ofertas** ⚪ — cargar productos con **1 a 3 fotos** (ver abajo).
6. **Cuenta** ⚪ — cambiar email/contraseña.

## Carga de productos y la regla del destacado (núcleo del modelo)
- El comercio **carga un producto** con **1 a 3 fotos**, nombre, precio, descripción.
- Eso **se publica en el ecommerce** (catálogo) → **gratis e ilimitado**.
- **Extra opcional (pago):** que **1 de esas fotos** quede **destacada en el feed de
  buscadonde**. Si lo elige:
  - se crea una **`publicacion`** (tipo `oferta`) ligada a ese producto, con un
    **`costo`** (ej. $1.000 ARS),
  - entra a **moderación** (o directo si `confiable`),
  - el costo **se acumula** y **se cobra junto con la suscripción** (facturación
    acumulada). El comercio lo ve en "Suscripción → resumen de cargos".

### Decisión tomada: buscadonde gestiona, el ecommerce almacena
El comercio carga el producto **desde buscadonde**, pero el producto vive en la
**base del ecommerce** (reusamos su buscador/filtros/ficha/carrito). buscadonde
guarda solo una **referencia** y opera por API.

**Prerequisito (clave):** la tienda hoy es **deploy-por-cliente** (una base por
comercio). Para esto hace falta **UNA tienda compartida multi-vendedor** =
"el ecommerce de buscadonde" (`reservalo.com`), con `vendedor_id` en cada
producto. La tienda per-cliente (Amanda) sigue como **producto premium** aparte.

**Contrato de integración:**
- Tabla nueva en buscadonde **`producto_ref`**: `comercio_id`, `tienda_producto_id`,
  `url`, `estado`, `destacado_pub_id?`, `created_at`.
- API de la tienda (servicio-a-servicio, shared secret): `POST/PUT/DELETE
  /api/vendedores/{id}/productos`, `GET .../productos`.
- buscadonde panel → "Cargar/editar/borrar producto" llama a esa API y sincroniza
  `producto_ref`. "Ver en el ecommerce" abre `url`.
- **Destacado pago**: queda en buscadonde como `publicacion` (tipo oferta) con `costo`,
  ligada vía `producto_ref.destacado_pub_id`. Se factura con la suscripción.

**Trabajo en la tienda (otro repo):** producto→`vendedor_id`, catálogo/checkout
filtrables por vendedor, carrito→WhatsApp del vendedor correcto, API de servicio.

> Sub-decisión a confirmar: ¿una **tienda compartida multi-vendedor** para la masa
> (recomendado) y la per-cliente solo premium?

## Cambios de datos necesarios (migraciones)
- `productos`: pasar de `foto_url` (1) a **`foto_urls text[]`** (1–3). ⚪
- `publicaciones`: agregar **`costo numeric`** + **`producto_id`** (link al producto)
  + **`cobrado bool`** (si ya se facturó). ⚪
- Nueva tabla **`mensajes`** (comercio_id, autor `admin|cliente|comercio`, nombre,
  contacto, cuerpo, leido, created_at). ⚪
- Reusar **`pagos`** + `comercios.paga_hasta`/`suspendido` (ya existen). 🟢

## Endpoints (backend) — qué reusa y qué se crea
Reusa: `get_comercio`, `update_comercio`, `list_leads_by_comercio`,
`list_publicaciones_de_comercio`, `registrar_pago`. **Nuevos:**
- `GET /comercio/perfil` 🟡 · `PUT /comercio/perfil` 🟡 (whitelist de campos editables)
- `GET /comercio/suscripcion` 🟡 (estado + cargos acumulados)
- `GET /comercio/metricas` 🟡 (resumen de leads + publicaciones)
- `POST /comercio/pago` ⚪ (sube comprobante QR → pago pendiente de confirmar)
- `GET/POST/PUT/DELETE /comercio/productos` ⚪ (multi-foto)
- `GET/POST /comercio/mensajes` ⚪ · `POST /mensaje` (cliente→comercio, público) ⚪

## Orden de build (slices)
1. 🟡 **Base visible:** panel `/mi-comercio` (auth) + Perfil (ver/editar) +
   Suscripción (estado) + Contactos. *No depende de la decisión abierta.*
2. ⚪ **Pago QR** self-service (comprobante) + resumen de cargos.
3. ⚪ **Productos multi-foto** + destacado cobrable (tras la decisión del ecommerce).
4. ⚪ **Mensajería** admin↔comercio↔cliente.
