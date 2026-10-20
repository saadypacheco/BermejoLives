"use client";

import { Children, useCallback, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";

/**
 * La fila de «Novedades» de la portada, en carrusel: las novedades primero y
 * después los comercios destacados (los que pagan), con su foto.
 *
 * Avanza sola de a una tarjeta cada `cadaMs`; se frena mientras la persona la
 * toca, la recorre o tiene el mouse encima, y no se mueve con «reducir
 * movimiento». Al llegar al final vuelve al principio. Las tarjetas son las de
 * siempre (`.uk-offer`): sólo cambia que van en una fila que se desliza.
 */
export function CarruselNovedades({ children, cadaMs = 4500 }: { children: React.ReactNode; cadaMs?: number }) {
  const pista = useRef<HTMLDivElement>(null);
  const [quieto, setQuieto] = useState(false);
  // ¿Hay tarjetas fuera de la vista? Sin eso las flechas no tienen a dónde ir y
  // parecen rotas (pasaba con 3 o 4 tarjetas en la compu).
  const [desborda, setDesborda] = useState(false);
  const total = Children.count(children);

  useEffect(() => {
    const p = pista.current;
    if (!p) return;
    const medir = () => setDesborda(p.scrollWidth > p.clientWidth + 4);
    medir();
    const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(medir) : null;
    ro?.observe(p);
    window.addEventListener("resize", medir);
    return () => { ro?.disconnect(); window.removeEventListener("resize", medir); };
  }, [total]);

  const paso = useCallback(() => {
    const el = pista.current?.firstElementChild as HTMLElement | null;
    if (!el) return 0;
    const gap = parseFloat(getComputedStyle(pista.current as HTMLElement).columnGap || "0") || 0;
    return el.getBoundingClientRect().width + gap;
  }, []);

  const mover = useCallback((dir: 1 | -1) => {
    const p = pista.current;
    if (!p) return;
    const fin = p.scrollWidth - p.clientWidth - 4;
    if (dir === 1 && p.scrollLeft >= fin) p.scrollTo({ left: 0, behavior: "smooth" });
    else if (dir === -1 && p.scrollLeft <= 4) p.scrollTo({ left: p.scrollWidth, behavior: "smooth" });
    else p.scrollBy({ left: dir * paso(), behavior: "smooth" });
  }, [paso]);

  useEffect(() => {
    if (quieto || total < 2) return;
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) return;
    const id = window.setInterval(() => {
      if (document.visibilityState !== "visible") return;
      const p = pista.current;
      // Si entra todo en la pantalla no hay nada que pasar.
      if (!p || p.scrollWidth <= p.clientWidth + 4) return;
      mover(1);
    }, cadaMs);
    return () => window.clearInterval(id);
  }, [quieto, total, cadaMs, mover]);

  return (
    <div className="uk-carrusel"
         onMouseEnter={() => setQuieto(true)} onMouseLeave={() => setQuieto(false)}
         onTouchStart={() => setQuieto(true)} onTouchEnd={() => setTimeout(() => setQuieto(false), 6000)}
         onFocusCapture={() => setQuieto(true)} onBlurCapture={() => setQuieto(false)}>
      <div ref={pista} className="uk-carrusel-pista" role="list">
        {Children.map(children, (c) => <div role="listitem" className="uk-carrusel-item">{c}</div>)}
      </div>
      {desborda && (
        <>
          <button type="button" className="uk-carrusel-flecha izq" aria-label="Anterior" onClick={() => mover(-1)}>
            <Ic n="volver" s={20} />
          </button>
          <button type="button" className="uk-carrusel-flecha der" aria-label="Siguiente" onClick={() => mover(1)}>
            <Ic n="seguir" s={20} />
          </button>
        </>
      )}
    </div>
  );
}
