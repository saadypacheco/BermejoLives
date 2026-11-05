# Teléfonos en las fotos de los comercios — spec corta (5/11/2026)

## Qué y por qué

Muchas portadas muestran el celular del comercio (cartel, vidriera, sticker). El dueño quiere leerlos para completar los comercios que no tienen WhatsApp y detectar los que lo tienen distinto. Se leen **las portadas** de todos los comercios activos (hoy ~6000); la galería queda como opción.

**Nada se escribe solo en la ficha.** Todo número leído queda como **propuesta** y una persona la aplica o la descarta.

## Motor (costo cero por defecto, §17 de contenido-redes-tecnico.md)

- **Por defecto: OCR local gratis (Tesseract)** en el backend (`apt-get install tesseract-ocr`, dependencia nueva `pytesseract`: «OCR local sin costo para leer teléfonos en las portadas»). Preproceso con Pillow: `exif_transpose`, gris, lado mayor 1600, autocontraste; OCR con `--psm 11` y lista blanca de dígitos, `+`, espacios, guiones, puntos y paréntesis; además una pasada sobre la imagen invertida (carteles claros sobre fondo oscuro).
- **Opcional, con interruptor de costo `gemini_phone_scan`** (nuevo en `cost_switches.CATALOGO`): label «Leer teléfonos en las fotos con Gemini», cost «Estimado: menos de US$ 5 para todas las portadas (unas 6000); 0 si la clave es del nivel gratis», off_means «Se usa el lector gratis (Tesseract), que se pierde algunos números en carteles chicos o torcidos». Prendido, la foto va a Gemini (`vision._post_con_reintentos`, foto a 1024 px) con un prompt que sólo pide `{"telefonos": ["…"]}` tal como están escritos.
- **Gratis siempre:** el relevamiento por fotos que ya existe (`vision.analizar_fotos`, ya pago) suma el campo `telefonos` a su JSON y guarda lo que encuentre como propuestas (`motor='gemini-relevamiento'`). No agrega llamadas.

## Normalización (pura, `core/telefonos_foto.py`, con tests)

- **Bolivia:** celular de 8 dígitos que empieza en 6 o 7 → `+591XXXXXXXX`; con prefijo `591` / `+591`, igual. Fijo: 7 dígitos con código de área (2, 3, 4) → `tipo='fijo'`.
- **Argentina** (ciudades de frontera): `+54` / `54` + 10 dígitos, o 10 dígitos con códigos de la región (p. ej. 387, 3878) → `+54…`; el 9 de celular se normaliza.
- Se descarta: menos de 7 dígitos, fechas, horarios, precios, años, NIT, códigos de producto, números repetidos (`11111111`) y **los números de URUKU** (67671888, 67677803 y los que estén en la config).
- Un número que aparece en **4 o más comercios** se marca `compartido` (galería, administración, agente) y no se ofrece en el lote.

## Datos — migración `0184_telefonos_en_fotos.sql`

```sql
create table if not exists public.fotos_escaneadas (      -- qué foto ya se leyó y con qué motor
  foto_url     text not null,
  motor        text not null check (motor in ('tesseract', 'gemini', 'gemini-relevamiento')),
  comercio_id  uuid not null references public.comercios(id),
  numeros      int not null default 0,
  error        text,
  escaneada_at timestamptz not null default now(),
  primary key (foto_url, motor)
);
create table if not exists public.telefonos_detectados (
  id            uuid primary key default gen_random_uuid(),
  comercio_id   uuid not null references public.comercios(id),
  numero        text not null,                 -- E.164 (+591…, +54…)
  tipo          text not null check (tipo in ('celular', 'fijo')),
  texto_leido   text not null check (length(texto_leido) <= 60),
  foto_url      text not null,
  motor         text not null,
  estado        text not null default 'pendiente' check (estado in
                ('pendiente', 'coincide', 'aplicado_whatsapp', 'aplicado_telefono', 'descartado')),
  compartido    boolean not null default false,
  revisado_por  text,
  revisado_at   timestamptz,
  activo        boolean not null default true,
  created_at    timestamptz not null default now(),
  unique (comercio_id, numero)
);
```

RLS activo, revoke a `public, anon, authenticated`, grant a `service_role`. Mismo archivo en `supabase/migrations/` y `selfhost/postgres-init/`. Al guardar, si el número ya es el `whatsapp` o el `telefono` del comercio → `estado='coincide'`.

## Worker

- `_telefonos_foto_loop` en `main.py`, detrás de `TELEFONOS_FOTO_WORKER` (default false). Toma de a **20 portadas** sin fila en `fotos_escaneadas` para el motor activo (primero los comercios **sin WhatsApp**), las procesa **de a una** (en un hilo, sin frenar la API) y duerme 30 s entre tandas. Una portada que cambia de URL se vuelve a leer sola.
- Ritmo esperado con Tesseract: 1 a 3 s por foto → las ~6000 en 3 a 5 h. Log `telefonos_foto.tanda` con leídas, números y errores.
- Sin `tesseract` instalado (PC de desarrollo) el loop avisa una vez y no toma trabajos.

## API (permiso de edición de comercios del panel, el mismo de «Editar negocio»; agentes limitados a su ciudad)

- `GET /admin/telefonos-detectados?ciudad=&estado=pendiente&sin_whatsapp=true&limit=50&offset=` → `{items: [{id, comercio: {id, nombre, slug, whatsapp, telefono, ciudad}, numero, numero_visible, tipo, texto_leido, foto_url, motor, estado, compartido, otros_comercios}], total}` (sólo panel interno; nunca público).
- `GET /admin/telefonos-detectados/resumen` → `{escaneadas, pendientes_de_escanear, numeros, sin_whatsapp_con_numero, motor_activo, worker}`.
- `POST /admin/telefonos-detectados/{id}/aplicar` body `{como: "whatsapp" | "telefono", reemplazar?: bool}`: escribe en `comercios` por el mismo camino que «Editar negocio» (con su validación y auditoría); si el comercio ya tenía otro valor, 409 salvo `reemplazar: true`. `estado` → `aplicado_*`.
- `POST /admin/telefonos-detectados/{id}/descartar`.
- `POST /admin/telefonos-detectados/aplicar-lote` body `{ids: [...]}` (≤ 100): sólo aplica como WhatsApp en comercios **sin** WhatsApp, con número `celular` y no `compartido`; devuelve `{aplicados, saltados: [{id, motivo}]}`.

## Panel: Admin › Comercios › «Teléfonos en fotos»

- Resumen arriba (escaneadas, faltan, números encontrados, comercios sin WhatsApp que ya tienen uno propuesto) y el motor activo («Lector gratis» o «Gemini · tiene costo», con link a Servicios con costo).
- Lista: miniatura de la portada (tocar = ampliar), nombre del comercio, WhatsApp actual (o «sin WhatsApp»), número leído grande, insignias «Coincide», «Compartido con N comercios», «Fijo».
- Acciones por fila: «Usar como WhatsApp», «Usar como teléfono», «Descartar»; selección múltiple + «Usar como WhatsApp los marcados» (sólo los que cumplen la regla del lote). Filtros: ciudad, estado, sólo sin WhatsApp.
- Íconos de `ic.tsx`, voseo. Que ande en el celular.
