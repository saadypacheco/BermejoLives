# Carga de comercios desde fotos de tarjetas (spec corta, 12/11/2026)

Pedido del dueño: los vendedores le pasan **fotos de tarjetas de presentación de papel**. Quiere subirlas y que
cada una quede cargada en una ciudad, con nombre, dirección y teléfonos, **sin tipearlas**. La ubicación se busca
sola a partir de la dirección.

## Decisiones

- **Entra por Importados** (Comercios › Importados, tabla `comercios_importados`, 0066), con `fuente = 'tarjeta'`.
  Nada aparece en el sitio hasta que una persona lo revisa y toca «Promover». Es la misma sala de espera que los
  importados de OpenStreetMap.
- **Lectura gratis por defecto**: Tesseract, el mismo lector de «Teléfonos en fotos» (`services/telefonos_foto.py`),
  que ya está instalado en la imagen del backend. Opcional y apagado: Gemini, detrás de un interruptor de costo
  nuevo `gemini_tarjetas` en `cost_switches.CATALOGO` (mismo patrón que `gemini_phone_scan`: sólo `equipo` lo
  prende, con `confirm_cost`).
- **Ubicación automática** con Nominatim de OpenStreetMap (gratis). Se respeta su política de uso: 1 pedido por
  segundo como máximo, User-Agent propio `URUKU/1.0 (+https://uruku.bo)`, caché por consulta, sin consultas
  masivas. Se busca acotado a la ciudad elegida. Si no encuentra la dirección, queda sin punto y la persona lo marca
  a mano en el mapa al revisarlo. Un punto encontrado se marca como **aproximado** hasta que alguien lo confirma.
- **Teléfonos**: misma normalización que «Teléfonos en fotos» (Bolivia y Argentina; los argentinos sin 9 se toman
  como celular). El primero que sea celular va a `whatsapp`; el resto, a `telefono`.
- **Repetidos**: si un teléfono de la tarjeta ya es de un comercio activo (whatsapp, telefono o números
  autorizados), se marca `duplicado_de` y se muestra en la revisión.
- **La foto de la tarjeta es privada**: puede traer datos personales. Va al disco privado
  (`services/archivos_privados.py`, referencia `privado:`), nunca a `/fotos`. Se ve sólo en el panel.
- **Idempotente**: la misma foto subida dos veces no crea dos filas (`fuente_id = 'tarjeta:' + sha256` del archivo).

## Contrato

Todo con permiso vigente `datos` (el de la sección Importados), salvo donde se indica.

| Método y ruta | Entrada | Salida |
|---|---|---|
| `POST /admin/importados/tarjetas` | multipart: `ciudad_id` (uuid) y `fotos` (1 a 20 archivos JPEG, PNG o WebP, ≤ 10 MB cada uno) | `{ "items": [Importado], "errores": [{ "archivo": str, "motivo": str }] }` |
| `GET /admin/importados?fuente=tarjeta` | el listado de siempre con un filtro nuevo `fuente` (`osm` \| `tarjeta`) | igual que hoy; cada item suma los campos de abajo |
| `GET /admin/importados/{id}/foto` | — | la imagen (privada, `Cache-Control: no-store`); 404 si no es de tarjeta |
| `PATCH /admin/importados/{id}` | `{ nombre?, direccion?, telefono?, whatsapp?, website?, email?, rubro_slug?, lat?, lng? }` | el Importado actualizado (sólo si `estado = 'nuevo'`) |
| `POST /admin/importados/{id}/ubicar` | `{ direccion }` | `{ lat, lng, aproximada: true, encontrado: bool, display_name }`; con `encontrado: false` no cambia nada |
| `POST /admin/importados/{id}/promover` | el de siempre (`nombre?`, `rubro_slug?`, `whatsapp?`) | el de siempre; para tarjetas también copia `telefono`, `website` y `direccion` |

Campos que suma cada Importado de tarjeta: `fuente: "tarjeta"`, `email`, `tiene_foto: true`,
`ubicacion: "aproximada" | "confirmada" | "no_encontrada"`, `texto_leido` (el texto crudo del lector, sólo panel) y
`lector: "tesseract" | "gemini"`. Mover el punto a mano o guardar `lat`/`lng` por PATCH lo pasa a `"confirmada"`.

## Pantalla (Comercios › Importados)

- Botón **«Cargar tarjetas»**: elegir la ciudad (por defecto la del panel), subir varias fotos, barra de progreso y
  al final cuántas se leyeron y cuáles fallaron, con el motivo.
- Filtro **OSM / Tarjetas** en el listado.
- Cada tarjeta en revisión muestra: la foto (se agranda al tocarla), los campos leídos **editables**, el aviso de
  repetido si lo hay, un mapa chico con el punto **arrastrable**, el botón «Buscar la dirección» y, como siempre,
  «Promover» y «Descartar». Sin punto no se puede promover; el botón lo dice.
- Íconos de `components/ic.tsx`, sin emojis.

## Criterios de terminado

1. Subir 5 fotos de tarjetas crea 5 importados con nombre, teléfonos y dirección leídos (o vacíos, nunca inventados).
2. Subir la misma foto otra vez no crea otra fila.
3. Una dirección que Nominatim encuentra deja el punto aproximado dentro de la ciudad; una que no, queda sin punto.
4. Un teléfono que ya tiene un comercio marca el repetido.
5. La foto de la tarjeta no se puede abrir sin sesión de panel.
6. Con el interruptor `gemini_tarjetas` apagado no se llama a Gemini nunca.
7. Promover crea el comercio con nombre, dirección, teléfonos, web y punto; no sale verificado ni confiable.
