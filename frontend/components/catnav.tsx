"use client";

import Link from "next/link";
import { useRef, useState, useEffect, useCallback } from "react";
import { CATS } from "@/components/uruku-ui";

/** Nav de categorías tipo carrusel: scroll horizontal + flechas. La flecha derecha
 * avanza y, si ya estás al final, vuelve al principio (loop). La izquierda aparece
 * cuando ya scrolleaste. */
export function CatNav({ active }: { active?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [overflow, setOverflow] = useState(false);
  const [atStart, setAtStart] = useState(true);
  const [atEnd, setAtEnd] = useState(false);

  const update = useCallback(() => {
    const el = ref.current;
    if (!el) return;
    setOverflow(el.scrollWidth > el.clientWidth + 2);
    setAtStart(el.scrollLeft <= 2);
    setAtEnd(el.scrollLeft + el.clientWidth >= el.scrollWidth - 2);
  }, []);

  useEffect(() => {
    update();
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [update]);

  const next = () => {
    const el = ref.current;
    if (!el) return;
    if (el.scrollLeft + el.clientWidth >= el.scrollWidth - 4) {
      el.scrollTo({ left: 0, behavior: "smooth" }); // al final → vuelve al principio
    } else {
      el.scrollBy({ left: el.clientWidth * 0.7, behavior: "smooth" });
    }
  };
  const prev = () => ref.current?.scrollBy({ left: -ref.current.clientWidth * 0.7, behavior: "smooth" });

  return (
    <nav className="uk-catnav">
      <div className="uk-container uk-catnav-wrap">
        {overflow && !atStart && (
          <button type="button" className="uk-catnav-arrow" onClick={prev} aria-label="Categorías anteriores">‹</button>
        )}
        <div className="uk-catnav-scroll" ref={ref} onScroll={update}>
          <Link href="/buscar" className={active === "Todos" ? "active" : ""}>Todos</Link>
          {CATS.filter((c) => c.q).map((c) => (
            <Link key={c.label} href={`/buscar?q=${c.q}`} className={active === c.label ? "active" : ""}>
              {c.label}
            </Link>
          ))}
        </div>
        {overflow && (
          <button type="button" className="uk-catnav-arrow" onClick={next}
            aria-label={atEnd ? "Volver al inicio" : "Más categorías"}>›</button>
        )}
      </div>
    </nav>
  );
}
