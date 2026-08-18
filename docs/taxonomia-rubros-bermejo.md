# Taxonomía de rubros para Bermejo (borrador para revisar)

> Objetivo: que el **agente elija un rubro amplio de un toque** (rápido en la calle) y
> escriba/grabe "qué vende" con **sus palabras**, y que el **buscador** encuentre igual
> gracias a **sinónimos AR/BO**. Nadie tiene que memorizar el "término correcto".
> Base: feedback de campo (acolchados, ropa americana, Tramontina, ollas usadas…) +
> [buscador-ia.md](buscador-ia.md) + [reglas-carga-comercios.md](reglas-carga-comercios.md).

## Principio
- **Rubro = categoría amplia** (lista corta y tap-eable). Un local puede tener **varios**.
- **"Qué vende" = texto libre** con las palabras reales del local ("acolchados, ropa de cama").
- **Sinónimos** (abajo) los maneja el **buscador**, no el agente. Así "championes",
  "zapatillas" y "tenis" caen todos en Calzado, y "acolchado", "cubrecama", "colcha" y
  "edredón" matchean lo mismo.
- Diferencia clave de frontera: **nuevo vs. americano/usado** (feria americana). Se marca
  como **atributo/palabra**, no como rubro nuevo, salvo que convenga separarlo (ver Ropa/Calzado).

## Rubros propuestos (los que toca el agente)

| Rubro | Qué entra | Sinónimos / términos que el buscador debe matchear (AR · BO · local) |
|---|---|---|
| **Ropa** | Indumentaria nueva | ropa, prendas, indumentaria, boutique, remera·polera, pantalón, campera·chamarra, pollera·falda, ropa interior, bebé |
| **Ropa americana / usada** | Feria americana, segunda mano | ropa americana, feria, usada, de fardo, segunda mano, roperos |
| **Calzado** | Zapatos y zapatillas (nuevo) | calzado, zapatos, **zapatillas·championes·tenis**, botas, sandalias, ojotas·chinelas |
| **Zapatillas americanas / usadas** | Calzado usado importado | zapatillas americanas, championes usados, calzado usado, feria |
| **Hogar y blanco** | Textil de casa | **acolchado·cubrecama·colcha·edredón**, ropa de cama, sábanas, **frazada·cobija**, cortinas, toallas, colchones, almohadas |
| **Bazar y cocina** | Utensilios, vajilla, ollas | **ollas·Tramontina·Essen**, sartenes, vajilla, cubiertos, utensilios, termos, bazar |
| **Electrodomésticos / línea blanca** | Electro grande | **heladera·refrigerador·frigo**, **lavarropas·lavadora**, cocina, microondas, licuadora, ventilador |
| **Electrónica / tecnología** | TV, audio, compu | TV·televisor, audio, parlantes, computación, notebook·laptop, tablet |
| **Celulares** | Teléfonos y accesorios | celular·teléfono·móvil, fundas, cargadores, auriculares, reparación de pantallas |
| **Ferretería / construcción** | Herramientas y materiales | ferretería, herramientas, pintura, cemento, cerámicos, sanitarios, electricidad |
| **Repuestos / neumáticos / motos** | Autopartes y gomería | repuestos, autopartes, **neumático·llanta·cubierta**, gomería, aceite, moto, accesorios moto |
| **Farmacia / perfumería / limpieza** | Salud, cosmética, limpieza | farmacia, remedios·medicamentos, perfumería, cosmética, **artículos de limpieza·insumos de limpieza** |
| **Alimentos / mercado** | Abarrotes y frescos | alimentos, abarrotes, **verduras·hortalizas**, frutas, carnicería, fiambrería, panadería |
| **Bebidas** | Gaseosas y licorería | bebidas, **gaseosas·refrescos**, agua, cerveza, licorería, vinos |
| **Muebles** | Muebles de hogar | muebles, sillas, mesas, roperos, placares, sommier |
| **Juguetería / librería** | Juguetes y escolar | juguetería, librería, escolar, útiles, papelería |
| **Usados en general / feria** | Segunda mano variado | usados, feria, segunda mano, todo suelto, remate |
| **Servicios** | No-venta (cambio, envíos…) | **cambio de moneda·cambista**, envíos, transporte, peluquería, gomería (servicio) |
| **Otros** | Lo que no encaja | (fallback) |

## Cómo esto alimenta el buscador (fases)
- **Ahora (Nivel 0-1, $0)**: el rubro va a la ficha + a la búsqueda full-text (ya existe,
  acento-insensible). Sumamos un **diccionario de sinónimos** corto (la col. de la derecha)
  para que "championes"→Calzado, "cobija"→Hogar, "llanta"→Neumáticos, etc.
- **Fase 2 (semántico)**: embeddings del texto {nombre + qué vende + rubros} → "algo para
  la cama" cae en Hogar sin que nadie lo programe. Ver [buscador-ia.md](buscador-ia.md).

## Nuevo vs. americano/usado — decisión
Bermejo tiene mucho **usado/feria americana**. Dos opciones:
- **(A)** Rubros separados "Ropa americana" y "Zapatillas americanas" (como en la tabla) →
  el comprador filtra fácil "usado" vs "nuevo". **Recomendado** (es un diferencial local).
- **(B)** Un solo rubro Ropa/Calzado + atributo "usado/americano". Menos pines, menos filtro.
Se puede empezar con (A) para lo más marcado (ropa y calzado) y (B) para el resto.

## Próximo paso (cuando lo revises)
1. **Ajustá esta lista** (agregá/sacá rubros, corregí sinónimos con términos reales de Bermejo).
2. La **cargamos en la tabla `rubros`** (seed) → aparecen como chips en el alta y filtros del mapa.
3. Sumamos el **diccionario de sinónimos** al buscador (Nivel 1).
4. Más adelante, embeddings (Fase 2) para el semántico.

> Regla de oro: **rubros amplios + sinónimos ricos**. No obligamos al agente a decidir
> terminología en la calle; el buscador hace el trabajo fino.
