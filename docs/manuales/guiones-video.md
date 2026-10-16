# Guiones de video — URUKU

Guiones de 1 a 2 minutos por perfil. Cada escena nombra la captura de
`docs/manuales/capturas.json` (`perfil/id`) que muestra esa pantalla: la ruta
y los pasos para llegar están ahí. Los textos entre «» son los de la pantalla,
tal cual. Todo lo que dice la voz está en el manual de ese perfil
(`frontend/content/manuales/*.md`) y respaldado en `docs/manuales/verificacion.md`.

---

## ADMINISTRADOR (manual del admin, capturas `admin/*`, computadora)

### Tema 1: El tablero diario (1:30)

**Escena 1** — `admin/01-ingreso`
- «Entrás a uruku.bo/admin con tu correo y tu contraseña.»

**Escena 2** — `admin/04-inicio`
- «Lo primero es el Inicio. Arriba, «Para hacer hoy»: vencimientos, pagos, publicaciones, reclamos, cambios de número… Cada fila tiene su botón que te lleva a la sección.»
- «Si no hay nada pendiente, dice «Todo al día».»

**Escena 3** — `admin/05-inicio-graficos`
- «Más abajo, los gráficos: altas por día, visitas y contactos, fichas completas y comercios por ciudad.»

**Escena 4** — `admin/03-ciudad`
- «Arriba elegís la ciudad. Las secciones que no dependen de la ciudad lo dicen debajo de la barra.»

### Tema 2: Verificar y editar negocios (2:00)

**Escena 1** — `admin/06-negocios-lista`
- «Comercios › Negocios. El resumen por ciudad, el buscador y los filtros: Todos, Pendientes, Verificados, Incompletos y Sin horario.»

**Escena 2** — `admin/07-negocios-incompletos`
- «En Incompletos, cada fila dice qué le falta: nombre, foto, contacto, rubro o productos.»

**Escena 3** — `admin/09-editar-negocio`
- «El lápiz abre «Editar negocio». Con las flechas pasás al siguiente sin cerrar.»

**Escena 4** — `admin/10-editar-fotos`
- «La galería: «Usar como portada» cambia la foto principal, y la anterior queda en la galería.»

**Escena 5** — `admin/11-editar-lo-que-suma`
- «En «Lo que suma»: pasero, envíos, factura, talles especiales, pedido mínimo, el canal y el catálogo.»

**Escena 6** — `admin/06-negocios-lista`
- ««Verificar» aparece en los pendientes. Tocalo cuando sabés que el comercio existe: no se deshace.»

### Tema 3: Clave, baja y reactivar (1:30)

**Escena 1** — `admin/12-generar-clave`
- «Si el dueño perdió la clave: «Generar clave nueva», «Sí, generar clave nueva». Se muestra una sola vez, con «Copiar».»

**Escena 2** — `admin/14-dar-de-baja`
- ««Dar de baja» lo saca del sitio. No se borra.»

**Escena 3** — `admin/15-dados-de-baja`
- «En «Dados de baja» está la lista, y «Reactivar» lo vuelve a mostrar.»

### Tema 4: Publicaciones (1:50)

**Escena 1** — `admin/25-publicaciones-pendientes`
- «Contenido › Publicaciones. En «Pendientes» está lo que mandaron los comercios que no son confiables.»
- «Aprobar, Solicitar cambios o Rechazar. El tipo se corrige con el selector.»

**Escena 2** — `admin/26-publicaciones-ia`
- ««Revisar con IA» sólo sugiere: no aprueba nada.»
- ««Revisar todas con IA» aprueba solas las que la IA marca con 80 % o más. El resto queda para vos.»

**Escena 3** — `admin/27-publicaciones-bajar`
- «En «Publicadas», «Bajar» saca una publicación del sitio. El motivo es obligatorio.»

### Tema 5: Calles y horarios (1:45)

**Escena 1** — `admin/16-calles-horarios` y `admin/17-calles-horario-calle`
- «Abrís una calle, destildás los rubros que no van, elegís el horario y tocás «Poner el horario a N comercios».»

**Escena 2** — `admin/18-calles-zonas`
- «En «Mapa», las zonas: cuanto más verde, más recorrido.»

**Escena 3** — `admin/19-calles-mapa`
- «En «Calles», el color de cada calle: naranja «Seguir por acá», verde recorrida, ámbar parcial, gris pendiente.»

**Escena 4** — `admin/20-calles-ficha`
- «Tocás una calle y la marcás: Recorrida, Sin comercios o Pendiente.»

### Tema 6: Cobrar (2:00)

**Escena 1** — `admin/38-suscripciones`
- «Negocio › Suscripciones. Filtrá «Interesados»: son los que un agente anotó en la calle.»

**Escena 2** — `admin/39-suscripciones-plan`
- ««Plan» elige el plan o lo da de cortesía: no paga, no vence y tiene la estrella.»

**Escena 3** — `admin/40-suscripciones-pago`
- ««+ Pago» registra un pago a mano y le crea al comercio su cuenta de Mi comercio.»

**Escena 4** — `admin/42-pagos`
- «En Pagos están los comprobantes que subieron los comercios: «Confirmar 1 mes» o «Confirmar 2 meses».»

### Tema 7: Cargas de los agentes (1:30)

**Escena 1** — `admin/35-cargas-historial`
- «Campo › Cargas. El historial: fecha, agente, comercios, horario, tiempo trabajado y kilómetros.»

**Escena 2** — `admin/36-cargas-dia`
- «Tocás una fila y ves el día: el recorrido en el mapa, comercios por hora y uno por uno.»

### Tema 8: El equipo y los manuales (1:30)

**Escena 1** — `admin/48-equipo-personas`
- «Equipo › Personas: «Agregar a alguien». Una persona no se borra: se apaga.»

**Escena 2** — `admin/49-equipo-roles`
- «Roles y permisos: los cuatro del sistema y los que armes vos.»

**Escena 3** — `admin/50-manuales`
- «En Manuales, el del agente sale con su nombre. Los demás se mandan con «Copiar enlace».»

---

## COMPRADOR (manual del comprador, capturas `comprador/*`, celular)

### Tema 1: Buscar (1:50)

**Escena 1** — `comprador/02-inicio`
- «Abrís uruku.bo. No hace falta descargar nada ni tener cuenta.»

**Escena 2** — `comprador/04-buscar-resultados`
- «Escribís lo que buscás y tocás Buscar. Cada comercio dice si está abierto, qué vende y si responde por WhatsApp.»

**Escena 3** — `comprador/06-cerca-de-mi`
- ««Cerca de mí» te muestra primero lo abierto y lo más cerca. Pide tu ubicación.»

**Escena 4** — `comprador/07-mapa`
- «En el mapa, cada comercio es un pin del color de su rubro. Tocás uno y le escribís o vas.»

### Tema 2: La ficha del comercio (2:00)

**Escena 1** — `comprador/08-ficha`
- «La ficha: la foto, el horario —«Abierto ahora», «Cerrado hoy · abre mañana»—, lo que suma y los botones de WhatsApp y Cómo llegar.»

**Escena 2** — `comprador/09-ficha-fotos`
- «En «Fotos del local» están sus ofertas y novedades, con sus filtros.»

**Escena 3** — `comprador/10-ficha-oferta`
- «Abrís una oferta y tenés «Reservar» y «Consultar».»

**Escena 4** — `comprador/11-ficha-informacion`
- «Abajo, toda la información, y «¿Hay algún dato incorrecto?» para avisarnos.»

### Tema 3: Reservar sin cuenta (1:20)

**Escena 1** — `comprador/10-ficha-oferta`
- «Tocás «Reservar» en una oferta.»

**Escena 2** — `comprador/15-reservas`
- «En «Tu reserva» tocás «Enviar reserva por WhatsApp». Queda apartado cuando el vendedor te contesta que sí.»

### Tema 4: Para el que viene a Bermejo (1:45)

**Escena 1** — `comprador/02-inicio`
- «En el Inicio, el estado del paso, el clima y el cambio del día.»

**Escena 2** — `comprador/19-turno-inicio` y `comprador/20-farmacias-turno`
- «Farmacias de turno hoy: cuál atiende las 24 horas, con Llamar y Cómo llegar.»

**Escena 3** — `comprador/21-guia`
- «La guía: cruzar, documentos, aduana, comprar, seguridad.»

**Escena 4** — `comprador/22-cambio`
- «La calculadora de cambio, con la cotización que te ofrecen.»

### Tema 5: Tu cuenta y tus guardados (1:30)

**Escena 1** — `comprador/23-entrar`
- «La primera vez confirmás con tu WhatsApp: tocás «Confirmar por WhatsApp» y enviás el mensaje.»

**Escena 2** — `comprador/24-perfil`
- «Con tu cuenta, desde Mi perfil ves tus locales guardados.»

**Escena 3** — `comprador/25-guardados`
- «Tus locales guardados, en cualquier teléfono donde entres.»

---

## VENDEDOR (manual del comerciante, capturas `vendedor/*`, celular)

### Tema 1: Entrar a tu negocio (1:45)

**Escena 1** — `vendedor/01-ingreso`
- «Entrás a uruku.bo/mi-comercio con tu celular y tu clave, que es una palabra de tu negocio y seis letras y números.»

**Escena 2** — `vendedor/02-ingreso-whatsapp`
- «¿Primera vez o te olvidaste la clave? Escribís tu celular, «Continuar» y «Confirmar por WhatsApp».»

**Escena 3** — `vendedor/03-clave-nueva`
- «Te aparece tu clave nueva una sola vez. Guardala y tocá «Ya la guardé».»

### Tema 2: Tu ficha al día (2:00)

**Escena 1** — `vendedor/04-mi-negocio`
- «Mi negocio: tus datos, tu clave, tu actividad y tu suscripción.»

**Escena 2** — `vendedor/07-editar-informacion`
- ««Editar información»: categoría, ubicación, contacto, horario y redes.»

**Escena 3** — `vendedor/08-lo-que-suma`
- ««Lo que suma a tu negocio»: pasero, envíos, factura, talles especiales, el catálogo en PDF y el canal.»

**Escena 4** — `vendedor/09-cambie-de-numero`
- «Si cambiaste de número: «Cambié de número», tu ubicación y una foto del local. URUKU lo revisa.»

### Tema 3: Fotos (1:30)

**Escena 1** — `vendedor/10-fotos-videos`
- «La foto principal y la galería. «Usar como portada» pasa una foto a la principal.»

**Escena 2** — `vendedor/11-tope-fotos`
- «Si llegás al tope de tu plan, elegís: pagar una foto extra o borrar la más vieja.»

### Tema 4: Publicar ofertas (2:00)

**Escena 1** — `vendedor/14-asistente`
- ««Nueva oferta» abre el asistente: una oferta, un video o una novedad.»

**Escena 2** — `vendedor/15-asistente-confirmar`
- «Si sos confiable sale en vivo; si no, va a moderación.»

**Escena 3** — `vendedor/12-mis-ofertas`
- «En Mis ofertas ves el estado: En vivo, En revisión, Pide cambios o Rechazada.»

**Escena 4** — (sin captura: pantalla de WhatsApp)
- «También podés mandar la foto y el precio por WhatsApp desde tu número registrado.»

### Tema 5: Tu suscripción (1:30)

**Escena 1** — `vendedor/05-aviso-pago`
- «Si se vence, te avisa arriba con «Pagar ahora».»

**Escena 2** — `vendedor/19-suscripcion`
- ««Consultá el monto y cómo pagar» te abre un WhatsApp con URUKU. Después subís la foto del comprobante y «Enviar comprobante».»

### Tema 6: Tu chatbot (1:15)

**Escena 1** — `vendedor/18-mensajes-chatbot`
- «En Mensajes, lo que te preguntaron y el chatbot no supo. Respondés una vez y desde ahí contesta solo.»

---

## AGENTE (manual del agente, capturas `agente/*`, celular)

### Tema 1: Qué hay acá (1:50)

**Escena 1** — `agente/02-que-hay-aca`
- «Al abrir la app, «Qué hay acá»: los locales ya cargados a menos de 150 metros.»
- «Si el de enfrente está, lo completás. Si no, «Cargar un local nuevo acá».»

**Escena 2** — `agente/03-ficha-local`
- «La ficha te dice qué le falta y tiene el botón «Completar».»

**Escena 3** — `agente/04-ubicacion-aproximada`
- «Si dice «Ubicación aproximada», parate en la puerta y tocá «Tomar el GPS acá».»

### Tema 2: Cargar un comercio (2:15)

**Escena 1** — `agente/07-alta-formulario`
- «En la puerta: nombre del cartel, ubicación y foto. Sólo la ubicación es obligatoria.»

**Escena 2** — `agente/08-ya-cargados-cerca`
- «Si ya está cargado a menos de 40 metros, tocás «Es este».»

**Escena 3** — `agente/09-alta-guardada`
- «Al guardar aparece la clave del dueño, una sola vez. Anotala a mano y dásela en un papel. Nunca por WhatsApp.»

**Escena 4** — `agente/10-completar-le-falta`
- «En «Completar comercio», la lista «Le falta» te lleva a cada campo.»

**Escena 5** — `agente/13-completar-lo-que-suma`
- «Y lo que suma: pasero, envíos, factura, talles especiales.»

### Tema 3: Por dónde seguir (1:40)

**Escena 1** — `agente/05-mapa-calles`
- «Prendé «Calles». Naranja es «Seguir por acá»: la cuadra que sigue a una recorrida.»
- «Verde recorrida, ámbar parcial, gris pendiente.»

**Escena 2** — `agente/06-ficha-calle`
- «Al terminar una cuadra la marcás: Recorrida, Sin comercios o Pendiente.»

### Tema 4: Ofrecer (1:20)

**Escena 1** — `agente/14-ofrecer`
- «Mostrale al dueño cómo se ven otros, y mandale su ficha por WhatsApp.»

**Escena 2** — `agente/15-interes-anotado`
- «Si le interesa un plan, lo anotás. No se cobra nada: el admin lo ve en Suscripciones y lo llama.»

### Tema 5: Sin señal y la lista de la ciudad (1:30)

**Escena 1** — `agente/19-sin-conexion`
- «Sin señal, el alta queda en el celular. Se sube con «Sincronizar» o «Ver y subir».»

**Escena 2** — `agente/16-comercios-mi-ciudad` y `agente/17-sin-horario`
- «En «Mis comercios», el filtro «Sin horario» los ordena por distancia para completarlos caminando.»

---

## Notas para la grabación

1. **Pantalla**: el admin en computadora (1280 px de ancho); comprador, vendedor y agente en celular (390 × 844).
2. **Datos**: grabar sobre la demo local (`scripts/demo/demo.py up`), nunca sobre producción: varios pasos escriben en la base (generar clave, marcar calles, anotar interés).
3. **Cuadros del navegador**: «Dar de baja», «Reactivar», «Solicitar cambios» y «Rechazar» abren un cuadro propio del navegador que la captura no muestra; en el video se ve.
4. **Duración**: indicativa. Voz clara, rioplatense, sin tecnicismos. Subtítulos en español.
5. **Sin emoji** en placas ni subtítulos (la marca usa sus propios íconos).
