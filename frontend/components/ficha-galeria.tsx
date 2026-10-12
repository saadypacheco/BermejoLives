"use client";

import { useState } from "react";
import type { GaleriaFoto } from "@/lib/data";
import { Ic } from "@/components/ic";

/**
 * La foto de arriba de la ficha: el FRENTE del local, grande.
 *
 * Es la que permite reconocerlo al pasar, y la que el comprador ya vio en los
 * resultados. Todas las demás —la mercadería— van más abajo, en «Fotos del
 * local», como una tienda (components/galeria-tienda.tsx): antes iban acá en
 * una tira de miniaturas, y con 50 o 300 fotos por plan mirar lo que vende un
 * local era tocar cuadradito por cuadradito. Sin enlace «Ver las N fotos»:
 * la vidriera está justo debajo.
 *
 * Sin portada, arriba va la primera foto de la galería.
 */
export function FichaGaleria({ portada, fotos, nombre, posicion }: {
  portada: string | null;
  fotos: GaleriaFoto[];
  nombre: string;
  /** El encuadre elegido en el panel, para que la grande recorte donde va. */
  posicion: number | null;
}) {
  const [zoom, setZoom] = useState<string | null>(null);
  const principal = portada ?? fotos[0]?.url ?? null;
  if (!principal) return null;

  return (
    <div className="uk-fgal">
      <div className="uk-fgal-main">
        <button type="button" onClick={() => setZoom(principal)} aria-label="Ampliar foto">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={principal} alt={nombre}
               style={portada && posicion != null ? { objectPosition: `center ${posicion}%` } : undefined} />
        </button>
      </div>

      {zoom && (
        <div className="gf-lightbox" onClick={() => setZoom(null)} role="dialog" aria-modal>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={zoom} alt="" />
          <button type="button" className="gf-close" aria-label="Cerrar"><Ic n="cerrar" s={18} /></button>
        </div>
      )}
    </div>
  );
}
