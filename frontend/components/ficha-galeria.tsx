"use client";

import { useCallback, useState } from "react";
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
  const [prop, setProp] = useState(4 / 3);
  const medir = useCallback((img: HTMLImageElement) => {
    if (!img.naturalWidth || !img.naturalHeight) return;
    const r = Math.min(2, Math.max(1, img.naturalWidth / img.naturalHeight));
    setProp((p) => (Math.abs(p - r) < 0.01 ? p : r));
  }, []);
  const principal = portada ?? fotos[0]?.url ?? null;
  if (!principal) return null;

  return (
    <div className="uk-fgal">
      <div className="uk-fgal-main">
        <button type="button" onClick={() => setZoom(principal)} aria-label="Ampliar foto">
          {/* El recuadro toma la forma de la foto: una horizontal se ve entera y
              llena el cuadro, sin el fondo difuminado que se veía raro. Una
              vertical va en un cuadrado y se recorta arriba/abajo según el
              encuadre del panel (`posicion`). Topes: 1 (cuadrado) a 2 (apaisada). */}
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={principal} alt={nombre}
               ref={(img) => { if (img?.complete) medir(img); }}
               onLoad={(e) => medir(e.currentTarget)}
               style={{ aspectRatio: String(prop),
                        ...(portada && posicion != null ? { objectPosition: `center ${posicion}%` } : {}) }} />
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
