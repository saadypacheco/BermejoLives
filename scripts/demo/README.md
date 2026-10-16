# Demo local de URUKU (datos ficticios)

Un URUKU completo en tu máquina, con comercios, ofertas, usuarios y farmacias de
turno **inventados**, para sacar capturas de los manuales y grabar videos. No toca
producción ni QA: todo corre en `127.0.0.1` con puertos propios.

## Levantar y bajar

Requisitos: Docker Desktop abierto, Python 3.12 con las dependencias del backend
(`pip install -e backend`), y `npm install` hecho en `frontend/`.

```bash
python scripts/demo/demo.py up            # levanta todo; la primera vez migra (~1 min) y siembra (~3 min)
python scripts/demo/demo.py status        # qué está corriendo
python scripts/demo/demo.py seed          # vuelve a sembrar (idempotente)
python scripts/demo/demo.py down          # baja backend y frontend (por PID)
python scripts/demo/demo.py down --docker # además detiene los contenedores (la base queda para el próximo up)
python scripts/demo/demo.py down --borrar # además borra los contenedores demo-manual-* (base incluida)
python scripts/demo/demo.py reset         # base de cero: borra todo y vuelve a levantar
```

| Pieza | Dónde | Notas |
|---|---|---|
| Sitio (next dev) | http://localhost:3990 | compila en `frontend/.next-demo` (no pisa tu `npm run dev`) |
| Backend (uvicorn) | http://localhost:8990 | `.env` de demo en `scripts/demo/.run/.env` |
| PostgREST | http://localhost:3999/rest/v1/ | nginx `demo-manual-gw` → `demo-manual-rest` |
| Postgres 16 | 127.0.0.1:5999 (`postgres` / `demo`) | contenedor `demo-manual-pg` |
| Teselas del mapa | http://localhost:3998/{z}/{x}/{y}.png | `demo-manual-tiles`: el caché de `selfhost/tiles/nginx.conf` delante de OSM |

Docker a mano, si hiciera falta: `docker stop demo-manual-tiles demo-manual-gw demo-manual-rest demo-manual-pg`
(o `docker rm -f …` y `docker network rm demo-manual-net` para borrarlos).

Lo que arma `up` queda en `scripts/demo/.run/` (ignorado por git): el `.env` del
backend, las fotos, los logs (`backend.log`, `frontend.log`) y los PID.

Migraciones: se aplican `selfhost/postgres-init/*.sql` en orden y se anotan en
`demo.migraciones` (esquema que PostgREST no expone): cada `up` aplica sólo las
nuevas. En un Postgres vanilla fallan siempre las mismas tres (0049, 0069, 0070;
lo que crean lo rehacen migraciones posteriores); la 0092 se aplica borrando antes
la función que cambia. Si `up` avisa de otra, es una migración nueva que no corre
en vanilla: mirala antes de seguir.

WhatsApp (WAHA), la IA (Gemini/OpenAI), la difusión, el clima y Reservalo están
**apagados**: sin claves y con los workers en `false`.

## Usuarios de demo

Panel (`/admin`, `/contenido`, `/publicar`) — clave **`demo1234`** para todos:

| Correo | Rol | Ciudad |
|---|---|---|
| `admin@demo.test` | Administrador | Bermejo |
| `moderador@demo.test` | Moderador | Bermejo |
| `publicador@demo.test` | Publicador | Bermejo |
| `agente@demo.test` | Agente de campo | Bermejo |
| `agente.yacuiba@demo.test` | Agente de campo | Yacuiba |
| `revisor@demo.test` | Revisor (modera, no edita fichas) | Bermejo |

Mi comercio (`/mi-comercio`): celular **`70000101`**, clave **`BOUTIQUE-DEMO26`**
→ «Boutique Ejemplo» (plan Destacado por vencer en 4 días: estrella, chatbot,
aviso de pago, ofertas en todos los estados).

Comprador (`/perfil`): celular **`70000201`**, clave **`246810`** (3 locales guardados).

## Qué hay sembrado

- Bermejo y Yacuiba activas; zonas; dos «lugares» (Galería Comercial Central, Mercado Central).
- 33 comercios en Bermejo (uno dado de baja y un borrador) y 5 en Yacuiba, con GPS dentro del casco, portada y galería
  (dibujadas por la semilla con Pillow, o fotos de `frontend/public/`), horarios
  variados (abiertos, cerrados, sin horario), «Lo que suma», planes: pagos al día,
  uno por vencer, uno vencido con comprobante por confirmar, uno suspendido, uno de
  cortesía; uno dado de baja y un borrador.
- Ofertas y novedades aprobadas, pendientes (con veredicto de IA), «pide cambios» y
  rechazadas; recepción de WhatsApp, difusión, reclamos, mensajes, un pedido de cambio
  de número, importados de OSM, adornos del mapa, Ayuda sin respuesta.
- Visitas, contactos y búsquedas de los últimos 30 días (para Inicio, KPIs y Demanda).
- Farmacias de turno: el rol de `backend/data/turnos_farmacia/…json` importado con
  `python -m app.scripts.importar_turnos_farmacia`, **con los teléfonos reemplazados**
  por números ficticios (el archivo trae celulares reales). Cubre del 4/10 al 12/12/2026.
- Calles de Bermejo desde OpenStreetMap (si no hay red, unas pocas a mano) con marcas
  de recorrido del centro hacia afuera.
- Novedades de URUKU, cotizaciones y clima fijos.

Teléfonos: `5917000NNNN` (inventados). Correos: `@demo.test` (dominio reservado).

## Capturas para los manuales

Con la demo levantada:

```bash
node scripts/capturas-manual.mjs                 # todas las de docs/manuales/capturas.json
node scripts/capturas-manual.mjs --solo "^vendedor/0[1-5]"   # algunas
```

Salen en `frontend/public/manuales/capturas/<perfil>/<id>-mobile.png` / `-desktop.png`.
Si una falla, la pantalla tal como quedó va a `scripts/demo/.run/fallas/`, y el
resumen de la corrida a `scripts/demo/.run/capturas-resultado.json`.

Algunas capturas escriben en la demo: el alta del agente («Demo …», en un punto
lejos del centro), el autoregistro («Almacén Doña Rosa») y generar la clave de
«Panadería El Sol». Por eso el script sólo se usa contra la demo, y cada corrida
suma un par de comercios; `demo.py reset` deja la base como recién sembrada.

Lo que la demo no puede mostrar de verdad se simula sólo en la captura:
- la galería llena (vendedor/11, agente/12): el script intercepta la API y contesta
  el tope (409) sin tocar la base;
- «¿Te contestó…?» (comprador/26): se precarga el contacto de hace 5 minutos en el
  navegador en vez de esperar 3 minutos;
- el selector de ciudad abierto (admin/03): un `<select>` nativo no sale en una
  captura, así que se dibuja la lista encima.

## Pasar las capturas a WebP (lo que usa el sitio)

Después de `node scripts/capturas-manual.mjs`:

```
python scripts/demo/capturas_a_webp.py
```

Los PNG quedan en la máquina (ignorados por git) para editar los videos; los manuales usan el `.webp`.
