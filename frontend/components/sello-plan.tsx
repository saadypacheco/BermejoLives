"use client";

import { Ic, type NombreIcono } from "@/components/ic";
import type { EstadoPlan } from "@/lib/campo";

/** Cómo se ve cada estado del plan para el agente. Texto + ícono (nunca sólo
 *  color) y SIN precios ni fechas de pago. */
export const PLAN_CFG: Record<EstadoPlan, { label: string; icono: NombreIcono; color: string; detalle: string }> = {
  al_dia:   { label: "Al día",       icono: "estrella", color: "var(--neon)",      detalle: "Tiene un plan pago y está al día." },
  cortesia: { label: "De cortesía",  icono: "destacado", color: "var(--blue-soft)", detalle: "Tiene el plan de cortesía: no paga ni vence." },
  gratis:   { label: "Gratis",       icono: "si",       color: "var(--txt-2)",     detalle: "Está en el plan Básico, gratis para siempre." },
  vencido:  { label: "Vencido",      icono: "aviso",    color: "var(--pink)",      detalle: "Su plan pago venció: volvió a gratis y sigue en el mapa." },
};

/** El sello del plan. Sin `plan` (el servidor todavía no lo manda, o es un dato
 *  viejo guardado en el celular) no dibuja nada. */
export function SelloPlan({ plan }: { plan: EstadoPlan | null | undefined }) {
  if (!plan || !PLAN_CFG[plan]) return null;
  const cfg = PLAN_CFG[plan];
  return (
    <span title={cfg.detalle}
          style={{ display: "inline-flex", alignItems: "center", gap: 4, fontSize: 11.5, fontWeight: 700, padding: "2px 9px", borderRadius: 999,
                   color: cfg.color, border: `1px solid ${cfg.color}`, whiteSpace: "nowrap" }}>
      <Ic n={cfg.icono} s={12} peso="fill" /> {cfg.label}
    </span>
  );
}
