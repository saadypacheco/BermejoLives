# Inventario de datos personales de URUKU

> **Borrador para revisión de un abogado. No es asesoramiento legal.**
> Verificado contra el código en `main` (`d35aa08`) el 19/10/2026. Es la **fuente** de la
> Política de privacidad (`politica-privacidad.md`): cada dato de la política tiene una fila acá
> (el ID va en un comentario `<!-- inv: … -->` de la política) y cada fila acá aparece en la política.
> Migraciones: `selfhost/postgres-init/` (idénticas en `supabase/migrations/`).

**Pendientes [completar]:** país del servidor (Hostinger, prod `srv1900330`, `docs/estado-vps-prod-uruku.md:11`) · si `GEMINI_API_KEY` es de pago o gratis · si `OPENAI_API_KEY` está cargada en prod · si `selfhost/backup.sh` ya corre en el VPS · si la difusión a Facebook/Instagram está encendida en prod.

**Base (columna «Base»):** **C** = consentimiento (lo da la persona) · **S** = necesario para el servicio que la persona pidió · **O** = operación y seguridad del sitio (interés legítimo; figura que Bolivia no define: a validar) · **L** = obligación legal o contable.
**Retención:** «Hoy» = lo que hace el código. «Prop.» = plazo propuesto (supuesto, ver §K). Todo usa baja lógica (`activo=false`, AGENTS.md §5): **hoy nada se borra salvo donde se indica**.

## A. Comercios (dueños y encargados)

| ID | Dato | De quién | Dónde | Para qué | Quién lo ve | Cuánto se guarda | Base |
|---|---|---|---|---|---|---|---|
| A1 | Nombre del comercio, descripción, rubro, horario, modalidad, monedas, datos fronterizos | Comercio | `comercios` (`0001_init.sql:28-33`, `0011_plataforma_frontera.sql:17-23`) | Ficha pública y buscador | **Público** (grant por columna `0145_comercios_columnas_publicas.sql:44-55`) | Hoy: sin plazo. Prop.: mientras el comercio exista; baja → anonimizar en 30 días (S-03) | S |
| A2 | WhatsApp, teléfono, email del comercio | Dueño/encargado | `comercios.whatsapp/telefono/email` (`0001_init.sql:39-41`) | Que el comprador lo contacte (`wa.me`); ingreso a Mi comercio | **Público** (`0145:45`). El email también es público | Ídem A1 | S |
| A3 | Redes (TikTok, Facebook, Instagram), web, link de canal/catálogo | Comercio | `0001_init.sql:44-47`, `0133_segunda_pasada.sql:11-15` | Ficha pública | Público | Ídem A1 | S |
| A4 | Dirección, calle, puesto, ubicación GPS del local | Comercio (la toma el agente o el dueño) | `0001_init.sql:51-54`, `0127:20`, `0039:19`; alta `api/campo.py:197-198,322-323`; por WhatsApp `services/ingest.py:567-570` | Mapa y «cómo llegar» | Público | Ídem A1 | S |
| A5 | Fotos y videos del local y productos (pueden mostrar personas) | Comercio / agente | Disco del backend (`services/imagenes.py:83-100`) + `comercio_fotos`, `comercio_videos` (`0030_galeria_comercio.sql:7-25`), `comercios.logo_url/portada_url` | Ficha, mapa, análisis IA (ver I1) | Público (`0030:34-43`) | Hoy: hasta que se borra o reemplaza (borrado físico: `services/fotos_galeria.py:300-305`). Las fotos se recomprimen y **pierden EXIF/GPS** (`imagenes.py:68-80`) | S + licencia (Términos §7) |
| A6 | Ofertas/publicaciones: foto, texto, precio | Comercio (o el explorador de URUKU, ver A7) | `publicaciones` (`0001_init.sql:97-126`) | Feed y buscador | Público si `estado='aprobado'`; `raw`, `moderado_por`, `ia_*` privados (`0149:199-203`) | Hoy: sin plazo; archivo por tope del plan (`api/moderacion.py:3080`) | S |
| A7 | Ofertas del **explorador**: foto y precio de un local que no se sumó, publicada a su nombre, contacto al número de URUKU | Local fotografiado | `publicaciones.origen='explorador'`, `contacto_whatsapp` (`0075_explorador_de_ofertas.sql:19-34`); `ingest.py:510-511` | Llenar el feed | Público tras moderación (siempre a cola) | Ídem A6 | O (a validar, H-08) |
| A8 | Consentimiento del dueño para aparecer (sí/no + fecha) | Dueño | `comercios.consentimiento_dueno(_en)` (`0155_consentimiento_dueno.sql:12-13`); `campo.py:199,341-342` | Prueba de que aceptó | Equipo (privado) | Mientras exista el comercio + prop. 5 años (S-05) | C |
| A9 | Quién lo cargó (email del agente) y hora del celular | Equipo URUKU | `comercios.cargado_por` (`0013:5`), `capturado_en` (`0138:17`) | Control de calidad del alta | Equipo (privado, `0145:5-17`) | Ídem A1 | O |
| A10 | Números autorizados a publicar (dueño, empleado) con etiqueta | Dueño/empleados | `comercio_numeros` (`0043_comercio_numeros.sql:15-27`) | Identificar quién publica por WhatsApp | Sólo backend | Hoy: baja lógica. Prop.: borrar al dar de baja el número | S |
| A11 | Grupo de WhatsApp atado al comercio (id y nombre del grupo) | Comercio | `comercio_wa_grupos` (`0065:30-37`), `comercios.wa_jid` (`0001:63`) | Saber de qué comercio es cada mensaje | Sólo backend (`0065:45-46`) | Hoy: sin plazo | S |
| A12 | Cuenta de Mi comercio: nombre, email (opcional), **hash** de la clave, código temporal y su vencimiento | Dueño | `comercio_usuarios` (`0004:16-24`, `0022:4-6`, `0029:14`, `0137:105`) | Ingresar a Mi comercio | Sólo backend (nunca la clave en claro) | Mientras exista la cuenta | S |
| A13 | Código del comercio `URUKU-XXXX` | Comercio | `comercios.codigo` (`0044:15`), privado (`0148`) | Publicar por WhatsApp | Sólo equipo | Ídem A1 | S |
| A14 | Plan, vencimiento, cortesía, pagos (monto, método, referencia, período, quién registró) | Comercio | `comercios.paga_hasta/plan_cortesia` (`0012:9`, `0143:40`), `pagos` (`0012:16-28`) | Cobrar y aplicar el plan | Equipo (privado) | Prop.: 5 años tras el pago [confirmar con contador] (S-05) | S + L |
| A15 | Eventos de la cuenta e interés en un plan (nota del agente) | Comercio | `comercio_eventos` (`0149:167-173`, `0151:18`) | Auditoría y seguimiento comercial | Equipo | Hoy: sin plazo | O |
| A16 | Pedido de cambio de número: número nuevo, foto actual del local, GPS, mensaje | Dueño | `solicitudes_cambio_numero` (`0024:8-19`, `0025:4-7`); `api/comercio.py:226-260` | Recuperar la cuenta | Equipo | Prop.: 12 meses tras resolverlo (S-04) | S |
| A17 | Mensajes del equipo al comercio (bandeja) | Equipo → comercio | `mensajes` (`0018:8-17`); hoy sólo escribe el admin (`api/moderacion.py:1104`) | Avisos al comercio | Comercio y equipo | Mientras exista el comercio | S |
| A18 | Contadores «¿te contestó?» (sí/no de 90 días) y estadísticas de su ficha | Comercio (dato agregado) | `comercios.contacto_ok/no` (`0120:22-23`) | Orden en el buscador; panel | Público (`0145:53`) | Se recalcula sobre 90 días | O |

## B. Compradores con cuenta

| ID | Dato | De quién | Dónde | Para qué | Quién lo ve | Cuánto se guarda | Base |
|---|---|---|---|---|---|---|---|
| B1 | Celular (E.164), hash de la clave, código temporal, fecha de verificación | Comprador | `usuarios` (`0026:5-14`, `0029:13`, `0137:74,106`); `api/usuario.py:40-67` | Cuenta y favoritos en cualquier equipo | Sólo backend | Hoy: sin plazo. Prop.: hasta la baja + 30 días (S-03) | S |
| B2 | Consentimiento para ofertas (tilde + fecha; pendiente hasta verificar) | Comprador | `usuarios.consentimiento_en/_pendiente` (`0137:75-76`); `repository.py:831-866` | Prueba del permiso para avisos | Equipo | Mientras exista la cuenta + prop. 5 años como prueba (S-05) | C |
| B3 | Código de origen `ref` (QR/volante/grupo por el que llegó) | Comprador | `usuarios.ref` (`0037:6`) | Medir qué QR trae gente | Equipo (conteos) | Ídem B1 | O |
| B4 | Favoritos (comercios guardados) | Comprador | `favoritos` (`0026:16-22`, `0137:89`) | Mostrarlos | El comprador | Ídem B1 | S |

## C. Visitantes del sitio (sin cuenta) — no se guarda IP ni user-agent

| ID | Dato | Dónde | Para qué | Quién lo ve | Cuánto | Base |
|---|---|---|---|---|---|---|
| C1 | Página vista, número al azar de la pestaña, dominio de origen, ciudad, `ref`, primera página | `visitas` (`0130:20-36`); `api/campo.py:932-949` | Contar visitas | Equipo (conteos) | Hoy: sin plazo. Prop.: 24 meses (S-04) | O |
| C2 | Texto de lo que se busca y qué comercios aparecieron | `busquedas` (`0034:2-7`), `busqueda_comercios` (`0036`); `campo.py:989-1001` | Mejorar el buscador; «términos» en Mi comercio | Equipo; el comercio ve los términos que lo encontraron | Ídem C1 | O |
| C3 | Clic de contacto (tipo, comercio, búsqueda, `ref`) y respuesta «¿te contestó?» | `leads` (`0011:41-46`, `0055:26`, `0114:14`, `0120:17-18`); `campo.py:890-905,956-980` | Estadística del comercio | Equipo; el comercio ve totales | Ídem C1 | O |
| C4 | Preguntas al asistente «Uruku Ayuda» o al chatbot de un comercio, respuesta, id al azar del navegador, 👍/👎 | `asistente_conversaciones` (`0106:25-39`) | Responder y aprender preguntas sin respuesta | Equipo; **el comercio ve las de su chatbot** (`frontend/lib/comercio.ts:585`) | Prop.: 12 meses (S-04) | S |
| C5 | Reclamo: nombre, contacto (email/WhatsApp), comercio, mensaje | `reclamos` (`0021:5-16`); `campo.py:1011-1020` | Responder el reclamo | Equipo | Prop.: 24 meses tras responder (S-04) | S |

## D. Mensajes de WhatsApp que recibe el número de URUKU (WAHA, sólo lectura)

| ID | Dato | De quién | Dónde | Para qué | Quién lo ve | Cuánto | Base |
|---|---|---|---|---|---|---|---|
| D1 | Mensaje completo: id, remitente (número/identificador), texto, tipo, link a la foto, **crudo** de WhatsApp, por dónde entró, qué pasó | **Cualquiera que escriba** al número o en un grupo donde está (comerciante, empleado, comprador que confirma, desconocido) | `wa_inbox` (`0001:135-146`, `0099:35-39`, `0104:9`); `ingest.py:471-485` | Publicar, confirmar cuentas, auditar | Equipo (Recepción) | Hoy: sin plazo. Prop.: 12 meses; `sin_comercio` 90 días (S-04) | S (comerciante) / O (resto, a validar) |
| D2 | Ubicación compartida por WhatsApp → actualiza el GPS del comercio | Comerciante | `ingest.py:567-575` | Mapa | Público (como A4) | Como A4 | S |
| D3 | Código `CONFIRMAR-XXXXXX` (prueba de que el número es tuyo) | Comprador/comerciante | `ingest.py:459-461`, `usuarios`/`comercio_usuarios.reset_code_confirmado_at` (`0029`) | Verificar el número | Backend | El código vence en 15 min (`usuario.py:63`); la fecha de verificación queda (B1) | S |

## E. Datos obtenidos de terceros

| ID | Dato | De quién | Dónde | Para qué | Quién lo ve | Cuánto | Base |
|---|---|---|---|---|---|---|---|
| E1 | Teléfono, nombre, grupo de WhatsApp y ciudad de **compradores de un Excel** de grupos de compras | Compradores que no se registraron | `contactos_base` (`0117:17-28`); `services/contactos.py` | Contar de qué grupos vienen y cruzar con `usuarios`. **No se les escribe** (`0117:5-12`) | Sólo backend; el panel muestra conteos | Hoy: sin plazo. **Recomendado: borrar** (H-01) | **Ninguna clara** (H-01) |
| E2 | Negocios de OpenStreetMap: nombre, teléfono, WhatsApp, web, horario, dirección, punto | Negocios (dato público, licencia ODbL) | `comercios_importados` (`0066:29-66`) | Saber qué falta relevar | Equipo | Mientras sirva al relevamiento | O |

## F. Equipo de URUKU (agentes, moderadores, admins)

| ID | Dato | Dónde | Para qué | Quién lo ve | Cuánto | Base |
|---|---|---|---|---|---|---|
| F1 | Email, nombre, hash de contraseña, ciudad, roles, último acceso | `usuarios_panel`, `usuario_roles` (`0126:46-64`); `agentes` (`0125:14-24`, tabla vieja) | Ingreso al panel | Admins | Mientras trabaje + prop. 12 meses | S |
| F2 | Qué cargó, dónde y cuándo; marcas en calles (email + nota) | A9, `calles_marcas.actor` (`0152:45-59`) | Control del trabajo de campo | Admins | Ídem F1 | O |
| F3 | Audio del agente «¿qué vende?» (no se guarda: se transcribe y se descarta) | `api/campo.py:62-101` | Llenar el alta | — | No se guarda | S |

## G. Seguridad y operación

| ID | Dato | Dónde | Para qué | Cuánto | Base |
|---|---|---|---|---|---|
| G1 | Intentos de ingreso: número, cuentas, **IP**, resultado | `clave_fallos` (`0137:147-155`) | Bloquear ataques (5 fallos/15 min) | Hoy: sin plazo. Prop.: 90 días (S-04) | O |
| G2 | Logs del backend: incluyen **IP** al verificar cuenta (`usuario.py:111`) y **teléfonos** de mensajes ignorados (`ingest.py:455-456,558`) | Logs de Docker en el VPS (sin rotación configurada: `docker-compose.prod.yml`) | Diagnóstico | Hoy: sin plazo. Prop.: 30 días (H-09) | O |
| G3 | Errores y tiempos de carga (ruta, mensaje, contexto) | `error_logs`, `perf_events` (`0027:7-37`) | Monitoreo propio | **30 días** (`services/observabilidad.py:16-17,76-81`) | O |
| G4 | Copias de seguridad de toda la base | `/docker/backups` (`selfhost/backup.sh:16-27`) | Recuperación | **14 días** de rotación; **[completar: si ya está instalado]** (`docs/pendientes-uruku.md:717-718`) | O |

## H. En el navegador o el teléfono de la persona (no llega al servidor salvo indicación)

| ID | Dato | Dónde | Para qué | Cuánto |
|---|---|---|---|---|
| H1 | Cookie de ciudad elegida (la deduce el navegador con tu ubicación, sin mandarla) | `components/city-selector.tsx:9,55-62` | Mostrar tu ciudad | 1 año |
| H2 | Sesión del comprador, del comercio y del agente (token + número) | localStorage: `lib/usuario.ts:57-58`, `lib/comercio.ts:51-52`, `lib/campo.ts:68` | Mantener la sesión | Hasta cerrar sesión |
| H3 | Tu ubicación (lat/lng) para «cerca mío» | localStorage `uk-ubicacion` (`lib/ubicacion.ts:12-13,47`) | Ordenar por cercanía **en el teléfono** | 10 minutos |
| H4 | `ref` de origen, id del asistente, contactos para «¿te contestó?», reservas armadas, tema, último horario, número de pestaña | `lib/ref.ts:55`, `components/asistente.tsx:40-43`, `lib/contestaron.ts:23`, `lib/reservas.ts:65`, `components/contador-visitas.tsx:30-38` (sessionStorage) | Funciones del sitio | `ref` 30 días; pestaña hasta cerrarla; resto hasta borrarlo |

## I. Terceros que reciben datos (dependencias externas)

| ID | Tercero | Qué recibe | Dónde | País | Nota |
|---|---|---|---|---|---|
| I1 | **Google (Gemini API)** | Fotos de ofertas y de locales, texto de publicaciones y descripciones, preguntas al asistente | `services/vision.py:315-346,388-417`; `clasificador.py:49-75,99-215`; `asistente.py:1002-1010`; `sinonimos.py:179-187`; `main.py:116-136` | Fuera de Bolivia (EE. UU. u otro) | En el plan **gratis** Google usa el contenido para mejorar productos y lo pueden leer revisores humanos; en el **pago**, no (términos del 28/04/2026). Exige 18+ (H-03) |
| I2 | **WhatsApp / Meta** | Todo lo que se escribe en chats, grupos y comunidades; URUKU lo lee vía WAHA (no oficial) | `docker-compose.prod.yml:84-85` (`waha_sessions`) | Fuera de Bolivia | Las personas aceptan los términos de WhatsApp aparte |
| I3 | Meta (Facebook, Instagram, canal de WhatsApp de URUKU) | Ofertas aprobadas (foto + texto del comercio) | `services/difusion.py:209`; `core/config.py:90-114` | Fuera de Bolivia | [completar: si FB/IG está encendido] |
| I4 | Hostinger (VPS) | Toda la base y las fotos | `docs/estado-vps-prod-uruku.md:11,30` | **[completar: país del servidor]** | Proveedor de infraestructura |
| I5 | Cloudflare | Tráfico del sitio (IP, páginas) al pasar por su red | `docs/estado-vps-prod-uruku.md:18-24` | Fuera de Bolivia | `api` y `db` no pasan por Cloudflare |
| I6 | OpenStreetMap / unpkg | IP del navegador al bajar mapas y la librería del mapa | `lib/mapa-tiles.ts:42` (respaldo si no hay tiles propios), `lib/mapa-visual.ts:145-149` | Fuera de Bolivia | Tiles propios en `tiles.uruku.bo` cuando está configurado |
| I7 | OpenAI (Whisper) | Audio del agente | `api/campo.py:85-101` | EE. UU. | **Sólo si** `OPENAI_API_KEY` está cargada; si no, se transcribe en el VPS [completar] |

## J. Previsto por spec, todavía NO en el código (`docs/grupos-por-comercio.md`, v2 19/10)

| ID | Dato | Dónde (spec) | Para qué | Cuánto | Base |
|---|---|---|---|---|---|
| J1 | Miembros de las comunidades de compradores y comercios: número o identificador (LID), entrada/salida, cruce con cuenta o comercio, **consentimiento = entrar** | `wa_community_members` (`grupos-por-comercio.md:284-300`) | Avisos y atar el comercio a su número | Mientras sea miembro; prop. al salir 30 días (S-03) | C |
| J2 | Pares identificador↔número y eventos de grupo crudos | `wa_lid_map`, `wa_group_events` (`:225-243`) | Saber quién entró | Prop. 12 meses | O |
| J3 | Fotos de números desconocidos en disco **privado** | `WA_RECEIVED_DIR` (`:395-396,443`) | No perder fotos de comercios sin atar | **30 días** | O |
| J4 | Nombre de quien atiende el comercio (va a la descripción del grupo, nunca al sitio) | `comercios.contact_name` (`:344-346`) | Grupo del comercio | Ídem A1 | S |
| J5 | Foto y credencial (QR) del agente | `usuarios_panel.photo_url`, `agent_credentials` (`:382-384`) | Que el comerciante verifique al agente | Ídem F1 | C (agente) |

## K. Hallazgos a resolver antes de publicar la política y supuestos

| # | Hallazgo | Evidencia | Recomendación |
|---|---|---|---|
| H-01 | Números de compradores de terceros sin consentimiento | `0117:3-15` | Borrar o reducir a conteos por grupo **antes** de publicar. Si se queda, la política lo declara (E1) |
| H-02 | El alta de campo toma consentimiento **por defecto en sí** y crea el comercio aunque sea no | `api/campo.py:199,341` | Default `False`; sin consentimiento, comercio no público |
| H-03 | Gemini: confirmar plan pago; sus términos piden 18+ y no apps accesibles a menores | I1 | Plan pago + revisión legal del asistente público |
| H-04 | Sin borrado ni retención (salvo G3); la baja lógica choca con el derecho a supresión | §A-G | Procedimiento manual de borrado/anonimización ante pedido (S-03) + jobs de retención |
| H-05 | Sin pantalla de privacidad/términos, sin aceptación en autoregistro ni cuenta, sin botón para retirar el consentimiento o borrar la cuenta | `frontend/app` (no hay coincidencias) | Enlace en pie, casilla en altas, «Borrar mi cuenta» en /perfil |
| H-06 | `/comunidad` dice «Tu número lo ven los del grupo» | `grupos-por-comercio.md:72` (P12) | Alinear con la política (§6) |
| H-07 | No hay QR de cobro hoy; `pagos.metodo` admite `efectivo` | `grupos-por-comercio.md:69` (P9); `0012:21` | Términos §6 no puede prometer QR hasta que exista |
| H-08 | El explorador publica a nombre de locales que no se sumaron | A7 | Términos §4: retiro a pedido en 48 h |
| H-09 | Logs de Docker con teléfonos e IP, sin rotación | G2 | `logging: max-size/max-file` |

**Supuestos (a confirmar por el dueño):**
- **S-01** Responsable: una sola persona o empresa titular de URUKU en Bolivia [completar].
- **S-02** El email de contacto de privacidad es distinto del personal del dueño [completar].
- **S-03** Ante una baja: se oculta al instante y se borra o anonimiza en 30 días, salvo pagos y pruebas de consentimiento.
- **S-04** Plazos propuestos: mensajes de WhatsApp 12 meses (`sin_comercio` 90 días); asistente 12 meses; visitas, búsquedas y reclamos 24 meses; intentos de ingreso 90 días; pedidos de cambio de número 12 meses.
- **S-05** Pagos y pruebas de consentimiento 5 años (plazo contable a confirmar con contador).
- **S-06** Cuentas de comprador y comunidades: sólo mayores de 18 años.
