# Qué falta — lista ordenada

> **Para operar los teléfonos —configuración, qué no hacer, y qué hacer cuando
> algo se rompe— está el
> [manual operativo](manual-operativo-whatsapp.md).**
>
> Al 17/9/2026. Ordenado por lo que **desbloquea a lo demás**, no por tamaño.
> Lo de arriba hace que lo de abajo tenga sentido.

## Lo que se hizo desde la lista del 10/9

Para no volver a buscarlo: deploy y `.env` de prod ✅ · perfil de WAHA
"Uruku" ✅ · prueba punta a punta de alta + oferta ✅ · Recepción, Difusión y
Demanda en el admin ✅ · miniaturas ✅ · buscador (rubro visible, orden total
en la base, zombis de React) ✅ · el sitio se recarga solo en cada deploy ✅ ·
volante al grupo, QR en la ficha, tarjeta de mesa ✅ · **Uruku Ayuda** (Nivel
0/1/3, saber local, Admin › Ayuda) ✅ · el asistente del comercio (Pro) ✅ ·
saber local de compras en Bermejo (14 entradas con fuentes) ✅ · `/cambio` con
conversor ✅ · dónde estoy y "cerca de mí" ✅ · **planes** en `/planes` y Admin
› Planes, sin canal, con chatbot desde Pro ✅ · `scripts/deploy-prod.sh` ✅.

**Del 16 y 17/9 (revisión completa del sitio):** el home nuevo ✅ · la guía
(`/guia`) ✅ · **los servicios son rubros** (baños, estacionamientos, cajeros,
wifi: una sola forma de cargar, como cualquier comercio) y el rubro principal
va primero (0113) ✅ · sin cifras de comercios para el público ✅ · el
cartel de permiso de ubicación con los pasos de cada aparato ✅ · 404 propia
y `/software` → `/planes` ✅ · el WhatsApp de contacto real (75314737) en el
alta y el volante ✅ · **`?ref=` en los tres QR** (volante, mesa, ficha) y
`?ref=fb/ig` en la difusión, con **Llegadas por QR en Admin › Panel** (0114)
✅ · la Ayuda contesta por rubro («¿dónde como?», «taxi», «farmacia de
turno») ✅ · cada ficha con su título y su foto al compartirla, y
`sitemap.xml` ✅ · 0115: el principal sale de la subcategoría (carnicerías,
kioscos, coca, Rústico) ✅ · deuda §5 cerrada (`_PLANES`, `types.ts`,
`planes_con_ingesta`, `deploy-all.sh`, contador de Ofertas) ✅ ·
`scripts/revision-sitio.mjs` recorre todas las rutas en compu y celular ✅.

---

## 0. Hoy mismo, porque lo de abajo lo necesita

- [ ] **Desplegar lo del 17/9** con la 0114 y la 0115:
  `bash scripts/deploy-prod.sh --sql selfhost/postgres-init/0114_de_donde_llego.sql --sql selfhost/postgres-init/0115_el_principal_es_lo_que_dice_la_subcategoria.sql frontend backend`
- [ ] **El 500 al guardar un comercio en el admin** (visto el 16/9, sin
  traceback todavía). Reproducirlo y mandar:
  `docker compose -f docker-compose.prod.yml logs --tail 200 backend | grep -B 5 -A 40 Traceback`
- [x] Cotización cargada (17/9). Falta decidir **quién la carga cada mañana**
  (el Anfitrión se la pide a una casa de cambio por WhatsApp; 20 segundos).
- [ ] **Facebook e Instagram**: la app de Meta → `FACEBOOK_PAGE_ID`,
  `FACEBOOK_PAGE_TOKEN`, `INSTAGRAM_USER_ID`. **Ahora es una promesa vendida**:
  Destacado dice "tus ofertas en las redes de URUKU". Sin token, la cola
  espera y nada sale. `difusion-redes.md` tiene el paso a paso.
- [x] La URL de Facebook en `/contenido` ✅ (17/9).
- [ ] **El estado de la frontera** en `/contenido`, cada mañana: al 17/9 el
  dato tenía dos días y la guía lo dice.
- [ ] **La Comunidad de WhatsApp de compradores** (18/9): crearla desde el
  Samsung (Anfitrión) con la tablet de segundo admin —grupo de avisos +
  un grupo por ciudad— y **pegar el enlace de invitación en `/contenido` ›
  Redes › Comunidad de WhatsApp**. Recién ahí aparece el botón «Unite a la
  comunidad» en el home, la guía y `/cambio`, y `/comunidad` muestra el QR.
  Después: subir el Excel en **Admin › Compradores** y darle a cada
  administrador de grupo su enlace `?ref=grupo-…` con el QR de la comunidad.

## 1. Los teléfonos (manual operativo, sección 2)

- [ ] **PIN de dos pasos** en la tablet y en el Samsung, con correo de recuperación.
- [ ] **Perfil URUKU también en el Samsung** (es el que crea los grupos).
- [ ] Copia de seguridad de WhatsApp en Google Drive, en el Samsung.
- [ ] **Los dos números nuevos del 15/9**: el Respaldo 1 (**67671888**, ya con
  WhatsApp) a `WA_NUMEROS_PROPIOS` y callado en cada grupo; el Explorador
  (**67677803**) con WhatsApp, y `WA_NUMEROS_EXPLORADOR=59167677803`. PIN de dos
  pasos en los dos. El 72900149 y el 68727944 quedan fuera de todo.
- [ ] Activar la eSIM del Respaldo 2 (68727584) y registrarle WhatsApp.
  **En el 67991916, NO** (va a la API oficial).
- [ ] **Probar el Plan B** (API oficial) con el número de prueba de Meta —
  `whatsapp-arquitectura-y-escala.md` tiene la guía.

## 2. Los datos, que es lo que hace que todo lo demás sirva

- [ ] **Los horarios.** Uno solo cargado de 1.000 activos. Ahora pesa más que antes: "¿qué hay
  abierto?", "¿está abierto Rústico?" y "casas de cambio abiertas ahora" del
  asistente contestan "no tiene horario" hasta que estén. Empezar por las 27
  casas de cambio, los restaurantes y los que tienen grupo.
- [ ] **El saber local que ninguna fuente publica** (Admin › Ayuda ›
  Agregar): cómo se llama la avenida de venta por unidad, dónde está la feria
  mayorista y de qué hora a qué hora, qué galerías hay y qué vende cada una,
  dónde queda el Mercado Central, el precio de la chalana hoy, dónde están los
  cambistas, la fecha del aniversario. Es lo que convierte "andá a la feria"
  en "la feria es en tal calle, de 4 a 9".
- [ ] **Mirar Admin › Ayuda › Sin respuesta** cada dos o tres días y contestar.
  Es la cola que hace crecer al asistente.
- [ ] **43 comercios sin WhatsApp** (de los 67 nuevos): sin número no hay lead.
- [ ] **194 comercios en la cola de revisión de rubros.** La 0115 resuelve
  sola los que tienen la subcategoría clara (carnicería, kiosco, coca,
  peluquería, restaurante); el resto sigue en Admin › Rubros. Y dos a mano
  que son vidriera: **CITY TRIKE** tiene `taxis` de secundario (aparece en
  el chip Taxis: destildarlo en su ficha) y **Vidriería Pacheco** queda en
  ferretería porque no hay rubro vidriería.
- [ ] **Cargar los servicios como comercios**: cajeros (hay cero), más baños,
  estacionamientos y wifi, y los taxis reales. Desde campo o Admin ›
  Comercios, con el rubro Baños públicos / Estacionamientos / Cajeros y
  bancos / Wifi gratis / Taxis. Los chips del home y la Ayuda los muestran
  apenas están.
- [ ] **927 de 1.000 comercios sin WhatsApp** y **431 que se llaman
  "Comercio"**: es lo que más se nota en la Ayuda y en las listas.
- [ ] **Nombres "Comercio"**: cientos de fichas se llaman así. Son a propósito
  (cargados desde la calle), pero en el asistente y en las listas se ven
  como cinco iguales. Cuando se les ponga nombre, todo mejora solo.

## 3. Antes de salir a difundir

- [ ] **Topes de la recompensa al explorador** (por publicación, por persona,
  por día) y **de la recompensa por traer usuarios**. Existe la atribución,
  no el tope: no prometer plata antes de esto.
- [ ] **`usuarios.ultima_actividad`** — no se guarda; sin eso no se sabe si un
  usuario traído volvió.
- [x] **`?ref=` en los QR** ✅ (17/9, 0114): `volante-<slug>`, `mesa-<slug>`,
  `ficha-<slug>`, y `fb`/`ig` en la difusión. **Admin › Panel › Llegadas por
  QR (30d)** los cuenta por clase y muestra el más escaneado. Los volantes
  y tarjetas impresos ANTES del 17/9 no llevan el `ref`: reimprimir los que
  se repartan de acá en más.
- [ ] **Panel de marca**: faltan preguntas al asistente por día y 👍/👎
  (están en la base: `asistente_conversaciones`), y comercios con papel.
- [ ] La base de 4.316 contactos: decidido el 13/9, **todavía no** (y nunca
  como difusión desde los números de la marca).

## 4. Producto — lo que sigue

- [ ] **Agente Catálogo** (cargar productos desde fotos), primero para uso
  interno. Es lo que hace rentable dar de alta a un comercio de Bs 1.250.
- [ ] **Agente Marketing**: cada lunes, los cuatro borradores de la semana
  (lo más buscado, los comercios nuevos, la mejor oferta, una pregunta del
  asistente) en Admin › Difusión para aprobar con un clic.
  `estrategia-marca-uruku.md` §2.
- [ ] **El asistente con la ubicación**: "¿qué farmacia hay cerca?" contesta
  por la ciudad, no por la cuadra. Mandarle la posición con la pregunta y
  ordenar por distancia.
- [ ] **La ficha del gratis, reducida.** Los planes venden "el gratis sólo
  aparece en el mapa" y hoy muestra la ficha completa. Es una promesa de
  menos, no de más, así que no urge — pero es lo que diferencia a Publica.
- [ ] **Caída del mapa** de los que no pagan tras la gracia (fase 2, decidido
  el 13/8).
- [ ] **Acciones** del agente (crear oferta, cambiar precio) con confirmación
  y auditoría.
- [ ] **WhatsApp multi-tenant** — bloqueado por Meta (Tech Provider). Se
  investiga en paralelo; nada del producto depende de esto.

## 5. Deuda técnica, chica y concreta

- [x] `/buscar?of=1` cuenta lo que muestra («N con ofertas») ✅.
- [x] `_PLANES`, `types.ts`, `planes_con_ingesta` (ahora los planes pagos de
  la tabla), `deploy-all.sh` borrado ✅.
- [x] `?ref=fb` / `?ref=ig` en la difusión ✅.
- [ ] `usuarios.ultima_actividad`: sigue sin guardarse (sólo importa cuando
  exista la recompensa por traer usuarios).

---

## Lo que yo haría en este orden

1. **Desplegar lo del 17/9** (0114 + 0115) y mandar el traceback del 500 (0).
2. **Los tokens de Facebook e Instagram** (0): es lo único que hace que
   Destacado cumpla lo que dice.
3. **Horarios de casas de cambio, restaurantes y los que tienen grupo**, y el
   saber local de la calle (2). Es lo que hace que el asistente conteste de
   verdad, y es lo que ninguna base ni ningún modelo puede saber por vos.
4. **Los teléfonos** (1), antes de sumar más grupos.
5. **`?ref=` en los QR** (3), antes de repartir tarjetas: si no, no se puede
   saber si sirvieron.
6. Recién ahí, el Agente Catálogo y el Agente Marketing (4).
