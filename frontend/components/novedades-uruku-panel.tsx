"use client";

// «Novedades de URUKU» en el panel del publicador (/contenido): lo que cuenta la
// marca misma —«URUKU auspició el Festival del Lapacho»— con portada, fotos y
// video. Lista (activas e inactivas), alta y edición, medios con progreso y baja
// lógica. Contrato: docs/novedades-uruku.md.
//
// El flujo es en dos pasos porque los archivos cuelgan de un id: primero se
// guardan los datos, y recién entonces el formulario ofrece portada, fotos y video.

import { useEffect, useMemo, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { getCiudades } from "@/lib/data";
import type { Ciudad } from "@/lib/types";
import {
  bajaNovedadUruku, crearNovedadUruku, editarNovedadUruku, listarNovedadesUruku, quitarFotoNovedad,
  subirFotoNovedad, subirPortadaNovedad, subirVideoNovedad,
  type NovedadUrukuAdmin, type NovedadUrukuCampos,
} from "@/lib/publicador";

const MAX_FOTOS = 12;
const MAX_FOTO_BYTES = 15 * 1024 * 1024;
const MAX_VIDEO_BYTES = 100 * 1024 * 1024;
const TIPOS_VIDEO = ["video/mp4", "video/webm", "video/quicktime"];

/** Hoy en La Paz como YYYY-MM-DD: es la fecha por defecto de la columna. */
function hoyLaPaz(): string {
  try { return new Intl.DateTimeFormat("en-CA", { timeZone: "America/La_Paz" }).format(new Date()); }
  catch { return new Date().toISOString().slice(0, 10); }
}

function fechaCorta(iso: string): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

type Form = { titulo: string; texto: string; fecha: string; ciudadSlug: string; enlace: string; destacada: boolean };
const FORM_VACIO = (): Form => ({ titulo: "", texto: "", fecha: hoyLaPaz(), ciudadSlug: "", enlace: "", destacada: false });

export function NovedadesUrukuPanel({ flash, fail }: { flash: (m: string) => void; fail: (e: unknown) => void }) {
  const [items, setItems] = useState<NovedadUrukuAdmin[] | null>(null);
  const [errCarga, setErrCarga] = useState("");
  const [ciudades, setCiudades] = useState<Ciudad[]>([]);
  // `null` = ninguna abierta; "nueva" = formulario de alta; un id = editando esa.
  const [abierta, setAbierta] = useState<string | null>(null);

  const cargar = async () => {
    try { setItems(await listarNovedadesUruku()); setErrCarga(""); }
    catch (e) { setErrCarga(e instanceof Error ? e.message : "No se pudo cargar"); setItems((s) => s ?? []); fail(e); }
  };
  useEffect(() => {
    void cargar();
    getCiudades().then(setCiudades).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const nombreCiudad = (id: string | null) => (id ? ciudades.find((c) => c.id === id)?.nombre ?? "Una ciudad" : "Todas las ciudades");
  const editando = abierta && abierta !== "nueva" ? items?.find((n) => n.id === abierta) ?? null : null;

  async function darDeBaja(n: NovedadUrukuAdmin) {
    if (!window.confirm(`¿Dar de baja «${n.titulo}»? Deja de verse en el sitio. Después podés reactivarla.`)) return;
    try { await bajaNovedadUruku(n.id); flash("Novedad dada de baja"); await cargar(); } catch (e) { fail(e); }
  }
  async function reactivar(n: NovedadUrukuAdmin) {
    try { await editarNovedadUruku(n.id, { activo: true }); flash("Novedad reactivada"); await cargar(); } catch (e) { fail(e); }
  }

  return (
    <div className="glass" style={{ padding: 18, borderRadius: 16, marginBottom: 16 }} id="novedades-uruku">
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, flexWrap: "wrap" }}>
        <h3 style={{ margin: 0 }}><Ic n="novedades" s={17} /> Novedades de URUKU</h3>
        {abierta === null && (
          <button className="btn btn-primary btn-sm" onClick={() => setAbierta("nueva")}><Ic n="mas" s={15} /> Nueva novedad</button>
        )}
      </div>
      <p style={{ fontSize: 12.5, color: "var(--txt-3)", margin: "6px 0 12px" }}>
        Salen primero en «Novedades» del inicio y en /novedades. Una novedad «de todas las ciudades» se ve en todas.
      </p>

      {abierta !== null && (
        <Editor
          key={abierta}
          novedad={editando}
          ciudades={ciudades}
          flash={flash}
          fail={fail}
          onCambio={cargar}
          onCerrar={() => setAbierta(null)}
          onCreada={async (n) => { await cargar(); setAbierta(n.id); }}
        />
      )}

      {items === null && <p style={{ color: "var(--txt-3)", fontSize: 13 }}><Ic n="reloj" s={15} /> Cargando novedades…</p>}
      {errCarga && (
        <div style={{ color: "var(--pink)", fontSize: 13, marginBottom: 8 }}>
          <Ic n="aviso" s={15} /> {errCarga}{" "}
          <button className="link-more" onClick={() => void cargar()}>Reintentar</button>
        </div>
      )}
      {items !== null && items.length === 0 && !errCarga && abierta === null && (
        <p style={{ color: "var(--txt-3)", fontSize: 13 }}>Todavía no cargaste novedades de URUKU.</p>
      )}

      <div style={{ display: "grid", gap: 10 }}>
        {(items ?? []).map((n) => (
          <div key={n.id} style={{ display: "flex", gap: 12, alignItems: "flex-start", padding: 10, borderRadius: 12,
                                   border: "1px solid var(--stroke)", opacity: n.activo ? 1 : 0.7, flexWrap: "wrap" }}>
            <div style={{ width: 64, height: 64, flex: "0 0 64px", borderRadius: 10, overflow: "hidden", background: "#000",
                          display: "grid", placeItems: "center", color: "var(--txt-3)" }}>
              {n.portada_thumb_url || n.portada_url
                // eslint-disable-next-line @next/next/no-img-element
                ? <img src={n.portada_thumb_url || n.portada_url || ""} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                : <Ic n={n.video_url ? "video_play" : "foto"} s={24} />}
            </div>
            <div style={{ flex: "1 1 180px", minWidth: 0 }}>
              <b style={{ fontSize: 14, overflowWrap: "anywhere" }}>{n.titulo}</b>
              <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 2 }}>
                {fechaCorta(n.fecha)} · {nombreCiudad(n.ciudad_id)} · {n.fotos.length} foto{n.fotos.length === 1 ? "" : "s"}{n.video_url ? " · con video" : ""}
              </div>
              <div style={{ display: "flex", gap: 6, flexWrap: "wrap", marginTop: 6, fontSize: 12, fontWeight: 700 }}>
                {n.activo
                  ? <span style={{ color: "var(--neon)" }}><Ic n="listo" s={14} /> Activa</span>
                  : <span style={{ color: "var(--pink)" }}><Ic n="aviso" s={14} /> De baja</span>}
                {n.destacada && <span style={{ color: "var(--amber)" }}><Ic n="destacado" s={14} /> Destacada</span>}
              </div>
            </div>
            <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
              <button className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} onClick={() => setAbierta(n.id)}><Ic n="editar" s={15} /> Editar</button>
              {n.activo
                ? <button className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} onClick={() => void darDeBaja(n)}>Dar de baja</button>
                : <button className="btn btn-primary btn-sm" style={{ minHeight: 44 }} onClick={() => void reactivar(n)}>Reactivar</button>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function Editor({ novedad, ciudades, flash, fail, onCambio, onCerrar, onCreada }: {
  novedad: NovedadUrukuAdmin | null;
  ciudades: Ciudad[];
  flash: (m: string) => void;
  fail: (e: unknown) => void;
  onCambio: () => Promise<void>;
  onCerrar: () => void;
  onCreada: (n: NovedadUrukuAdmin) => Promise<void>;
}) {
  const inicial = useMemo<Form>(() => novedad ? {
    titulo: novedad.titulo, texto: novedad.texto ?? "", fecha: novedad.fecha || hoyLaPaz(),
    ciudadSlug: ciudades.find((c) => c.id === novedad.ciudad_id)?.slug ?? "",
    enlace: novedad.enlace_url ?? "", destacada: novedad.destacada,
  } : FORM_VACIO(),
  // Sólo cuando cambia de novedad o llegan las ciudades: no pisar lo que se está escribiendo.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  [novedad?.id, ciudades.length]);
  const [f, setF] = useState<Form>(inicial);
  useEffect(() => setF(inicial), [inicial]);
  const [guardando, setGuardando] = useState(false);
  const [aviso, setAviso] = useState("");

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setAviso("");
    const titulo = f.titulo.trim();
    if (!titulo) { setAviso("Falta el título."); return; }
    const enlace = f.enlace.trim();
    if (enlace && !/^https?:\/\/\S+$/i.test(enlace)) { setAviso("El enlace tiene que empezar con http:// o https://"); return; }
    const texto = f.texto.trim();
    const campos: NovedadUrukuCampos = {
      titulo, fecha: f.fecha || hoyLaPaz(), destacada: f.destacada,
      texto: texto || null, enlace_url: enlace || null,
    };
    // Al editar, «todas» tiene que viajar explícito para poder sacar la ciudad;
    // al crear, no mandar nada ya es «todas».
    if (novedad) campos.ciudad_slug = f.ciudadSlug || null;
    else if (f.ciudadSlug) campos.ciudad_slug = f.ciudadSlug;
    setGuardando(true);
    try {
      if (novedad) { await editarNovedadUruku(novedad.id, campos); flash("Novedad guardada"); await onCambio(); }
      else { const n = await crearNovedadUruku(campos); flash("Novedad creada. Ahora podés subir la portada, las fotos y el video."); await onCreada(n); }
    } catch (ex) { fail(ex); } finally { setGuardando(false); }
  }

  return (
    <div style={{ border: "1px solid var(--neon)", borderRadius: 14, padding: 14, marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <b style={{ fontSize: 15 }}>{novedad ? "Editar novedad" : "Nueva novedad"}</b>
        <button className="link-more" style={{ minHeight: 44 }} onClick={onCerrar}><Ic n="cerrar" s={14} /> Cerrar</button>
      </div>

      <form onSubmit={guardar} style={{ display: "grid", gap: 10 }}>
        <label style={{ display: "grid", gap: 4, fontSize: 13, fontWeight: 600 }}>
          Título
          <input className="adm-input" value={f.titulo} maxLength={120} required placeholder="URUKU auspició el Festival del Lapacho"
                 onChange={(e) => setF((s) => ({ ...s, titulo: e.target.value }))} />
        </label>
        <label style={{ display: "grid", gap: 4, fontSize: 13, fontWeight: 600 }}>
          Texto
          <textarea className="adm-input" rows={5} maxLength={2000} value={f.texto} style={{ resize: "vertical" }}
                    placeholder="Qué pasó, con qué comercios, dónde…" onChange={(e) => setF((s) => ({ ...s, texto: e.target.value }))} />
          <small style={{ fontWeight: 400, color: "var(--txt-3)" }}>{f.texto.length} / 2000</small>
        </label>
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))", gap: 10 }}>
          <label style={{ display: "grid", gap: 4, fontSize: 13, fontWeight: 600 }}>
            Fecha
            <input className="adm-input" type="date" value={f.fecha} onChange={(e) => setF((s) => ({ ...s, fecha: e.target.value }))} />
          </label>
          <label style={{ display: "grid", gap: 4, fontSize: 13, fontWeight: 600 }}>
            Ciudad
            <select className="adm-input" value={f.ciudadSlug} onChange={(e) => setF((s) => ({ ...s, ciudadSlug: e.target.value }))}>
              <option value="">Todas las ciudades</option>
              {ciudades.filter((c) => c.activa || c.id === novedad?.ciudad_id).map((c) => <option key={c.slug} value={c.slug}>{c.nombre}</option>)}
            </select>
          </label>
        </div>
        <label style={{ display: "grid", gap: 4, fontSize: 13, fontWeight: 600 }}>
          Enlace (opcional)
          <input className="adm-input" type="url" inputMode="url" autoCapitalize="none" autoCorrect="off" spellCheck={false}
                 value={f.enlace} placeholder="https://…" onChange={(e) => setF((s) => ({ ...s, enlace: e.target.value }))} />
        </label>
        <label style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 14, minHeight: 44 }}>
          <input type="checkbox" checked={f.destacada} style={{ width: 22, height: 22 }}
                 onChange={(e) => setF((s) => ({ ...s, destacada: e.target.checked }))} />
          <span><Ic n="destacado" s={15} /> Destacada: sale antes que las demás</span>
        </label>
        {aviso && <div style={{ color: "var(--pink)", fontSize: 13 }}><Ic n="aviso" s={15} /> {aviso}</div>}
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <button className="btn btn-primary" type="submit" disabled={guardando} style={{ minHeight: 44 }}>
            {guardando ? "Guardando…" : novedad ? "Guardar cambios" : "Crear y seguir con las fotos"}
          </button>
        </div>
      </form>

      {novedad
        ? <Medios novedad={novedad} flash={flash} fail={fail} onCambio={onCambio} />
        : <p style={{ fontSize: 12.5, color: "var(--txt-3)", margin: "12px 0 0" }}>La portada, las fotos y el video se suben después de crearla.</p>}
    </div>
  );
}

function Medios({ novedad, flash, fail, onCambio }: {
  novedad: NovedadUrukuAdmin; flash: (m: string) => void; fail: (e: unknown) => void; onCambio: () => Promise<void>;
}) {
  const [progPortada, setProgPortada] = useState<number | null>(null);
  const [progFotos, setProgFotos] = useState<{ n: number; de: number; pct: number } | null>(null);
  const [progVideo, setProgVideo] = useState<number | null>(null);
  const [poster, setPoster] = useState<File | null>(null);
  const [aviso, setAviso] = useState("");
  const refPortada = useRef<HTMLInputElement>(null);
  const refFotos = useRef<HTMLInputElement>(null);
  const refVideo = useRef<HTMLInputElement>(null);
  const refPoster = useRef<HTMLInputElement>(null);
  const ocupado = progPortada !== null || progFotos !== null || progVideo !== null;

  const esImagen = (f: File) => f.type.startsWith("image/");

  async function onPortada(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = "";
    if (!file) return;
    setAviso("");
    if (!esImagen(file)) { setAviso("La portada tiene que ser una imagen."); return; }
    if (file.size > MAX_FOTO_BYTES) { setAviso("La portada pesa más de 15 MB."); return; }
    setProgPortada(0);
    try { await subirPortadaNovedad(novedad.id, file, setProgPortada); flash("Portada subida"); await onCambio(); }
    catch (ex) { fail(ex); } finally { setProgPortada(null); }
  }

  async function onFotos(e: React.ChangeEvent<HTMLInputElement>) {
    const elegidas = Array.from(e.target.files ?? []); e.target.value = "";
    if (elegidas.length === 0) return;
    setAviso("");
    const lugar = MAX_FOTOS - novedad.fotos.length;
    if (lugar <= 0) { setAviso(`Ya tiene ${MAX_FOTOS} fotos, que es el máximo. Sacá alguna para sumar otra.`); return; }
    const validas = elegidas.filter((f) => esImagen(f) && f.size <= MAX_FOTO_BYTES);
    const descartadas = elegidas.length - validas.length;
    const subir = validas.slice(0, lugar);
    const sobran = validas.length - subir.length;
    if (descartadas > 0 || sobran > 0) {
      setAviso([
        descartadas > 0 ? `${descartadas} no se subieron (no son imagen o pesan más de 15 MB).` : "",
        sobran > 0 ? `Entran ${lugar} más: ${sobran} quedaron afuera (máximo ${MAX_FOTOS}).` : "",
      ].filter(Boolean).join(" "));
    }
    if (subir.length === 0) return;
    // De a una: así el progreso es claro y, si una falla, las anteriores ya quedaron.
    let subidas = 0;
    try {
      for (let i = 0; i < subir.length; i++) {
        setProgFotos({ n: i + 1, de: subir.length, pct: 0 });
        await subirFotoNovedad(novedad.id, subir[i], (pct) => setProgFotos({ n: i + 1, de: subir.length, pct }));
        subidas++;
      }
      flash(subidas === 1 ? "Foto subida" : `${subidas} fotos subidas`);
    } catch (ex) { fail(ex); }
    finally { setProgFotos(null); if (subidas > 0) await onCambio(); }
  }

  async function sacarFoto(url: string) {
    if (!window.confirm("¿Sacar esta foto de la novedad?")) return;
    try { await quitarFotoNovedad(novedad.id, url); flash("Foto sacada"); await onCambio(); } catch (ex) { fail(ex); }
  }

  async function onVideo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = "";
    if (!file) return;
    setAviso("");
    if (!TIPOS_VIDEO.includes(file.type)) { setAviso("El video tiene que ser mp4, webm o mov."); return; }
    if (file.size > MAX_VIDEO_BYTES) { setAviso("El video pesa más de 100 MB."); return; }
    if (novedad.video_url && !window.confirm("Esta novedad ya tiene un video. ¿Reemplazarlo?")) return;
    setProgVideo(0);
    try { await subirVideoNovedad(novedad.id, file, poster, setProgVideo); setPoster(null); flash("Video subido"); await onCambio(); }
    catch (ex) { fail(ex); } finally { setProgVideo(null); }
  }

  const caja: React.CSSProperties = { marginTop: 16, paddingTop: 14, borderTop: "1px solid var(--stroke)" };
  const barra = (pct: number) => (
    <div role="progressbar" aria-valuenow={pct} aria-valuemin={0} aria-valuemax={100}
         style={{ height: 8, borderRadius: 999, background: "var(--stroke)", overflow: "hidden", marginTop: 6 }}>
      <div style={{ width: `${pct}%`, height: "100%", background: "var(--neon)", transition: "width .15s" }} />
    </div>
  );

  return (
    <div>
      {aviso && <div style={{ ...caja, color: "var(--amber)", fontSize: 13 }}><Ic n="aviso" s={15} /> {aviso}</div>}

      {/* Portada */}
      <div style={caja}>
        <b style={{ fontSize: 14 }}><Ic n="foto" s={16} /> Portada</b>
        <div style={{ display: "flex", gap: 12, alignItems: "center", flexWrap: "wrap", marginTop: 8 }}>
          {novedad.portada_thumb_url || novedad.portada_url
            // eslint-disable-next-line @next/next/no-img-element
            ? <img src={novedad.portada_thumb_url || novedad.portada_url || ""} alt="Portada actual" style={{ width: 96, height: 96, objectFit: "cover", borderRadius: 10 }} />
            : <span style={{ fontSize: 13, color: "var(--txt-3)" }}>Sin portada: la tarjeta sale con el fondo verde.</span>}
          <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={ocupado} onClick={() => refPortada.current?.click()}>
            {novedad.portada_url ? "Cambiar portada" : "Subir portada"}
          </button>
          <input ref={refPortada} type="file" accept="image/*" hidden onChange={onPortada} />
        </div>
        {progPortada !== null && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 8 }}>Subiendo portada… {progPortada}%{barra(progPortada)}</div>}
      </div>

      {/* Fotos */}
      <div style={caja}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
          <b style={{ fontSize: 14 }}><Ic n="foto" s={16} /> Fotos ({novedad.fotos.length} de {MAX_FOTOS})</b>
          <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }}
                  disabled={ocupado || novedad.fotos.length >= MAX_FOTOS} onClick={() => refFotos.current?.click()}>
            <Ic n="mas" s={15} /> Agregar fotos
          </button>
          <input ref={refFotos} type="file" accept="image/*" multiple hidden onChange={onFotos} />
        </div>
        {progFotos && (
          <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 8 }}>
            Subiendo foto {progFotos.n} de {progFotos.de}… {progFotos.pct}%{barra(progFotos.pct)}
          </div>
        )}
        {novedad.fotos.length === 0 && !progFotos && <p style={{ fontSize: 13, color: "var(--txt-3)", margin: "8px 0 0" }}>Todavía no hay fotos. Elegí varias a la vez.</p>}
        <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(88px, 1fr))", gap: 8, marginTop: 10 }}>
          {novedad.fotos.map((fo, i) => (
            <div key={fo.url} style={{ position: "relative", borderRadius: 10, overflow: "hidden", border: "1px solid var(--stroke)" }}>
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={fo.thumb_url || fo.url} alt={`Foto ${i + 1}`} style={{ width: "100%", aspectRatio: "3 / 4", objectFit: "cover", display: "block" }} />
              <button type="button" onClick={() => void sacarFoto(fo.url)} aria-label={`Sacar la foto ${i + 1}`} disabled={ocupado}
                      style={{ position: "absolute", top: 4, right: 4, width: 32, height: 32, borderRadius: "50%", background: "rgba(0,0,0,.7)",
                               color: "#fff", display: "grid", placeItems: "center" }}>
                <Ic n="cerrar" s={14} />
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Video */}
      <div style={caja}>
        <b style={{ fontSize: 14 }}><Ic n="videos" s={16} /> Video</b>
        {novedad.video_url && (
          <video src={novedad.video_url} poster={novedad.video_poster_url ?? undefined} controls playsInline preload="metadata"
                 style={{ display: "block", width: "100%", maxHeight: 280, background: "#000", borderRadius: 10, marginTop: 8 }} />
        )}
        <p style={{ fontSize: 12.5, color: "var(--txt-3)", margin: "8px 0" }}>mp4, webm o mov, hasta 100 MB. El póster es la imagen que se ve antes de darle play (opcional).</p>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <button type="button" className="btn btn-ghost btn-sm" style={{ minHeight: 44 }} disabled={ocupado} onClick={() => refPoster.current?.click()}>
            <Ic n="foto" s={15} /> {poster ? "Cambiar póster" : "Elegir póster"}
          </button>
          <input ref={refPoster} type="file" accept="image/*" hidden
                 onChange={(e) => { const p = e.target.files?.[0] ?? null; e.target.value = ""; setPoster(p && esImagen(p) && p.size <= MAX_FOTO_BYTES ? p : null); }} />
          {poster && <span style={{ fontSize: 12, color: "var(--txt-2)" }}>{poster.name}</span>}
          <button type="button" className="btn btn-primary btn-sm" style={{ minHeight: 44 }} disabled={ocupado} onClick={() => refVideo.current?.click()}>
            <Ic n="video" s={15} /> {novedad.video_url ? "Reemplazar video" : "Subir video"}
          </button>
          <input ref={refVideo} type="file" accept="video/mp4,video/webm,video/quicktime" hidden onChange={onVideo} />
        </div>
        {progVideo !== null && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 8 }}>Subiendo video… {progVideo}%{barra(progVideo)}</div>}
      </div>
    </div>
  );
}
