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
