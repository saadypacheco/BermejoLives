"use client";

import Link from "next/link";
import { sinEmoji } from "@/lib/rubros";
import { useRef, useState, useEffect, useCallback } from "react";
import { useSearchParams } from "next/navigation";
import { getRubros } from "@/lib/data-client";
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
export function CatNav({ active, rubrosIniciales }: {
  active?: string;
  /** Los rubros leídos en el servidor: así los enlaces están en el HTML y un
   *  rastreador sin JavaScript ve la barra entera, no sólo «Todos». */
  rubrosIniciales?: Rubro[];
}) {
  // El rubro de la URL MANDA sobre el que llega por prop. En /buscar la barra
  // es además el filtro: si no se marcara cuál está puesto, la persona ve
  // trescientos resultados de «Moda y ropa» con «Todos» resaltado arriba.
  // En el home no hay `?rubro`, así que ahí sigue mandando la prop.
  const sp = useSearchParams();
  const activo = sp?.get("rubro") || active;
  const soloComerciales = (rs: Rubro[]) => rs.filter((r) => r.comercial !== false);
  const [rubros, setRubros] = useState<Rubro[]>(rubrosIniciales ? soloComerciales(rubrosIniciales) : []);
  // Sólo los rubros comerciales: baños, cajeros, estacionamientos y wifi
  // son servicios y tienen su fila propia en el home. En una barra de
  // "qué querés comprar", "Wifi gratis" es ruido.
  useEffect(() => {
    if (rubrosIniciales?.length) return;
    getRubros().then((rs) => setRubros(soloComerciales(rs))).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
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

  return (
    <nav className="uk-catnav">
      <div className="uk-container uk-catnav-wrap">
        {overflow && !atStart && (
          <button type="button" className="uk-catnav-arrow" onClick={prev} aria-label="Categorías anteriores">‹</button>
        )}
        <div className="uk-catnav-scroll" ref={ref} onScroll={update}>
          <Link href="/buscar" className={!activo || activo === "Todos" ? "active" : ""}>Todos</Link>
          {rubros.map((r) => (
            <Link key={r.slug} href={`/buscar?rubro=${r.slug}`}
                  className={activo === r.slug ? "active" : ""}>
              {sinEmoji(r.nombre)}
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
