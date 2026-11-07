"use client";

import type { CSSProperties } from "react";
import { contacto, type TipoLead } from "@/lib/medicion";

/** Enlace que sale de URUKU y deja registrado que salió desde acá.
 *
 * Existe para los enlaces que viven en páginas de servidor (la ficha del
 * comercio), donde no se puede colgar un onClick sin un componente cliente.
 *
 * El registro es fire-and-forget a propósito: si el servidor de métricas está
 * caído, la persona igual llega a Google Maps. Perder un número no puede costar
 * una visita al local. */
export function LeadLink({
  comercioId, href, tipo, detalle, className, style, children,
}: {
  comercioId: string;
  href: string;
  tipo: TipoLead;
  /** La red (`instagram`, `facebook`, `tiktok`, `youtube`) cuando `tipo` es `red`. */
  detalle?: string;
  className?: string;
  style?: CSSProperties;
  children: React.ReactNode;
}) {
  return (
    <a className={className} style={style} href={href} target="_blank" rel="noopener"
       onClick={() => { void contacto(comercioId, tipo, { detalle }); }}>
      {children}
    </a>
  );
}
