"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";
import { InstalarAppBoton } from "@/components/instalar-app";

/** Botón "Ingresar" en el header: ofrece las dos entradas de login (comprador y comercio). */
export function IngresarMenu() {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const h = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false); };
    document.addEventListener("click", h);
    return () => document.removeEventListener("click", h);
  }, []);

  return (
    <div className="uk-acct" ref={ref}>
      {/* El rótulo va en su propio <span> para poder esconderlo en los celulares
          más angostos (queda el ícono). El aria-label evita que sin texto el
          botón quede mudo para un lector de pantalla. */}
      <button type="button" className="uk-pill uk-acct-btn" aria-label="Ingresar" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" width="16" height="16" aria-hidden="true"><path d="M20 21a8 8 0 1 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" /></svg>
        <span className="uk-pill-txt">Ingresar</span>
      </button>
      {open && (
        <div className="uk-acct-menu">
          <Link href="/perfil" className="uk-acct-item" onClick={() => setOpen(false)}>
            <b>Soy comprador</b><small>Guardá tus locales favoritos (entrás con tu WhatsApp)</small>
          </Link>
          <Link href="/mi-comercio" className="uk-acct-item" onClick={() => setOpen(false)}>
            <b>Tengo un negocio</b><small>Entrá a tu panel de comercio</small>
          </Link>
          {/* Se esconde solo si la app ya está instalada. */}
          <InstalarAppBoton variante="menu" alElegir={() => setOpen(false)} />
        </div>
      )}
    </div>
  );
}
