"use client";

import { useEffect, useState } from "react";
import { alCambiar, alternarReserva, estaReservado, itemDeOferta } from "@/lib/reservas";
import type { FeedItem } from "@/lib/types";

/** "Reservar" sobre una oferta.
 *
 * Va en la oferta y no en el comercio: se reserva una cosa, no un local. Ese
 * detalle es el que decide la forma de todo lo demás — por eso las ofertas se
 * muestran una por una en la tarjeta del buscador y no como un contador.
 */
export function ReservarBoton({ oferta, className }: { oferta: FeedItem; className?: string }) {
  // Arranca en false y se corrige al montar: `localStorage` no existe en el
  // servidor, y leerlo durante el render daría una pantalla distinta a la que
  // el servidor mandó (error de hidratación).
  const [puesto, setPuesto] = useState(false);
  useEffect(() => {
    const leer = () => setPuesto(estaReservado(oferta.id));
    leer();
    return alCambiar(leer);
  }, [oferta.id]);

  return (
    <button
      type="button"
      className={`uk-reservar${puesto ? " puesto" : ""}${className ? " " + className : ""}`}
      aria-pressed={puesto}
      onClick={(e) => {
        // Casi siempre está adentro de un enlace a la ficha.
        e.preventDefault();
        e.stopPropagation();
        setPuesto(alternarReserva(itemDeOferta(oferta)));
      }}
    >
      {puesto ? "✓ En tu reserva" : "Reservar"}
    </button>
  );
}
