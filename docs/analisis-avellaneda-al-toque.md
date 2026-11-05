# Avellaneda a un Toque vs. URUKU: qué conviene tomar (3/11/2026)

> **Qué es:** análisis funcional de lo que el dueño marcó en avellanedaauntoque.com, punto por punto. **No hay código.**
> **Fuentes:** las URLs de §12, consultadas el 3/11/2026, y el código de este repo (rama `feat/videos-v2`).
> **Límite de la lectura:** el sitio de Avellaneda arma casi todo en el navegador, así que lo que vimos son textos y enlaces, no la pantalla dibujada. No encontramos una página de videos (`/videos` devuelve 404) ni una ficha «sólo venta online» abierta. Esa etiqueta la vimos únicamente en las tarjetas de productos.
> Los supuestos van numerados **S-01…** y las preguntas para el dueño, en §11.

## 0. En una pantalla

Avellaneda a un Toque (de «Mercados a un toque SRL») es el **catálogo de un solo centro mayorista de ropa** (Av. Avellaneda, Flores). Los locales cargan sus productos con precio, compra mínima, talles y colores, y la compra se cierra por WhatsApp o en el local. Tiene carrito, favoritos, locales seguidos, calificación de la tienda y apps en las dos tiendas. **No media la compra.** Su FAQ lo dice así: «no podemos garantizar que los locales cumplan con lo acordado».

URUKU resuelve **otro problema**: una ciudad entera, de todos los rubros, con un comprador que muchas veces viene de otro país. Esto lo hace mejor, y Avellaneda no lo tiene:

| Lo que URUKU tiene y Avellaneda no | Dónde está |
|---|---|
| Mapa de toda la ciudad, «qué hay cerca tuyo» y «Cómo llegar» en cada ficha | `/buscar?vista=mapa`, `app/comercios/[slug]/page.tsx` |
| Servicios de la ciudad: baños, cajeros, estacionamiento, wifi, taxis, policía, farmacias de turno | `components/accesos-ciudad.tsx`, `app/page.tsx` (`SERVICIOS`), `TarjetaTurnoHoy` |
| Guía de frontera (aduana, documentos, paso, chalanas, río) y «Hoy en Bermejo» | `app/page.tsx` (`GUIAS`, `uk-home-hoy`), `/guia` |
| Cambio del día con calculadora, también en el header | `/cambio`, `components/uruku-shell.tsx` |
| WhatsApp directo con mensaje armado y contacto medido, y la marca «Responde» / «Últimamente no contesta» | `WaLeadLink`, pills `responde`/`noResponde` en la ficha |
| «Abierto ahora», y el aviso cuando el horario es el habitual de la zona y no uno confirmado | `HorarioBadge`, `horario_estimado` |
| Agentes que recorren y cargan cada local en la puerta | manual, `/agentes`, `fuente='campo'` |
| QR de cada ficha y varias ciudades con SEO (JSON-LD, ISR) | ficha, `lib/seo.ts` |
| Se usa sin registrarse ni descargar nada | manual `content/manuales/uruku.md` |

**Lo que de verdad falta no es una función: es contenido.** La home de Avellaneda siempre está llena porque miles de productos con precio la alimentan solos. La de URUKU en producción no tenía hoy **ni ofertas ni videos**: las dos secciones existen en el código y se esconden cuando no hay nada que mostrar. Según el comentario de `comercios/[slug]/page.tsx`, 138 de 1.253 comercios tienen WhatsApp, un dato que hay que revalidar. Cualquier mejora visual rinde poco si no sube el volumen de publicaciones.

## 1. Apps para iPhone y Android

| | |
|---|---|
| **Avellaneda** | Apps en las dos tiendas ([App Store](https://apps.apple.com/uy/app/avellaneda-a-un-toque/id1596612134), [Google Play](https://play.google.com/store/apps/details?id=com.avellanedaaltoque.aat)). La FAQ dice: «Para la mejor experiencia, recomendamos usar las apps nativas». La de iPhone pesa **479 KB** (versión 1.7), así que muy probablemente es una envoltura del sitio (inferencia, no confirmada) |
| **URUKU hoy** | **PWA confirmada.** `frontend/app/manifest.ts` (standalone, colores de marca, accesos directos a Cargar, Mis comercios y Panel). `frontend/public/sw.js` lo registra `components/sw-register.tsx`. El aviso para instalar está en `components/install-prompt.tsx`, con botón nativo en Android e instrucciones en iPhone. Los dos se montan en `app/layout.tsx`. La app de tienda está **diseñada y no empezada**: `docs/app-nativa.md` (Capacitor 8, `mobile/` todavía no existe, ~5 semanas, USD 124 el primer año) |
| **Dónde URUKU ya es mejor** | No obliga a instalar: el que cruza el puente una vez entra por un link o un QR. Cada cambio de la web llega sin publicar versión |
| **Hallazgo** | `install-prompt.tsx` muestra un **emoji** en iPhone («Tocá compartir (⬆️)…»), contra la regla de marca de AGENTS.md §6. Además la clave de localStorage todavía se llama `encontralo_install_dismissed`, aunque eso es cosmético |
| **Propuesta** | (a) Reemplazar el emoji por `<Ic n="compartir">` o el que corresponda del catálogo. **S, P1.** (b) Hacer las apps como dice `app-nativa.md`, pero **después** de publicar Términos y Privacidad (§3), que Apple y Google exigen. Lo que justifica la app son los **avisos** («llegó una oferta del local que guardaste»), no estar en la tienda por estar. **L, P3** |

## 2. Buscador arriba más limpio

| | |
|---|---|
| **Avellaneda** | Header mínimo: logo, avisos, favoritos, locales seguidos e iniciar sesión. Abajo, **«Búsquedas frecuentes»** como chips (`/r?query=baggy`). El menú tiene 5 rubros grandes (Mujer, Hombre, Niños, Más) |
| **URUKU hoy** | `components/uruku-shell.tsx`. Primera fila: logo, **redes**, clima, cotización, menú (Guía, Mapa, Ofertas, Novedades, Cambio), ciudad, Ingresar y tema. Segunda fila: el buscador («¿Qué estás buscando?»). Tercera: `CatNav` (rubros de la base). En la home se suma una cuarta: `AccesosCiudad` (10 chips de servicios). Son **cuatro franjas antes del título** |
| **Dónde URUKU ya es mejor** | El buscador entiende sinónimos y no le importan los acentos (migraciones 0049/0051). Los accesos llevan a servicios reales del mapa |
| **Propuesta** | (a) **Sacar las redes del header**: ya están en el pie y en el celular empujan todo hacia abajo. **S, P1.** (b) Placeholder con ejemplos («Probá: zapatillas, celulares, farmacia»). **S, P1.** (c) Chips **«Lo más buscado»** sacados de la tabla `busquedas` (0034). Un admin los aprueba y nunca se muestra cuántas veces se buscó cada uno (S-01). Reemplazan a `CatNav` en la home, que pasa a ser un botón «Todos los rubros». **M, P2.** (d) Mantener los accesos de servicios: son el diferencial de URUKU y no se tocan |

## 3. Redes sociales al pie

| | |
|---|---|
| **Avellaneda** | Pie con Facebook, Instagram y TikTok, **Preguntas frecuentes**, **Términos y condiciones**, Contacto, «Tengo local en Flores» y «Ver como mayorista» |
| **URUKU hoy** | **Ya las tiene**, arriba y en el pie (`SocialLinks` en `uruku-shell.tsx` y `uruku-ui.tsx`): TikTok, Instagram, Facebook y YouTube @uruku.bo, y una red sin URL no se dibuja. Lo que **falta** son Términos y Privacidad: el comentario del pie dice que «vuelven cuando estén escritos», pero ya están escritos en `docs/legal/terminos.md` y `politica-privacidad.md`, sólo que no publicados |
| **Dónde URUKU ya es mejor** | WhatsApp de URUKU en el pie, «Cómo se usa URUKU», agentes autorizados y las ciudades |
| **Propuesta** | (a) Publicar `/terminos` y `/privacidad` y enlazarlos desde el pie. Es requisito de las apps (Apple 5.1.1) y del aviso P2P, y se publican tras una lectura del abogado (S-02). **S-M, P1.** (b) Cambiar «Cómo se usa URUKU» por «Preguntas frecuentes» o sumar los dos: es lo que la gente busca en un pie. **S, P2.** (c) Pendiente del handoff del 3/10: el handle de YouTube todavía dice `@Uruku-Bermejo` |

## 4. Categorías y carrusel de destacados

| | |
|---|---|
| **Avellaneda** | «Categorías recomendadas» con foto (Mujer, Hombre, Niños, Blanquería) y subcategorías en cada una. Tres banners grandes (envíos, liquidación, fiesta). **No vimos** una sección de locales destacados: el local aparece dentro de la tarjeta del producto |
| **URUKU hoy** | Los rubros salen de la base (`CatNav`, `/[city]` y `/[city]/[category]`). Los destacados (comercios con estrella y sus fotos) ya están en un carrusel, pero **mezclados dentro de «Novedades»** (`components/tarjetas-promo.tsx`) con la farmacia de turno, los baños, el servicio de URUKU, Dax y «Aparecé en URUKU». En producción hoy ese carrusel era casi todo «Destacado» |
| **Dónde URUKU ya es mejor** | Los destacados rotan al azar en cada visita, nunca se dice cuántos hay y la categoría tiene página propia indexable por ciudad |
| **Propuesta** | (a) **Separar «Comercios destacados»** en su propio carrusel, arriba de Novedades. Así «Novedades» vuelve a ser novedades y el plan pago tiene una vidriera que se le puede mostrar al comerciante. **S, P1.** (b) Una fila de **8 rubros con ícono grande** en la home (los más buscados de la ciudad) en lugar de la tira de texto. **S, P2.** (c) Banners de campaña (liquidación, día de la madre): **no por ahora**. Sin un equipo que los renueve se quedan viejos, y un banner vencido se ve peor que no tener ninguno |

## 5. Productos con precio

| | |
|---|---|
| **Avellaneda** | El producto es el centro. Precio mayorista, «precio por menor», compra mínima (3 unidades; 10 para envío), talles, colores, «Más del vendedor» y «También podría interesarte». El precio se ve siempre |
| **URUKU hoy** | Precio **sólo en ofertas**: `precio`, `moneda` y `descuento_pct` en la home (`app/page.tsx`), en `/ofertas` y en la vidriera de la ficha (`galeria-tienda.tsx`, con «Reservar» y WhatsApp). La ficha tiene «Qué podés encontrar acá» en texto (sin precio) y «Ver catálogo», un link externo que sólo se muestra si el comercio es de confianza. Los **productos de Reservalo** (`/tienda`) tienen precio, pero están **escondidos de Mi comercio desde el 6/10** (memoria de planes) |
| **Dónde URUKU ya es mejor** | Tiene la **cotización del día**: puede mostrar «≈ $ ARS» al lado de un precio en Bs, que es justo lo que pregunta el que viene de Argentina |
| **Riesgo** | Un precio viejo en una ficha es una promesa rota que paga URUKU, no el comercio. En Avellaneda lo carga y lo mantiene el local, que vive de eso. En URUKU la mayoría de los comercios no tiene cuenta y los carga un agente |
| **Propuesta** | (a) Mantener la regla: **precio obligatorio sólo en la oferta**, que ya vence. (b) **Precio opcional con fecha** en las fotos de la vidriera, sólo para comercios con cuenta («Bs 220 · actualizado hace 3 días»). Se esconde solo a los 30 días sin actualizar (S-03). **M, P2, con OK del dueño.** (c) **«≈ $ ARS» al lado de todo precio en Bs** en ciudades de frontera, con la cotización de `lib/cambio.ts`. **S, P2.** (d) Reactivar Reservalo como catálogo: **no por ahora**. Duplica la vidriera, que ya hace el mismo trabajo con fotos, y suma un sistema que mantener |

## 6. Videos que al tocar van a TikTok u otras redes

| | |
|---|---|
| **Avellaneda** | «Videos destacados» en carrusel con «Ver todos», más «Videos» en la barra de abajo. Los videos se **hostean en su propio dominio** (`videos.avellanedaaltoque.com`). En la home **no vimos** links a TikTok ni Instagram, y no pudimos confirmar adónde lleva el toque |
| **URUKU hoy** | Franja **«Videos de URUKU»** (`components/videos-uruku.tsx` + `video-uruku-card.tsx`). Al tocar, el video se reproduce **ahí mismo** (no baja nada antes, `preload="none"`). Abajo están «Ver en TikTok / Instagram / Facebook / YouTube» y «Ver el comercio» o «Ver el rubro», más JSON-LD `VideoObject` para Google. En la home de producción **no apareció** porque todavía no hay videos publicados (los workers están apagados, memoria de contenido). Además, la home tiene una **segunda** sección de video, «Recorrimos Bermejo» (`getVideosPromo`, `<video controls>`), y la ficha muestra los videos del comercio en la vidriera |
| **Dónde URUKU ya es mejor** | Ir derecho a TikTok **saca al comprador del sitio** y le pide la app o el login de TikTok. El reproductor propio lo deja en URUKU, a un toque del WhatsApp del comercio, y la red queda como opción. Es igual o mejor que lo de Avellaneda, y además posiciona en Google |
| **Propuesta** | (a) **Unificar las dos secciones de video** de la home en una sola. **S, P2.** (b) Página **`/videos`** con «Ver todos»: scroll vertical tipo reels, cada video con su comercio y el botón de WhatsApp. **M, P2.** (c) No cambiar a «tocar y salir a TikTok». **No conviene**: perdés al comprador justo cuando estaba interesado |

## 7. Bloques de ofertas y novedades

| | |
|---|---|
| **Avellaneda** | «Te va a encantar» (productos con precio, precio tachado y «6% OFF»), «**Ofertas por vencer · Última oportunidad**» (carrusel) y un bloque de productos con el logo, el nombre y la dirección del local |
| **URUKU hoy** | «Ofertas destacadas» (grilla fija de 4, con `-%` y precio) y «Novedades» (carrusel: primero las de URUKU, después las de los comercios y los destacados). Las dos se **ocultan si están vacías**, así que hoy en producción no se ven las ofertas. Las ofertas tienen vencimiento (`vencimientoFmt` en `lib/types.ts`) |
| **Dónde URUKU ya es mejor** | La oferta lleva al comercio con WhatsApp y «Reservar». La moderación y los comercios de confianza (AGENTS.md §4) evitan que se publique basura |
| **Propuesta** | (a) Tira **«Vencen hoy / Últimos días»** con las ofertas que vencen en 48 h. **S, P2.** (b) Mostrar el **local y su zona** en cada tarjeta de oferta (ya lleva `zona_nombre` como etiqueta): no tocar. (c) Sin ofertas, en lugar de esconder la sección, una sola línea: «Todavía no hay ofertas hoy en {ciudad}. Mirá los comercios en el mapa». **S, P2.** (d) Lo que más mueve la aguja es operativo: que los agentes consigan **una oferta por semana** de los comercios con WhatsApp (S-04) |

## 8. Qué muestra cada comercio

| Dato | Avellaneda | URUKU hoy (`app/comercios/[slug]/page.tsx`) | Propuesta |
|---|---|---|---|
| **Local físico vs. «sólo venta online»** | En la tarjeta: dirección («Av. Avellaneda 3636») o «SOLO VENTA ONLINE» | Sólo un caso especial para **taxis** sin parada (`sinParada`: «En toda la ciudad, se pide por WhatsApp»). Un comercio sin local no tiene cómo decirlo | Campo **`attention_mode`**: `store` (con local) / `online_only` («Atiende sólo por WhatsApp») / `delivery` («Va a domicilio»). Si no tiene local, la ficha esconde «Cómo llegar» y el comercio no aparece en el mapa. Regla 11 de AGENTS.md: la columna nace privada, así que hay que darle el `grant select`. **M, P2** |
| **Verificado** | «Tienda oficial» + «Tienda verificada». La FAQ describe un «estricto proceso de verificación» con visitas periódicas. Muestra también seguidores, me gusta, visitas y una calificación de 4.8 | Estrella **«Verificado por URUKU» = plan pago al día** (`estrella-verificado.tsx`). La tilde `verificado` (la pone el admin) y `fuente='campo'` (lo cargó un agente) **no se ven en público** | **Separar las dos cosas.** La estrella pasa a decir «**Destacado**» (es publicidad) y «**Datos verificados por URUKU · visitado el 12/10**» sale de `verificado`/`fuente='campo'`. Hoy un comprador puede leer «verificado» como «es de confianza» cuando en realidad significa «pagó». Avellaneda verifica sin cobrar el sello. **S, P1, decide el dueño (P-01)** |
| **Info del local** | Dirección, horarios (en otra pestaña), contacto, email, Instagram y Facebook del local, «Ver mapa» | **Más completo**: horario con «abierto ahora» y aviso de horario estimado, dónde queda, WhatsApp, teléfono, monedas que acepta, pedido mínimo, redes, cómo llegar, QR, «Responde», farmacia de turno, «Lo que suma» (pasero, envíos, factura, talles especiales), canal de WhatsApp y catálogo | Sumar **formas de pago** (efectivo, QR, transferencia, tarjeta): Avellaneda lo muestra y su FAQ dice que se puede filtrar por eso. Hoy URUKU sólo tiene `monedas_aceptadas`. **S-M, P2** |
| **Productos del local** | Catálogo con precio, «Más del vendedor» y ordenar por relevancia | Vidriera con fotos y ofertas con precio (`galeria-tienda.tsx`), «Qué podés encontrar acá» y catálogo externo | Ver §5 (b) |
| **Seguir / favoritos** | «Seguir tienda», con avisos | «Guardar» (`GuardarBoton`, `/guardados`), sin avisos | Los avisos llegan con la app (§1) o con Web Push. No antes |
| **Calificaciones, seguidores y visitas públicas** | Sí | No (las visitas sólo las ve el comerciante en «Mi comercio») | **No conviene por ahora.** Con pocos contactos por ficha, «2 seguidores» aleja más de lo que atrae. «Responde» ya cumple ese papel con datos reales |
| **Formas de envío** | «Hace envíos», «Todos los medios de transporte a cargo del comprador» y un mínimo para envío por producto | Sello «Hace envíos», que sale de una columna llamada **`envios_internacionales`** (0011). El nombre dice una cosa y el sello otra: el comprador no sabe a dónde envía | Ver §9 |

## 9. Envíos

| | |
|---|---|
| **Avellaneda** | **No envía la plataforma, envía el local**: «Todos los locales realizan envíos a todo el país». El transporte lo paga el comprador y hay un mínimo por producto. Lo anuncia con un banner, «Envíos a todo el país» |
| **URUKU hoy** | (1) Sellos «Hace envíos» y «Tiene pasero» en la ficha. (2) El **servicio propio de encargos y guardería** ya tiene spec completa (`docs/servicio-encargos-guarderia.md`: compra por encargo, retiro de compras ya pagadas, depósito, código de retiro y garantía de custodia). Por ahora sólo existe la **tarjeta del carrusel** que abre WhatsApp al 67 671 888 (`tarjetas-promo.tsx`). `/encargos` **no existe** todavía. (3) La spec **excluye** que URUKU envíe o traslade mercadería a Argentina: «URUKU no cruza mercadería» |
| **Dónde URUKU ya es mejor** | Para el que viene de Argentina, «te lo compramos y te lo guardamos hasta que vengas» resuelve más que un envío, y no expone a URUKU a la aduana (ver §8.5 de la spec: RG ARCA 5910/2026 y el control del «contrabando hormiga») |
| **Propuesta** | (a) Reemplazar el sello por **«Cómo entrega»** con varias opciones: retira en el local / envío dentro de la ciudad / envío a otras ciudades de Bolivia (por encomienda) / envía a Argentina. Más un texto opcional «Mínimo para envío». Lo declara el comercio y URUKU no lo garantiza, con el mismo aviso P2P (S-05). **M, P2.** (b) **Lanzar `/encargos` MVP** según la spec (formulario, panel, depósito y retiro). Es la respuesta de URUKU a «envíos», y además monetiza. **L, P2.** Primero hay que cerrar P-01 de la spec (dónde paga el anticipo un cliente argentino). (c) URUKU haciendo envíos propios a Argentina: **no conviene**, por riesgo aduanero y legal; ya está excluido. (d) Envíos de URUKU dentro de Bolivia: **fuera de alcance** hasta que el encargo funcione en Bermejo |

## 10. Lista priorizada

| # | Mejora | Punto | Esfuerzo | Prioridad |
|---|---|---|---|---|
| 1 | Sacar el emoji del aviso «Instalá URUKU» en iPhone | 1 | S | P1 |
| 2 | Separar la estrella «Destacado» (pago) de «Datos verificados por URUKU» (visita) | 8 | S | P1 (decide el dueño) |
| 3 | Carrusel propio de «Comercios destacados», fuera de Novedades | 4 | S | P1 |
| 4 | Header más limpio: redes sólo al pie y placeholder con ejemplos | 2 | S | P1 |
| 5 | Publicar Términos y Privacidad en el pie, más Preguntas frecuentes | 3 | S-M | P1 |
| 6 | «≈ $ ARS» al lado de cada precio en Bs (frontera) y tira «Vencen hoy» | 5, 7 | S | P2 |
| 7 | Una sola sección de videos en la home y página `/videos` con «Ver todos» | 6 | S + M | P2 |
| 8 | Ficha: «Cómo atiende» (local / sólo WhatsApp / domicilio), «Cómo entrega» y formas de pago | 8, 9 | M | P2 |
| 9 | «Lo más buscado» desde `busquedas`, aprobado por un admin | 2 | M | P2 |
| 10 | `/encargos` MVP (spec lista) | 9 | L | P2 |
| 11 | Precio opcional con fecha en la vidriera (comercios con cuenta) | 5 | M | P2 (con OK del dueño) |
| 12 | Apps en Google Play y App Store (Capacitor, `docs/app-nativa.md`) | 1 | L | P3 (después del #5) |

**No conviene tomar:** carrito y checkout (URUKU no es ecommerce y la propia Avellaneda tampoco cobra), envíos hechos por URUKU, calificaciones, seguidores o visitas a la vista del público, banners de campaña sin alguien que los renueve, rubros tipo «Mujer / Hombre / Niños» (sirven para un mayorista de ropa, no para una ciudad), y mandar los videos directo a TikTok.

**Supuestos a validar**
- **S-01** «Lo más buscado» muestra hasta 8 términos aprobados a mano, sin cantidades, y se renueva cada semana.
- **S-02** Los textos de `docs/legal/` se publican tal como están, previa lectura del abogado. La versión de encargos (§6 bis) se suma recién cuando el servicio salga.
- **S-03** El precio de una foto de la vidriera se esconde solo a los 30 días sin actualizar.
- **S-04** El objetivo operativo inicial es una oferta por semana por comercio con WhatsApp, conseguida por los agentes.
- **S-05** «Cómo entrega» es un dato que declara el comercio, con el mismo aviso P2P. URUKU no lo verifica.

## 11. Preguntas que sólo puede contestar el dueño

| # | Pregunta | Recomendación |
|---|---|---|
| P-01 | ¿El sello público de confianza tiene que seguir atado al pago? | **No.** «Destacado» para el pago y «Datos verificados» para la visita del agente. La confianza no se vende |
| P-02 | ¿Se muestran precios fuera de las ofertas (en las fotos de la vidriera), aunque alguno pueda quedar viejo? | **Sí**, pero sólo para comercios con cuenta, con fecha, y que se escondan solos (S-03) |
| P-03 | ¿Seguimos mostrando «Envía a Argentina» como dato del comercio, o lo sacamos por el riesgo aduanero? | Mostrarlo **como dato del comercio**, con el aviso de franquicia de la guía. Confirmar con el abogado |
| P-04 | ¿Arrancamos ya con `/encargos`? Depende de P-01 de su spec: ¿hay una cuenta en pesos para cobrar el anticipo? | Sí, si hay una cuenta en pesos. Sin ella, el cliente de Orán no puede pagar a distancia |
| P-05 | ¿Están las cuentas de Apple y Google y los 12 testers con Android para las apps? | Abrirlas cuando estén publicados Términos y Privacidad (#5) |

### Decisiones del dueño (5/11/2026)

| # | Respuesta | Qué cambia |
|---|---|---|
| P-01 | **Sí, sigue atado al pago** | No se separa «Destacado» de «Datos verificados»: la estrella sigue siendo del plan |
| P-02 | **No** | Precios sólo en ofertas |
| P-03 | **Sí** | Se mantiene el sello «Envía a Argentina» |
| P-04 | **Sí** | `/encargos` es la próxima feature (spec existente) |
| P-05 | **No están, hay que crearlas** | Apple Developer US$ 99 por año y Google Play US$ 25 una vez (cuentas personales nuevas de Google: 12 testers durante 14 días). Las apps esperan esas cuentas y Términos y Privacidad publicados |

Primer incremento (sin la separación del sello): emoji del aviso de iPhone, header más limpio con redes sólo al pie, carrusel propio de comercios destacados, «≈ $ ARS» junto al precio en Bs en ciudades de frontera, tira «Vencen hoy» y mensaje cuando no hay ofertas, una sola sección de videos. Términos y Privacidad se publican cuando el dueño apruebe los textos de `docs/legal/`.

## 12. Fuentes

**Avellaneda a un Toque** (consultadas el 3/11/2026):
- Home: https://www.avellanedaauntoque.com
- Producto: https://www.avellanedaauntoque.com/p/0MLAT4N-conjunto-deportivo?&r=P5FD8N8
- Info de la tienda: https://www.avellanedaauntoque.com/p/0MLAT4N-conjunto-deportivo?r=P5FD8N8&view=tienda
- Tienda del local: https://www.avellanedaauntoque.com/s/EN3RFK-indumentaria-emmu
- Categoría: https://www.avellanedaauntoque.com/?rubro=mujer
- Preguntas frecuentes: https://www.avellanedaauntoque.com/preguntas-frecuentes
- `/videos`: https://www.avellanedaauntoque.com/videos (404)
- App Store: https://apps.apple.com/uy/app/avellaneda-a-un-toque/id1596612134
- Google Play: https://play.google.com/store/apps/details?id=com.avellanedaaltoque.aat (la página llegó cortada, sin datos)

**URUKU:** https://uruku.bo (home de producción, 3/11/2026). En el código: `frontend/app/page.tsx`, `components/uruku-shell.tsx`, `components/videos-uruku.tsx`, `components/video-uruku-card.tsx`, `components/tarjetas-promo.tsx`, `components/accesos-ciudad.tsx`, `components/install-prompt.tsx`, `components/sw-register.tsx`, `app/manifest.ts`, `app/comercios/[slug]/page.tsx`, `components/galeria-tienda.tsx`, `components/estrella-verificado.tsx`, `app/[city]/page.tsx`. En la documentación: `docs/app-nativa.md`, `docs/servicio-encargos-guarderia.md`, `docs/legal/`, `content/manuales/uruku.md`.
