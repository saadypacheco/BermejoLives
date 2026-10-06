# Segunda pasada del agente: completar un comercio ya cargado — spec

> **Estado: implementada el 6/10/2026.**

## El problema

El agente vuelve a un comercio que ya está en el mapa para cargar todo lo que
tiene: horario, qué vende, fotos del local, puesto, redes. Hoy la app del agente
tiene DOS editores que no se ven entre sí:

- **«Editar»** (en «Comercios de mi ciudad», y lo que abre «Es este» desde «Ya
  cargados acá cerca»): nombre, WhatsApp, referencia, rubros, foto y galería.
- **La segunda pasada** (`components/segunda-pasada.tsx`): teléfono, correo,
  modalidad, mercado y puesto, qué vende, catálogo, redes, canal. Sólo aparece
  justo después de dar de alta un comercio NUEVO.

Y **ninguno carga el horario**, que es el dato más preguntado: el filtro «Sin
horario» llevaba a un editor que no lo podía cargar. (El backend ya lo acepta:
`PATCH /campo/mis-comercios/{id}` con `horario`.)

## Qué se construye

**Una sola pantalla «Completar comercio»** para cualquier comercio ya cargado.
Se abre desde:
- «Es este» en «Ya cargados acá cerca»;
- «Editar» en «Comercios de mi ciudad» (incluido el filtro «Sin horario»);
- el final del alta de un comercio nuevo (reemplaza la segunda pasada suelta).

Arriba, **«Le falta»**: la lista de lo que el comercio no tiene, cada ítem un
toque que lleva a su campo. Lo que ya está cargado no se vuelve a pedir.

| Ítem | Falta si |
|---|---|
| Horario | `horario` vacío |
| Contacto | sin WhatsApp ni teléfono |
| Foto de la vidriera | sin `portada_url` |
| Fotos del local | la galería vacía |
| Qué vende | `prod_obs_human` vacío |
| Rubro | sin rubro |
| Puesto | está en un mercado o galería y no tiene puesto |

Debajo, **todos los campos**, en el orden de la charla con el dueño: horario →
contacto → qué vende → rubros → mercado y puesto → fotos y videos → redes,
catálogo y canal → correo.

**El horario** con los mismos atajos que el panel del admin (presets de un
toque, «Igual que el anterior», y escribirlo a mano). Al guardarlo deja de ser
«estimado».

**El WhatsApp de un comercio que ya lo tiene no se cambia** (regla de seguridad
de la limpieza): se muestra y se ofrece «Cambié de número». Si está vacío, se
completa.

## Criterios de aceptación

1. Desde «Es este» se llega a «Completar comercio» con «Le falta» calculado.
2. Desde «Sin horario», un toque abre el comercio con el horario listo para
   cargar; guardado, sale del filtro.
3. Todo lo que tenía «Editar» y la segunda pasada se carga desde la misma
   pantalla. No quedan dos editores.
4. El horario se carga con un preset en un toque.
5. `tsc` sin errores; tests del backend en verde.
