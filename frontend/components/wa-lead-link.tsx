"use client";

import { waLink } from "@/lib/types";
import { registrarLead } from "@/lib/campo";

export function WaLeadLink({
  comercioId, whatsapp, mensaje, className, children,
}: {
  comercioId: string;
  whatsapp: string;
  mensaje: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <a
      className={className}
      href={waLink(whatsapp, mensaje)}
      target="_blank"
      rel="noopener"
      onClick={() => registrarLead(comercioId)}
    >
      {children}
    </a>
  );
}
