# Pendientes — URUKU (prod uruku.bo + QA encontralo.store)

> Lista viva. Prod está **vivo** en uruku.bo. Ver
> [estado-vps-prod-uruku.md](estado-vps-prod-uruku.md) y [deploy-prod-nuevo-vps.md](deploy-prod-nuevo-vps.md).
> **Reservalo se deja de usar** (29/8): todo vive en URUKU. Ver
> [decision-uruku-sin-reservalo.md](decision-uruku-sin-reservalo.md).
> La **clasificación por IA** y el prompt vigente: [clasificacion-ia.md](clasificacion-ia.md).

> **La lista corta y ordenada de qué falta está en
> [que-falta.md](que-falta.md).** Este archivo es el detalle y el porqué de cada
> cosa; aquél es el orden en que conviene hacerlas.

## 📍 Situación al 2026-09-03

> Handoff con el estado completo: [handoff-2026-09-03.md](handoff-2026-09-03.md)

| | |
|---|---|
| Comercios activos | **888** (eran 680 el 28/8, 270 el 25/8) |
| Rubros | **56** — 12 creados el 2 y 3/9 |
| Asignaciones de rubro | **2.440** · `completar_rubros.py` aplicado |
| **Con horario** | **0 de 888** — el dato que más diferencia, y el único que nadie puede deducir |
| Publicaciones (ofertas) | **1 en total** → el canal está construido y apagado |
| Canal de WhatsApp | WAHA emparejado, **sin grupos creados** · faltan 3 chips |
| Mapa | tiles propios en `tiles.uruku.bo` · arranca sólo con adornos |
| Pantallas | `/mapa` y `/buscar` **unificadas**; `/mapa` redirige |

**Lo que falta no es código, es carga.** Los horarios son 888 y están a dos
toques cada uno (filtro "Sin horario" + presets + "igual que el anterior"). Las
ofertas necesitan que el canal de WhatsApp arranque. Las fechas del panel de
Vencimientos las tiene que averiguar una persona.

**El buscador y el mapa quedaron cerrados**: una sola pantalla, resultados que
dicen qué vende cada local con lo buscado resaltado, ofertas con foto y precio
en la tarjeta, carrito de reservas sin cuenta, y el mapa servido desde el VPS
propio.

---

## ⚠️ La forma en que este proyecto falla

Hay UN error que apareció **siete veces** en una sola semana, siempre disfrazado
de otra cosa. Vale más que cualquier lista de pendientes, porque es el que hace
perder las horas:

> **Una guarda que se lee como protección y no protege nada. No da error: devuelve
> un resultado plausible.**

Las siete, para reconocer la octava:

| Dónde | Qué parecía | Qué era |
|---|---|---|
| `.limit(250)` en el mapa | la lista completa | 250 de 588; el 58% invisible |
| `.limit(20000)` en `comercio_rubros` | todo | 1000 (tope de PostgREST). El informe propuso 1295 rubros para 599 comercios que ya los tenían |
| `.limit(5000)` en `list_todos_comercios` | todo | entra hoy con 888; a los 1000 el panel muestra 1000 de 1100 |
| `on conflict do nothing` sin índice único | idempotente | cada corrida duplicó el sembrado: 16 filas donde iban 8 |
| `len(relaciones) < len(comercios)` | un guard | compara unidades distintas: 1000 > 886, nunca salta |
| `WA_NUMEROS_PROPIOS=591XXXXXXXX` | configurado | normaliza a `591`: la guarda existe y no cubre a nadie |
| fechas contra UTC | la fecha de hoy | Bolivia es UTC−4: lo que vence hoy figura vencido cuatro horas antes |

Y la variante de la misma familia: **un dato que no llega y se lee como dato
vacío.** Al select del panel le faltaba `horario`, así que el filtro "Sin
horario" habría contado los 888 para siempre y el modal habría mostrado vacío
incluso a los que ya tenían uno. No se notaba porque hoy no hay ninguno cargado:
el bug esperaba a la primera pasada de carga.

**La regla que sale de esto:** ante un número redondo (1000, 250, 500), un cero
tranquilizador o un "está todo bien", medir contra la fuente antes de creerle.
Y al escribir una guarda, preguntarse qué la haría saltar — si no hay respuesta,
es decoración.

### Y dos que son operativas

**El cache de esquema de PostgREST.** Cada migración lo deja viejo. Síntomas: 500
en endpoints con selects embebidos, `PGRST204`, "la tabla no existe" aunque psql
la lea. **Siempre `docker compose restart postgrest` después de migrar.** Y un
embed que falla devuelve `[]` en silencio: quien lo llama no puede distinguir
"no hay datos" de "no pude leer".

**Las migraciones se corren EN ORDEN, y se verifica que corrieron.** En prod se
aplicó la 0070 sin la 0069, y como la 0070 recrea la misma función, la búsqueda
quedó bien y una función de la 0069 nunca se creó. No hubo error: el frontend la
pedía, no existía, y devolvía vacío — se veía una pantalla sin chips, no una
falla.

```sql
select proname from pg_proc where proname in ('buscar_comercios','refinamientos_busqueda');
```

---

## 🟣 Uruku AI — decidido el 10/9

Los dos documentos de análisis, adaptados a lo que URUKU ya tiene, en
[uruku-ai-plan.md](uruku-ai-plan.md). Lo esencial:

- **No se rehace el backend.** Los documentos proponen Node porque no saben que
  existen 621 tests en Python. Se mantiene y se le suma funcionalidad.
- **URUKU no necesita WhatsApp para tener agentes.** Primero adentro del sitio;
  WhatsApp después, como canal. Ser Tech Provider de Meta son meses de trámite
  ajeno y no puede estar en el camino crítico.
- **Plan Empleado Digital creado a Bs 1.250**, con el precio editable desde el
  panel — los costos de un agente 24/7 todavía no están medidos.
- **El Agente Catálogo es lo que da margen**, no una función más: a Bs 1.250,
  si dar de alta un comercio cuesta dos días de carga de datos, el primer mes
  ya se fue.
- **El Agente Analista se puede construir hoy** y es el único: las búsquedas ya
  se registran. "26 personas buscaron esto y no encontraron nada" es una
  consulta, no un modelo — y es el mejor argumento de venta que hay.

- [ ] Informe de demanda (Agente Analista) — sin IA, con datos que ya están.
- [ ] Nivel 0: horario, dirección y teléfono sin modelo.
- [ ] Escribir las preguntas frecuentes, que Uruku Ayuda necesita y no existen.
- [ ] Verificar si WAAC / número compartido entre partners existe de verdad
      para Bolivia antes de planificar nada encima.

## 🟣 La escala de WhatsApp — analizado el 10/9

El detalle entero en
[whatsapp-arquitectura-y-escala.md](whatsapp-arquitectura-y-escala.md). Lo que
hay que retener:

- **Un teléfono no llega a 20.000 grupos**, y se rompe antes por sincronización
  que por baneo. El techo práctico son cientos, no miles.
- **La API oficial de Meta no tiene grupos.** El modelo de un grupo por comercio
  no migra: allá es chat uno a uno. Cada grupo que se crea hoy es trabajo que no
  se transporta.
- **Recibir y contestar por la API oficial es gratis**: sólo se pagan las
  plantillas de marketing que inicia la empresa. La tarifa de Bolivia hay que
  mirarla en Meta, no está inventada acá.
- **Ya está construida la capa** que hace que migrar sea configuración y no
  reescritura, con tests. Se puede probar en paralelo con el número de prueba
  que regala Meta, sin tocar lo que funciona.

- [ ] Poner el segundo administrador del canal (lo único irrecuperable de un
      baneo, y cuesta dos minutos).
- [ ] Dar de alta la app de Meta y probar con el número de prueba.
- [ ] Al pasar los ~300 comercios: decidir chat directo en vez de grupo.

## 🟣 Las seis decisiones a cerrar antes de salir a difundir (10/9/2026)

> Todo esto son decisiones de negocio con consecuencias técnicas, no tareas de
> programación. Están juntas porque comparten una cosa: **si se salen a difundir
> sin cerrarlas, cada una se cierra sola de la peor manera** — el canal se llena
> y la gente lo silencia, el comerciante publica de más y nadie le cobra, el
> que trajo usuarios reclama una plata que nadie puede calcular.

### 1. El canal no aguanta todo lo que manden los vendedores

**El problema, con números.** Un plan Publica son 50 publicaciones al mes. Con
30 comercios en ese plan son 1.500 publicaciones mensuales: **50 por día en el
canal**. Nadie sigue un canal que le tira cincuenta notificaciones diarias — lo
silencia el primer día y lo abandona el tercero.

Y ahí se pierde lo único que no se puede rehacer. Los grupos se vuelven a crear;
los seguidores no vuelven.

**Lo que NO es la solución.** Cambiar de plataforma no arregla nada:

- **WhatsApp Business (la app)** tiene listas de difusión de 256 contactos y —lo
  que la hace inservible— **sólo le llega a quien tenga tu número agendado**. Es
  peor que el canal, no mejor.
- **Telegram** no tiene límites y es gratis, pero en Bermejo no lo usa nadie.
  Una herramienta perfecta a la que no entra el público no sirve.

El canal es la plataforma correcta. **El problema no es dónde se publica: es
cuánto.**

**La salida, y de paso es plata.** Un canal es un boletín, no una base de datos.
El sitio se queda con todo; el canal se queda con la selección:

- **Un resumen diario**: una sola publicación con "las ofertas de hoy" y el
  enlace al sitio. Volumen constante, sin importar cuántas entren.
- **Más unos pocos lugares individuales por día** (tres o cuatro), y **ésos se
  venden**. "Tu oferta sale sola en el canal de URUKU" pasa a ser un beneficio
  escaso del plan Destacado/Pro, en vez de un derecho ilimitado que arruina el
  canal para todos.

Convierte el problema de volumen en una razón para subir de plan. Y le da al
plan caro algo que el barato no puede tener, que es justo lo que hoy le falta.

- [ ] Decidir: ¿resumen diario, lugares vendidos, o las dos cosas?
- [ ] Programarlo (hoy la difusión manda TODO lo aprobado al canal).

### 2. La IA revisa antes que el humano, y hoy no lo hace

Lo que hay: la IA (`moderar_publicacion`, Gemini) da un veredicto
aprobar/rechazar/dudoso **cuando el moderador aprieta un botón en el panel**. O
sea: primero mira una persona, después opina la máquina. Está al revés.

Lo que falta: que la IA corra **al entrar el mensaje** y guarde el veredicto, de
modo que la cola llegue ordenada — lo dudoso arriba, lo limpio abajo. Con dos o
tres ofertas por día da igual; con cincuenta, es la diferencia entre revisar y
no revisar.

El orden que quedó definido, y que ya está construido de la mitad para adelante:

```
llega al grupo → IA opina (falta) → humano aprueba (hay) → cola de difusión (hay)
              → sale espaciado, 5 por vuelta (hay)
```

- [ ] Correr la IA en la ingesta y guardar veredicto + confianza.
- [ ] Ordenar la cola de moderación por eso.
- [ ] Recién entonces decidir si algo se auto-aprueba solo (la nota vieja decía
      ≥0.8; con el volumen de hoy no hace falta y es prematuro).

### 3. Cuánto puede publicar cada plan — hoy no lo cuenta nadie

**Lo que se vende no existe en el código.** La página de planes promete 15 y 50
publicaciones por mes. El sistema **no cuenta nada**: hay un interruptor que
deja publicar o no por WhatsApp según el plan (`INGESTA_REQUIERE_PLAN`,
apagado), y ninguna cuota. Un comercio del plan de 15 puede mandar 300 y salen
las 300.

Y hay otra inconsistencia que va a doler: los planes que conoce el código son
`gratis / pro / premium`, y los que se venden son **Básico, Publica, Destacado,
Pro**. Son dos vocabularios distintos para la misma cosa.

**Lo que hay que construir**, y el orden importa:

1. Una tabla de planes con la cuota, el precio y **el precio de la publicación
   extra** — en la base, no en el `.env` ni en el código. Los Bs 5 van a cambiar,
   y el día que cambien tiene que poder hacerlo quien vende, sin un deploy.
2. Contar las publicaciones **por ciclo de facturación**, no por mes
   calendario: se paga hoy y corren dos meses desde hoy, así que el mes
   calendario no significa nada para el comerciante.
3. Qué pasa al llegar al tope. **Acá está la trampa**: bloquear en silencio es
   lo peor que puede pasar. El comerciante manda la foto, no aparece, y no se
   entera de por qué — igual que las ofertas que se perdían antes de la bandeja.

   Tiene que avisarle **por WhatsApp, en el momento**, y con las dos salidas:

   > *"Llegaste a las 50 de tu plan. La próxima sale Bs 5, o pasás al plan
   > Destacado y tenés 50 más por mes."*

   Las dos opciones juntas, no una. El que no quiere gastar más igual se entera
   de que existe el plan de arriba; el que tiene apuro paga los 5 y publica.

- [ ] Tabla de planes con cuota y precios editables.
- [ ] Contador por ciclo de facturación.
- [ ] Aviso automático al llegar al tope, con las dos salidas.
- [ ] Unificar los nombres de plan del código con los que se venden.

### 4. El número de la marca con IA 24/7 — cuánto cuesta de verdad

**Es el 67991916**, y hay una cosa que hacer YA, que es **no tocarlo**: no
registrarle WhatsApp común. Un número que ya tiene WhatsApp normal no se puede
pasar a la API oficial sin darlo de baja antes, y hoy es el único candidato
limpio.

**Por qué la API oficial y no WAHA, que es gratis.** Éste es el único número que
va impreso en volantes, en el sitio y en Facebook: es el que **no puede morir**.
Y un número que contesta todo el día a desconocidos es justo el patrón de uso
que hace que WhatsApp banee una cuenta no oficial. Pagar por lo oficial acá es
comprar que no se caiga.

**Los costos, que son más bajos de lo que parece:**

- **Meta**: las conversaciones que **inicia el usuario** (te escriben y
  contestás) **no se cobran**. Se cobran las que inicia la empresa con
  plantillas — o sea, mandar promociones. Un asistente que sólo responde es,
  del lado de Meta, prácticamente gratis.
- **La IA**: con un modelo chico (Gemini Flash, Haiku), una conversación de diez
  mensajes cuesta fracciones de centavo. Mil conversaciones al mes son unos
  pocos dólares.
- **Lo que sí cuesta**: la verificación del negocio en Meta (trámite, no plata) y
  el trabajo de armarlo.

Media parte ya está: el proyecto tiene un cliente de la Cloud API
(`whatsapp_client.py`, hecho para el OTP).

**Los límites que hay que ponerle al asistente antes de encenderlo.** Una IA
contestando como la marca puede inventar, y lo que invente lo dijo URUKU:

- Contesta sobre qué es URUKU, los planes, cómo publicar, cómo sumarse.
- **Nunca** afirma precios, stock ni horarios de un comercio: para eso manda a
  la ficha.
- Lo que no sabe, lo pasa a una persona. Un "no sé, te contesta alguien" es
  infinitamente mejor que una respuesta inventada a un cliente.

- [ ] Decidir si se hace ahora o después de la primera tanda de comercios.
- [ ] Verificación de negocio en Meta.
- [ ] Definir por escrito qué puede y qué no puede contestar.

### 5. Pagar por ofertas: cómo no financiar el fraude

La idea: quien le manda ofertas a URUKU cobra plata o descuentos. Funciona, y
tiene un modo de fallar muy conocido — **si se paga por mandar, se recibe
basura**; si se paga por publicar, alguien va a inventar ofertas.

Las reglas que lo hacen sostenible, todas juntas:

- **Se paga por lo aprobado, nunca por lo enviado.** La revisión humana va antes
  del pago, siempre.
- **Sólo cuenta lo que agrega algo**: un comercio que todavía no está, o uno que
  no publica hace X días. Diez fotos del mismo local en una tarde valen una.
- **Tope por persona y por mes**, y además **tope de presupuesto total**. Sin el
  segundo, una semana en que la idea se vuelve popular cuesta plata de verdad.
- **Un pago por número de WhatsApp verificado.** Sin eso, la misma persona cobra
  cinco veces.
- **Crédito antes que efectivo.** Un descuento o un mes de plan atrae a gente que
  quiere el servicio; la plata en mano atrae a gente que quiere la plata. El
  crédito además vuelve al negocio.

- [ ] Fijar los tres números: por publicación, tope por persona, tope mensual.
- [ ] Decidir crédito o efectivo (recomendado: crédito).
- [ ] Construir el registro de recompensas — hoy no existe ninguno.

### 6. La recompensa por traer usuarios: existe la mitad que no se ve

**Lo que hay de verdad:** la columna `usuarios.ref`, que guarda el código del QR
por el que llegó cada usuario y **no se pisa nunca** (queda el primero). Eso es
la atribución, y está bien hecha.

**Lo que NO hay:** el registro de recompensas, el cálculo, el tope mensual y el
control de fraude. Nada de eso existe.

**Y una cosa que hay que corregir de la idea, porque no se puede medir.** "Que
dure más de 7 días con la aplicación instalada" **no es medible**: URUKU es una
aplicación web, y ni en iOS ni en Android se puede saber si sigue instalada. Lo
dice el comentario de la propia migración que creó `ref`, de hace meses.

Lo que sí se puede medir, y sirve igual o más:

> **Un usuario que se registró con ese código y volvió a usar el sitio después
> de 7 días.**

Es mejor métrica que la instalación: una app instalada y nunca abierta no vale
nada, y un usuario que volvió a la semana es exactamente el que se buscaba.

Para eso falta una pieza chica: **hoy no se guarda cuándo fue la última vez que
un usuario usó el sitio**. Sin ese dato no hay forma de saber quién volvió.

- [ ] Agregar `usuarios.ultima_actividad`.
- [ ] Definir: cuánto por usuario, tope por promotor, tope mensual total.
- [ ] Registro de recompensas con estado (pendiente / pagado) — un pago que se
      calcula a mano se paga dos veces.
- [ ] Un pago por WhatsApp verificado, y no contar a los que trae el propio
      equipo.

### Lo que no puede salir a la calle antes de esto

Difundir es prometer. De esta lista, lo que **hay que cerrar sí o sí antes** de
salir a buscar comercios y usuarios:

1. **El tope del canal** (punto 1) — porque el daño es a los seguidores, que no
   vuelven.
2. **El aviso al llegar a la cuota** (punto 3) — porque el silencio es cómo se
   pierde un comerciante que ya había pagado.
3. **Los topes de las dos recompensas** (puntos 5 y 6) — porque prometer una
   plata sin techo es una deuda que se descubre cuando ya se contrajo.

El asistente 24/7 (punto 4) y el orden de la IA (punto 2) pueden esperar a que
haya volumen: hoy no hay tanta consulta ni tanta cola.

## 🔴 Ahora / alta prioridad

### Los 888 horarios (2026-09-03)
**0 de 888 comercios tienen horario.** Es el dato que decide si alguien camina
hasta el local, el que hace que la ficha diga "Abierto ahora", y lo único que
URUKU puede tener y Facebook no. También es el único que no se puede deducir de
una foto: hay que cargarlo.

La herramienta está: **Admin › Negocios → filtro "Sin horario"**, presets de un
toque y **"↩ Igual que el anterior"** —que es el que más rinde, porque viniendo
de a uno con las flechas el anterior suele ser el vecino de la cuadra—. Con eso
cada comercio son dos toques: repetir y "Guardar y siguiente".

El modal muestra abajo **qué entendió el sitio** de lo escrito, y avisa en ámbar
cuando no entiende. Un horario que el parser no interpreta es PEOR que ninguno:
el comprador no ve "Abierto ahora" y nadie se entera de por qué.

- [ ] Hacer la pasada. Es trabajo manual y no hay forma de evitarlo.

### El canal de WhatsApp sigue apagado
Todo lo que se construyó alrededor —el explorador, el carrito de reservas, las
ofertas en la tarjeta— no tiene qué mostrar hasta que entre la primera oferta.

- [x] WAHA emparejado con el **64610187** (sesión `WORKING`, verificado el 6/9).
- [x] Los cinco números definidos, con el bloque exacto de `backend/.env` en
      [numeros-whatsapp-uruku.md](numeros-whatsapp-uruku.md). No hay que comprar
      chips: las cuatro eSIM de Entel ya están, les falta registrar WhatsApp.
- [ ] Dejar el bloque de `.env` en el VPS y reiniciar el backend. Hoy el único
      que está puesto es `WA_NUMEROS_PROPIOS`; falta `BOT_WHATSAPP_NUMERO`, y
      sin él el enlace de recuperación sale como `wa.me/?text=…` — sin
      destinatario, o sea que no le llega a nadie.
- [ ] Poner el perfil del operativo como **URUKU** (hoy dice "Juan"). Un
      desconocido llamado Juan agregándote a un grupo es lo que la gente
      reporta como spam, y el reporte es lo que dispara el baneo. **Antes de
      crear el primer grupo**: el nombre que ve el comerciante es el de ese
      momento.
- [ ] **Activar** las tres eSIM que están sin activar (68727584, 68727944,
      72900149). Una línea inactiva no recibe el SMS de verificación, así que
      sin esto no se les puede registrar WhatsApp.
- [ ] Registrar WhatsApp en el respaldo 2 (68727584) y el explorador
      (68727944). **En el 67991916 NO**: ése va a la API oficial de Meta como
      número de la marca, y registrarle WhatsApp común lo quema.
- [ ] Agregar el **respaldo 1 (75314737)** como segundo administrador del
      canal. Dos minutos, y es lo único que hace que el canal sobreviva al día
      que baneen al operativo.
- [ ] Los respaldos entran a los grupos **antes** de necesitarlos: una cuenta
      baneada no puede agregar a nadie. Si algún grupo queda sin ellos, se
      arregla desde **Admin › WhatsApp → "Agregar un número a los grupos"**, de
      a tandas chicas.

### Las 8 fechas del panel de Vencimientos
Están cargadas sin fecha a propósito — ése es el estado real, nadie las anotó
nunca. La más urgente es **`uruku.bo`**: si vence no se cae "el sitio",
desaparecen también todos los enlaces que los comerciantes ya mandaron por
WhatsApp, y los `.bo` se renuevan con trámite y no con un clic.

Los **chips prepagos** llevan fecha de recarga, no de vencimiento: es el único
riesgo que se pudre solo mientras nadie mira.

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
- [x] ~~**gimnasio**~~ — resuelto el 4/9, y de una forma que nadie esperaba: el
      rubro `gimnasios` YA existía (0086) y además alguien había creado un
      segundo rubro llamado `gimnasio` desde el panel. Los comercios estaban
      repartidos entre los dos, 5 y 5, y ninguno se veía completo. La 0095 los
      fusiona y la 0094 saca `gimnasio` del diccionario de `deportes`, que era
      lo que hacía ganar al genérico.
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

### "Abierto ahora" no puede funcionar: NINGÚN comercio tiene horario
Medido el 27/8: `count(*) filter (where horario <> '')` da **0** sobre los
comercios activos. O sea que el indicador "Abierto/Cerrado ahora" de la ficha y
el filtro "Abierto ahora" del mapa —los dos figuran como hechos— están
construidos y **no tienen con qué decidir**. No fallan: simplemente no hacen
nada, que es la forma de romperse más difícil de ver.

- [x] ~~Esconder el filtro~~ — hecho, y como REGLA y no como parche: un filtro
      sólo se dibuja si hay datos que pueda filtrar (`getFiltrosDisponibles`).
      Aplica a Zona, Precio y Ofertas. **Tipo (mayorista/minorista) queda
      siempre visible por decisión del producto**, aunque el reparto esté
      desbalanceado: es un filtro que la gente entiende y busca.
- [ ] **El horario se carga después** (decidido el 28/8: NO se agrega al alta
      por ahora). Cuando haya horarios cargados, el filtro **reaparece solo** —
      no hay que acordarse de volver a mostrarlo ni tocar código.

### El normalizador de subcategorías corta la última sílaba
En la §3 de `novedades.sql` aparecen `muebl` y `cepillo de dient`. El reordenado
alfabético (`americana ropa`, `mujer ropa`) **es a propósito** —así "bolsos y
mochilas" y "mochilas y bolsos" cuentan como uno solo, arreglo del 22/8— pero el
recorte no. Sólo afecta al conteo, no a lo que se muestra.

- [ ] Mirar `subcategoria_norm`: parece un stemmer demasiado agresivo.

### Ofertas por WhatsApp — grupos ✅ construido
El modelo de **un grupo por comerciante** está hecho y probado: el grupo
identifica al comercio, los números de URUKU no publican, la foto se baja a
disco propio y el grupo se ve en el perfil del comercio (Admin › el comercio ›
Grupo de WhatsApp). Detalle completo en
**[grupos-whatsapp-uruku.md](grupos-whatsapp-uruku.md)**.

Falta de este canal: **verificar que la sesión de WAHA esté vinculada** (paso
cero), la retención de `waha_media`, y decidir lo de los **grupos compartidos de
captación** — analizado en la §2 de ese documento, con una recomendación.

### Lo que quedó pendiente de este canal
- [ ] **Verificar que la sesión de WAHA esté vinculada** (`/api/sessions`). Con 1
      publicación en toda la base, es probable que nunca se escaneara el QR — y
      eso explicaría el cero sin que falte una línea de código. **Es el paso
      cero**: hasta que esto no esté, nada del canal se ejercita.
- [ ] **Retención de `waha_media`.** El volumen crece sin límite; con video llena
      el disco. Importa menos desde que la foto se copia a disco propio.
- [ ] **Los grupos compartidos de captación** (donde se metió a URUKU en grupos
      ya existentes de comerciantes para juntar volumen al principio). Analizado
      en la §2 de [grupos-whatsapp-uruku.md](grupos-whatsapp-uruku.md): un grupo
      compartido **no identifica a nadie**, así que el remitente vuelve a ser el
      único dato — que es justo lo que el modelo de grupos vino a reemplazar. Hay
      recomendación y no está decidido.
- [ ] **Decidir cuándo se enciende `ingesta_requiere_plan`**, que es lo que
      convierte "publicar por WhatsApp" en una función que se paga. Hoy está
      apagado a propósito para que el catálogo tenga volumen.

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
- [ ] **`completar_rubros.py` sigue SIN APLICAR** — y el 4/9 dejó de ser el
      camino principal. Ver la sección de la sesión del 4-5/9 más abajo: la
      revisión de rubros mide 194 comercios que no cierran, de los cuales 102
      se resuelven con una corrida y 92 a mano. Ese botón hace lo que este
      script iba a hacer, con vista previa y sin pisar lo corregido a mano.
      Lo de abajo sigue valiendo como criterio: El diccionario ya está
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

## 🔵 De la sesión del 4-5/9 — lo que quedó a medio aplicar

Todo esto está **escrito y desplegado en código**. Lo que falta es correrlo
contra la base de producción, y hasta que se corra el sitio se comporta como
antes. Es la clase de pendiente que se olvida porque "ya está hecho".

### Antes de nada: medir qué se aplicó
Las migraciones 0089 a 0098 se fueron dando de a una y no hay registro de
cuáles corrieron. Esto lo contesta de una:

```sql
select 'reclamos con grant' as que,
       has_table_privilege('service_role','reclamos','select')::text as estado
union all select 'portada_pos', (to_regclass('comercios') is not null and exists (
  select 1 from information_schema.columns
   where table_name='comercios' and column_name='portada_pos'))::text
union all select 'rubro_revisado_at', (exists (
  select 1 from information_schema.columns
   where table_name='comercios' and column_name='rubro_revisado_at'))::text
union all select 'rubros_a_revisar', (to_regproc('rubros_a_revisar') is not null)::text
union all select 'salones y agro', (select count(*)::text from rubros
   where slug in ('salones','agro') and activo)
union all select 'rubros duplicados sueltos', (select count(*)::text from rubros
   where activo and nombre !~ '[A-ZÁÉÍÓÚ]');
```

### Después, en orden
- [ ] **Aplicar las migraciones que falten** (0090 grants · 0091 texto único ·
      0092 principal por identidad · 0093 salones y agro · 0094 palabras
      repetidas · 0095 rubros duplicados · 0096 buscar por todas las palabras ·
      0097 sin tildes · 0098 encuadre). Cada una con `restart postgrest`.
- [ ] **Regenerar las miniaturas**
      (`backend/scripts/regenerar_miniaturas.py`). Sin esto las 1079 fotos
      cargadas siguen viéndose borrosas: el arreglo del tamaño sólo alcanza a
      las nuevas.
- [ ] **Correr "Completar rubros"** después de la 0093: `salones` y `agro`
      nacieron con cero comercios y el diccionario recién ahora puede
      alcanzarlos.
- [ ] **Revisar rubros** (Admin › Revisar rubros). Medido: 194 no cierran, 102
      con una sola sugerencia —se resuelven con la corrida y su vista previa— y
      92 a mano. Los 7 anotados en [rubros-a-corregir.md](rubros-a-corregir.md)
      salen ahí.
- [ ] **Encuadrar las portadas** de los comercios donde el recorte al centro
      corta el cartel. Es la barra del editor; se hace de corrido con el modal
      saltando de ficha en ficha.

### Lo que el verificador del buscador dejó abierto
`scripts/verificar-buscador.sql`, corrido el 5/9.

- [ ] **36 palabras del diccionario no traen ningún comercio.** Algunas son
      correctas y no hay negocio todavía (`agroquimico`, `dhl`); otras son de
      producto y nadie las escribe (`ibuprofeno`, `paracetamol`); y una,
      `quiosqu`, es un prefijo a propósito y no una palabra — el informe la
      cuenta mal. Decidir cuáles se sacan.
- [ ] **La mitad de los 99 términos buscados son tecleo** (`zempanad`,
      `zempanada`, `zempanadas`). Sigue sin aplicarse
      `limpiar_busquedas_de_tecleo.sql`, y mientras tanto la lista de "buscado
      sin resultado" —la que dice a qué rubros salir a buscar comercios— está
      llena de fragmentos.
- [ ] **Las búsquedas largas traen de más.** Con menos de 5 resultados fuertes
      entra la red de contención y "artículos de limpieza" devuelve 27 sobre 4
      comercios del rubro. Es lo correcto mientras el catálogo esté flaco;
      revisarlo cuando los rubros tengan volumen.

### Lo que el diseño nuevo dejó pedido
- [ ] **Distancia en km en la tarjeta de resultados.** Es lo que más agregaría
      en una ciudad donde todo está a diez cuadras, y necesita pedir permiso de
      ubicación. Decisión de producto: cuándo se pide y qué se muestra si dicen
      que no.
- [ ] **Opiniones.** El diseño las pide (`4.8 (12)`) y no existe el sistema. Es
      una funcionalidad entera, no un campo.
- [ ] **Contador de fotos sobre la portada** (`📷 3`): el dato existe por
      comercio pero `buscar_comercios` no lo devuelve.
- [ ] **Reservar desde la tarjeta de resultados**, que se perdió al hacerla
      compacta. Sigue en la ficha. Revisar si hace falta cuando haya reservas
      de verdad.

## 🎨 Diseño (menor, no bloquea)
- [x] **Fuera la fila “Mostrando” — 2026-09-03.**
      Cada vez que escribías o aplicabas un filtro aparecía un renglón nuevo
      debajo de los chips (`Mostrando · “estacion de servicio” ×`) que empujaba
      los resultados hacia abajo, y arriba del mapa un renglón se paga en mapa
      cortado. Además repetía: buscabas `estacion de servicio`, tocabas el
      refinamiento `estación de servicio` y quedaban dos etiquetas casi iguales,
      una sin tilde. Se fue la fila entera, y con ella el botón “Limpiar todo”:
      el buscador se lee de una sola pasada. Lo que está filtrando se ve donde
      se eligió —el texto en el buscador, la subcategoría en su chip encendido,
      rubro / zona / precio / tipo en la etiqueta del propio filtro— y cada uno
      se saca desde ahí. Ver
      [buscar-client.tsx](../frontend/components/buscar-client.tsx).

- [ ] **Input del buscador en modo oscuro:** se pierde, hay muy poco contraste
      contra el fondo. Debería leerse claramente dónde se escribe.
- [x] ~~**Header partido en el celular**~~ — arreglado el 5/9. El wordmark a
      72px más el selector de ciudad, Ingresar y el tema no entraban en 390px,
      así que "Bermejo · Ingresar" caía un renglón abajo con el logo solo
      arriba. Baja a 46px bajo 560px. Se veía en todo el sitio porque el header
      es uno solo.

- [ ] **Barra de redes / clima / cotización en escritorio:** queda pegada debajo
      del logo y se ve rara. En móvil está bien; el problema es el ancho grande.
- [ ] **Puntos del mapa:** sigue sin convencer (pendiente de la sesión del 2026-08-22).
- [ ] **Adornos del mapa:** el editor ya está (Admin › Adornos) y ahora pone
      chalanas, lapachos y **banderas** (Bolivia, Argentina, Bermejo, Tarija,
      Santa Cruz, La Paz). Falta **ubicarlos** en el mapa. Las chalanas quedaron
      a un cuarto del tamaño original y el lapacho se redibujó mirando fotos
      reales (copa ancha en domo, ramas visibles, pétalos caídos).
- [ ] **Fotos reales de lapacho (decidido el 2026-08-27: las saca el equipo).**
      El código ya las acepta: si `LAPACHOS[<variedad>].foto` existe, el mapa
      muestra la foto; si no, dibuja el vector. Van en `public/adornos/`, una
      por variedad (rosa, amarillo, rosa fuerte, blanco).

      **Por qué propias y no de un banco:** se probó con Pngtree y su "gratis"
      es gratis de DESCARGAR, no libre de usar — el uso comercial pide plan
      pago, y URUKU cobra planes. Es el mismo criterio con el que se descartó
      Google Places. Además una foto del equipo es un lapacho **de Bermejo**,
      que es la misma lógica que hace valer la foto de vidriera contra el pin
      importado sin foto.

      **Cómo tienen que ser:** el árbol contra cielo despejado, sin cables
      cruzando, sin casas detrás, tronco entero hasta el piso. El recorte lo
      hace el código/quien programe — el cielo parejo se separa bien.

      **No bloquea nada:** sin fotos el mapa dibuja el vector. Se suman de a una.

      Ojo con el tamaño: el adorno se dibuja a 48 px de ancho y ahí una foto
      pierde el detalle. Si se quiere que se lea, hay que agrandarlo a 80-96 px
      — y a ese tamaño empieza a competir con los pines de comercio, que es lo
      único que el mapa existe para mostrar. Decisión pendiente.
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

## 🛒 Ofertas y reserva, dentro de URUKU

Reemplaza a Reservalo. Decisión y fundamento en
[decision-uruku-sin-reservalo.md](decision-uruku-sin-reservalo.md).

- [x] ~~Sacar las puertas de entrada a Reservalo~~ — el modo "Productos" del
      buscador, el chip "Productos ↗" y los enlaces de la ficha. El contenedor y
      los datos quedan: la decisión es reversible mientras no se borre nada.
- [ ] **Los dos bloques en el buscador**: "N ofertas con precio" arriba y
      "N comercios que venden esto" abajo. Hoy el primero queda vacío y la
      pantalla se ve igual que ahora — ésa es la gracia.
- [ ] **La tarjeta de oferta con su comercio adentro**: foto, precio, nombre del
      local, a cuántas cuadras, Cómo llegar, WhatsApp y Reservar.
- [ ] **Reserva por comercio, varias abiertas a la vez.** En el celular, sin
      login. Un mensaje de WhatsApp por local.
- [ ] **La confirma el vendedor** respondiendo en su grupo de WhatsApp. Hasta
      entonces la pantalla no puede decir "reservado": nada queda apartado.
- [ ] Sacar del panel de admin el bloque que lee datos de Reservalo (hoy
      muestra ceros).

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

### 2026-09-02 y 03
- [x] **URUKU pasa a ser el directorio de la CIUDAD.** Rubros nuevos: hoja de
      coca, taller mecánico, taxis, baños, bares/boliches/karaoke, carpintería,
      herrería, carnicería, limpieza, funeraria, telas, gimnasios. Y la bandera
      `rubros.comercial`: un baño público no tiene WhatsApp ni productos y no
      puede quedar en la cola de incompletos para siempre.
- [x] **Los rubros se manejan desde el panel, no por SSH.** Admin › Rubros
      muestra lo que la IA pidió y no existe, con DOS salidas por propuesta
      —rubro nuevo o sinónimo de uno existente— porque confundirlas es cómo se
      llegó a los 19 rubros vacíos de agosto. La lógica se sacó del script a
      `services/rubros_auto.py`, así el botón y el script corren lo mismo.
- [x] **Vista previa determinista antes de guardar una palabra**: a cuántos
      comercios alcanza, cuántos son nuevos y con qué otros rubros conviven. El
      error caro del diccionario nunca fue de criterio sino de ALCANCE —"papa
      frita" describe bien la comida rápida y está en todos los kioscos— y eso
      es contable, no opinable. Por eso lo cuenta una consulta y no un modelo.
- [x] **Crear un rubro lo APLICA en el mismo acto**, sobre los comercios que la
      vista previa acaba de mostrar. Antes el rubro quedaba con cero comercios
      hasta que alguien se acordara de correr el completado.
- [x] **Las fotos de las ofertas se analizan.** Una foto sin texto era una
      oferta invisible: el índice sale de título+descripción y con foto el
      título queda en NULL. No pisa lo que escribió el comerciante y el precio
      sólo se LEE de la imagen, nunca se estima.
- [x] **El horario que cruza la medianoche.** "22-4" no se cumplía nunca y el
      local figuraba cerrado las 24 horas. Habría aparecido el primer sábado
      con boliches cargados.
- [x] **"Buscado sin resultado" estaba lleno de tecleo.** El registro vivía en
      el debounce de 280ms de la búsqueda: escribir "surtidor" dejaba cuatro
      filas. La lista que dice a qué rubros salir a buscar era ruido.
- [x] **Los desplegables del panel eran blanco sobre blanco.** Las variables
      `--uk-*` sólo existían dentro de `.uk` y el admin no está adentro; una
      declaración con una variable inexistente se descarta ENTERA.
- [x] Buscador del panel por palabras y no por la frase pegada; catálogo con las
      subcategorías de menor a mayor; `otros` deja de convivir con rubros reales.

### Semana del 2026-09-01 al 03
- [x] **Una sola pantalla.** `/mapa` y `/buscar` estaban duplicadas y ninguna
      completa: una tenía el mapa lindo sin buscador, la otra el buscador con un
      mapa pelado, y el botón "Ver mapa completo" llevaba al menos completo de
      los dos. `/mapa` queda como redirección — hay enlaces compartidos por
      WhatsApp que no pueden romperse. `mobile-home.tsx` y `home-map.tsx`
      quedaron **sin usar y sin borrar**, por si hay que volver atrás.
- [x] **El mapa arranca sólo con los adornos.** Los comercios aparecen al
      filtrar, no al hacer zoom: acercarse no es decir qué se quiere. Los
      destacados y los que pagan sí se ven desde el arranque — esa primera vista
      **es el cupo que se vende**, y `tierDe` ya sabía quién es quién.
- [x] **Tiles propios** (`tiles.uruku.bo`, nginx cacheando OSM). Mil personas
      mirando el centro son UN pedido a OSM. Ver
      [tiles-propios.md](tiles-propios.md), incluido lo que costó levantarlo.
- [x] **Mapa claro siempre.** El filtro oscuro destapaba las costuras entre
      tiles (fracciones de píxel entre imágenes). Se tapó el síntoma a
      conciencia: el arreglo real es pelearle al subpíxel del navegador y no
      valía a días de arrancar.
- [x] **Carrito de reservas** sin cuenta, por comercio, con el pedido armado
      hacia el WhatsApp de ese local. Nada dice "reservado" hasta que el
      vendedor conteste.
- [x] **El explorador**: URUKU fotografía ofertas de locales que todavía no
      publican y se publican **a nombre del comercio real**, marcadas `URUKU`,
      con la consulta llegando a URUKU. Ver
      [numeros-whatsapp-uruku.md](numeros-whatsapp-uruku.md).
- [x] **Panel de Vencimientos**: dominios, VPS y chips cargados a mano;
      certificados TLS medidos en vivo. "Falta la fecha" no cuenta como sano.
- [x] **El resultado dice qué vende el local**, con lo buscado adelante y
      resaltado; las ofertas van con foto y precio en la tarjeta.
- [x] **"Cómo llegar" se registra como contacto** en los cuatro lugares donde
      aparece. Y `contactos_30d` contaba las visitas a la ficha: el número que
      se le iba a mostrar al comerciante estaba inflado.
- [x] **Rubro de estación de servicio** (0076) y `completar_rubros.py` aplicado:
      49 rubros en 48 comercios, con `sinonimos` fuera del texto que clasifica —
      de ahí salía casi todo el ruido.

### Antes
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

## 🌍 Comercios importados de fuentes externas (2026-08-26)

**Construido**: tabla `comercios_importados`, importador desde OpenStreetMap
(`backend/scripts/importar_osm.py`) y panel **Admin › Importados** donde se
revisan y se promueven **de a uno** al mapa.

**Lo que la fuente da, medido** (19.861 negocios de las cinco ciudades):

| Ciudad | Total | Con nombre | Teléfono | WhatsApp | Foto |
|---|---|---|---|---|---|
| Bermejo | 20 | 18 | 2 | 0 | **0** |
| Tarija | 808 | 535 | 35 | 0 | **0** |
| Cochabamba | 5.892 | 3.389 | 724 | 207 | **2** |
| La Paz | 8.103 | 6.581 | 646 | 1 | **87** |
| Santa Cruz | 5.038 | 4.697 | 387 | 4 | **2** |

- **Bermejo no vale importarlo**: 20 registros (bancos y gasolineras) contra 270
  relevados a pie. Ahí el equipo de campo le gana a la API por catorce a uno.
- **Foto 0,5% · WhatsApp 1% · teléfono 9%.** Lo que se obtiene es nombre,
  ubicación y categoría. **La foto de vidriera no la da ninguna API** — es el
  dato que sólo se consigue caminando, y es el que hace útil a la ficha.
- **Google Places / HERE / Mapbox quedan afuera**, y no por precio: sus términos
  prohíben almacenar los datos y mostrarlos fuera de su mapa, en cualquier plan.

- [ ] Correr `importar_osm.py` para La Paz y Cochabamba, que son las que traen
      dato utilizable. Tarija con expectativa baja. Bermejo no.
- [ ] Decidir qué se hace con los ~4.600 sin nombre que se descartan al importar.
- [ ] **Atribución a OpenStreetMap** en el pie del mapa cuando haya promovidos:
      la licencia ODbL la exige y hoy no está puesta.
