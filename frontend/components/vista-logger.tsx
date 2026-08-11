"use client";

import { useEffect } from "react";
import { registrarLead } from "@/lib/campo";

/** Loguea una "vista" de la ficha del comercio (KPI: locales más visitados). */
export function VistaLogger({ comercioId }: { comercioId: string }) {
  useEffect(() => {
    registrarLead(comercioId, "vista");
  }, [comercioId]);
  return null;
}
