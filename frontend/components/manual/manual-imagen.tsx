"use client";

// Una captura dentro de un manual (`![texto](/manuales/capturas/…png)`).
//
// Si el archivo no está (la captura todavía no se sacó, o se borró) la figura
// se esconde entera en vez de mostrar el ícono de imagen rota: el servidor ya
// saca las que faltan al armar la página, esto cubre lo que falle después.
// El texto va de `alt` y de epígrafe: se lee igual en el PDF impreso.

import { useEffect, useRef, useState } from "react";

export function ManualImagen({ src, alt }: { src: string; alt: string }) {
  const ref = useRef<HTMLImageElement>(null);
  const [falta, setFalta] = useState(false);

  // La imagen pudo fallar antes de que React se enganchara (el HTML viene del
  // servidor): en ese caso `onError` ya no llega y se mira a mano.
  useEffect(() => {
    const img = ref.current;
    if (img && img.complete && img.naturalWidth === 0) setFalta(true);
  }, []);

  if (falta) return null;
  // Las de celular son angostas y altas: se muestran más chicas que las de computadora.
  const celular = /-mobile\.[a-z]+$/.test(src);
  return (
    <figure className={`mn-figura${celular ? " mn-figura-cel" : ""}`}>
      {/* Un archivo estático de public/: un <img> común alcanza. */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img ref={ref} src={src} alt={alt} loading="lazy" decoding="async" onError={() => setFalta(true)} />
      {alt && <figcaption>{alt}</figcaption>}
    </figure>
  );
}
