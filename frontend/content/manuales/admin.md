# Manual del administrador

El panel de URUKU desde el navegador: **uruku.bo/admin**.

Para quienes moderan publicaciones, verifican negocios, cobran suscripciones, organizan el trabajo de los agentes y atienden a los comerciantes. Cada persona ve en el menú sólo las secciones para las que tiene permiso.

---

## Entrar y moverse

Entrá con tu correo y tu contraseña y tocá **«Entrar»**. Si dice «Credenciales incorrectas», revisalos.

![La pantalla de ingreso al panel](/manuales/capturas/admin/01-ingreso-desktop.webp)

- **El menú** (a la izquierda) agrupa las secciones. Algunas llevan un número con lo pendiente: Negocios (sin verificar), Publicaciones, Reclamos, Recepción (sin comercio), Cambios de número, Pagos, Suscripciones y Vencimientos (en rosa: es urgente).
- **La barra de arriba** tiene **la ciudad**, **«Ver sitio»** y **«Salir»**.
- Cada sección tiene su propia dirección (`uruku.bo/admin?s=negocios`, por ejemplo): se puede guardar o mandar.
- Si entrás por enlace a una sección sin permiso, dice **«No tenés permiso para entrar a esta sección.»** con **«Ir al Inicio»**.

![La sección a la que no tenés permiso](/manuales/capturas/admin/02-sin-permiso-desktop.webp)

### La ciudad

En la barra de arriba elegís una ciudad o **«Todas las ciudades»**. El panel la recuerda. Algunas secciones se filtran por esa ciudad; las que no, lo dicen debajo de la barra: **«Esta sección no depende de la ciudad»** o **«Esta sección todavía muestra todas las ciudades»**.

![El selector de ciudad del panel](/manuales/capturas/admin/03-ciudad-desktop.webp)

### Las 27 secciones

| Grupo | Secciones |
|---|---|
| (arriba) | Inicio |
| Comercios | Negocios · Calles y horarios · Lugares · Importados · Adornos · Cambios de número |
| Contenido | Publicaciones · Recepción · Difusión · Reclamos |
| Catálogo | Catálogo · Rubros · Revisar rubros |
| Campo | Cargas |
| Negocio | Planes · Suscripciones · Pagos · Vencimientos |
| Análisis | Monitoreo · KPIs · Demanda · Compradores |
| Equipo | Equipo · Manuales · Ayuda |

Aparte del panel está **uruku.bo/contenido** (cotización, frontera, videos y Novedades de URUKU), al final de este manual.

---

## Inicio

El tablero. No pide permiso. Se filtra por la ciudad.

![El Inicio: «Para hacer hoy» y las tarjetas](/manuales/capturas/admin/04-inicio-desktop.webp)

Arriba dice a qué hora se actualizó, con el botón **«Actualizar»**.

**«Para hacer hoy»**: lo que alguien tiene que resolver, cada fila con su botón:

| Fila | Botón |
|---|---|
| Vencimientos (urgente) | «Ver alertas» |
| Pagos por confirmar (urgente) | «Confirmar pagos» |
| Suscripciones por vencer, vencidas o suspendidas | «Ver suscripciones» |
| Publicaciones por moderar | «Moderar» |
| Reclamos | «Ver reclamos» |
| Cambios de número | «Resolver» |
| Mensajes de Recepción sin comercio (7 días) | «Ver mensajes» |
| Comercios sin verificar | «Verificar» |

Sólo ves las filas de las secciones que podés abrir. Las que no dependen de la ciudad dicen «de todas las ciudades». Si no hay nada: **«Todo al día»**.

**Las tarjetas**: Comercios, Verificados (con **«Verificar (N)»**), Con horario (con **«Cargar horarios (N)»**), Con WhatsApp, Visitas y Contactos de los últimos 7 días.

**Los gráficos**: «Altas por día», «Visitas y contactos por día» (30 días), «Fichas completas» (horario, WhatsApp, foto, rubro) y «Comercios por ciudad» (siempre todas las ciudades).

![Los gráficos del Inicio](/manuales/capturas/admin/05-inicio-graficos-desktop.webp)

---

## Comercios › Negocios

Permiso: `moderar`. Se filtra por la ciudad.

La lista de todos los comercios activos, con el editor de cada uno.

![Negocios: la lista con filtros](/manuales/capturas/admin/06-negocios-lista-desktop.webp)

### Qué se ve

- **«Resumen por ciudad»**: una tabla con Total, Con foto sin clasificar, Incompletos, Sin horario y Sin verificar por ciudad. Tocá una fila para elegir esa ciudad.
- **«Activos» / «Dados de baja»** (con permiso `comercios.editar`).
- **El buscador**: nombre, código (URUKU-K7M2), productos, dirección, teléfono, rubro o ciudad. Tienen que estar todas las palabras.
- **El orden**: «Más recientes», «A → Z», «Pendientes primero».
- **«Lista» / «Mapa»**, y el atajo a **«Calles y horarios»**.
- **Los filtros**, con cuántos hay: **Todos**, **Pendientes** (sin verificar), **Verificados**, **Incompletos** y **Sin horario**.

**Incompleto** quiere decir: sin nombre (salvo los marcados «sin cartel»), sin foto, sin contacto, sin clasificar (sin rubro o con «otros») o sin productos. A los servicios que no son comercios (baños, cajeros…) sólo se les pide nombre y foto.

![El filtro «Incompletos»](/manuales/capturas/admin/07-negocios-incompletos-desktop.webp)

En **«Mapa»** cada pin es un comercio; tocarlo abre el editor.

![Negocios en vista de mapa](/manuales/capturas/admin/08-negocios-mapa-desktop.webp)

Cada fila muestra la foto (tocala para verla grande), el nombre, si está **verificado**, **pendiente** o **suspendido**, lo que le falta, su código `URUKU-…`, los rubros (el principal en negrita), la ciudad, la modalidad y lo que vende.

### Los botones de cada fila

Son íconos; al pasar el mouse dicen qué hacen:

- **«WhatsApp +…»**: abre un chat con el comercio.
- **«Ver en mapa»**.
- **«Volante para imprimir»** y **«Tarjeta de mesa con el QR (4 por hoja)»**.
- **«Recalcular el rubro»**: abre «Rubros de …» en la misma fila (ver Revisar rubros).
- **«Editar»** (el lápiz). Tocar el nombre también abre el editor.
- **«Verificar»**: sólo en los que no están verificados.
- **«Dar de baja»** (con `comercios.editar`).

**«Clasificar por fotos»**: arriba de la lista, si hay comercios con foto y sin clasificar, **«Analizar N pendientes»** le pide a la IA que los clasifique mirando la foto (**«Detener»** lo corta).

### Verificar

Tocalo cuando ya chequeaste que el comercio existe. No pide confirmación y **no se deshace**: no hay botón para quitar la verificación.

### Editar negocio

![El editor de un negocio](/manuales/capturas/admin/09-editar-negocio-desktop.webp)

Arriba dice **«Editar negocio»** y la posición («3 de 120»). Las flechas **«←»** y **«→»** pasan al anterior o al siguiente **sin guardar**; Escape lo cierra.

- **Foto principal**: «Es la primera que ve el comprador». **«Subir otra»** la reemplaza: la app avisa que la actual **no queda guardada** (si querés conservarla, elegí otra de la galería con «Usar como portada»). Con **«Más arriba»** / **«Más abajo»** se ajusta el recorte.
- **Nombre** («El nombre del cartel») y el tilde **«No tiene cartel ni nombre propio»**: URUKU arma el nombre con lo que vende y dónde está.
- **Código para publicar por WhatsApp**: `URUKU-…` con **«Copiar»**.
- **WhatsApp**: sólo lo cambia quien tiene `comercios.cuenta` («El WhatsApp es la llave de la cuenta»).
- **Teléfono**, **Productos observados** (lo escribe una persona; la IA no lo toca), lo **detectado por IA** y la **Descripción** (la regenera la IA en cada análisis).
- **Categorías** (tocá varias) y **el principal**, que es el que se ve en la ficha.
- **Modalidad**: Mayorista, Minorista o Mayorista y minorista.
- **Dirección**.
- **Horario**, con atajos («8-12 · 14:30-20 (L-S)», «Corrido 8-20 (L-S)», «24 horas», «Noche 21-4 (V y S)»…), **«Limpiar»** y **«Igual que el anterior»** (aparece si ya guardaste otro horario en este navegador). Debajo dice cómo lo entiende el sitio («Ahora mismo: …») o **«No se entiende»**.
- **Redes y contacto**: Instagram, Facebook, TikTok, sitio web y email.

#### Galería: fotos del local

![La foto principal y la galería en el editor](/manuales/capturas/admin/10-editar-fotos-desktop.webp)

- **«+ Agregar fotos»** sube varias.
- Cada foto tiene **«Borrar foto»** (pide confirmación; no se deshace) y **«Usar como portada»** (con `comercios.editar`): la elegida pasa a ser la foto principal y **la anterior entra a la galería**.
- La cantidad de fotos depende del plan del comercio. Si llegó al tope, el panel muestra **«Llegaste al tope de fotos»** y cuál se borraría: **«Borrar esa y subir la nueva»** o **«Cancelar»**. Desde el panel no se cobra una foto extra.

#### Lo que suma

![«Lo que suma» en el editor](/manuales/capturas/admin/11-editar-lo-que-suma-desktop.webp)

- Tildes: **Tiene pasero**, **Hace envíos**, **Da factura**, **Trabaja talles especiales**.
- **Pedido mínimo**: texto libre («3 docenas, 200 Bs»).
- **Canal de WhatsApp del comercio**: un enlace (el del comercio, no el de URUKU). Vacío lo quita.
- **Catálogo**: **«Subir catálogo (PDF…)»**, **«Cambiar el PDF»**, **«Quitar»**, o un enlace.

#### Clasificar desde las fotos (IA)

**«Analizar»** le pide a la IA el rubro y los productos mirando las fotos. Muestra la confianza («alta», «media», «baja») y se elige **«Aplicar»** o **«Descartar»**.

#### Generar clave nueva

Sólo con `comercios.cuenta`. Es la clave con la que el dueño entra a Mi comercio.

![Generar una clave nueva para el comercio](/manuales/capturas/admin/12-generar-clave-desktop.webp)

1. Tocá **«Generar clave nueva»**.
2. El panel avisa: «La clave anterior deja de servir». Confirmá con **«Sí, generar clave nueva»**.
3. Aparece **«Clave nueva de …»**, con la forma `NOMBRE-XXXXXX`, una sola vez, con **«Copiar»** y **«Listo»**. La sesión que el dueño tenía abierta se cierra.

Entregásela sólo al dueño, en mano o por el WhatsApp de la ficha.

#### Guardar

Abajo: **«Cancelar»**, **«Guardar cambios»** y **«Guardar y siguiente →»**.

#### Sólo lectura

Si tu rol puede ver Negocios pero no tiene `comercios.editar`, el editor dice **«Sólo lectura: tu cuenta no tiene permiso para editar negocios. Las fotos de la galería sí las podés agregar o borrar.»** y abajo sólo está **«Cerrar»**.

![El editor en sólo lectura](/manuales/capturas/admin/13-solo-lectura-desktop.webp)

### Dar de baja, Dados de baja y Reactivar

**«Dar de baja»** (en la fila) pregunta «¿Dar de baja …? Deja de verse en URUKU. No se borra: lo podés reactivar desde «Dados de baja».» No pide motivo: queda registrado como «Dado de baja por el admin».

![El botón «Dar de baja» en la fila de un comercio](/manuales/capturas/admin/14-dar-de-baja-desktop.webp)

En **«Dados de baja»** ves los que no se muestran en URUKU, con la fecha y el motivo. **«Reactivar»** pregunta y lo vuelve a mostrar. Los que se bajaron por falta de pago no se reactivan acá: vuelven solos al registrar el pago.

![La lista «Dados de baja» con «Reactivar»](/manuales/capturas/admin/15-dados-de-baja-desktop.webp)

> El tilde **Confiable**, **Suspender** y los **grupos y números de WhatsApp** de cada comercio están en **Suscripciones**, no acá.

---

## Comercios › Calles y horarios

Permiso: `moderar` (poner horarios en lote pide además `comercios.editar`). Se filtra por la ciudad.

Dos pestañas: **«Horarios»** y **«Mapa»**.

### Horarios: cargar el horario a toda una calle

![Calles y horarios: la lista de calles](/manuales/capturas/admin/16-calles-horarios-desktop.webp)

La calle sale del GPS de cada comercio. Cada fila es una calle, con cuántos comercios tiene y cuántos sin horario.

1. Abrí la calle.
2. En **«¿A qué rubros de esta calle les va el mismo horario?»**, destildá los que no van (baños, cajeros, estacionamientos, wifi, taxis y emergencias vienen destildados).
3. Elegí uno de los 4 atajos («Mayorista · 6 a 16», «Comercio · 8-12 y 14:30-20», «Corrido · 8 a 20», «Alimentos · 7 a 21») o escribilo. Los dos turnos de un día van con **«y»**.
4. **«Sólo a los que no tienen horario»** y **«Marcarlo como estimado»** vienen tildados. Destildá el primero sólo si querés pisar horarios ya cargados. Con el segundo, la ficha dice que es el horario habitual de la calle y que conviene confirmar.
5. Tocá **«Poner el horario a N comercios»**. No pide confirmación.

![Una calle abierta, lista para ponerle el horario](/manuales/capturas/admin/17-calles-horario-calle-desktop.webp)

### Mapa: lo recorrido

Hay que elegir una ciudad. Arriba dice **«X de Y km recorridos (N %)»**, con **«Actualizar»** y los botones **«Zonas»** y **«Calles»**.

- **Zonas**: cada cuadrado son unas cuatro cuadras; cuanto más verde, más recorrido. Tocá uno para acercarte y ver sus calles.

![El mapa por zonas](/manuales/capturas/admin/18-calles-zonas-desktop.webp)

- **Calles**: cada calle pintada según su estado.

![El mapa de calles con su leyenda](/manuales/capturas/admin/19-calles-mapa-desktop.webp)

| Color | Estado |
|---|---|
| Naranja | **Seguir por acá**: la cuadra pendiente que sigue a una recorrida |
| Verde | **Recorrida**: el 60 % o más tiene un comercio cerca |
| Ámbar, rayado | **Parcial**: entre el 15 y el 60 % |
| Gris, fino | **Pendiente** |
| Gris claro, punteado | **Sin comercios** |

Lo que marca una persona gana sobre el cálculo. Tocá una calle para abrir **su ficha**: cobertura, cuántos comercios, el último paso, la marca, una **nota** y los botones **«Recorrida»**, **«Sin comercios»** y **«Pendiente»**.

![La ficha de una calle](/manuales/capturas/admin/20-calles-ficha-desktop.webp)

Si una ciudad todavía no tiene calles, el botón **«Traer calles de OpenStreetMap»** las carga (pide el permiso `lugares`; puede tardar un minuto).

---

## Comercios › Lugares

Permiso: `lugares`. Hay que elegir una ciudad.

Los **mercados, galerías, paseos, shoppings y referencias** de la ciudad, sobre un mapa.

![Lugares: el mapa con mercados y galerías](/manuales/capturas/admin/21-lugares-desktop.webp)

- Escribí el nombre, elegí el tipo y **tocá el mapa** para ubicarlo. **«Agregar»** lo crea; con uno elegido, **«Guardar cambios»**, **«Nuevo»** o **«Borrar»** (los comercios quedan sin lugar).
- **«Dibujar manzana»**: tocá las esquinas (al menos 3) y **«Guardar manzana»**; **«↶ Deshacer»** y **«Cancelar»**. **«Borrar manzana»** la quita.
- Abajo, la lista: cada lugar con su tipo y cuántos puestos tiene.

---

## Comercios › Importados

Permiso del menú: `datos` (las acciones piden `panel`). Se filtra por la ciudad.

Negocios traídos de **OpenStreetMap**. Traen nombre y ubicación, a veces teléfono y casi nunca foto.

![Importados: los negocios de OpenStreetMap](/manuales/capturas/admin/22-importados-desktop.webp)

- Filtros: **«Sin revisar»**, **«En el mapa»**, **«Descartados»**, y un buscador.
- El tilde **«Ocultar N que parecen ya estar cargados»** viene prendido; los dudosos dicen «ya cargado?».
- En «Sin revisar», elegí el rubro y tocá **«Al mapa»** (crea el comercio, activo y sin verificar; no pide confirmación) o **«Descartar»** (pide el motivo: cerrado, duplicado, no es comercio…).

---

## Comercios › Adornos

Permiso del menú: `lugares` (guardar pide `panel`). Hay que elegir una ciudad.

Las **chalanas**, los **lapachos** y las **banderas** que se dibujan en el mapa público, debajo de los pines.

![Adornos sobre el mapa](/manuales/capturas/admin/23-adornos-desktop.webp)

Elegí qué querés poner y **tocá el mapa**: se crea al instante. Arrastralo para moverlo. Con uno elegido: **Tamaño**, **Cuál** (el color del lapacho o el país de la bandera), **Giro** (chalanas) y **«Borrar»** (no pide confirmación).

---

## Comercios › Cambios de número

Permiso: `panel`. Muestra todas las ciudades.

Los dueños que perdieron el celular y piden cambiar el WhatsApp de su comercio. **Nunca se aprueba solo.**

![Un pedido de cambio de número](/manuales/capturas/admin/24-cambio-numero-desktop.webp)

Cada pedido muestra el número actual y el nuevo, **«Ver ubicación enviada»** (dónde estaba al pedirlo), el mensaje, y **«Foto registrada»** junto a **«Foto nueva»**.

1. Compará la fachada y la ubicación con las de la ficha.
2. Si coinciden, tocá **«Aprobar»**: el número cambia y **las claves del comercio dejan de servir** (el dueño entra por WhatsApp desde el número nuevo y recibe otra).
3. Si no, **«Rechazar»**.

No piden confirmación.

---

## Contenido › Publicaciones

Permiso: `moderar`. Muestra todas las ciudades.

Dos pestañas: **«Pendientes (N)»** y **«Publicadas»**.

### Pendientes: la cola de aprobación

Lo que mandaron los comercios que **no son confiables** (lo de los confiables sale directo).

![La cola de publicaciones pendientes](/manuales/capturas/admin/25-publicaciones-pendientes-desktop.webp)

Cada tarjeta muestra la foto, el comercio y el tipo, el texto, el precio, si trae TikTok y la fecha, y **cómo se identificó** al comercio («por código URUKU-…», «número sin confirmar» o «sin identificar»). La cola viene ordenada con lo más dudoso arriba.

Los botones de cada una (íconos):

- **El tipo** (Oferta, Novedad o Video): corregilo si hace falta; se guarda con cualquiera de los tres botones de abajo.
- **«Revisar con IA»**: muestra qué sugiere la IA («IA sugiere aprobar», «IA sugiere rechazar» o «IA: revisión humana», con el porcentaje y el motivo). **No aprueba nada.**
- **«Aprobar»**: sale publicada y entra en la cola de **Difusión** (el canal de WhatsApp de URUKU; Facebook e Instagram, si el plan los incluye).
- **«Solicitar cambios»** y **«Rechazar»**: piden un motivo, opcional. El comercio ve «Pide cambios» o «Rechazada».

![El veredicto de la IA en una publicación](/manuales/capturas/admin/26-publicaciones-ia-desktop.webp)

> El comercio ve el estado, **no el motivo**. Si tiene que saber qué cambiar, avisale por WhatsApp.

**«Revisar todas con IA»** aprueba solas las que la IA marca para aprobar con 80 % de confianza o más. El resto queda para vos. No pide confirmación.

Si aparece la tarjeta **«Leer las fotos de las ofertas»**, **«Analizar»** hace que la IA lea las ofertas que llegaron como foto sin texto, para que se puedan buscar (pide el permiso `panel`).

### Publicadas: bajar una publicación

![«Publicadas» con el botón «Bajar»](/manuales/capturas/admin/27-publicaciones-bajar-desktop.webp)

Lo que ya se ve en el sitio, con un buscador por título o comercio. **«Bajar»** pide un **motivo obligatorio** y **«Bajar esta publicación»**: deja de verse y el comercio la ve «Rechazada».

Cada plan tiene un máximo de publicaciones guardadas (se cambia en Planes). Cuando un comercio lo pasa, se archiva sola la más vieja.

---

## Contenido › Recepción

Permiso del menú: `whatsapp` (ver la bandeja pide `moderar`). Muestra todas las ciudades.

Los mensajes de WhatsApp que llegaron y qué pasó con cada uno.

![Recepción: la bandeja de WhatsApp](/manuales/capturas/admin/28-recepcion-desktop.webp)

Arriba dice **«WhatsApp conectado»**, **«WAHA no responde»** o **«WhatsApp caído»**. Si no dice conectado, **no entra ninguna oferta**: avisale al equipo técnico.

- **El buscador**: un comercio por nombre, código `URUKU-…` o teléfono. Al buscar, muestra todo lo de ese comercio.
- **Los filtros**: **«Para mirar»** (lo que no se supo de quién es, lo que el plan no permite, los errores y lo que quedó sin procesar), **«Publicadas»**, **«Ignoradas»** y **«Últimas 150»**.
- **«Por comercio»** / **«Lista plana»**: agrupado o uno abajo del otro.
- Cada mensaje dice su resultado: **Publicada**, **Ignorada**, **No se supo de quién es**, **El plan no alcanza**, **Error** o **Sin registrar**, con el motivo, el grupo o el número, y el texto.
- **«Reprocesar»**: en los que quedaron a medio procesar.
- **«Plan B · API oficial de Meta»** (plegado): el estado del número de respaldo y **«Mandar un mensaje de prueba»**.

Desde acá **no se le asigna un mensaje a un comercio**. Para que lo que llegue de un grupo o de un número cuente para un comercio, atalo en **Suscripciones** › «Confiable y números autorizados». Vale para los mensajes que lleguen después.

---

## Contenido › Difusión

Permiso del menú: `difusion` (ver la cola pide `moderar`). Muestra todas las ciudades.

La cola de envíos de las ofertas aprobadas a las redes de URUKU: el canal de WhatsApp, Facebook e Instagram.

![Difusión: la cola de envíos a las redes](/manuales/capturas/admin/29-difusion-desktop.webp)

- Arriba, cuántas esperan y el estado de cada red («sale solo», «a mano desde la tablet», «falta configurar»).
- Filtros: **«Todo»**, **«Esperando»**, **«Fallaron»**, **«Publicadas»**.
- Cada envío: **Publicada**, **Esperando**, **Falló** o **No corresponde**, con los intentos y **«ver el posteo»**.
- **«Publicar»** en una fila manda (o reintenta) ese envío. **«Publicar 10 que esperan»** manda los pendientes.

---

## Contenido › Reclamos

Permiso: `panel`. Muestra todas las ciudades.

![Reclamos de URUKU y consultas de Reservalo](/manuales/capturas/admin/30-reclamos-desktop.webp)

- **«Reclamos (URUKU)»**: lo que dejaron los compradores en **«¿Hay algún dato incorrecto?»** › **«Informar un problema»** de una ficha.
- **«Consultas y reclamos (Reservalo)»**: el formulario de contacto de la tienda.

**«Responder»** abre «Tu respuesta…» con **«Enviar»**. En los reclamos de URUKU la respuesta **se guarda pero no le llega a nadie**: si hay que avisarle a alguien, hacelo por WhatsApp. En las consultas de Reservalo, la respuesta se manda a Reservalo.

---

## Catálogo › Catálogo

Permiso del menú: `datos` (los datos piden `moderar`). Sólo para mirar.

Qué hay cargado y, sobre todo, qué falta.

![Catálogo: lo que falta en la ciudad](/manuales/capturas/admin/31-catalogo-desktop.webp)

- El resumen: comercios activos, rubros, **rubros sin comercios**, productos distintos y búsquedas sin resultado.
- **«Lo buscaron y no lo encontraron»**.
- **«Rubros»**, con cuántos comercios tiene cada uno; **«Ver sólo los vacíos»**.
- **«Subcategorías»** y **«Productos»**.

---

## Catálogo › Rubros

Permiso: `rubros`. No depende de la ciudad.

![Rubros: lo que pidió la IA y no existe](/manuales/capturas/admin/32-rubros-desktop.webp)

**«Categorías que la IA pidió y no existen»**: cada una con cuántas veces se pidió y **«Resolver»**:

- **«Es un rubro nuevo»**: nombre, identificador y si **no es un negocio** (baño, trámite, plaza). **«Crear rubro»** o **«Crear y aplicar a N»**.
- **«Es otra forma de decir uno que existe»**: elegí el rubro y **«Agregar como palabra»** (o «Agregar y aplicar a N»).
- **«Palabras que lo detectan»**, y la vista previa: a cuántos comercios alcanza y cuántos son nuevos.

**«Completar rubros»**: **«Analizar»** busca comercios a los que les falta un rubro según el diccionario; **«Aplicar»** pregunta y **sólo suma** rubros (nunca saca).

Los rubros no se renombran ni se borran desde el panel.

---

## Catálogo › Revisar rubros

Permiso del menú: `rubros` (ver la cola pide `moderar`). Muestra todas las ciudades.

Los comercios cuyo rubro principal **no coincide con lo que dice el diccionario** de URUKU. Una persona decide cada uno.

![Revisar rubros: la cola «No cierran»](/manuales/capturas/admin/33-revision-rubros-desktop.webp)

- Pestañas **«No cierran (N)»** y **«Sin datos (N)»** (los que no tienen texto para clasificar), y cuántos van revisados.
- Cada comercio: «Está en X · el diccionario dice Y», el texto que se usó y los rubros que ya tiene. Botones **«Está bien»**, **«→ (rubro sugerido)»** y **«Editar los rubros»**.
- **«Recalcular en tanda»**: **«Ver qué cambiaría · sólo el principal»** o **«Ver qué cambiaría · recalcular de cero»**, y después **«Aplicar los N»** / **«Reemplazar en N comercios»** (pide confirmación).

**«Editar los rubros»** abre «Rubros de …»: cómo va a quedar (con la estrella del principal), lo que deduce el sistema **por sus palabras**, lo que **propone la IA** (segunda opinión), todos los rubros con un filtro, y una **palabra para el diccionario**. Termina con **«Guardar el rubro»** o **«Ya estaba bien, no tocar»**.

![El editor «Rubros de …»](/manuales/capturas/admin/34-editar-rubros-desktop.webp)

---

## Campo › Cargas

Permiso: `equipo`. Se filtra por la ciudad.

**«Cargas del día»**: qué cargó cada agente, cuándo y por dónde anduvo.

### Historial

Los últimos 60 días: Fecha, Agente, Comercios, Desde–hasta, Trabajado y Km. Tocá una fila para abrir ese día y ese agente.

![Cargas: el historial](/manuales/capturas/admin/35-cargas-historial-desktop.webp)

### El día

Elegís la **Fecha** (o **«Hoy»**) y el **Agente**.

- **Resumen**: Comercios, Desde–hasta, Tiempo trabajado, Recorrido (en línea recta) y **Tramos** (un tramo se corta con una pausa de más de 30 minutos).
- **«Comercios por hora»**.
- **«El recorrido»**: el mapa con los comercios numerados en orden, unidos por una línea, un color por tramo. Tocá un punto para ver el nombre y la hora.
- **«Uno por uno»**: orden, hora, comercio y distancia desde el anterior, con la marca «subido más tarde (sin señal)».

![Cargas: el detalle de un día](/manuales/capturas/admin/36-cargas-dia-desktop.webp)

Antes del 6/10/2026 la hora es la de llegada al servidor, no la del celular. Los km son en línea recta entre comercio y comercio.

---

## Negocio › Planes

Permiso del menú: `planes` (ver la lista pide `moderar` o `pagos`). No depende de la ciudad.

Lo que se ve en uruku.bo/planes y lo que el sistema cobra.

![Planes: la tarjeta de cada plan](/manuales/capturas/admin/37-planes-desktop.webp)

Una tarjeta por plan, con sus funciones (redes, chatbot…). **Las funciones no se cambian desde acá**: las decide el sistema. Los planes ocultos se ven atenuados. Se editan:

- **Nombre**, **Precio/mes (Bs)**.
- **Publicaciones/mes** (vacío = sin límite) y **Publicaciones guardadas (máx.)** (vacío = sin tope).
- **Fotos del local (máximo)** (un número entre 0 y 1000) y **Extra (Bs c/u)**: el precio de cada foto o publicación extra.
- **Meses que puede publicar** (vacío = siempre).
- **Qué es, en una frase** y **Qué incluye** (una línea por viñeta).
- **«Cobra extras al pasarse (si no, se corta)»** y **«Se muestra en /planes»**.

Tocá **«Guardar»**.

Al llegar al máximo de publicaciones guardadas se archiva la más vieja. Al llegar al máximo de fotos, el comercio elige entre pagar una foto extra o borrar la más vieja. Si el pago vence, vale el máximo del plan gratis.

---

## Negocio › Suscripciones

Permiso: `pagos`. Se filtra por la ciudad.

Los comercios y el estado de su suscripción.

![Suscripciones: la lista con filtros](/manuales/capturas/admin/38-suscripciones-desktop.webp)

- **El buscador**: nombre, teléfono o código.
- **Los filtros**: **Todos**, **Interesados**, **Activo**, **De cortesía**, **Por vencer** (vence en 5 días o menos), **Vencido**, **Suspendido** y **Sin plan**.
- Cada fila: nombre, WhatsApp, si está verificado, el estado, el plan y cuándo vence.
- **«Interesado: (plan) · (agente) · (fecha)»**: un agente anotó en la calle que le interesa ese plan, y todavía no hay un pago confirmado después. Es para llamarlo.

### Los botones de cada fila

- **«Enviar mensaje al comercio»** (con `comercios.cuenta`): el mensaje le llega a la bandeja de Mi comercio.
- **«Confiable y números autorizados»** (con `comercios.cuenta`).
- **«Plan»**: elegir el plan o darlo de cortesía.
- **«+ Pago»**: registrar un pago.
- **«Suspender»** / **«Reactivar»**: no pide confirmación. Suspendido, el comercio sale de la búsqueda y pierde la estrella. Reactivar no devuelve a un comercio que el admin dio de baja en Negocios.

### Plan y cortesía

![Elegir el plan o darlo de cortesía](/manuales/capturas/admin/39-suscripciones-plan-desktop.webp)

**«Plan del comercio»**: elegí el plan y, si corresponde, tildá **«De cortesía (no paga, no vence)»**. Un comercio de cortesía tiene la estrella «Verificado por URUKU» y no aparece en cobros ni vencimientos. Sólo se da sobre un plan pago. El panel pide confirmación al darla y al quitarla. Tocá **«Guardar plan»**.

### Registrar un pago

![Registrar un pago](/manuales/capturas/admin/40-suscripciones-pago-desktop.webp)

**«Registrar pago»**: monto, moneda (BOB, ARS, USD), método (QR Bolivia, Efectivo, Transferencia), meses (1, 3, 6 o 12), comprobante y notas. **«Confirmar pago»**: la suscripción se extiende, se quita la suspensión y se le crea al comercio la cuenta para entrar a Mi comercio. Si hay algo que revisar con el dueño (por ejemplo, que no tiene un WhatsApp válido), el panel lo avisa.

### Confiable y números autorizados

![Código, confianza y números autorizados](/manuales/capturas/admin/41-suscripciones-confiable-desktop.webp)

- **Código del local** `URUKU-…`: escribiéndolo en un WhatsApp, sus ofertas caen en este comercio.
- **«Comercio confiable»**: lo que publique sale directo, sin moderación.
- **Rubros**: tocá para agregar o sacar; el primero es el principal.
- **Grupo de WhatsApp**: **«Crear el grupo de WhatsApp»**, o los pasos para crearlo a mano cuando WhatsApp está en sólo lectura. Para atar uno existente, pegá su identificador (termina en `@g.us`) y tocá **«Atar»**; **«Soltar»** lo desata.
- **Números que pueden publicar**: número, de quién es y **«Autorizar número»**. Lo que llegue de ese número cuenta como de este comercio. Si no hay ninguno, el panel avisa que un WhatsApp desde otro número va a crear un comercio duplicado.

---

## Negocio › Pagos

Permiso: `pagos`. Muestra todas las ciudades.

**«Pagos por confirmar»**: los comprobantes que subieron los comercios desde Mi comercio.

![Pagos por confirmar](/manuales/capturas/admin/42-pagos-desktop.webp)

1. Tocá la miniatura para ver el comprobante. Revisá que sea genuino y por el monto que corresponde.
2. Si hace falta, elegí el **Plan** (o «Sin cambiar el plan»). Elegir un plan le quita la cortesía.
3. Tocá **«Confirmar 1 mes»** o **«Confirmar 2 meses»** (no pide confirmación).

La suscripción queda al día hasta la nueva fecha y, si estaba suspendido, se reactiva.

---

## Negocio › Vencimientos

Permiso del menú: `moderar` (agregar y editar piden `pagos`). No depende de la ciudad.

Lo que vence de la infraestructura de URUKU, para renovar antes de que algo deje de andar. Las suscripciones de los comercios **no** están acá.

![Vencimientos y certificados](/manuales/capturas/admin/43-vencimientos-desktop.webp)

- **«+ Agregar»**: nombre, tipo (Dominio, Hosting / VPS, Servicio, Chip / SIM, Plan, Otro), fecha, **avisar días antes** (30 de entrada), proveedor y **qué se cae si esto vence**.
- Estados: **VENCIDO**, **vence ya** (7 días o menos), **por vencer**, **falta la fecha**, **al día**.
- **«Editar»** y **«Dejar de vigilar»** (pide confirmación).
- **«Certificados HTTPS»**: los de uruku.bo y sus servicios, medidos en vivo.

---

## Análisis › Monitoreo

Permiso: `datos` (algunos bloques piden además `moderar` o `panel`). Muestra todas las ciudades.

![Monitoreo](/manuales/capturas/admin/44-monitoreo-desktop.webp)

- **«Visitas al sitio»** (7, 30 o 90 días): páginas vistas, personas, fichas vistas y los que escribieron o llamaron; por día, las páginas más vistas, de dónde llegan y las llegadas por QR o enlace marcado.
- **«Altas por día»**: los últimos 60 días, con nombre, foto, WhatsApp y agentes.
- Tarjetas: negocios nuevos (7 días), ofertas activas, contactos (30 días), llegadas por QR (30 días), bajas y vencidos.
- **«No contestan el WhatsApp»**.
- **«Peso de las fotos»**: **«Medir»** y **«Reducir peso»** (avisa que el original se pierde y no se puede deshacer).
- **Comercios con más ofertas** y **más contactados**, y los datos de Reservalo cuando responde.

---

## Análisis › KPIs

Permiso: `datos`.

Elegí el período (**Hoy**, **Últimos 7**, **30** o **90 días**, **Último año**) y ves:

![KPIs](/manuales/capturas/admin/45-kpis-desktop.webp)

- **Comercios activos**, **Pagando** y **Gratis** (todos los que no pagan, incluidas las cortesías).
- **Más buscado**, con cuántos resultados da hoy.
- **Sigue sin resultado**.
- **Locales más visitados**.
- **Ya no son un hueco**: lo que antes no tenía resultado y ahora sí.

---

## Análisis › Demanda

Permiso del menú: `datos` (los datos piden `moderar`).

**«Qué busca la gente»**, por **7**, **30** o **90 días**, con **«↻ Actualizar»**. Sirve para saber qué comercios faltan.

![Demanda: qué busca la gente](/manuales/capturas/admin/46-demanda-desktop.webp)

- **«Para decirle a un comerciante»**: una frase lista con **«Copiar»**.
- **«No encontraron nada»**.
- **«Lo más buscado»**.

---

## Análisis › Compradores

Permiso: `datos`. No depende de la ciudad.

La base de compradores, importada desde **Excel o CSV**. Desde acá no se le escribe a nadie.

![Compradores: importar y resumen por grupo](/manuales/capturas/admin/47-compradores-desktop.webp)

1. **«Importar un Excel o CSV»** y elegí qué columna es el **Teléfono / WhatsApp**, el **Grupo**, la **Ciudad** y el **Nombre**, y el país de los números sin código (o un grupo fijo para todo el archivo).
2. Mirá la vista previa y tocá **«Importar N filas»**: «N nuevos · N ya estaban · N con número raro».

El resumen muestra Contactos, Grupos, **Ya usan URUKU** y Números raros; la tabla **«Por grupo»** trae **el enlace de cada grupo** (`uruku.bo/?ref=grupo-…`) con **«Copiar»**, para medir de dónde llegan; y **«Por ciudad»**.

---

## Equipo › Equipo

Permiso: `equipo`. Dos pestañas: **«Personas»** y **«Roles y permisos»**.

### Personas

![Equipo: agregar a alguien y la tabla del equipo](/manuales/capturas/admin/48-equipo-personas-desktop.webp)

**«Agregar a alguien»**: correo (con el que entra), contraseña (6 o más), nombre, **ciudad donde carga** (sólo para agentes) y uno o más **roles**. **«Crear»**. Después aparece **«Copiar para mandar por WhatsApp»**: la contraseña no se puede volver a ver.

**«El equipo»**: correo, nombre, roles, ciudad y último acceso. En cada fila se cambian los **roles** y la **ciudad** (se guardan al instante), una **clave nueva** con **«Cambiar»**, y **«Apagar» / «Encender»**. Una persona no se borra: se **apaga** y no puede entrar. El nombre y el correo no se cambian.

### Roles y permisos

![Roles y permisos](/manuales/capturas/admin/49-equipo-roles-desktop.webp)

Un rol es una lista de permisos. Vienen cuatro con el sistema, que no se borran:

| Rol | Qué puede |
|---|---|
| **Administrador** | Todo |
| **Moderador** | `moderar`, `comercios.editar`, `comercios.cuenta`, `ayuda`, `lugares`, `whatsapp`, `rubros` |
| **Publicador** | `contenido`, `moderar`, `comercios.editar` |
| **Agente de campo** | `comercios.cargar` (sólo la app de campo; no entra al panel) |

Con **«Nombre del rol nuevo»** y **«Crear rol»** armás otro, tildando permisos. Los tildes se guardan al instante. Los roles nuevos tienen **«Borrar»**.

Los permisos:

| Permiso | Qué abre |
|---|---|
| `moderar` | Aprobar o rechazar lo que mandan los comercios |
| `comercios.editar` | Editar la ficha de cualquier comercio |
| `comercios.cuenta` | Cambiar WhatsApp, confiable, números y grupos de un comercio |
| `comercios.cargar` | Cargar comercios desde la calle (app de campo) |
| `contenido` | Cotización, estado de la frontera, videos y redes |
| `ayuda` | Contestar preguntas y cargar el saber local |
| `lugares` | Mercados, galerías y puntos del mapa |
| `rubros` | Rubros, palabras y revisión de la clasificación |
| `difusion` | Publicar en las redes de URUKU |
| `whatsapp` | La bandeja de WhatsApp y los grupos |
| `planes` | Precios, cuotas y funciones de los planes |
| `pagos` | Registrar pagos, suscripciones y vencimientos |
| `datos` | KPIs, base de compradores y estadísticas |
| `equipo` | Crear usuarios, asignar roles y cambiar permisos |
| `panel` | El resto del panel (lo que no tiene permiso propio) |

---

## Equipo › Manuales

Sin permiso propio. Abrí el manual y tocá **«Guardar como PDF»** para mandarlo por WhatsApp.

![Manuales](/manuales/capturas/admin/50-manuales-desktop.webp)

- **Manual del agente**: uno por agente del equipo, con su nombre, su ciudad y su correo ya puestos (**«Abrir manual»**), y la **versión genérica**. La lista pide el permiso `equipo`.
- **Manual del admin**, **Manual del comerciante**, **Manual del comprador** y **Qué es URUKU**: **«Abrir»** y **«Copiar enlace»**. El del comerciante y el del comprador se pueden mandar tal cual por WhatsApp.

---

## Equipo › Ayuda

Permiso: `ayuda`.

Lo que sabe el asistente de URUKU (Dax) y las respuestas que cargan los comercios.

![Ayuda: preguntas y saber local](/manuales/capturas/admin/51-ayuda-desktop.webp)

**«Preguntas y saber local»**:

- **«Sin respuesta (N)»**: lo que preguntó la gente y Dax no supo. Escribí la respuesta y tocá **«Responder y guardar como saber local»**, o **«Descartar»**.
- **«Saber local (N)»**: lo que Dax tiene que saber. **«+ Agregar algo que el asistente tenga que saber»**; cada entrada con **«Editar»**, **«Apagar» / «Encender»** y **«Borrar»**.
- **«Ver las últimas 200 preguntas»**.

**«Respuestas de los locales»**: las respuestas que cargaron los comercios para su chatbot, con un buscador y el interruptor **Activa / Desactivada**. No se editan ni se borran desde acá.

---

## Fuera del panel: uruku.bo/contenido

Es una página aparte para el contenido del sitio. Se entra con la misma cuenta del panel y hace falta el permiso `contenido` (Administrador y Publicador).

![Contenido de la home](/manuales/capturas/admin/52-contenido-desktop.webp)

Bloques: **Cotizaciones** (carga diaria), **La frontera hoy**, **Clima**, **Recorrimos Bermejo (videos)**, **Novedades de URUKU** y **Redes sociales**.

### Videos promocionales

Escribí el título y tocá **«+ Video»** (hasta 100 MB). Se ven en el Inicio de Bermejo («Recorrimos …») y en la guía. La **X** lo borra (pide confirmación y no se recupera).

### Novedades de URUKU

Salen primero en «Novedades» del Inicio y en /novedades. Una novedad «de todas las ciudades» se ve en todas.

![Una novedad de URUKU: los datos y los medios](/manuales/capturas/admin/53-contenido-novedad-desktop.webp)

1. Tocá **«Nueva novedad»**: título, texto, fecha, ciudad (o **«Todas las ciudades»**), un enlace opcional y **«Destacada: sale antes que las demás»**.
2. Tocá **«Crear y seguir con las fotos»**.
3. Subí la **portada** (sin portada, la tarjeta sale con fondo verde), hasta **12 fotos** y un **video** (mp4, webm o mov, hasta 100 MB) con su póster.

Cada novedad tiene **«Editar»**, **«Dar de baja»** (deja de verse; se puede **«Reactivar»**).

---

## Farmacias de turno: importar el rol

El rol de turnos no se carga desde el panel: lo importa el equipo técnico con un archivo, por comando en el servidor:

`python -m app.scripts.importar_turnos_farmacia data/turnos_farmacia/<archivo>.json`

El archivo trae las farmacias (las que ya están en URUKU y las nuevas, con su dirección y teléfonos) y qué farmacias están de turno cada día. El turno va de 8:00 a 8:00 del día siguiente. Se puede correr las veces que haga falta sin duplicar nada; si algo del archivo no cierra, no cambia nada. Las farmacias nuevas cuyo punto sale de la dirección quedan con **ubicación aproximada**: el agente la confirma en la puerta con «Tomar el GPS acá».

El público lo ve en **«Farmacias de turno hoy»** del Inicio y en /farmacias-de-turno.

---

## Permisos: lo que hay que saber

En algunas secciones el permiso que muestra el menú no es el mismo que pide el sistema para los datos. Con el rol **Administrador** no pasa nada; con roles armados a mano puede pasar que alguien vea una sección y le dé error, o al revés:

| Sección | El menú pide | Además hace falta |
|---|---|---|
| Recepción | `whatsapp` | `moderar` para ver la bandeja |
| Difusión | `difusion` | `moderar` para ver la cola |
| Catálogo | `datos` | `moderar` |
| Revisar rubros | `rubros` | `moderar` para ver la cola |
| Planes | `planes` | `moderar` o `pagos` para ver la lista |
| Demanda | `datos` | `moderar` |
| Vencimientos | `moderar` | `pagos` para agregar o editar |
| Importados | `datos` | `panel` |
| Adornos | `lugares` | `panel` para guardar (al Moderador le falta) |
| Calles y horarios | `moderar` | `comercios.editar` para poner horarios en lote |

---

## Lo que hacés todos los días

### 1. Mirá «Para hacer hoy»

Entrá al Inicio. Arriba están los vencimientos y los pagos, después el resto.

### 2. Moderá las publicaciones

**«Publicaciones»**. Revisá que la foto se vea y que sea del comercio. Aprobá, pedí cambios o rechazá. Si hay muchas, **«Revisar todas con IA»** aprueba sola las seguras y te deja el resto.

### 3. Verificá comercios

**«Negocios»** › **«Pendientes»**. Revisá el número (podés escribirle) y tocá **«Verificar»** si el comercio existe. Si no estás seguro, dejalo sin verificar.

### 4. Cargá horarios por calle

**«Calles y horarios»**, abrí la calle, destildá los rubros que no van, elegí el horario y tocá **«Poner el horario a N comercios»**.

### 5. Confirmá pagos y mirá los interesados

**«Pagos»**: revisá cada comprobante y confirmá. En **«Suscripciones»** › **«Interesados»**, llamá a los que un agente anotó.

### 6. Resolvé los cambios de número

**«Cambios de número»**: compará la fachada y la ubicación y tocá **«Aprobar»** o **«Rechazar»**.

### 7. Mirá Recepción

Fijate que diga **«WhatsApp conectado»** y revisá **«Para mirar»**. Si un grupo o número tiene que contar para un comercio, atalo en Suscripciones.

### 8. Mirá cómo va el campo

**«Cargas»** para el día de cada agente y **«Calles y horarios»** › **«Mapa»** para ver lo recorrido.

---

## Si algo no anda

Escribile al equipo técnico por el WhatsApp de URUKU.
