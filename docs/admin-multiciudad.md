# Admin multiciudad — spec

> **Estado: Fase 1 implementada el 4/10/2026, sin desplegar y sin probar en un
> navegador.** Las fases 2 y 3 siguen sin aprobar. Ver «Estado de la Fase 1» al
> final.

## El problema

El panel nació para una ciudad y hoy carga comercios de varias. Medido el 4/10
sobre las 22 pestañas:

- **Ninguna pestaña filtra por ciudad en el servidor.** Negocios filtra, pero
  en el navegador y sólo su lista.
- **Lugares y Adornos están clavadas en Bermejo en las dos puntas**: el
  componente no manda ciudad y el backend cae en `bermejo`. El mapa centra en
  coordenadas fijas. Un mercado de Santa Cruz no se puede cargar.
- **«Clasificar por fotos» mezcla todas las ciudades** y le dice al modelo que
  el local es de Bermejo, ciudad de frontera.
- **Difusión firma toda oferta «📍 {comercio}, Bermejo»**, sea de donde sea.
- **Importados** ya acepta ciudad en el backend; el panel no la manda.
- El token del panel ya lleva la ciudad del usuario. Sólo la usa la app de
  campo.

## Qué se construye

1. **Un selector de ciudad en la cabecera del panel**, igual al del home, con
   «Todas las ciudades» como opción.
2. **Un resumen por ciudad** arriba de Negocios: una fila por ciudad con sus
   totales. Tocar una fila elige esa ciudad.
3. **Cada pestaña respeta la ciudad elegida** donde el dato tiene ciudad.

## Decisiones

- **Es un filtro, no un permiso.** Cualquiera con acceso a una pestaña puede
  mirar cualquier ciudad. Restringir por ciudad es otra feature.
- **Arranca en la ciudad del usuario** si tiene una asignada; si no, en
  «Todas». Se recuerda por navegador.
- **No comparte la cookie del sitio público.** Cambiar el filtro del panel no
  tiene que cambiarle la ciudad al sitio, y la cookie pública no tiene «todas».
- **Lista todas las ciudades de `ciudades`**, activas o no: en el panel se
  cargan comercios antes de abrir una ciudad al público. Las inactivas van
  marcadas.
- **El filtro va en el servidor en toda lista con tope.** Filtrar en el
  navegador una lista cortada en 200 da un número plausible y falso. Sólo
  Negocios filtra en el navegador, porque ya trae todo paginado.
- **Lugares y Adornos necesitan una ciudad concreta** (son un mapa). Con
  «Todas» elegido piden elegir una; no caen en Bermejo.
- **Vencimientos, Planes, Rubros y Compradores son globales.** El selector se
  ve atenuado con la leyenda «esta pestaña no depende de la ciudad».
- **Una pestaña que todavía no filtra lo dice.** Mientras las fases 2 y 3 no
  estén hechas, esas pestañas muestran «esta pestaña todavía muestra todas las
  ciudades». Un selector que dice «Santa Cruz» sobre una lista que muestra todo
  sería una guarda que no protege.
- **Una ciudad que no existe da error, no Bermejo.** Lugares y Adornos caían en
  Bermejo ante cualquier slug desconocido. Ahora contestan 404. Sin parámetro
  siguen en Bermejo, para no romper los bundles viejos que quedan en el
  service worker.

## Fases

### Fase 1 — sin migraciones

| Pieza | Cambio |
|---|---|
| Cabecera | Selector de ciudad, con estado compartido por todas las pestañas |
| Negocios | Usa el selector global; se va su desplegable propio |
| Resumen por ciudad | Por ciudad: total · con foto sin clasificar · incompletos · sin horario · sin verificar. Sale de la misma lista que Negocios, para que no haya dos números |
| Contador «pend.» de la pestaña | Cuenta real de la ciudad elegida; hoy es el tope de 200 de una consulta |
| Clasificar por fotos | El número y la tanda siguen la ciudad elegida |
| Prompt de análisis | Nombra la ciudad del comercio. La regla de sinónimos «argentino / boliviano» sólo para ciudades de frontera |
| Lugares, Adornos | Lista, alta y centro del mapa de la ciudad elegida, con sus tiles |
| Importados | Filtra por ciudad y muestra el resumen por ciudad que el backend ya devuelve |
| Difusión (texto) | «📍 {comercio}, {ciudad del comercio}» |

### Fase 2 — sin migraciones, filtro en servidor a través del comercio

Publicaciones, Suscripciones, Pagos, Reclamos, Cambios de número, Recepción,
Difusión (la cola), Monitoreo y KPIs (lo que sale de comercios, leads y
visitas), Ayuda (saber local y sus textos) y Equipo.

Lo que no tiene comercio —un mensaje de WhatsApp sin atribuir, un reclamo sobre
la plataforma— no tiene ciudad: se muestra sólo con «Todas».

### Fase 3 — necesita migración

- **Revisar rubros:** la función `rubros_a_revisar` no recibe ni devuelve
  ciudad; hay que redefinirla.
- **Demanda y las búsquedas de KPIs:** `busquedas` no guarda ciudad. Se puede
  empezar a guardar; el histórico queda sin ciudad para siempre.

## Criterios de aceptación — Fase 1

1. Elegir Santa Cruz en la cabecera y recorrer Negocios, Lugares, Adornos e
   Importados: en ninguna aparece un dato de otra ciudad.
2. El resumen por ciudad suma, entre todas sus filas, el total de Negocios.
3. Con Santa Cruz elegida, «Clasificar por fotos» dice cuántos hay de Santa
   Cruz y analiza sólo ésos.
4. Un lugar creado con La Paz elegida queda en La Paz, y el mapa abre centrado
   en La Paz.
5. Con «Todas», Lugares y Adornos piden elegir ciudad.
6. Al recargar el panel, la ciudad elegida sigue elegida.
7. El texto de difusión de un comercio de Tarija dice Tarija.
8. Los tests del backend siguen verdes y `tsc` no da errores.

## Fuera de alcance

- Permisos por ciudad (que un moderador de Santa Cruz no vea La Paz).
- Una dirección por ciudad en el sitio público (`uruku.bo/santa-cruz`): es el
  pendiente grande del handoff y es otra feature.
- La app de campo y sus valores por defecto en `bermejo`.
- Clima, cotización y estado de frontera por ciudad.

## Pregunta abierta

**Qué cuenta como «pendiente».** Hoy los 1308 comercios están sin verificar y
ninguno verificado, así que «sin verificar» por ciudad va a repetir el total.
El resumen propuesto muestra las cinco columnas y deja que se vea cuál sirve;
si «pendiente» es una sola de ellas, se dice y las otras se sacan.

## Estado de la Fase 1

**Verificado:** 859 tests del backend en verde (94 nuevos de esta fase, en
`test_admin_multiciudad.py` y `test_admin_multiciudad_qa.py`) y `tsc` sin
errores. Pasó por QA y por revisión de código, y sus hallazgos están
integrados.

**Sin verificar:** nada de la interfaz se abrió en un navegador. No hay tests
de frontend en el repo y la base no es alcanzable en local. El layout de la
cabecera en teléfono, el desplazamiento de la tabla de resumen y el recentrado
de los mapas se ven recién en producción.

**Lo que salió de la revisión y no estaba en la spec:**

- El listado de comercios tiene un tope de 5000. De esa lista salen el contador
  de la pestaña y el resumen por ciudad, así que ahora el backend avisa cuando
  llega al tope y el panel lo dice en rojo. El tope sigue ahí: el arreglo de
  fondo es filtrar en el servidor.
- Si la tabla de ciudades no se puede leer, el panel lo dice y queda en
  «todas». Antes habría caído en una lista de demostración con ids inventados.
- El prompt de análisis toma el país de la ciudad. La tabla tiene ciudades
  argentinas y «en La Quiaca, Bolivia» era el mismo dato supuesto con otro
  nombre.

**Limitaciones conocidas, sin arreglar:**

- En Adornos, los comercios de fondo se traen por un recuadro alrededor del
  centro de la ciudad, no por ciudad. Dos ciudades a pocos kilómetros (Villazón
  y La Quiaca) se verían mezcladas en ese fondo. Son sólo referencia visual.
- Quien tiene ciudad asignada ve «todas» por un instante en Negocios, hasta que
  cargan las ciudades y el panel se para en la suya.
