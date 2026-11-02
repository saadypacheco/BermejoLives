"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE } from "@/components/content/content-ui";
import { comprimirImagen } from "@/lib/imagen";
import { useObjectUrls } from "@/lib/object-url";
import type { ContentAssetUploadResponse, ContentBankApi } from "@/lib/content";
import {
  esErrorDeRed, frenaLaTanda, hexDe, mensajeDeSubida, type MetaSubida,
} from "@/lib/content-pure";
import {
  colaDisponible, encolarSubida, listarSubidas, quitarSubida, sincronizarSubidas, type SubidaPendiente,
} from "@/lib/content-queue";

/** 2048 px de lado mayor y calidad 0,8 (T-12): un cuadro 9:16 mide 1920 de alto y
 *  el zoom suma 6 %; con 1600 px la foto vertical se agrandaba y perdía nitidez. */
const LADO_MAX = 2048;
const CALIDAD = 0.8;

type Falla = { nombre: string; motivo: string };

/** El resumen de la última tanda, para decirlo con palabras. */
type Resumen = { subidas: number; yaEstaban: number; sinSenal: number; fallas: Falla[]; avisos: string[] };

const RESUMEN_VACIO: Resumen = { subidas: 0, yaEstaban: 0, sinSenal: 0, fallas: [], avisos: [] };

/** SHA-256 del ORIGINAL (antes de comprimir): es la clave que hace seguros los
 *  reintentos. `crypto.subtle` sólo existe en https o localhost; sin él no hay
 *  hash y el backend simplemente no puede deduplicar por origen. */
async function shaDe(file: File): Promise<string | null> {
  try {
    if (typeof crypto === "undefined" || !crypto.subtle) return null;
    return hexDe(await crypto.subtle.digest("SHA-256", await file.arrayBuffer()));
  } catch { return null; }
}

function avisosDe(r: ContentAssetUploadResponse): string[] {
  const out: string[] = [];
  if (r.asset.too_small) out.push("Alguna foto es muy chica para video: se guarda igual, pero no entra en videos.");
  if (r.ficha.requested && !r.ficha.added) {
    out.push(r.ficha.reason === "tope"
      ? "Alguna foto no entró a la ficha: el comercio llegó al tope de fotos de su plan. Quedó en el banco."
      : "Alguna foto no pudo entrar a la ficha. Quedó en el banco.");
  }
  for (const w of r.warnings ?? []) out.push(w);
  return out;
}

/**
 * Subida de fotos al banco desde el celular (§9.2): se sacan o eligen VARIAS de
 * una vez, para un comercio ya elegido. Cada foto se comprime acá, se le saca la
 * huella (`sha256` del original) y sube con su progreso. Lo que no sube por falta
 * de señal queda en el teléfono (IndexedDB) y se reintenta solo al volver la
 * señal y al abrir la pantalla; reintentar es seguro (el servidor contesta
 * `duplicate` ante lo repetido).
 *
 * El panel y la app de campo lo usan igual: lo que cambia (token y endpoints)
 * llega en `api`.
 */
export function ContentBankUploader({ comercioId, api, onSubida }: {
  comercioId: string;
  api: ContentBankApi;
  /** Cada foto que el servidor aceptó: quien muestra la grilla se pone al día. */
  onSubida: (r: ContentAssetUploadResponse) => void;
}) {
  const [mostrarFicha, setMostrarFicha] = useState(false);
  const [hayPersonas, setHayPersonas] = useState(false);
  const [aceptaron, setAceptaron] = useState(false);
  const [subiendo, setSubiendo] = useState(false);
  const [lote, setLote] = useState<{ total: number; actual: number; pct: number } | null>(null);
  const [resumen, setResumen] = useState<Resumen | null>(null);
  const [frenada, setFrenada] = useState("");
  const [pendientes, setPendientes] = useState<SubidaPendiente[]>([]);
  const [otrosPend, setOtrosPend] = useState(0);
  const [sincronizando, setSincronizando] = useState(false);
  const [errCola, setErrCola] = useState("");

  const camaraRef = useRef<HTMLInputElement>(null);
  const galeriaRef = useRef<HTMLInputElement>(null);
  const cancelar = useRef(false);
  const ocupado = useRef(false);          // una sola tanda a la vez (subida o sincronización)
  const vivo = useRef(true);
  useEffect(() => { vivo.current = true; return () => { vivo.current = false; }; }, []);

  const pendUrls = useObjectUrls(pendientes, (p) => p.blob);
  const puedeSubir = !subiendo && !sincronizando && (!hayPersonas || aceptaron);

  const refrescarCola = useCallback(async () => {
    if (!colaDisponible()) return;
    try {
      const todas = await listarSubidas(api.scope);
      if (!vivo.current) return;
      setPendientes(todas.filter((p) => p.comercioId === comercioId));
      setOtrosPend(todas.filter((p) => p.comercioId !== comercioId).length);
    } catch { /* sin cola: sigue andando, sólo que sin reintento automático */ }
  }, [api.scope, comercioId]);

  const metaDe = (p: SubidaPendiente): MetaSubida => ({
    source_sha256: p.source_sha256 || null, taken_at_ms: p.taken_at_ms,
    show_in_ficha: p.show_in_ficha, has_people: p.has_people, people_ok: p.people_ok,
  });

  /** Sube lo que quedó en la cola del teléfono (de este comercio y de los demás
   *  del mismo ámbito: cada entrada lleva su comercio). */
  const sincronizar = useCallback(async () => {
    if (ocupado.current || !colaDisponible()) return;
    ocupado.current = true;
    setSincronizando(true); setErrCola("");
    try {
      const r = await sincronizarSubidas({
        ambito: api.scope,
        subir: (item) => api.subir(
          item.comercioId, new File([item.blob], item.name, { type: item.blob.type || "image/jpeg" }), metaDe(item),
          (pct) => { if (vivo.current) setLote({ total: 1, actual: 1, pct }); }),
        esRed: (ex) => esErrorDeRed(ex, typeof navigator === "undefined" || navigator.onLine),
        frena: frenaLaTanda,
        mensaje: mensajeDeSubida,
        onSubida: (item, resp) => { if (item.comercioId === comercioId && vivo.current) onSubida(resp); },
      });
      if (!vivo.current) return;
      if (r.error) setErrCola(r.error);
    } finally {
      ocupado.current = false;
      if (vivo.current) { setSincronizando(false); setLote(null); await refrescarCola(); }
    }
  }, [api, comercioId, onSubida, refrescarCola]);

  // Al abrir la pantalla y cada vez que vuelve la señal: mira la cola y la sube.
  useEffect(() => {
    void refrescarCola().then(() => { void sincronizar(); });
    const alVolver = () => { void sincronizar(); };
    window.addEventListener("online", alVolver);
    return () => window.removeEventListener("online", alVolver);
  }, [comercioId]);   // eslint-disable-line react-hooks/exhaustive-deps

  async function procesar(files: File[]) {
    if (!files.length || ocupado.current) return;
    ocupado.current = true;
    cancelar.current = false;
    setSubiendo(true); setResumen(null); setFrenada(""); setErrCola("");
    const r: Resumen = { subidas: 0, yaEstaban: 0, sinSenal: 0, fallas: [], avisos: [] };
    const avisosVistos = new Set<string>();
    try {
      for (let i = 0; i < files.length; i++) {
        if (cancelar.current) break;
        const original = files[i];
        setLote({ total: files.length, actual: i + 1, pct: 0 });
        const sha = await shaDe(original);
        let foto: File = original;
        try { foto = await comprimirImagen(original, LADO_MAX, CALIDAD); } catch { /* se sube el original */ }
        const meta: MetaSubida = {
          source_sha256: sha, taken_at_ms: original.lastModified || null,
          show_in_ficha: mostrarFicha, has_people: hayPersonas, people_ok: hayPersonas ? aceptaron : null,
        };
        try {
          const resp = await api.subir(comercioId, foto, meta, (pct) => { if (vivo.current) setLote({ total: files.length, actual: i + 1, pct }); });
          if (resp.duplicate) r.yaEstaban += 1; else r.subidas += 1;
          for (const a of avisosDe(resp)) if (!avisosVistos.has(a)) { avisosVistos.add(a); r.avisos.push(a); }
          onSubida(resp);
        } catch (ex) {
          if (colaDisponible() && esErrorDeRed(ex, navigator.onLine)) {
            // Sin señal: queda en el teléfono y sube sola. No es un error de la persona.
            await encolarSubida({
              ambito: api.scope, comercioId, blob: foto,
              name: foto.name || "foto.jpg",
              // Sin huella (http) la clave sale de lo que tiene el archivo; no se manda al servidor.
              source_sha256: sha ?? "",
              taken_at_ms: meta.taken_at_ms, show_in_ficha: meta.show_in_ficha,
              has_people: meta.has_people, people_ok: meta.people_ok,
            }).catch(() => { r.fallas.push({ nombre: original.name, motivo: "No se pudo guardar en el teléfono" }); });
            r.sinSenal += 1;
          } else {
            r.fallas.push({ nombre: original.name || `Foto ${i + 1}`, motivo: mensajeDeSubida(ex) });
            if (frenaLaTanda(ex)) { setFrenada(mensajeDeSubida(ex)); break; }
          }
        }
      }
    } finally {
      ocupado.current = false;
      if (vivo.current) {
        setSubiendo(false); setLote(null); setResumen(r);
        await refrescarCola();
      }
    }
  }

  function alElegir(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? []);
    e.target.value = "";            // el mismo archivo se puede volver a elegir
    void procesar(files);
  }

  async function descartar(p: SubidaPendiente) {
    if (!window.confirm("¿Descartar esta foto? No se sube y se borra del teléfono.")) return;
    await quitarSubida(p.key).catch(() => {});
    await refrescarCola();
  }

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div style={{ display: "grid", gap: 8 }}>
        <label style={{ display: "flex", gap: 10, alignItems: "center", minHeight: 44, fontSize: 14 }}>
          <input type="checkbox" checked={mostrarFicha} onChange={(e) => setMostrarFicha(e.target.checked)} style={{ width: 20, height: 20 }} />
          Mostrar también en la ficha
        </label>
        <label style={{ display: "flex", gap: 10, alignItems: "center", minHeight: 44, fontSize: 14 }}>
          <input type="checkbox" checked={hayPersonas}
                 onChange={(e) => { setHayPersonas(e.target.checked); if (!e.target.checked) setAceptaron(false); }}
                 style={{ width: 20, height: 20 }} />
          Hay personas que se reconocen
        </label>
        {hayPersonas && (
          <label style={{ display: "flex", gap: 10, alignItems: "center", minHeight: 44, fontSize: 14, marginLeft: 8 }}>
            <input type="checkbox" checked={aceptaron} onChange={(e) => setAceptaron(e.target.checked)} style={{ width: 20, height: 20 }} />
            Las personas de la foto aceptaron aparecer
          </label>
        )}
        {hayPersonas && !aceptaron && (
          <p style={{ margin: 0, fontSize: 12.5, color: "var(--amber)" }}>
            <Ic n="aviso" s={13} /> Confirmá que aceptaron antes de subir. Clientes y chicos: no. Ante la duda, no la subas con personas.
          </p>
        )}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary" style={{ ...BTN_GRANDE, flex: "1 1 160px" }} disabled={!puedeSubir}
                onClick={() => camaraRef.current?.click()}>
          <Ic n="foto" s={18} /> Sacar fotos
        </button>
        <button type="button" className="btn btn-ghost" style={{ ...BTN_GRANDE, flex: "1 1 160px" }} disabled={!puedeSubir}
                onClick={() => galeriaRef.current?.click()}>
          <Ic n="subir" s={18} /> Elegir de la galería
        </button>
      </div>
      <input ref={camaraRef} type="file" accept="image/*" capture="environment" hidden onChange={alElegir} />
      <input ref={galeriaRef} type="file" accept="image/*" multiple hidden onChange={alElegir} />

      {(subiendo || sincronizando) && lote && (
        <div role="status" aria-live="polite" style={{ display: "grid", gap: 6 }}>
          <div style={{ height: 8, borderRadius: 4, background: "var(--stroke)", overflow: "hidden" }}>
            <div style={{ height: "100%", width: `${lote.pct}%`, background: "var(--neon)", transition: "width .15s" }} />
          </div>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap", fontSize: 13.5 }}>
            <span>{sincronizando && !subiendo ? "Subiendo lo que quedó sin señal" : `Subiendo ${lote.actual}/${lote.total}`} · {lote.pct}%</span>
            {subiendo && (
              <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => { cancelar.current = true; }}>
                <Ic n="cerrar" s={14} /> Cancelar
              </button>
            )}
          </div>
        </div>
      )}

      {frenada && <Aviso tono="error">{frenada}</Aviso>}

      {resumen && (
        <div style={{ display: "grid", gap: 6 }}>
          {(resumen.subidas > 0 || resumen.yaEstaban > 0 || resumen.sinSenal > 0) && (
            <Aviso tono="ok">
              {resumen.subidas > 0 && <>Subiste {resumen.subidas} {resumen.subidas === 1 ? "foto" : "fotos"}. </>}
              {resumen.yaEstaban > 0 && <>{resumen.yaEstaban} ya {resumen.yaEstaban === 1 ? "estaba" : "estaban"} en el banco. </>}
              {resumen.sinSenal > 0 && <>{resumen.sinSenal} quedaron guardadas en el teléfono sin señal: se suben solas cuando haya internet.</>}
            </Aviso>
          )}
          {resumen.fallas.length > 0 && (
            <Aviso tono="error">
              {resumen.fallas.length === 1 ? "1 foto no subió:" : `${resumen.fallas.length} fotos no subieron:`}
              <ul style={{ margin: "4px 0 0", paddingLeft: 18 }}>
                {resumen.fallas.slice(0, 5).map((f, i) => <li key={i}>{f.nombre}: {f.motivo}</li>)}
                {resumen.fallas.length > 5 && <li>y {resumen.fallas.length - 5} más</li>}
              </ul>
            </Aviso>
          )}
          {resumen.avisos.map((a, i) => <Aviso key={i} tono="aviso">{a}</Aviso>)}
        </div>
      )}

      {(pendientes.length > 0 || otrosPend > 0) && (
        <div style={{ display: "grid", gap: 8, padding: 10, border: "1px dashed var(--amber)", borderRadius: 10 }}>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap", fontSize: 13.5 }}>
            <Ic n="reloj" s={15} />
            <b>{pendientes.length + otrosPend} sin subir</b>
            <span style={{ color: "var(--txt-3)" }}>
              (sin señal{otrosPend > 0 && pendientes.length > 0 ? `; ${otrosPend} son de otros comercios` : otrosPend > 0 ? "; son de otros comercios" : ""})
            </span>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => void sincronizar()} disabled={sincronizando || subiendo}>
              <Ic n="actualizar" s={14} /> {sincronizando ? "Subiendo…" : "Reintentar ahora"}
            </button>
          </div>
          {errCola && <p role="alert" style={{ margin: 0, fontSize: 12.5, color: "var(--pink)" }}><Ic n="aviso" s={13} /> {errCola}</p>}
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {pendientes.map((p, i) => (
              <div key={p.key} style={{ position: "relative", width: 72, height: 72, borderRadius: 8, overflow: "hidden", border: "1px solid var(--stroke)" }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={pendUrls[i]} alt="Foto esperando señal" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                <span title="Sin subir" style={{ position: "absolute", left: 3, top: 3, color: "#fff", background: "rgba(0,0,0,.55)", borderRadius: 6, padding: "1px 4px" }}><Ic n="reloj" s={12} /></span>
                {p.ultimoError && (
                  <button type="button" aria-label="Descartar esta foto" title={`No subió: ${p.ultimoError}. Tocá para descartarla.`}
                          onClick={() => void descartar(p)}
                          style={{ position: "absolute", right: 2, top: 2, minWidth: 28, minHeight: 28, borderRadius: 14, border: "none", background: "rgba(0,0,0,.65)", color: "#fff", cursor: "pointer" }}>
                    <Ic n="cerrar" s={13} />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
