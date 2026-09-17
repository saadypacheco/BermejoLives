"use client";

import { useEffect } from "react";
import { registrarLead } from "@/lib/campo";

/** Loguea una "vista" de la ficha del comercio (KPI: locales más visitados),
 *  con el `?ref=` si llegó por un QR (volante, tarjeta de mesa, el QR de la
 *  ficha) o un enlace marcado. Es lo que después dice si las tarjetas
 *  trajeron a alguien. */
export function VistaLogger({ comercioId }: { comercioId: string }) {
  useEffect(() => {
    let origen: string | null = null;
    try { origen = new URLSearchParams(window.location.search).get("ref"); } catch { /* nada */ }
    registrarLead(comercioId, "vista", null, origen);
  }, [comercioId]);
  return null;
}
