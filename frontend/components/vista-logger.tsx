"use client";

import { useEffect } from "react";
import { contacto, origenDeLaUrl } from "@/lib/medicion";

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
    // `contacto()` deduplica (una vista por ficha cada 30 min por pestaña) y no cuenta al equipo ni al
    // dueño del comercio.
    void contacto(comercioId, "vista", { origen: origenDeLaUrl(window.location.search) });
  }, [comercioId]);
  return null;
}
