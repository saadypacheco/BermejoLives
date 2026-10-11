"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { TopeFotos } from "@/lib/upload";
import { Ic } from "@/components/ic";

export type DecisionTope = "reemplazar" | "pagar";

function precio(n: number, moneda: string): string {
  const monto = Number.isInteger(n) ? String(n) : n.toFixed(2);
  return `${moneda === "BOB" ? "Bs" : moneda} ${monto}`;
}

const boton: React.CSSProperties = {
  width: "100%", minHeight: 48, padding: "10px 14px", borderRadius: 12, fontSize: 15, fontWeight: 700,
  display: "flex", alignItems: "center", justifyContent: "center", gap: 8, textAlign: "center",
  cursor: "pointer", lineHeight: 1.25,
};

/**
 * Se abre cuando la galería llegó al tope de fotos del plan (409 del backend).
 * Deja elegir: pagar una foto extra (sólo el comerciante), borrar la más vieja
 * (se muestra ANTES de confirmar) o cancelar. No hace nada por su cuenta: avisa
 * la decisión a quien lo abrió, que reintenta la subida con el campo que toque.
 *
 * Va en un portal (a `#ukroot`, o a `body` si no hay): las tarjetas `.glass` tienen
 * backdrop-filter y un `position: fixed` adentro se centraría sobre la tarjeta
 * y no sobre la pantalla.
 */
export function TopeFotosDialogo({ tope, puedePagarExtra, onElegir }: {
  tope: TopeFotos;
  /** Sólo la galería del comerciante: el agente y el admin no comprometen plata. */
  puedePagarExtra: boolean;
  /** `null` = cancelar. */
  onElegir: (d: DecisionTope | null) => void;
}) {
  const [montado, setMontado] = useState(false);
  const cancelar = useRef<HTMLButtonElement>(null);
  useEffect(() => setMontado(true), []);

  // Escape cancela; el fondo no se desplaza mientras está abierto.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onElegir(null); };
    window.addEventListener("keydown", onKey);
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = antes; };
  }, [onElegir]);

  // El foco arranca en «Cancelar»: lo irreversible nunca queda a un Enter de distancia.
  useEffect(() => { if (montado) cancelar.current?.focus(); }, [montado]);

  if (!montado) return null;

  const pagar = puedePagarExtra && tope.precio_extra > 0;
  return createPortal(
    <div
      onClick={(e) => { if (e.target === e.currentTarget) onElegir(null); }}
      style={{
        position: "fixed", inset: 0, zIndex: 1300, background: "rgba(0,0,0,.7)",
        display: "flex", alignItems: "center", justifyContent: "center", padding: 16, overflowY: "auto",
      }}
    >
      <div
        role="dialog" aria-modal="true" aria-labelledby="tope-fotos-titulo"
        style={{
          width: "100%", maxWidth: 420, maxHeight: "100%", overflowY: "auto", background: "var(--bg-2, #0e1320)",
          color: "var(--txt, #e8edf4)", border: "1px solid var(--stroke-2, #444)", borderRadius: 16, padding: 18,
          display: "grid", gap: 14, boxShadow: "0 12px 40px rgba(0,0,0,.4)",
        }}
      >
        <div>
          <h2 id="tope-fotos-titulo" style={{ margin: 0, fontSize: 17, display: "flex", alignItems: "center", gap: 8 }}>
            <Ic n="aviso" s={20} /> Llegaste al tope de fotos
          </h2>
          <p style={{ margin: "8px 0 0", fontSize: 14, color: "var(--txt-2, #aab4c3)", lineHeight: 1.45 }}>
            {tope.limite > 0
              ? `Tu galería ya tiene las ${tope.limite} fotos que permite tu plan. Para subir esta, elegí qué hacer.`
              : "Tu galería ya tiene todas las fotos que permite tu plan. Para subir esta, elegí qué hacer."}
          </p>
        </div>

        {tope.mas_vieja && (
          <div style={{
            display: "flex", alignItems: "center", gap: 12, padding: 10, borderRadius: 12,
            border: "1px solid var(--stroke-2, #444)",
          }}>
            <img
              src={tope.mas_vieja.url} alt="La foto más vieja de tu galería"
              style={{ width: 84, height: 84, objectFit: "cover", borderRadius: 10, flex: "none", background: "var(--stroke-2, #444)" }}
            />
            <div style={{ fontSize: 13.5, lineHeight: 1.4 }}>
              <b>Esta es la que se borraría.</b>
              <div style={{ color: "var(--txt-3, #8a97a3)", marginTop: 2 }}>La más vieja de tu galería.</div>
            </div>
          </div>
        )}

        <div style={{ display: "grid", gap: 10 }}>
          {pagar && (
            <div style={{ display: "grid", gap: 4 }}>
              <button type="button" onClick={() => onElegir("pagar")}
                style={{ ...boton, background: "var(--neon, #1D8D52)", color: "#04240f", border: "none" }}>
                <Ic n="pagos" s={18} /> Pagar {precio(tope.precio_extra, tope.moneda)} por una foto extra
              </button>
              <small style={{ color: "var(--txt-3, #8a97a3)", fontSize: 12.5, textAlign: "center" }}>
                Se suma a tu próximo pago.
              </small>
            </div>
          )}
          {tope.mas_vieja && (
            <button type="button" onClick={() => onElegir("reemplazar")}
              style={{ ...boton, background: "transparent", color: "var(--txt, #e8edf4)", border: "1.5px solid var(--pink, #d33)" }}>
              <Ic n="cerrar" s={16} /> Borrar esa y subir la nueva
            </button>
          )}
          <button ref={cancelar} type="button" onClick={() => onElegir(null)}
            style={{ ...boton, background: "transparent", color: "var(--txt-2, #aab4c3)", border: "1.5px solid var(--stroke-2, #556)" }}>
            Cancelar
          </button>
        </div>
      </div>
    </div>,
    // Dentro de `#ukroot` si existe: ahí viven las variables del tema (claro u
    // oscuro) y un portal a `body` quedaría fuera de ellas.
    document.getElementById("ukroot") ?? document.body,
  );
}
