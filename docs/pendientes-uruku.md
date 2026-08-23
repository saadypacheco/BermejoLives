# Pendientes — URUKU (prod uruku.bo + QA encontralo.store)

> Lista viva. Prod está **vivo** en uruku.bo. Ver
> [estado-vps-prod-uruku.md](estado-vps-prod-uruku.md) y [deploy-prod-nuevo-vps.md](deploy-prod-nuevo-vps.md).
> La **tienda (Reservalo)** tiene su propio plan: [plan-tienda-reservalo.md](plan-tienda-reservalo.md).
> La **clasificación por IA** y el prompt vigente: [clasificacion-ia.md](clasificacion-ia.md).

## 📍 Situación al 2026-08-23

| | |
|---|---|
| Comercios cargados | **203** (dos salidas al campo) |
| Analizados por IA | 202 · sólo 1 sin ningún rubro real |
| Rubros por comercio | 2,69 promedio · multi-rubro funcionando |
| Diccionario de sinónimos | 697 términos · 203 de 203 comercios con sinónimos |
| Sin nombre real | ~100 de 203 — **es normal en Bermejo**, no es error de carga |
| Sin WhatsApp | ~49 con nombre |
| Publicaciones (ofertas) | **1 en total, 0 aprobadas** → el canal está construido y apagado |
| Búsquedas registradas | Muy pocas: los informes de analítica todavía son anécdota |

**El buscador quedó cerrado esta semana:** sinónimos de frontera (remera/polera/
camiseta devuelven lo mismo), tolerancia a errores de tipeo, búsqueda por varias
palabras, y los 36 filtros de categoría verificados uno por uno.

---

## 🔴 Ahora / alta prioridad

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

### Limpieza de datos (scripts listos, falta correr y revisar)
- [ ] `limpiar_rubros.py` — saca los rubros amplios sin respaldo (alimentos, hogar).
- [ ] `completar_rubros.py` — agrega los 78 rubros que los productos piden.
- [ ] `nombrar_desde_cartel.py` — lee el nombre del cartel en las fotos ya sacadas.
- [ ] Revisar las 4 categorías que la IA propuso: `artículos de plástico`,
      `calzado de trabajo`, `lencería`, `ropa de fiesta`. Sólo **lencería** tiene
      respaldo (3 comercios con esa subcategoría).

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
