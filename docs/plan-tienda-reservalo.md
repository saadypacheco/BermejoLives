# Plan — Tienda (Reservalo) sin Supabase, integrada a URUKU

> Objetivo: que la tienda quede **100% en el VPS** (sin Supabase Cloud), con el
> **comprador logueado en URUKU** (no en Reservalo), las **imágenes de producto en el
> disco de URUKU**, y las **reservas/carrito** funcionando. Todo cambio se replica en **QA**.
> Base de la investigación: informes de mapeo de ambos repos (2026-08-13).

## Cómo está hoy (resumen del mapeo)

**URUKU**
- Comprador: login **sin contraseña por WhatsApp**. Token **JWT HS256** firmado con `jwt_secret`
  del backend (claims `{usuario_id, whatsapp, rol:"usuario", exp:+30d}`), en `localStorage`
  (`bermejo_usuario_token`). Hoy solo habilita favoritos.
- URUKU→Reservalo: **servicio-a-servicio con `X-API-Key`** (`TiendaClient`: upsert vendedor +
  crear producto). Viaja la identidad del **comercio**, nunca la del comprador.
- Storage en disco listo: `procesar_imagen` + `guardar_foto_local(subpath)` → `/data/fotos`,
  servido en `/fotos`. Las fotos de **producto** hoy NO usan esto: se mandan a Reservalo.

**Reservalo**
- Comprador: **100% Supabase Auth (gotrue)**. `JWT_SECRET` está declarado pero **muerto** (no firma nada).
- Carrito: **local** (zustand + localStorage). Dos caminos de reserva **que conviven**:
  - **A) WhatsApp directo** al vendedor (CTA principal, no persiste nada).
  - **B) Pedido persistido**: `POST /pedidos` (o `/pedidos/guest`) → tablas `pedidos`+`items_pedido`;
    el comercio los ve en `admin/pedidos` o recibe comprobante por WhatsApp.
- Amarres a Supabase: **(1) gotrue** (login/`get_user`), **(2) Storage** (`productos`/`avatares`,
  3 routers), **(3) RLS `auth.uid()`** + FK `usuarios.id → auth.users` (~11 migraciones),
  **(4) realtime** del chat comprador↔vendedor.
- **El backend usa `service_role` y bypassa RLS** → las RLS solo protegen el acceso directo del
  frontend con anon key. Si movemos todo por el backend, sacar las RLS es seguro.

## Decisión de arquitectura (la clave)
- **Mismo origen `uruku.bo`** → la tienda **reusa el token de URUKU** del `localStorage`. Un solo login.
- Reservalo backend **valida el JWT de URUKU** (mismo `jwt_secret`, HS256) en vez de gotrue.
- Data layer: **Postgres+PostgREST self-host propio de Reservalo** en el VPS (stack `reservalo-*`,
  patrón idéntico a URUKU). El backend usa un `service_role` self-host → bypassa RLS (que sacamos).
- Imágenes de producto → **disco de URUKU** (subcarpeta `productos/…`, servida por `api.uruku.bo/fotos`).

---

## Fases

### Fase A · Imágenes de producto al disco de URUKU
*Saca la dependencia de Supabase Storage. Chica y de alto valor.*
- **URUKU** `crear_producto` (`comercio.py`): en vez de mandar bytes, guardar con
  `guardar_foto_local("productos/{slug}/{token}.jpg", data)` (+ thumb) y obtener la URL pública.
  Pasar a Reservalo las **URLs** (no los bytes).
- **Reservalo** `POST /api/servicio/vendedores/{id}/productos` (`servicio.py`): aceptar URLs de
  imagen y guardarlas; **eliminar** `db.storage.from_("productos")`.
- **Comprobantes de pago** (`pedidos.py` usa Storage): mandarlos al disco (de URUKU o un volumen
  propio de Reservalo) o dejarlos solo por WhatsApp. Eliminar `db.storage`.
- Limpieza por antigüedad: job que borra `productos/…` archivados (opcional, fase posterior).

### Fase B · Auth del comprador por token de URUKU (sacar gotrue)
*El comprador se loguea en URUKU; la tienda confía en ese token.*
- **Reservalo backend**: dependency `get_current_user` que **valida el JWT de URUKU**
  (`jwt.decode(token, JWT_SECRET, HS256)`, exige `rol=="usuario"`) y devuelve `usuario_id`/`whatsapp`.
  Reemplazar **todos** los `supabase.auth.get_user(token)` (auth.py, pedidos.py, chat.py, etc.).
- **Reservalo `usuarios`**: dejar de referenciar `auth.users`; clave propia = `usuario_id` de URUKU.
  Alta progresiva (crear la fila en el 1er pedido si no existe, como hace URUKU).
- **Reservalo frontend**: leer `bermejo_usuario_token` del `localStorage` (mismo origen) y mandarlo
  como `Bearer`. Quitar `supabase.auth` (`useAuth`, páginas `login`/`registro`). Si no hay token →
  mandar a la pantalla de login de comprador de **URUKU**.
- **Guest checkout** (nombre+teléfono) se mantiene igual (sin auth).
- Eliminar `JWT_SECRET` muerto y setear el **mismo `jwt_secret` que URUKU** en Reservalo (para validar).

### Fase C · Base self-host de Reservalo (sacar la base Supabase)
*La tienda con su propia base en el VPS.*
- Stack `reservalo-postgres` + `reservalo-postgrest` en `/docker/reservalo` (patrón de URUKU:
  `postgres-init` con las migraciones de Reservalo **adaptadas**).
- **Adaptar migraciones**: sacar FK `usuarios.id → auth.users`, sacar RLS `auth.uid()` (el backend
  usa `service_role`), sacar `007_storage_buckets`, sacar la publicación realtime de `004`.
- **Reservalo backend**: apuntar el cliente supabase-py al PostgREST self-host con un `service_role`
  self-host (JWT firmado con el `PGRST_JWT_SECRET` de Reservalo), igual que URUKU.
- **Frontend**: dejar de leer datos con supabase-js (anon); todo por el backend FastAPI.

### Fase D · Realtime del chat → polling (o diferir)
*Único uso de realtime (chat comprador↔vendedor).*
- Reemplazar `supabase.channel(...)` por **polling** cada ~3-5s contra el backend (como el polling
  de confirmación de URUKU), **o diferir** el chat para el lanzamiento si no es crítico.

### Fase E · Reservas / carrito con el comprador de URUKU
*Lo que destacaste. En gran parte ya existe; se completa con B.*
- Camino **A (WhatsApp)**: ya funciona, no toca auth/BD. Se mantiene.
- Camino **B (pedido persistido)**: tras Fase B, el checkout "registrado" usa el **comprador de URUKU**.
  Verificar el flujo end-to-end: carrito → checkout → `POST /pedidos` con token URUKU → el comercio
  lo ve en su panel / recibe aviso por WhatsApp.

---

## Orden sugerido de ejecución
1. **A** (imágenes a disco) — desacopla Storage, bajo riesgo, valor inmediato.
2. **B** (auth por token URUKU) — el corazón de la integración; habilita reservas del comprador.
3. **C** (base self-host) — la más grande; migrar datos actuales de Reservalo (o arrancar limpio).
4. **D** (realtime → polling) — o diferir el chat.
5. **E** (verificación end-to-end de reservas).

## Reglas transversales
- **Todo cambio en prod se replica en QA** (`encontralo.store`): mismos commits, `DOMAIN` distinto.
  QA de Reservalo con base self-host propia (aislada de prod).
- **Migración de datos** de Reservalo: al pasar a self-host (Fase C) hay que exportar/importar el
  catálogo/pedidos actuales de la Supabase de Reservalo, o arrancar limpio si aún no hay datos reales.
  **Confirmar cuántos datos reales tiene Reservalo hoy.**
- Testing por fase antes de avanzar. El backend ya usa `service_role`, lo que reduce el riesgo de RLS.

## Riesgos / a decidir
- **Chat**: ¿se sostiene (polling) o se difiere para el lanzamiento?
- **Cuentas mayoristas / cuenta corriente** (migración 015): son features B2B con auth. Si no se usan
  aún, se difieren; si se usan, entran en Fase B/C.
- **Datos actuales en la Supabase de Reservalo**: definen si Fase C es "migrar" o "arrancar limpio".
