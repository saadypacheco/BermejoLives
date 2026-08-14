"use client";

import { useEffect } from "react";

/**
 * Atribución de origen (referidos): si el usuario llega con ?ref=CODIGO (QR de un
 * negocio, punto, creador o vendedor), guarda ese código en localStorage la PRIMERA
 * vez (first-touch, no se pisa). Se envía al registrarse para saber de dónde vino.
 */
export function RefCapture() {
  useEffect(() => {
    try {
      const ref = new URLSearchParams(window.location.search).get("ref");
      if (ref && !localStorage.getItem("uruku_ref")) {
        localStorage.setItem("uruku_ref", ref.slice(0, 64));
      }
    } catch {
      /* localStorage no disponible — ignorar */
    }
  }, []);
  return null;
}
