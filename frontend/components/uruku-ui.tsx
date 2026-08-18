// Piezas compartidas del diseño URUKU (puras, sin estado → server o client).
import React from "react";

/** Ícono SVG de línea (liviano, sin librerías). */
export const Ic = ({ d }: { d: string }) => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

/** Categorías del sitio (label + query de búsqueda + path del ícono).
 * Orden priorizado para Bermejo (ciudad-frontera): ropa/calzado y consumo primero.
 * TODO: seguir afinando rubros con datos reales de la ciudad. */
export const CATS = [
  { label: "Ropa", q: "ropa", d: "M20 6l-4-3-4 2-4-2-4 3 3 3v10h10V9z" },
  { label: "Zapatillas", q: "calzado", d: "M3 14l6-4 2 2h6a4 4 0 0 1 4 4v1H3zM3 17h18" },
  { label: "Belleza", q: "belleza", d: "M9 2h6v3l-1 2v13a1 1 0 0 1-1 1h-2a1 1 0 0 1-1-1V7L9 5zM9 11h6" },
  { label: "Mascotas", q: "mascota", d: "M4.5 12.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM9 8a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM15 8a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM19.5 12.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM12 20c3 0 5-2 5-4s-2-4-5-4-5 2-5 4 2 4 5 4z" },
  { label: "Restaurantes", q: "restaurante", d: "M6 3v7a2 2 0 0 0 2 2v9M6 3v4M9 3v4M9 3v7a2 2 0 0 1-2 2M18 3c-1.5 0-3 1.8-3 5s1.5 4 3 4v9" },
  { label: "Mercados", q: "mercado", d: "M3 3h2l2.4 12.3a1 1 0 0 0 1 .7h9.7a1 1 0 0 0 1-.8L22 7H6M9 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM18 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2z" },
  { label: "Electrónica", q: "electronica", d: "M3 4h18v13H3zM8 21h8M12 17v4" },
  { label: "Celulares", q: "celular", d: "M7 2h10v20H7zM10 18h4" },
  { label: "Tablets", q: "tablet", d: "M5 3h14v18H5zM11 18h2" },
  { label: "Ferretería", q: "ferreteria", d: "M14 2l8 8-3 3-8-8zM11 5L3 13v4M3 21l6-6" },
  { label: "Hogar", q: "hogar", d: "M3 11l9-8 9 8M5 10v10h14V10" },
  { label: "Electrodomésticos", q: "electrodomesticos", d: "M6 2h12v20H6zM6 9h12M9 5v2M9 12v3" },
  { label: "Salud", q: "farmacia", d: "M12 21s-7-4.5-9.5-9A5 5 0 0 1 12 6a5 5 0 0 1 9.5 6C19 16.5 12 21 12 21z" },
  { label: "Más", q: "", d: "M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z" },
];

/** Logo de marca por red social (clave de la tabla `redes`). SVG RELLENO (paths
 * estilo simple-icons) para que sean los logos reconocibles, no íconos de línea. */
export const RED_D: Record<string, string> = {
  facebook: "M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z",
  instagram: "M12 2.163c3.204 0 3.584.012 4.85.07 1.366.062 2.633.334 3.608 1.308.975.975 1.246 2.242 1.308 3.608.058 1.266.069 1.646.069 4.85 0 3.204-.012 3.584-.07 4.85-.062 1.366-.333 2.633-1.308 3.608-.975.975-2.242 1.246-3.608 1.308-1.266.058-1.646.07-4.85.07-3.204 0-3.584-.012-4.85-.07-1.366-.062-2.633-.334-3.608-1.308-.975-.975-1.246-2.242-1.308-3.608C2.175 15.647 2.163 15.267 2.163 12S2.175 8.416 2.233 7.15c.062-1.366.333-2.633 1.308-3.608.975-.975 2.242-1.246 3.608-1.308C8.416 2.175 8.796 2.163 12 2.163zM12 0C8.741 0 8.332.014 7.052.072 5.197.157 3.355.673 2.014 2.014.673 3.355.157 5.197.072 7.052.014 8.332 0 8.741 0 12s.014 3.668.072 4.948c.085 1.855.601 3.697 1.942 5.038 1.341 1.341 3.183 1.857 5.038 1.942C8.332 23.986 8.741 24 12 24s3.668-.014 4.948-.072c1.855-.085 3.697-.601 5.038-1.942 1.341-1.341 1.857-3.183 1.942-5.038.058-1.28.072-1.689.072-4.948s-.014-3.668-.072-4.948c-.085-1.855-.601-3.697-1.942-5.038C20.645.673 18.803.157 16.948.072 15.668.014 15.259 0 12 0zm0 5.838a6.162 6.162 0 100 12.324 6.162 6.162 0 000-12.324zM12 16a4 4 0 110-8 4 4 0 010 8zm6.406-11.845a1.44 1.44 0 100 2.881 1.44 1.44 0 000-2.881z",
  tiktok: "M12.525.02c1.31-.02 2.61-.01 3.91-.02.08 1.53.63 3.09 1.75 4.17 1.12 1.11 2.7 1.62 4.24 1.79v4.03c-1.44-.05-2.89-.35-4.2-.97-.57-.26-1.1-.59-1.62-.93-.01 2.92.01 5.84-.02 8.75-.08 1.4-.54 2.79-1.35 3.94-1.31 1.92-3.58 3.17-5.91 3.21-1.43.08-2.86-.31-4.08-1.03-2.02-1.19-3.44-3.37-3.65-5.71-.02-.5-.03-1-.01-1.49.18-1.9 1.12-3.72 2.58-4.96 1.66-1.44 3.98-2.13 6.15-1.72.02 1.48-.04 2.96-.04 4.44-.99-.32-2.15-.23-3.02.37-.63.41-1.11 1.04-1.36 1.75-.21.51-.15 1.08-.14 1.62.24 1.64 1.82 3.02 3.5 2.87 1.12-.01 2.19-.66 2.77-1.61.19-.33.4-.67.41-1.06.1-1.79.06-3.57.07-5.36.01-4.03-.01-8.05.02-12.07z",
  whatsapp: "M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z",
  whatsapp_canal: "M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413z",
  youtube: "M23.498 6.186a3.016 3.016 0 00-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 00.502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 002.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 002.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z",
};

/** Formatea un valor de cotización. */
export const money = (v: number | null | undefined) =>
  v && v > 0 ? v.toLocaleString("es-AR", { maximumFractionDigits: 2 }) : "s/d";

/** Base de URL por red, para cuando en el admin cargan un handle (@usuario) en vez de la URL completa. */
const RED_BASE: Record<string, string> = {
  instagram: "https://instagram.com/",
  tiktok: "https://tiktok.com/@",
  facebook: "https://facebook.com/",
  youtube: "https://youtube.com/@",
};

/** Devuelve una URL absoluta y válida para la red, sea que cargaron la URL completa o solo el handle. */
export function redHref(clave: string, url: string): string {
  const u = url.trim();
  if (/^https?:\/\//i.test(u)) return u;              // ya es URL completa
  const handle = u.replace(/^@+/, "");                 // saca @ del handle
  const base = RED_BASE[clave];
  if (base) return base + handle;                      // arma URL por red
  return u.includes(".") ? `https://${u}` : u;         // fallback: prepend https si parece dominio
}

/** Color oficial de cada red (fondo del tile). Instagram va con su gradiente. */
export const RED_BG: Record<string, string> = {
  facebook: "#1877F2",
  instagram: "linear-gradient(45deg,#feda75,#fa7e1e,#d62976,#962fbf,#4f5bd5)",
  tiktok: "#010101",
  whatsapp: "#25D366",
  whatsapp_canal: "#25D366",
  youtube: "#FF0000",
};

/** Íconos de redes (desde la tabla `redes`, cargados en el admin). Tile con el color
 * oficial de la marca + glifo blanco (estilo app-icon). */
export function SocialLinks({ redes, cls }: { redes: { clave: string; url: string | null; etiqueta: string }[]; cls: string }) {
  const items = redes.filter((r) => r.url);
  if (!items.length) return null;
  return (
    <div className={cls}>
      {items.map((r) => (
        <a key={r.clave} href={redHref(r.clave, r.url as string)} target="_blank" rel="noopener" aria-label={r.etiqueta}
          style={{ background: RED_BG[r.clave] ?? "#444" }}>
          <svg viewBox="0 0 24 24" fill="#fff" aria-hidden><path d={RED_D[r.clave] ?? RED_D.facebook} /></svg>
        </a>
      ))}
    </div>
  );
}
