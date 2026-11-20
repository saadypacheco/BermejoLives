"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Ic, IcRubro } from "@/components/ic";
import { conFiltros } from "@/lib/filtros-rapidos";
import type { IdIntencion, Intencion } from "@/lib/home-ciudad-pure";
import { useFiltrosRapidos } from "./use-filtros-rapidos";
import { useHoja } from "./use-hoja";

/**
 * La fila de botones de intención del home de las ciudades (docs/home-ciudades.md §4): Comer, Negocios,
 * Productos, Servicios, Farmacias, Bancos y cajeros, Dormir. Cada uno abre un panel que sube desde abajo con
 * sus opciones; cada opción lleva al mapa del rubro. El orden y el cartel verde de adentro los decide el
 * servidor según la hora de Bolivia (`intencionesDeCiudad`): acá no se saca nada, sólo se muestra.
 *
 * Los botones miden lo mismo que los accesos de siempre (`.uk-home-chips a`): el cartel va ADENTRO, a la
 * derecha del nombre, y no agranda el botón.
 */
export function IntencionesCiudad({ intenciones }: { intenciones: Intencion[] }) {
  const [abierta, setAbierta] = useState<IdIntencion | null>(null);
  const { cerrar } = useHoja(abierta !== null, () => setAbierta(null));
  const router = useRouter();
  const [filtros] = useFiltrosRapidos();
  const botonCerrar = useRef<HTMLButtonElement>(null);
  const disparador = useRef<HTMLElement | null>(null);
  const actual = intenciones.find((i) => i.id === abierta) ?? null;

  // El foco entra al panel al abrirse y vuelve al botón que lo abrió al cerrarse.
  useEffect(() => {
    if (actual) botonCerrar.current?.focus();
    else disparador.current?.focus();
  }, [actual]);

  if (intenciones.length === 0) return null;

  const ir = (href: string) => cerrar(() => router.push(conFiltros(href, filtros)));
  const alClic = (href: string) => (e: React.MouseEvent<HTMLAnchorElement>) => {
    // Con Ctrl, Cmd o botón del medio el navegador abre otra pestaña: se lo deja.
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.button !== 0) return;
    e.preventDefault();
    ir(href);
  };

  return (
    <>
      <nav className="uk-container uk-home-chips uk-intenciones" aria-label="Qué necesitás">
        {intenciones.map((i) => (
          <button key={i.id} type="button" className={i.cartel ? "ahora" : undefined} aria-haspopup="dialog"
                  onClick={(e) => { disparador.current = e.currentTarget; setAbierta(i.id); }}>
            <Ic n={i.icono} s={18} />{i.titulo}
            {i.cartel && <span className="uk-int-cartel">{i.cartel}</span>}
          </button>
        ))}
      </nav>

      {actual && (
        <>
          <div className="uk-hoja-velo" onClick={() => cerrar()} aria-hidden="true" />
          <div className="uk-hoja uk-hoja-intencion" role="dialog" aria-modal="true" aria-label={actual.titulo}>
            <button type="button" className="uk-hoja-tirador" aria-label="Cerrar" onClick={() => cerrar()} />
            <div className="uk-hoja-cab">
              <div><b>{actual.tipo === "productos" ? "Buscá por producto" : actual.titulo}</b><span>{actual.subtitulo}</span></div>
              <button type="button" ref={botonCerrar} className="uk-hoja-cerrar" onClick={() => cerrar()}>
                <Ic n="cerrar" s={15} /> Cerrar
              </button>
            </div>
            <div className="uk-hoja-cuerpo">
              {actual.tipo === "productos" ? (
                <div className="uk-hoja-chips">
                  {actual.productos.map((p) => {
                    const href = `/buscar?q=${encodeURIComponent(p)}`;
                    return <a key={p} href={conFiltros(href, filtros)} onClick={alClic(href)}>{p}</a>;
                  })}
                </div>
              ) : (
                actual.opciones.map((o) => (
                  <a key={o.href} href={conFiltros(o.href, filtros)} className="uk-hoja-op" onClick={alClic(o.href)}>
                    {o.rubro ? <IcRubro slug={o.rubro} s={24} tono="marca" /> : <Ic n={o.i} s={24} tono="marca" />}
                    <span><b>{o.t}</b>{o.d && <small>{o.d}</small>}</span>
                    <i>{o.href.startsWith("/buscar") ? "Ver en el mapa" : "Ver"} ›</i>
                  </a>
                ))
              )}
            </div>
          </div>
        </>
      )}
    </>
  );
}
