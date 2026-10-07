# Rediseño del panel de administración — spec

> **Estado: implementada el 6/10/2026.**

## El problema

- **23 pestañas en una fila** que se parte en tres renglones: nada se encuentra.
  «Calles» (cargar horarios por calle) ni siquiera está en la fila: es un botón
  dentro de Negocios, y el dueño no lo encontró.
- **Lento al entrar**: el panel baja la lista COMPLETA de comercios (1.300+ filas
  con todas sus columnas) y otras seis listas antes de mostrar un número. Los
  totales de las pestañas salen de contar esas listas en el navegador.
- **No hay un tablero**: no hay una pantalla que diga cómo está todo y qué hay
  que hacer hoy.

## Qué se construye

### 1. Estructura

- **Barra de arriba, fija**: URUKU (lleva al Inicio del panel), el selector de
  **ciudad** (el `SelectorCiudad` de hoy, con su aviso de pestañas que no
  filtran), **Ver sitio**, y el usuario con **Salir**.
- **Menú lateral** con todo lo demás, agrupado (ver tabla). Cada ítem con ícono
  (`<Ic>`, nunca emoji), su nombre y, si hay algo pendiente, un número. Se
  respetan los permisos de hoy (`puedo(...)`).
- **En el celular** (el admin lo usa desde el teléfono): el menú se esconde y se
  abre con un botón en la barra de arriba; al elegir una sección se cierra.
- **La sección va en la URL** (`/admin?s=negocios`): el botón Atrás funciona y se
  puede mandar un enlace a una sección.
- **El contenido usa todo el ancho** (hoy está encerrado en 1000 px).

### 2. Menú (no se pierde nada de lo que hay)

| Grupo | Sección (`id`) | Era la pestaña | Permiso |
|---|---|---|---|
| — | Inicio (`inicio`) | **nueva** | — |
| Comercios | Negocios (`negocios`) | Negocios (lista y mapa) | — |
| | Calles y horarios (`calles`) | Negocios › Calles | — |
| | Lugares (`lugares`) | Lugares | lugares |
| | Importados (`importados`) | Importados | datos |
| | Adornos (`adornos`) | Adornos | lugares |
| | Cambios de número (`cambio-numero`) | Cambios de número | — |
| Contenido | Publicaciones (`publicaciones`) | Publicaciones | — |
| | Recepción (`whatsapp`) | Recepción | whatsapp |
| | Difusión (`difusion`) | Difusión | difusion |
| | Reclamos (`reclamos`) | Reclamos | — |
| Catálogo | Catálogo (`catalogo`) | Catálogo | datos |
| | Rubros (`rubros`) | Rubros | rubros |
| | Revisar rubros (`revision-rubros`) | Revisar rubros | rubros |
| Campo | Cargas (`cargas`) | Cargas | equipo |
| Negocio | Planes (`planes`) | Planes | planes |
| | Suscripciones (`suscripciones`) | Suscripciones | — |
| | Pagos (`pagos`) | Pagos | — |
| | Vencimientos (`vencimientos`) | Vencimientos | — |
| Análisis | Monitoreo (`monitoreo`) | Monitoreo | — |
| | KPIs (`kpis`) | KPIs | — |
| | Demanda (`demanda`) | Demanda | datos |
| | Compradores (`compradores`) | Compradores | datos |
| Equipo | Equipo (`equipo`) | Equipo | equipo |
| | Ayuda (`ayuda`) | Ayuda | ayuda |

La fuente única es `frontend/components/admin/secciones.ts`.

### 3. Inicio: el tablero

Lo primero que se ve al entrar. Sale de **un solo pedido** (`GET /admin/resumen`),
no de bajar listas.

- **Para hacer hoy** (arriba, lo más visible): cada pendiente con su número y un
  botón que lleva a la sección: publicaciones por moderar, comercios sin
  verificar, pagos por confirmar, reclamos, cambios de número, suscripciones por
  vencer o vencidas, alertas de vencimientos, mensajes de Recepción sin comercio.
  Lo que está en cero no ocupa lugar (o se muestra apagado, «al día»).
- **Tarjetas** con los números grandes: comercios, verificados (%), con horario
  (%), con WhatsApp (%), visitas 7 días, contactos 7 días.
- **Gráficos** (SVG propios, sin librerías nuevas):
  - Altas por día, últimos 30 días (barras).
  - Visitas y contactos por día, últimos 30 días (líneas).
  - Fichas completas: horario, WhatsApp, foto, rubro (barras de progreso).
  - Comercios por ciudad, con sin verificar y sin horario (barras).
- Respeta la ciudad elegida arriba en los comercios, sus tarjetas y la actividad.
  «Por ciudad» muestra siempre todas. Los pendientes (salvo «sin verificar»)
  son de todas las ciudades, porque su sección todavía lista todo; con una
  ciudad elegida, la fila dice «de todas las ciudades».

### 4. Rápido

- **Nada se baja al entrar** salvo `/admin/resumen`. Cada sección pide sus datos
  cuando se abre (la lista de comercios, sólo en Negocios, Calles o donde se use).
- **Los números del menú** salen de `/admin/resumen`, no de contar listas. Se
  refrescan al volver al Inicio y cuando una acción cambia algo (aprobar,
  verificar, confirmar un pago…).

### 5. Contrato `GET /admin/resumen?ciudad=<slug>`

Cualquier usuario logueado en el panel. `ciudad` opcional (sin ella, todas).
Tipo en `frontend/lib/api.ts` → `ResumenAdmin`. Los conteos van todos en la misma
respuesta; si una parte falla (p.ej. Reservalo no contesta) esa parte viene en
`null` y el resto igual.

## Criterios de aceptación

1. Cada una de las 23 pestañas de hoy está en el menú lateral y hace lo mismo
   que hacía. Calles y horarios tiene su propio ítem.
2. Al entrar se ve el Inicio con números y gráficos sin esperar la lista de
   comercios (un solo pedido).
3. Ningún dato se baja al entrar salvo el resumen; cada sección carga lo suyo.
4. En un celular de 360 px el menú se abre y cierra, nada se sale de la
   pantalla de costado y los botones se tocan cómodos.
5. `/admin?s=calles` abre directo Calles y horarios; Atrás vuelve a la anterior.
6. `tsc` sin errores; tests del backend en verde.
