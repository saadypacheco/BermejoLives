// Piezas compartidas del diseño URUKU (puras, sin estado → server o client).
import React from "react";

/** Ícono SVG de línea (liviano, sin librerías). */
export const Ic = ({ d }: { d: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

/** Categorías del sitio (label + query de búsqueda + path del ícono). */
export const CATS = [
  { label: "Restaurantes", q: "restaurante", d: "M6 3v7a2 2 0 0 0 2 2v9M6 3v4M9 3v4M9 3v7a2 2 0 0 1-2 2M18 3c-1.5 0-3 1.8-3 5s1.5 4 3 4v9" },
  { label: "Supermercados", q: "supermercado", d: "M3 3h2l2.4 12.3a1 1 0 0 0 1 .7h9.7a1 1 0 0 0 1-.8L22 7H6M9 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM18 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" },
  { label: "Ropa", q: "ropa", d: "M20 6l-4-3-4 2-4-2-4 3 3 3v10h10V9z" },
  { label: "Salud", q: "farmacia", d: "M12 21s-7-4.5-9.5-9A5 5 0 0 1 12 6a5 5 0 0 1 9.5 6C19 16.5 12 21 12 21z" },
  { label: "Ferretería", q: "ferreteria", d: "M14 2l8 8-3 3-8-8zM11 5L3 13v4M3 21l6-6" },
  { label: "Belleza", q: "belleza", d: "M9 2h6v3l-1 2v13a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1V7L9 5zM9 11h6" },
  { label: "Mascotas", q: "mascota", d: "M4.5 12.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM9 8a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM15 8a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM19.5 12.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM12 20c3 0 5-2 5-4s-2-4-5-4-5 2-5 4 2 4 5 4z" },
  { label: "Más", q: "", d: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" },
];

/** Path del ícono por red social (clave de la tabla `redes`). */
export const RED_D: Record<string, string> = {
  tiktok: "M9 18a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM12 15V4l7-1v9",
  instagram: "M7 2h10a5 5 0 0 1 5 5v10a5 5 0 0 1-5 5H7a5 5 0 0 1-5-5V7a5 5 0 0 1 5-5zM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8zM17.5 6.5h.01",
  facebook: "M14 9h3V5h-3a4 4 0 0 0-4 4v2H7v4h3v6h4v-6h3l1-4h-4V9a1 1 0 0 1 1-1z",
  youtube: "M22 8.2a3 3 0 0 0-2.1-2.1C18 5.5 12 5.5 12 5.5s-6 0-7.9.6A3 3 0 0 0 2 8.2 31 31 0 0 0 1.5 12 31 31 0 0 0 2 15.8a3 3 0 0 0 2.1 2.1c1.9.6 7.9.6 7.9.6s6 0 7.9-.6a3 3 0 0 0 2.1-2.1A31 31 0 0 0 22.5 12 31 31 0 0 0 22 8.2zM10 15V9l5 3z",
  whatsapp_canal: "M12 3a9 9 0 0 0-7.7 13.6L3 21l4.5-1.2A9 9 0 1 0 12 3z",
};

/** Formatea un valor de cotización. */
export const money = (v: number | null | undefined) =>
  v && v > 0 ? v.toLocaleString("es-AR", { maximumFractionDigits: 2 }) : "s/d";

/** Íconos de redes (desde la tabla `redes`, cargados en el admin). */
export function SocialLinks({ redes, cls }: { redes: { clave: string; url: string | null; etiqueta: string }[]; cls: string }) {
  const items = redes.filter((r) => r.url);
  if (!items.length) return null;
  return (
    <div className={cls}>
      {items.map((r) => (
        <a key={r.clave} href={r.url as string} target="_blank" rel="noopener" aria-label={r.etiqueta}>
          <Ic d={RED_D[r.clave] ?? "M4 4h16v16H4z"} />
        </a>
      ))}
    </div>
  );
}
