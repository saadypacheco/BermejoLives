"use client";

import { useEffect } from "react";
import { registrarLead } from "@/lib/campo";

/** Loguea una "vista" de la ficha del comercio (KPI: locales más visitados),
 *  con el `?ref=` si llegó por un QR (volante, tarjeta de mesa, el QR de la
 *  ficha) o un enlace marcado. Es lo que después dice si las tarjetas
 *  trajeron a alguien.
 *
 *  Sin `?ref=` toma el `?utm_source=`: los asistentes de IA (ChatGPT, por
 *  ejemplo) marcan sus enlaces con `utm_source=chatgpt.com`, y así `leads.origen`
 *  dice que la persona vino de ahí (§3.11 de docs/visibilidad-buscadores-ia.md).
 *  El backend limpia el valor igual que el `ref`. */
export function VistaLogger({ comercioId }: { comercioId: string }) {
  useEffect(() => {
    let origen: string | null = null;
    try {
      const q = new URLSearchParams(window.location.search);
      origen = q.get("ref") || q.get("utm_source");
    } catch { /* nada */ }
    registrarLead(comercioId, "vista", null, origen);
  }, [comercioId]);
  return null;
}
