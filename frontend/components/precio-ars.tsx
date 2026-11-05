"use client";

import { createContext, useContext } from "react";
import { precioArsTexto } from "@/lib/precios-pure";

/**
 * «≈ $ 14.710 ARS» al lado de un precio en bolivianos.
 *
 * El cambio del día lo trae el marco (`UrukuShell`), que ya lo lee para el
 * encabezado: lo pone acá UNA vez con `CambioArsProvider` y cualquier precio de
 * la página —sea de un componente de servidor o de uno de cliente— lo toma sin
 * que haya que pasarlo de mano en mano. Fuera del marco, o en una ciudad que
 * no es de frontera, o sin cambio cargado, el valor es `null` y `PrecioArs` no
 * dibuja NADA: nunca un «≈ $ 0» ni un precio inventado.
 */
const CambioArs = createContext<number | null>(null);

/** `arsPorBs`: cuántos Bs vale 1 ARS (`tasasDe(...).ars_bob`), o `null` si no se muestra. */
export function CambioArsProvider({ arsPorBs, children }: { arsPorBs: number | null; children: React.ReactNode }) {
  return <CambioArs.Provider value={arsPorBs}>{children}</CambioArs.Provider>;
}

/** La aproximación en pesos de un precio. Sólo si el precio es en Bs y hay cambio. */
export function PrecioArs({ precio, moneda, enLinea = false }: {
  precio: number | null;
  moneda: string;
  /** Al lado del precio, en el mismo renglón (por defecto va debajo). */
  enLinea?: boolean;
}) {
  const arsPorBs = useContext(CambioArs);
  const texto = precioArsTexto(precio, moneda, arsPorBs);
  if (!texto) return null;
  return (
    <span className={`uk-ars${enLinea ? " uk-ars-linea" : ""}`} title="Aproximado, con el cambio del día">{texto}</span>
  );
}
