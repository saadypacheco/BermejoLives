"use client";

import { registrarLead, type TipoLead } from "@/lib/campo";

/** Enlace que sale de URUKU y deja registrado que salió desde acá.
 *
 * Existe para los enlaces que viven en páginas de servidor (la ficha del
 * comercio), donde no se puede colgar un onClick sin un componente cliente.
 *
 * El registro es fire-and-forget a propósito: si el servidor de métricas está
 * caído, la persona igual llega a Google Maps. Perder un número no puede costar
 * una visita al local. */
export function LeadLink({
  comercioId, href, tipo, className, children,
}: {
  comercioId: string;
  href: string;
  tipo: TipoLead;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <a className={className} href={href} target="_blank" rel="noopener"
       onClick={() => registrarLead(comercioId, tipo)}>
      {children}
    </a>
  );
}
