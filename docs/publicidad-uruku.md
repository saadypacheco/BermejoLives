# Cómo se da a conocer URUKU

> Escrito para dos personas distintas: el **comprador**, que tiene que llegar al
> sitio, y el **comerciante**, que tiene que sumarse. Confundirlos es el error
> más caro de todos — se gasta plata hablándole a uno con el argumento del otro.

## Antes que nada: el orden importa

Con un solo comercio publicando ofertas, traer compradores es tirar plata: el
que entra no encuentra nada nuevo y no vuelve. Y sin compradores, el comerciante
no tiene por qué pagar.

**Primero se llena, después se anuncia.** El número que habilita la publicidad
al comprador no es una fecha: es **cuántos comercios están publicando seguido**.
Con veinte locales subiendo ofertas por semana hay algo que mostrar; con uno,
no.

Mientras tanto, toda la comunicación va al **comerciante**, que es gratis y se
hace caminando.

---

## El video de 30 segundos

Vertical, para el estado de WhatsApp, TikTok e Instagram. Se graba con el
celular, sin equipo. Lo importante es que **se entienda sin sonido**: en Bermejo
se mira en la calle y con el volumen bajo, así que todo lo hablado va también
como texto en pantalla.

### Versión para el COMERCIANTE

| Seg | Se ve | Texto en pantalla |
|---|---|---|
| 0–4 | Un cartel de local, de frente, en la calle | *Su cartel dice el nombre de su local.* |
| 4–8 | Alguien caminando, mirando el celular | *La gente busca lo que vende.* |
| 8–14 | Pantalla del celular: se escribe **zapatillas** y aparece la lista con fotos | *En URUKU lo encuentran por lo que vende.* |
| 14–20 | Se toca un local y se abre la ficha: foto, horario, WhatsApp | *Su ficha, con su WhatsApp.* |
| 20–25 | Se toca WhatsApp y se abre el chat | *El cliente le escribe directo. Sin comisión.* |
| 25–30 | Logo URUKU + `uruku.bo` | *Su negocio ya está. Búsquelo.* |

**El remate importa más que todo lo anterior**: *"su negocio ya está"* convierte
el video en una invitación a verificar algo, no en una publicidad. El que lo ve
abre el sitio a buscarse.

### Versión para el COMPRADOR — cuando haya ofertas

| Seg | Se ve | Texto en pantalla |
|---|---|---|
| 0–5 | Tres o cuatro ofertas reales pasando, con precio | *Lo que hay hoy en Bermejo.* |
| 5–12 | El mapa con los pines de la ciudad | *Dónde está, cuánto sale, si está abierto.* |
| 12–20 | Se busca algo puntual y aparece | *Buscá lo que necesitás.* |
| 20–25 | Se toca WhatsApp del local | *Escribile al local, directo.* |
| 25–30 | Logo + `uruku.bo` | *URUKU. Bermejo, en tu teléfono.* |

**No grabar esta versión hasta que las ofertas sean reales.** Un video con
ofertas inventadas se nota, y el que entra y no las encuentra no vuelve.

### El video de placas ya está automatizado

`frontend/scripts/video-promo.mjs` lo arma solo, con capturas de `uruku.bo` en
vivo. **Se corre en la PC, no en el VPS**: el servidor no tiene Node ni ffmpeg y
no vale la pena instalarlos — el script entra al sitio por internet como
cualquier visitante, así que da igual desde dónde salga.

```
cd frontend
npm i --no-save playwright && npx playwright install chromium
node scripts/video-promo.mjs
```

Rehacerlo cuando cambie una pantalla es volver a correrlo. Lo que sigue abajo es
para la versión buena: la grabada con el teléfono.

### Cómo grabarlo

Tres o cuatro tomas de la calle (carteles, vidrieras, gente caminando) y el
resto es **grabación de pantalla del celular** — no hace falta filmar la
pantalla con otra cámara, iOS y Android graban la pantalla solos y se ve
infinitamente mejor.

Música sin derechos de la propia biblioteca de TikTok o Instagram. Nada
descargado de YouTube: lo silencian y el video queda mudo justo donde la mitad
lo mira sin sonido.

---

## El volante

Ya está hecho y se imprime desde el panel: **Admin › Negocios → el botón 🖨** de
cada comercio, o directo en `uruku.bo/volante/<slug>`.

Sale en **A5** (media hoja), así que entran dos por página en una impresora
común. Lleva el nombre del local y un **QR a su propia ficha**.

**Por qué uno por comercio y no un folleto general.** Un papel que dice "sumate
a URUKU" es publicidad y se tira. Éste dice *"su local ya está adentro, escanee
y lo ve"*, y el QR lo prueba en dos segundos. Deja de ser una promesa.

Es además la salida para el caso más común de la calle: el comerciante está
atendiendo y no puede escucharte. Insistir ahí quema el local; dejarle el
volante y volver el martes, no.

**Imprimir por tanda, no de a uno.** Antes de salir a una cuadra, imprimir los
volantes de los locales de esa cuadra. La app de campo ya los tiene cargados con
foto.

---

## Cómo se hacen conocidas las redes de URUKU

> Escrito el 10/9, cuando ya existen las cuatro cuentas (`@uruku.bo` en TikTok,
> Instagram y Facebook, `@Uruku-Bermejo` en YouTube) y el canal de WhatsApp.
> Tener las cuentas no es tener audiencia: son cinco perfiles vacíos hasta que
> alguien los siga.

### El error que hay que no cometer: repartirse en cuatro

Publicar lo mismo en cuatro redes no construye ninguna. Cada red premia a quien
publica seguido en ELLA, y cuatro cuentas con tres seguidores cada una son peor
que una con doscientos.

**El orden para Bermejo, que no es el mismo que para una ciudad grande:**

1. **Canal de WhatsApp.** Es el único donde el mensaje llega sin pelear con un
   algoritmo. En Bolivia todo el mundo usa WhatsApp y nadie tiene que aprender
   nada nuevo. Es el que hay que empujar en cada conversación.
2. **Facebook.** En Bolivia sigue siendo donde se compra y se vende en las
   ciudades del interior, sobre todo de treinta para arriba — que es quien tiene
   la plata. Y tiene la pieza que ninguna otra red tiene: los **grupos de compra
   y venta de Bermejo**, que ya existen y ya tienen a la gente adentro.
3. **TikTok / Instagram.** Para los jóvenes y para el contenido de recorridos.
   Rinde, pero más lento, y es el que más trabajo pide por publicación.
4. **YouTube.** Último. Sirve como archivo de los videos largos, no para que
   alguien te descubra.

### La palanca más grande: el comerciante distribuye por vos

URUKU tiene 888 comercios cargados. Cada uno tiene sus propios clientes, su
propio WhatsApp y su propia gente. **La suma de sus contactos es enormemente más
grande que cualquier cantidad de seguidores que la marca pueda juntar sola.**

Por eso, cuando la oferta de un comercio sale a las redes de URUKU, el paso que
no hay que saltear es **mandarle el enlace del posteo al comerciante**:

> *"Publicamos tu oferta acá 👇 compartila con tus clientes."*

Hace dos cosas al mismo tiempo, y las dos importan:

- Le da **la prueba** de que URUKU hizo lo que prometió — que es lo que sostiene
  el cobro del mes que viene mejor que cualquier argumento.
- Lo convierte en el que reparte. Comparte un posteo donde aparece **su** local,
  no una publicidad ajena.

Es también lo que hace crecer las redes de URUKU sin pagar nada: cada vez que un
comerciante comparte, su gente ve el nombre de la marca.

### Qué publicar para que se comparta

En una ciudad chica funciona lo que la gente **reconoce**: la vidriera de la
esquina, el mostrador, la cara del que atiende. Nadie comparte un placeholder
bonito; todo el mundo comparte algo donde aparece.

- **La oferta con precio.** Es el contenido que la gente guarda y reenvía.
- **Recorridos de galerías y locales.** Sirven doble: son contenido para el
  comprador y son el mejor argumento de venta para el comerciante — *"te
  grabamos el local"*.
- **El "ya está adentro".** Mostrar la ficha de un local que se acaba de sumar y
  etiquetarlo. El local lo comparte casi siempre.
- **Nada de frases de marca sin producto.** "Bienvenidos a URUKU" no lo comparte
  nadie.

**Constancia antes que cantidad.** Tres o cuatro publicaciones por semana,
sostenidas, valen más que veinte una semana y cero el mes siguiente. Las redes
castigan la irregularidad más que el volumen bajo.

### Los primeros seguidores no salen de las redes

Nadie va a encontrar `@uruku.bo` buscándolo. Los primeros seguidores salen de
donde ya hay gente:

- **Los grupos de compra y venta de Bermejo que ya existen** — una oferta buena
  por vez, con el enlace. No spamear: una cuenta que satura un grupo termina
  expulsada y con la marca quemada.
- **El QR**, que ya está hecho ([frontend/public/qr/](../frontend/public/qr/)):
  en el volante, en la vidriera del local, en la firma del correo.
- **Cada visita de campo.** El agente que carga un local puede pedirle que siga
  el canal ahí mismo, con el teléfono en la mano. Es el momento de más
  disposición que va a haber.
- **Cruce entre las propias redes.** El canal de WhatsApp anuncia el TikTok, el
  TikTok manda al canal.

### Pauta paga: última, y con una condición

Antes de que haya ofertas de verdad, pagar publicidad es pagar por traer gente a
una casa vacía. Cuando las haya, lo más barato que existe es **promocionar un
posteo que ya funcionó solo** — no uno nuevo. Facebook lo cobra por alcance y en
Bermejo el alcance es barato justamente porque la ciudad es chica.

### Lo que falta para dejar de adivinar

Hoy no hay forma de saber **qué red trae gente al sitio**. Sin eso, la decisión
de dónde poner el esfuerzo se toma por intuición. Lo que falta es marcar los
enlaces que se publican en cada red y contar las visitas por origen — es poco
trabajo y cambia la conversación de "me parece que Facebook anda mejor" a un
número.

## Dónde anunciar, por orden de lo que rinde

**1. Los grupos de WhatsApp que ya existen.** Bermejo tiene grupos de compra y
venta con cientos de personas. Es gratis, es donde ya está la gente, y una
oferta real puesta ahí con el enlace a la ficha rinde más que cualquier pauta.
Lo que no hay que hacer es spamear: una oferta buena por vez.

**2. El canal de WhatsApp de URUKU.** Es el único medio propio donde la gente
recibe sin buscar. Hoy está creado y **sin cargar en el sitio**, así que la
sección del home que invita a seguirlo no se dibuja. Es el arreglo más barato
con más efecto que hay pendiente.

**3. TikTok e Instagram.** Los recorridos de locales funcionan bien en ciudades
chicas: la gente reconoce la vidriera. Y le sirve doble — es contenido para el
comprador y es el mejor argumento de venta para el comerciante ("te grabamos el
local").

**4. Pauta paga.** Última, y sólo cuando haya ofertas de verdad. Antes de eso se
paga por traer gente a una casa vacía.

---

## Lo que no hay que prometer

Vale para el video, el volante y la conversación:

- **No prometer ventas.** Prometemos que lo encuentren.
- **No prometer "toda Argentina".** Lo cierto es Bermejo y los que cruzan de
  Aguas Blancas y Orán. Es más chico, es verdad y convence más.
- **No inventar números de visitas.** Si son pocos, se dice que se está
  arrancando — el que promete miles y no cumple no entra dos veces al mismo
  local.
