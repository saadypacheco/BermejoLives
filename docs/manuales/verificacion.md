# Verificación de los manuales contra el código

Cada afirmación funcional de los manuales (`frontend/content/manuales/*.md`), con
el `archivo:línea` del código que la respalda. Relevado el 15/10/2026 sobre
`main` (6a4c002) más los cambios de esta tanda. Lo que no tuvo respaldo se sacó
del manual (lista al final).

Rutas relativas a la raíz del repo. Abreviaturas:

| Abrev. | Archivo |
|---|---|
| **P** | `frontend/app/admin/page.tsx` |
| **S** | `frontend/components/admin/secciones.ts` |
| **SH** | `frontend/components/admin/admin-shell.tsx` |
| **D** | `frontend/components/admin/dashboard.tsx` |
| **AC** | `frontend/components/admin-ciudad.tsx` |
| **M** | `backend/app/api/moderacion.py` |
| **R** | `backend/app/db/repository.py` |
| **PE** | `backend/app/core/permisos.py` |
| **MC** | `frontend/app/mi-comercio/page.tsx` |
| **IC** | `frontend/components/ingresar-comercio.tsx` |
| **AR** | `frontend/app/autoregistro/page.tsx` |
| **API** | `backend/app/api/comercio.py` |
| **ING** | `backend/app/services/ingest.py` |
| **GU** | `frontend/components/galeria-uploader.tsx` |
| **PUB** | `frontend/app/publicar/page.tsx` |
| **QA** | `frontend/components/que-hay-aca.tsx` |
| **FA** | `frontend/components/ficha-agente.tsx` |
| **CC** | `frontend/components/completar-comercio.tsx` |
| **CAM** | `backend/app/api/campo.py` |
| **FICHA** | `frontend/app/comercios/[slug]/page.tsx` |
| **BC** | `frontend/components/buscar-client.tsx` |
| **HOME** | `frontend/app/page.tsx` |

Las líneas son exactas o el rango que contiene el texto (se comprobó una muestra
al azar de 20 referencias: todas dentro del rango, ±2 líneas).

---

## Páginas de manuales (cambio de esta tanda)

| Afirmación | Respaldo |
|---|---|
| `/manual/comprador` existe y se genera en el build | `frontend/lib/manuales.ts:12,24`; `frontend/app/manual/[tipo]/page.tsx:22-24` |
| `/manual/*` es público, también en modo captura (no pide login) | `frontend/middleware.ts:5`; `frontend/app/manual/[tipo]/page.tsx` (sin sesión) |
| Las capturas `![…](/manuales/…)` se dibujan; sólo archivos propios de `public/manuales/` | `frontend/lib/manual-md.ts:154-162,275-276`; `frontend/components/manual/manual-vista.tsx:81` |
| Una captura que todavía no existe no se muestra (servidor) | `frontend/components/manual/manual-servidor.tsx:27,35-52` |
| …y si falla en el navegador se esconde en vez de mostrar el ícono roto | `frontend/components/manual/manual-imagen.tsx:14,20,30` |
| Admin › Manuales ofrece el del comprador con «Abrir» y «Copiar enlace» | `frontend/components/admin/manuales-panel.tsx:89-90,118-120` |
| Mi perfil tiene «Cómo se usa URUKU» → `/manual/comprador` | `frontend/app/perfil/page.tsx:76-77` |
| El PDF del comprador lleva su pie «URUKU · Manual del comprador» | `frontend/app/styles/manual.css:196-201` |

---

## Manual del administrador (`admin.md`)

### Entrar y moverse

| Afirmación | Respaldo |
|---|---|
| Ingreso con «tunombre@uruku.bo», «Contraseña», «Entrar»; «Credenciales incorrectas» | P:477-480, P:422 |
| El menú esconde las secciones sin permiso | SH:82-84 |
| Números en el menú (Negocios, Publicaciones, Reclamos, Recepción, Cambios de número, Pagos, Suscripciones, Vencimientos en rosa) | SH:26-36 |
| Barra de arriba: ciudad, «Ver sitio», «Salir» | AC:163; SH:172,176 |
| Cada sección tiene su dirección `?s=` | S:91-93; P:342 |
| «No tenés permiso para entrar a esta sección.» + «Ir al Inicio» | P:489-499 |
| La ciudad se recuerda; leyendas «no depende de la ciudad» / «todavía muestra todas» | AC:25, AC:135-137 |
| Son 27 secciones en 8 grupos | S:12-19, S:37-83 |

### Inicio

| Afirmación | Respaldo |
|---|---|
| Sin permiso propio, filtra por ciudad | S:39; P:173 |
| «Actualizado a las…», «Actualizar» | D:98-105 |
| Filas de «Para hacer hoy» y sus botones | D:57-76 |
| Sólo las filas que se pueden abrir; «de todas las ciudades»; «Todo al día» | D:157, D:206, D:175-176 |
| Tarjetas (Comercios, Verificados «Verificar (N)», Con horario «Cargar horarios (N)», WhatsApp, Visitas, Contactos) | D:238-249 |
| Gráficos (Altas por día, Visitas y contactos, Fichas completas, Comercios por ciudad siempre todas) | D:296-321, D:398-401 |

### Negocios

| Afirmación | Respaldo |
|---|---|
| Permiso `moderar`, filtra | S:42; M:264-269 |
| «Resumen por ciudad» y sus columnas | P:1780-1822 |
| «Activos» / «Dados de baja» con `comercios.editar` | P:1953-1955 |
| Buscador por nombre, código, productos, dirección, teléfono, rubro, ciudad (todas las palabras) | P:1896-1904, P:1977 |
| Orden «Más recientes», «A → Z», «Pendientes primero»; «Lista»/«Mapa»; atajo Calles | P:1986-1988, P:1996, P:2003 |
| Filtros Todos/Pendientes/Verificados/Incompletos/Sin horario | P:1920-1929 |
| Qué es «Incompleto» (incluye sin productos y rubro «otros»; servicios sólo nombre y foto) | P:1655-1679 |
| En el mapa tocar un pin abre el editor | P:2037 |
| Contenido de la fila (chip verificado/pendiente/suspendido, código, rubros…) | P:2053-2091 |
| Íconos WhatsApp, Ver en mapa, Volante, Tarjeta de mesa, Recalcular el rubro, Editar, Verificar, Dar de baja | P:2135-2185 |
| «Clasificar por fotos»: «Analizar N pendientes» / «Detener» | P:2977-2992; M:1891-1909 |
| Verificar: sin confirmación, no se deshace | P:384-396; M:288-291 (no hay endpoint inverso) |
| Editor: «Editar negocio», «X de Y», «←» «→» sin guardar, Escape | P:2581-2601, P:2430-2437 |
| Foto principal: «Subir otra» reemplaza sin guardar la anterior; recorte «Más arriba/abajo» | P:2617-2624; `frontend/components/foto-principal.tsx:77-111` |
| Nombre y «No tiene cartel ni nombre propio» | P:2638-2662 |
| «Código para publicar por WhatsApp» con «Copiar» | P:2669-2676 |
| WhatsApp sólo con `comercios.cuenta` | P:2680-2686 |
| Productos observados / Detectado por IA / Descripción | P:2692-2705 |
| Categorías y principal; Modalidad; Dirección | P:2724-2780 |
| Horario: atajos, «Limpiar», «Igual que el anterior», «Ahora mismo»/«No se entiende» | P:2790; `frontend/components/editor-horario.tsx:40-93` |
| Redes y contacto | P:2798-2804 |
| Galería: «+ Agregar fotos», «Borrar foto» con confirmación, «Usar como portada» intercambia | P:3247-3325; P:3255 |
| Tope: «Llegaste al tope de fotos», «Borrar esa y subir la nueva», sin pago desde el panel | P:3328 (`puedePagarExtra={false}`); `frontend/components/tope-fotos-dialogo.tsx:264-315` |
| Lo que suma: tildes, pedido mínimo texto libre, canal (enlace), catálogo PDF o enlace | P:2812-2851; `frontend/components/tildes-suma.tsx:16-23`; `frontend/components/catalogo-pdf.tsx:98-102` |
| Clasificar desde las fotos (IA): Analizar, confianza, Aplicar/Descartar | P:2858-3160; M:1814-1818 |
| Generar clave nueva (con `comercios.cuenta`), confirmación, «Clave nueva de …», `NOMBRE-XXXXXX`, «Copiar», «Listo», cierra la sesión del dueño | P:2712; `frontend/components/admin/generar-clave.tsx:91-115`; `backend/app/core/clave_comercio.py:45-47,127`; M:1184-1215 |
| Pie: «Cancelar», «Guardar cambios», «Guardar y siguiente →» | P:2870-2877; M:400-404 |
| Sólo lectura: texto exacto y «Cerrar» | P:2409, P:2605-2610, P:2882 |
| Dar de baja: confirmación, sin motivo, «Dado de baja por el admin» | P:2176-2185; R:2051-2052; M:301-304 |
| Dados de baja: lista, «Reactivar» con confirmación; vencidos se reactivan al pagar | P:2266-2306; M:315-340, M:327-328 |
| Confiable, Suspender y grupos/números están en Suscripciones | P:1575-1593 |

### Calles y horarios

| Afirmación | Respaldo |
|---|---|
| Permiso `moderar`; lote pide `comercios.editar`; traer calles pide `lugares` | S:43; M:514-517; `backend/app/api/calles.py:45-48` |
| Pestañas «Horarios» y «Mapa» | `frontend/components/admin-calles.tsx:60` |
| La calle sale del GPS; filas con comercios y sin horario | `admin-calles.tsx:111-164` |
| Rubros que vienen destildados | `admin-calles.tsx:183` |
| 4 atajos y la regla de «y» | `admin-calles.tsx:29-36, 256-258` |
| Tildes «Sólo a los que no tienen horario» y «Marcarlo como estimado» | `admin-calles.tsx:188-189, 265, 275` |
| «Poner el horario a N comercios», sin confirmación | `admin-calles.tsx:203, 287` |
| Mapa: elegir ciudad; «X de Y km recorridos»; «Zonas»/«Calles»; arranca en Zonas | `admin-calles.tsx:76`; `frontend/components/admin-calles-mapa.tsx:39, 144-158` |
| Zonas: cuatro cuadras, más verde = más recorrido, tocar acerca | `admin-calles-mapa.tsx:170, 245-248` |
| Leyenda y colores | `frontend/components/calle-panel.tsx:39-56`; `frontend/lib/calles.ts:59-75` |
| Umbrales 60 % / 15 %; la marca manual gana | `backend/app/services/calles_mapa.py:14-20, 120-130` |
| Ficha de la calle: Cobertura, Comercios, Último paso, Marca, Nota, 3 botones | `calle-panel.tsx:62-64, 106-169` |
| «Traer calles de OpenStreetMap» | `admin-calles-mapa.tsx:113-123` |

### Lugares, Importados, Adornos, Cambios de número

| Afirmación | Respaldo |
|---|---|
| Lugares: permiso `lugares`, elegir ciudad | S:44; M:716-771; `frontend/components/lugares-editor.tsx:30` |
| Tipos Mercado/Galería/Paseo/Shopping/Referencia; tocar el mapa; Agregar/Guardar/Nuevo/Borrar | `lugares-editor.tsx:19, 163, 173-191` |
| Manzana: Dibujar, ≥3 esquinas, Deshacer, Guardar, Cancelar, Borrar | `lugares-editor.tsx:136, 189, 199-207` |
| Importados: menú `datos`, backend `panel`; de OpenStreetMap | S:45; M:1339-1415; `frontend/components/importados-panel.tsx:103-106` |
| Filtros, buscador, «Ocultar N que parecen ya estar cargados» | `importados-panel.tsx:29-33, 43, 115-139, 197` |
| «Al mapa» sin confirmación (activo, sin verificar); «Descartar» pide motivo | `importados-panel.tsx:181, 227-236`; M:1381-1391 |
| Adornos: chalanas, lapachos y banderas; menú `lugares`, guardar `panel` | S:46; M:2010-2069; `frontend/components/adornos-editor.tsx:31` |
| Tocar el mapa crea; arrastrar mueve; Tamaño, Cuál, Giro, Borrar sin confirmación; debajo de los pines | `adornos-editor.tsx:83-131, 207-275` |
| Cambios de número: permiso `panel`, todas las ciudades, nunca se aprueba solo | S:47; M:1113-1151; P:969-970 |
| Pedido: número actual → nuevo, «Ver ubicación enviada», «Foto registrada»/«Foto nueva» | P:980-1002 |
| «Aprobar» cambia el número y anula las claves; «Rechazar»; sin confirmación | P:1008-1009; M:1129-1141 |

### Publicaciones, Recepción, Difusión, Reclamos

| Afirmación | Respaldo |
|---|---|
| Publicaciones: permiso `moderar`; pestañas «Pendientes (N)» y «Publicadas» | S:50; P:613 |
| Sólo los no confiables pasan por la cola | `backend/app/services/ingest.py:628-683`; API:879-901 |
| Tarjeta: foto, comercio, tipo, texto, precio, TikTok, fecha; identificación | P:645-652, P:848-867 |
| Orden: lo dudoso arriba | M:135-141 |
| Selector de tipo aplicado con cualquier botón | P:428, P:680-687; M:196-197 |
| «Revisar con IA» sólo sugiere | P:438-447, P:665-671; M:251-253 |
| Aprobar → difusión: canal siempre, FB/IG si el plan tiene redes | M:225; `backend/app/services/difusion.py:230-243` |
| Solicitar cambios / Rechazar: motivo opcional; el comercio ve «Pide cambios»/«Rechazada», no el motivo | P:427; M:226-229; MC:378-379 |
| «Revisar todas con IA» ≥ 80 %, sin confirmación | P:451-462, P:633 |
| «Leer las fotos de las ofertas» / «Analizar» (`panel`) | P:3978-4059; M:2444 |
| Publicadas: buscador, «Bajar», motivo obligatorio, queda «Rechazada» | P:705-839, P:753-756, P:812-822 |
| Máximo de guardadas: se archiva la más vieja | `backend/app/services/planes.py:233-244`; `frontend/components/planes-panel.tsx:89` |
| Recepción: menú `whatsapp`, bandeja pide `moderar` | S:51; M:2523 |
| Estado del canal | `frontend/components/bandeja-whatsapp.tsx:415-427` |
| Buscador, filtros «Para mirar»/«Publicadas»/«Ignoradas»/«Últimas 150», vista | `bandeja-whatsapp.tsx:382-383, 443-469`; R:684-689 |
| Resultados (Publicada… Sin registrar) | `bandeja-whatsapp.tsx:8-15` |
| «Reprocesar» | `bandeja-whatsapp.tsx:243-251`; M:3247-3248 |
| Plan B y «Mandar un mensaje de prueba» | `bandeja-whatsapp.tsx:154, 192, 492-494` |
| No se asigna un mensaje a un comercio; se ata en Suscripciones | (no hay endpoint: M sólo `asignar_plan_comercio` :995); P:3588, P:3620 |
| Difusión: menú `difusion`, ver `moderar`; destinos; filtros; estados; «Publicar»; «Publicar 10 que esperan» | S:52; M:3000-3059; `frontend/components/difusion-panel.tsx:13-18, 67-171` |
| Reclamos: `panel`; dos tarjetas; «Responder» guarda sin avisar (URUKU) y va a Reservalo (tienda) | S:53; P:882-955; R:2989-3001; M:905 |
| Los reclamos vienen de «¿Hay algún dato incorrecto?» › «Informar un problema» | FICHA:416-422 |

### Catálogo, Rubros, Revisar rubros

| Afirmación | Respaldo |
|---|---|
| Catálogo: menú `datos`, backend `moderar`; resumen, «Lo buscaron…», Rubros, «Ver sólo los vacíos», Subcategorías, Productos | S:56; M:2081; `frontend/components/catalogo-panel.tsx:38-121` |
| Rubros: `rubros`, global; «Categorías que la IA pidió…», «Resolver» | S:57; `frontend/components/rubros-panel.tsx:75-100` |
| «Es un rubro nuevo» / «Es otra forma de decir…», palabras, vista previa | `rubros-panel.tsx:189-358` |
| «Completar rubros»: Analizar / Aplicar sólo suma | `rubros-panel.tsx:46-50, 118-147` |
| Los rubros no se renombran ni se borran | (no hay PUT/PATCH/DELETE de `/admin/rubros` en `backend/app/api/*.py`) |
| Revisar rubros: menú `rubros`, cola `moderar`; pestañas; revisados | S:58; M:2760; `frontend/components/revision-rubros.tsx:155-181` |
| Fila: «Está en X · el diccionario dice Y», «Está bien», «→ rubro», «Editar los rubros» | `revision-rubros.tsx:311-359` |
| «Recalcular en tanda»: Ver qué cambiaría (2 modos), Aplicar/Reemplazar con confirmación | `revision-rubros.tsx:123-142, 195-238` |
| Editor «Rubros de …»: Va a quedar así, Por sus palabras, La IA propone, Todos, palabra, Guardar / Ya estaba bien | `frontend/components/rubro-recalcular.tsx:151-302`; M:2830 |

### Cargas

| Afirmación | Respaldo |
|---|---|
| Permiso `equipo`, filtra; «Cargas del día» | S:61; M:1538, M:1569; `frontend/components/cargas-panel.tsx:321-323` |
| Historial 60 días y columnas; tocar una fila | `cargas-panel.tsx:339-358` |
| El día: Fecha, «Hoy», Agente | `cargas-panel.tsx:390-407` |
| Resumen, recorrido en línea recta, tramos por pausa > 30 min | `cargas-panel.tsx:444-456`; `backend/app/services/cargas.py:21-22` |
| «Comercios por hora», «El recorrido», «Uno por uno», «subido más tarde (sin señal)» | `cargas-panel.tsx:103-109, 464-513` |
| Antes del 6/10/2026 la hora es la del servidor | `cargas-panel.tsx:330-333` |

### Planes, Suscripciones, Pagos, Vencimientos

| Afirmación | Respaldo |
|---|---|
| Planes: menú `planes`, lista `moderar` o `pagos`; funciones no editables; ocultos atenuados | S:64; M:3087-3103; `planes-panel.tsx:19-22, 74-77` |
| Campos, casillas y «Guardar»; fotos 0-1000 | `planes-panel.tsx:45-48, 80-108`; M:3082 |
| Nota: guardadas, tope de fotos, plan gratis si vence | `planes-panel.tsx:89-92`; `backend/app/services/fotos_galeria.py:78-92` |
| Suscripciones: `pagos`, filtra; buscador; filtros | S:65; M:805-822; P:1485-1517 |
| Estados y regla «Por vencer» ≤ 5 días | R:2442, R:2460-2475; P:1025-1034 |
| «Interesado: plan · agente · fecha» | P:1556-1564; M:813-821; R:2809-2815; CAM:642-659 |
| Botones Enviar mensaje / Confiable (`comercios.cuenta`), Plan, + Pago, Suspender/Reactivar sin confirmación | P:1466, P:1568-1593, P:399-409 |
| Suspendido sale de la búsqueda y pierde la estrella; Reactivar no deshace una baja del admin | `supabase/migrations/0143_estrella_y_cortesia.sql:76-80, 211`; R:2521-2537; M:1038-1039 |
| El mensaje llega a la bandeja de Mi comercio | M:1093-1108; MC:1109-1143 |
| Plan y cortesía: modal, confirmaciones, sólo sobre plan pago, «Guardar plan» | P:3636-3709; M:994-1017 |
| Cortesía: estrella, sin cobros ni vencimientos | P:3687-3691; R:2565 |
| Registrar pago: campos, «Confirmar pago», extiende, quita suspensión, crea la cuenta, avisos | P:3711-3817; R:2479-2518; M:955-977 |
| Confiable y números: código, confiable, rubros, grupo (crear / a mano / Atar / Soltar), números | P:3340-3631; M:1166-1170, M:1226-1311 |
| Pagos: `pagos`; «Pagos por confirmar»; miniatura; «Plan (opcional)»; Confirmar 1/2 meses sin confirmación | S:66; P:1059-1097; M:1053-1085 |
| Confirmar extiende, quita suspensión, plan saca cortesía | R:2616-2656 |
| Vencimientos: menú `moderar`, escribir `pagos`; tipos; avisar días; estados; Editar / Dejar de vigilar; HTTPS | S:67; M:2164-2233; `frontend/components/vencimientos-panel.tsx:23-211`; `backend/app/services/vencimientos.py:43-77` |

### Monitoreo, KPIs, Demanda, Compradores

| Afirmación | Respaldo |
|---|---|
| Monitoreo: `datos`; Visitas al sitio 7/30/90 | S:70; M:825-831; `frontend/components/panel-visitas.tsx:35-100` |
| Altas por día (60 días), tarjetas, No contestan, Peso de las fotos, más ofertas / contactados, Reservalo | P:1229-1437, P:3848-3943; M:1509-1512, M:2099-2129 |
| KPIs: `datos`; períodos; tarjetas; listas | S:71; M:834-842; P:1110-1186; R:3688-3708 |
| Demanda: menú `datos`, backend `moderar`; 7/30/90; «Para decirle a un comerciante»; listas | S:72; M:3165-3168; `frontend/components/demanda-panel.tsx:80-127` |
| Compradores: `datos`, global; importar Excel/CSV; columnas; vista previa; resumen; enlace por grupo | S:73; M:669-690; `frontend/components/contactos-panel.tsx:111-220` |

### Equipo, Manuales, Ayuda

| Afirmación | Respaldo |
|---|---|
| Equipo: `equipo`; pestañas «Personas» y «Roles y permisos» | S:76; M:563-646; `frontend/components/equipo-panel.tsx:32-33` |
| Agregar a alguien: campos, ciudad sólo agentes, «Crear», «Copiar para mandar por WhatsApp» | `equipo-panel.tsx:58-112`; M:582-591 |
| Tabla; roles y ciudad al instante; clave nueva; Apagar/Encender; no se borra ni se edita nombre/correo | `equipo-panel.tsx:119-184`; R:1192 |
| Roles del sistema y sus permisos | PE:55-76 |
| Agente no entra al panel | PE:112-119 |
| Crear rol, tildes al instante, Borrar sólo los nuevos | `equipo-panel.tsx:203-251`; M:648-649 |
| Catálogo de permisos con su texto | PE:20-42 |
| Manuales: sin permiso; agentes con `equipo`; genérica; tarjetas fijas con Abrir/Copiar enlace | S:79; `frontend/components/admin/manuales-panel.tsx:37-117` |
| Ayuda: `ayuda`; pestañas; Sin respuesta, Saber local, últimas 200; Respuestas de los locales Activa/Desactivada | S:80; `backend/app/api/asistente.py:144-232`; `frontend/components/asistente-panel.tsx:59-341` |

### /contenido y farmacias de turno

| Afirmación | Respaldo |
|---|---|
| Página aparte, cuenta del panel, permiso `contenido` (admin y publicador) | `frontend/app/contenido/page.tsx:42-49`; `backend/app/api/contenido.py:29-37`; `backend/app/core/auth.py:176-178`; PE:59-70 |
| Bloques de la página | `frontend/app/contenido/page.tsx:113-231` |
| Videos: título, «+ Video», 100 MB, borrar con confirmación y sin recuperar; dónde se ven | `contenido/page.tsx:105, 164-170`; `contenido.py:24, 137-157`; R:3347-3349; HOME:378-389; `frontend/app/guia/page.tsx:252-260` |
| Novedades de URUKU: dónde salen; todas las ciudades | `frontend/components/novedades-uruku-panel.tsx:77`; `frontend/lib/data.ts:688-698` |
| Formulario, «Crear y seguir con las fotos», portada (fondo verde), 12 fotos, video 100 MB | `novedades-uruku-panel.tsx:181-396` |
| Editar / Dar de baja / Reactivar | `novedades-uruku-panel.tsx:61, 121-131`; `contenido.py:296-305` |
| Importar turnos por comando; idempotente; no escribe si algo no cierra; 8:00 a 8:00 | `backend/app/scripts/importar_turnos_farmacia.py:3-8, 51-56`; `backend/app/services/turnos_farmacia.py:1-20, 43-95, 113-120, 150-163` |
| Las nuevas sin punto quedan con ubicación aproximada | `turnos_farmacia.py:43-95` (`ubicacion_aproximada`); FA:55-59 |
| El público lo ve en el Inicio y en /farmacias-de-turno | `frontend/components/tarjeta-turno-hoy.tsx:13-19`; `frontend/app/farmacias-de-turno/page.tsx:67-159` |

### Tabla de permisos que no coinciden

| Sección | Respaldo |
|---|---|
| Recepción | S:51 vs M:2523 |
| Difusión | S:52 vs M:3000 |
| Catálogo | S:56 vs M:2081 |
| Revisar rubros | S:58 vs M:2760 |
| Planes | S:64 vs M:3093 |
| Demanda | S:72 vs M:3168 |
| Vencimientos | S:67 vs M:2199 |
| Importados | S:45 vs M:1345 |
| Adornos | S:46 vs M:2023, 2049, 2069; PE:61-65 (moderador sin `panel`) |
| Calles y horarios | S:43 vs M:517 |

---

## Manual del comprador (`comprador.md`)

| Afirmación | Respaldo |
|---|---|
| No hace falta cuenta para buscar | `frontend/app/buscar/page.tsx`; BC (sin sesión) |
| «Instalá URUKU» / «Instalar»; iPhone «Agregar a inicio»; X y no vuelve | `frontend/components/install-prompt.tsx:51-54, 66-75` |
| Ciudad: elige la más cercana la primera vez; «Elegí tu ciudad»; «Próximamente» | `frontend/components/city-selector.tsx:52-66, 79, 93` |
| Guía, estado del paso y cambio sólo en ciudades de frontera / con guía | `frontend/components/uruku-shell.tsx:63`; `frontend/app/guia/page.tsx:72`; `frontend/app/cambio/page.tsx:34` |
| Inicio: buscador del header | `uruku-shell.tsx:124-128` |
| Accesos rápidos con y sin guía | `frontend/components/accesos-ciudad.tsx:22-39` |
| Hero, «Ver ofertas del día», «Explorar servicios»/«Ver el mapa» | HOME:178-187 |
| «Hoy en {ciudad}» | HOME:191-214 |
| Farmacias de turno hoy | `tarjeta-turno-hoy.tsx:13-19`; HOME:220 |
| WhatsApp de URUKU con QR | `frontend/components/contacto-uruku.tsx:29-42` |
| Servicios útiles, Antes de comprar, Herramientas útiles | HOME:41-75, 229-261 |
| Ofertas destacadas y Novedades (las de URUKU primero) | HOME:297-358 |
| Barra de abajo con y sin guía | `frontend/components/bottom-nav.tsx:14-32` |
| Buscar con «Buscar» o Enter | BC:39-43, 574-589 |
| Cantidad de resultados | BC:685-695 |
| Tarjeta: estrella, abierto/«¡Oferta!», rubro, modalidad, resaltado, oferta, «Responde por WhatsApp», distancia, botones | BC:854-971 |
| Rubro en la caja con ×; «Buscar «…» en todos los rubros» | BC:577-584, 759-817 |
| Servicios: «Baños públicos en …» con «Ver en el mapa» | BC:87-88, 745-750; `frontend/lib/servicios.ts:16-23` |
| «Cerca de mí» / «Qué hay cerca tuyo» activa solo | BC:78-98, 270, 698-706 |
| Orden: abiertos primero, franjas 300 m / 1 km | `frontend/lib/orden-cerca.ts:1-12`; BC:472-494 |
| «Dar permiso de ubicación»; bloqueado + «Probar de nuevo» | `frontend/components/permiso-ubicacion.tsx:24, 66-88`; `frontend/lib/geo.ts:20-49` |
| Mapa: color por rubro, anillo con estrella, «Dónde estoy» | `frontend/components/map-results.tsx:25-33, 89, 181` |
| Sin filtro: «Buscá o elegí una categoría…»; globo con WhatsApp/Cómo llegar/Ver comercio | `map-results.tsx:241-276, 296-301` |
| Ficha: foto que se amplía | `frontend/components/ficha-galeria.tsx:27-45` |
| Estrella = plan al día o cortesía, «Verificado por URUKU» | `frontend/components/estrella-verificado.tsx:3-7`; `supabase/migrations/0143_estrella_y_cortesia.sql:7-10` |
| Pastillas y textos del horario («Abierto · cierra», «Cerrado hoy · abre mañana»…, «Suele estar…») | FICHA:180-188, 325-328; `frontend/lib/horario.ts:181-196`; `frontend/components/horario-badge.tsx:26-33` |
| Lo que suma: botones y sellos (canal/catálogo si verificado, confiable o de agente) | FICHA:126-134, 222-245 |
| WhatsApp con «Hola {nombre}, te contacto desde URUKU»; «Llamar»; sin ninguno | FICHA:247-267 |
| Cómo llegar, Llamar, Guardar (marcador), Compartir («¡Link copiado!») | FICHA:269-282; `frontend/components/guardar-boton.tsx:36-45`; `frontend/components/compartir-boton.tsx:12-35` |
| QR de la ficha | FICHA:284-291 |
| «Fotos del local», etiquetas, «X% OFF», filtros «Ofertas (N)»/«Novedades (N)», flechas | `frontend/components/galeria-tienda.tsx:113-204` |
| Oferta abierta: «Reservar» y «Consultar» | `galeria-tienda.tsx:240-268` |
| Información del negocio y Ubicación | FICHA:315-403 |
| «¿Hay algún dato incorrecto?» › «Informar un problema» › «Enviar comentario»; lo lee el equipo | FICHA:416-422; `frontend/app/reclamos/page.tsx:49-66` |
| «Preguntame» con Dax; sugerencias; «Enviar»; «¿Te sirvió?» | `frontend/components/asistente.tsx:51, 67, 115-123, 166-186` |
| Asistente del local y «Preguntarle a … por WhatsApp» | FICHA:150-153; `asistente.tsx:65-66, 130-131, 155-160` |
| Reservar sin cuenta, en el celular, una por comercio; barra «Ver reserva» | `frontend/lib/reservas.ts:1-14, 52-73`; `frontend/components/reserva-barra.tsx:22-33`; `frontend/app/reservas/page.tsx:51-53` |
| «Vaciar», «Enviar reserva por WhatsApp», mensaje, «Todavía no está reservado», URUKU no participa | `reservas/page.tsx:30-42, 79-130` |
| /ofertas: «Todo» y rubros; foto → ficha; WhatsApp; solapa Novedades | `frontend/app/ofertas/page.tsx:62-66`; `frontend/components/rubros-publicaciones.tsx:32-39`; `frontend/components/publicaciones-grid.tsx:15-50` |
| /novedades: «De URUKU» arriba | `frontend/app/novedades/page.tsx:58, 71-84` |
| Página de una novedad de URUKU con Compartir | `frontend/app/novedades/uruku/[id]/page.tsx:44-66` |
| Farmacias de turno: De turno ahora, Llamar, Cómo llegar, mapa, Próximos 7 días, 8 a 8; sello en la ficha | `frontend/app/farmacias-de-turno/page.tsx:67-159`; FICHA:192-207 |
| Guía: título, frontera, cambio, secciones, mapa, ofertas y videos | `frontend/app/guia/page.tsx:35-43, 104-254` |
| Cambio: referencia, tus valores, tres cuentas, Dónde cambiar con Cómo llegar | `frontend/components/cambio-calculadora.tsx:108-196` |
| La cuenta sirve para guardar locales, en el servidor | `frontend/lib/usuario.ts:1-5, 109-116` |
| «Ingresar» › «Soy comprador»; el marcador sin sesión abre el ingreso | `frontend/components/ingresar-menu.tsx:21-26`; `guardar-boton.tsx:30, 46-50` |
| Primera vez: «Confirmá con tu WhatsApp», «Continuar», «Confirmar por WhatsApp», CONFIRMAR, 15 min, «Pedir otro código» | `frontend/components/comprador-auth.tsx:134-178`; `backend/app/core/config.py:43-52` |
| «Tu clave para entrar»: 6 números, «Copiar», «Ya la guardé», una sola vez | `comprador-auth.tsx:110-132`; `frontend/components/clave-una-vez.tsx:16, 56, 60` |
| Siguientes: celular + clave de 6 números | `comprador-auth.tsx:118-132` |
| Mi perfil: WhatsApp, guardados, «Cómo se usa URUKU», «Cerrar sesión» | `frontend/app/perfil/page.tsx:54-77` |
| Tus locales guardados: foto, dirección, WhatsApp, X | `frontend/app/guardados/page.tsx:46-85` |
| «¿Te contestó …?» con Sí / No / Todavía no | `frontend/components/pregunta-contesto.tsx:51-58`; `frontend/lib/contestaron.ts:5-12` |
| URUKU no media | `reservas/page.tsx:127-130` |
| WhatsApp 67 671 888 | `frontend/lib/contacto.ts:7-9` |

---

## Manual del comerciante (`comercio.md`)

| Afirmación | Respaldo |
|---|---|
| uruku.bo/mi-comercio; «Ingresar» › «Tengo un negocio»; «¿Cómo se usa?» | MC:75-86; `frontend/components/ingresar-menu.tsx:29` |
| 8 dígitos = +591; «Mostrar»; «Entrar» | IC:59-62, 97-124 |
| Clave `NOMBRE-XXXXXX`, mayúsculas/guion indistintos; la vieja de 6 números sirve | `backend/app/core/clave_comercio.py:1-27, 45-48`; API:292-294 |
| Bloqueo por intentos | API:299-300 |
| Primera vez: pasos, varios negocios, CONFIRMAR, 15 min, «Pedir otro código» | IC:235-321; API:372-401; `backend/app/core/config.py:43-52` |
| Clave nueva con «Copiar» y «Ya la guardé» | API:434-467; `frontend/components/clave-una-vez.tsx:16, 54-61` |
| Tiene que ser el mismo número | API:372-376 |
| Mandar la clave por WhatsApp la anula | ING:463-468; `backend/app/services/clave_filtrada.py:1-19` |
| Menú, Plan actual, Ver planes, Cerrar sesión; «¿Cómo se usa?» y «Publicar oferta» | MC:109-118, 146-175 |
| Aviso de suscripción con «Pagar ahora» | MC:540-555, 578 |
| Mi negocio: Verificado, tarjetas | MC:205-315 |
| Tu clave: Generar, confirmación, «Tu clave nueva» con Copiar; 3 por hora; cierra otras sesiones | `frontend/components/clave-del-comercio.tsx:39-66`; API:478-492 |
| Editar: avisos, vista previa, Categoría, Ubicación, Contacto (horario texto libre), Redes, Guardar cambios | MC:600-611, 649-892 |
| Lo que suma: canal (enlace), catálogo PDF 8 MB o enlace, tildes, pedido mínimo | MC:692-701, 859-881; `frontend/components/tildes-suma.tsx:16-23`; `frontend/components/catalogo-pdf.tsx:44-103`; `frontend/lib/catalogo.ts:5-6` |
| Sellos que ve el comprador; canal/catálogo si verificado o confiable | FICHA:126-134, 222-245 |
| WhatsApp no se edita: «Cambié de número» | MC:597-599, 842; API:666-667 |
| Cambié de número: buscar, número, ubicación y foto obligatorias, «Enviar solicitud»; lo aprueba un admin; claves anuladas | `frontend/app/recuperar-negocio/page.tsx:30-165`; API:235-237; M:1129-1141 |
| Foto principal: Subir/Cambiar; reemplaza sin guardar | `frontend/components/foto-principal.tsx:75-95`; MC:514 |
| «Usar como portada»; «+ Foto»; contador; ×; tope por plan; gratis si vence | GU:317-362; `backend/app/services/fotos_galeria.py:3-16, 78-92` |
| Diálogo de tope: Pagar Bs (si hay precio), Borrar esa y subir la nueva, Cancelar | `frontend/components/tope-fotos-dialogo.tsx:59, 78-131` |
| Videos: 5, 60 s | GU:36, 365-381; API:1191-1193 |
| Sin cola sin señal: avisa cuántas no subieron | MC:524; GU:88, 205-216 |
| Estados En vivo / En revisión / Pide cambios / Rechazada; motivo no se muestra | MC:375-380 |
| Editar (campos, vuelve a revisión) / Eliminar | MC:391-495; API:540-553 |
| Asistente: tipos, preguntas por tipo, imagen como enlace, Descuento/Válido hasta, Publicar en vivo / Enviar a moderación, Aviso sobre tu plan | AR:311-497 |
| Confiable → directo | API:879-901 |
| Dónde se ven: «Fotos del local» con filtros; Reservar en ofertas | `frontend/components/galeria-tienda.tsx:115-125, 255` |
| Reservar llega por WhatsApp; apartado cuando contesta | `frontend/app/reservas/page.tsx:30-42, 116-121` |
| WhatsApp 1-a-1 por el número registrado, sin código | ING:134-138 |
| Directo si confiable; tipo y precio automáticos | ING:242-272, 635, 655-681 |
| Foto y precio en 2 mensajes dentro de 10 min | ING:198-239, 700-705 |
| Compartir la ubicación la actualiza | ING:565-575 |
| URUKU lee y no contesta | `backend/app/core/config.py:187`; `backend/app/services/mensajeria.py:56-58` |
| Otro número sin código no se identifica | ING:140-157; AGENTS.md §3 (`wa_inbox` sin_comercio) |
| Grupo atado; otro remitente → moderación | ING:87-104, 642-646 |
| Contactos: visitas 30/7, quién te contactó por tipo; llamadas no se cuentan | MC:325-363; FICHA:254, 276 |
| Estadísticas: visitas, Con qué te buscan, contactos, publicaciones | MC:1044-1103; API:811-847 |
| Chatbot: Preguntame siempre; Destacado/Pro; preguntas, Responder, Guardar respuesta; respuestas; tarjeta sin plan | `frontend/components/chatbot-del-local.tsx:127-305`; FICHA:150-153; `supabase/migrations/0136_chatbot_de_los_comercios.sql:63-65`; `supabase/migrations/0108_planes_sin_canal_con_chatbot.sql:44` |
| Bandeja: Responder por WhatsApp / Marcar leído | MC:1109-1143 |
| Suscripción: Ver planes / Pagar ahora; estados; Consultá el monto; formulario; Enviar comprobante; lo confirma un admin | MC:899-1030; API:750-787, 1126-1158 |
| Configuración «Próximamente» | MC:365-372 |
| Ficha pública: botones y secciones | FICHA:222-421 |

---

## Manual del agente (`agente.md`)

| Afirmación | Respaldo |
|---|---|
| uruku.bo/publicar; login; «Credenciales incorrectas» | PUB:489, 494-503; CAM:46-58 |
| Se instala como «URUKU Campo» | `frontend/app/publicar/layout.tsx:3-12`; `frontend/public/campo.webmanifest:3-4` |
| Recuerda la sesión; «Manual» y «Salir» | PUB:37-56, 95, 103; QA:268-273 |
| «Qué hay acá» primera pantalla; toma el GPS | PUB:88, 110-119; QA:183 |
| Precisión, «Actualizar mi ubicación», aviso > 50 m | QA:333-345 |
| Pines con foto y borde del color del plan | `frontend/components/mapa-aca.tsx:143-163` |
| «Cargados a menos de 150 m»; ítem con sello «Al día/De cortesía/Gratis/Vencido», Completo / Le faltan | QA:48, 395-441; `frontend/components/sello-plan.tsx:8-12` |
| «Ver más lejos (hasta 400 m)» / «Volver a 150 m» | QA:445-454 |
| «Cargar un local nuevo acá» con el GPS tomado | QA:458-459; PUB:114 |
| Sin señal: lista guardada; ficha y mapa necesitan conexión | QA:194, 210, 219-223, 349-353 |
| Ficha del local: secciones, Completar / Revisar o editar, Plan y estado | FA:164-284 |
| Ubicación aproximada = salió de la dirección; «Tomar el GPS acá», pregunta, botones; > 50 m no | FA:53-109, 206-208; CAM:745-751 |
| «Calles» Sí/No, recuerda | QA:120, 286-293 |
| «X de Y km recorridos» | QA:294-298 |
| Leyenda y colores | `frontend/components/calle-panel.tsx:33-56`; `frontend/lib/calles.ts:59-83`; `frontend/lib/calles-mapa.ts:49-98` |
| «Calles pendientes cerca» (8) | QA:54, 363-391 |
| Ficha de la calle: Cobertura, Comercios, Último paso, Marca, Nota, botones, «Marcada como…», sin señal no marca | `calle-panel.tsx:61-169` |
| Sólo su ciudad | `backend/app/api/calles.py:87-110` |
| La ciudad sale del GPS | CAM:255-262 |
| Alta: campos, sólo ubicación obligatoria, botones exactos | PUB:903, 1214-1254; CAM:223-240 |
| Nombre vacío lo arma URUKU | CAM:267-273 |
| El rubro no se elige en el alta | PUB:928-930; CAM:362-365 |
| «Ya cargados acá cerca»: 40 m, «Es este» | `frontend/components/ya-cargados-aca.tsx:22, 60, 73-99`; PUB:1202-1211 |
| Después de guardar: orden de lo que aparece | PUB:1003-1079 |
| WhatsApp: país, «Guardar +591 …», vista previa | `frontend/components/captura-whatsapp.tsx:98-170` |
| Un WhatsApp distinto ya no se pone desde la app | CAM:728-742 |
| Clave `NOMBRE-XXXXXX`, prefijo y azar | `backend/app/core/clave_comercio.py:45, 101-128` |
| Una sola vez, sin copiar, papel aparte, «Listo» | `frontend/components/clave-una-vez.tsx:24-26, 54-58`; CAM:398-410 |
| Se pierde al tocar Listo / Cargar otro / Volver / Ver mis comercios o recargar | PUB:1070-1077 (estado en memoria) |
| El agente no genera otra; el dueño por WhatsApp o el admin | IC:120; `frontend/components/admin/generar-clave.tsx:53` |
| Completar: desde dónde se abre, «Le falta (N)», «No le falta nada de lo básico» | CC:339-386; `frontend/lib/faltas.ts:23-37` |
| Orden de las secciones (incluye Lo que suma) | CC:389-597 |
| Fotos/portada/PDF se suben solos; botón «N cambios sin guardar», «Guardar», «Reintentar guardar» | CC:99, 291, 601-636 |
| Rubro principal = el primero | CC:263; `backend/app/db/repository.py:2884-2888` |
| Atajos de horario | `frontend/components/editor-horario.tsx:39-50` |
| WhatsApp ya cargado: «no se cambia desde acá» y «Cambié de número» | CC:398-433 |
| Cambiar foto: la actual pasa a la galería | CC:328; CAM:815-826 |
| «+ Foto», «Usar como portada», «+ Video» ≤ 60 s | GU:317-382 |
| Tope del plan: texto exacto | GU:318-329 |
| Lo que suma: tildes y pedido mínimo; sellos en la ficha | CC:575-584; FICHA:129-134 |
| Ofrecer: tres bloques, «Ver ficha», «Anotar interés», «Anotado…», no cobra, sin precios, «Mandarle su ficha», «Abrir WhatsApp con el mensaje» (no se guarda), «Ver el mensaje» | `frontend/components/ofrecer-comercio.tsx:72-248`; CAM:556-660 |
| «Mis comercios»: toda la ciudad + lo suyo afuera | PUB:155-473; CAM:515-553 |
| Buscador, orden, filtros con conteo y su definición, «Acá» 120 m | PUB:129-138, 152, 191-202, 282-347 |
| Sin horario: «Usar mi ubicación» / ordenados por distancia; «Cargar horario» | PUB:377-388, 417-458 |
| «Ver más (N restantes)», de a 50 | PUB:463-466 |
| Vista Mapa: color por rubro, punto ámbar | `frontend/components/admin-map.tsx:184-203` |
| Sin conexión: se guarda en el celular ante cualquier error; aviso ámbar con Sincronizar / Ver cuáles son / Descartar | PUB:954-980, 1018, 1115-1175 |
| «N alta guardada sin subir» con «Ver y subir» | QA:277-281 |
| Sube solo sólo con la pantalla de alta abierta | PUB:776-783 |
| «Clave de …» y «Ya se la di al dueño» al subir | PUB:62-75 |
| Edita cualquier comercio de su ciudad | CAM:589-605 |
| No verifica, no da de baja | CAM:327, 663-709 |
| No borra fotos, videos ni catálogo | CAM:795-803, 1019-1023, 1041-1045, 1083-1087; `backend/app/services/fotos_galeria.py:49` |
| Agente = sólo `comercios.cargar`, no entra al panel | PE:71-75, 112-119 |

---

## Qué es URUKU (`uruku.md`)

| Afirmación | Respaldo |
|---|---|
| Sin descargar ni registrarse | `frontend/app/buscar/page.tsx`, BC (sin sesión) |
| Muestra quién vende, dónde y si está abierto | BC:854-971; `frontend/lib/horario.ts:181-196` |
| WhatsApp y Cómo llegar | FICHA:247-282 |
| Ofertas y novedades; servicios y cambio | HOME:229-358; `frontend/app/cambio/page.tsx` |
| Se puede entrar desde cualquier lugar | `frontend/middleware.ts` (sin restricción geográfica) |
| Mi comercio: datos, visitas y contactos | MC:288-293, 325-363 |
| Publicar por WhatsApp | ING:134-138 |
| Las ofertas se revisan salvo los de confianza | `backend/app/services/ingest.py:628-683` |
| «¿Hay algún dato incorrecto?» | FICHA:416-422 |
| Cargamos los locales parados en su puerta | CAM:223-240 (el alta exige el GPS del agente) |
| WhatsApp 67 671 888 y su QR | `frontend/lib/contacto.ts:7-9`; `frontend/components/manual/manual-servidor.tsx:57-83` |

---

## Lo que se sacó por inventado o sin respaldo

### agente.md
- Sección **«Por rubro»** del mapa de calles: no existe. `rubro` no aparece en `lib/calles.ts`, `lib/calles-mapa.ts`, `components/calle-panel.tsx`, `components/admin-calles*.tsx`, `components/mapa-aca.tsx`, `components/que-hay-aca.tsx`, `backend/app/api/calles.py` ni `backend/app/services/calles_mapa.py`; `TramoCalle` no tiene rubro (`lib/calles.ts:26-40`).
- Colores **verde / amarillo / rojo** del mapa de calles y «Tocá «Mapa» en el menú»: es el interruptor «Calles» con cinco estados.
- «Ver los comercios que la tocan» y «Marcarla como hecha»: la ficha muestra la cantidad y los botones son Recorrida / Sin comercios / Pendiente.
- **«Ofrecer plan»**, **«Ofrecerle un interés»** («Nadie vende X acá», «Mercería») y **«tomar el comprobante»**: no existen; es «Le interesa un plan» y no cobra.
- «Copiar su WhatsApp», «Ver dónde está en el mapa», «Mirar su ficha — cómo quedó en el sitio» en la ficha del agente.
- «Ubicación aproximada = sin señal» y «URUKU ubica el local, no al agente»: aproximada es la que salió de una dirección.
- «Solo vos subís información… Nadie más edita lo que cargaste».
- «Cambiar foto reemplaza la del frente» (pasa a la galería).
- «Cuando vuelva internet, se sube solo» (sólo con la pantalla de alta abierta).
- Tiempos por comercio y por hora (4-6 min, 10-12 por hora, 35-45 por mañana): sin respaldo; queda el consejo de calidad.

### admin.md
- Publicaciones «sólo la cola de pendientes» (hay «Publicadas» y «Bajar»).
- Difusión «Reintentar» (el botón es «Publicar»).
- Rubros «los cambios de nombre se ven en el sitio» (no se renombran).
- «Recalcular en tanda» como botón (es un título con dos botones).
- Mapa de calles verde/amarillo/rojo, «cargar horarios para esa zona» y «zoom por rubro».
- En el editor: «Foto de la vidriera (portada)», «Pagar una foto extra», Lo que suma con «checkbox» para canal y catálogo, pedido mínimo «número», «hasta 3 claves por hora» (eso es de Mi comercio).
- «La X» de dar de baja y «Dados de baja» como sección aparte.
- Planes «Gratis, Publica, Básico, Destacado y Pro» (el gratis se llama Básico; hay ocultos).
- Manuales «los cuatro, incluido el comprador» (no estaba; ahora sí).
- Equipo «roles: admin, moderador, publicador y agente» como lista cerrada (se pueden crear).

### comercio.md
- El menú «Configuración › Ver planes» y «en la app no hay botones de compra».
- «El teléfono no la copia» (la clave del comerciante sí tiene «Copiar»).
- Fotos sin señal guardadas en el celular (eso es del agente).
- «Foto de la vidriera (portada)» y «Borrar la más vieja» como texto del botón.
- El asistente que pide TikTok para cualquier oferta, y las secciones «Ofertas»/«Novedades» de la ficha.
- Estadísticas «Mensajes por WhatsApp».
- «Si escribís desde otro número, no se publica» sin matices: se reformuló.

### comprador.md
- Sugerencias del buscador mientras escribís, filtros «Abierto», orden por nombre, Categoría/Zona/Precio.
- Estrella = «el equipo comprobó que el local existe» (es plan al día o cortesía).
- Contador de «Contactos» en la ficha.
- Login «Seleccioná URUKU de la lista de chats… Verificá el código».
- Guardar con «corazón», guardar ofertas y reservas en Guardados, «Compartir» la lista.
- «Reservas» con estado y confirmación del comercio; «sin cuenta no podés reservar».
- WhatsApp directo a las casas de cambio; búsqueda y mapa dentro de /ofertas.
- Guía con sección «Medios de pago»; «Explorar servicios › Guía».
- «El equipo avisa al comercio para que corrija».

### uruku.md
- «Cargamos cada local en su puerta, con su dueño» y «No es un listado copiado de internet» (hay horarios estimados por calle e importados de OpenStreetMap): reformulado a lo que respalda el código.

---

## Hallazgos del relevamiento (código, no manual)

No se corrigieron en esta tanda; quedan para decidir:

1. **Agente — videos**: el botón de borrar video se muestra, el servidor responde 403 y la app igual lo saca de la lista (`frontend/components/galeria-uploader.tsx:287-291, 371`; `frontend/lib/campo.ts:133-134`).
2. **Agente — «Cambiar» el WhatsApp** después del alta siempre termina en error si el número es otro (`frontend/components/captura-whatsapp.tsx:106`; CAM:728-742).
3. **Agente — casilla «El dueño aceptó aparecer»** no se guarda, sólo va al log (CAM:301-338, 397).
4. **Agente — modo mercado** del alta no se puede activar (`crearNuevoLugar` sin uso, PUB:833).
5. **Importados — «Descartar»**: cancelar el cuadro del motivo descarta igual (`frontend/components/importados-panel.tsx:181-182`).
6. **Permisos menú ≠ backend** en 10 secciones (tabla de arriba); el Moderador ve Adornos y no puede guardar.
7. **Mi comercio en el celular**: la barra lateral de 244 px no tiene versión móvil (MC:125).
8. **Mi comercio — «Acepto reservas»** no tiene efecto visible: nada lee `acepta_reservas` (MC:883-886; `galeria-tienda.tsx:255`).
9. **«Soy comprador»** promete «Guardá locales y ofertas»: sólo se guardan locales (`frontend/components/ingresar-menu.tsx:26`; `frontend/lib/usuario.ts:109-116`).
10. **Guardados vacío** dice que se guarda «desde el mapa», pero el globo del mapa no tiene botón de guardar (`frontend/app/guardados/page.tsx:63`).
11. **Pie del sitio**: «Preguntas frecuentes», «Términos y condiciones» y «Política de privacidad» apuntan a `#` (`frontend/components/uruku-shell.tsx:169-171`).
12. **/perfil, /guardados, /reservas** muestran siempre la barra de abajo «con guía» (`bottom-nav.tsx:34`).
