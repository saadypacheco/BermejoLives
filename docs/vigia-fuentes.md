# Vigía de fuentes — revisar las páginas todos los días (spec)

> Estado: **propuesta** (16/11). Reemplaza las corridas a mano de `importar_turismo` y `ubicar_direccion`.

## Problema

Hoy cada fuente se importa **una vez**, a mano, desde la consola del servidor:

- `importar_turismo` lee las páginas y **saltea** lo que ya existe: no se entera de un teléfono nuevo, un horario
  cambiado ni un negocio que cerró.
- `ubicar_direccion` vuelve a preguntarle todo a Nominatim en cada corrida (~700 pedidos). El 16/11, después de
  cuatro corridas, dejó de contestar.
- Nadie se entera de un negocio nuevo en la página de turismo hasta que alguien vuelve a correr el comando.

## Qué hace

Una vuelta por día (de madrugada, hora de Bolivia), sola, por cada fuente y ciudad:

1. **Lee la fuente** con cortesía: un pedido por segundo, el mismo `User-Agent` de siempre, respeta `robots.txt`.
   Si la página no cambió desde ayer (misma huella del HTML), no la vuelve a procesar.
2. **Compara con lo de ayer**, negocio por negocio:
   | Qué pasó | Qué deja |
   |---|---|
   | Negocio que no estaba | Un importado `nuevo` (cola de revisión, como hoy) |
   | Cambió un dato (teléfono, dirección, horario, web, rubro) | Un **cambio pendiente**: campo, antes, después |
   | No aparece **3 días seguidos** | Marca «ya no figura en la fuente» (posible cierre) para revisar |
   | Igual que ayer | Sólo actualiza «visto por última vez» |
3. **Ubica sólo lo nuevo o lo que cambió de dirección**, con un **caché permanente** de Nominatim: unos pocos
   pedidos por día en vez de cientos por corrida.
4. **Deja un resumen** de la corrida en el panel.

**Nunca publica ni pisa nada solo.** Un cambio en un negocio ya promovido aparece como propuesta en el panel:
«La página de turismo cambió el teléfono de X: *aplicar* / *ignorar*». El dato del comercio (lo cargó él o el
equipo) puede ser más nuevo que el de la página.

## Fuentes

| Fuente | Cómo se lee | Qué trae |
|---|---|---|
| `turismo` (tarijaturismo.com) | Las 7 páginas de lista (`SITIOS`) | Nombre, dirección, teléfonos, rubro |
| Fichas de «Qué hacer» | Sólo la ficha de un negocio nuevo o cambiado | Horario y dirección completa |
| `osm` (OpenStreetMap, Overpass) | **Una** consulta por ciudad | Negocios con punto exacto, horario, web |

**Agregar una fuente = un lector nuevo.** Cada fuente tiene una función que devuelve la misma `Entrada`
(nombre, dirección, teléfonos, enlace, horario…). El resto (comparar, cambios, ubicar, resumen) es común.

**OSM ayuda a ubicar sin Nominatim.** El paso «por nombre» del ubicador primero busca el nombre entre los
negocios de OSM de la ciudad que ya se trajeron. Sólo si no está, le pregunta a Nominatim.

## Modelo de datos (migración nueva)

- `comercios_importados`, columnas nuevas:
  - `huella`: hash de los campos comparables;
  - `visto_at`: última vez que la fuente lo mostró;
  - `ausente_desde`: primera corrida en que faltó; se borra si vuelve.
- `importados_cambios`: `importado_id`, `comercio_id` (si ya fue promovido), `campo`, `antes`, `despues`,
  `detectado_at`, `estado` (`pendiente` / `aplicado` / `ignorado`), `revisado_por`, `revisado_at`.
  Sólo borrado lógico.
- `geocache`: `consulta` normalizada, `ciudad_id`, `rango_minimo`, `largo_maximo_m`, `resultado` (jsonb, también
  «no encontrado»), `consultado_at`. Vale 90 días; los «no encontrado», 7 días.
- `vigia_corridas`: `fuente`, `ciudad_id`, `inicio`, `fin`, `leidas`, `nuevas`, `cambiadas`, `ausentes`,
  `pedidos_nominatim`, `error`.

Todas con RLS activo y sin acceso para `anon`. Sólo las usa el backend con `service_role`. Los GRANT van
explícitos en la migración.

## Cómo corre

- Un loop más en el `lifespan` del backend, como los otros diarios (AGENTS.md §7.13: un solo worker). Arranca a
  las 04:00 de Bolivia.
- **Apagado por defecto**: se enciende con `VIGIA_FUENTES_ACTIVO=1` en `backend/.env`. Costo cero: sólo usa
  servicios gratuitos.
- También a mano: `python -m app.services.vigia --ciudad tarija [--fuente turismo] [--dry-run]`.
- Si una fuente falla (página caída, HTML cambiado: «0 negocios leídos» cuando ayer había 340), la corrida queda
  con `error` y **no marca a nadie como ausente**. Así un cambio del sitio no se confunde con cierres masivos.

## Clave del negocio (ojo)

Hoy `fuente_id` de turismo es `nombre|dirección`: si cambia la dirección, parece un negocio nuevo y el viejo «ya
no figura». La comparación junta esos dos casos por nombre, dentro de la misma corrida, y los registra como **un
cambio de dirección**.

## Panel

Sección «Novedades de fuentes» en Importados:

- el resumen de la última corrida por fuente;
- la lista de cambios pendientes, con «aplicar» o «ignorar»;
- la lista de «ya no figura».

## Límites (no cambian)

- Sólo datos y el enlace a la fuente: no se copian textos ni fotos.
- Nada de Google.
- No se manda ningún mensaje a los comercios.
- Nominatim: un pedido por segundo y siempre a través del caché.

## Fases

1. `geocache`, y que `ubicar_direccion` lo use. Arregla ya el problema del 16/11.
2. Vigía de `turismo`: comparar, cambios, ausentes, corridas, comando a mano y loop apagado.
3. Panel «Novedades de fuentes».
4. OSM diario, y el paso «por nombre» contra OSM local.
5. Fichas de «Qué hacer»: horario y dirección completa.
6. Más fuentes, según las que haya.
