"use client";

import { Ic, type NombreIcono } from "@/components/ic";

/** Los «sí / no» de «Lo que suma» en la ficha (spec docs/ficha-destacados.md).
 *  Cada uno aparece en la ficha como un sello sólo si está tildado. */
export type Tildes = {
  tiene_pasero: boolean;
  envios_internacionales: boolean;
  tiene_factura: boolean;
  talles_especiales: boolean;
};
export const CLAVES_TILDES: (keyof Tildes)[] = ["tiene_pasero", "envios_internacionales", "tiene_factura", "talles_especiales"];

const ITEMS: { k: keyof Tildes; icono: NombreIcono; dueno: string; agente: string; ayuda: string }[] = [
  { k: "tiene_pasero", icono: "pasero", dueno: "Tengo pasero", agente: "Tiene pasero",
    ayuda: "Alguien que le cruza la compra al comprador." },
  { k: "envios_internacionales", icono: "envios", dueno: "Hago envíos", agente: "Hace envíos",
    ayuda: "Manda pedidos a otro país." },
  { k: "tiene_factura", icono: "factura", dueno: "Doy factura", agente: "Da factura",
    ayuda: "Entrega factura al comprador que la pide." },
  { k: "talles_especiales", icono: "ropa", dueno: "Trabajo talles especiales", agente: "Trabaja talles especiales",
    ayuda: "Talles grandes o muy chicos, que no se consiguen en cualquier lado." },
];

/**
 * Los tildes, en filas grandes (44 px o más) para tocar con el dedo. El estado
 * se lee por el tilde y por el borde, no sólo por el color.
 *
 * `quien` decide la persona del verbo: el dueño en Mi comercio habla de sí
 * («Tengo pasero»); el agente habla del local («Tiene pasero»).
 */
export function TildesSuma({ valor, onChange, quien }: {
  valor: Tildes;
  onChange: (k: keyof Tildes, v: boolean) => void;
  quien: "dueno" | "agente";
}) {
  return (
    <div style={{ display: "grid", gap: 8 }}>
      {ITEMS.map((it) => {
        const on = valor[it.k];
        return (
          <label key={it.k}
                 style={{ display: "flex", alignItems: "center", gap: 12, minHeight: 48, padding: "8px 12px", borderRadius: 12, cursor: "pointer",
                          border: `1px solid ${on ? "var(--neon)" : "var(--stroke)"}`,
                          background: on ? "rgba(57,255,158,.08)" : "transparent" }}>
            <input type="checkbox" checked={on} onChange={(e) => onChange(it.k, e.target.checked)}
                   style={{ width: 22, height: 22, flexShrink: 0 }} />
            <span style={{ display: "flex", flexDirection: "column", minWidth: 0 }}>
              <b style={{ fontSize: 14, display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Ic n={it.icono} s={17} /> {quien === "dueno" ? it.dueno : it.agente}
              </b>
              <span style={{ fontSize: 12, color: "var(--txt-3)", lineHeight: 1.35 }}>{it.ayuda}</span>
            </span>
          </label>
        );
      })}
    </div>
  );
}
