# Modelo comercial y ecosistema — Bermejo Live Market

> Documento vivo. Registra el modelo de negocio (embudo, membresías, add-ons),
> ideas de crecimiento y el análisis del ecosistema (amandaclothing).
> Complementa el ADR de producto: `../../architect-kb/decisions/2026-06-10-modelo-producto-bermejo.md`.
> Última actualización: 2026-06-10.

## 0. Principio rector (recordatorio)

Bermejo Live Market es una **capa de descubrimiento + conexión**, NO un
marketplace. La venta ocurre directo comprador↔vendedor por WhatsApp; la
plataforma no es dueña de la transacción. **Si algo obliga a la plataforma a ser
dueña de la transacción, no es para este producto.** (Ver ADR de producto.)

---

## 1. Embudo de onboarding — 3 pasadas

| Pasada | Qué pasa | Cobro | Consentimiento | Estado en el sistema |
|---|---|---|---|---|
| **1ª · Relevamiento** | El agente de campo carga la ficha básica (nombre, celular, rubro, modalidad, GPS, foto). El local **ya aparece en el mapa** como "presencia básica". | — (gancho gratis) | Verbal (marcado) | ✅ construido (`/bermejo`) |
| **2ª · Venta + alta** | Vuelve, le muestra que **ya está en el mapa**, explica el **alcance regional** (BA, Córdoba, Tucumán, Orán, Salta + redes + medios) y cierra el **1er cobro / mes de prueba**. | **Sí — primer cobro** | **Papel presencial** (foto del papel firmado) | Falta: registro de pago + consentimiento (tipo=papel) + "modo venta" en el agente |
| **3ª · Activación** | Le da **acceso al panel**: publicar ofertas + subir videos al **canal TikTok del sitio**. | Continúa membresía | **Formulario web** (datos privados) | ✅ panel `/publicar`; falta consentimiento digital |
| **Luego · Upsell** | Con usuarios activos, se ofrecen servicios "llave en mano". | Add-ons | Por servicio | Falta: catálogo de add-ons |

**Gancho de la 2ª pasada:** *"ya estás en el mapa de Bermejo que ven los
compradores de Salta/Orán/Tucumán antes de cruzar la frontera"*. Eso justifica el
primer pago.

**Distinción de alcance (importante para no prometer de más):**
- **Orgánico** (sitio + redes propias + canal TikTok del sitio) → costo marginal
  bajo → incluido en las membresías.
- **Pauta paga en medios** (ads en redes, radio, diarios de BA/Córdoba/Tucumán/
  Orán/Salta) → cuesta plata real → **add-on o tier premium**, nunca regalado.
  *Evaluar costos antes de prometer.*

---

## 2. Membresías (recurrente) — 4 niveles

| | **Presencia** (gancho) | **Activo** (entrada, prueba 1 mes) | **Destacado** (Pro) | **Premium Frontera** |
|---|---|---|---|---|
| Mapa + buscador | ✅ | ✅ | ✅ | ✅ |
| Ficha con WhatsApp + cómo llegar | ✅ | ✅ | ✅ | ✅ |
| Publicar ofertas | — | ✅ (moderación) | ✅ más cupo | ✅ **directa** (confiable) |
| Video al canal TikTok del sitio | — | 1/mes | varios/mes | ilimitado |
| Publicidad orgánica regional | — | ✅ | ✅ prioridad | ✅ máxima |
| Hot-sale destacado en el mapa | — | — | ✅ | ✅ |
| Verificado (insignia) | — | — | — | ✅ |
| Bot de WhatsApp | — | — | opcional | ✅ |
| Reporte visitas/contactos | — | mensual | semanal | semanal + preguntas |
| Cupo de pauta paga incluida | — | — | — | una cuota/mes |

> "Probar un mes" = primer mes de **Activo** (mensual, baja cuando quiera). El
> consentimiento papel de la 2ª pasada lo habilita.
> Mapea al campo `comercios.plan` (hoy gratis/pro/premium → renombrar/extender).

**Decisiones abiertas:** nombres de tiers (propuestos: Presencia/Activo/
Destacado/Premium Frontera) · ¿la presencia básica es gratis? (recomendado: sí,
como gancho).

---

## 3. Add-ons "llave en mano" (alto margen — vendés conocimiento)

À la carte, one-time o mensual:

- 🎬 **Creación de TikTok** (por video o pack mensual).
- 📱 **Creación y manejo de redes** (IG/FB).
- 💬 **WhatsApp Business llave en mano** (catálogo, bienvenida, etiquetas).
- 📸 **Sesión de fotos profesional**.
- 🎨 **Logo y branding**.
- 📣 **Campaña de pauta** (ads en redes/medios regionales) — packs por alcance.
- 🎓 **Capacitación** (panel / vender por WhatsApp).
- 🛍️ **Tienda online + auto-redes** (ver §6, motor estilo amandaclothing).

---

## 4. Ideas de crecimiento

1. **"Reclamá tu local gratis"** — la presencia básica engancha al embudo.
2. **Combo por galería/mercado** — vender una galería entera (tarifa grupal).
3. **Cupón de frontera** — "mostrá esta oferta al cruzar" → tráfico medible.
4. **Anclas publicitarias** — importador grande paga banner (ingreso aparte).
5. **Referido vecino** — un comercio trae a otro → descuento (viral local).
6. **Eventos de temporada** — "Hot Sale Frontera", Día de la Madre.
7. **Reporte mensual como retención** — "te vieron 320, te escribieron 41".

---

## 5. Lo que el sistema necesita para soportar el modelo

- **Login con teléfono O email (teléfono como principal)** — muchos comercios no
  tienen email. Patrón KB `identidad-celular-progresiva`: **celular único**, email
  **opcional** (o sintético `cel@bermejolive.local`), y el "magic link" se
  reemplaza por **OTP por WhatsApp** para el teléfono. Es **transversal** (Bermejo +
  el motor de tiendas). Hoy **ni Bermejo ni `tienda` lo tienen** (ambos usan
  email/clave) → construir una vez y reusar (~1 semana).
- **Suscripción + pagos** (F-007): tiers + prueba + baja. Cobro inicial manual
  (efectivo/QR en Bermejo) registrado a mano; luego MercadoPago.
- **Tabla de consentimientos** (tipo papel/web, fecha, foto del papel o datos del
  form, qué autorizó).
- **"Modo venta" en el agente** (2ª pasada): alta paga + foto del papel + tier.
- **Catálogo de add-ons** (servicios contratados por comercio).
- Flags `origen`/`reclamado` + modo "reclamar local cercano" (va con el import OSM).

---

## 6. amandaclothing — análisis de ecosistema (crítico)

**Qué es:** sitio propio, estilo MercadoLibre pero más simple, hecho para la
esposa del dueño. Los **clientes suben sus productos** y comercializan; al subir
un producto, **se publica en redes sociales**. El dueño no sube nada (cada cliente
carga lo suyo).

### Tensión estratégica (lo más importante)

amandaclothing es un **marketplace/tienda** (suben productos, se vende).
Bermejo es **lo contrario** (capa de descubrimiento, sin checkout, venta por
WhatsApp). **Combinarlos ingenuamente traiciona la tesis de Bermejo.** No fundir
los modelos.

### El problema duro de todo marketplace: los COMPRADORES, no los vendedores

"Cada cliente sube sus cosas" resuelve el lado **fácil** (oferta). El lado difícil
es la **demanda**: ¿quién compra? El moat de MercadoLibre es el **tráfico de
compradores**, no el catálogo. Un amandaclothing **multi-vendedor** enfrenta un
cold-start de compradores brutal. Para **una sola marca** (Amanda, que trae su
propio tráfico por redes) funciona perfecto — es su tienda, no un mercado.

### "Se puede vender también" = ¿pagos?

Si hay **checkout real**, heredás pagos, fraude, devoluciones, disputas, logística
— pesado, y rompe la seguridad de "no soy dueño de la transacción". Si es
**contacto-para-comprar** (WhatsApp/manual), es liviano y compatible con Bermejo.
**Hay que aclarar cuál es.**

### Auto-publicar en redes — feasibility honesta

- **A una cuenta central** (la de Amanda): fácil y robusto. ✅
- **A la cuenta propia de cada cliente** (automático): **difícil y frágil** —
  requiere Instagram/Facebook Graph API con cuentas Business, **revisión de app de
  Meta**, OAuth y tokens por usuario (expiran), rate limits (~25 posts/día/IG).
  TikTok: Content Posting API con aprobación. **Hay que aclarar cómo lo hace hoy.**

### Veredicto por escenario

| Escenario | Feasibilidad |
|---|---|
| Tienda de **una marca** (Amanda) + auto-post a cuenta central | ✅ Sólido y útil |
| **Multi-vendedor** compitiendo con ML/Shein | ⚠️ Muy duro (cold-start de compradores, pagos, confianza) |
| **Add-on de Bermejo** (tienda online + auto-redes para comercios Premium) | ✅✅ El encaje más fuerte |

### Recomendación de encaje

1. **Bermejo NO se vuelve marketplace.** Sigue siendo capa de descubrimiento.
2. **amandaclothing = (a)** la tienda de Amanda (funciona), **y (b)** un potencial
   **add-on white-label "Tienda online + auto-redes"** que le vendés a los
   comercios **Pro/Premium** de Bermejo que SÍ quieren catálogo y publicación
   automática. Así se monetiza por el **paquete de Bermejo**, esquivando la
   economía de marketplace.
3. El **motor upload→auto-post** de amandaclothing puede potenciar el add-on
   "publicaciones + redes" del §3.
4. **No fusionar** los modelos de datos; integrar por límites claros (identidad
   del comercio, WhatsApp, motor de publicación).

### Preguntas que cambian el veredicto (a responder)

1. El auto-post: ¿a una **cuenta central** o a la **cuenta propia de cada cliente**?
2. El "vender": ¿**checkout/pagos real** o **contacto por WhatsApp**?
3. ¿amandaclothing es hoy **una marca** (Amanda) o ya **multi-vendedor**?
4. Stack de amandaclothing (para evaluar integración real).

---

## 7. Capa de tienda/ofertas (BermejoOfertas + tiendas por vendedor)

**Jerarquía correcta (aclarada por el dueño):**
1. **Núcleo:** Bermejo Live Market (descubrimiento + mapa + WhatsApp) — lo construido.
2. **Como servicio adicional**, una capa de **tienda con carrito**. El dueño la
   piensa en dos formas (no excluyentes):
   - **Opción A — BermejoOfertas:** un sitio **compartido** con los productos en
     oferta que publican todos los vendedores.
   - **Opción B — Tienda por vendedor:** venderle a **cada vendedor su propio sitio**
     con carrito y todo lo necesario para la operación (es lo que ya existe para
     **amandaclothing**, replicado/white-label por vendedor).

**Venta en ambos:** solo **contacto por WhatsApp** + **QR** o **reserva**; **carrito**
que arma el pedido y se envía por WhatsApp; **sin envío** salvo acuerdo
comprador↔vendedor. Compatible con el principio de Bermejo: el carrito solo arma el
mensaje; la plataforma **no procesa pagos ni logística**.

### El nombre: "BermejoOfertas" ✅ (mejor que "MercadoOfertas")

Bajo la marca propia **Bermejo** evita el conflicto con la familia "Mercado___" de
MercadoLibre (que litiga marca agresivamente). Igual conviene chequear dominio +
redes. *No es asesoría legal.*

### Regla técnica innegociable: UN motor multi-tenant, NO un sitio por vendedor

"Generar otro sitio para cada vendedor" **copiando el código = pesadilla de
mantenimiento**. Tiene que ser **multi-tenant**: **una sola app**, cada vendedor es
un *tenant* (subdominio `vendedor.bermejolive.com` o ruta `/tienda/vendedor`), **un
solo deploy**. Es el motor de amandaclothing convertido en multi-tenant.

### La síntesis: A y B salen del MISMO motor

Construís **un motor storefront multi-tenant** (catálogo + carrito→WhatsApp+QR +
auto-redes, reusando amandaclothing) y de ahí salen las dos cosas:

- **Opción B (tienda por vendedor)** = el **producto que se vende** (add-on "Tienda
  online" del §3). **Sin cold-start de compradores**: cada vendedor trae SU
  audiencia (como Amanda) + Bermejo le manda tráfico. **Es el camino de plata claro.**
- **Opción A (BermejoOfertas)** = una **vista agregada** de las ofertas de todas esas
  tiendas, bajo el paraguas Bermejo. **Sale casi gratis** del mismo motor (es un
  catálogo que junta los productos-oferta de los tenants).

> O sea: **construí B, y A te queda casi de regalo.** Bermejo (mapa/descubrimiento)
> manda tráfico a las dos.

### Veredicto

1. **Nombre:** "BermejoOfertas" OK (mejor que "MercadoOfertas").
2. **Arranca por B** (tiendas por vendedor) = monetización directa, sin cold-start,
   ya tenés el código (amandaclothing) → volverlo **multi-tenant**.
3. **A (BermejoOfertas)** = vista agregada que sale del mismo motor; no es un tercer
   producto ni un código aparte.
4. **No copiar el código por vendedor.** Multi-tenant siempre.
5. **Cuidado A como destino:** como mercado-destino independiente hereda cold-start;
   como vista bajo Bermejo (que ya trae audiencia local + regional) es razonable.

### Análisis de `tienda` (amandaclothing) — hallazgos clave

Revisado el repo `C:\repos\proyectosClaude\tienda`:

- **Mismo stack que Bermejo** (Next 14 + FastAPI + Supabase + MercadoPago + Gemini) ✅
- **Ya tiene**: carrito → **checkout por WhatsApp** (wa.me con pedido pre-armado),
  transferencia y MercadoPago; **auto-publicación a redes** (Telegram, Facebook e
  Instagram por Graph API; TikTok manual) por **botón** del admin; panel de carga
  de productos con fotos a Storage; **modo mayorista B2B** (listas de precio,
  cuenta corriente). Muy completo.
- **Auto-post = a las cuentas PROPIAS de la tienda** (FB_PAGE_ID / IG_USER_ID /
  Telegram configurados por deploy), no a la cuenta de cada comprador. **Es el
  patrón robusto** (resuelve la duda del §6). Pero **se dispara con un botón**, no
  automático al subir (matiz).
- **Multi-tenancy = un deploy + una Supabase POR cliente** (white-label vía tabla
  `tienda_config` + CSS variables). **NO hay `tenant_id` ni RLS por tienda.** Alta
  de cliente nuevo ≈ 30–60 min (Supabase + dominio + contenedor). True multi-tenant
  (una sola BD, muchas tiendas) = **refactor de 4–6 semanas**.
- **Auth = email + clave** únicamente. **No** tiene teléfono/OTP/magic-link.

### Recomendación corregida (con estos datos)

1. **NO refactorizar a multi-tenant ahora, NO rehacer.** Usar `tienda` **tal cual**
   (deploy-por-cliente) para **vender tiendas por vendedor** (Opción B) a los
   comercios Premium. Ya tiene carrito→WhatsApp + auto-redes + B2B → **se puede
   vender YA**. Costo: una Supabase + dominio por tienda (aceptable para pocos
   premium; no para cientos).
2. **Corrección al "A sale gratis de B":** con deploy-por-cliente **no** es
   automático. PERO **BermejoOfertas (A) = el feed/buscador que Bermejo YA tiene**.
   No hay que construir un sitio agregado nuevo: cuando una tienda publica una
   oferta, se **empuja también** a una `publicacion` de Bermejo (integración chica).
   Bermejo sigue siendo el **hub de descubrimiento**; las tiendas son el **upsell de
   catálogo profundo + carrito**.
3. **Login teléfono/OTP** (§5) falta en ambos → construir una vez, reusar.
4. **Multi-tenant** se evalúa **más adelante**, cuando la cantidad de tiendas haga
   doler el costo por-deploy.

---

## 9. Roadmap: relevamiento manual → autoregistro + suscripción

**Fase 1 (en producción):** carga **manual** por el agente (`/bermejo`) de empresas,
comercios y todos los rubros, hasta **~500 negocios**. El sitio público está en
"Próximamente" (modo captura).

**Fase 2:** **autoregistro abierto**. La persona entra y se registra sola; carga
sus redes (**Facebook/Marketplace, TikTok, Instagram, web**) y todo lo que quiera.
- Los campos de redes **ya existen** en `comercios` (tiktok/facebook/instagram/web).
- Hace falta un **panel "Mi comercio"**: ver su info, **modificar**, **alta/baja**.
- **Reclamar listado:** si su negocio ya fue cargado en Fase 1, que lo **reclame
  por su teléfono** (no duplicar). Mismo patrón que el "claim" de OSM.

**Monetización:** **todos** pagan una **cuota mensual por QR**. El pago desbloquea:
subir contenido, generar ofertas, estar en el mapa, (y opcional) subir productos.
- **Suscripción automática:** paga → datos visibles; **no paga → cuenta
  desactivada** hasta que vuelva a pagar. Automático.

### ⚠️ Lo único realmente complicado: automatizar el pago QR en Bolivia

- **Desactivar automático = fácil:** un **job nocturno** desactiva (`activo=false`)
  a quien tenga `paga_hasta < hoy`. Reactivar al pagar es subir esa fecha.
- **Detectar el pago automático = el problema:** un QR estático (de billetera/banco)
  **no avisa** a tu sistema cuando alguien paga → habría que conciliar a mano.
  Para automatizar de verdad necesitás un **proveedor con webhook**.
  - **MercadoPago** (que ya usa `tienda`) tiene webhook de suscripción, **pero
    puede no operar en Bolivia** → a verificar.
  - Alternativas Bolivia: **QR Simple** (estándar interoperable del BCB) vía algún
    banco/fintech con API, o un PSP local. **A investigar.**
  - **MVP pragmático:** el comercio paga por QR y manda el **comprobante por
    WhatsApp** → admin (o un mini-flujo) confirma y el sistema **extiende
    `paga_hasta` 1 mes**. La **desactivación** ya queda 100% automática. Después se
    enchufa el webhook del PSP cuando se resuelva el proveedor.
- **Datos:** `comercios.plan` + `paga_hasta` (fecha) + `estado_pago`; tabla `pagos`
  (fecha, monto, periodo, método, comprobante).

### Productos ("MercadoLibre sin comisiones") — add-on, NO bloquea

Reafirma lo del §7: dar gestión de productos con carrito es el **motor de `tienda`**
(deploy-por-cliente hoy). Es un **add-on premium posterior**, no parte del MVP de
suscripción. La cuota base da perfil + ofertas + mapa + contenido; **productos se
suma después** para los que lo quieran, sin frenar el lanzamiento.

## 10. Posicionamiento: "Páginas Amarillas vivas" + consentimiento + QR Bolivia

**La metáfora rectora:** es la vieja sección de **Páginas Amarillas** de la guía
telefónica (todos los rubros, todos los negocios) — pero **viva**: en vez de un
listado estático una vez al año, hay **ofertas en tiempo real, WhatsApp, fotos y
video**. *"Las páginas amarillas, pero en vivo."* Esto unifica el producto:
- **La base** = directorio por **rubro** y por **ciudad** (ya tenés rubros + ciudades).
- **La monetización** = el **mismo modelo que las páginas amarillas**: pagás por
  estar y por un **aviso destacado** (negrita/color/arriba). Tus tiers
  (Destacado/Premium) = el "aviso grande". Modelo probado por décadas.

**Consentimiento (obligatorio en la carga de datos):**
- **Fase 1 (agente):** verbal/papel — ya hay checkbox de consentimiento en `/bermejo`.
- **Fase 2 (autoregistro):** **formulario de consentimiento digital** (términos +
  uso de datos + autorización a publicar sus datos, fotos y videos). Guardar
  registro del consentimiento (tipo, fecha, qué autorizó).

**QR de pago — Bolivia, cuenta boliviana (requisito firme):**
- El cobro mensual se hace con **QR de Bolivia a una cuenta boliviana** → MercadoPago
  queda descartado si no opera en BO. Camino: **QR Simple (BCB)** vía banco/fintech
  con API/webhook, o PSP boliviano. (Ver §9 para la automatización.)

**Contenido que el comercio puede subir (cerrado):**
- **Foto** (a Storage, ya implementado) · **Video** (link de TikTok — sin hostear) ·
  **datos de contacto + redes** (WhatsApp, Facebook/Marketplace, TikTok, Instagram,
  web) · **ubicación** · **ofertas/publicaciones**. Todos los campos ya existen en
  el modelo; falta el panel "Mi comercio" para que lo gestionen ellos (Fase 2).

**Más opciones sobre la idea Páginas Amarillas (para desarrollar):**
1. **Buscar por rubro/categoría** (la UX clásica) + **"Cerca de mí"** (geo).
2. **Urgencias/servicios 24h:** gomero, farmacia de turno, grúa, cerrajero,
   electricista — las páginas amarillas vivían de esto. Ángulo fuerte en frontera.
3. **Abierto ahora** (horarios) · **Reseñas/rating** (la confianza que la guía no tenía).
4. **Aviso destacado pago** = el "recuadro grande" de la guía (tu tier Destacado).
5. **Cupones/ofertas del día** (la sección de descuentos).
6. **QR físico / sticker** para el local ("encontranos en buscadonde") = puente
   offline→online.
7. **Rubros profesionales y turismo:** médicos, talleres, **hoteles**, transporte,
   mayoristas — la amplitud real de una guía (encaja con la visión Bolivia).

## 8. Decisiones abiertas (pendientes de confirmar)

- Nombres de los tiers.
- ¿Presencia básica gratis como gancho? (recomendado: sí).
- amandaclothing: las 4 preguntas del §6.
- Costos de pauta en medios (evaluar antes de prometer en tiers/add-ons).
- **¿Arrancamos por la Opción B** (tiendas por vendedor multi-tenant, reusando
  amandaclothing) y dejamos BermejoOfertas como vista agregada? (recomendado: sí).
- **Stack/forma de amandaclothing** (para ver el costo de volverlo multi-tenant).
- Chequear dominio + redes para "BermejoOfertas".
