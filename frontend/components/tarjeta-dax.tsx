"use client";

import { Ic } from "@/components/ic";

/** Tarjeta del carrusel que abre a Dax (el asistente flotante) con el evento
 *  `uk-abrir-ayuda` que escucha `components/asistente.tsx`. Es el «cómo hago
 *  para encontrar algo»: la gente le escribía al WhatsApp de URUKU preguntando
 *  dónde conseguir productos. */
export function TarjetaDax() {
  return (
    <button type="button" className="uk-offer sin-foto uk-offer-servicio uk-offer-dax"
            onClick={() => window.dispatchEvent(new CustomEvent("uk-abrir-ayuda"))}>
      <span className="uk-offer-tag">¿Cómo encuentro algo?</span>
      <span className="uk-offer-emoji"><Ic n="buscar" s={64} peso="fill" /></span>
      <span className="uk-offer-body">
        <span className="uk-offer-tit">Preguntale a Dax dónde conseguirlo</span>
        <small>Te dice qué comercio lo tiene, si está abierto y su WhatsApp</small>
      </span>
    </button>
  );
}
