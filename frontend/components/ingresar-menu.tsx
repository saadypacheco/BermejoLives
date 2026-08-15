"use client";

import { useState, useRef, useEffect } from "react";
import Link from "next/link";

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
      <button type="button" className="uk-pill uk-acct-btn" onClick={() => setOpen((o) => !o)}>
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" width="16" height="16"><path d="M20 21a8 8 0 1 0-16 0M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8z" /></svg>
        Ingresar
      </button>
      {open && (
        <div className="uk-acct-menu">
          <Link href="/perfil" className="uk-acct-item" onClick={() => setOpen(false)}>
            <b>Soy comprador</b><small>Guardá locales y ofertas (entrás con tu WhatsApp)</small>
          </Link>
          <Link href="/mi-comercio" className="uk-acct-item" onClick={() => setOpen(false)}>
            <b>Tengo un negocio</b><small>Entrá a tu panel de comercio</small>
          </Link>
        </div>
      )}
    </div>
  );
}
