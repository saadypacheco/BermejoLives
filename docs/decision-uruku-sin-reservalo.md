# Un solo producto: URUKU. Reservalo se deja de usar (2026-08-29)

> Reemplaza la sección "Búsqueda unificada" de
> [contrato-integracion.md](contrato-integracion.md) y deja
> [marketplace-ecommerce.md](marketplace-ecommerce.md) y
> [plan-tienda-reservalo.md](plan-tienda-reservalo.md) como historia.

## Qué se decidió

Todo pasa a vivir en URUKU. El comprador busca, ve **ofertas** con su precio y su
comercio, y **reserva**. No hay segundo sitio.

## Por qué

**El contrato decía lo contrario y era la decisión peor fundamentada del
diseño.** Todas las del marketplace (D1 a D7) tienen su razón escrita; la de
"mostrar comercios y no productos sueltos" tenía una línea: *"el mapa de
comercios es el diferencial"*. Y está fechada el **22 de junio**, cuando no
había un comercio cargado ni una foto analizada. Se decidió sobre una idea del
producto, no sobre evidencia.

**Los números.** Al 29/8: URUKU tiene 790 comercios con foto, rubro deducido y
ubicación. Reservalo tiene un esquema de 26 tablas y prácticamente nada adentro
— su backup pesa 17 KB y creció 2 KB en once días, mientras el de URUKU pasó de
14 KB a 448 KB. No es que se usó poco: no arrancó.

**El motivo de fondo.** Reservalo le pedía al comerciante cargar productos con
precio en un sistema aparte. A un comerciante de Bermejo que todavía no manda
una foto por WhatsApp, ese salto le queda lejos. Ningún rediseño del sitio
arregla eso.

**Y lo que lo destrabó**: al decidir que se publica SÓLO por WhatsApp, la oferta
que manda el comerciante **es** el producto. Deja de haber dos catálogos, así
que deja de haber algo que integrar.

## Cómo queda la pantalla

Un solo listado, dos bloques rotulados:

    3 ofertas con precio
      [ Zapatilla urbana · Bs 260 · A&M Lencería · a 240 m ]
    17 comercios que venden zapatillas
      [ las tarjetas de hoy ]

Sin pestañas. El rótulo explica por qué está cada cosa donde está, nadie queda
escondido, y **hoy se ve igual que ahora** porque el primer bloque está vacío.

Efecto de negocio buscado: el comerciante que no publica se ve debajo del que
sí. Abre el sitio, busca lo que él vende, y ve competidores arriba con precio.
Ése es el argumento para que empiece a mandar fotos, sin tener que explicárselo.

## La reserva

- **Una reserva por comercio, varias abiertas a la vez.** El mensaje va al
  WhatsApp de ESE local, así que un carrito mezclado no se puede mandar a
  ningún lado. Si el comprador elige de dos locales, se arman dos reservas — y
  se entiende solo, porque va a caminar a dos lugares distintos.
- Vive en el celular, **sin cuenta ni login**.
- **La confirma el vendedor por WhatsApp**, en el mismo grupo por donde manda
  las ofertas: no aprende nada nuevo.
- Hasta que confirme, la pantalla NO puede decir "reservado". Nada queda
  apartado. Si alguien camina veinte cuadras confiando en eso y el producto no
  está, se pierden el comprador y el comercio de una vez.

## Qué NO se hace

**No se borra nada.** Se sacan las puertas de entrada (el modo "Productos" del
buscador, el chip "Productos ↗", los enlaces de la ficha) y el contenedor y los
datos quedan donde están. La decisión es reversible mientras no se borre.

Lo que sí se cae de la lista de pendientes: sacar Supabase de Reservalo,
replicarlo en QA, y la búsqueda unificada multi-vendedor.

## Lo que se pierde, dicho de frente

Carrito con varios ítems, checkout, listas de precio, variantes por talle y
color, cuentas corriente. Si algún día hace falta vender online de verdad, hay
que volver a construirlo. Se decide igual porque **hoy nada de eso está en uso**
y sostenerlo cuesta más que rehacerlo el día que haga falta.
