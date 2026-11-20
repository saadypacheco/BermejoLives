"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";

/**
 * Una fila de tarjetas que se desliza, con flechas en la compu (en el celular se arrastra con el dedo y las
 * flechas no se dibujan). Sin avance automático: es una vidriera, no un anuncio. Las tarjetas traen su propio
 * ancho (`.uk-hc-prod`, `.uk-hc-com`).
 */
export function PistaCarrusel({ children, etiqueta }: { children: React.ReactNode; etiqueta: string }) {
  const pista = useRef<HTMLDivElement>(null);
  const [desborda, setDesborda] = useState(false);

  useEffect(() => {
    const p = pista.current;
    if (!p) return;
    const medir = () => setDesborda(p.scrollWidth > p.clientWidth + 4);
    medir();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(medir) : null;
    ro?.observe(p);
    return () => ro?.disconnect();
  }, [children]);

  const mover = useCallback((dir: 1 | -1) => {
    const p = pista.current;
    if (p) p.scrollBy({ left: dir * p.clientWidth * 0.8, behavior: "smooth" });
  }, []);

  return (
    <div className="uk-hc-carrusel">
      <div ref={pista} className="uk-hc-pista" role="list" aria-label={etiqueta}>{children}</div>
      {desborda && (
        <>
          <button type="button" className="uk-carrusel-flecha izq" aria-label="Anterior" onClick={() => mover(-1)}><Ic n="volver" s={20} /></button>
          <button type="button" className="uk-carrusel-flecha der" aria-label="Siguiente" onClick={() => mover(1)}><Ic n="seguir" s={20} /></button>
        </>
      )}
    </div>
  );
}
