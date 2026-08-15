"use client";

import { useState } from "react";

/** Botón compartir: usa Web Share API (nativo en móvil) y cae a copiar el link. */
export function CompartirBoton({ titulo, texto, className }: { titulo: string; texto?: string; className?: string }) {
  const [copiado, setCopiado] = useState(false);

  async function compartir() {
    const url = typeof window !== "undefined" ? window.location.href : "";
    const data = { title: titulo, text: texto || titulo, url };
    if (typeof navigator !== "undefined" && navigator.share) {
      try {
        await navigator.share(data);
        return;
      } catch {
        return; // el usuario canceló: no hacemos nada
      }
    }
    try {
      await navigator.clipboard.writeText(url);
      setCopiado(true);
      setTimeout(() => setCopiado(false), 1800);
    } catch {
      /* sin clipboard: no-op */
    }
  }

  return (
    <button type="button" className={className || "uk-btn uk-btn-secondary"} onClick={compartir} aria-label="Compartir">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
        <circle cx="18" cy="5" r="3" /><circle cx="6" cy="12" r="3" /><circle cx="18" cy="19" r="3" />
        <path d="M8.6 13.5 15.4 17.5M15.4 6.5 8.6 10.5" />
      </svg>
      {copiado ? "¡Link copiado!" : "Compartir"}
    </button>
  );
}
