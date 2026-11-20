"use client";

import Link from "next/link";
import { conFiltros } from "@/lib/filtros-rapidos";
import { useFiltrosRapidos } from "@/components/home-ciudad/use-filtros-rapidos";

const ic = (d: string) => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

// "Inicio" = landing para el comprador (/inicio). "Mapa" = el mapa con todos
// los comercios (/). "Cambio" = la cotización y el conversor: en una ciudad
// de frontera, "cuánto son mis pesos" se pregunta más veces por día que
// cualquier otra cosa, y merece el lugar en la barra. Perfil sigue en el
// header ("Ingresar"), que es donde lo busca el que tiene cuenta.
const ITEMS = [
  { key: "Inicio", href: "/", d: "M3 11l9-8 9 8M5 10v10h14V10" },
  { key: "Mapa", href: "/buscar?vista=mapa", d: "M9 3 3 6v15l6-3 6 3 6-3V3l-6 3-6-3zM9 3v15M15 6v15" },
  // Ofertas y Novedades son la misma pantalla con dos solapas, así que con
  // un botón se llega a las dos y la barra no pasa de cinco.
  { key: "Ofertas", href: "/ofertas", d: "M20.6 13.4 11 3.8H4v7l9.6 9.6a2 2 0 0 0 2.8 0l4.2-4.2a2 2 0 0 0 0-2.8zM7 7h.01" },
  // "Guía" en lugar de "Guardados": el que llega a Bermejo necesita la guía
  // antes que los favoritos, que siguen en el pie y en el perfil.
  { key: "Guía", href: "/guia", d: "M4 19.5A2.5 2.5 0 0 1 6.5 17H20M4 19.5A2.5 2.5 0 0 0 6.5 22H20V2H6.5A2.5 2.5 0 0 0 4 4.5v15zM9 7h7M9 11h5" },
  { key: "Cambio", href: "/cambio", d: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 6.5v11M14.8 9.3c-.3-1.1-1.4-1.8-2.8-1.8-1.6 0-2.8.9-2.8 2.1 0 1.3 1.2 1.8 2.8 2.2 1.6.4 2.8.9 2.8 2.2 0 1.3-1.2 2.2-2.8 2.2-1.5 0-2.6-.8-2.9-1.9" },
];

// Sin la guía (que hoy es la de Bermejo) no hay Guía ni Cambio en la barra:
// vuelven Guardados y Perfil, que tienen sentido en cualquier ciudad.
const ITEMS_SIN_GUIA = [
  ITEMS[0], ITEMS[1], ITEMS[2],
  { key: "Guardados", href: "/guardados", d: "M6 3h12v18l-6-4-6 4V3z" },
  { key: "Perfil", href: "/perfil", d: "M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" },
];

// Las ciudades que no son Bermejo (docs/home-ciudades.md §8): Inicio · Mapa · Dax · Novedades · Guardados. Dax va
// al centro, con su cara en un círculo que sobresale, y abre el panel (el evento lo escucha components/asistente.tsx).
const ITEMS_CON_DAX = [
  ITEMS[0], ITEMS[1], null,
  { key: "Novedades", href: "/novedades", d: "M4 5h16v14H4zM8 9h8M8 13h8M8 17h5" },
  { key: "Guardados", href: "/guardados", d: "M6 3h12v18l-6-4-6 4V3z" },
];

export function BottomNav({ active = "Mapa", conGuia = true, conDax = false }: { active?: string; conGuia?: boolean; conDax?: boolean }) {
  const [rapidos] = useFiltrosRapidos();
  if (conDax) {
    return (
      <nav className="bottomnav bottomnav-dax" aria-label="Navegación principal">
        {ITEMS_CON_DAX.map((it) => it ? (
          <Link key={it.key} href={conFiltros(it.href, rapidos)} className={`bn-item ${active === it.key ? "active" : ""}`}
                aria-current={active === it.key ? "page" : undefined}>
            {ic(it.d)}<span>{it.key}</span>
          </Link>
        ) : (
          <button key="Dax" type="button" className="bn-item bn-dax" aria-haspopup="dialog" aria-label="Abrir Dax, tu guía"
                  onClick={() => window.dispatchEvent(new CustomEvent("uk-abrir-ayuda"))}>
            <img className="bn-dax-cara" src="/dax-avatar.png" alt="" width={46} height={46} />
            <span>Dax</span>
          </button>
        ))}
      </nav>
    );
  }
  return (
    <nav className="bottomnav">
      {(conGuia ? ITEMS : ITEMS_SIN_GUIA).map((it) => (
        <Link key={it.key} href={it.href} className={`bn-item ${active === it.key ? "active" : ""}`}>
          {ic(it.d)}<span>{it.key}</span>
        </Link>
      ))}
    </nav>
  );
}
