"use client";

import { useState } from "react";
import type { GaleriaFoto, GaleriaVideo } from "@/lib/data";

/**
 * La galería de arriba de la ficha: una foto grande, tres miniaturas al lado y
 * el resto detrás de un botón.
 *
 * POR QUÉ ASÍ Y NO UNA GRILLA
 * ===========================
 * La grilla anterior mostraba las doce fotos del mismo tamaño, todas iguales de
 * importantes. En un local de Bermejo la primera foto es el frente —lo que
 * permite reconocerlo al pasar— y las demás son la mercadería. No valen lo
 * mismo, y una grilla dice que sí.
 *
 * Las miniaturas cargan `thumb_url`; la grande, la grande. Es la única foto de
 * la página que justifica los 1280px.
 */
export function FichaGaleria({ portada, fotos, videos, nombre, posicion }: {
  portada: string | null;
  fotos: GaleriaFoto[];
  videos: GaleriaVideo[];
  nombre: string;
  /** El encuadre elegido en el panel, para que la grande recorte donde va. */
  posicion: number | null;
}) {
  // La portada primero: es la que eligió el agente parado en la vereda, y la
  // que el comprador ya vio en los resultados. Empezar por otra rompe la
  // continuidad entre la tarjeta y la ficha.
  const todas = [
    ...(portada ? [{ id: "portada", url: portada, thumb_url: portada }] : []),
    ...fotos.map((f) => ({ id: f.id, url: f.url, thumb_url: f.thumb_url || f.url })),
  ];
  const [i, setI] = useState(0);
  const [zoom, setZoom] = useState<string | null>(null);
  const [verTodas, setVerTodas] = useState(false);

  if (todas.length === 0 && videos.length === 0) return null;
  const actual = todas[Math.min(i, todas.length - 1)];
  const laterales = todas.filter((_, n) => n !== i).slice(0, 3);

  return (
    <div className="uk-fgal">
      <div className="uk-fgal-main">
        {actual && (
          <button type="button" onClick={() => setZoom(actual.url)} aria-label="Ampliar foto">
            <img src={actual.url} alt={nombre}
                 style={posicion != null ? { objectPosition: `center ${posicion}%` } : undefined} />
          </button>
        )}
        {todas.length > 1 && (
          <span className="uk-fgal-count">📷 {i + 1} / {todas.length}</span>
        )}
      </div>

      {(laterales.length > 0 || videos.length > 0) && (
        <div className="uk-fgal-side">
          {laterales.map((f) => (
            <button type="button" key={f.id} onClick={() => setI(todas.findIndex((x) => x.id === f.id))}
                    aria-label="Ver esta foto">
              <img src={f.thumb_url} alt="" loading="lazy" decoding="async" />
            </button>
          ))}
          {(todas.length > 4 || videos.length > 0) && (
            <button type="button" className="uk-fgal-todas" onClick={() => setVerTodas(true)}>
              🖼 Ver todas ({todas.length + videos.length})
            </button>
          )}
        </div>
      )}

      {verTodas && (
        <div className="gf-lightbox" onClick={() => setVerTodas(false)} role="dialog" aria-modal>
          <div className="uk-fgal-todas-grid" onClick={(e) => e.stopPropagation()}>
            {todas.map((f) => (
              <button type="button" key={f.id} onClick={() => { setZoom(f.url); setVerTodas(false); }}>
                <img src={f.thumb_url} alt="" loading="lazy" />
              </button>
            ))}
            {videos.map((v) => (
              <video key={v.id} src={v.url} controls preload="metadata" playsInline />
            ))}
          </div>
          <button type="button" className="gf-close" aria-label="Cerrar">✕</button>
        </div>
      )}

      {zoom && (
        <div className="gf-lightbox" onClick={() => setZoom(null)} role="dialog" aria-modal>
          <img src={zoom} alt="" />
          <button type="button" className="gf-close" aria-label="Cerrar">✕</button>
        </div>
      )}
    </div>
  );
}
