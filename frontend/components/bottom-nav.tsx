"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { clearComercio } from "@/lib/comercio";
import { clearUsuario } from "@/lib/usuario";

const ic = (d: string) => (
  <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>
);

// "Mapa" (antes "Inicio"): muestra todos los negocios registrados, sean
// comercios, hospitales, restaurantes, hoteles, etc. — no es solo "inicio".
const ITEMS = [
  { key: "Mapa", href: "/", d: "M3 11l9-8 9 8M5 10v10h14V10" },
  { key: "Guardados", href: "/guardados", d: "M6 3h12v18l-6-4-6 4V3z" },
  { key: "Ofertas", href: "/?of=1", d: "M20.6 13.4 11 3.8H4v7l9.6 9.6a2 2 0 0 0 2.8 0l4.2-4.2a2 2 0 0 0 0-2.8zM7 7h.01" },
  { key: "Perfil", href: "/perfil", d: "M20 21a8 8 0 1 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" },
];

export function BottomNav({ active = "Mapa" }: { active?: string }) {
  const router = useRouter();
  function salir() {
    clearComercio();
    clearUsuario();
    router.push("/");
  }
  return (
    <nav className="bottomnav">
      {ITEMS.map((it) => (
        <Link key={it.key} href={it.href} className={`bn-item ${active === it.key ? "active" : ""}`}>
          {ic(it.d)}<span>{it.key}</span>
        </Link>
      ))}
      <button type="button" className="bn-item" onClick={salir}>
        {ic("M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9")}<span>Salir</span>
      </button>
    </nav>
  );
}
