"use client";

import { useEffect, useRef, useState } from "react";
import { comprimirImagen } from "@/lib/imagen";
import { duracionVideo } from "@/lib/upload";
import { encolarMedia, listarMedia, sincronizarMedia, type MediaPendiente } from "@/lib/offline-media";

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

// ¿La subida falló por FALTA DE SEÑAL (para diferirla) y no por otra cosa?
function esErrorRed(ex: unknown): boolean {
  if (typeof navigator !== "undefined" && !navigator.onLine) return true;
  return ex instanceof TypeError || /fetch|network|failed|load|timeout|conexi/i.test(String(ex));
}

/** `comercioId` opcional: si viene, las subidas que fallen por señal se guardan
 * en el celu (cola offline) y se suben solas cuando vuelve la señal. Es la 2ª
 * pasada del agente (video + fotos extra sobre un local ya cargado). */
export function GaleriaUploader({ api, comercioId }: { api: GaleriaApi; comercioId?: string }) {
  const [fotos, setFotos] = useState<FotoG[]>([]);
  const [videos, setVideos] = useState<VideoG[]>([]);
  const [pendientes, setPendientes] = useState<MediaPendiente[]>([]);
  const [prog, setProg] = useState<number | null>(null);
  const [tipo, setTipo] = useState<"foto" | "video">("foto");
  const [sincronizando, setSincronizando] = useState(false);
  const [err, setErr] = useState("");
  const fotoInput = useRef<HTMLInputElement>(null);
  const videoInput = useRef<HTMLInputElement>(null);

  const offlineOn = !!comercioId;
  const pendFotos = pendientes.filter((p) => p.kind === "foto");
  const pendVideos = pendientes.filter((p) => p.kind === "video");

  async function refrescarPend() {
    if (!comercioId) return;
    setPendientes(await listarMedia(comercioId).catch(() => []));
  }

  async function sincronizar() {
    if (!comercioId || sincronizando) return;
    setSincronizando(true);
    try {
      const r = await sincronizarMedia(comercioId);
      if (r.subidas > 0) {
        // lo que subió ya está en el server: recargamos las listas reales
        api.cargarFotos().then(setFotos).catch(() => {});
        api.cargarVideos().then(setVideos).catch(() => {});
      }
    } finally {
      await refrescarPend();
      setSincronizando(false);
    }
  }

  useEffect(() => {
    api.cargarFotos().then(setFotos).catch(() => {});
    api.cargarVideos().then(setVideos).catch(() => {});
    if (offlineOn) {
      refrescarPend();
      sincronizar();                       // intento subir lo pendiente al abrir
      const onOnline = () => sincronizar(); // y cuando vuelve la señal
      window.addEventListener("online", onOnline);
      return () => window.removeEventListener("online", onOnline);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function onFoto(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []); e.target.value = "";
    if (!files.length) return;
    setErr("");
    setTipo("foto");
    // Sube de a una e INDEPENDIENTE: si una falla, sigue con el resto. Sin señal
    // (y con comercioId) se difiere a la cola offline; el local ya existe.
    const espacio = MAX_FOTOS - fotos.length - pendFotos.length;
    let fallas = 0, diferidas = 0;
    for (const file of files.slice(0, Math.max(0, espacio))) {
      let comp: File = file;
      try { comp = await comprimirImagen(file); } catch { /* subo el original */ }
      try {
        setProg(0);
        const foto = await api.subirFoto(comp, setProg);
        setFotos((f) => [...f, foto]);
      } catch (ex) {
        if (offlineOn && esErrorRed(ex)) { await encolarMedia(comercioId!, "foto", comp); diferidas += 1; }
        else fallas += 1;
      }
    }
    setProg(null);
    await refrescarPend();
    if (diferidas) setErr(`${diferidas} foto(s) guardadas sin señal 📴 — se suben solas cuando haya internet.`);
    else if (fallas) setErr(`${fallas} foto(s) no subieron. Probá de nuevo con esas.`);
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
    } catch (ex) {
      if (offlineOn && esErrorRed(ex)) {
        await encolarMedia(comercioId!, "video", file, dur || null);
        await refrescarPend();
        setErr("Video guardado sin señal 📴 — se sube solo cuando haya internet.");
      } else setErr(ex instanceof Error ? ex.message : "No se pudo subir");
    } finally { setProg(null); }
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
  const totalFotos = fotos.length + pendFotos.length;
  const totalVideos = videos.length + pendVideos.length;
  return (
    <div className="galup">
      {offlineOn && pendientes.length > 0 && (
        <div className="galup-pend">
          <span>📴 {pendientes.length} sin subir (sin señal)</span>
          <button type="button" onClick={sincronizar} disabled={sincronizando}>
            {sincronizando ? "Subiendo…" : "Sincronizar"}
          </button>
        </div>
      )}

      <div className="galup-head"><b>Fotos del local</b><span>{totalFotos}/{MAX_FOTOS}</span></div>
      <div className="galup-grid">
        {fotos.map((f) => (
          <div key={f.id} className="galup-item">
            <img src={f.thumb_url || f.url} alt="" loading="lazy" />
            <button type="button" className="galup-del" onClick={() => delFoto(f.id)} aria-label="Borrar">✕</button>
          </div>
        ))}
        {pendFotos.map((p) => (
          <div key={p.id} className="galup-item galup-penditem" title="Se sube cuando haya señal">
            <img src={URL.createObjectURL(p.blob)} alt="" />
            <span className="galup-clock">📴</span>
          </div>
        ))}
        {totalFotos < MAX_FOTOS && (
          <button type="button" className="galup-add" onClick={() => fotoInput.current?.click()} disabled={subiendo}>+ Foto</button>
        )}
      </div>

      <div className="galup-head" style={{ marginTop: 16 }}><b>Videos</b><span>{totalVideos}/{MAX_VIDEOS} · ≤60s</span></div>
      <div className="galup-grid">
        {videos.map((v) => (
          <div key={v.id} className="galup-item galup-vid">
            <video src={v.url} muted playsInline preload="metadata" />
            <span className="galup-dur">{v.duracion_seg ? `${v.duracion_seg}s` : "▶"}</span>
            <button type="button" className="galup-del" onClick={() => delVideo(v.id)} aria-label="Borrar">✕</button>
          </div>
        ))}
        {pendVideos.map((p) => (
          <div key={p.id} className="galup-item galup-vid galup-penditem" title="Se sube cuando haya señal">
            <span className="galup-clock">📴</span>
            <span className="galup-dur">{p.dur ? `${p.dur}s` : "▶"}</span>
          </div>
        ))}
        {totalVideos < MAX_VIDEOS && (
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

      <input ref={fotoInput} type="file" accept="image/*" capture="environment" multiple hidden onChange={onFoto} />
      <input ref={videoInput} type="file" accept="video/*" capture="environment" hidden onChange={onVideo} />
    </div>
  );
}
