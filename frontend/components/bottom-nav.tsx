import Link from "next/link";

const ic = (d: string) => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

const ITEMS = [
  { href: "/", label: "Inicio", d: "M3 11l9-8 9 8M5 10v10h14V10" },
  { href: "/buscar", label: "Mapa", d: "M9 3 3 6v15l6-3 6 3 6-3V3l-6 3-6-3zM9 3v15M15 6v15" },
  { href: "/mi-comercio", label: "Guardados", d: "M6 3h12v18l-6-4-6 4V3z" },
  { href: "/buscar", label: "Ofertas", d: "M20.6 13.4 11 3.8H4v7l9.6 9.6a2 2 0 0 0 2.8 0l4.2-4.2a2 2 0 0 0 0-2.8zM7 7h.01" },
  { href: "/mi-comercio", label: "Perfil", d: "M20 21a8 8 0 1 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" },
];

export function BottomNav({ active = "Inicio" }: { active?: string }) {
  return (
    <nav className="bottomnav">
      {ITEMS.map((it) => (
        <Link key={it.label} href={it.href} className={`bn-item ${active === it.label ? "active" : ""}`}>
          {ic(it.d)}<span>{it.label}</span>
        </Link>
      ))}
    </nav>
  );
}
