"use client";

// La página de un manual: la barra de arriba (sólo en pantalla), el manual y el
// pie que sale en cada hoja impresa.
//
// Es de cliente por dos cosas: el botón «Guardar como PDF» (`window.print()`)
// y las marcas del manual del agente, que se completan con `?nombre=&ciudad=&mail=`.
// El HTML del servidor ya trae el manual entero en su versión genérica (el
// `fallback` del Suspense es esa misma versión); al montarse, si hay
// parámetros, se completan sin que el texto salte.

import { Suspense, useEffect, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import "@/app/styles/manual.css";
import { Ic } from "@/components/ic";
import { ManualVista } from "@/components/manual/manual-vista";
import { MARCAS_POR_DEFECTO, type Bloque, type ValoresMarca } from "@/lib/manual-md";
import { TITULO_MANUAL, type TipoManual } from "@/lib/manuales";

/** Un parámetro de la URL, limpio: sin caracteres de control ni espacios de más
 *  y con un tope de largo. Se muestra siempre como texto (React lo escapa). */
function limpio(s: string | null, max: number): string {
  // eslint-disable-next-line no-control-regex
  return (s ?? "").replace(/[\u0000-\u001f\u007f]/g, " ").replace(/\s+/g, " ").trim().slice(0, max);
}

/** `extra`: lo que va después del texto y que el Markdown no sabe dibujar (el
 *  QR del contacto en «Qué es URUKU»). Lo arma el servidor. */
export function ManualPagina({ tipo, bloques, extra }: { tipo: TipoManual; bloques: Bloque[]; extra?: ReactNode }) {
  return (
    <Suspense fallback={<Pagina tipo={tipo} bloques={bloques} v={MARCAS_POR_DEFECTO} extra={extra} />}>
      {tipo === "agente"
        ? <ConParametros tipo={tipo} bloques={bloques} />
        : <Pagina tipo={tipo} bloques={bloques} v={MARCAS_POR_DEFECTO} extra={extra} />}
    </Suspense>
  );
}

function ConParametros({ tipo, bloques }: { tipo: TipoManual; bloques: Bloque[] }) {
  const sp = useSearchParams();
  const v: ValoresMarca = {
    NOMBRE: limpio(sp.get("nombre"), 60),
    CIUDAD: limpio(sp.get("ciudad"), 60) || MARCAS_POR_DEFECTO.CIUDAD,
    MAIL: limpio(sp.get("mail"), 100) || MARCAS_POR_DEFECTO.MAIL,
  };
  return <Pagina tipo={tipo} bloques={bloques} v={v} />;
}

function Pagina({ tipo, bloques, v, extra }: { tipo: TipoManual; bloques: Bloque[]; v: ValoresMarca; extra?: ReactNode }) {
  const titulo = TITULO_MANUAL[tipo];

  // El navegador propone el título de la pestaña como nombre del PDF:
  // «URUKU · Manual del agente · Carlos.pdf» en vez de «Manual del agente».
  useEffect(() => {
    const antes = document.title;
    document.title = `URUKU · ${titulo}${v.NOMBRE ? ` · ${v.NOMBRE}` : ""}`;
    return () => { document.title = antes; };
  }, [titulo, v.NOMBRE]);

  return (
    <div className="mn-root" data-tipo={tipo}>
      <div className="mn-barra">
        <button type="button" className="mn-pdf" onClick={() => window.print()}>
          <Ic n="imprimir" s={22} /> Guardar como PDF
        </button>
        <p className="mn-ayuda">
          En la ventana que se abre, elegí «Guardar como PDF» como impresora.
          <span> Si aparecen la fecha o la dirección en los bordes de la hoja, destildá «Encabezados y pies de página».</span>
        </p>
      </div>

      <ManualVista bloques={bloques} v={v} etiqueta={titulo} />
      {extra}
    </div>
  );
}
