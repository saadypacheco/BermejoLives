"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { HorarioBadge } from "@/components/horario-badge";
import { formatDistancia } from "@/lib/distancia";
import { ahoraEnBolivia } from "@/lib/horario";
import { prepararCarrusel, type ComercioCarrusel } from "@/lib/home-ciudad-pure";
import { permisoUbicacion, pedirUbicacion, ubicacionGuardada, type Ubicacion } from "@/lib/ubicacion";
import { conFiltros } from "@/lib/filtros-rapidos";
import { PistaCarrusel } from "./pista-carrusel";
import { useFiltrosRapidos } from "./use-filtros-rapidos";

/**
 * El carrusel de comercios del home de las ciudades (docs/home-ciudades.md §7). El servidor manda los
 * candidatos de la franja del día (con foto); acá se decide cuáles se ven, porque hace falta la hora, la
 * ubicación y los interruptores de la persona: con «Abiertos» sólo los abiertos, y el orden es el de
 * «Cerca de mí» (abiertos, plan estrella, distancia). Con «Más cerca» cada tarjeta dice a cuántos metros queda.
 *
 * El primer dibujo usa la hora del servidor (`ahoraIso`), así no hay diferencias con el HTML; después de
 * montar, sigue la hora real y se refresca cada minuto.
 */
export function CarruselComercios({ candidatos, titulo, subtitulo, verTodos, ciudad, ahoraIso }: {
  candidatos: ComercioCarrusel[];
  titulo: string;
  subtitulo: string;
  verTodos: string;
  ciudad: string;
  ahoraIso: string;
}) {
  const [filtros] = useFiltrosRapidos();
  const [ubicacion, setUbicacion] = useState<Ubicacion | null>(null);
  const [ahora, setAhora] = useState<Date>(() => ahoraEnBolivia(new Date(ahoraIso)));

  useEffect(() => {
    setAhora(ahoraEnBolivia());
    const t = window.setInterval(() => setAhora(ahoraEnBolivia()), 60_000);
    return () => window.clearInterval(t);
  }, []);

  // La ubicación se usa si ya se conocía (o el permiso ya estaba dado). Pedirla es cosa del interruptor.
  useEffect(() => {
    const guardada = ubicacionGuardada();
    if (guardada) { setUbicacion(guardada); return; }
    if (!filtros.cerca) return;
    permisoUbicacion().then((p) => { if (p === "granted") pedirUbicacion().then(setUbicacion).catch(() => {}); });
  }, [filtros.cerca]);

  const tarjetas = useMemo(
    () => prepararCarrusel(candidatos, { abiertos: filtros.abiertos, cerca: filtros.cerca, ubicacion, ahora }),
    [candidatos, filtros.abiertos, filtros.cerca, ubicacion, ahora],
  );

  if (candidatos.length === 0) return null;
  return (
    <section className="uk-container uk-home-sec uk-hc-sec" aria-labelledby="home-comercios">
      <div className="uk-section-head">
        <h2 id="home-comercios">{titulo} <small>{subtitulo}</small></h2>
        <Link href={conFiltros(verTodos, filtros)}>Ver todos →</Link>
      </div>
      {tarjetas.length === 0 ? (
        // Con «Abiertos» prendido y nadie abierto: se dice, no se deja un hueco.
        <p className="uk-hc-vacio" role="status">Ahora no hay locales abiertos en esta lista. Apagá «Abiertos» para verlos todos.</p>
      ) : (
        <PistaCarrusel etiqueta={titulo}>
          {tarjetas.map((c) => (
            <div role="listitem" key={c.id} className="uk-hc-item">
              <Link href={`/comercios/${encodeURIComponent(c.slug)}`} className="uk-hc-com">
                <span className="uk-hc-com-foto">
                  <img src={c.foto} alt="" loading="lazy" decoding="async"
                       style={c.fotoPos != null ? { objectPosition: `center ${c.fotoPos}%` } : undefined} />
                  <HorarioBadge horario={c.horario} estimado={c.horarioEstimado} />
                </span>
                <span className="uk-hc-com-txt">
                  <b>{c.nombre}</b>
                  <small>
                    {c.rubroNombre ? `${c.rubroNombre} · ` : ""}
                    {c.metros != null ? <em className="uk-hc-dist">{formatDistancia(c.metros)}</em> : ciudad}
                  </small>
                </span>
              </Link>
            </div>
          ))}
        </PistaCarrusel>
      )}
    </section>
  );
}
