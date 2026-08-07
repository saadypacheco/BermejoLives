"use client";

import { useState } from "react";
import type { GaleriaFoto, GaleriaVideo } from "@/lib/data";

/** Galería pública en la ficha del comercio: fotos (thumb → lightbox) + videos. */
export function GaleriaFicha({ fotos, videos }: { fotos: GaleriaFoto[]; videos: GaleriaVideo[] }) {
  const [zoom, setZoom] = useState<string | null>(null);
  if (fotos.length === 0 && videos.length === 0) return null;

  return (
    <div style={{ marginTop: 34 }}>
      <div className="section-head"><div><h2 style={{ fontSize: 24 }}>Fotos y videos</h2></div></div>

      {fotos.length > 0 && (
        <div className="gf-grid">
          {fotos.map((f) => (
            <button type="button" key={f.id} className="gf-item" onClick={() => setZoom(f.url)} aria-label="Ampliar foto">
              <img src={f.thumb_url || f.url} alt="" loading="lazy" decoding="async" />
            </button>
          ))}
        </div>
      )}

      {videos.length > 0 && (
        <div className="gf-videos">
          {videos.map((v) => (
            <video key={v.id} className="gf-video" src={v.url} controls preload="metadata" playsInline />
          ))}
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
