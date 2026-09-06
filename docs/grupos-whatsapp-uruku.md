# Grupos de WhatsApp — el canal de ofertas

> Lo construido está andando. Lo de abajo de la línea es análisis, no plan
> aprobado. Última actualización: **2026-08-25**.

## 1. El modelo que existe: un grupo por comerciante

Cada comerciante tiene **un** grupo, chico:

| Quién | Para qué |
|---|---|
| El celular del comercio | El único que publica |
| El **operativo** | La cara de URUKU adentro del grupo Y el número vinculado a WAHA: es el que trae el contenido a la base |
| Los **respaldos** | No hacen nada. Están adentro para el día que baneen al operativo |

> **"Testigo" y "operativo" son el mismo número.** Este documento decía
> "testigo" para el vinculado a WAHA y "un celular de URUKU" para quien habla,
> como si fueran dos. Al principio lo eran; después se unificaron —WhatsApp
> marca como propios los mensajes del número vinculado (`fromMe`), así que la
> misma línea puede escribirle al comerciante sin que eso se convierta en una
> oferta— y el documento no se actualizó.
>
> La palabra "testigo" quedó en varios comentarios del código. Significa
> siempre lo mismo: **el operativo**.
>
> Importa porque lleva a una conclusión equivocada sobre el baneo: que los
> respaldos, "los que pasan los datos a la base", serían los expuestos. **No
> pasan nada.** WAHA lee sólo a través de la cuenta que tiene vinculada, que es
> una sola. Los respaldos son miembros inertes: entran al grupo, no publican, no
> capturan y no escriben. Esa inactividad es justamente lo que los mantiene
> sanos para el día que hagan falta.

**Por qué el grupo y no el número.** Antes la ingesta identificaba al comercio
por el teléfono de quien mandaba. Eso se rompe de dos maneras que pasan seguido:
el comerciante cambia de celular y se pierde el vínculo, o publica el hijo desde
otro número y el mensaje termina creando un comercio nuevo. **El JID de un grupo
no cambia** aunque cambien todos sus miembros.

Y da una segunda señal gratis: el grupo dice **de qué comercio** es el mensaje,
el remitente dice **si es él**. Cruzarlas permite detectar a un cuarto
participante que nadie invitó — no se descarta en silencio ni se publica: va a
moderación.

**Cómo se ata:** desde el celular del comercio se manda `URUKU-XXXX` una sola vez
adentro del grupo. También se puede a mano desde Admin › el comercio › Grupo de
WhatsApp, para cuando el grupo se rehízo.

**Reglas que ya están en el código:**

- Un grupo sin atar **no crea nada**. El crudo queda en `wa_inbox`; cuando se
  ate se sabe qué llegó antes. (Antes, cada grupo generaba un "Comercio 1234".)
- El código de otro local **no le roba el grupo** a nadie: el primero que lo ata
  se lo queda.
- Los números de URUKU (`WA_NUMEROS_PROPIOS`) no publican nunca. El operativo ya
  estaba cubierto por `fromMe` —es el vinculado—; los respaldos no lo estaban, y
  sin la lista cada "buen día" que escriba uno se publicaba como oferta del
  comerciante.
- La foto se baja al disco propio apenas llega. La URL de WAHA es interna y
  efímera, y **acá la foto es la oferta**.
- Soltar un grupo no borra lo publicado: son ofertas que existieron.

---

## 2. Lo que falta decidir: los grupos compartidos de captación

Existen grupos —de comerciantes, ya armados— donde se metió a URUKU para juntar
contenido al principio, con ofertas de gente que todavía no paga. La idea es que
sea sólo el arranque.

### 2.1 Son dos problemas y conviene separarlos

Vienen pegados en la conversación pero no tienen nada que ver:

**Que no paguen ya está resuelto.** El gate por plan existe
(`ingesta_requiere_plan`) y está **apagado a propósito**: durante la captación
conviene que cualquiera pueda mandar productos para que el catálogo tenga
volumen. No hay que construir nada para que un comercio sin plan publique. Lo
que sí hay que decidir algún día es **cuándo se enciende el gate** y qué pasa con
los grupos de los que no pasaron a pagar.

**El grupo compartido sí es un problema nuevo**, y es de identidad.

### 2.2 El problema real: un grupo compartido no identifica a nadie

Todo el modelo se apoya en que **grupo → comercio** es 1 a 1. En un grupo con
veinte comerciantes esa relación no existe: el contenido es de muchos locales.
Entonces el único dato que dice de quién es cada oferta vuelve a ser **el
remitente** — que es exactamente lo que el modelo de grupos vino a reemplazar.

Dicho de otra forma: un grupo compartido es el modelo viejo (por número)
corriendo adentro de un grupo, con todas sus fallas y una más — que ahora también
hay que distinguir a los comerciantes de los curiosos.

### 2.3 Las tres salidas, y qué cuesta cada una

**(a) Identificar por remitente dentro del grupo compartido.**
Funciona para los comerciantes que ya están cargados con su número. Para los que
no, hay que elegir entre no publicar o crear un borrador — y ahí vuelve el
comercio fantasma que acabamos de sacar. Además hereda el bug de origen: el que
cambia de celular deja de ser reconocido.

**(b) Publicaciones sin comercio ("ofertas de la ciudad").**
Requiere que `publicaciones.comercio_id` acepte nulo, y abre una pregunta que no
tiene buena respuesta: **¿a dónde lleva el clic?** Una oferta sin local es una
foto que el comprador no puede ir a comprar. Es contenido que llena el feed y no
sirve para lo que el sitio existe.

**(c) El grupo compartido como bandeja de captación, no como canal de
publicación.** Nada sale solo. Todo lo que llega queda en `wa_inbox` y aparece en
una cola donde una persona **le asigna el comercio** —creándolo si hace falta,
que es trabajo que igual había que hacer— antes de que se publique.

### 2.4 Lo que recomiendo, y por qué

**(c)**, por cuatro razones:

1. **No inventa esquema.** `wa_inbox` ya guarda todos los mensajes crudos. Lo
   que falta es una pantalla que los muestre, no una tabla nueva.
2. **No crea fantasmas.** Asignar el comercio a mano es la única forma honesta
   de saber de quién es una foto en un grupo de veinte personas.
3. **El trabajo humano es proporcional al valor.** Al principio hay poco
   volumen; si algún día hay mucho, es porque el canal funcionó y ahí se
   justifica automatizarlo.
4. **Es reversible.** Cuando un comerciante pasa al modelo propio, se le arma su
   grupo y se deja de mirar el compartido. El grupo de captación se apaga sin
   tocar código.

### 2.5 Lo que hay que mirar aunque se elija otra cosa

**La gente de esos grupos no pidió que la publiquen.** En el grupo propio el
comerciante sabe a qué entró; en un grupo preexistente están hablando entre
ellos. La primera vez que alguien vea publicado algo que escribió creyendo que
era un chat, se va del grupo y les avisa a los demás — y se pierde el grupo
entero, no un comerciante. Cualquiera de las tres salidas necesita que se avise
adentro del grupo antes de publicar nada. La opción (c) además deja que una
persona pregunte antes, caso por caso.

**El material que no es oferta.** En un grupo compartido la proporción de
charla es mucho más alta que en el grupo de a uno. Con la regla actual —todo va
a moderación— la cola se llena, y una cola con ruido se deja de mirar.

---

## 3. Pendientes del canal

- [ ] **Verificar que la sesión de WAHA esté vinculada.** Con 1 publicación en
      toda la base, es probable que nunca se escaneara el QR. Es el paso cero:
      sin eso nada de esto se ejercita.
      ```bash
      docker exec buscadonde-waha sh -c \
        'curl -s -H "X-Api-Key: $WAHA_API_KEY" localhost:3000/api/sessions'
      ```
- [ ] **Retención de `waha_media`.** El volumen crece sin límite y con video
      llena el disco. Importa menos desde que la foto se copia a disco propio,
      pero sigue pendiente.
- [ ] **Decidir lo de la sección 2.**
- [ ] **Decidir cuándo se enciende `ingesta_requiere_plan`**, que es lo que
      convierte "publicar por WhatsApp" en una función que se paga.
