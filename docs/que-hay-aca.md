# «Qué hay acá»: la primera pantalla del agente — spec

> **Estado: implementada el 13/10/2026.**

## El problema (dueño, 13/10)

Parado frente a un local, el agente no sabe si ya está cargado. El aviso «Ya cargados acá
cerca» existe pero aparece recién dentro del alta, después de tomar el GPS. La idea: si no
está, lo carga y le ofrece la suscripción; si está, le muestra lo cargado y le ofrece.

## Decisiones (13/10)

1. **Primera pantalla del agente** (`/publicar`): «Qué hay acá», con mapa y lista.
2. «Ofrecer» = **ficha + lo que le falta + plan/estado**, **anotar interés** para el admin y
   **mandarle su ficha por WhatsApp** desde el celular del agente. **Sin precios** en la app
   (los precios están en la guía de venta).
3. **2 o 3 comercios completos de ejemplo** de la ciudad (mejor del mismo rubro), para
   mostrarle al dueño cómo se ve un local bien cargado. En un local recién cargado y en uno
   incompleto.
4. Guía de venta: el plan Básico es **gratis para siempre** (decisión del 12/10), no «el primer mes».

## Pantalla «Qué hay acá» (frontend, `/publicar`)

- Arriba, **mapa** (Leaflet, mismas teselas que el resto: `lib/mapa-tiles.ts`): el punto del
  agente con su precisión, un círculo de 100 m y un pin con la **miniatura de la portada** de
  cada comercio cargado cerca (toca el pin → abre su ficha). Botón «Actualizar mi ubicación».
- Abajo, **lista por distancia** (hasta 150 m; «Ver más lejos» amplía a 400 m): foto grande,
  nombre, «a 12 m», sello del plan (★ al día · De cortesía · Gratis · Vencido) y estado
  («Completo» o «Le faltan 3: horario, WhatsApp, fotos»).
- Botón fijo **«+ Cargar un local nuevo acá»** → el alta de hoy, con el GPS ya tomado.
- Funciona **sin señal** con la lista guardada (`lib/campo-cache.ts`), como hoy.
- El aviso «Ya cargados acá cerca» del alta queda (es la red de seguridad).

## Ficha del local para el agente (al tocar un comercio)

- Fotos (portada + galería), datos, «Lo que suma», **«Le falta»** (reusar la lógica de
  `components/completar-comercio.tsx`) con **«Completar»** (abre Completar comercio).
- Su **plan y estado** (sin precio).
- **«Mostrale cómo se ven otros»**: 2-3 ejemplos completos (tarjeta con portada, nombre y
  rubro; tocar abre su ficha pública en otra pestaña).
- **«Le interesa un plan»**: elegir el plan (sólo nombres) y una nota opcional → queda
  anotado para el admin.
- **«Mandarle su ficha por WhatsApp»**: abre `wa.me/<whatsapp del comercio>` (si no tiene,
  pide el número) con un mensaje armado: saludo, el link de su ficha
  `https://uruku.bo/comercios/<slug>`, qué gana completándola y que para sumarse a un plan
  responda ese mensaje. Sin precios. Sale del celular del agente (WAHA no envía).
- Después de un **alta nueva**, la pantalla de «listo» muestra los mismos ejemplos y las
  mismas dos acciones.

## Backend

- `GET /campo/mis-comercios` (la lista que ya se guarda en el celular) suma por comercio:
  `estado_plan` (`al_dia` | `cortesia` | `gratis` | `vencido`, sin precios ni `paga_hasta`),
  `fotos_count` y `rubro_slug`, lo justo para el sello y «Le falta» sin pedir nada más.
- `GET /campo/ejemplos?rubro=<slug>&excluir=<id>` → hasta 3 comercios **activos y completos**
  de la ciudad del agente (preferir el rubro; si no alcanza, otros): `{items: [{id, slug,
  nombre, rubro_nombre, portada_thumb_url}]}`. «Completo» = el mismo criterio que «Le falta»
  (portada, WhatsApp, horario, al menos 3 fotos de galería, lo que vende) — documentarlo en el código.
- `GET /campo/planes` → planes activos pagos `{items: [{slug, nombre}]}` (sin precios).
- `POST /campo/mis-comercios/{id}/interes` `{plan: slug, nota?: str ≤ 300}` (regla de ciudad
  de siempre) → registra en `comercio_eventos` (`tipo='interes_plan'`) con un `detalle jsonb`
  (`{plan, nota}`): migración **0151** suma `detalle jsonb` a `comercio_eventos` (privada).
- `GET /admin/suscripciones` suma a cada comercio `interes: {plan, nota, actor, created_at} | null`
  (el último interés sin pago posterior).

## Admin

- **Suscripciones**: sello «Interesado: Destacado · agente · fecha» y un chip **«Interesados (n)»**.

## Criterios

1. Al abrir `/publicar`, el agente ve el mapa con su punto y los comercios cercanos con foto; sin señal, la lista guardada.
2. Frente a un local no cargado, «Cargar un local nuevo acá» abre el alta con el GPS.
3. Al tocar uno cargado ve fotos, datos, Le falta, plan, 2-3 ejemplos, «Le interesa un plan» y «Mandarle su ficha por WhatsApp».
4. El interés aparece en Admin › Suscripciones con su chip.
5. Ningún precio en la app del agente; la guía de venta dice Básico gratis.
6. Tests verdes, `tsc` y `next build` ok, sin emoji.

## Criterio de completo (backend)

Lo implementa `es_completo(comercio, fotos_count)` en `backend/app/services/que_hay_aca.py` y es lo
que decide quién sale en `GET /campo/ejemplos`. Un comercio es **completo** si cumple las cinco:

1. **Portada**: `portada_url` con valor.
2. **WhatsApp**: `whatsapp` con valor (el `telefono` solo no alcanza).
3. **Horario**: `horario` con valor.
4. **Galería**: `fotos_count >= 3` (fotos de la galería, sin contar la portada).
5. **Lo que vende**: `prod_obs_human` con valor, o si no `descripcion`.

Un texto de puros espacios cuenta como vacío. Además, para ser ejemplo tiene que estar activo, no
suspendido y ser de la ciudad del agente. Para copiarlo en el frontend (con los datos de
`/campo/mis-comercios`, que ya trae `fotos_count`):

```ts
const lleno = (v?: string | null) => !!(v ?? "").trim();
const esCompleto = (c) =>
  lleno(c.portada_url) && lleno(c.whatsapp) && lleno(c.horario) &&
  (c.fotos_count ?? 0) >= 3 && (lleno(c.prod_obs_human) || lleno(c.descripcion));
```

(`/campo/mis-comercios` no trae `descripcion`: ahí usar sólo `prod_obs_human`.)

## Contrato del backend (implementado)

- `GET /campo/mis-comercios` -> cada item suma `estado_plan` (`al_dia` | `cortesia` | `gratis` |
  `vencido`), `fotos_count` (int) y `rubro_slug` (string | null). Nunca `plan`, precios ni `paga_hasta`.
  `GET /campo/mis-comercios/{id}` trae lo mismo.
- `GET /campo/ejemplos?rubro=<slug>&excluir=<id>` -> `{items: [{id, slug, nombre, rubro_nombre,
  portada_thumb_url}]}` (0 a 3).
- `GET /campo/planes` -> `{items: [{slug, nombre}]}`.
- `POST /campo/mis-comercios/{id}/interes` `{plan, nota?}` -> `{ok: true, plan, nota}`; 400 si el plan no
  existe o no es de pago, o la nota pasa de 300; 404 fuera de su ciudad.
- `GET /admin/suscripciones` -> cada item suma `interes: {plan, plan_nombre, nota, actor, created_at} | null`.
