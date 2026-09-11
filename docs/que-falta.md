# Qué falta — lista ordenada

> **Para operar los teléfonos —configuración, qué no hacer, y qué hacer cuando
> algo se rompe— está el
> [manual operativo](manual-operativo-whatsapp.md).**
>
> Al 10/9/2026. Ordenado por lo que **desbloquea a lo demás**, no por tamaño.
> Lo de arriba hace que lo de abajo tenga sentido; hacer lo de abajo primero es
> trabajar sobre algo que nadie puede ver todavía.

---

## 0. Lo que bloquea absolutamente todo

### 0.1 Desplegar — **18 commits y 3 migraciones sin subir**

Todo lo construido en los últimos días **no existe en producción**: la difusión
a redes, los planes en la base, las cuotas, el informe de demanda, el tope del
canal, la capa de Meta. Cualquier otra cosa que se haga encima es trabajo que
nadie puede ver ni probar.

Las migraciones nuevas: `0100` (cola de difusión), `0101` (planes y cargos),
`0102` (plan Empleado Digital).

Los pasos, uno por uno y con verificación, en [deploy-10-09.md](deploy-10-09.md).

### 0.2 El `.env` de producción

Decidido el 11/9: **WAHA sólo lee**, y se queda en la **tablet (64610187)**,
donde ya está vinculado. El Tigo es el Anfitrión. El bloque final y el porqué
de cada línea en [numeros-whatsapp-uruku.md](numeros-whatsapp-uruku.md):

```
WA_NUMEROS_PROPIOS=59164610187,59167991916,59168727944,59175314737,59168727584
WA_NUMEROS_GRUPO=
WA_NUMEROS_EXPLORADOR=59168727944
WA_CONTACTO_EXPLORADOR=
BOT_WHATSAPP_NUMERO=59164610187
WA_CANAL_ID=
```

- [ ] Poner ese bloque y levantar el backend.
- [ ] **PIN de dos pasos** en la tablet y en el Samsung, con correo de
      recuperación. Es lo que impide que alguien se quede con el número con un
      duplicado de chip, y lo que te pide WhatsApp al cambiar de aparato.
- [ ] **Perfil URUKU también en el Samsung**: es el que crea los grupos y el
      nombre que ve el comerciante.
- [ ] Copia de seguridad de WhatsApp en Google Drive, en el Samsung.

---

## 1. Antes de tocar un solo grupo de comerciante

Son minutos cada una y **después ya no se pueden hacer**.

- [ ] **Perfil del operativo: de "Juan" a URUKU**, con logo. El nombre que ve el
      comerciante es el del momento en que lo agregan. Un desconocido llamado
      Juan agregándote a un grupo es lo que la gente reporta como spam, y el
      reporte es lo que dispara el baneo.
- [ ] **Segundo administrador del canal: el Tigo**, desde la tablet. El canal
      vive en el número que corre WAHA; esto es lo que lo cubre si ese número
      se pierde.

---

## 2. Encender lo que ya está construido

Todo esto es pegar credenciales. El código está y probado.

- [ ] **Canal de WhatsApp en `/contenido`.** Sin el enlace, la sección del home
      que le habla al comprador no se dibuja. **El enlace ya está** (salió en
      los registros de WAHA): `https://whatsapp.com/channel/0029Vb8mQrMGOj9rI7Bg4S1a`.
      Tiene 0 seguidores.
- [ ] **Facebook en `/contenido`**: `https://www.facebook.com/uruku.bo/`. La URL
      ya está anotada; falta pegarla.
- [x] ~~`WA_CANAL_ID`~~ — **decidido el 11/9: el canal se publica a mano
      desde la tablet.** El identificador (`120363412598489616@newsletter`)
      queda anotado por si algún día se enciende.
- [ ] **App de Meta** → `FACEBOOK_PAGE_ID`, `FACEBOOK_PAGE_TOKEN`,
      `INSTAGRAM_USER_ID`. ~30 minutos, una sola vez. Pasos en
      [difusion-redes.md](difusion-redes.md).
      **La misma app sirve para las tres cosas**: difusión a Facebook, a
      Instagram y, después, WhatsApp oficial.
- [ ] **Probar el Plan B (API oficial)** con el número de prueba de Meta, sin
      migrar nada. Ahora se verifica desde **Admin › WhatsApp → Plan B**: token
      válido, último mensaje recibido por esa vía, y un botón para mandar uno
      de prueba. Pasos en
      [manual-operativo-whatsapp.md](manual-operativo-whatsapp.md), sección 7.

---

## 3. Los teléfonos

- [ ] **Activar las tres eSIM** sin activar (68727584, 68727944, 72900149). Una
      línea inactiva no recibe el SMS de verificación: sin esto no se les puede
      registrar WhatsApp.
- [ ] **Registrar WhatsApp** en el respaldo 2 (68727584) y el explorador
      (68727944).
- [ ] **En el 67991916, NO.** Ése va a la API oficial como número de la marca, y
      registrarle WhatsApp común lo quema.
- [ ] Recuperar el **72900149** (puede necesitar el reinicio de 7 días de la
      verificación en dos pasos).

---

## 4. Los datos, que es lo que hace que todo lo demás sirva

Sin esto, el sitio y los agentes no tienen qué mostrar.

- [ ] **Los 888 horarios.** Ninguno cargado. "Abierto ahora" no puede funcionar,
      y el Nivel 0 del asistente sólo podría contestar dirección y teléfono.
      Es trabajo manual y no hay forma de evitarlo.
- [ ] **43 de los 67 nuevos no tienen WhatsApp.** Sin número, el comercio no
      tiene canal de contacto y la ficha es una vidriera muda.
- [ ] **194 comercios en la cola de revisión de rubros**, de los cuales 102 se
      resuelven con un clic (tienen una sola sugerencia).
- [ ] **`backend/scripts/regenerar_miniaturas.py`**: 1.079 fotos siguen con
      miniaturas de 200 px y se ven borrosas en las tarjetas.

---

## 5. Antes de salir a difundir

De las seis decisiones, éstas son las que **si no se cierran se cierran solas,
y mal**:

- [ ] **Topes de la recompensa al explorador**: por publicación, por persona y
      **de presupuesto total**. Sin el tercero, la semana que la idea se vuelva
      popular cuesta plata de verdad. Y se paga por lo **aprobado**, nunca por
      lo enviado.
- [ ] **Topes de la recompensa por traer usuarios.** Existe sólo la atribución
      (`usuarios.ref`); no hay registro de recompensas, ni cálculo, ni control
      de fraude.
- [ ] **`usuarios.ultima_actividad`** — hoy no se guarda, así que no hay forma
      de saber quién volvió a los 7 días. Y "7 días con la app instalada" **no
      es medible**: es una app web. Lo medible es que haya vuelto.

El tope del canal y el aviso al llegar a la cuota ya están hechos.

---

## 6. Producto — lo que sigue de Uruku AI

En orden de **valor sobre esfuerzo con los datos que hay**:

- [x] ~~Informe de demanda (Agente Analista)~~ — **hecho el 10/9**.
- [x] ~~**IA en la ingesta.**~~ **Hecho el 11/9.** Un worker revisa lo
      pendiente cada minuto y guarda el veredicto en la fila; la cola llega
      ordenada al moderador (rechazable y dudoso arriba). Migración `0103`.
      El auto-aprobar existe como perilla (`IA_AUTO_APROBAR_DESDE`) y arranca
      **apagado**: aprobar manda al canal y a las redes, y una foto que nadie
      miró en el muro de la marca no se deshace.
- [ ] **Nivel 0** — dirección, teléfono y cómo llegar por consulta directa, sin
      modelo. *Los horarios quedan afuera hasta que el punto 4 esté hecho.*
- [ ] **Resumen diario del canal** (una publicación con "las ofertas de hoy").
      El tope ya protege a los seguidores; esto agrega volumen sin costo.
- [ ] **Uruku Ayuda** — necesita un texto de preguntas frecuentes que hay que
      escribir primero, y no existe.
- [ ] **Agente Catálogo**, primero para uso interno. **Es lo que hace que el
      plan de Bs 1.250 tenga margen**: si dar de alta un comercio cuesta dos
      días de carga, el primer mes ya se fue.
- [ ] **Uruku Chat** — el agente de la ficha, con los datos que cargue el
      anterior.
- [ ] **Acciones** (crear oferta, cambiar precio) con confirmación y auditoría.
- [ ] **WhatsApp multi-tenant** — bloqueado por ser Tech Provider de Meta, que
      son meses de trámite ajeno. **Empezar el trámite ahora**, aunque el
      desarrollo vaya por otro lado.

---

## 7. Deuda técnica encontrada, chica y concreta

- [ ] **`_PLANES` en `comercio.py:33`** es código muerto: define
      `{gratis, pro, premium}` y no lo usa nadie. Borrarlo antes de que alguien
      lo "arregle" usándolo y rompa los planes nuevos.
- [ ] **`frontend/lib/types.ts:33`** declara `plan: "gratis" | "pro" |
      "premium"`. Los planes que se venden ahora son cinco. El tipo miente.
- [ ] **`planes_con_ingesta = "premium"`** (config): si alguien enciende
      `INGESTA_REQUIERE_PLAN`, ningún comercio con los planes nuevos podría
      publicar. Está apagado, así que es una bomba dormida, no un incendio.
- [ ] **Marcar los enlaces por red** para saber qué red trae gente al sitio.
      Hoy se elige dónde poner el esfuerzo por intuición.

---

## Lo que yo haría en este orden

1. **Desplegar** (0.1 y 0.2). Sin esto, nada de lo de arriba existe.
2. **Perfil del operativo y segundo admin del canal** (1). Minutos, y después
   ya no se pueden hacer.
3. **Encender el canal y las redes** (2). Todo es pegar credenciales.
4. **Horarios y rubros** (4). Es lo que hace que el sitio y los agentes tengan
   qué decir.
5. **Topes de las recompensas** (5) antes de prometer plata.
6. Recién ahí, seguir con los agentes (6).
