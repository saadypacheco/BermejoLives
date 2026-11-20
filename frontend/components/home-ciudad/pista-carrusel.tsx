"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";

/** Los puntitos son páginas, no tarjetas: con 12 tarjetas serían 12 puntos y se leen como ruido. */
const MAX_PUNTOS = 6;

/**
 * Una fila de tarjetas que se desliza (docs/home-ciudades.md §11). Sin avance automático: es una vidriera, no un
 * anuncio. Las tarjetas traen su propio ancho (`.uk-hc-prod`, `.uk-hc-com`).
 *
 * - En la compu: flechas AFUERA de la foto (en los márgenes de la pista), no encima.
 * - En pantallas táctiles: nada encima de las fotos; el dedo arrastra y abajo van unos puntitos que dicen dónde está
 *   la persona. Qué se ve en cada caso lo decide el CSS (`hover: none`), así el primer dibujo del servidor es igual.
 */
export function PistaCarrusel({ children, etiqueta }: { children: React.ReactNode; etiqueta: string }) {
  const pista = useRef<HTMLDivElement>(null);
  const [desborda, setDesborda] = useState(false);
  const [puntos, setPuntos] = useState(0);
  const [activo, setActivo] = useState(0);

  const medir = useCallback(() => {
    const p = pista.current;
    if (!p) return;
    const sobra = p.scrollWidth - p.clientWidth;
    setDesborda(sobra > 4);
    const paginas = sobra > 4 ? Math.min(MAX_PUNTOS, Math.max(2, Math.ceil(p.scrollWidth / p.clientWidth))) : 0;
    setPuntos(paginas);
    setActivo(paginas > 0 ? Math.round((p.scrollLeft / sobra) * (paginas - 1)) : 0);
  }, []);

  useEffect(() => {
    const p = pista.current;
    if (!p) return;
    medir();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(medir) : null;
    ro?.observe(p);
    return () => ro?.disconnect();
  }, [children, medir]);

  const mover = useCallback((dir: 1 | -1) => {
    const p = pista.current;
    if (p) p.scrollBy({ left: dir * p.clientWidth * 0.8, behavior: "smooth" });
  }, []);

  return (
    <div className="uk-hc-carrusel">
      <div ref={pista} className="uk-hc-pista" role="list" aria-label={etiqueta} onScroll={medir}>{children}</div>
      {desborda && (
        <>
          <button type="button" className="uk-carrusel-flecha izq" aria-label="Anterior" onClick={() => mover(-1)}><Ic n="volver" s={20} /></button>
          <button type="button" className="uk-carrusel-flecha der" aria-label="Siguiente" onClick={() => mover(1)}><Ic n="seguir" s={20} /></button>
        </>
      )}
      {puntos > 1 && (
        <div className="uk-hc-puntos" aria-hidden="true">
          {Array.from({ length: puntos }, (_, i) => <i key={i} className={i === activo ? "on" : undefined} />)}
        </div>
      )}
    </div>
  );
}
