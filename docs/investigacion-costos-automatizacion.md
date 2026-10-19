# Investigación: costos y riesgos de automatización para URUKU

> Fecha de consulta de todas las fuentes: **2026-10-19**. País: Bolivia (Bermejo). Moneda base: **USD**.
> Alcance: solo hechos, precios, límites y riesgos con fuente. No hay opinión de arquitectura.
> Los precios cambian (Meta puede cambiar tarifas cada trimestre; Google, Anthropic y los SaaS, sin aviso). Revalidar antes de comprometer presupuesto.

## Convenciones

- **Confirmado**: fuente oficial del proveedor, leída en esta sesión.
- **Probable**: fuente secundaria (blog, comparador, proveedor competidor) o lectura parcial de la oficial.
- **No encontrado / no confirmado**: no se pudo verificar; se indica dónde buscar.
- **Precio local en Bolivia**: no se encontró ningún precio en bolivianos publicado por ninguno de los proveedores; todos cotizan en USD. Referencia de tipo de cambio (probable): el BCB fijó **Bs 11,58 por USD** para el 15-17/ago/2026 y el paralelo rondaba Bs 11,40-11,43 (Correo del Sur, 2026-08-15). No pude verificar el valor de septiembre/octubre 2026: el tipo de cambio oficial ahora se publica a diario (tabla histórica en bcb.gob.bo). Para convertir, usar Bs ~11,5 por USD sólo como orden de magnitud.

## Resumen: opción · costo mensual estimado · riesgo · fuente

| Tema | Opción | Costo mensual estimado (USD) | Riesgo principal | Fuente | Confianza |
|---|---|---|---|---|---|
| Fotos | Gemini 3.1 Flash Lite Image / "Nano Banana 2.1", 1K | 300 fotos: ~$10 · 1.000: ~$34 · 3.000: ~$101 (mitad con Batch) | Sin cuota gratis; el precio por imagen no incluye (según lo leído) el costo de la imagen de entrada | [1] | Confirmado (precio de salida) |
| Fotos | Photoroom API Remove Background | 300: ~$20 · 1.000: ~$20 · 3.000: ~$56-60 | Plan mínimo $20 por 1.000 imágenes, sin rollover | [2][3] | Confirmado $0,02/img; plan mínimo probable |
| Fotos | remove.bg API | 300: ~$42-68 · 1.000: ~$140-225 · 3.000: ~$390 | API self-service cierra el 2026-12-01 (dato de un competidor) | [3][4] | Probable |
| Fotos | rembg local (u2net / isnet / BiRefNet) | $0 (usa PC o VPS propios) | RAM: BiRefNet y bria-rmbg se mataron con ~7 GB libres en un test; bria-rmbg no es gratis para uso comercial | [5][6][7] | Confirmado licencias; RAM probable |
| WhatsApp | App WhatsApp Business | $0 | Poca automatización (saludo, ausencia, respuestas rápidas); sin API | [8] | Probable (sin página oficial legible) |
| WhatsApp | Cloud API, solo responder dentro de 24 h | $0 hasta 1.000 mensajes de servicio/número/mes; luego $0,0113 c/u (Rest of LatAm) = $11,30 por cada 1.000 extra, más lo que cobre un proveedor (BSP) si se usa | Número dedicado; Meta no admite chatbots de IA de propósito general; los grupos existentes no se leen igual | [9][10][11] | Confirmado (estructura); tarifa por fuente secundaria |
| WhatsApp | Meta Business Agent (IA de Meta) | $2,00 por millón de tokens; ~$0,04-0,05 por mensaje; 1.000 mensajes ≈ $40-50 | Disponibilidad en Bolivia no confirmada | [9][12] | Confirmado precio; país no confirmado |
| WhatsApp | WAHA / Baileys / whatsapp-web.js (no oficial) | $0 (WAHA es gratis desde 2026.6.1; tier voluntario $5/mes sin ventajas) | **Baneo del número**: viola los términos de WhatsApp; sin garantía | [13][14][15] | Confirmado el riesgo; umbrales no publicados |
| WhatsApp | Coexistence (app Business + API en el mismo número) | Sin costo extra de Meta confirmado; tarifas de API aplican | No sincroniza grupos; se desactivan listas de difusión; requiere ser Solution Partner/Tech Provider; países no listados oficialmente | [16] | Confirmado limitaciones; países no confirmados |
| Redes | Meta Business Suite + TikTok Studio | $0 | TikTok Studio: sólo escritorio, ventana 10 o 30 días (fuentes en conflicto) | [17][18] | Probable |
| Redes | Metricool Free / Buffer Free | $0 (Metricool: 1 marca, 20 posts/mes; Buffer: 3 canales, 10 posts por canal) | Límites chicos | [19][20] | Confirmado (lectura de página oficial) |
| Redes | Buffer Essentials | $5 por canal/mes (3 canales = $15) | Cifras de la página no cuadran del todo | [20] | Confirmado con reserva |
| Redes | Metricool Starter (5 marcas) | $20-25/mes | No tiene API/Zapier (sólo Advanced, $53-67) | [19] | Confirmado con reserva |
| Videos | ffmpeg / plantillas propias | $0 | Tiempo de desarrollo; Remotion es gratis sólo hasta 3 personas | [21][22] | Confirmado |
| Videos | CapCut Pro | $17,99/mes o $149,99/año | Términos de uso comercial de plantillas/música no verificados | [23] | Confirmado precio |
| Videos | Veo 3.1 (API de Google), 30 videos de 15 s | Lite 720p ~$22,50 · Fast 720p ~$45 · Standard ~$180 | Costo crece con la duración; sin cuota gratis | [1] | Confirmado |
| Asistente | Claude Pro | $20/mes ($17 si es anual, $200 por adelantado) | Límites por ventana de 5 h y semanales, compartidos con claude.ai | [24][25] | Confirmado |
| Asistente | Claude Max | desde $100/mes | Igual, con más cupo (5x o 20x) | [24] | Confirmado |
| Asistente | Claude Code por API | Promedio empresarial ~$13 por día activo, $150-250 por mes | Gasto variable sin tope si no se limita | [26] | Confirmado (dato de Anthropic) |
| Asistente | Gemini CLI gratis | **Ya no existe**: dejó de atender cuentas gratis el 2026-06-18; lo reemplaza Antigravity CLI | Cuota gratis semanal, sin números oficiales | [27][28] | Probable |

---

## 1. Mejora de fotos con IA

### 1.1 Modelos de imagen de Google vía API (confirmado, [1])

La página oficial de precios del Gemini API (ai.google.dev/gemini-api/docs/pricing, consultada 2026-10-19) lista, en el nivel de pago, USD por imagen generada o editada:

| Modelo | Estándar (por imagen) | Batch (por imagen) | Cuota gratis |
|---|---|---|---|
| Gemini Nano Banana 2.1 | ~$0,0336 (1K), ~$0,0504 (2K), ~$0,113 (4K) | ~$0,0168 / $0,0252 / $0,0567 | No disponible |
| Gemini 3.1 Flash Image (Nano Banana 2) | ~$0,045 (0,5K), ~$0,067 (1K), ~$0,101 (2K), ~$0,151 (4K) | ~$0,022 / $0,034 / $0,050 / $0,076 | No disponible |
| Gemini 3.1 Flash Lite Image (Nano Banana 2 Lite) | ~$0,0336 (1K) | ~$0,0168 (1K) | No disponible |
| Gemini 3 Pro Image (Nano Banana Pro) | ~$0,134 (1K/2K), ~$0,24 (4K) | ~$0,067 / $0,12 | No disponible |
| Gemini 2.5 Flash Image (Nano Banana) | ~$0,039 | ~$0,0195 | No disponible. **Deprecado; fecha de cierre 2026-10-02** (ya pasó a la fecha de esta consulta) |

Notas:
- **Cuota gratis por API para modelos de imagen: no existe** según la propia página ("Not available" en todos los modelos de imagen).
- La página no muestra Imagen (el modelo anterior de Google).
- La página resumida no aclara si el costo de los tokens de la imagen de **entrada** (la foto original que se edita) se suma al precio por imagen de salida. **No confirmado**: revisar la columna de tokens de entrada en la misma página o probar con 10 fotos y mirar el consumo en AI Studio.
- El precio es el del nivel de pago; la herramienta de lectura resumió la página, así que revalidar números exactos en la fuente antes de presupuestar.

### 1.2 APIs de quitar fondo

| Servicio | Precio por imagen | Plan mínimo | Estado | Fuente |
|---|---|---|---|---|
| Photoroom Remove Background (plan Basic) | $0,02 | Probable: $20/mes por 1.000 imágenes (la página oficial sólo da el ejemplo "$20 = 1.000"); no hay rollover | Confirmado ($0,02); mínimo probable | [2][3] |
| Photoroom Image Editing (plan Plus) | $0,10 | Precio mensual del plan Plus no listado en la página | Confirmado ($0,10); plan no confirmado | [2] |
| Photoroom gratis | 1.000 llamadas sandbox/mes con marca de agua; 10 llamadas gratis de Remove Background sin marca | Sin tarjeta | Confirmado | [2] |
| remove.bg | 1 crédito por imagen (~$0,225 en el plan chico, hasta ~$0,0727 en el más grande) | Suscripción desde 40 créditos por $9/mes; pago único desde 3 créditos por $3 hasta 8.000 por $1.699 | Probable (la página oficial no cargó completa; cifras de un comparador de Photoroom) | [3][4] |
| remove.bg gratis | 50 llamadas API de vista previa por mes | | Confirmado en remove.bg/api | [4] |
| Clipdrop | Precio por API no publicado; se redirige a contacto de Jasper | | No confirmado | (búsqueda, ver [29]) |

Advertencias:
- **remove.bg**: un artículo de Photoroom (competidor, 2026-10-01) afirma que la API self-service de remove.bg deja de aceptar pedidos el **2026-12-01** (los contratos enterprise siguen). **Probable, no confirmado por remove.bg**: verificar en remove.bg antes de integrarlo.
- Los comparadores de terceros (toolradar, costbench, tekpon) se contradicen en los precios de remove.bg ($29 vs $39 por 200 créditos); se tomó como más confiable la tabla del artículo de Photoroom, que coincide con la cifra oficial de 40 créditos por $9.
- Leonardo.Ai aparece en ese mismo artículo con un precio plano de $0,1047 por imagen (probable).

### 1.3 Quitar fondo local (open source)

| Modelo | Licencia del código/pesos | ¿Uso comercial? | CPU / RAM observados | Fuente |
|---|---|---|---|---|
| rembg (la herramienta) | MIT | Sí | n/a | [5] |
| u2net | Apache-2.0 (repo U-2-Net) | Sí | Test en CPU: ~2,1 GB de RAM pico; 0,12 s por imagen | [6][7] |
| isnet-general-use | Apache-2.0 según el test | Sí | ~2,8 GB pico; 0,33 s por imagen | [7] |
| BiRefNet (general, general-lite) | MIT (modelo en Hugging Face) | Sí | En el test, el proceso se mató al superar ~6,6-6,9 GB y no terminó; trabaja siempre a 1024x1024 | [7][30] |
| BRIA RMBG-2.0 (`bria-rmbg`, default de rembg) | **CC BY-NC 4.0** | **No sin acuerdo comercial pago con BRIA** | Se mató a ~6,9 GB en el test | [5][31] |

Detalles y límites de la evidencia:
- Los números de CPU/RAM salen de **un solo test de un blog** (creativeainews.com, 2026) en una máquina **AMD Ryzen 7 9700X, 6 vCPU, 12 GB de RAM con ~6,9 GB libres**. **No se midió en un i5-7200U** (la PC del dueño es bastante más lenta) ni en el VPS de 15 GB. Esos tiempos son optimistas para el i5; no hay cifra confirmada para ese procesador.
- Con 15 GB de RAM en el VPS, BiRefNet no debería quedarse sin memoria como en el test (que tenía 6,9 GB libres), pero **no hay medición publicada**: no confirmado. Medirlo con 20 fotos reales.
- rembg avisa en su README que "los pesos de los modelos tienen su propia licencia, independiente de la MIT de rembg": revisar cada modelo antes de usarlo en producción. El default (`bria-rmbg`) es justamente el no comercial; hay que fijar el modelo (por ejemplo `u2net` o `isnet-general-use`) con `new_session()`.
- Quitar fondo no es "mejorar la foto" (luz, nitidez, escena): eso sí requiere un modelo generativo (sección 1.1).

### 1.4 Costo mensual estimado (USD)

Supuestos: 1 edición o 1 quitado de fondo por foto; 1K de resolución; sin reintentos.

| Opción | 300 fotos | 1.000 fotos | 3.000 fotos | Nota |
|---|---|---|---|---|
| Gemini Nano Banana 2.1 / Flash Lite Image (1K, estándar) | $10,08 | $33,60 | $100,80 | Batch a la mitad: $5,04 / $16,80 / $50,40 |
| Gemini 3.1 Flash Image (1K) | $20,10 | $67,00 | $201,00 | |
| Gemini 3 Pro Image (1K/2K) | $40,20 | $134,00 | $402,00 | |
| Photoroom Remove BG (Basic) | $20 (mínimo) | $20 | ~$60 | A $0,02 por imagen por encima del mínimo; el comparador calcula $56 para 2.800 |
| Photoroom Image Editing (Plus, $0,10) | $30 | $100 | $300 | Precio mensual del plan Plus no confirmado |
| remove.bg | ~$42-68 | ~$140-225 | ~$390 | Sólo orden de magnitud: no se conocen los escalones intermedios de plan |
| rembg local | $0 | $0 | $0 | Costo real: CPU/RAM propias y tiempo de proceso |

---

## 2. WhatsApp: atender automáticamente

### 2a. App WhatsApp Business (gratis)

- **Costo**: $0 (confirmado en el sitio oficial de WhatsApp Business, [8]).
- **Qué automatiza** (probable; no pude abrir la página oficial de ayuda de WhatsApp para estas funciones, el FAQ devolvió "contenido no disponible"; los datos vienen de guías de terceros, [8]):
  - Mensaje de bienvenida: se dispara con contactos nuevos y, según una fuente, tras 14 días sin actividad.
  - Mensaje de ausencia: fuera de horario.
  - Respuestas rápidas: hasta 50 (una fuente), atajos de hasta 25 caracteres.
  - Etiquetas: manuales; una fuente indica que no hay asignación automática y un tope de 20 etiquetas (una sola fuente, no verificado).
  - Catálogo: hasta 500 productos; sin checkout nativo.
- **Dispositivos vinculados**: 1 teléfono + hasta 4 dispositivos vinculados (guías de terceros; coincide con la documentación oficial de Meta para desarrolladores sobre coexistence, que menciona "hasta cuatro clientes vinculados"). Confirmado para el contexto coexistence [16]; probable para la app sola.
- **IA de Meta para negocios ("Business AI" / "Meta Business Agent")**: el sitio de WhatsApp Business la promociona [8] y Meta la lanzó el 2026-07-01 con cobro desde 2026-08-01 ([12]). Prensa de negocios indica despliegue gradual desde mayo-junio 2026, con México como primer mercado; las fuentes no coinciden en fechas ([32], probable). **Bolivia: no encontré ninguna fuente que confirme disponibilidad.** Buscar en: el menú "Herramientas" de la propia app Business en el número del comercio, o consultar a Meta/un BSP. La página oficial de precios de Meta no lista países para este producto.

### 2b. API oficial (WhatsApp Business Platform / Cloud API)

**Modelo de precios (confirmado, [9], documentación oficial de Meta)**:
- Cobro **por mensaje entregado** desde 2025-07-01, según categoría del mensaje y país del destinatario (código telefónico).
- Los mensajes del usuario hacia el negocio son gratis.
- Categorías: marketing, utility, authentication, service y **Meta Business Agent** (nueva, 2026-07-01).
- **Bolivia (+591) está en la región "Rest of Latin America"**.
- Tarifas vigentes desde **2026-10-01** (tarjetas publicadas en CSV/PDF en 16 monedas; USD disponible).

**Cambio importante de octubre de 2026 (confirmado, [9][33])**: los mensajes de **servicio** (respuestas dentro de la ventana de 24 h después de que el cliente escribió) eran gratis desde nov/2024 y los **utility dentro de la ventana** eran gratis desde jul/2025. **Desde 2026-10-01 ambos se cobran**, con estas reglas:
- Los primeros **1.000 mensajes de servicio por número de teléfono por mes** son gratis (no se acumulan).
- Desde el mensaje 1.001 se cobra al valor de la tarifa utility/authentication del mercado.
- Se debe tener método de pago cargado; sin él, Meta deja de entregar los mensajes de servicio una vez usada la cuota gratis (el plazo era 2026-09-30).
- **Siguen gratis**: ventana de entrada gratuita de hasta 7 días cuando el usuario escribe desde un anuncio Click-to-WhatsApp (Meta Business Agent sí se cobra igual).

**Tarifas para "Rest of Latin America", USD por mensaje entregado, vigentes 2026-10-01**:

| Categoría | Tarifa | Estado |
|---|---|---|
| Service (tras 1.000 gratis/mes/número) | $0,0113 | Probable: Zernio y 360dialog coinciden; ManyChat y Sleekflow también listan $0,0113 [10][33]. La CSV oficial de Meta no se pudo abrir |
| Utility | $0,0113 | Probable [10] |
| Authentication | $0,0113 | Probable [10] |
| Marketing | $0,0740 (Zernio) **o** $0,0851 (ManyChat) | **Conflicto entre fuentes**; ninguna es oficial. Verificar en business.whatsapp.com/products/platform-pricing (seleccionar Resto de Latinoamérica y USD) |
| Meta Business Agent | $2,00 por millón de tokens, tarifa global (≈ $0,04-0,05 por mensaje; consulta simple de 4 mensajes ≈ $0,16-0,20) | Confirmado [9][12] |

Ejemplo de cuenta (probable, aplicando la tarifa anterior): 3.000 respuestas de servicio en un mes con un solo número = (3.000 - 1.000) × $0,0113 = **$22,60**. Si un BSP (proveedor intermediario) se interpone, suma su propia comisión: **no relevada**.

**Requisitos (mezcla de oficial y secundario)**:
- Número propio, con código de país, capaz de recibir SMS o llamada; **no puede estar en uso en la app de WhatsApp** (hay que borrarlo antes, salvo coexistence) y, si está baneado, hay que apelar antes (documentación de números de Meta, [34], vía espejo; probable).
- Verificación en dos pasos con PIN de 6 dígitos obligatoria (probable, [34]).
- Verificación del negocio: la documentación oficial de límites dice que los portafolios nuevos arrancan en **250 usuarios únicos por 24 h** (mensajes iniciados por el negocio fuera de la ventana) y suben a 2.000 con verificación del negocio o con el historial de envíos; luego 10.000, 100.000 e ilimitado [35]. Las respuestas dentro de la ventana de 24 h no cuentan contra ese límite (interpretación; la página resumida no lo dice con esas palabras).
- Los guías de terceros dicen que se necesita un Meta Business Manager verificado para empezar; la documentación oficial leída **no lo exige explícitamente para empezar**: no confirmado [34].
- **Grupos**: la Groups API oficial exige ser Official Business Account (OBA), tiene un máximo de **8 participantes por grupo**, **no está disponible para números de la app WhatsApp Business**, y los grupos son sólo por invitación del negocio [36]. No encontré que el Cloud API pueda leer grupos de comerciantes que ya existen. **Esto es un límite duro frente al flujo actual de URUKU (grupos con comerciantes): no confirmado que se pueda replicar con la API oficial.**
- **Chatbots de IA**: desde 2026-01-15 los Términos de la Business Solution prohíben bots de IA de propósito general como oferta principal; un bot de atención de un comercio sigue permitido (prensa: TechCrunch, 9to5mac, [37]; probable, no abrí el texto de Meta).

### 2c. Automatización por WhatsApp Web (WAHA, whatsapp-web.js, Baileys)

**Costo**:
- **WAHA**: gratis. Desde la versión **2026.6.1** el proyecto eliminó los niveles Core/Plus/PRO; todo lo que era Plus está en la imagen gratis. Queda un tier voluntario "Community" de **$5/mes, sin ventajas** ([13], confirmado en el blog oficial). Hasta entonces, Plus costaba $19/mes y PRO $99/mes (dato histórico, probable).
- **Baileys**: MIT. **whatsapp-web.js**: Apache-2.0 ([14][15], confirmado).

**Términos de WhatsApp (confirmado, [38], Términos de Servicio leídos 2026-10-19)**:
- Los Términos **no nombran** a los clientes no oficiales, pero prohíben: ingeniería inversa o crear obras derivadas de los Servicios; construir software o APIs que funcionen esencialmente como los Servicios; acceder "directa o indirectamente, mediante medios automatizados" de forma no autorizada; y "enviar comunicaciones ilegales o no permitidas como **mensajería masiva, mensajería automática (auto-messaging), auto-marcado**"; y uso "no personal" salvo autorización.
- Consecuencia prevista: "deshabilitar o suspender tu cuenta".
- **Lectura**: un bot de WAHA es un cliente no oficial; los términos lo cubren por vía de las cláusulas de ingeniería inversa/acceso automatizado. Que un bot que **solo responde** a quien escribió esté dentro de "auto-messaging" es una interpretación, no una declaración de WhatsApp.

**Aviso del propio proyecto (confirmado, [13][15])**: WAHA y whatsapp-web.js dicen textualmente que "WhatsApp no permite bots ni clientes no oficiales" y que "no está garantizado que no te bloqueen". Baileys: "no condonamos el uso que viole los Términos; no hagas spam; desalentamos mensajería masiva o automatizada".

**Qué dispara baneos (evidencia, ninguna oficial de WhatsApp)**:

| Hecho | Fuente | Confianza |
|---|---|---|
| Números nuevos que escriben a muchos destinatarios distintos en poco tiempo se marcan, incluso sin API; algunos bloqueos ocurrieron tras ~10 mensajes a destinatarios distintos | Z-API, "Blocks and bans (2025)" [39] | Probable (proveedor, tests propios) |
| La **cantidad de destinatarios únicos** pesa más que el volumen total; el contenido (términos financieros), el historial del número reciclado y reusar nombre/foto de un número baneado también | [39] | Probable |
| Conectar un número nuevo, sólo por eso, a veces provocó baneo; rotar IP/ASN no redujo bloqueos | [39] | Probable |
| Caso reportado (2026-01-30): cuenta con Baileys que subió estados a 2.000-3.000 contactos en tandas de 100, desde un servidor: 2 bloqueos temporales y luego baneo permanente; sin respuesta de mantenedores; causa no confirmada (comentaristas sugieren patrón de envío e IP de datacenter) | Baileys issue #2309 [40] | Confirmado el reporte; causa no confirmada |
| Un reporte antiguo en Baileys dice que 10 números fueron baneados al publicar en grupos, y ninguno tras migrar a whatsapp-web.js (anécdota, sin comparación controlada) | Baileys issue #1925 (vía búsqueda) | Anecdótico |
| "No hay ninguna práctica 100 % efectiva para evitar bans" | [39] | Probable |

**¿Responder sólo a quien escribió primero baja el riesgo?** Un blog de un proveedor comercial (2026) afirma que sí, "sustancialmente"; los hallazgos de Z-API (el riesgo viene de muchos destinatarios nuevos) apuntan en la misma dirección. **No existe una declaración oficial de WhatsApp** que garantice que responder sea seguro, y los términos prohíben "auto-messaging". Estado: **probable que reduzca el riesgo, no confirmado, y no lo elimina**.

**Lo que no se encontró**: una tasa de baneo para el uso "sólo leer" (lo que URUKU hace hoy con WAHA: recibir fotos) ni umbrales numéricos de WhatsApp. Donde buscar: issues recientes de `devlikeapro/waha`, `pedroslopez/whatsapp-web.js` y `WhiskeySockets/Baileys`.

### 2d. Coexistence (mismo número en la app Business y en la API)

Confirmado en la documentación oficial de Meta ([16], "Onboard WhatsApp Business app users"):
- Requiere la **app WhatsApp Business versión 2.24.17 o superior**.
- El onboarding lo hace un **Solution Partner o Tech Provider mediante Embedded Signup** (con registro de sesión) y un webhook confiable. **No encontré que un negocio individual pueda hacerlo por su cuenta**: no confirmado.
- **Grupos: no se admiten ni se sincronizan.**
- **Listas de difusión: se desactivan** al hacer el onboarding (las existentes quedan de sólo lectura).
- Hasta **4 dispositivos vinculados**; el onboarding desvincula los compañeros y hay que volver a vincularlos; WhatsApp para Windows y WearOS no son compatibles.
- Si el teléfono principal está inactivo ~14 días, puede desconectarse (`PRIMARY_INACTIVITY`).
- Ventana de 24 h tras el onboarding para sincronizar contactos e historial.
- Rendimiento fijo de 20 mensajes por segundo en números con ambos usos.

**Países**: la documentación oficial leída no incluye lista de países. Un proveedor (Chakra, 2026) afirma que está disponible globalmente; otro proveedor listó antes Suiza, Australia y Japón como no disponibles. **Bolivia: no confirmado** (fuentes secundarias en conflicto). Buscar en: Meta for Developers (coexistence) o consultar a un BSP.

Costos: la app sigue gratis; la API se cobra según 2b (probable).

---

## 3. Manejo de redes (Facebook, Instagram, TikTok)

### 3.1 Programación gratis (probable, [17][18])

- **Meta Business Suite**: nativa y gratuita; programa publicaciones en Facebook e Instagram (hace falta conectar la cuenta de Instagram profesional). No pude abrir el centro de ayuda oficial; los detalles salen de guías de terceros (Buffer, RecurPost).
- **TikTok Studio**: programación gratuita **sólo en escritorio**, para cuentas Creator o Business. **Ventana en conflicto**: unas guías dicen hasta 30 días, otras (incluida Hootsuite) 10 días; el selector de fecha de la propia cuenta muestra el tope real. Una publicación programada no se edita (hay que borrarla y subirla de nuevo).

### 3.2 Herramientas pagas

| Herramienta | Plan gratis | Plan pago más barato | Qué incluye | Fuente |
|---|---|---|---|---|
| Metricool | 1 marca, 20 posts programados/mes, 5 competidores, 30 días de analítica; todas las redes menos LinkedIn y X | Starter, 5 marcas: $20-25/mes (EUR 16-20) según facturación anual o mensual (la página no lo rotula) | Programación "ilimitada" bajo política de uso justo | [19] |
| Metricool Advanced | | 15 marcas $53-67/mes | **Única con API/Zapier/Make** | [19] |
| Buffer | 3 canales, 10 posts programados por canal | Essentials **$5 por canal por mes** ($60 al año por canal) | La página dice 20 % de descuento anual y "ahorrá 2 meses": las cifras no concilian; confirmar en el checkout | [20] |

### 3.3 Publicación automática por API (límites)

| API | Límite / requisito | Estado | Fuente |
|---|---|---|---|
| Facebook Pages (Graph API) | Permiso `pages_manage_posts` otorgado por alguien que administre la Página; publicar con `POST /{page_id}/feed`; programar con `scheduled_publish_time` entre **10 minutos y 30 días** desde el pedido; fotos por `/{page_id}/photos`, video aparte (`publish_video`). La página no habla de revisión de app ni de límites de tasa | Confirmado | [41] |
| Instagram Content Publishing | Cuenta profesional; permisos `instagram_business_content_publish` (o `instagram_content_publish` por Facebook Login); acceso Standard o Advanced; medios en URL pública; imágenes sólo JPEG; carrusel de hasta 10 elementos que cuenta como 1 publicación; **tope de 100 publicaciones por API en 24 h móviles** (la misma página dice 50 en la sección de carruseles: **inconsistencia de la documentación**); consulta el uso con `GET /<IG_ID>/content_publishing_limit` | Confirmado, con la inconsistencia señalada | [42] |
| TikTok Content Posting API | Para Direct Post: scope `video.publish` aprobado. **Clientes sin auditar: todo contenido queda en modo privado (SELF_ONLY), máximo 5 usuarios en 24 h, cuentas privadas**. La auditoría exige que la app sirva a un público amplio; **"herramientas para subir a cuentas que maneja tu propio equipo no califican"**. Tope por creador ~15 posts/día (varía) compartido entre clientes. Exigencias de UX: elegir privacidad sin valor por defecto, consentimiento de música, vista previa, etc. | Confirmado | [43][44] |

Consecuencia directa de la fuente (no es opinión): publicar en TikTok automáticamente **en público** para cuentas propias o administradas por el equipo no cumple el criterio de auditoría descrito por TikTok. La guía "Upload" (borrador al buzón del usuario) existe pero no la pude leer: **no confirmado** si evita la auditoría. Buscar en: developers.tiktok.com/doc/content-posting-api-get-started-upload-content.

---

## 4. Generación de videos para redes

| Opción | Costo | Detalle | Fuente | Estado |
|---|---|---|---|---|
| ffmpeg + plantillas propias | $0 | Armar videos verticales a partir de fotos y texto; costo = tiempo de desarrollo y CPU del VPS/PC | n/a | La licencia de ffmpeg (LGPL/GPL según compilación) **no fue verificada aquí** |
| Remotion (videos con código React) | $0 si son hasta 3 personas (individuos u organizaciones con hasta 3 empleados); desde 4 personas: $25/mes por asiento, o "Automators" $0,01 por render con mínimo $100/mes | En la versión 5.0 la licencia "cambiará levemente" (sin detalle) | [22] | Probable (resultado de búsqueda sobre la página oficial) |
| CapCut | Gratis: plantillas y edición básica. **Pro: $17,99/mes o $149,99/año** (1.200 créditos de IA/mes, plantillas premium, 1 TB) | Términos de uso comercial de plantillas y música gratis: **no verificados** (la página enlaza el Acuerdo de Licencia y los Términos de Creadores sin transcribirlos) | [23] | Confirmado precio |
| Shotstack (API de renderizado) | Pago por uso ~$0,40 por minuto (mínimo $10 por 25 créditos); planes desde $39/mes (200 créditos = 200 minutos hasta 1080p, ~$0,20/min) | Cifras de guías de terceros | [45] | Probable |
| Creatomate | Plan Essential ~$54/mes por 2.000 créditos | Cifras en conflicto entre fuentes | [45] | Probable |
| Veo 3.1 (Google, con audio por defecto) | Lite 720p $0,05/s · 1080p $0,08/s; Fast 720p $0,10/s · 1080p $0,12/s · 4K $0,30/s; Standard 720p/1080p $0,40/s · 4K $0,60/s. Sólo se cobra si el video se genera con éxito. Sin cuota gratis | Pagina oficial de precios del Gemini API | [1] | Confirmado |
| Gemini Omni Flash | $1,50 por millón de tokens de entrada y $17,50 por millón de tokens de video de salida (≈ $0,10 por segundo en 720p según la página) | | [1] | Confirmado |
| Otros (Kling, Seedance, Runway, Luma) | Rango reportado: ~$0,03-0,75 por segundo; Kling 2.6 Pro ~$0,14/s (fal.ai), Seedance 2.0 ~$0,30/s (fal.ai), Veo 3.1 Fast ~$0,15/s (fal.ai) | Fuentes de afiliados/proveedores de abril-junio 2026; los números se contradicen | [46] | No confirmado |

**Estimación para 30 videos/mes** (USD):

| Opción | Duración por video | Cálculo | Total/mes |
|---|---|---|---|
| ffmpeg / plantillas propias | cualquiera | | **$0** |
| CapCut Pro | cualquiera | suscripción | $17,99 (o ~$12,50 si es anual) |
| Shotstack pago por uso | 15 s (7,5 min en total) | ~$0,40/min, mínimo de compra $10 | ~$3 (o el mínimo de $10) |
| Veo 3.1 Lite 720p | 8 s | 30 × 8 × $0,05 | $12,00 |
| Veo 3.1 Lite 720p | 15 s | 30 × 15 × $0,05 | $22,50 |
| Veo 3.1 Fast 720p | 8 s / 15 s | 30 × 8 × $0,10 / 30 × 15 × $0,10 | $24,00 / $45,00 |
| Veo 3.1 Standard 1080p | 8 s / 15 s | 30 × 8 × $0,40 / 30 × 15 × $0,40 | $96,00 / $180,00 |

Nota: la página de precios no dice la duración máxima de un clip de Veo; para videos largos podría hacer falta unir clips (no confirmado).

---

## 5. Asistente personal con Claude Code

### 5.1 Cómo se cobra (confirmado, docs oficiales)

- **Planes de claude.ai que incluyen Claude Code** ([24] claude.com/pricing, consultada 2026-10-19; "Claude Code is included in all paid plans"):
  - **Pro**: $20/mes facturado mensualmente, o $17/mes facturado por adelantado como $200 al año.
  - **Max**: desde $100/mes (la página no publica un precio aparte del nivel 20x; sólo dice "5x o 20x" más uso que Pro). Se factura mensual.
- **Límites** ([24][25]): ventana móvil de **5 horas** y **límites semanales**; todo el uso de web, escritorio, móvil y Claude Code **comparte el mismo cupo**. Pro ofrece al menos 5x más uso por sesión que Free; Max, 5x o 20x más que Pro. Anthropic puede aplicar topes adicionales. **No hay cifra publicada de mensajes por ventana** (el artículo de ayuda no da estimaciones de prompts por 5 horas).
- Al llegar al límite: esperar el reinicio, subir de plan, activar **usage credits** (se cobra a tarifas de API) o pasar a créditos de la Console.
- Si existe la variable de entorno `ANTHROPIC_API_KEY`, Claude Code **usa la API y cobra por token** en lugar de la suscripción ([25]).
- **Por API (Claude Console)**: Claude Code "cobra por consumo de tokens". Dato oficial de Anthropic: en despliegues empresariales el costo promedio es ~**$13 por desarrollador por día activo** y **$150-250 por desarrollador por mes**, con menos de $30 por día activo para el 90 % de los usuarios ([26]). Es un dato de desarrolladores de tiempo completo: **para uso ocasional "abrir la terminal y pedir tareas" no hay cifra oficial**.
- **Precios por millón de tokens, API, USD** ([47] platform.claude.com/docs/en/about-claude/pricing, 2026-10-19), entrada / salida:

| Modelo | Entrada | Salida |
|---|---|---|
| Claude Haiku 5.5 (prompts hasta 100.000 tokens) | $0,10 | $0,50 |
| Claude Sonnet 5.5 | $2 | $10 |
| Claude Opus 5.5 | $4 | $20 |
| Claude Opus 5 / 4.8 / 4.7 / 4.6 | $5 | $25 |
| Claude Fable 5.1 | $10 | $50 |

Lectura de aritmética (no opinión): con el promedio de $13/día activo, 20 días activos al mes ≈ $260/mes; con 10 días activos ≈ $130/mes. Esto supera al Pro ($20) y se acerca a Max ($100) solo si el uso real es intensivo; el consumo real depende del modelo, del tamaño del repo y de las sesiones largas ([26] enumera los factores que inflan el consumo).


### 5.2 Alternativa: Gemini como asistente de terminal

- **Gemini CLI** (Apache-2.0): el README oficial dice que **fue reemplazado por Antigravity CLI el 2026-06-18** para usuarios sin pago y de Google One ([27], confirmado). Prensa técnica: Gemini CLI deja de atender cuentas gratis, AI Pro y AI Ultra individuales el 2026-06-18; quienes tienen API keys de pago o licencias de Code Assist/Google Cloud conservan el acceso ([28], probable).
- **Cuota gratis anterior** (hasta el 2026-06-18): 60 solicitudes/minuto y 1.000/día con cuenta personal de Google ([28], probable). **Esa cuota gratis ya no aplica.**
- **Antigravity** (probable, fuentes secundarias de ~agosto 2026, ninguna es la página oficial de Google): nivel **Individual gratis ($0)** con Tab/Command ilimitados y una cuota semanal de agente (sin números publicados); Google AI Pro ~$19,99-20/mes; Ultra con 5x de cupo ~$100/mes; nivel superior ~$200/mes (antes $250). **No confirmado**: cantidad exacta de uso gratis. Buscar en la página oficial de Google AI plans / documentación de Antigravity.
- **Gemini API con clave de AI Studio**: la propia documentación indica que los límites se miden por proyecto en solicitudes por minuto, tokens por minuto y solicitudes por día, y varían por modelo; **no pude confirmar cifras gratuitas vigentes para Flash** (fuentes de terceros se contradicen: 250, 1.500 o ~20 por día). Los prompts del nivel gratis pueden usarse para mejorar productos de Google, y en EEE/Suiza/Reino Unido hay que usar el nivel pago. Revisar la cuota real del proyecto en la consola de AI Studio.

---

## Lo que no pude confirmar (y dónde buscar)

1. **Tarifa oficial de marketing para "Rest of Latin America"** (conflicto $0,0740 vs $0,0851) y la CSV oficial de Meta: business.whatsapp.com/products/platform-pricing (Resto de Latinoamérica, USD).
2. **Disponibilidad en Bolivia de Meta Business Agent / Business AI** y de **coexistence**: Meta for Developers, o consulta a un BSP.
3. **Si el Cloud API puede recibir mensajes de grupos existentes de comerciantes**: documentación Groups messaging reference de Meta.
4. **Comisión de un BSP** sobre las tarifas de Meta, y si un negocio individual puede hacer el onboarding de coexistence sin ser Tech Provider.
5. **Umbrales de baneo de WhatsApp** y tasa de baneo del uso "sólo leer"/"sólo responder": no son públicos. Issues de WAHA, Baileys y whatsapp-web.js.
6. **Precio de Clipdrop API** (no publicado), **escalones intermedios de remove.bg**, **plan mensual Photoroom Plus**, y si la API self-service de remove.bg cierra el 2026-12-01 (sólo lo dice un competidor).
7. **CPU/RAM de rembg y BiRefNet en el i5-7200U de 8 GB y en el VPS de 15 GB**: no existe medición publicada; medir con fotos reales.
8. **Si el costo de la imagen de entrada se suma** al precio por imagen de Gemini.
9. **Terminos de uso comercial de plantillas y música gratis de CapCut**, y licencia de ffmpeg para el tipo de uso de URUKU.
10. **Si el flujo "Upload" (borrador) de TikTok evita la auditoría**.
11. **Cuota gratis exacta de Antigravity y del Gemini API (Flash)**: página oficial de Google.
12. **Ventana de programación de TikTok Studio** (10 vs 30 días) y límites oficiales de Meta Business Suite: abrir la herramienta con la cuenta real.
13. **Tipo de cambio de octubre 2026** (el último dato es de agosto): bcb.gob.bo/tiposDeCambioHistorico.
14. **Conteo de publicaciones de Instagram por API**: la documentación dice 100 y 50 en dos secciones.

---

## Fuentes (todas consultadas el 2026-10-19)

1. Gemini API, precios: https://ai.google.dev/gemini-api/docs/pricing (oficial; lectura resumida)
2. Photoroom API, precios: https://www.photoroom.com/api/pricing (oficial)
3. Photoroom, comparación con remove.bg (2026-10-01, competidor): https://www.photoroom.com/blog/remove-bg-api-cost-leonardo-ai-vs-photoroom
4. remove.bg API (50 llamadas gratis, límites): https://www.remove.bg/api ; página de precios (cargó incompleta): https://www.remove.bg/pricing
5. rembg (README, licencias): https://github.com/danielgatis/rembg
6. U-2-Net (Apache-2.0): https://github.com/xuebinqin/U-2-Net
7. Test de rembg en CPU (creativeainews, 2026): https://www.creativeainews.com/articles/rembg-background-removal-models-tested-2026/
8. WhatsApp Business (sitio oficial): https://whatsappbusiness.com/products/business-app/ ; guías de terceros de funciones: https://www.qiscus.com/en/blog/whatsapp-business-features/ , https://chatdaddy.tech/blog/whatsapp-business-features
9. Meta, precios de WhatsApp Business Platform (oficial): https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing.md
10. Zernio, tarifas octubre 2026 (secundaria): https://zernio.com/whatsapp-api-pricing
11. Meta, mensajes no plantilla (servicio y Business Agent): https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/non-template-messages.md
12. Meta, mismo documento [11] para tokens de Meta Business Agent.
13. WAHA, blog 2026.6 y docs: https://waha.devlike.pro/blog/waha-2026-6/ , https://waha.devlike.pro/docs/overview/introduction
14. Baileys: https://github.com/WhiskeySockets/Baileys
15. whatsapp-web.js: https://github.com/pedroslopez/whatsapp-web.js
16. Meta, coexistence (oficial): https://developers.facebook.com/documentation/business-messaging/whatsapp/embedded-signup/onboarding-business-app-users
17. Buffer sobre Meta Business Suite (secundaria): https://buffer.com/resources/how-to-use-meta-business-suite/
18. TikTok Studio, programación (secundarias): https://socialbu.com/blog/how-to-schedule-tiktok-posts , https://www.hopperhq.com/blog/how-to-schedule-tiktok-posts-desktop-mobile/
19. Metricool, precios: https://metricool.com/pricing/
20. Buffer, precios: https://buffer.com/pricing
21. FFmpeg — License and Legal Considerations (LGPL 2.1+, GPL si se compila con componentes GPL; uso comercial permitido): https://ffmpeg.org/legal.html
22. Remotion, licencia y precios: https://www.remotion.dev/docs/license/pricing , https://github.com/remotion-dev/remotion/blob/main/LICENSE.md
23. CapCut, precios: https://www.capcut.com/pricing
24. Claude, precios: https://claude.com/pricing
25. Claude Code con Pro/Max: https://support.claude.com/en/articles/11145838-using-claude-code-with-your-pro-or-max-plan
26. Claude Code, costos: https://code.claude.com/docs/en/costs
27. Gemini CLI (README): https://github.com/google-gemini/gemini-cli
28. Cobertura de la sustitución por Antigravity: https://thenewstack.io/gemini-cli-antigravity-replacement/ , https://letsdatascience.com/news/google-replaces-gemini-cli-with-antigravity-cli-574b2056
29. Clipdrop, precios (agregadores, no oficial): https://costbench.com/software/ai-media-apis/clipdrop-api/
30. BiRefNet (Hugging Face, MIT): https://huggingface.co/ZhengPeng7/BiRefNet
31. BRIA RMBG-2.0 (CC BY-NC 4.0): https://huggingface.co/briaai/RMBG-2.0
32. Business AI en México/Brasil (prensa): https://www.xataka.com.mx/aplicaciones/asistentes-ia-llegan-a-whatsapp-business-mexico-asi-nueva-herramienta-pymes-automaticen-sus-ventas/amp , https://ecosistemastartup.com/meta-lleva-su-agente-de-ia-a-whatsapp-business-en-mexico/
33. 360dialog, cobro de mensajes de servicio desde 2026-10-01: https://360dialog.com/blog/whatsapp-service-message-charging-october-2026/
34. Meta, números de teléfono (espejo): https://support.chatarchitect.com/books/meta-whatsapp/page/business-phone-numbers-developer-documentation
35. Meta, límites de mensajería: https://developers.facebook.com/documentation/business-messaging/whatsapp/messaging-limits.md
36. Meta, Groups API: https://developers.facebook.com/documentation/business-messaging/whatsapp/groups
37. Prohibición de chatbots de IA de propósito general (2026-01-15): https://techcrunch.com/2025/10/18/whatssapp-changes-its-terms-to-bar-general-purpose-chatbots-from-its-platform/ , https://9to5mac.com/2025/10/20/whatsapp-bans-ai-chatbots-from-using-its-business-api/ ; precios para AI Providers: https://developers.facebook.com/documentation/business-messaging/whatsapp/pricing/ai-providers.md
38. Términos de Servicio de WhatsApp: https://www.whatsapp.com/legal/terms-of-service
39. Z-API, "Blocks and bans (2025)": https://v2.developer.z-api.io/en/tips/blockednumbernew
40. Baileys issue #2309: https://github.com/WhiskeySockets/Baileys/issues/2309 ; #1925: https://github.com/WhiskeySockets/Baileys/issues/1925
41. Meta, publicar en Páginas: https://developers.facebook.com/docs/pages-api/posts
42. Meta, Instagram Content Publishing: https://developers.facebook.com/docs/instagram-platform/content-publishing/
43. TikTok, Content Posting API (inicio): https://developers.tiktok.com/doc/content-posting-api-get-started
44. TikTok, guías de uso y auditoría: https://developers.tiktok.com/doc/content-sharing-guidelines
45. Shotstack / Creatomate (comparadores): https://www.wireflow.ai/blog/shotstack-pricing , https://www.wireflow.ai/blog/creatomate-vs-shotstack
46. APIs de video (comparadores, abril-junio 2026): https://fal.ai/learn/tools/best-image-to-video-apis-2026 , https://techsy.io/en/blog/best-ai-video-providers
47. Anthropic, precios de la API: https://platform.claude.com/docs/en/about-claude/pricing
48. Antigravity, planes (secundarias): https://www.cloudzero.com/blog/google-antigravity-pricing/ , https://techcabal.com/2026/06/05/google-ai-subscription-plans-explained/
49. Tipo de cambio Bolivia (agosto 2026): https://correodelsur.com/economia/20260815/dolar-paralelo-registra-volatilidad-y-cierra-en-bs-11-43-mientras-el-oficial-baja-a-bs-11-58.html
