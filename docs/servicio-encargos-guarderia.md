# Encargos y guardería de URUKU: spec funcional (v1, 20/10/2026)

> **Estado:** spec funcional para validar con el dueño. No hay código. Lo legal es **borrador para abogado/despachante**.
> **Decisión de origen (dueño, 20/10/2026):** URUKU, como empresa, compra por encargo en comercios de Bermejo y guarda paquetes hasta que el cliente los retira. Garantía = **custodia**. Precios: los carga el admin y no se muestran al público hasta activarlos.
> Supuestos numerados **S-01…**; preguntas al dueño en §12.

## 0. En una pantalla

Un cliente de Aguas Blancas, Orán, Salta u otra ciudad pide en `uruku.bo/encargos` (o escribiendo al **67671888**) lo que quiere comprar en Bermejo. Un operador le confirma por WhatsApp los productos, el precio estimado y el anticipo. El cliente paga el anticipo; el admin lo registra a mano. El operador compra, saca foto del producto y del comprobante, y lo ingresa al **depósito** como paquete (código, foto, valor declarado, estante). El cliente sigue todo por un **link privado** y viene a Bermejo a retirarlo con su **código de retiro + documento**. También puede dejar en guardería compras que hizo él mismo. Si algo guardado se pierde o se daña, URUKU **repone o devuelve el valor declarado**. URUKU **no cruza mercadería**: se entrega siempre en Bermejo.

**Esto no es ecommerce:** el comercio no vende por URUKU ni hay carrito de comercios. URUKU es un cliente más del comercio, que compra por cuenta de otra persona.

## 1. Alcance

### MVP (primer incremento)
- Página pública `/encargos`: cómo funciona, garantía de custodia, qué no cubre, formulario. Sin precios mientras estén ocultos. Sin conteos de comercios.
- Encargo por formulario web **o** cargado por el operador cuando entra por WhatsApp.
- **Retiro de compras ya pagadas** (pedido del dueño, 20/10): el cliente compró y pagó en un comercio (en persona o por WhatsApp con el comercio) y URUKU pasa a buscar la compra y la guarda. Es un encargo de tipo `pickup`: sin anticipo de productos (ya están pagos), con comprobante del comercio como prueba de pago y foto al retirarla; después sigue igual desde (d). La tarjeta de la portada lo ofrece así: «Retiramos o hacemos tus compras · Te las guardamos en la guardería URUKU».
- Cotización, anticipo **registrado a mano por el admin** (con comprobante), compra con foto + comprobante del comercio.
- Depósito: ingreso de paquetes (de encargos y de clientes que traen sus compras), ubicación, vencimientos.
- Retiro con código de retiro + documento; persona autorizada.
- Seguimiento del cliente por link con token, sin cuenta.
- Reclamos de custodia.
- Precios del servicio editables en el admin, con flag de visibilidad pública.
- Avisos al cliente **a mano**: botón `wa.me` prellenado que abre el WhatsApp del 67671888 (nada automático).
- Roles nuevos en el panel: operador de encargos y operador de depósito.

### Segunda etapa
- Avisos automáticos por la **Marca 67991916 con API oficial** (plantillas *utility*), reusando el adaptador de `docs/cobro-mensual.md` (§2.2 T3).
- QR de cobro y página de pago con comprobante (mismo patrón que `/pagar/<token>` de cobro mensual).
- «Mis encargos» en `/perfil` para quien tiene cuenta de comprador con el mismo número verificado (`CONFIRMAR`).
- Botón «Pedilo por encargo» en ofertas y fichas (precarga producto y comercio).
- Etiquetas impresas con QR; inventario con lector.
- Seguro contratado sobre bienes de terceros (dependencia externa).

### Fuera de alcance (excluido, se dice en la página)
- **Envíos o traslados** a Argentina u otro lugar. URUKU **no cruza mercadería** ni contrata a quien la cruce.
- Trámites aduaneros, despachantes o pago de franquicias por el cliente.
- Garantía del **producto** (fallas, talle, modelo, precio): sigue siendo entre cliente y comercio.
- Perecederos, refrigerados, animales, medicamentos, líquidos inflamables, dinero, documentos, armas y todo lo prohibido en Términos §5.
- Compras en comercios fuera de Bermejo (S-01).
- Cantidades comerciales (reventa): se rechazan (S-02).
- Checkout o pagos online de comercios.

## 2. Canal de entrada: qué número usar

| Número | ¿Sirve para encargos? | Por qué |
|---|---|---|
| Registrador 64610187 (WAHA) | **No** | WAHA sólo lee y nunca escribe a un comprador (decisión 6/10). Un encargo necesita conversación |
| Marca 67991916 | **Segunda etapa** | Es el número público futuro, pero va **sólo** por API oficial (no registrarle WhatsApp común) y hoy la Cloud API no anda (`cobro-mensual.md` §1) |
| **67671888** | **Sí, MVP** | Ya es «el número de las personas» en Términos §9 y Privacidad §1; lo atiende alguien con la app de verdad |

**Recomendación:** MVP con **formulario web + 67671888**. El formulario termina con un botón `wa.me/59167671888?text=Hola, mi encargo es ENC-XXXX`: así el cliente **escribe primero** (opt-in y número confirmado de hecho) y el operador ya tiene el código. Si alguien escribe directo sin formulario, el operador carga el encargo en el panel.

**Decidido (19/10):** el 67671888 es el número **público** de URUKU para personas desde el 7/10 y **no** se conecta a WAHA (`docs/grupos-por-comercio.md`). Los encargos los atiende una persona desde ese número; los chats no entran a `wa_inbox`. El respaldo callado de los grupos es el 68727584 (Respaldo 2), que hay que activar. Ver P-08.

## 3. Flujos paso a paso

### (a) El cliente pide
1. Entra a `/encargos` (desde el sitio, un QR o un link). Lee cómo funciona y la garantía.
2. Completa: nombre, WhatsApp con prefijo (+54 / +591), ciudad, lista de productos (texto libre por renglón: qué, comercio si lo sabe, cantidad, precio máximo que acepta), fecha estimada en que viene a Bermejo, y tilda «Acepto las condiciones del servicio».
3. Recibe el código **ENC-XXXX** y su **link de seguimiento** («guardalo: es tu acceso»), más el botón para escribir al 67671888.
4. El encargo queda `requested` en el panel.
- **Por WhatsApp sin formulario:** el operador lo carga con los mismos campos y le manda el link por `wa.me`.

### (b) URUKU confirma y cobra el anticipo
1. El operador revisa disponibilidad (llama o va al comercio) y arma la **cotización**: por ítem, comercio, precio estimado y foto si la tiene; más la tarifa del servicio (S-03).
2. Pasa el encargo a `quoted` y le manda al cliente el resumen por `wa.me` (el link muestra lo mismo).
3. El cliente **aprueba** (respondiendo por WhatsApp; el operador marca «aprobado por el cliente» con fecha) y paga el **anticipo = 100 % del valor estimado de los productos** (S-04). La tarifa del servicio y el guardado se pagan al retirar.
4. El **admin** registra el pago a mano: monto, moneda, medio (transferencia / efectivo en oficina), referencia y foto del comprobante. Encargo → `paid`. **El operador que compra no cobra** (como «el agente nunca cobra» de los planes).
5. Si el cliente no paga en **72 h**, el encargo pasa a `expired` (S-05).

### (c) URUKU compra (o retira, si el encargo es `pickup`)

En un `pickup` no se compra: el operador va al comercio con el comprobante que mandó el cliente, verifica que el pedido esté pagado y completo, saca foto del paquete y del comprobante, y pasa a (d). Si el comercio no lo tiene listo o falta algo, se avisa al cliente y el encargo queda `waiting_store`.

1. Compra el operador de encargos, en el comercio, con fondos de la **caja de compras** de URUKU (no con su plata).
2. Antes de pagar al comercio, si el producto no coincide con la cotización o el precio supera el estimado en **más del 10 %**, consulta al cliente por WhatsApp y espera respuesta (S-06). Si no hay stock: ítem `unavailable`, se ofrece reemplazo o se devuelve esa parte del anticipo.
3. Registra por ítem: precio real, **foto del producto**, **foto del comprobante/factura del comercio**. Factura a nombre del cliente si dio NIT/CI; si no, sin nombre (S-07).
4. Con todo comprado → `purchased`. La diferencia (a favor o en contra) queda calculada para el retiro.

### (d) Ingreso a guardería
Vale para encargos y para **clientes que traen sus compras** (en ese caso el operador crea el cliente en el momento, sin encargo).
1. El operador de depósito arma el paquete: bolsa o caja **cerrada con precinto numerado** frente al cliente (si está presente).
2. Carga: código **PKG-XXXX** (lo da el sistema), foto del contenido y del paquete cerrado, descripción, **valor declarado** (encargo: lo pagado según comprobante; traído por el cliente: lo que declara, con su comprobante si lo tiene), ubicación (estante-caja), fecha de ingreso.
3. Escribe el PKG-XXXX en el paquete (MVP; impreso en segunda etapa).
4. El sistema genera el **código de retiro** (6 dígitos, se ve en el link del cliente) y calcula el fin del guardado gratis.
5. Si el valor declarado supera el **tope por paquete**, no se recibe o se divide (S-08). Si el contenido está en la lista de excluidos, no se recibe.

### (e) Aviso al cliente
- MVP: en cada cambio importante (cotizado, comprado, guardado, por vencer, vencido) el panel muestra un botón **«Avisar por WhatsApp»** que abre `wa.me` desde el 67671888 con el texto y el link. El operador lo manda y queda registrado «avisado» con fecha (no se puede saber si lo leyó).
- Segunda etapa: plantillas automáticas desde la Marca.

### (f) Retiro
1. El cliente llega con su **código de retiro** y su **documento** (DNI, CI o pasaporte).
2. El operador busca por código, nombre o PKG; el sistema muestra los paquetes, la ubicación y **el saldo a pagar** (diferencia de compra + tarifa + días de guardado si corresponde).
3. Verifica: código correcto **y** el número de documento que tipea coincide con el registrado (el sistema compara; ver §11) **y** el nombre coincide con el documento.
4. Cobra el saldo (efectivo o transferencia con comprobante); lo registra.
5. El cliente revisa el paquete con el precinto **delante del operador** y confirma «recibí conforme» (tilde en la tablet + nombre; foto opcional del retiro). Paquete → `picked_up`. Con todos los paquetes retirados, el encargo → `delivered`.
- **Retira otra persona:** sólo si el cliente la autorizó **antes** desde su link (nombre + documento). En el mostrador vale igual: código + documento del autorizado.
- **3 códigos mal** seguidos para el mismo paquete → se bloquea el retiro y avisa al admin.

### (g) Vencimiento del guardado
- **Días gratis:** 7 corridos desde el ingreso (S-09); después se cobra por día (precio a definir, oculto al público).
- Aviso manual 2 días antes de vencer el gratis y al vencer (paquete → `overdue`, sigue guardado).
- **Abandono:** a los **90 días** del ingreso sin retiro, y tras 3 avisos registrados (días 7, 30 y 75), el paquete pasa a `abandoned`. El admin decide: donar, vender para cubrir lo adeudado, o esperar. El sobrante de una venta queda a favor del cliente 12 meses (S-10, **validar con abogado**).
- El anticipo de un encargo no retirado cubre primero lo adeudado por guardado.

### (h) Reclamo de garantía de custodia
1. Lo abre el operador (al retirar, si el cliente ve un daño) o el admin (si un paquete no aparece). El cliente también puede pedirlo por el 67671888.
2. Se registra: paquete, tipo (`lost` / `damaged`), descripción, fotos del momento, foto del ingreso como comparación.
3. **Plazos:** daño visible → se reclama **en el retiro**, antes de firmar «recibí conforme». Pérdida → hasta 30 días después de que el paquete debió estar disponible.
4. Admin resuelve en **10 días hábiles**: `approved` (repone el mismo producto o devuelve el valor declarado, lo que elija URUKU con acuerdo del cliente) o `rejected` (con motivo: precinto intacto y foto de ingreso igual, falla de fábrica, excluido).
5. Pago registrado → `paid`. El paquete perdido queda `lost`.

## 4. Estados

### Encargo (`orders.status`)
```
requested ──cotiza──> quoted ──cliente aprueba + admin registra anticipo──> paid
    │                   │                                                    │
    │                   └──72 h sin pago──> expired                          ├──compra todo──> purchased ──paquetes retirados──> delivered
    └──rechazo (prohibido, comercial, fuera de Bermejo)──> rejected          └──nada disponible──> cancelled (devuelve anticipo)
Desde requested/quoted/paid: cancelled (a pedido del cliente; si ya pagó, se devuelve lo no gastado)
```
Ítem (`order_items.status`): `pending` → `bought` | `unavailable` | `replaced`.

### Paquete (`packages.status`)
```
stored ──vence el gratis──> overdue ──90 días──> abandoned ──> disposed
  │                           │
  └──────retiro──────────────┴──> picked_up
stored/overdue ──no aparece──> lost   (siempre con reclamo)
```
Daño = reclamo sobre el paquete, no un estado del paquete.

### Reclamo (`custody_claims.status`)
`open` → `approved` → `paid` · `open` → `rejected`.

## 5. Historias de usuario

**HU-01 · Cliente pide un encargo.** Como cliente de Orán, quiero pedir productos de Bermejo desde mi casa para no viajar dos veces.
- [ ] Given el formulario completo con la casilla tildada, When envío, Then veo ENC-XXXX, el link de seguimiento y el botón al 67671888.
- [ ] Sin la casilla, o sin WhatsApp válido, o sin al menos un producto, no se envía y el error dice qué falta.
- [ ] Más de 3 envíos por hora desde el mismo número/navegador → «Probá más tarde».
- [ ] La página no muestra precios si el flag está apagado ni cantidad de comercios.

**HU-02 · Cliente sigue su encargo.** Como cliente, quiero ver en qué está mi encargo sin crear cuenta.
- [ ] Con el link válido veo estado, ítems, precios reales, fotos del producto, saldo, días de guardado gratis restantes y el código de retiro.
- [ ] Con un token inválido veo «Link no válido» sin ningún dato.
- [ ] No veo fotos del comprobante del comercio ni datos del operador.

**HU-03 · Cliente autoriza a otra persona.** Como cliente, quiero que retire mi hermana.
- [ ] Desde el link cargo nombre y documento del autorizado; el operador lo ve en el retiro.
- [ ] Puedo quitar la autorización mientras el paquete no se retiró.

**HU-04 · Operador cotiza.** Como operador de encargos, quiero armar la cotización por ítem para que el cliente apruebe antes de pagar.
- [ ] No puedo pasar a `quoted` sin precio estimado en cada ítem.
- [ ] El botón «Avisar por WhatsApp» arma el texto con el total, el anticipo y el link.
- [ ] Puedo rechazar con motivo (prohibido / comercial / fuera de Bermejo); el cliente lo ve en el link.

**HU-05 · Admin registra el anticipo.** Como admin, quiero registrar el pago con su comprobante para que el operador pueda comprar.
- [ ] Sin foto de comprobante o sin referencia, transferencia no se guarda; efectivo pide el nombre de quien recibió.
- [ ] Sólo el rol con `servicios.pagos` ve este botón; el operador de encargos no.
- [ ] Al guardar, el encargo pasa a `paid` y queda en la lista «para comprar».

**HU-06 · Operador compra.** Como operador, quiero registrar cada compra con fotos para tener prueba ante el cliente.
- [ ] Un ítem no pasa a `bought` sin precio real, foto del producto y foto del comprobante.
- [ ] Si el precio real supera el estimado en más del 10 %, el sistema pide marcar «el cliente aceptó» con fecha.
- [ ] La caja de compras muestra, por día, anticipos recibidos vs. gastado.

**HU-07 · Depósito ingresa un paquete.** Como operador de depósito, quiero ingresar un paquete para saber siempre dónde está.
- [ ] No se guarda sin foto del contenido, foto cerrado, valor declarado, ubicación y número de precinto.
- [ ] Valor declarado por encima del tope → bloquea con mensaje.
- [ ] Para un cliente sin encargo, se crea en el mismo formulario (nombre, WhatsApp, documento).
- [ ] Al guardar se generan PKG-XXXX, código de retiro y fecha de fin del gratis.

**HU-08 · Depósito entrega.** Como operador de depósito, quiero verificar identidad antes de entregar para no darle el paquete a otro.
- [ ] Sin código correcto y documento coincidente, el botón «Entregar» no se habilita.
- [ ] Con saldo pendiente, no se entrega hasta registrar el cobro.
- [ ] Tras 3 códigos mal, el paquete queda bloqueado hasta que un admin lo libere.
- [ ] El retiro guarda operador, hora, quién retiró (titular o autorizado) y «recibí conforme».

**HU-09 · Admin ve vencimientos.** Como admin, quiero la lista de paquetes por vencer y vencidos para avisar a tiempo.
- [ ] Filtros: vence en 2 días, `overdue`, a punto de `abandoned` (>75 días).
- [ ] Cada fila muestra cuántos avisos se registraron y el botón `wa.me`.

**HU-10 · Admin resuelve un reclamo.** Como admin, quiero resolver reclamos con evidencia para pagar sólo lo que corresponde.
- [ ] El reclamo muestra lado a lado foto de ingreso y fotos del reclamo.
- [ ] `approved` exige monto ≤ valor declarado; `rejected` exige motivo.
- [ ] Reclamo por daño sin registrarse antes del «recibí conforme» → el sistema avisa «fuera de plazo».

**HU-11 · Admin define precios.** Como admin, quiero cargar las tarifas y decidir cuándo se ven.
- [ ] Con «Mostrar precios al público» apagado, `/encargos` y su API **no devuelven** ningún precio.
- [ ] Las cotizaciones individuales sí usan las tarifas cargadas (el cliente ve **su** precio).
- [ ] El cambio de tarifa no altera encargos ya cotizados (se guarda una copia en la cotización).

**HU-12 · Admin apaga el servicio.** Como admin, quiero pausar los encargos (vacaciones, depósito lleno).
- [ ] Con el servicio pausado, `/encargos` explica que no se toman pedidos y no muestra el formulario; la guardería de lo ya guardado sigue.

## 6. Pantallas (wireframes)

### 6.1 Pública `/encargos`
```
+----------------------------------------------------------+
| URUKU · Encargos y guardería en Bermejo                  |
| Comprá en Bermejo sin estar acá. Te lo compramos y lo    |
| guardamos hasta que vengas.                              |
| [Hacer un encargo]   [Escribinos al 67671888]            |
|----------------------------------------------------------|
| Cómo funciona  1 Pedís  2 Te confirmamos precio  3 Pagás |
|                el anticipo  4 Compramos y guardamos      |
|                5 Retirás con tu código y documento       |
|----------------------------------------------------------|
| Garantía de custodia: si algo que guardamos se pierde o  |
| se daña, lo reponemos o te devolvemos el valor declarado.|
| No cubre: fallas del producto, modelo o talle, precios.  |
|----------------------------------------------------------|
| Importante: entregamos sólo en Bermejo. No cruzamos      |
| mercadería. Aduana y franquicias son tuyas. [Leer más]   |
|----------------------------------------------------------|
| Tarifas: (flag apagado) «Te las confirmamos antes de     |
|  comprar, sin compromiso» / (prendido) tabla de tarifas  |
| Preguntas frecuentes · Condiciones del servicio          |
+----------------------------------------------------------+
Servicio pausado: se oculta el formulario y se muestra «Por ahora no tomamos encargos».
```

### 6.2 Formulario de encargo
```
Nombre [________]  WhatsApp [+54 v][__________]  Ciudad [________]
Qué querés (uno por renglón)
 [Producto______] [Comercio (opcional)____] [Cant 1] [Hasta $ ___ moneda v] [x]
 [+ Agregar otro]
¿Cuándo venís a Bermejo? [fecha]   Notas [__________]
[ ] Acepto las condiciones del servicio y la garantía de custodia
[Enviar encargo]
Errores en línea: «Falta tu WhatsApp», «Agregá al menos un producto».
Éxito: «Tu encargo es ENC-7K2Q. Guardá este link: uruku.bo/encargos/s/<token>»
       [Copiar link] [Escribir al 67671888 con mi código]
```

### 6.3 Seguimiento `/encargos/s/<token>`
```
ENC-7K2Q · Estado: Comprado, en depósito
Línea de tiempo: Pedido ✓  Cotizado ✓  Anticipo ✓  Comprado ✓  Guardado ✓  Retirado –
Ítems: Zapatilla X T42 · Comercio Y · Bs 380 [foto]   Mochila · sin stock (devuelto Bs 120)
Pagado: Bs 500 · Saldo a pagar al retirar: Bs 75 (incluye tarifa)
Paquetes: PKG-31AF · guardado gratis hasta 27/10
Código de retiro: 482 913   (traé tu documento)
Personas autorizadas: [+ Autorizar a alguien]
¿Dudas? [WhatsApp 67671888]
Vacío/errores: token inválido → «Link no válido». Encargo cancelado → motivo y devolución.
```

### 6.4 Panel › Servicios
```
Pestañas: Encargos | Depósito | Retiros | Vencimientos | Reclamos | Caja | Precios
Encargos: [Buscar ENC/nombre/WhatsApp] [Estado v] [+ Cargar encargo]
  ENC-7K2Q · Ana P. · +54 387… · quoted · hace 3 h · [Abrir]
  Detalle: ítems editables · [Avisar por WhatsApp] · [Registrar anticipo]* · [Rechazar]
Depósito: [+ Ingresar paquete] · lista por ubicación · PKG · cliente · estado · días
Retiros: [Código o PKG] → paquetes + saldo + [Documento: ____] → [Cobrar] → [Entregar]
Vencimientos: por vencer / overdue / >75 días, con avisos registrados y botón wa.me
Reclamos: abiertos primero · foto ingreso vs. foto reclamo · [Aprobar monto] [Rechazar]
Caja: anticipos recibidos, compras, saldos cobrados, devoluciones, por día y por operador
Precios: concepto · monto · moneda · [ ] activo   |  [ ] Mostrar precios al público
          [ ] Servicio de encargos activo
* sólo con permiso servicios.pagos
Estados vacíos: «No hay encargos nuevos», «El depósito está vacío».
```

## 7. Roles y permisos nuevos

Se suman a la tabla `roles` (0126) como hizo la 0146 con el publicador:

| Permiso | Operador de encargos (`encargos`) | Operador de depósito (`deposito`) | Admin |
|---|---|---|---|
| `encargos.ver` / `encargos.gestionar` (cargar, cotizar, comprar, avisar) | Sí | Ver | Sí |
| `deposito.ingresar` / `deposito.entregar` | No | Sí | Sí |
| `servicios.pagos` (anticipos, saldos, devoluciones) | **No** | Cobra el saldo **sólo al entregar** | Sí |
| `servicios.reclamos` (resolver) | Abrir | Abrir | Resolver |
| `servicios.precios` (tarifas, flags) | No | No | Sí |
| Liberar retiro bloqueado, marcar `abandoned`/`disposed` | No | No | Sí |

Separación buscada: **quien compra no registra el anticipo** y **quien recibe no resuelve reclamos**. En un equipo de 2 personas se permite que una tenga los dos roles de operador, nunca `servicios.pagos` + `encargos.gestionar` (S-11).

## 8. Legal: qué cambia

### 8.1 Términos (`docs/legal/terminos.md`)
- **§1:** queda «guía de comercios», pero el párrafo «no vende, no compra…» pasa a decir: «En la guía, URUKU no vende, no compra… Además, URUKU ofrece **servicios propios** (encargos y guardería, §6 bis) donde sí es parte y responde por lo que ahí se dice».
- **§3** («las compras son entre vos y el comercio»): agregar «salvo lo que URUKU guarda en su servicio de guardería: ver §6 bis». El consejo «Ninguna persona de URUKU te va a pedir plata por una compra» cambia a: «Sólo te pedimos plata en un encargo **que vos iniciaste**, por los medios oficiales de uruku.bo/encargos, y siempre con tu código ENC».
- **§6 bis nuevo — Encargos y guardería** (texto propuesto en 8.2).
- **§12:** «No respondemos por las compras… salvo la custodia de §6 bis».

### 8.2 Cláusula de custodia (propuesta)
> **Garantía de custodia.** Desde que URUKU registra un paquete en su depósito hasta que vos (o la persona que autorizaste) lo retirás y firmás «recibí conforme», URUKU es responsable de guardarlo. Si se **pierde**, es **robado** o se **daña** mientras está en nuestro depósito, te reponemos el mismo producto o te devolvemos su **valor declarado**, a elección de URUKU y con tu acuerdo. **Nuestra responsabilidad máxima es el valor declarado** al ingresar el paquete (en un encargo, lo que se pagó según el comprobante del comercio), con un tope de [Bs 3.500] por paquete.
> **No cubre:** fallas o defectos de fábrica; que el producto no te guste o no sea el modelo, talle o color que esperabas cuando coincide con la foto que aprobaste; diferencias de precio; garantías del comercio; lo que pase después del retiro; ni objetos excluidos que no declaraste. Esos reclamos son con el comercio.
> **Plazos.** Revisá el paquete al retirarlo: un daño se reclama **antes** de firmar «recibí conforme». Una pérdida se reclama hasta 30 días después de la fecha en que tu paquete estaba disponible. Respondemos en 10 días hábiles.
> **Guardado.** Los primeros [7] días son gratis; después se cobra la tarifa diaria vigente. Si a los [90] días no lo retiraste y te avisamos al menos 3 veces al WhatsApp que diste, el paquete se considera abandonado y URUKU puede disponer de él para cubrir lo adeudado; si sobra dinero, queda a tu favor por 12 meses.
> **Retiro.** Sólo con tu código de retiro y tu documento, o los de la persona que autorizaste desde tu link. Si alguien retira con tu código y tu documento, se considera que retiraste vos.
> **Frontera.** Entregamos sólo en Bermejo. URUKU no traslada mercadería entre países. Cruzar con lo que compraste, declararlo y pagar lo que corresponda es tu responsabilidad.

### 8.3 Privacidad (`politica-privacidad.md`) — nueva §3.9 «Si usás encargos o guardería»
Datos: nombre, WhatsApp, ciudad (no pedimos dirección: no hay envíos, S-12), lista de productos, cotizaciones, pagos y comprobantes, fotos de productos y paquetes, número de documento (**guardado cifrado de forma que sólo sirve para comparar**, más los últimos 3 dígitos visibles), personas autorizadas (nombre + documento, igual), registro de retiro y reclamos. **Nunca públicos.** El comercio no ve tus datos (URUKU compra a nombre propio o con tu NIT/CI si lo pediste para la factura). Plazos: pagos y comprobantes 5 años (contable); fotos y documento 12 meses después del último retiro o del cierre del reclamo; encargos `expired`/`rejected` 90 días. Base: necesario para el servicio que pediste; documento = seguridad del retiro.

### 8.4 Inventario (`inventario-datos.md`) — nueva sección **L. Encargos y guardería** (todo «J» hasta que exista el código)
L1 cliente (nombre, WhatsApp, ciudad) · L2 documento (hash + 3 dígitos) · L3 encargos e ítems · L4 pagos/anticipos/devoluciones y comprobantes (disco privado) · L5 fotos de productos, comprobantes de comercios y paquetes (disco privado) · L6 personas autorizadas · L7 retiros (operador, hora, conforme) · L8 reclamos y evidencias · L9 token de seguimiento (hash). Base: S (L1-L7), L (L4), O (L9).

### 8.5 Aduana y frontera (**verificar con abogado y despachante**)
- **Franquicia argentina por paso terrestre (2026):** USD 300 por adulto y USD 150 por menor de 16, **mensual y no acumulable**; el excedente paga 50 %; sin free shop extra salvo Puerto Iguazú ([iProfesional, 27/07/2026](https://www.iprofesional.com/legales/460837-cual-es-el-limite-de-arca-para-ingresar-compras-del-exterior-sin-tributar); [La Nación](https://www.lanacion.com.ar/economia/cual-es-el-limite-en-dolares-para-traer-productos-del-exterior-y-no-pagar-impuestos-nid21012026/)). No encontramos régimen especial para Aguas Blancas–Bermejo: confirmar en ARCA.
- **Tráfico vecinal fronterizo:** el Código Aduanero (arts. 578-580) excluye su uso con fines comerciales; la **RG ARCA 5910/2026** (vigente desde el 10/10/2026) fijó USD 150 por día y por poblador, pero para el régimen de **exportación** (de Argentina hacia el país vecino) ([Contadores en Red](https://contadoresenred.com/arca-fija-tope-diario-y-suma-prohibiciones-al-trafico-fronterizo/amp/)). No aplica directo a las compras en Bermejo, pero muestra que ARCA está controlando el «contrabando hormiga» ([Letra P](https://www.letrap.com.ar/politica/una-medida-arca-frenar-el-contrabando-hormiga-alarma-las-ciudades-fronterizas-del-norte-grande-n5427337)).
- **Riesgo para URUKU:** guardar muchos paquetes de una persona, o cantidades de reventa, puede verse como facilitar el ingreso comercial no declarado. Mitigación: entregar sólo en Bermejo, rechazar cantidades comerciales (S-02), aviso de franquicia en la página y en la cotización, y no asesorar sobre cómo cruzar.
- **Lado boliviano** (factura, salida de mercadería, si URUKU necesita una actividad registrada de mandato/depósito): **verificar con contador y abogado** antes de lanzar.

## 9. Riesgos operativos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| **Dinero de terceros** (anticipos que no son ingreso de URUKU) | Cuenta separada para anticipos; anticipo registrado sólo por admin; caja diaria (anticipos vs. compras vs. devoluciones) con cierre firmado; devolución de lo no gastado en 48 h. Tratamiento impositivo: contador |
| Operador que compra con plata propia o cobra en mano | Prohibido por regla y en la página («sólo pagás por los medios oficiales, siempre con tu ENC»); el operador no tiene `servicios.pagos` |
| Robo en el depósito (externo o interno) | Acceso con llave sólo a operadores de depósito; precintos numerados; fotos de ingreso; **inventario ciego semanal** (se cuenta sin ver la lista y se cruza); cámara en el depósito (S-13) |
| Sin seguro: una pérdida grande la paga URUKU entera | Tope por paquete (S-08) y tope total en depósito; cotizar póliza de robo/incendio sobre bienes de terceros (**dependencia externa**) antes de pasar de ese tope |
| Disputa «me cambiaron el producto» | Cliente aprueba foto antes de pagar; foto del paquete cerrado con precinto; revisión y «recibí conforme» en el mostrador |
| Retiro por un impostor | Código + documento coincidente + bloqueo a los 3 intentos; autorización sólo desde el link |
| Estafadores usando «URUKU encargos» | Un solo número (67671888) y un solo dominio; la página lo dice; el link de seguimiento muestra el pago registrado |
| Producto prohibido o perecedero | Lista de excluidos en página, formulario y cotización; el operador puede rechazar |
| Paquetes que nadie retira | 7 días gratis, cobro diario, 3 avisos, abandono a 90 días con texto aceptado al pedir |
| El 67671888 se satura o es baneado | Es WhatsApp común con humano (bajo riesgo); textos manuales, sin masivos; Marca con API oficial en segunda etapa |
| Alguien conecta el 67671888 a WAHA por error | Prohibido por decisión del 19/10: el respaldo de WAHA es el 68727584 (P-08) |
| Comercio que no da comprobante | El operador no compra ahí sin comprobante (al menos nota de venta) o lo documenta con foto del producto + precio en el local |

## 10. Supuestos (a confirmar uno por uno)

- **S-01** Sólo comercios de Bermejo (no Tarija, no otros pueblos).
- **S-02** Se rechazan cantidades comerciales: más de 3 unidades iguales o un total que supere USD 300 por persona por encargo, salvo aprobación del admin.
- **S-03** Tarifa del servicio = monto fijo por encargo + % opcional sobre lo comprado; guardería walk-in = fijo por paquete; guardado = por día tras los gratis. Todo en Bs, editable, oculto al público hasta activarlo.
- **S-04** Anticipo del 100 % del valor estimado de los productos antes de comprar; tarifa y guardado al retirar.
- **S-05** Cotización vigente 72 h; sin pago, `expired`.
- **S-06** Diferencia de precio tolerada sin consultar: hasta 10 %; se ajusta al retirar.
- **S-07** Factura del comercio a nombre del cliente si da NIT/CI; si no, sin nombre. URUKU factura sólo su tarifa (cuando tenga NIT).
- **S-08** Tope de valor declarado: Bs 3.500 por paquete y Bs 50.000 en todo el depósito, editables.
- **S-09** 7 días corridos de guardado gratis para encargos y walk-in.
- **S-10** Abandono a los 90 días con 3 avisos; sobrante a favor del cliente 12 meses.
- **S-11** Equipo inicial: 1 o 2 operadores + el admin (dueño).
- **S-12** No se pide dirección del cliente (no hay envíos).
- **S-13** El depósito es un espacio cerrado en la oficina de URUKU, con horario de retiro = horario de oficina.
- **S-14** El cliente acepta las condiciones con una casilla en el formulario; quien llega por WhatsApp, al aprobar la cotización (texto con link a las condiciones).

## 11. Para el arquitecto

**Numeración:** las migraciones arrancan en **0168** (0156-0158 marketing, 0159-0164 grupos, 0165-0166 cobro mensual, 0167 device tokens). Archivo idéntico en `supabase/migrations/` y `selfhost/postgres-init/`, con GRANTs explícitos y test.

**Entidades sugeridas (sin SQL definitivo):**
- `service_clients`: nombre, whatsapp E.164, ciudad, país, `doc_type`, `doc_hash` (HMAC con secreto del backend), `doc_last3`, `usuario_id` opcional (segunda etapa), `activo`.
- `orders`: código ENC, cliente, estado, fechas por estado, `quote_snapshot` (tarifas al cotizar), `customer_approved_at`, `tracking_token_hash`, origen (`web`/`whatsapp`/`walk_in`), motivo de rechazo/cancelación.
- `order_items`: producto, comercio (`comercio_id` opcional + texto libre), cantidad, precio máx., estimado, real, moneda, estado, foto producto, foto comprobante, `price_change_accepted_at`.
- `service_payments`: encargo o cliente, tipo (`advance`/`balance`/`refund`/`claim_payout`), monto, moneda, medio, referencia, comprobante, registró (email), fecha. No reusar `pagos` (es de comercios).
- `packages`: código PKG, cliente, encargo opcional, descripción, valor declarado, moneda, precinto, ubicación, estado, `stored_at`, `free_until`, `pickup_code_hash`, intentos fallidos, fotos.
- `package_events`: ingreso, movimiento, aviso registrado, retiro, intento fallido, abandono (actor + hora). Auditoría append-only.
- `authorized_pickers`: paquete o encargo, nombre, `doc_hash`, `doc_last3`, activo.
- `custody_claims`: paquete, tipo, descripción, fotos, estado, monto, motivo, resolvió.
- `service_prices`: concepto, monto, moneda, activo; `service_settings`: `prices_public` (bool), `orders_enabled` (bool), días gratis, días de abandono, topes.
- Caja: vista o reporte sobre `service_payments` + `order_items.real`.

**Reglas:**
- Todo **privado**: RLS sin grants a anon. La página pública y el seguimiento van por **FastAPI** (token → hash → datos filtrados), nunca PostgREST directo.
- El endpoint público de precios devuelve vacío si `prices_public = false` (no basta con esconderlo en el front).
- Fotos de comprobantes, documentos y paquetes en **disco privado** servido sólo al panel (como `PAYMENT_PROOFS_DIR` de cobro mensual, T9), nunca bajo `/fotos/`.
- Soft-delete en todo; ningún DELETE físico. Códigos ENC/PKG sin caracteres ambiguos. Código de retiro y token se guardan hasheados.
- Permisos nuevos en `roles` (§7), sin prender roles vaciados (patrón 0146).
- **No tocar la ingesta de WAHA**: los encargos no entran por `wa_inbox`. En segunda etapa, los entrantes a la Marca se separan antes de la ingesta (`cobro-mensual.md` T13).
- Fechas en hora de Bolivia (no `date.today()` del contenedor, ver `cobro-mensual.md` §1).
- Rate limit + honeypot en el formulario público.

## 12. Preguntas para el dueño (cerradas, con recomendación)

| # | Pregunta | Recomendación |
|---|---|---|
| P-01 | ¿Dónde paga el anticipo un cliente argentino: (a) cuenta boliviana en Bs, (b) cuenta argentina en pesos (alias), (c) sólo efectivo en la oficina? | **(b) + (c)**: sin cuenta en pesos, el cliente de Orán no puede pagar a distancia y el servicio no arranca |
| P-02 | ¿Anticipo del 100 % de los productos antes de comprar? | **Sí** (S-04): URUKU no pone plata propia por un cliente que quizá no vuelve |
| P-03 | ¿Días de guardado gratis: 7, 15 o 30? | **7** (S-09): el depósito es chico y el abandono es el mayor costo oculto |
| P-04 | ¿Abandono a los 90 días con 3 avisos y URUKU dispone del paquete? | **Sí**, sujeto a abogado (S-10) |
| P-05 | ¿Tope de valor declarado por paquete en Bs 3.500? | **Sí**, editable, hasta tener seguro (S-08) |
| P-06 | Si URUKU compra algo **distinto a la foto que aprobó el cliente**, ¿URUKU lo cambia a su costo? | **Sí**: es error nuestro, no del producto; sin esto la garantía pierde credibilidad. No cambia la exclusión de producto fallado |
| P-07 | ¿El depósito es la oficina actual, con retiro en horario de oficina? | **Sí** para el MVP (S-13); un depósito aparte, cuando el volumen lo pida |
| P-08 | ¿Activamos ya el Respaldo 2 (68727584) como respaldo callado de WAHA, dado que el 67671888 es el público y no se conecta a WAHA? | **Sí** |
