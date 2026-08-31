"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { alCambiar, leerReservas, porComercio } from "@/lib/reservas";

/** Barra flotante con lo que el comprador lleva reservado.
 *
 * Sólo aparece si hay algo: una barra permanente vacía le come alto a todas las
 * pantallas para no decir nada. Y nombra al comercio cuando es uno solo —
 * "2 en A&M Calzados" recuerda a dónde hay que ir a buscarlo, "2 reservas" no.
 */
export function ReservaBarra() {
  const [grupos, setGrupos] = useState<ReturnType<typeof porComercio>>([]);
  useEffect(() => {
    const leer = () => setGrupos(porComercio(leerReservas()));
    leer();
    return alCambiar(leer);
  }, []);

  const total = grupos.reduce((n, g) => n + g.items.length, 0);
  if (total === 0) return null;

  return (
    <Link href="/reservas" className="uk-reserva-barra">
      <span className="n">{total}</span>
      <span className="txt">
        {grupos.length === 1
          ? `${total === 1 ? "1 producto" : `${total} productos`} en ${grupos[0].comercio_nombre}`
          : `${total} productos en ${grupos.length} comercios`}
      </span>
      <span className="ver">Ver reserva ›</span>
    </Link>
  );
}
