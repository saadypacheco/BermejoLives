"use client";

// «Fotos del local» como una tienda: fotos grandes en columnas que siguen hacia
// abajo (2 en el celular, 3 en la tableta, 4 en la compu), no una tira de
// miniaturas. Con topes de 50 a 300 fotos por plan, la tira obligaba a tocar
// cuadradito por cuadradito para ver la mercadería; acá se recorre como una
// vidriera, con el dedo hacia abajo.
//
// Cada foto carga la miniatura (400 px) o la grande según el ancho que ocupa
// (`srcSet`), y recién cuando se acerca a la pantalla (`loading="lazy"`): 300
// fotos grandes de una vez tirarían cualquier celular. Se muestran de a 24, con
// «Ver más». Tocar una la abre grande, con flechas (y el teclado) para pasar.

import { useCallback, useEffect, useState } from "react";
import type { GaleriaFoto, GaleriaVideo } from "@/lib/data";
import { Ic } from "@/components/ic";

const DE_A = 24;

export function GaleriaTienda({ fotos, videos, nombre }: {
  fotos: GaleriaFoto[];
  videos: GaleriaVideo[];
  nombre: string;
}) {
  const [cuantas, setCuantas] = useState(DE_A);
  const [abierta, setAbierta] = useState<number | null>(null);
  const [video, setVideo] = useState<string | null>(null);

  const mover = useCallback((paso: number) => {
    setAbierta((n) => (n === null ? n : (n + paso + fotos.length) % fotos.length));
  }, [fotos.length]);

  useEffect(() => {
    if (abierta === null) return;
    const tecla = (e: KeyboardEvent) => {
      if (e.key === "Escape") setAbierta(null);
      else if (e.key === "ArrowRight") mover(1);
      else if (e.key === "ArrowLeft") mover(-1);
    };
    window.addEventListener("keydown", tecla);
    return () => window.removeEventListener("keydown", tecla);
  }, [abierta, mover]);

  if (fotos.length === 0 && videos.length === 0) return null;
  const visibles = fotos.slice(0, cuantas);
  const quedan = fotos.length - visibles.length;
  const foto = abierta !== null ? fotos[abierta] : null;

  return (
    <section id="fotos" className="uk-tienda" aria-labelledby="uk-tienda-tit">
      <div className="uk-section-head">
        <h2 id="uk-tienda-tit"><Ic n="foto" s={22} /> Fotos del local{fotos.length > 0 ? ` (${fotos.length})` : ""}</h2>
      </div>

      <ul className="uk-tienda-grid">
        {visibles.map((f, n) => (
          <li key={f.id}>
            <button type="button" onClick={() => setAbierta(n)} aria-label={`Ver la foto ${n + 1} de ${fotos.length}`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={f.thumb_url || f.url}
                srcSet={f.thumb_url && f.thumb_url !== f.url ? `${f.thumb_url} 400w, ${f.url} 1280w` : undefined}
                sizes="(max-width: 600px) 50vw, (max-width: 1000px) 33vw, 25vw"
                alt={`${nombre}, foto ${n + 1}`}
                loading="lazy" decoding="async"
              />
            </button>
          </li>
        ))}
        {/* Los videos al final de la grilla, con su ícono de play. */}
        {quedan === 0 && videos.map((v) => (
          <li key={v.id}>
            <button type="button" className="con-video" onClick={() => setVideo(v.url)} aria-label="Ver el video">
              <video src={v.url} preload="metadata" muted playsInline />
              <span><Ic n="video_play" s={40} /></span>
            </button>
          </li>
        ))}
      </ul>

      {quedan > 0 && (
        <button type="button" className="uk-btn-ghost uk-tienda-mas" onClick={() => setCuantas((c) => c + DE_A)}>
          Ver más fotos ({quedan})
        </button>
      )}

      {foto && abierta !== null && (
        <div className="gf-lightbox" onClick={() => setAbierta(null)} role="dialog" aria-modal aria-label={`Foto ${abierta + 1} de ${fotos.length}`}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={foto.url} alt={`${nombre}, foto ${abierta + 1}`} onClick={(e) => e.stopPropagation()} />
          {fotos.length > 1 && (
            <>
              <button type="button" className="uk-tienda-flecha izq" aria-label="Foto anterior"
                      onClick={(e) => { e.stopPropagation(); mover(-1); }}>
                <Ic n="volver" s={24} />
              </button>
              <button type="button" className="uk-tienda-flecha der" aria-label="Foto siguiente"
                      onClick={(e) => { e.stopPropagation(); mover(1); }}>
                <Ic n="seguir" s={24} />
              </button>
              <span className="uk-tienda-cuenta">{abierta + 1} / {fotos.length}</span>
            </>
          )}
          <button type="button" className="gf-close" aria-label="Cerrar"><Ic n="cerrar" s={18} /></button>
        </div>
      )}

      {video && (
        <div className="gf-lightbox" onClick={() => setVideo(null)} role="dialog" aria-modal>
          <video src={video} controls autoPlay playsInline onClick={(e) => e.stopPropagation()} />
          <button type="button" className="gf-close" aria-label="Cerrar"><Ic n="cerrar" s={18} /></button>
        </div>
      )}
    </section>
  );
}
