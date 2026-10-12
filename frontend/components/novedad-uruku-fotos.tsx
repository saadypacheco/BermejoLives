"use client";

// Las fotos de una novedad de URUKU como vidriera: la grilla de
// `galeria-tienda.tsx` (mismas clases `.uk-tienda-*`: 2 columnas en el celular,
// 3 en la tableta, 4 en la compu, miniatura en la grilla y la grande recién al
// abrir) con el mismo visor de pantalla completa, flechas y teclado. Sin
// filtros ni carga progresiva: una novedad trae 12 fotos como máximo.

import { useCallback, useEffect, useState } from "react";
import { Ic } from "@/components/ic";
import type { NovedadFoto } from "@/lib/data";

export function NovedadUrukuFotos({ fotos, titulo }: { fotos: NovedadFoto[]; titulo: string }) {
  const [abierta, setAbierta] = useState<number | null>(null);

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

  if (fotos.length === 0) return null;
  const foto = abierta !== null ? fotos[abierta] : null;

  return (
    <section className="uk-tienda" aria-labelledby="uk-nov-fotos">
      <div className="uk-section-head">
        <h2 id="uk-nov-fotos"><Ic n="foto" s={22} /> Fotos ({fotos.length})</h2>
      </div>
      <ul className="uk-tienda-grid">
        {fotos.map((f, n) => (
          <li key={f.url}>
            <button type="button" onClick={() => setAbierta(n)} aria-label={`Ver la foto ${n + 1} de ${fotos.length}`}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={f.thumb_url || f.url} alt={`${titulo}, foto ${n + 1}`} loading="lazy" decoding="async" />
            </button>
          </li>
        ))}
      </ul>

      {foto && abierta !== null && (
        <div className="gf-lightbox uk-tienda-visor" onClick={() => setAbierta(null)} role="dialog" aria-modal
             aria-label={`Foto ${abierta + 1} de ${fotos.length}`}>
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src={foto.url} alt={`${titulo}, foto ${abierta + 1}`} onClick={(e) => e.stopPropagation()} />
          {fotos.length > 1 && (
            <>
              <button type="button" className="uk-tienda-flecha izq" aria-label="Anterior"
                      onClick={(e) => { e.stopPropagation(); mover(-1); }}>
                <Ic n="volver" s={24} />
              </button>
              <button type="button" className="uk-tienda-flecha der" aria-label="Siguiente"
                      onClick={(e) => { e.stopPropagation(); mover(1); }}>
                <Ic n="seguir" s={24} />
              </button>
              <span className="uk-tienda-cuenta">{abierta + 1} / {fotos.length}</span>
            </>
          )}
          <button type="button" className="gf-close" aria-label="Cerrar"><Ic n="cerrar" s={18} /></button>
        </div>
      )}
    </section>
  );
}
