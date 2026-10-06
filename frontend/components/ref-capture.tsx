"use client";

import { useEffect } from "react";
import { guardarRef, leerRef } from "@/lib/ref";

/**
 * Atribución de origen (referidos): si el usuario llega con ?ref=CODIGO (QR de un
 * negocio, punto, creador o vendedor), guarda ese código la PRIMERA vez
 * (first-touch, no se pisa mientras esté vigente). Se envía al registrarse para
 * saber de dónde vino. Vence a los 30 días (ver lib/ref.ts): pasado ese plazo,
 * un ref nuevo vuelve a guardarse.
 */
export function RefCapture() {
  useEffect(() => {
    try {
      const ref = new URLSearchParams(window.location.search).get("ref");
      if (ref && !leerRef()) guardarRef(ref);
    } catch {
      /* sin acceso a la URL o al almacenamiento — ignorar */
    }
  }, []);
  return null;
}
