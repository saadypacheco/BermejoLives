# Qué falta — lista ordenada

> **Para operar los teléfonos —configuración, qué no hacer, y qué hacer cuando
> algo se rompe— está el
> [manual operativo](manual-operativo-whatsapp.md).**
>
> Al 15/9/2026. Ordenado por lo que **desbloquea a lo demás**, no por tamaño.
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

---

## 0. Hoy mismo, porque lo de abajo lo necesita

- [ ] **Desplegar `3a84fcc`** con la 0108 (planes). Prod está en `16fe18e` /
  backend `496b371`: la página de planes y las reglas de redes/gratis no
  existen todavía.
  `bash scripts/deploy-prod.sh --sql selfhost/postgres-init/0108_planes_sin_canal_con_chatbot.sql frontend backend`
- [ ] **Cargar la cotización de hoy** en `/contenido`. Está del 15 de agosto y
  el sitio lo dice en naranja. Y decidir **quién la carga cada mañana** (el
  Anfitrión se la pide a una casa de cambio por WhatsApp; 20 segundos).
- [ ] **Facebook e Instagram**: la app de Meta → `FACEBOOK_PAGE_ID`,
  `FACEBOOK_PAGE_TOKEN`, `INSTAGRAM_USER_ID`. **Ahora es una promesa vendida**:
  Destacado dice "tus ofertas en las redes de URUKU". Sin token, la cola
  espera y nada sale. `difusion-redes.md` tiene el paso a paso.
- [ ] **La URL de Facebook en `/contenido`** (`https://www.facebook.com/uruku.bo/`).

## 1. Los teléfonos (manual operativo, sección 2)

- [ ] **PIN de dos pasos** en la tablet y en el Samsung, con correo de recuperación.
- [ ] **Perfil URUKU también en el Samsung** (es el que crea los grupos).
- [ ] Copia de seguridad de WhatsApp en Google Drive, en el Samsung.
- [ ] **Activar las tres eSIM** (68727584, 68727944, 72900149) y registrar
  WhatsApp en respaldo y explorador. **En el 67991916, NO** (va a la API oficial).
- [ ] Recuperar el **72900149** (no agregarlo a grupos hasta entonces).
- [ ] **Probar el Plan B** (API oficial) con el número de prueba de Meta —
  `whatsapp-arquitectura-y-escala.md` tiene la guía.

## 2. Los datos, que es lo que hace que todo lo demás sirva

- [ ] **Los horarios.** Ninguno cargado. Ahora pesa más que antes: "¿qué hay
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
- [ ] **194 comercios en la cola de revisión de rubros.**
- [ ] **Nombres "Comercio"**: cientos de fichas se llaman así. Son a propósito
  (cargados desde la calle), pero en el asistente y en las listas se ven
  como cinco iguales. Cuando se les ponga nombre, todo mejora solo.

## 3. Antes de salir a difundir

- [ ] **Topes de la recompensa al explorador** (por publicación, por persona,
  por día) y **de la recompensa por traer usuarios**. Existe la atribución,
  no el tope: no prometer plata antes de esto.
- [ ] **`usuarios.ultima_actividad`** — no se guarda; sin eso no se sabe si un
  usuario traído volvió.
- [ ] **`?ref=` en los QR** del volante y la tarjeta (`ref=volante-<slug>`,
  `ref=mesa-<slug>`) y el conteo de llegadas por `ref` en el admin. Sin
  esto no se sabe si las tarjetas de mesa trajeron a alguien.
  `estrategia-marca-uruku.md` §4.
- [ ] **Panel de marca**: llegadas por `ref`, preguntas al asistente por día,
  👍/👎, comercios con papel. Cuatro números, una vez por semana.
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

- [ ] `/buscar?of=1` (Ofertas): el contador dice "N resultados" y la lista
  muestra sólo los que tienen oferta. Contar lo que se muestra.
- [ ] **`_PLANES` en `comercio.py:33`** es código muerto; **`frontend/lib/types.ts:33`**
  declara un `plan` que no coincide con la base; **`planes_con_ingesta = "premium"`**
  en config apunta a un plan oculto.
- [ ] `scripts/deploy-all.sh` está viejo (paths y sin GIT_SHA); `deploy-prod.sh`
  lo reemplaza. Borrarlo o apuntar la doc.
- [ ] **Marcar los enlaces por red** (`?ref=fb`, `?ref=ig`) en la difusión.

---

## Lo que yo haría en este orden

1. **Desplegar `3a84fcc`** y cargar la cotización de hoy (0). Diez minutos.
2. **Los tokens de Facebook e Instagram** (0): es lo único que hace que
   Destacado cumpla lo que dice.
3. **Horarios de casas de cambio, restaurantes y los que tienen grupo**, y el
   saber local de la calle (2). Es lo que hace que el asistente conteste de
   verdad, y es lo que ninguna base ni ningún modelo puede saber por vos.
4. **Los teléfonos** (1), antes de sumar más grupos.
5. **`?ref=` en los QR** (3), antes de repartir tarjetas: si no, no se puede
   saber si sirvieron.
6. Recién ahí, el Agente Catálogo y el Agente Marketing (4).
