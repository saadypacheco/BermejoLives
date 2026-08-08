"use client";

import Link from "next/link";

const ic = (d: string) => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

// "Inicio" = landing para el comprador (/inicio). "Mapa" = el mapa con todos
// los comercios (/). Salir vive en Perfil ("Cerrar sesión").
const ITEMS = [
  { key: "Inicio", href: "/", d: "M3 11l9-8 9 8M5 10v10h14V10" },
  { key: "Mapa", href: "/mapa", d: "M9 3 3 6v15l6-3 6 3 6-3V3l-6 3-6-3zM9 3v15M15 6v15" },
  { key: "Ofertas", href: "/mapa?of=1", d: "M20.6 13.4 11 3.8H4v7l9.6 9.6a2 2 0 0 0 2.8 0l4.2-4.2a2 2 0 0 0 0-2.8zM7 7h.01" },
  { key: "Guardados", href: "/guardados", d: "M6 3h12v18l-6-4-6 4V3z" },
  { key: "Perfil", href: "/perfil", d: "M20 21a8 8 0 1 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" },
];

export function BottomNav({ active = "Mapa" }: { active?: string }) {
  return (
    <nav className="bottomnav">
      {ITEMS.map((it) => (
        <Link key={it.key} href={it.href} className={`bn-item ${active === it.key ? "active" : ""}`}>
          {ic(it.d)}<span>{it.key}</span>
        </Link>
      ))}
    </nav>
  );
}
