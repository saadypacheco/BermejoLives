# Cargas del día: qué cargó cada agente, cuándo y por dónde — spec

> **Estado: implementada el 6/10/2026.**

## El problema

El admin no puede ver cómo trabajó un agente: a qué hora empezó, cuánto paró,
cuántos comercios cargó por hora ni qué recorrido hizo. «Altas por día»
(Monitoreo) da totales por día, y además corta el día en UTC: lo cargado
después de las 20:00 de Bolivia cae en el día siguiente.

Y la hora que hay es la de llegada al servidor (`created_at`). Lo cargado sin
señal queda en la cola del celular y llega todo junto cuando vuelve la señal:
diez comercios «cargados» en el mismo minuto. La cola ya guarda la hora real
(`creado` en `lib/offline-altas.ts`), pero no la manda.

## Qué se construye

### 1. La hora del celular

- Migración **0138** (`supabase/migrations/` y `selfhost/postgres-init/`,
  idénticas): `comercios.capturado_en timestamptz` (null en lo viejo) + índices
  parciales sobre `capturado_en` y `created_at` (`where cargado_por is not null`).
  **El deploy va con `--sql` de la 0138** (si no, el alta pierde la hora del
  celular hasta que se corra, pero no se cae).
- `POST /campo/comercio` acepta `capturado_en` (ISO 8601). Se guarda sólo si
  está entre «hace 7 días» y «dentro de 5 minutos»; si no, se descarta y se
  loguea `campo.capturado_en_descartado` (un reloj de celular mal puesto no
  puede mover una carga a otro mes).
- El celular la manda siempre: con señal, la hora del «Guardar»; desde la cola,
  `creado` del registro (así también las altas que YA están en cola).

**La hora de una carga** = `capturado_en` si existe, si no `created_at`.
**El día** es el de Bolivia: UTC−4 fijo (Bolivia no tiene horario de verano).

### 2. Backend (sólo admin: `require_admin`)

`GET /admin/cargas/dia?fecha=YYYY-MM-DD&ciudad=<slug>` — `fecha` por defecto hoy
(Bolivia); `ciudad` opcional. 400 si la fecha no es válida.

```json
{
  "fecha": "2026-10-06",
  "agentes": [{
    "agente": "pedro@uruku.bo",
    "comercios": 23,
    "desde": "09:12", "hasta": "17:40",
    "minutos_trabajados": 395,
    "metros": 4210,
    "tramos": [{ "n": 1, "desde": "09:12", "hasta": "12:05", "minutos": 173, "comercios": 11 }],
    "por_hora": [{ "hora": "09", "comercios": 4 }],
    "puntos": [{
      "orden": 1, "tramo": 1, "id": "…", "slug": "…", "nombre": "…",
      "lat": -22.73, "lng": -64.34,
      "hora": "09:12", "hora_del_celular": true, "subido_tarde": false,
      "min_desde_anterior": null, "m_desde_anterior": null,
      "foto": "<portada_thumb_url|null>", "rubro": "…", "ciudad": "Bermejo"
    }]
  }]
}
```

`GET /admin/cargas/historial?dias=60&ciudad=<slug>` (`dias` 1..365):

```json
{ "items": [{ "fecha": "2026-10-06", "agente": "pedro@uruku.bo", "comercios": 23,
              "desde": "09:12", "hasta": "17:40", "minutos_trabajados": 395,
              "tramos": 2, "metros": 4210 }] }
```
Ordenado por fecha descendente y después por agente.

Reglas de cálculo:
- Sólo comercios **activos** con `cargado_por` (los importados no tienen agente).
- **Tramo** nuevo cuando pasan **más de 30 minutos** desde la carga anterior del
  mismo agente. `minutos_trabajados` = suma de la duración de los tramos.
- `metros` = suma de las distancias en línea recta (haversine) entre cargas
  consecutivas **del mismo tramo** (el salto entre tramos —almuerzo, otra zona—
  no es recorrido de trabajo). Puntos sin lat/lng no suman.
- `subido_tarde` = llegó al servidor más de 10 minutos después de
  `capturado_en` (se cargó sin señal).
- `hora_del_celular` = true si la hora sale de `capturado_en`.
- Un comercio cuenta en el día de SU hora de carga, aunque haya llegado al
  servidor al día siguiente.
- «Altas por día» (`altas_por_dia`) pasa a cortar los días en hora de Bolivia.

### 3. Admin: pestaña «Cargas»

Respeta el selector de ciudad del panel (`useAdminCiudad`).

1. **Historial** (arriba): tabla fecha · agente · comercios · desde–hasta ·
   horas trabajadas · km. Tocar una fila abre ese día y ese agente abajo.
2. **El día**: selector de fecha (hoy por defecto) y de agente (los que
   cargaron ese día). Resumen (comercios, desde–hasta, tiempo trabajado, km,
   tramos), barras por hora (CSS, sin librerías nuevas).
3. **El recorrido**: mapa Leaflet (`loadLeaflet`, `agregarTiles`) con los
   puntos numerados en orden y una línea que los une, un color por tramo. Tocar
   un punto: nombre, hora y foto.
4. **La lista**: # · hora · nombre · minutos y metros desde el anterior, y la
   marca «subido más tarde (sin señal)».
5. Aviso fijo: antes del 6/10 la hora es la de llegada al servidor.

## Criterios de aceptación

1. Una carga sin señal a las 10:00 que sube a las 13:00 aparece a las 10:00.
2. Una carga a las 22:00 de Bolivia cuenta en ese día, no en el siguiente.
3. Dos cargas separadas por 31 minutos quedan en tramos distintos; por 30, en el mismo.
4. Un `capturado_en` de dentro de una hora o de hace un mes se descarta.
5. Un token de agente, de comercio o sin token recibe 401/403 en `/admin/cargas/*`.
6. Desde el historial, un toque abre el día y el recorrido de ese agente.
7. `tsc` sin errores; tests del backend en verde.
