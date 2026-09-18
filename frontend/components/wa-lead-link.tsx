"use client";

import { waLink } from "@/lib/types";
import { registrarLead } from "@/lib/campo";

export function WaLeadLink({
  comercioId, whatsapp, mensaje, className, children, nombre,
}: {
  comercioId: string;
  whatsapp: string;
  mensaje: string;
  className?: string;
  children: React.ReactNode;
  /** El nombre del local, para el «¿te contestó Rústico?» de después. */
  nombre?: string;
}) {
  return (
    <a
      className={className}
      href={waLink(whatsapp, mensaje)}
      target="_blank"
      rel="noopener"
      onClick={() => registrarLead(comercioId, "whatsapp", null, null, nombre)}
    >
      {children}
    </a>
  );
}
