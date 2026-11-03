"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Cargando, ErrorConReintento, Insignia } from "@/components/content/content-ui";
import { ResumenTextosVideo, TextosDelVideo } from "@/components/content/content-video-texts";
import {
  aprobarEnLote, aprobarPieza, getPieza, guardarTextosPieza, listarPiezas, mensajeContent, rearmarPieza,
  reintentarPieza, saltarPieza, type ContentPieceResponse, type ContentPieceSkip, type ContentPieceUpdate,
} from "@/lib/content";
import {
  aprobableEnLote, CAPTION_LABEL, CAPTION_MAX, contadorTexto, esPiezaV2, fechaConDia, fotoMarcadaPorGemini,
  hashtagsDisponibles, motivoNoAprobable, normalizarHashtag, piezaEnMovimiento, SKIP_REASON_LABEL, urlApiOpt,
  type CaptionCampo,
} from "@/lib/content-pure";

const ESTADOS_REVISION = ["ready_for_review", "failed", "queued", "rendering"] as const;
const POLL_MS = 20000;

/**
 * Admin › Contenido para redes › Revisión (§9.3): cada pieza armada por el
 * servidor se ve, se corrige y se aprueba o se saltea ACÁ. Nada sale a las redes
 * sin pasar por una persona.
 *
 * Mientras haya piezas en cola o armándose, la pantalla pregunta cada 20 s.
 */
export function ContentReview({ onCambioCola, sinArmador }: { onCambioCola?: () => void; sinArmador?: boolean }) {
  const [piezas, setPiezas] = useState<ContentPieceResponse[] | null>(null);
  const [cargando, setCargando] = useState(true);
  const [err, setErr] = useState("");
  const [mensaje, setMensaje] = useState("");
  const [lote, setLote] = useState(false);

  const cargar = useCallback(async (silencioso = false) => {
    if (!silencioso) setCargando(true);
    setErr("");
    try {
      const nuevas = await listarPiezas(ESTADOS_REVISION);
      // Lo que no cambió de estado se deja como está: así un texto a medio editar
      // no se pisa con la respuesta de la consulta automática.
      setPiezas((prev) => nuevas.map((n) => {
        const v = prev?.find((x) => x.id === n.id);
        return v && v.status === n.status ? v : n;
      }));
    } catch (ex) { setErr(mensajeContent(ex, "No se pudieron cargar las piezas")); }
    finally { setCargando(false); }
  }, []);

  useEffect(() => { void cargar(); }, [cargar]);

  const hayMovimiento = (piezas ?? []).some((p) => piezaEnMovimiento(p.status));
  useEffect(() => {
    if (!hayMovimiento) return;
    const t = setInterval(() => { void cargar(true); }, POLL_MS);
    return () => clearInterval(t);
  }, [hayMovimiento, cargar]);

  const reemplazar = useCallback((p: ContentPieceResponse) => {
    setPiezas((prev) => (prev ? prev.map((x) => (x.id === p.id ? p : x)) : prev));
  }, []);
  const quitar = useCallback((id: string, texto: string) => {
    setPiezas((prev) => (prev ? prev.filter((x) => x.id !== id) : prev));
    setMensaje(texto);
    onCambioCola?.();
  }, [onCambioCola]);

  const lista = piezas ?? [];
  const paraRevisar = lista.filter((p) => p.status === "ready_for_review");
  const conProblemas = lista.filter((p) => p.status === "failed");
  const enCola = lista.filter((p) => piezaEnMovimiento(p.status));
  const enVerde = paraRevisar.filter(aprobableEnLote);

  async function aprobarVerdes() {
    if (enVerde.length === 0) return;
    if (!window.confirm(`¿Aprobar las ${enVerde.length} piezas que están en verde? Van a quedar listas para publicar en el Paquete del día.`)) return;
    setLote(true); setErr(""); setMensaje("");
    try {
      const r = await aprobarEnLote(enVerde.map((p) => p.id));
      const ok = new Set(r.approved);
      setPiezas((prev) => (prev ? prev.filter((x) => !ok.has(x.id)) : prev));
      setMensaje(
        `${r.approved.length === 1 ? "Se aprobó 1 pieza" : `Se aprobaron ${r.approved.length} piezas`}.` +
        (r.refused.length > 0 ? ` No se aprobaron ${r.refused.length}: ${r.refused.map((x) => x.motivo).join(" · ")}.` : ""));
      onCambioCola?.();
    } catch (ex) { setErr(mensajeContent(ex, "No se pudieron aprobar las piezas")); }
    finally { setLote(false); }
  }

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
        <b style={{ fontSize: 15 }}>
          Revisión · {paraRevisar.length} para revisar · {conProblemas.length} con problemas · {enCola.length} en cola
        </b>
        <button type="button" className="btn btn-ghost btn-sm" style={{ ...BTN_GRANDE, marginLeft: "auto" }} onClick={() => void cargar()} disabled={cargando}>
          <Ic n="actualizar" s={15} /> Actualizar
        </button>
      </div>

      {mensaje && <Aviso tono="ok">{mensaje}</Aviso>}
      {cargando && !piezas && <Cargando texto="Cargando las piezas…" />}
      {err && <ErrorConReintento mensaje={err} onReintentar={() => void cargar()} />}

      {piezas && !cargando && !err && lista.length === 0 && (
        <p style={{ margin: 0, fontSize: 14, color: "var(--txt-3)", lineHeight: 1.5 }}>
          No hay piezas para revisar. Armá la semana en la pestaña «Semana» y los videos aparecen acá cuando el servidor los termina.
        </p>
      )}

      {paraRevisar.map((p) => (
        <PiezaRevision key={`${p.id}:${p.status}`} pieza={p} sinArmador={sinArmador}
                       onCambio={reemplazar}
                       onAprobada={(x) => quitar(x.id, `Aprobada: ${fechaConDia(x.scheduled_for)} · ${x.comercio?.nombre ?? x.pillar_label}. Ya está en el Paquete del día.`)}
                       onSaltada={(x) => quitar(x.id, `Salteada: ${fechaConDia(x.scheduled_for)} · ${x.comercio?.nombre ?? x.pillar_label}.`)} />
      ))}

      {enVerde.length > 0 && (
        <div style={{ position: "sticky", bottom: 8, zIndex: 2 }}>
          <button type="button" className="btn btn-primary" style={{ ...BTN_GRANDE, width: "100%" }} onClick={() => void aprobarVerdes()} disabled={lote}>
            <Ic n="listo" s={18} /> {lote ? "Aprobando…" : `Aprobar todas las que están en verde (${enVerde.length})`}
          </button>
        </div>
      )}

      {conProblemas.map((p) => (
        <PiezaConProblemas key={`${p.id}:${p.status}`} pieza={p} onCambio={reemplazar} sinArmador={sinArmador}
                           onSaltada={(x) => quitar(x.id, `Salteada: ${fechaConDia(x.scheduled_for)} · ${x.comercio?.nombre ?? x.pillar_label}.`)} />
      ))}

      {enCola.map((p) => (
        <div key={p.id} className="panel-card glass" style={{ padding: 12, display: "grid", gap: 8 }}>
          <div style={{ display: "flex", gap: 10, alignItems: "center", flexWrap: "wrap" }}>
            <Insignia icono="reloj" tono="info">{p.status === "rendering" ? "ARMANDO EL VIDEO" : "EN COLA"}</Insignia>
            <span style={{ fontSize: 14 }}>{fechaConDia(p.scheduled_for)} · {p.pillar_label}{p.comercio ? ` · ${p.comercio.nombre}` : ""}</span>
            <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>El servidor la está preparando; se actualiza sola.</span>
          </div>
          {/* En las piezas v2 se ven los textos que se están armando, no el video viejo. */}
          {esPiezaV2(p) && (
            <>
              <div role="status" style={{ display: "flex", gap: 8, alignItems: "center", fontSize: 14, color: "var(--txt-2)" }}>
                <Ic n="actualizar" s={16} /> Armando el video…
              </div>
              <ResumenTextosVideo pieza={p} />
              {sinArmador && <Aviso tono="aviso">El armador de videos no está disponible. La pieza espera en la cola hasta que vuelva.</Aviso>}
            </>
          )}
        </div>
      ))}
    </div>
  );
}

/* ─── Una pieza para revisar ─────────────────────────────────────────────── */

const CAMPOS: CaptionCampo[] = ["caption_tiktok", "caption_ig", "caption_channel"];

function PiezaRevision({ pieza, sinArmador, onCambio, onAprobada, onSaltada }: {
  pieza: ContentPieceResponse;
  sinArmador?: boolean;
  onCambio: (p: ContentPieceResponse) => void;
  onAprobada: (p: ContentPieceResponse) => void;
  onSaltada: (p: ContentPieceResponse) => void;
}) {
  const [textos, setTextos] = useState<Record<CaptionCampo, string>>({
    caption_tiktok: pieza.caption_tiktok ?? "", caption_ig: pieza.caption_ig ?? "", caption_channel: pieza.caption_channel ?? "",
  });
  const [hashtags, setHashtags] = useState<string[]>(pieza.hashtags);
  const [quitarPos, setQuitarPos] = useState<number[]>([]);
  const [ocupado, setOcupado] = useState<"" | "guardar" | "aprobar" | "rearmar" | "saltar">("");
  const [errTextos, setErrTextos] = useState("");
  const [err, setErr] = useState("");
  const [saltando, setSaltando] = useState(false);
  const [motivo, setMotivo] = useState<ContentPieceSkip["reason"]>("bad_photos");
  const [nota, setNota] = useState("");
  const ultimaRecarga = useRef(0);
  const [videoSucio, setVideoSucio] = useState(false);
  const v2 = esPiezaV2(pieza);

  const original = {
    caption_tiktok: pieza.caption_tiktok ?? "", caption_ig: pieza.caption_ig ?? "", caption_channel: pieza.caption_channel ?? "",
  };
  const cambiados = CAMPOS.filter((c) => textos[c] !== original[c]);
  const hashCambiaron = hashtags.join("|") !== pieza.hashtags.join("|");
  const sucio = cambiados.length > 0 || hashCambiaron;
  const pasado = CAMPOS.some((c) => textos[c].length > CAPTION_MAX[c]);

  const portada = urlApiOpt(pieza.cover_url);
  const video = urlApiOpt(pieza.video_url);

  /** Venció la firma del video: se pide la pieza otra vez para traer la URL nueva. */
  async function videoRoto() {
    if (Date.now() - ultimaRecarga.current < 30000) return;
    ultimaRecarga.current = Date.now();
    try { onCambio(await getPieza(pieza.id)); } catch { /* el aviso de abajo queda */ }
  }

  async function guardar() {
    setOcupado("guardar"); setErrTextos("");
    const patch: ContentPieceUpdate = {};
    for (const c of cambiados) patch[c] = textos[c];
    if (hashCambiaron) patch.hashtags = hashtags;
    try {
      const nueva = await guardarTextosPieza(pieza.id, patch);
      // Lo que quedó guardado (el servidor puede haber recortado espacios) es lo que se ve.
      setTextos({ caption_tiktok: nueva.caption_tiktok ?? "", caption_ig: nueva.caption_ig ?? "", caption_channel: nueva.caption_channel ?? "" });
      setHashtags(nueva.hashtags);
      onCambio(nueva);
    } catch (ex) { setErrTextos(mensajeContent(ex, "No se pudieron guardar los textos")); }
    finally { setOcupado(""); }
  }

  /** Guarda lo que haya a medias en los textos de las redes (lo usa «Guardar y volver a armar»:
   *  la tarjeta se rehace al re-encolar y se perdería). Si falla, tira el error al que llama. */
  async function guardarAntes() {
    if (!sucio) return;
    const patch: ContentPieceUpdate = {};
    for (const c of cambiados) patch[c] = textos[c];
    if (hashCambiaron) patch.hashtags = hashtags;
    await guardarTextosPieza(pieza.id, patch);
  }

  async function aprobar() {
    if (pieza.caption_checks.length > 0 &&
        !window.confirm(`El validador tiene objeciones:\n- ${pieza.caption_checks.join("\n- ")}\n\n¿Aprobar igual?`)) return;
    setOcupado("aprobar"); setErr("");
    try { onAprobada(await aprobarPieza(pieza.id)); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo aprobar la pieza")); setOcupado(""); }
  }

  async function rearmar() {
    if (quitarPos.length === 0) return;
    if (!window.confirm(`¿Rearmar el video sin ${quitarPos.length === 1 ? "la foto marcada" : `las ${quitarPos.length} fotos marcadas`}? Se vuelve a armar en el servidor y tarda unos minutos.`)) return;
    setOcupado("rearmar"); setErr("");
    try { onCambio(await rearmarPieza(pieza.id, quitarPos)); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo rearmar la pieza")); setOcupado(""); }
  }

  async function saltar() {
    if (!window.confirm("¿Saltar esta pieza? No se publica." + (pieza.counts_for_quota ? " La cuota del comercio no se consume: se reprograma." : ""))) return;
    setOcupado("saltar"); setErr("");
    try { onSaltada(await saltarPieza(pieza.id, { reason: motivo, note: nota.trim() || null })); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo saltar la pieza")); setOcupado(""); }
  }

  const disponibles = hashtagsDisponibles(pieza.hashtags_allowed, hashtags);
  const motor = pieza.caption_engine.startsWith("gemini") ? "Gemini" : "plantilla fija";
  const ocupada = ocupado !== "";
  const noAprobable = v2 ? motivoNoAprobable(pieza) : null;
  const sinGuardar = sucio || (v2 && videoSucio);

  return (
    <article className="panel-card glass" style={{ padding: 14, display: "grid", gap: 12 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <b style={{ fontSize: 15 }}>{fechaConDia(pieza.scheduled_for)} · {pieza.pillar_label}{pieza.comercio ? ` · ${pieza.comercio.nombre}` : ""}</b>
        {pieza.counts_for_quota && <Insignia tono="ok" icono="estrella">Suscriptor</Insignia>}
        {pieza.caption_edited && <Insignia tono="info" icono="editar">Editada</Insignia>}
      </div>

      {video ? (
        <video controls playsInline preload="metadata" poster={portada ?? undefined} src={video} onError={() => void videoRoto()}
               style={{ width: "100%", maxWidth: 270, aspectRatio: "9 / 16", background: "#000", borderRadius: 12, justifySelf: "center" }}>
          Tu navegador no puede reproducir el video.
        </video>
      ) : (
        <Aviso tono="aviso">Esta pieza todavía no tiene video para mirar.</Aviso>
      )}
      {pieza.duration_s ? <span style={{ fontSize: 12.5, color: "var(--txt-3)", textAlign: "center" }}>{pieza.duration_s} s</span> : null}

      {/* Fotos: tocar = marcar para quitar. */}
      <div style={{ display: "grid", gap: 6 }}>
        <b style={{ fontSize: 13.5 }}>Fotos (tocá las que no sirven)</b>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {pieza.sources.map((s) => {
            const marcada = quitarPos.includes(s.position);
            return (
              <button key={s.position} type="button" aria-pressed={marcada}
                      aria-label={`Foto ${s.position + 1}${s.caption_fact ? ` (${s.caption_fact})` : ""}${fotoMarcadaPorGemini(s.photo_flags) ? ", se ve un precio o un código" : ""}${marcada ? ", marcada para quitar" : ""}`}
                      onClick={() => setQuitarPos((q) => (marcada ? q.filter((x) => x !== s.position) : [...q, s.position]))}
                      style={{ position: "relative", width: 72, height: 72, padding: 0, borderRadius: 10, overflow: "hidden", cursor: "pointer",
                               border: `2px solid ${marcada ? "var(--pink)" : "var(--stroke)"}`, opacity: marcada ? 0.55 : 1 }}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={urlApiOpt(s.thumb_url) ?? ""} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} />
                <span style={{ position: "absolute", left: 3, top: 3, fontSize: 11, fontWeight: 700, background: "rgba(0,0,0,.65)", color: "#fff", borderRadius: 6, padding: "0 5px" }}>
                  {marcada ? "Quitar" : s.position + 1}
                </span>
                {fotoMarcadaPorGemini(s.photo_flags) && (
                  <span title="Se ve un precio o un código" aria-hidden="true"
                        style={{ position: "absolute", right: 3, bottom: 3, display: "inline-flex", background: "var(--amber)", color: "#000", borderRadius: 6, padding: 2 }}>
                    <Ic n="aviso" s={14} />
                  </span>
                )}
              </button>
            );
          })}
        </div>
        <div>
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => void rearmar()} disabled={ocupada || quitarPos.length === 0 || quitarPos.length > 6}>
            <Ic n="actualizar" s={15} /> {ocupado === "rearmar" ? "Rearmando…" : "Rearmar sin las marcadas"}
          </button>
        </div>
      </div>

      {/* Textos del video (plantillas v2, §16.10) */}
      {v2 && (
        <TextosDelVideo pieza={pieza} sinArmador={sinArmador} ocupadaAfuera={ocupada}
                        antesDeGuardar={guardarAntes} onCambio={onCambio} onSucio={setVideoSucio} />
      )}

      {/* Textos */}
      <div style={{ display: "grid", gap: 10 }}>
        {CAMPOS.map((c) => {
          const cont = contadorTexto(textos[c], CAPTION_MAX[c]);
          return (
            <label key={c} style={{ display: "grid", gap: 3, fontSize: 12.5 }}>
              <span style={{ display: "flex", justifyContent: "space-between", gap: 8, color: "var(--txt-3)" }}>
                <span>{CAPTION_LABEL[c]}</span>
                <span style={{ color: cont.pasado ? "var(--pink)" : undefined, fontWeight: cont.pasado ? 700 : 400 }}>
                  {cont.texto}{cont.pasado ? " · se pasó" : ""}
                </span>
              </span>
              <textarea className="adm-input" rows={c === "caption_ig" ? 5 : 3} value={textos[c]}
                        onChange={(e) => setTextos((t) => ({ ...t, [c]: e.target.value }))} />
            </label>
          );
        })}

        <div style={{ display: "grid", gap: 6 }}>
          <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>Hashtags</span>
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {hashtags.map((h) => (
              <button key={h} type="button" className="chip" style={{ ...BTN_GRANDE, cursor: "pointer", fontSize: 13 }}
                      aria-label={`Quitar ${h}`} onClick={() => setHashtags((x) => x.filter((y) => y !== h))}>
                {normalizarHashtag(h)} <Ic n="cerrar" s={12} />
              </button>
            ))}
            {disponibles.map((h) => (
              <button key={h} type="button" className="chip" style={{ ...BTN_GRANDE, cursor: "pointer", fontSize: 13, opacity: 0.8 }}
                      aria-label={`Agregar ${h}`} onClick={() => setHashtags((x) => [...x, h])}>
                <Ic n="mas" s={12} /> {normalizarHashtag(h)}
              </button>
            ))}
          </div>
        </div>

        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          {pieza.caption_checks.length === 0
            ? <Insignia tono="ok" icono="listo">Validador: en verde</Insignia>
            : <Insignia tono="aviso" icono="aviso">Validador: {pieza.caption_checks.length === 1 ? "1 objeción" : `${pieza.caption_checks.length} objeciones`}</Insignia>}
          <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>Textos: {motor}</span>
        </div>
        {pieza.caption_checks.length > 0 && (
          <ul style={{ margin: 0, paddingLeft: 18, fontSize: 12.5, color: "var(--amber)" }}>
            {pieza.caption_checks.map((o, i) => <li key={i}>{o}</li>)}
          </ul>
        )}

        {sucio && (
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} onClick={() => void guardar()} disabled={ocupada || pasado}>
              <Ic n="si" s={15} /> {ocupado === "guardar" ? "Guardando…" : "Guardar textos"}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={ocupada}
                    onClick={() => { setTextos(original); setHashtags(pieza.hashtags); setErrTextos(""); }}>
              Descartar cambios
            </button>
          </div>
        )}
        {errTextos && <Aviso tono="error">{errTextos}</Aviso>}
      </div>

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary" style={{ ...BTN_GRANDE, flex: "1 1 160px" }} onClick={() => void aprobar()}
                disabled={ocupada || sinGuardar || noAprobable !== null}
                title={sinGuardar ? "Guardá los cambios antes de aprobar" : (noAprobable ?? undefined)}>
          <Ic n="listo" s={18} /> {ocupado === "aprobar" ? "Aprobando…" : sinGuardar ? "Guardá los cambios para aprobar" : "Aprobar"}
        </button>
        <button type="button" className="btn btn-ghost" style={{ ...BTN_GRANDE, flex: "1 1 120px" }} onClick={() => setSaltando((s) => !s)} disabled={ocupada}>
          <Ic n="seguir" s={18} /> Saltar
        </button>
      </div>

      {/* El motivo de por qué no se aprueba (o el 409 del backend) va pegado al botón. */}
      {noAprobable && !err && <Aviso tono="aviso">{noAprobable}</Aviso>}
      {err && <Aviso tono="error">{err}</Aviso>}

      {saltando && (
        <div style={{ display: "grid", gap: 8, padding: 10, border: "1px solid var(--stroke)", borderRadius: 10 }}>
          <label style={{ display: "grid", gap: 3, fontSize: 12.5 }}>
            <span style={{ color: "var(--txt-3)" }}>Motivo</span>
            <select className="adm-input" style={{ minHeight: 48 }} value={motivo} onChange={(e) => setMotivo(e.target.value as ContentPieceSkip["reason"])}>
              {(["bad_photos", "merchant_asked", "other"] as const).map((m) => <option key={m} value={m}>{SKIP_REASON_LABEL[m]}</option>)}
            </select>
          </label>
          <label style={{ display: "grid", gap: 3, fontSize: 12.5 }}>
            <span style={{ color: "var(--txt-3)" }}>Nota (opcional)</span>
            <input className="adm-input" maxLength={300} style={{ minHeight: 48 }} value={nota} onChange={(e) => setNota(e.target.value)} />
          </label>
          <div>
            <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} onClick={() => void saltar()} disabled={ocupada}>
              {ocupado === "saltar" ? "Saltando…" : "Confirmar: saltar esta pieza"}
            </button>
          </div>
        </div>
      )}
    </article>
  );
}

/* ─── Una pieza con problemas ────────────────────────────────────────────── */

function PiezaConProblemas({ pieza, sinArmador, onCambio, onSaltada }: {
  pieza: ContentPieceResponse;
  sinArmador?: boolean;
  onCambio: (p: ContentPieceResponse) => void;
  onSaltada: (p: ContentPieceResponse) => void;
}) {
  const [ocupado, setOcupado] = useState(false);
  const [err, setErr] = useState("");
  const [corrigiendo, setCorrigiendo] = useState(false);

  async function reintentar() {
    setOcupado(true); setErr("");
    try { onCambio(await reintentarPieza(pieza.id)); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo reintentar")); setOcupado(false); }
  }
  async function saltar() {
    if (!window.confirm("¿Saltar esta pieza? No se publica.")) return;
    setOcupado(true); setErr("");
    try { onSaltada(await saltarPieza(pieza.id, { reason: "bad_photos", note: pieza.render_error ? pieza.render_error.slice(0, 280) : null })); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo saltar la pieza")); setOcupado(false); }
  }

  return (
    <article className="panel-card glass" style={{ padding: 14, display: "grid", gap: 8, border: "1px solid var(--pink)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <Insignia tono="error" icono="aviso">CON PROBLEMAS</Insignia>
        <b style={{ fontSize: 14.5 }}>{fechaConDia(pieza.scheduled_for)} · {pieza.comercio?.nombre ?? pieza.pillar_label}</b>
      </div>
      <p style={{ margin: 0, fontSize: 13.5, color: "var(--txt-2)", lineHeight: 1.45 }}>
        {pieza.render_error ? pieza.render_error : "El servidor no pudo armar el video."}
      </p>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} onClick={() => void reintentar()} disabled={ocupado}>
          <Ic n="actualizar" s={15} /> {ocupado ? "Un momento…" : "Reintentar"}
        </button>
        {esPiezaV2(pieza) && (
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} aria-expanded={corrigiendo}
                  onClick={() => setCorrigiendo((c) => !c)} disabled={ocupado}>
            <Ic n="editar" s={15} /> {corrigiendo ? "Cerrar los textos del video" : "Corregir los textos del video"}
          </button>
        )}
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => void saltar()} disabled={ocupado}>Saltar</button>
      </div>
      {err && <Aviso tono="error">{err}</Aviso>}
      {corrigiendo && esPiezaV2(pieza) && (
        <TextosDelVideo pieza={pieza} sinArmador={sinArmador} ocupadaAfuera={ocupado} onCambio={onCambio} />
      )}
    </article>
  );
}
