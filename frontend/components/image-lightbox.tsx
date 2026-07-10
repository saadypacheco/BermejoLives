"use client";

import { useEffect } from "react";

/** Overlay de imagen a pantalla completa. Cerrar con X, click afuera o Escape. */
export function ImageLightbox({ src, alt, onClose }: { src: string; alt?: string; onClose: () => void }) {
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="lightbox-backdrop" onClick={onClose}>
      <button className="lightbox-close" onClick={onClose} aria-label="Cerrar">✕</button>
      <img className="lightbox-img" src={src} alt={alt ?? ""} onClick={(e) => e.stopPropagation()} />
    </div>
  );
}
