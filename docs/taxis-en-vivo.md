# Taxis con ubicación en vivo — lo que hay que saber antes de construirlo

## La restricción que decide todo

**Una PWA no puede seguir la ubicación en segundo plano.** No es una limitación
de este proyecto: iOS mata el proceso cuando la app deja de estar en pantalla, y
Android la estrangula a los pocos minutos. Sólo hay posición mientras el
taxista tiene la pantalla encendida y la app abierta y visible.

Ningún taxista va a manejar ocho horas con el teléfono despierto mostrando
URUKU. Y si igual lo hiciera, el costo es suyo: batería y datos.

Eso significa que **"ver el taxi en tiempo real" con una PWA no funciona**. Para
que funcione hace falta una app nativa con permiso de ubicación en segundo
plano, y eso es otro producto: otra tienda, otra aprobación, otro
mantenimiento.

## Lo que sí sirve, y es casi todo el valor

Lo que necesita alguien que quiere un taxi no es ver el punto moviéndose: es
**conseguir uno ahora**. En orden de utilidad real:

1. **El teléfono, y que atienda.** Es lo que la gente hace hoy y funciona.
2. **Si está disponible o no.** Ver diez taxis y que ninguno conteste es peor
   que ver dos que sí.
3. **Dónde está la parada.** Fija, no la del auto.
4. La posición del auto en vivo.

Los tres primeros no necesitan nada que no exista ya.

## El camino por etapas

**Fase 1 — ahora (no cuesta nada nuevo).**
Rubro `taxis`, cada taxi o parada como una ficha con nombre, WhatsApp, teléfono,
horario y ubicación de la parada. El botón de llamar y el de "cómo llegar" ya
están. Sirve el primer día.

**Fase 2 — "disponible ahora".**
El taxista marca disponible/ocupado desde una pantalla de un botón, o mandando
un mensaje al grupo de WhatsApp (el canal que ya existe y que ya sabe usar). Se
apaga solo a las N horas: un "disponible" de ayer es peor que nada, porque el
comprador llama y no atiende.

Esto da el 80% del valor con el 5% del trabajo, y **no depende de que nadie deje
el teléfono prendido**.

**Fase 3 — ubicación en vivo, si la fase 2 demuestra que hace falta.**
Recién acá aparece el problema de fondo, y con la evidencia de si vale la pena.
Requiere app nativa, o aceptar que la posición sólo existe mientras el taxista
tiene URUKU abierto en pantalla — que en la práctica es cuando está parado
esperando, no manejando.

## Lo que hay que decidir antes, y no es técnico

- **¿El taxista quiere ser visto?** Publicar dónde está un auto es un dato
  sensible. Hace falta que lo prenda él y lo pueda apagar en un toque.
- **¿Quién responde si el taxi no llega?** Hoy URUKU dice explícitamente que no
  media en las transacciones. Mostrar un taxi "disponible" se acerca bastante a
  prometer un servicio.
- **¿Se muestran taxis sin registrar?** Un directorio incompleto de taxis puede
  ser peor que ninguno: el que no está pierde viajes por no haberse enterado.
