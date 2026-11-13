# Importar negocios de una página de turismo (spec corta, 12/11/2026)

Pedido del dueño: la Secretaría de Turismo de Tarija (https://tarijaturismo.com, sitio de la Alcaldía) publica
listados de hoteles, restaurantes, operadoras y agencias con nombre, dirección, teléfono y Facebook. Quiere
traerlos a URUKU sin tipearlos. Primera página: Tarija; si después hay otras ciudades, cada sitio es un lector
aparte (cada página arma su HTML distinto).

## Decisiones

- **Entra por Importados** (`comercios_importados`, 0066) con `fuente = 'turismo'`. Nada aparece en el sitio hasta
  que una persona lo revisa y toca «Promover». Misma ficha de revisión que las tarjetas (`docs/carga-tarjetas.md`):
  campos editables, mapa con el punto arrastrable, «Buscar la dirección», aviso de repetido.
- **Sólo datos, nunca fotos ni textos.** Se copian nombre, dirección, teléfonos y enlace (web o Facebook): son
  datos de contacto públicos. Las fotos y las descripciones de la página tienen autor y no se traen.
  `cargado_por = 'import:turismo'` en el comercio promovido; el importado guarda la URL de la sección de origen.
- **Se corre a mano, una vez**, dentro del contenedor del backend (como `scripts/osm_import.py`). No hay botón ni
  tarea programada: la página cambia poco y no hace falta volver a leerla.
- **Páginas que lee (7):** dónde dormir, dónde comer, qué hacer, operadoras, agencias, cómo moverse (radio móviles y
  transporte a los alrededores, con destino y precio en la nota) y guías de turismo autorizados (sólo licencia vigente).
- **Buena educación con el sitio:** robots.txt lo permite; 1 pedido por segundo, User-Agent
  `URUKU/1.0 (+https://uruku.bo)`, 7 páginas en total.
- **Ubicación**: Nominatim, igual que las tarjetas (`tarjetas.buscar_direccion`, 1 pedido por segundo, acotado a la
  ciudad). Si no la encuentra, queda sin punto y se marca a mano.
- **Teléfonos**: la misma normalización que tarjetas (`repartir_telefonos`). Fijos de Tarija como `466-48444`
  se entienden como `4 6648444`.
- **Repetidos**: por teléfono (como tarjetas) y por nombre parecido en la misma ciudad.
- **Idempotente**: `fuente_id = 'turismo:<host>:<slug nombre>|<slug dirección>'`; correrlo dos veces no duplica.
  Una sucursal (otra dirección del mismo negocio) es otra fila.
- Entradas sin teléfono ni dirección no se traen. **Plazas, miradores, museos, centros culturales y atractivos de
  «Qué hacer» tampoco**: no son comercios, van a Lugares (`docs/lugares-turismo.md`).
- **Rubro sugerido** según la sección (hospedaje, restaurantes, comida rápida, cafetería, bebidas, nocturna,
  gimnasios, taxis). Agencias, operadoras, guías, complejos turísticos y balnearios van a `turismo`, que **se crea
  desde el panel** (Catálogo › Rubros, slug `turismo`) antes de correr el importador; si no existe, quedan sin rubro.
- **Guías**: son personas con su celular. Se promueven recién después de avisarles por WhatsApp (a mano).

## Uso

```
docker exec buscadonde-backend python -m app.services.importar_turismo --ciudad tarija --dry-run
docker exec buscadonde-backend python -m app.services.importar_turismo --ciudad tarija
```

`--dry-run` lee y muestra lo que cargaría sin escribir nada ni consultar Nominatim.

## Pantalla

- Filtro **Fuente: Todas / OSM / Tarjetas / Turismo** en Importados.
- La ficha de Turismo es la de tarjetas sin foto, con un enlace a la página de origen.

## Criterios de terminado

1. El dry-run sobre las páginas de Tarija lista ~340 negocios con nombre y al menos teléfono o dirección.
2. Correrlo dos veces no crea filas nuevas.
3. Cada fila trae un rubro sugerido según la sección (hotel, gastronomía…) o vacío si no hay uno que corresponda.
4. Un teléfono que ya tiene un comercio marca el repetido.
5. Promover crea el comercio con nombre, dirección, teléfonos, web y punto; no sale verificado ni confiable.
6. No se descarga ninguna imagen de la página.

## Ubicar por esquinas (13/11/2026)

En la carga real de Tarija, Nominatim ubicó 25 de 343: las direcciones vienen como
«Z/Central, Calle La Madrid #282 esq. Sucre» o «C/Sucre entre Corrado y Domingo Paz #0966», y Nominatim no entiende
«Z/», «B/», «esq.» ni «entre»; y aun limpiando, Tarija no tiene numeración en OpenStreetMap (cae en la calle, no en
el número). La forma boliviana de dar una dirección es la esquina o la cuadra, así que se ubica así:

1. **Partir la dirección** (`partir_direccion`): calle principal, número, `esquina` («esq.», «esquina», «casi»),
   `entre A y B`; se descartan zona y barrio («Z/…», «B/…», «Barrio …», «Zona …»), «C/», «Calle», «Av.»,
   «Nº», «#». Nombres normalizados (minúsculas, sin tildes, «Gral.» = «General», «O'Connor» / «O´connor» /
   «O’connor» iguales, «Mcal.» = «Mariscal»).
2. **Con las calles de la ciudad** (`calles_tramos`, «Calles y horarios», una fila por cuadra con nombre y
   geometría): «A esq. B» → el punto donde se tocan una cuadra de A y una de B; «A entre B y C» → el punto medio
   entre la esquina A–B y la esquina A–C (si las dos existen y están a menos de 600 m). Nombres comparados con
   tolerancia (una tilde o una abreviatura no impiden el match), sin adivinar: si hay dudas, no hay punto.
3. **Si no**, Nominatim con la dirección limpia («Calle La Madrid 282»): punto aproximado sobre la calle.
4. **Si no**, sin punto (se marca a mano).

Todo punto sigue entrando como **aproximado** (`ubicacion = 'aproximada'`) hasta que una persona lo confirma.
Sin servicios nuevos: la geometría ya está en la base.

**Volver a ubicar** los importados que quedaron sin punto, sin volver a leer la página:

```
docker exec buscadonde-backend python -m app.services.ubicar_direccion --ciudad tarija --dry-run --solo-esquinas   # segundos: sin Nominatim, lista las calles que no reconoce
docker exec buscadonde-backend python -m app.services.ubicar_direccion --ciudad tarija --dry-run
docker exec buscadonde-backend python -m app.services.ubicar_direccion --ciudad tarija
```

Recorre `comercios_importados` con `estado = 'nuevo'`, `fuente in ('turismo','tarjeta')`, sin `lat` y con
dirección; muestra cuántos ubicó por esquina, por cuadra, por calle y cuántos no. Si la ciudad no tiene calles
cargadas lo avisa (se importan desde el panel, «Calles y horarios») y sigue sólo con Nominatim. El mismo ubicador
lo usan el importador de turismo, la carga de tarjetas y el botón «Buscar la dirección» del panel.
