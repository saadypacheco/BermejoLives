"use client";

import { useFiltrosRapidos } from "./use-filtros-rapidos";

/** Dentro del formulario del buscador del encabezado: si los interruptores están prendidos, la búsqueda
 *  viaja con `abierto=1` / `cerca=1` (campos ocultos). Sin interruptores prendidos no dibuja nada. */
export function CamposFiltrosBusqueda() {
  const [f] = useFiltrosRapidos();
  return (
    <>
      {f.abiertos && <input type="hidden" name="abierto" value="1" />}
      {f.cerca && <input type="hidden" name="cerca" value="1" />}
    </>
  );
}
