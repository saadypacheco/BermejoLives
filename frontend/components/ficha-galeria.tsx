"use client";

import { useState } from "react";
import type { GaleriaFoto, GaleriaVideo } from "@/lib/data";

/**
 * La galería de arriba de la ficha: UNA foto grande y abajo, a la vista, todas
 * las demás.
 *
 * La primera foto es el frente del local —lo que permite reconocerlo al
 * pasar— y las demás son la mercadería: no valen lo mismo, y por eso una
 * grande y el resto chicas. Pero el resto tiene que VERSE. Antes se mostraban
 * tres al costado y las otras quedaban detrás de un «Ver todas (6)» que abría
 * una ventana: para mirar lo que vende un local hacían falta dos clics y
 * cerrar un modal. En una ficha, la mercadería es el contenido — no un anexo.
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
  const [video, setVideo] = useState<string | null>(null);

  if (todas.length === 0 && videos.length === 0) return null;
  const actual = todas[Math.min(i, todas.length - 1)];

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

      {/* TODAS, abajo y a la vista. Tocar una la pone arriba; nada se abre ni
          se cierra. Con muchas fotos la tira se desplaza al costado, que es el
          gesto natural en un celular. */}
      {(todas.length > 1 || videos.length > 0) && (
        <div className="uk-fgal-tira">
          {todas.map((f, n) => (
            <button type="button" key={f.id} className={n === i ? "on" : ""}
                    onClick={() => setI(n)} aria-label={`Ver la foto ${n + 1}`}
                    aria-current={n === i}>
              <img src={f.thumb_url} alt="" loading="lazy" decoding="async" />
            </button>
          ))}
          {videos.map((v) => (
            <button type="button" key={v.id} className="con-video" onClick={() => setVideo(v.url)}
                    aria-label="Ver el video">
              <video src={v.url} preload="metadata" muted playsInline />
              <span aria-hidden>▶</span>
            </button>
          ))}
        </div>
      )}

      {video && (
        <div className="gf-lightbox" onClick={() => setVideo(null)} role="dialog" aria-modal>
          <video src={video} controls autoPlay playsInline onClick={(e) => e.stopPropagation()} />
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
