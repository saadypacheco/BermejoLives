# Clave automática del comercio y código sólo en el admin — spec

> **Estado: implementada el 12/10/2026.**

## Decisiones del dueño (12/10)

1. El **usuario** sigue siendo el número de celular.
2. La **clave se genera sola, al azar**, con el nombre del local adelante para recordarla.
   Se ve **una sola vez**: el **agente** al terminar el alta y el **admin** con «Generar
   clave nueva». El comerciante también la recibe al confirmar por WhatsApp si no tenía.
3. Las **claves de 6 números que ya existen siguen sirviendo** hasta que se cambien.
4. El **código URUKU-XXXX sólo se ve en el admin**: ni volante, ni Mi comercio, ni app
   del agente, ni autoregistro, ni páginas públicas, ni lectura pública en la base.
5. Descartado (12/10): una clave deducible (últimos 4 del celular + código, o el
   nombre solo). El celular y el nombre son públicos: cualquiera la armaría.

## Formato de la clave

`<PREFIJO>-<AZAR>`, p. ej. `BOUTIQUE-K7M2P9`.

- **PREFIJO** (sólo para recordarla, no suma seguridad): la primera palabra significativa
  del nombre (se saltean `el, la, los, las, lo, de, del, y, e, mi, tu, su, un, una`), en
  mayúsculas, sin tildes ni ñ (`Ñ→N`), sólo letras y números, máximo 8. Si el comercio
  es `sin_cartel`, la primera palabra de `subcategoria` o, si no hay, del rubro. Sin
  nada utilizable: `LOCAL`. **Nunca** `URUKU` (se confundiría con el código).
- **AZAR**: 6 caracteres de `23456789ABCDEFGHJKMNPQRSTUVWXYZ` (sin 0/O/1/I/L), con
  `secrets`. ≈ 887 millones de combinaciones; el login ya bloquea el número a los 5
  fallos en 15 min, anula la clave a los 10 en 24 h y limita la IP.
- **Al comparar**: mayúsculas, sin espacios ni guiones (`boutique k7m2p9` =
  `BOUTIQUE-K7M2P9`). Se guarda sólo el hash de la forma normalizada. Una clave vieja de
  6 números normaliza a sí misma y sigue entrando.

## Contrato (backend ↔ frontend)

- `POST /comercio/ingresar` (el login de hoy): `clave` pasa a aceptar hasta 24
  caracteres alfanuméricos con guiones/espacios; se normaliza en el servidor.
- **Clave en la respuesta, una sola vez**, campo `"clave": "BOUTIQUE-K7M2P9"`:
  - alta del agente (la ruta de alta de `/campo`): genera la clave del comercio nuevo;
  - **`POST /admin/comercio/{id}/clave`** (permiso **`comercios.cuenta`**): genera una
    nueva y la anterior deja de servir → `{"clave": "..."}`;
  - confirmación por WhatsApp sin clave previa (`claveNueva` de hoy) y
    `POST /comercio/clave` (el comerciante pide otra): en el formato nuevo.
- La clave nunca va a logs, a localStorage, al volante ni a ninguna página pública.
- **Código sólo admin**:
  - las respuestas de `/comercio/*`, `/campo/*` y del autoregistro dejan de traer
    `codigo`/`codigo_formateado`;
  - migración **0148** (`0148_codigo_solo_admin.sql`, dos carpetas, idempotente):
    `revoke select (codigo) on comercios from anon, authenticated`; `codigo` pasa a
    `PRIVADAS_EXTRA` en `test_comercios_columnas_publicas.py`, y sale de la lista de
    columnas públicas de la 0145 (comentario) y de `COLUMNAS_COMERCIO` en `lib/data.ts`;
  - la ingesta sigue aceptando el código (el admin se lo dicta a quien haga falta).

## Frontend

- Login del comercio (`components/ingresar-comercio.tsx`): campo de texto (no numérico),
  `autoCapitalize="characters"`, ayuda «Ej.: BOUTIQUE-K7M2P9 (o tu clave de 6 números)».
  El comprador (`comprador-auth.tsx`, `lib/acceso.ts`) **no cambia**.
- Agente: al terminar el alta, pantalla «Clave del comercio: BOUTIQUE-K7M2P9 —
  anotala y entregásela en un papel aparte; no se vuelve a mostrar», con «Copiar».
- Admin › Editar negocio (con `comercios.cuenta`): «Generar clave nueva» con
  confirmación («la anterior deja de servir»), muestra la clave una vez con «Copiar».
- Sacar el código de: `app/volante/[slug]/**`, `app/mi-comercio/page.tsx`
  (`CodigoYClave`: queda sólo lo de la clave), `app/autoregistro/page.tsx`,
  `app/publicar/page.tsx` y `lib/campo.ts`/`lib/comercio.ts`/`lib/upload.ts`
  (tipos). En el admin se queda.
- Manual del comerciante (`content/manuales/comercio.md`) y demás textos: sin «mandá tu
  código»; explicar la clave nueva y que se publica desde el número registrado.

## Criterios de aceptación

1. Un alta de agente devuelve una clave `PREFIJO-XXXXXX` válida, y con celular + esa
   clave (en minúsculas, con o sin guion) se entra.
2. Sin cartel → prefijo de lo que vende; sin nada → `LOCAL`; nunca `URUKU`.
3. Una clave vieja de 6 números sigue entrando.
4. «Generar clave nueva» del admin invalida la anterior; sin `comercios.cuenta` → 403.
5. Como anon, `comercios?select=codigo` da error de permiso; volante, Mi comercio,
   autoregistro y app del agente no muestran el código; el admin sí.
6. La ingesta con `URUKU-XXXX` sigue funcionando.
7. Tests verdes, `tsc` y `next build` ok, sin emoji.
