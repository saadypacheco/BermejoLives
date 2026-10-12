"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { comprimirImagen } from "@/lib/imagen";
import { useObjectUrls } from "@/lib/object-url";
import { duracionVideo, datosTope, type ListaFotos, type OpcionesFoto, type RespuestaPortada, type TopeFotos } from "@/lib/upload";
import { encolarMedia, listarMedia, sincronizarMedia, quitarMedia, type MediaPendiente } from "@/lib/offline-media";
import { Ic } from "@/components/ic";
import { TopeFotosDialogo, type DecisionTope } from "@/components/tope-fotos-dialogo";

export type FotoG = { id: string; url: string; thumb_url: string | null };
export type VideoG = { id: string; url: string; duracion_seg: number | null };

/** El padre inyecta las operaciones (agente vs dueño usan endpoints distintos). */
/** La portada vigente del comercio (la foto principal, aparte de la galería). */
export type PortadaG = { url: string | null; thumb_url: string | null };

export type GaleriaApi = {
  /** Trae las fotos y, si el backend lo manda, el tope actual del plan (`limite`). */
  cargarFotos: () => Promise<ListaFotos<FotoG>>;
  /** `opts`: reintento tras el 409 del tope (`reemplazar=<id>` o `extra=pagar`). */
  subirFoto: (file: File, onP: (p: number) => void, opts?: OpcionesFoto) => Promise<FotoG>;
  /** Sin esta función no hay botón de borrar (el agente de campo no borra: lo hace URUKU). */
  borrarFoto?: (id: string) => Promise<void>;
  /** «Usar como portada»: intercambia la foto elegida con la portada actual y
   *  devuelve la portada nueva y la galería reacomodada. Sin ella no hay botón. */
  usarComoPortada?: (fotoId: string) => Promise<RespuestaPortada<FotoG>>;
  cargarVideos: () => Promise<VideoG[]>;
  subirVideo: (file: File, dur: number | null, onP: (p: number) => void) => Promise<VideoG>;
  borrarVideo: (id: string) => Promise<void>;
};

// El tope de fotos lo manda el backend (depende del plan). Este número sólo se
// usa hasta que llega, o si el backend todavía no lo manda.
const LIMITE_FOTOS_RESPALDO = 10;
const MAX_VIDEOS = 5, MAX_VIDEO_SEG = 60, MAX_VIDEO_MB = 50;

// ¿La subida falló por FALTA DE SEÑAL (para diferirla) y no por otra cosa?
function esErrorRed(ex: unknown): boolean {
  if (typeof navigator !== "undefined" && !navigator.onLine) return true;
  return ex instanceof TypeError || /fetch|network|failed|load|timeout|conexi/i.test(String(ex));
}

/** `comercioId` opcional: si viene, las subidas que fallen por señal se guardan
 * en el celu (cola offline) y se suben solas cuando vuelve la señal. Es la 2ª
 * pasada del agente (video + fotos extra sobre un local ya cargado). */
export function GaleriaUploader({ api, comercioId, puedePagarExtra = false, portada: portadaProp, onPortada, refrescar, onFotos, onFotosError, onLimite }: {
  api: GaleriaApi; comercioId?: string;
  /** La portada que ya tiene el comercio: va primero, con la etiqueta «Portada». */
  portada?: PortadaG | null;
  /** Avisa que la portada cambió (tras «Usar como portada»), para que quien la
   *  muestra en otro lado (la foto principal, la tarjeta) se ponga al día. */
  onPortada?: (p: PortadaG) => void;
  /** Un número que el padre sube cuando la galería cambió por fuera (p. ej. subió
   *  otra portada y la anterior pasó a la galería): se vuelve a pedir la lista. */
  refrescar?: number;
  /** Sólo la galería del COMERCIANTE: en el tope puede pagar una foto extra. El
   *  agente y el admin no comprometen plata del comercio: sólo borrar la más vieja. */
  puedePagarExtra?: boolean;
  /** Avisa el tope de fotos del plan cuando se conoce o cambia. */
  onLimite?: (n: number) => void;
  /** Avisa cuántas fotos YA SUBIDAS tiene la galería: al cargarla y cada vez que
   *  cambia. «Completar comercio» lo usa para el «Le falta: fotos del local». */
  onFotos?: (n: number) => void;
  /** Avisa que la lista de fotos no se pudo bajar: sin esto, quien espera el
   *  número se quedaría diciendo «mirando…» para siempre. */
  onFotosError?: () => void;
}) {
  const [fotos, setFotos] = useState<FotoG[]>([]);
  const [fotosListas, setFotosListas] = useState(false);
  const [videos, setVideos] = useState<VideoG[]>([]);
  const [pendientes, setPendientes] = useState<MediaPendiente[]>([]);
  const [prog, setProg] = useState<number | null>(null);
  const [tipo, setTipo] = useState<"foto" | "video">("foto");
  const [sincronizando, setSincronizando] = useState(false);
  const [err, setErr] = useState("");
  const [limite, setLimite] = useState(LIMITE_FOTOS_RESPALDO);
  const [portada, setPortada] = useState<PortadaG | null>(portadaProp ?? null);
  // Foto que se está pasando a portada (una a la vez).
  const [cambiando, setCambiando] = useState<string | null>(null);
  // Diálogo del tope abierto: `resolver` devuelve la decisión a quien esperaba.
  const [dlg, setDlg] = useState<{ tope: TopeFotos; resolver: (d: DecisionTope | null) => void } | null>(null);
  // Foto de la cola sin señal que chocó con el tope al sincronizar.
  const [topePend, setTopePend] = useState<{ id: string; tope: TopeFotos } | null>(null);
  const fotoInput = useRef<HTMLInputElement>(null);
  const videoInput = useRef<HTMLInputElement>(null);

  const offlineOn = !!comercioId;
  const puedeBorrar = !!api.borrarFoto;
  const portadaUrl = portadaProp?.url ?? null, portadaThumb = portadaProp?.thumb_url ?? null;
  // Si el padre la cambia por otro camino (subió una nueva), se refleja acá.
  useEffect(() => {
    if (portadaProp === undefined) return;
    setPortada(portadaUrl || portadaThumb ? { url: portadaUrl, thumb_url: portadaThumb } : null);
  }, [portadaProp === undefined, portadaUrl, portadaThumb]);  // eslint-disable-line react-hooks/exhaustive-deps
  const pendFotos = useMemo(() => pendientes.filter((p) => p.kind === "foto"), [pendientes]);
  // Una URL por pendiente, revocadas juntas. Estaba `URL.createObjectURL(p.blob)`
  // adentro del JSX: eso crea una URL NUEVA cada vez que React redibuja —y
  // redibuja en cada tick del progreso de subida— sin revocar ninguna. Cada una
  // deja la foto anclada en memoria hasta cerrar la pestaña.
  const pendFotoUrls = useObjectUrls(pendFotos, (p) => p.blob);
  const pendVideos = pendientes.filter((p) => p.kind === "video");

  async function refrescarPend() {
    if (!comercioId) return;
    setPendientes(await listarMedia(comercioId).catch(() => []));
  }

  function aplicarLimite(n: number | null | undefined) {
    if (typeof n === "number" && n > 0) { setLimite(n); onLimite?.(n); }
  }

  /** Vuelve a pedir las fotos (y el tope). Devuelve false si no pudo. */
  async function recargarFotos(): Promise<boolean> {
    try {
      const r = await api.cargarFotos();
      setFotos(r.items); aplicarLimite(r.limite);
      return true;
    } catch { return false; }
  }

  /** Abre el diálogo del tope y espera la decisión (`null` = cancelar). */
  function preguntarTope(tope: TopeFotos): Promise<DecisionTope | null> {
    aplicarLimite(tope.limite);
    return new Promise((res) => setDlg({ tope, resolver: (d) => { setDlg(null); res(d); } }));
  }

  const opcionesDe = (d: DecisionTope, tope: TopeFotos): OpcionesFoto =>
    d === "pagar" ? { extra: "pagar" } : { reemplazar: tope.mas_vieja?.id };

  async function sincronizar() {
    if (!comercioId || sincronizando) return;
    setSincronizando(true);
    try {
      const r = await sincronizarMedia(comercioId);
      if (r.subidas > 0) {
        // lo que subió ya está en el server: recargamos las listas reales
        recargarFotos();
        api.cargarVideos().then(setVideos).catch(() => {});
      }
      // Una foto chocó con el tope: sigue en la cola (no se pierde) y se avisa.
      if (r.tope) { setTopePend({ id: r.tope.id, tope: r.tope.datos }); aplicarLimite(r.tope.datos.limite); }
      else if (typeof navigator === "undefined" || navigator.onLine) setTopePend(null);
    } finally {
      await refrescarPend();
      setSincronizando(false);
    }
  }

  const refrescarInicial = useRef(refrescar);
  useEffect(() => {
    if (refrescar === refrescarInicial.current) return;
    void recargarFotos();
  }, [refrescar]);  // eslint-disable-line react-hooks/exhaustive-deps

  // Sólo después de que llegó la lista: antes, «0» sería mentira.
  useEffect(() => { if (fotosListas) onFotos?.(fotos.length); }, [fotos.length, fotosListas]);  // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    api.cargarFotos().then((r) => { setFotos(r.items); aplicarLimite(r.limite); setFotosListas(true); }).catch(() => onFotosError?.());
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
    // Ya no se recorta por un tope fijo: lo decide el backend, y al chocar con
    // él se le pregunta a la persona qué prefiere (borrar la más vieja o pagar).
    let fallas = 0, diferidas = 0, sinLugar = 0;
    for (let i = 0; i < files.length; i++) {
      const file = files[i];
      let comp: File = file;
      try { comp = await comprimirImagen(file); } catch { /* subo el original */ }
      let opts: OpcionesFoto | undefined;
      let cancelada = false;
      for (;;) {
        try {
          setProg(0);
          const foto = await api.subirFoto(comp, setProg, opts);
          setFotos((f) => [...f.filter((x) => x.id !== opts?.reemplazar), foto]);
          if (opts?.extra) setLimite((l) => l + 1);
          if (opts) recargarFotos();   // trae el tope y la lista reales
          break;
        } catch (ex) {
          const tope = datosTope(ex);
          if (tope) {
            setProg(null);
            const dec = await preguntarTope(tope);
            if (!dec) { cancelada = true; break; }
            opts = opcionesDe(dec, tope);
            continue;
          }
          if (offlineOn && esErrorRed(ex)) { await encolarMedia(comercioId!, "foto", comp); diferidas += 1; }
          else fallas += 1;
          break;
        }
      }
      if (cancelada) { sinLugar = files.length - i; break; }
    }
    setProg(null);
    await refrescarPend();
    if (sinLugar) setErr(`${sinLugar} foto(s) no se subieron: llegaste al tope de ${limite} fotos de tu plan.`);
    else if (diferidas) setErr(`${diferidas} foto(s) guardadas sin señal — se suben solas cuando haya internet.`);
    else if (fallas) setErr(`${fallas} foto(s) no subieron. Probá de nuevo con esas.`);
  }

  /** Una foto de la cola sin señal chocó con el tope: elegir y reintentarla. */
  async function resolverPendiente() {
    if (!topePend) return;
    const p = pendientes.find((x) => x.id === topePend.id);
    if (!p) { setTopePend(null); return; }
    const dec = await preguntarTope(topePend.tope);
    if (!dec) return;
    setErr(""); setTipo("foto");
    try {
      setProg(0);
      const file = new File([p.blob], p.name, { type: p.blob.type });
      await api.subirFoto(file, setProg, opcionesDe(dec, topePend.tope));
      await quitarMedia(p.id);          // recién cuando entró: antes seguía a salvo en la cola
      setTopePend(null);
      await recargarFotos();
      await refrescarPend();
      await sincronizar();              // las demás de la cola: puede pedir otra decisión
    } catch (ex) {
      const t = datosTope(ex);
      if (t) setTopePend({ id: p.id, tope: t });
      else setErr(ex instanceof Error ? ex.message : "No se pudo subir");
    } finally { setProg(null); await refrescarPend(); }
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
        setErr("Video guardado sin señal — se sube solo cuando haya internet.");
      } else setErr(ex instanceof Error ? ex.message : "No se pudo subir");
    } finally { setProg(null); }
  }

  async function delFoto(id: string) {
    if (!api.borrarFoto) return;
    if (!window.confirm("¿Borrar esta foto?")) return;
    await api.borrarFoto(id).catch(() => {});
    setFotos((f) => f.filter((x) => x.id !== id));
  }

  /** Intercambio: la elegida pasa a ser la portada y la portada anterior entra a
   *  la galería. Si falla, no se toca nada: la portada anterior sigue igual. */
  async function usarComoPortada(id: string) {
    if (!api.usarComoPortada || cambiando) return;
    setErr(""); setCambiando(id);
    try {
      const r = await api.usarComoPortada(id);
      const nueva: PortadaG = { url: r.portada_url, thumb_url: r.portada_thumb_url };
      setPortada(nueva); setFotos(r.fotos); aplicarLimite(r.limite);
      onPortada?.(nueva);
    } catch (ex) {
      const sinRed = (typeof navigator !== "undefined" && !navigator.onLine) || ex instanceof TypeError;
      setErr(sinRed
        ? "Sin conexión: no se pudo cambiar la portada. La anterior sigue igual."
        : "No se pudo cambiar la portada. Probá de nuevo: la anterior sigue igual.");
    } finally { setCambiando(null); }
  }
  async function delVideo(id: string) {
    if (!window.confirm("¿Borrar este video?")) return;
    await api.borrarVideo(id).catch(() => {});
    setVideos((v) => v.filter((x) => x.id !== id));
  }

  const subiendo = prog !== null;
  const totalFotos = fotos.length + pendFotos.length;
  const enElTope = totalFotos >= limite;
  const totalVideos = videos.length + pendVideos.length;
  return (
    <div className="galup">
      {offlineOn && pendientes.length > 0 && (
        <div className="galup-pend">
          <span><Ic n="aviso" s={14} /> {pendientes.length} sin subir (sin señal)</span>
          <button type="button" onClick={sincronizar} disabled={sincronizando}>
            {sincronizando ? "Subiendo…" : "Sincronizar"}
          </button>
        </div>
      )}

      {offlineOn && topePend && (
        <div className="galup-pend" role="alert">
          <span><Ic n="aviso" s={14} /> Hay fotos esperando lugar: llegaste al tope de fotos de tu plan.</span>
          <button type="button" onClick={resolverPendiente} disabled={subiendo} style={{ minHeight: 44, padding: "6px 16px" }}>
            Resolver
          </button>
        </div>
      )}

      <div className="galup-head"><b>Fotos del local</b><span title="Fotos que tenés / tope de tu plan">{totalFotos}/{limite}</span></div>
      {enElTope && (
        <div className="galup-tope" style={{ display: "flex", gap: 6, alignItems: "flex-start", margin: "0 0 8px", fontSize: 12.5, lineHeight: 1.4, color: "var(--txt-2)" }}>
          <span style={{ flex: "none", marginTop: 1 }}><Ic n="aviso" s={14} /></span>
          <span>
            Llegaste al tope de fotos de tu plan.{" "}
            {!puedeBorrar
              ? "Las fotos las borra URUKU: avisale al admin si hay que liberar lugar."
              : puedePagarExtra
                ? "Si subís otra, vas a poder pagar una foto extra o borrar la más vieja."
                : "Si subís otra, se te va a ofrecer borrar la más vieja."}
          </span>
        </div>
      )}
      <div className="galup-grid">
        {/* La portada primero y con su etiqueta: es la foto que ve el comprador antes que nada. */}
        {(portada?.url || portada?.thumb_url) && (
          <div className="galup-cell">
            <div className="galup-item galup-portada">
              <img src={(portada.thumb_url || portada.url) as string} alt="Portada actual" />
              <span className="galup-tag"><Ic n="estrella" s={11} peso="fill" /> Portada</span>
            </div>
          </div>
        )}
        {fotos.map((f) => (
          <div key={f.id} className="galup-cell">
            <div className="galup-item">
              <img src={f.thumb_url || f.url} alt="" loading="lazy" />
              {puedeBorrar && (
                <button type="button" className="galup-del" onClick={() => delFoto(f.id)} aria-label="Borrar"><Ic n="cerrar" s={13} /></button>
              )}
            </div>
            {api.usarComoPortada && (
              <button type="button" className="galup-usar" disabled={!!cambiando || subiendo} onClick={() => usarComoPortada(f.id)}>
                {cambiando === f.id ? "Cambiando…" : "Usar como portada"}
              </button>
            )}
          </div>
        ))}
        {pendFotos.map((p, i) => (
          <div key={p.id} className="galup-item galup-penditem" title="Se sube cuando haya señal">
            <img src={pendFotoUrls[i]} alt="" />
            <span className="galup-clock" title="Sin subir"><Ic n="reloj" s={13} /></span>
          </div>
        ))}
        <button type="button" className="galup-add" onClick={() => fotoInput.current?.click()} disabled={subiendo}>+ Foto</button>
      </div>

      <div className="galup-head" style={{ marginTop: 16 }}><b>Videos</b><span>{totalVideos}/{MAX_VIDEOS} · ≤60s</span></div>
      <div className="galup-grid">
        {videos.map((v) => (
          <div key={v.id} className="galup-item galup-vid">
            <video src={v.url} muted playsInline preload="metadata" />
            <span className="galup-dur">{v.duracion_seg ? `${v.duracion_seg}s` : <Ic n="video_play" s={13} />}</span>
            <button type="button" className="galup-del" onClick={() => delVideo(v.id)} aria-label="Borrar"><Ic n="cerrar" s={13} /></button>
          </div>
        ))}
        {pendVideos.map((p) => (
          <div key={p.id} className="galup-item galup-vid galup-penditem" title="Se sube cuando haya señal">
            <span className="galup-clock" title="Sin subir"><Ic n="reloj" s={13} /></span>
            <span className="galup-dur">{p.dur ? `${p.dur}s` : <Ic n="video_play" s={13} />}</span>
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

      {dlg && <TopeFotosDialogo tope={dlg.tope} puedePagarExtra={puedePagarExtra} puedeBorrar={puedeBorrar} onElegir={dlg.resolver} />}
    </div>
  );
}
