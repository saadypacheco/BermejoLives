# Chatbot de los comercios — spec

> **Estado: implementada el 5/10/2026, sin desplegar.** Ver «Estado» al final.

## Decisión

URUKU usa su propio chatbot en la ficha de cada comercio. Se descartó el agente
de IA de Meta en WhatsApp Business: cuesta desde USD 15 por mes para el
comerciante, el precio lo fija Meta, y no se pudo confirmar que esté disponible
en Bolivia.

| Plan | Ficha |
|---|---|
| Básico, Publica | Sólo el botón de WhatsApp, como hoy |
| **Destacado** | **Chatbot sin IA** + derivación a WhatsApp |
| **Pro** | **Chatbot con IA** + derivación a WhatsApp |
| Empleado Digital | Igual que Pro (el plan está oculto) |

## Cómo sabe las cosas

No se entrena: en cada pregunta lee la base.

- **De la ficha:** horario, dirección, WhatsApp, qué vende, descripción.
- **Las ofertas publicadas:** una oferta nueva, apenas se aprueba, ya la
  conoce.
- **Las respuestas del local (nuevo):** preguntas y respuestas que carga el
  comerciante desde su cuenta («¿hacen envíos?» → «Sí, a todo Bermejo por Bs
  10»). Cuando el chatbot no sabe algo, la pregunta queda anotada; el
  comerciante la contesta una vez en «Mi comercio» y desde ahí el chatbot la
  contesta solo.

## Sin IA y con IA

- **Sin IA (Destacado):** contesta lo que sale directo de la base: horario,
  dirección, contacto, ofertas, **qué vende** (nuevo) y las respuestas del
  local que se parezcan a la pregunta. Costo por pregunta: cero.
- **Con IA (Pro):** además, si eso no alcanza, Gemini contesta con todos los
  datos de arriba en el prompt, incluidas las respuestas del local.

## La derivación a WhatsApp

Cuando el chatbot no sabe, muestra un botón **«Preguntarle a {comercio} por
WhatsApp»**. Abre el WhatsApp del comprador con este mensaje ya escrito:

> Hola, te escribo desde URUKU. Le pregunté a tu asistente: «{pregunta}»

Sólo la pregunta que no supo contestar, no la conversación entera. El
comprador toca enviar y el comerciante le contesta directo. No pasa por WAHA
ni por la API de Meta: es un enlace `wa.me`, como el botón de la ficha. El
clic se registra como contacto de WhatsApp, igual que hoy. Si el comercio no
tiene WhatsApp cargado, no hay botón y el chatbot dice cómo llegar.

## Decisiones técnicas

- **Dos funciones de plan:** `asistente_24_7` (el chatbot, con derivación) y
  `asistente_ia` (nueva: habilita la IA). La migración se las da a Destacado
  (la primera) y a Pro y Empleado Digital (las dos), y actualiza las viñetas
  de esos planes. Sin mencionar las redes de URUKU.
- **Las respuestas del local van en `saber_local`** con una columna nueva
  `comercio_id` (NULL = el saber de URUKU). El asistente del sitio **nunca**
  usa las filas de un comercio, y el chatbot de un comercio sólo usa las suyas.
- **La ficha decide si muestra el chatbot por la función del plan**, no por el
  nombre del plan. Hoy está escrito fijo «empleado_ia», y con eso el chatbot no
  se ve en ningún otro plan.
- Soft-delete en las respuestas del local.

## Criterios de aceptación

1. Un comercio Destacado tiene chatbot en su ficha; uno de Publica, no.
2. El chatbot de un Destacado nunca llama a la IA; el de un Pro sí, cuando la
   base no alcanza.
3. «¿Qué venden?» se contesta sin IA con lo que dice la ficha.
4. Una respuesta del local cargada por el comerciante contesta una pregunta
   parecida, sin IA.
5. Una respuesta del local nunca aparece en el asistente del sitio ni en el
   chatbot de otro comercio.
6. Cuando no sabe, la respuesta trae la derivación: el número del comercio y el
   texto con la pregunta. Sin WhatsApp cargado, no trae derivación.
7. El comerciante ve sus preguntas sin respuesta, contesta una y desde ahí el
   chatbot la contesta.
8. El comerciante puede ver, agregar, editar y borrar sus respuestas.
9. Tests del backend verdes y `tsc` sin errores.

## Estado

**Verificado:** 1144 tests del backend en verde y `tsc` sin errores. Pasó QA y
revisión de código, y una ronda de arreglos con sus hallazgos. **Sin
verificar:** la migración no se corrió contra una base real y nada se abrió en
un navegador.

**Decisiones del usuario durante la implementación (5/10/2026):**
- Las respuestas del local salen sin moderación. URUKU las ve en Admin › Ayuda ›
  «Respuestas de los locales» y puede desactivar una.
- Un comercio suspendido o vencido sigue con chatbot hasta que sale del mapa.

**Lo que corrigió la revisión:**
- `saber_local` era legible por el público desde la 0110: con la columna nueva,
  cualquiera habría leído las respuestas de todos los locales y el email de cada
  dueño. La 0136 limita al público al saber de URUKU y le quita `creado_por`, y
  las respuestas nuevas guardan `comercio:<id>` en lugar del email.
- El admin ya no puede convertir una pregunta de una ficha en saber del sitio.
- Horario, dirección y contacto se contestan antes que las respuestas del local,
  y éstas matchean sólo por su pregunta: antes «¿a qué hora abren?» podía
  contestarse con la respuesta del delivery.
- Las respuestas del local entran al prompt del Pro como datos citados,
  recortados y sin saltos de línea, con las reglas antes.
- Un Pro sin ofertas prueba la IA antes de decir que no sabe.
- El botón de WhatsApp sólo aparece con un número válido.
- Tope de 200 respuestas por comercio, con aviso.

**Pendientes conocidos:**
- El tope de 200 no es atómico: dos altas simultáneas pueden pasarlo por una.
- Un comercio sin chatbot puede cargar respuestas; no se usan hasta que su plan
  lo incluya.

## Fuera de alcance

- Que el chatbot avise al comerciante por WhatsApp (WAHA está en sólo
  lectura).
- Respuestas del local cargadas por el agente de campo (el admin sólo puede
  activarlas o desactivarlas).
- Métricas de cuántas derivaciones terminan en venta.
