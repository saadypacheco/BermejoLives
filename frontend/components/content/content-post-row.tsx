"use client";

import { useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BotonCopiar, BTN_GRANDE, Insignia } from "@/components/content/content-ui";
import {
  linksDeDescarga, marcarPublicada, mensajeContent, miIdentidad, reclamarPost, saltarPost, soltarPost,
  type ContentPostResponse,
} from "@/lib/content";
import {
  horaBo, minutosDesde, minutosRestantes, redLabel, urlApi, validarLinkDeRed, POST_STATUS_LABEL, SKIP_REASON_LABEL,
} from "@/lib/content-pure";

/** Agrega `download=1` a una URL firmada (va FUERA de la firma, §4.2): el
 *  navegador la baja en vez de abrirla. */
function paraDescargar(rel: string): string {
  const u = new URL(urlApi(rel));
  u.searchParams.set("download", "1");
  return u.toString();
}

/** Baja un archivo con la descarga NATIVA del navegador (sin cargarlo como blob:
 *  un video de 10 MB en memoria en un celular chico es pedir problemas). */
function bajar(url: string) {
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
}

/**
 * Una red de una pieza en el Paquete del día (modo B: la publica una PERSONA).
 *
 *   pendiente  →  [Copiar texto] [Voy a publicar]          (reclama la red)
 *   reclamada por mí  →  descargar video y portada, copiar texto, y avisar si
 *                        salió: [Pegar link] [Salió sin link] [No salió] [Saltar]
 *   reclamada por otra persona  →  sólo lectura, con su nombre y hace cuánto
 *   publicada  →  hora y link
 *
 * El reclamo dura 20 minutos: así dos personas no publican lo mismo.
 */
export function ContentPostRow({ post, pieceId, onCambio }: {
  post: ContentPostResponse;
  pieceId: string;
  onCambio: (p: ContentPostResponse) => void;
}) {
  const [mio, setMio] = useState(false);     // lo reclamé en esta pantalla
  const [modo, setModo] = useState<"" | "link" | "saltar">("");
  const [link, setLink] = useState("");
  const [motivo, setMotivo] = useState("");
  const [ocupado, setOcupado] = useState(false);
  const [err, setErr] = useState("");
  const [bajando, setBajando] = useState(false);

  const yo = miIdentidad();
  const claimedBy = (post.claimed_by ?? "").toLowerCase();
  const esMia = post.status === "claimed" && (
    mio || (!!claimedBy && (claimedBy === (yo.email ?? "").toLowerCase() || claimedBy === (yo.nombre ?? "").toLowerCase()))
  );
  const red = post.network_label || redLabel(post.network);

  async function correr(fn: () => Promise<ContentPostResponse>, tras?: (p: ContentPostResponse) => void) {
    setOcupado(true); setErr("");
    try {
      const p = await fn();
      onCambio(p);
      tras?.(p);
    } catch (ex) { setErr(mensajeContent(ex)); }
    finally { setOcupado(false); }
  }

  const reclamar = () => correr(() => reclamarPost(post.id), () => setMio(true));
  const soltar = () => correr(() => soltarPost(post.id), () => { setMio(false); setModo(""); });

  async function descargar(que: "video" | "portada") {
    setBajando(true); setErr("");
    try {
      const l = await linksDeDescarga(pieceId);
      bajar(que === "video" ? urlApi(l.video_download_url) : paraDescargar(l.cover_url));
    } catch (ex) { setErr(mensajeContent(ex, "No se pudo preparar la descarga")); }
    finally { setBajando(false); }
  }

  function guardarLink() {
    const v = validarLinkDeRed(post.network, link);
    if (!v.ok) { setErr(v.motivo); return; }
    void correr(() => marcarPublicada(post.id, v.url, false), () => { setModo(""); setLink(""); });
  }

  function sinLink() {
    if (!window.confirm(`¿Confirmás que salió en ${red} pero no tenés el link?`)) return;
    void correr(() => marcarPublicada(post.id, null, true));
  }

  function saltar() {
    const m = motivo.trim();
    if (!m) { setErr("Contá por qué se saltea esta red"); return; }
    if (!window.confirm(`¿Saltar ${red} para esta pieza? No se va a publicar ahí.`)) return;
    void correr(() => saltarPost(post.id, m.slice(0, 200)), () => { setModo(""); setMotivo(""); });
  }

  return (
    <div style={{ display: "grid", gap: 8, padding: "10px 0", borderTop: "1px solid var(--stroke)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <b style={{ minWidth: 92, fontSize: 14 }}>{red}</b>

        {post.status === "pending" && <Insignia icono="reloj" tono="info">{POST_STATUS_LABEL.pending.toUpperCase()}</Insignia>}
        {post.status === "claimed" && (
          <Insignia icono="usuario" tono="aviso">
            PUBLICANDO · {esMia ? "vos" : (post.claimed_by_name ?? "alguien")} · hace {minutosDesde(post.claimed_at)} min
          </Insignia>
        )}
        {post.status === "posted" && (
          <Insignia icono="listo" tono="ok">PUBLICADA {horaBo(post.posted_at)}</Insignia>
        )}
        {post.status === "skipped" && <Insignia icono="cerrar" tono="info">SALTADA</Insignia>}

        {post.status === "posted" && post.post_url && /^https:\/\//.test(post.post_url) && (
          <a href={post.post_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 13, display: "inline-flex", alignItems: "center", gap: 4, minHeight: 44 }}>
            <Ic n="abrir" s={14} /> abrir el link
          </a>
        )}
        {post.status === "posted" && !post.post_url && post.posted_without_link && (
          <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>sin link</span>
        )}
        {post.status === "skipped" && post.skip_reason && <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>{SKIP_REASON_LABEL[post.skip_reason] ?? post.skip_reason}</span>}
      </div>

      {post.status === "pending" && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          <BotonCopiar texto={post.caption_text} />
          <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} onClick={() => void reclamar()} disabled={ocupado}>
            <Ic n="enviar" s={15} /> {ocupado ? "Reclamando…" : "Voy a publicar"}
          </button>
        </div>
      )}

      {post.status === "claimed" && !esMia && (
        <p style={{ margin: 0, fontSize: 12.5, color: "var(--txt-3)" }}>
          La está publicando otra persona. Si pasan {minutosRestantes(post.claim_expires_at)} min sin que la marque, se libera sola.
          Revisá en la red si salió antes de reintentar.
        </p>
      )}

      {post.status === "claimed" && esMia && (
        <div style={{ display: "grid", gap: 8 }}>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={bajando} onClick={() => void descargar("video")}>
              <Ic n="descargar" s={15} /> {bajando ? "Preparando…" : "Descargar video"}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={bajando} onClick={() => void descargar("portada")}>
              <Ic n="foto" s={15} /> Descargar portada
            </button>
            <BotonCopiar texto={post.caption_text} />
          </div>
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <b style={{ fontSize: 13.5 }}>¿Salió?</b>
            <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} onClick={() => { setModo("link"); setErr(""); }} disabled={ocupado}>
              <Ic n="enlace" s={15} /> Pegar link
            </button>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={sinLink} disabled={ocupado}>Salió sin link</button>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => void soltar()} disabled={ocupado}>No salió</button>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => { setModo("saltar"); setErr(""); }} disabled={ocupado}>Saltar esta red</button>
          </div>

          {modo === "link" && (
            <form onSubmit={(e) => { e.preventDefault(); guardarLink(); }} style={{ display: "grid", gap: 6 }}>
              <label style={{ display: "grid", gap: 3, fontSize: 12.5 }}>
                <span style={{ color: "var(--txt-3)" }}>Link del posteo en {red}</span>
                <input className="adm-input" type="url" inputMode="url" autoComplete="off" style={{ minHeight: 48 }}
                       value={link} onChange={(e) => setLink(e.target.value)} placeholder="https://…" />
              </label>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="submit" className="btn btn-primary btn-sm" style={BTN_GRANDE} disabled={ocupado}>
                  <Ic n="si" s={15} /> {ocupado ? "Guardando…" : "Marcar como publicada"}
                </button>
                <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => { setModo(""); setErr(""); }}>Cancelar</button>
              </div>
            </form>
          )}

          {modo === "saltar" && (
            <form onSubmit={(e) => { e.preventDefault(); saltar(); }} style={{ display: "grid", gap: 6 }}>
              <label style={{ display: "grid", gap: 3, fontSize: 12.5 }}>
                <span style={{ color: "var(--txt-3)" }}>¿Por qué se saltea esta red?</span>
                <input className="adm-input" maxLength={200} style={{ minHeight: 48 }} value={motivo} onChange={(e) => setMotivo(e.target.value)}
                       placeholder="Ej: no hay cuenta de Facebook" />
              </label>
              <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
                <button type="submit" className="btn btn-primary btn-sm" style={BTN_GRANDE} disabled={ocupado}>Saltar {red}</button>
                <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => { setModo(""); setErr(""); }}>Cancelar</button>
              </div>
            </form>
          )}
        </div>
      )}

      {err && <Aviso tono="error">{err}</Aviso>}
    </div>
  );
}
