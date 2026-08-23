"use client";

import Link from "next/link";
import { useRef, useState, useEffect, useCallback } from "react";
import { getRubros } from "@/lib/data";
import type { Rubro } from "@/lib/types";

/** Nav de categorías tipo carrusel: scroll horizontal + flechas. La flecha derecha
 * avanza y, si ya estás al final, vuelve al principio (loop). La izquierda aparece
 * cuando ya scrolleaste.
 *
 * Las categorías salen de la BASE, no de una lista escrita a mano.
 *
 * Antes eran fijas y no filtraban por categoría: cada una disparaba una BÚSQUEDA
 * DE TEXTO (`?q=mascota`). "Mascotas", "Tablets", "Mercados" y "Salud" no existen
 * como rubro ni aparecen en ningún producto, así que devolvían cero y parecía que
 * el buscador estaba roto. Lo que estaba roto era la promesa: la barra decía
 * "categoría" y hacía otra cosa.
 *
 * Ahora enlaza a `?rubro=<slug>`, que es el filtro real — el diagnóstico confirmó
 * que los 36 rubros devuelven exactamente los comercios que tienen. Y al venir de
 * la base, una categoría nueva aparece sola, sin tocar código. */
export function CatNav({ active }: { active?: string }) {
  const [rubros, setRubros] = useState<Rubro[]>([]);
  useEffect(() => { getRubros().then(setRubros).catch(() => {}); }, []);
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
    // `rubros` en las dependencias: el carrusel mide el ancho al montar, y ahora
    // las categorías llegan de la base DESPUÉS. Sin volver a medir, las flechas
    // de scroll no aparecerían nunca aunque la lista desborde.
  }, [update, rubros]);

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

  // Los nombres de los rubros traen el emoji adelante ("👟 Calzado"). En esta
  // barra ya hay poco espacio y el emoji no agrega nada: se muestra el texto.
  function etiqueta(nombre: string): string {
    return nombre.replace(/^[^\p{L}\p{N}]+/u, "").trim() || nombre;
  }

  return (
    <nav className="uk-catnav">
      <div className="uk-container uk-catnav-wrap">
        {overflow && !atStart && (
          <button type="button" className="uk-catnav-arrow" onClick={prev} aria-label="Categorías anteriores">‹</button>
        )}
        <div className="uk-catnav-scroll" ref={ref} onScroll={update}>
          <Link href="/buscar" className={active === "Todos" ? "active" : ""}>Todos</Link>
          {rubros.map((r) => (
            <Link key={r.slug} href={`/buscar?rubro=${r.slug}`}
                  className={active === r.slug ? "active" : ""}>
              {etiqueta(r.nombre)}
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
