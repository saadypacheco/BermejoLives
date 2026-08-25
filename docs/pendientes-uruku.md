# Pendientes — URUKU (prod uruku.bo + QA encontralo.store)

> Lista viva. Prod está **vivo** en uruku.bo. Ver
> [estado-vps-prod-uruku.md](estado-vps-prod-uruku.md) y [deploy-prod-nuevo-vps.md](deploy-prod-nuevo-vps.md).
> La **tienda (Reservalo)** tiene su propio plan: [plan-tienda-reservalo.md](plan-tienda-reservalo.md).
> La **clasificación por IA** y el prompt vigente: [clasificacion-ia.md](clasificacion-ia.md).

## 📍 Situación al 2026-08-25

| | |
|---|---|
| Comercios activos | **270** (tres salidas al campo) |
| Tercera salida | **67 comercios, los 67 analizados** · 0 pendientes |
| Analizados | 269 de 270 · sólo 1 sin ningún rubro real |
| Rubros por comercio | 2,51 promedio · multi-rubro funcionando |
| Rubros en la taxonomía | 4 nuevos (marroquinería, lencería, blanquería, kiosco) · 19 apagados |
| Diccionario de sinónimos | **847 términos** · los 270 comercios con sinónimos · 253 de 258 términos nuevos ya cubiertos |
| **Sin WhatsApp** | **43 de los 67 nuevos** — el número más caro de la tanda |
| Sin nombre real | **3 de 67** en la tercera salida (eran ~100 de 203 antes de `nombre_cartel`) |
| Publicaciones (ofertas) | **1 en total, 0 aprobadas** → el canal está construido y apagado |
| Búsquedas registradas | Muy pocas: la analítica todavía es anécdota |

**La tercera salida cerró bien.** 67 de 67 con productos detectados, **cero fotos
sin mercadería**, ningún comercio en "Otros" y 36 rubros repartidos. Fue la
primera tanda analizada con el prompt completo y se nota justo donde tenía que
notarse: el nombre leído del cartel bajó los "sin nombre" de la mitad de la base
a tres casos.

**El buscador quedó cerrado**: sinónimos de frontera, tolerancia a errores de
tipeo, búsqueda por varias palabras, y los 36 filtros de categoría verificados
uno por uno. **El mapa también**: filtraba sólo por el rubro principal, así que
mostraba menos pines de los que corresponden.

**La limpieza de rubros está hecha y verificada**: `alimentos` pasó de 25
asignaciones a 4 y `hogar` de 25 a 10, sin que ningún otro rubro perdiera una
sola. Ver [clasificacion-ia.md](clasificacion-ia.md) §2.

---

## ⚠️ Dos trampas que ya costaron horas

**El cache de esquema de PostgREST.** Cada migración lo deja viejo. Síntomas: 500
en endpoints con selects embebidos, `PGRST204`, "la tabla no existe" aunque psql
la lea. **Siempre `docker compose restart postgrest` después de migrar.** Y un
embed que falla devuelve `[]` en silencio: quien lo llama no puede distinguir
"no hay datos" de "no pude leer". Un script informó "0 asignaciones sin
respaldo" cuando había 37, y eso se lee como "está todo bien".

**Pushear antes de dar comandos de `git pull`.** Pasó dos veces: el commit estaba
hecho, el pull no traía nada, y el rato siguiente se fue buscando el bug en el
lugar equivocado. Si algo no aparece después de un pull, comparar el hash con
`git log --oneline -3` en el servidor antes de seguir.

---

## 🔴 Ahora / alta prioridad

### 43 de los 67 nuevos no tienen WhatsApp
Es lo más caro que dejó la tanda. Sin WhatsApp el comercio no tiene canal de
contacto ni puede recibir ofertas, así que queda en el mapa como una ficha que
no lleva a ningún lado. Son las **4 farmacias**, los **9 kioscos** y las **8
zapatillerías** entre otros — la lista completa con los códigos sale de la §8 de
`novedades.sql`.

- [ ] Definir cómo se completan: ¿segunda pasada al campo sólo por el número?
      ¿se busca en las fotos del cartel (muchos lo tienen pintado)? Lo segundo
      es barato: la IA ya mira esas fotos.

### Los nombres genéricos son a propósito
Ocho comercios se llaman "Zapatillas Americanas", nueve "Kiosko", y hay "Ropa",
"Licoreria", "Muebleria". **No es un error de carga ni una falla del prompt: los
puso el relevador y es el nombre que se quiere.** En Bermejo muchos locales no
tienen otro, y el genérico describe lo que son.

Lo que sí importaba —que el comprador los encuentre— **ya funciona**: el buscador
matchea contra el nombre del comercio. Lo que estaba roto era el filtro por
categoría, y era un bug del diccionario, no del nombre: el patrón de
`calzado-usado` decía `zapatilla americana` en singular y no llegaba a
"Zapatillas Americanas". Arreglado en la **0063**.

- [ ] Queda una decisión de interfaz, no de datos: ocho fichas con el mismo
      nombre son indistinguibles en la lista de resultados. Si molesta, se
      resuelve mostrando la calle o una referencia al lado del nombre — no
      renombrando los locales.

### Decisiones de taxonomía que quedaron abiertas
La IA pidió 9 categorías nuevas en los 67 (§2 de `novedades.sql`). **No se creó
ninguna**, por la misma razón que se decidió con licorería: partir una categoría
para uno o dos comercios deja dos filtros que no filtran.

- [ ] **ropa de fiesta** (2 comercios) es la que primero va a pasar el umbral.
- [ ] **gimnasio** (1) es la que más incomoda: no es un negocio de venta y hoy
      está en "Deportes y fitness" junto a los que venden pelotas. Se arregla
      igual de bien sacándolo de ahí que creándole un rubro.
- [ ] **pinturería** (1) hoy cae en ferretería, que la cubre.
- [ ] Las otras seis ya están cubiertas (`pollería` → comida rápida, `calzado de
      trabajo` → calzado, `artículos de plástico` → bazar) o no son un rubro
      (`polirrubro` es la ausencia de uno). Y **`lencería` la pidió de nuevo**:
      confirma que la 0057 acertó.
- [ ] **Licorería**: sigue en "Bebidas y licorería". La tercera salida trajo una
      (`URUKU-BHH6`), así que el conteo va subiendo pero todavía no justifica
      partir la categoría.
- [ ] **"Deportes y fitness" se llevó 19 de 67.** Sospechoso para una ciudad de
      frontera: lo más probable es que esté absorbiendo *ropa deportiva*. Mismo
      patrón que `ropa` con 110. Verificar antes de que crezca más.

### El normalizador de subcategorías corta la última sílaba
En la §3 de `novedades.sql` aparecen `muebl` y `cepillo de dient`. El reordenado
alfabético (`americana ropa`, `mujer ropa`) **es a propósito** —así "bolsos y
mochilas" y "mochilas y bolsos" cuentan como uno solo, arreglo del 22/8— pero el
recorte no. Sólo afecta al conteo, no a lo que se muestra.

- [ ] Mirar `subcategoria_norm`: parece un stemmer demasiado agresivo.

### Ofertas por WhatsApp — grupos (en diseño)
El canal de WhatsApp **ya existe** en el código (WAHA + webhook con HMAC +
`ingest.py` → publicación `pendiente` + moderación). Lo que falta es adaptarlo al
modelo de **grupos** y llenar el hueco de las imágenes.

Modelo pedido: un grupo por comerciante con **uno de los 3 números operativos** de
URUKU + **2 testigos** (principal y backup). El número principal de la marca **no
entra a ningún grupo**. También se usan grupos ya existentes de comerciantes,
metiendo uno de los operativos, para juntar volumen al principio.

Lo que hay que construir:
- [ ] **Identificar por grupo, no por remitente.** Hoy `ingest.py` identifica al
      comercio por el teléfono de quien manda. En un grupo el remitente es una
      persona cualquiera y el `from` es el ID del grupo. Hace falta detectar
      `@g.us`, sacar el remitente real de `_data.key.participant`, y una tabla
      `comercio_wa_grupos` (grupo → comercio). **Ventaja sobre el número:** el
      comerciante cambia de celular sin perder nada y pueden publicar varias
      personas del mismo local.
- [ ] **Ignorar a los propios.** Los mensajes de los 3 operativos y los 2 testigos
      no pueden generar ofertas, o cada vez que alguien de URUKU escriba en el
      grupo se crea una publicación fantasma.
- [ ] **Bajar la imagen a storage propio.** 🚨 Hoy `imagen_url = payload.media_url`,
      que es la URL **interna y efímera** de WAHA. Acá **la foto es la oferta**:
      sin esto las ofertas llegan con la imagen rota. Es el pendiente que el otro
      proyecto (MentorComercial) marca como el hueco a llenar. Ya existen
      `procesar_imagen()` y `guardar_foto_local()` para reusar.
- [ ] **Retención de `waha_media`.** El volumen crece sin límite; con video llena
      el disco.
- [ ] **Decidir cómo se ata el grupo al comercio:** por código `URUKU-XXXX` mandado
      adentro del grupo (reusa lo que ya funciona) o a mano desde el admin.
- [ ] **Verificar que la sesión de WAHA esté vinculada** (`/api/sessions`). Con 1
      publicación en toda la base, es probable que nunca se escaneara el QR — y eso
      explicaría el cero sin que falte una línea de código.

### Ofertas por los otros dos canales
- [x] **Panel del comercio** → `origen: "panel"`, publica directo si es confiable.
- [ ] **Perfil publicador (`/contenido`)**: hoy sólo maneja cotizaciones, clima y
      videos promo. **No puede cargar ofertas** — es el único canal que falta.

### Plan con atención 24/7 (nuevo, a diseñar)
- [ ] Un plan que ofrezca **atención 24/7** al comprador para los locales que lo
      necesiten. Definir primero **qué significa**: ¿un bot que responde fuera de
      horario? ¿derivación a un número de guardia? ¿respuesta automática con el
      horario y los productos? Impacta en `horario.ts` (hoy sólo muestra
      abierto/cerrado) y en [monetizacion-planes-uruku]. **Sin definirlo no se
      puede estimar.**

### Datos que quedan por revisar
- [x] ~~Limpiar los rubros cajón de sastre~~ — hecho y verificado (§2 de
      clasificacion-ia.md).
- [x] ~~Procesar la tercera salida~~ — 67 de 67 analizados, con sinónimos y
      clasificados. Cero en "Otros".
- [x] ~~`nombrar_desde_cartel.py`~~ — **ya no hace falta**: el prompt lee el
      cartel desde el 23/8 y quedaron 3 comercios sin nombre en toda la tanda.
      Se resuelven a mano.
- [x] ~~Revisar las categorías propuestas~~ — hecho, ver arriba.
- [ ] **`completar_rubros.py` sigue SIN APLICAR.** El diccionario ya está
      corregido (migraciones 0061 y 0062, ver §2.8 de clasificacion-ia.md) pero
      falta lo último antes de dar el `APLICAR=1`:
      - medir cuánto ruido mete el blob de sinónimos al clasificar (§8 de
        `auditar_diccionario.sql`, sin correr todavía);
      - decidir el umbral para los rubros de especialización. Con corte en
        **≥4 palabras distintas**, lencería + marroquinería + blanquería pasan
        de 244 propuestas a 23, y los que quedan afuera no pierden nada:
        siguen en `ropa`, que es donde el comprador los busca.
      **Nada de esto tocó un solo comercio todavía**: `rubro_palabras` no lo lee
      ni el buscador ni el mapa ni las fichas, sólo los informes y ese script.

### Ciudades
- [ ] **Habilitar Santa Cruz, La Paz y Tarija** en el selector. Ya existen en la
      base desde `0008_ciudades.sql` con `activa = false`:
      ```sql
      update ciudades set activa = true where slug in ('santa-cruz','la-paz','tarija');
      ```
      Ojo: el selector es sólo la puerta. Sin comercios cargados, quien elija esas
      ciudades ve el mapa vacío — conviene decidir si se abren antes o después de
      tener algo que mostrar.

---

## 🎨 Diseño (menor, no bloquea)
- [ ] **Input del buscador en modo oscuro:** se pierde, hay muy poco contraste
      contra el fondo. Debería leerse claramente dónde se escribe.
- [ ] **Barra de redes / clima / cotización en escritorio:** queda pegada debajo
      del logo y se ve rara. En móvil está bien; el problema es el ancho grande.
- [ ] **Puntos del mapa:** sigue sin convencer (pendiente de la sesión del 2026-08-22).
- [ ] **Adornos del mapa:** el editor ya está (Admin › Adornos). Falta **ubicar**
      las chalanas y los lapachos, y revisar si los dibujos convencen antes de
      cargar veinte.
- [ ] **Imágenes por ciudad:** el campo existe (`ciudades.hero_url`, `foto_url`)
      y Santa Cruz / La Paz / Tarija usan las de Bermejo hasta que haya fotos
      propias. `update ciudades set hero_url = '...' where slug = '...'`.
- [ ] **`<title>` de /software** sigue diciendo "Bermejo" fijo: Next resuelve
      metadata antes de conocer la cookie de ciudad.
- [ ] **Dar contexto a la IA antes de analizar:** hoy el análisis mira sólo las
      fotos. `prod_obs_human` entra en la deducción de rubros pero NO llega al
      prompt. Un campo "el relevador dice que…" sería un cambio chico.

## 🟠 Redirects de los dominios secundarios

- [ ] `uruku.com.bo`, `urucu.bo`, `urucu.com.bo` → **301 a `uruku.bo`**. Agregarlos como zonas en
      Cloudflare + **Redirect Rules**, o A al VPS + router de redirect en Traefik.

## 🟡 Infra / hardening
- [ ] **Fijar la versión de Traefik** (hoy `traefik:latest` por compat con Docker 29). Ver la versión
      con `docker exec traefik traefik version` y pinearla en el compose.
- [~] **Backups** del Postgres: script listo (`selfhost/backup.sh`, dump+gzip+rotación 14 días).
      Falta en el VPS: copiar a `/docker/backup.sh`, `chmod +x`, y cron `0 3 * * *`. Probar restore.
- [ ] **SSH hardening**: agregar SSH key y desactivar login por password (key-only).
- [ ] **Monitoreo básico**: disco (en QA estaba al 66%), RAM, uptime. Uptime Kuma u similar.

## 🔒 Seguridad (rotación)
- [ ] Prod arrancó con **secretos nuevos** (init_prod_env) ✅. Pero los **viejos expuestos**
      (service_role, password de DB, etc.) siguen en **QA** → **rotarlos en QA** también.
- [x] `WEBHOOK_SECRET` seteado en prod (init_prod_env). Confirmar/rotar en QA.

## 🟢 QA (encontralo.store) — espejo de prod
- [ ] Aplicar en QA los mismos cambios de **Reservalo** cuando se hagan en prod
      (basePath `/tienda`, **sacar Supabase** — Auth/Storage/DB → disco de URUKU + self-host).
- [ ] Redeploy de **Reservalo de QA** a `encontralo.store/tienda`.
- [ ] Rotar los secretos expuestos (ver arriba).

## 🛍️ Tienda (Reservalo) — proyecto aparte
- [ ] Ver **[plan-tienda-reservalo.md](plan-tienda-reservalo.md)**: sacar Supabase de Reservalo
      (imágenes al disco de URUKU, auth por token de URUKU, base self-host), reservas/carrito.
      **Regla:** todo cambio que se haga en prod se replica en QA.

## 💡 Ideas para explorar (registrar, pensar después)
- **Producción de contenido automatizada desde WhatsApp** (ver abajo).
- **Falloff del mapa (fase 2):** que los negocios que no pagan vayan cayendo del mapa para
  mantenerlo fresco. Ver [[monetizacion-planes-uruku]].
- **Más valor para el comprador:** botón "Llamar" (tel:) para mayores, orden por distancia en
  la lista, "cerca mío", historial de vistos, alertas de ofertas guardadas.
- **Producción de contenido automatizada desde WhatsApp.** Que el comerciante mande
  **texto / audio / fotos / videos** por WhatsApp y todo se guarde en la base (como el
  proyecto **MentorComercial** en `C:\repos\proyectosClaude\MentorComercial`, donde ya se
  ingestaba y almacenaba ese material). A partir de eso, **generar contenido** para redes
  y publicaciones del sitio (posts, reels, descripciones de producto) — con IA:
  transcripción de audio (Whisper, ya está en URUKU), generación de texto, y armado de
  piezas. Reusa el bridge WAHA + el webhook de ingesta que ya existen. **Analizar
  factibilidad y esfuerzo.** Encaja con los planes: "publicar por WhatsApp" (Plan 2/3) y
  el marketplace de contenido para creadores. Ver [[monetizacion-planes-uruku]].

## ✅ Hecho
- [x] **Taxonomía revisada (2026-08-24):** 4 rubros creados con su vocabulario,
      19 apagados (eran ciudades argentinas y duplicados del modelo viejo).
      Diccionario corregido: kiosco vs comida rápida, variantes de "kiosquito",
      licorería.
- [x] **El mapa respeta multi-rubro:** filtraba por el rubro principal, así que
      "Calzado" dejaba afuera a los que venden calzado con otro principal. Los
      chips salen de los comercios cargados: ninguno puede devolver cero.
- [x] **Un solo buscador en /buscar** (había dos cajas de texto y dos filas de
      chips) y los filtros reaccionan a la URL.
- [x] **Cambiar de ciudad cambia el sitio**, no sólo el título: imágenes desde
      la base, buscador parado en esa ciudad, textos sin "Bermejo" fijo.
- [x] **Ver la foto en grande desde el admin** (por Portal: `.glass` rompe
      `position: fixed`).
- [x] **Buscador (2026-08-22/23):** diccionario de sinónimos de frontera (la IA los
      aporta sola al analizar), subcategorías normalizadas, `pg_trgm` para errores de
      tipeo, búsqueda por varias palabras (entra por O, ordena por Y), y el índice
      con `unaccent` que se había perdido — "sartén" no se encontraba nunca.
      Verificado producto por producto: cero `NO ENCUENTRA NADA`.
- [x] **Los 36 filtros de categoría verificados** uno por uno contra la cantidad
      real de comercios de cada rubro. El síntoma "no filtran" era que el buscador
      leía la URL sólo al montarse.
- [x] **Analítica del buscador (2026-08-23):** `leads.busqueda_id` ata el contacto a
      la búsqueda que lo produjo → se puede medir si el buscador acierta (posición
      del elegido, términos que terminan en contacto, búsquedas con resultados que
      nadie tocó). Informe: `supabase/analitica_buscador.sql`.
- [x] **Panel de catálogo** (Admin › Catálogo): rubros y productos con su conteo,
      los rubros vacíos resaltados, y lo que la gente buscó sin encontrar.
- [x] **Adornos del mapa:** chalanas, lapachos y el uruku en el pie. Editor en
      Admin › Adornos (clic para ubicar, arrastrar para mover).
- [x] **WhatsApp en la segunda pantalla del alta**, con previsualización del mensaje
      que le va a llegar al comercio. Queda también en el formulario.
- [x] VPS prod (KVM4, Brasil), Docker + Traefik, DNS Cloudflare, URUKU desplegado y vivo (HTTPS OK).
- [x] Rediseño URUKU (shell, home, buscar, ficha, mapa, mi-negocio) + selector de ciudad.
- [x] Reservalo: código migrado a `/tienda` parametrizado por `DOMAIN` (falta sacar Supabase).
- [x] **Moderación humana + IA (2026-08-15):** cola abierta al **publicador** (`require_moderador`
      = admin/moderador/publicador); asistente IA `moderar_publicacion()` (Gemini) →
      `aprobar/rechazar/dudoso`, sin API key cae a "dudoso" (nunca aprueba a ciegas); endpoint
      `POST /moderacion/publicaciones/{id}/revisar-ia`; panel admin con botón ✨ por ítem +
      "Revisar todas con IA" (auto-aprueba solo confianza ≥0.8). +4 tests (136 verdes). Diseño:
      [moderacion-ia-humana.md](moderacion-ia-humana.md).
- [x] **Home (2026-08-15):** botón "Ingresar" (comprador → /perfil · comercio → /mi-comercio);
      "Lo mejor de hoy" oculta filas en 0.
- [x] **Valor para el comprador (2026-08-15):** indicador **"Abierto/Cerrado ahora"**
      (`lib/horario.ts`, parser heurístico de texto libre, hora local) en ficha + tarjeta del
      mapa; **botón Compartir** (Web Share + fallback copiar); filtro **"Abierto ahora"** en el mapa.
- [x] **Captura de referidos:** `?ref=` se guarda (first-touch) y viaja al alta del comprador.
