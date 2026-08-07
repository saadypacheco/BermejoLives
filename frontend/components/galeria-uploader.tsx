"use client";

import { useEffect, useRef, useState } from "react";
import { comprimirImagen } from "@/lib/imagen";
import { duracionVideo } from "@/lib/upload";

export type FotoG = { id: string; url: string; thumb_url: string | null };
export type VideoG = { id: string; url: string; duracion_seg: number | null };

/** El padre inyecta las operaciones (agente vs dueño usan endpoints distintos). */
export type GaleriaApi = {
  cargarFotos: () => Promise<FotoG[]>;
  subirFoto: (file: File, onP: (p: number) => void) => Promise<FotoG>;
  borrarFoto: (id: string) => Promise<void>;
  cargarVideos: () => Promise<VideoG[]>;
  subirVideo: (file: File, dur: number | null, onP: (p: number) => void) => Promise<VideoG>;
  borrarVideo: (id: string) => Promise<void>;
};

const MAX_FOTOS = 10, MAX_VIDEOS = 5, MAX_VIDEO_SEG = 60, MAX_VIDEO_MB = 50;

export function GaleriaUploader({ api }: { api: GaleriaApi }) {
  const [fotos, setFotos] = useState<FotoG[]>([]);
  const [videos, setVideos] = useState<VideoG[]>([]);
  const [prog, setProg] = useState<number | null>(null);
  const [tipo, setTipo] = useState<"foto" | "video">("foto");
  const [err, setErr] = useState("");
  const fotoInput = useRef<HTMLInputElement>(null);
  const videoInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    api.cargarFotos().then(setFotos).catch(() => {});
    api.cargarVideos().then(setVideos).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onFoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = "";
    if (!file) return;
    setErr("");
    try {
      const comp = await comprimirImagen(file);
      setTipo("foto"); setProg(0);
      const foto = await api.subirFoto(comp, setProg);
      setFotos((f) => [...f, foto]);
    } catch (ex) { setErr(ex instanceof Error ? ex.message : "No se pudo subir"); }
    finally { setProg(null); }
  }

  async function onVideo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = "";
    if (!file) return;
    setErr("");
    if (file.size > MAX_VIDEO_MB * 1024 * 1024) { setErr(`El video supera los ${MAX_VIDEO_MB} MB`); return; }
    const dur = await duracionVideo(file);
    if (dur > MAX_VIDEO_SEG) { setErr(`El video dura ${dur}s — máximo ${MAX_VIDEO_SEG}s`); return; }
    try {
      setTipo("video"); setProg(0);
      const video = await api.subirVideo(file, dur || null, setProg);
      setVideos((v) => [...v, video]);
    } catch (ex) { setErr(ex instanceof Error ? ex.message : "No se pudo subir"); }
    finally { setProg(null); }
  }

  async function delFoto(id: string) {
    if (!window.confirm("¿Borrar esta foto?")) return;
    await api.borrarFoto(id).catch(() => {});
    setFotos((f) => f.filter((x) => x.id !== id));
  }
  async function delVideo(id: string) {
    if (!window.confirm("¿Borrar este video?")) return;
    await api.borrarVideo(id).catch(() => {});
    setVideos((v) => v.filter((x) => x.id !== id));
  }

  const subiendo = prog !== null;
  return (
    <div className="galup">
      <div className="galup-head"><b>Fotos del local</b><span>{fotos.length}/{MAX_FOTOS}</span></div>
      <div className="galup-grid">
        {fotos.map((f) => (
          <div key={f.id} className="galup-item">
            <img src={f.thumb_url || f.url} alt="" loading="lazy" />
            <button type="button" className="galup-del" onClick={() => delFoto(f.id)} aria-label="Borrar">✕</button>
          </div>
        ))}
        {fotos.length < MAX_FOTOS && (
          <button type="button" className="galup-add" onClick={() => fotoInput.current?.click()} disabled={subiendo}>+ Foto</button>
        )}
      </div>

      <div className="galup-head" style={{ marginTop: 16 }}><b>Videos</b><span>{videos.length}/{MAX_VIDEOS} · ≤60s</span></div>
      <div className="galup-grid">
        {videos.map((v) => (
          <div key={v.id} className="galup-item galup-vid">
            <video src={v.url} muted playsInline preload="metadata" />
            <span className="galup-dur">{v.duracion_seg ? `${v.duracion_seg}s` : "▶"}</span>
            <button type="button" className="galup-del" onClick={() => delVideo(v.id)} aria-label="Borrar">✕</button>
          </div>
        ))}
        {videos.length < MAX_VIDEOS && (
          <button type="button" className="galup-add" onClick={() => videoInput.current?.click()} disabled={subiendo}>+ Video</button>
        )}
      </div>

      {subiendo && (
        <div className="galup-prog">
          <div className="galup-bar" style={{ width: `${prog}%` }} />
          <span>Subiendo {tipo}… {prog}%</span>
        </div>
      )}
      {err && <div className="galup-err">{err}</div>}

      <input ref={fotoInput} type="file" accept="image/*" capture="environment" hidden onChange={onFoto} />
      <input ref={videoInput} type="file" accept="video/*" capture="environment" hidden onChange={onVideo} />
    </div>
  );
}
