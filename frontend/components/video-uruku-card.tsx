"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { duracionCorta, VIDEO_NETWORK_LABEL, type PublicVideo, type VideoNetwork } from "@/lib/videos-pure";

const REDES: readonly VideoNetwork[] = ["tiktok", "instagram", "facebook", "youtube"];

/**
 * Una portada de la franja «Videos de URUKU» (§15.2). La portada y el título llegan
 * ya armados desde el servidor (`src`, `poster`); lo único que hace este componente
 * de cliente es abrir el reproductor al tocar. El video NO se baja hasta entonces
 * (`preload="none"`).
 */
export function VideoUrukuCard({ video, cover, src }: { video: PublicVideo; cover: string; src: string }) {
  const [abierto, setAbierto] = useState(false);
  const disparador = useRef<HTMLButtonElement>(null);
  const dur = duracionCorta(video.duration_s);

  const cerrar = useCallback(() => {
    setAbierto(false);
    disparador.current?.focus();
  }, []);

  return (
    <div className="uk-vc">
      <button ref={disparador} type="button" className="uk-vc-btn" onClick={() => setAbierto(true)}
              aria-label={`Ver el video: ${video.title}`} aria-haspopup="dialog">
        <img src={cover} alt="" loading="lazy" decoding="async" className="uk-vc-img" />
        <span className="uk-vc-play" aria-hidden><Ic n="video_play" s={44} peso="fill" /></span>
        {dur && <span className="uk-vc-dur">{dur}</span>}
      </button>
      <span className="uk-vc-t">{video.title}</span>
      {abierto && <ReproductorVideo video={video} cover={cover} src={src} onClose={cerrar} />}
    </div>
  );
}

function ReproductorVideo({ video, cover, src, onClose }: { video: PublicVideo; cover: string; src: string; onClose: () => void }) {
  const cerrarRef = useRef<HTMLButtonElement>(null);
  const [fallo, setFallo] = useState(false);

  useEffect(() => {
    cerrarRef.current?.focus();
    const antes = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("keydown", onKey); document.body.style.overflow = antes; };
  }, [onClose]);

  const redes = REDES.filter((r) => video.network_links[r]);

  return (
    <div className="uk-vm-fondo" onClick={onClose}>
      <div className="uk-vm" role="dialog" aria-modal="true" aria-label={video.title} onClick={(e) => e.stopPropagation()}>
        <button ref={cerrarRef} type="button" className="uk-vm-cerrar" onClick={onClose} aria-label="Cerrar el video">
          <Ic n="cerrar" s={18} />
        </button>
        <video className="uk-vm-video" src={src} poster={cover} controls playsInline preload="none" autoPlay
               onError={() => setFallo(true)} />
        {fallo && (
          <p className="uk-vm-error" role="alert">
            <Ic n="aviso" s={16} /> No se pudo reproducir el video. Probá de nuevo en un rato o mirá el enlace de abajo.
          </p>
        )}
        <b className="uk-vm-titulo">{video.title}</b>
        <div className="uk-vm-acciones">
          {redes.map((r) => (
            <a key={r} className="uk-btn-ghost" href={video.network_links[r]} target="_blank" rel="noopener noreferrer">
              <Ic n={r} s={16} /> Ver en {VIDEO_NETWORK_LABEL[r]}
            </a>
          ))}
          {video.comercio && (
            <Link className="uk-btn-ghost" href={`/comercios/${video.comercio.slug}`} onClick={onClose}>
              <Ic n="comercios" s={16} /> Ver el comercio
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
