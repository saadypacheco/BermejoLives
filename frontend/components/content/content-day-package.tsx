"use client";

import { useCallback, useEffect, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Cargando, ErrorConReintento, Insignia } from "@/components/content/content-ui";
import { ContentPostRow } from "@/components/content/content-post-row";
import {
  getPaqueteDelDia, mensajeContent, type ContentDayItem, type ContentDayPackageResponse, type ContentPostResponse,
} from "@/lib/content";
import { cerrarTarea } from "@/lib/subscribers";
import { ENTREGA_A_MANO, EntregaDescarga } from "@/components/subscribers/entrega-a-mano";
import { detalleDePieza, esPiezaPedida, fechaConDia, hoyBolivia, sumarDias, tituloDePieza, urlApiOpt } from "@/lib/content-pure";

/**
 * Admin › Contenido para redes › Paquete del día (§9.3): lo que hay para publicar
 * hoy, red por red, con «Atrasadas» (aprobadas de días anteriores con redes
 * pendientes) y lo que todavía falta aprobar. Se usa desde el celular o la PC; todos
 * leen la misma fila, así dos personas no publican lo mismo.
 */
export function ContentDayPackage({ onIrARevision }: { onIrARevision: () => void }) {
  const [fecha, setFecha] = useState(hoyBolivia());
  const [data, setData] = useState<ContentDayPackageResponse | null>(null);
  const [cargando, setCargando] = useState(true);
  const [err, setErr] = useState("");

  const cargar = useCallback(async (f: string, silencioso = false) => {
    if (!silencioso) setCargando(true);
    setErr("");
    try { setData(await getPaqueteDelDia(f)); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo cargar el paquete del día")); }
    finally { setCargando(false); }
  }, []);

  useEffect(() => { void cargar(fecha); }, [fecha, cargar]);

  /** Una red cambió: se refleja ya, sin recargar todo (y sin perder lo que la
   *  persona estaba haciendo en las otras redes). */
  function postCambio(pieceId: string, p: ContentPostResponse) {
    setData((d) => {
      if (!d) return d;
      const mapa = (it: ContentDayItem): ContentDayItem =>
        it.piece.id === pieceId ? { ...it, posts: it.posts.map((x) => (x.id === p.id ? p : x)) } : it;
      return { ...d, items: d.items.map(mapa), overdue: d.overdue.map(mapa) };
    });
    // Si fue la última red, la pieza pasa a «publicada» y le nace la tarea de entrega:
    // se vuelve a pedir el paquete para traer `delivery`.
    if (p.status === "posted" || p.status === "skipped") void cargar(fecha, true);
  }

  const esHoy = fecha === hoyBolivia();

  return (
    <div style={{ display: "grid", gap: 14 }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} aria-label="Día anterior" onClick={() => setFecha(sumarDias(fecha, -1))}>
          <Ic n="volver" s={15} />
        </button>
        <b style={{ fontSize: 15 }}>{esHoy ? "Hoy · " : ""}{fechaConDia(fecha)}</b>
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} aria-label="Día siguiente" onClick={() => setFecha(sumarDias(fecha, 1))}>
          <Ic n="seguir" s={15} />
        </button>
        {!esHoy && <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => setFecha(hoyBolivia())}>Ir a hoy</button>}
        <button type="button" className="btn btn-ghost btn-sm" style={{ ...BTN_GRANDE, marginLeft: "auto" }} onClick={() => void cargar(fecha)} disabled={cargando}>
          <Ic n="actualizar" s={15} /> Actualizar
        </button>
      </div>

      {cargando && !data && <Cargando texto="Cargando el paquete del día…" />}
      {err && <ErrorConReintento mensaje={err} onReintentar={() => void cargar(fecha)} />}

      {data && data.pending_review.length > 0 && (
        <Aviso tono="aviso" accion={<button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={onIrARevision}>Ir a Revisión</button>}>
          Falta aprobar {data.pending_review.length === 1 ? "1 pieza" : `${data.pending_review.length} piezas`} de este día:{" "}
          {data.pending_review.map((p) => detalleDePieza(p)).join(", ")}.
        </Aviso>
      )}

      {data && data.overdue.length > 0 && (
        <section aria-labelledby="dp-atras" style={{ display: "grid", gap: 10 }}>
          <h3 id="dp-atras" style={{ margin: 0, fontSize: 15, display: "flex", gap: 6, alignItems: "center" }}>
            <Ic n="aviso" s={16} /> Atrasadas
          </h3>
          {data.overdue.map((it) => <TarjetaPieza key={it.piece.id} it={it} atrasada onPost={postCambio} onEntregada={() => void cargar(fecha, true)} />)}
        </section>
      )}

      {data && data.items.map((it) => <TarjetaPieza key={it.piece.id} it={it} onPost={postCambio} onEntregada={() => void cargar(fecha, true)} />)}

      {data && !cargando && !err && data.items.length === 0 && data.overdue.length === 0 && data.pending_review.length === 0 && (
        <p style={{ margin: 0, fontSize: 14, color: "var(--txt-3)", lineHeight: 1.5 }}>
          {esHoy ? "Hoy" : "Ese día"} no hay piezas.
          {data.next ? ` La próxima: ${fechaConDia(data.next.date)}, ${data.next.pillar_label}.` : ""}
        </p>
      )}
    </div>
  );
}

function TarjetaPieza({ it, atrasada, onPost, onEntregada }: {
  it: ContentDayItem; atrasada?: boolean;
  onPost: (pieceId: string, p: ContentPostResponse) => void;
  onEntregada: () => void;
}) {
  const { piece } = it;
  const portada = urlApiOpt(piece.cover_url);
  return (
    <article className="panel-card glass" style={{ padding: 14, display: "grid", gap: 8 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "flex-start" }}>
        {portada && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={portada} alt="Portada del video" style={{ width: 54, height: 96, objectFit: "cover", borderRadius: 8, flex: "none", background: "var(--panel)" }} />
        )}
        <div style={{ display: "grid", gap: 4, minWidth: 0 }}>
          <b style={{ fontSize: 15 }}>{tituloDePieza(piece)}</b>
          <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>
            {fechaConDia(piece.scheduled_for)}{piece.ciudad_nombre ? ` · ${piece.ciudad_nombre}` : ""}{piece.duration_s ? ` · ${piece.duration_s} s` : ""}
          </span>
          <span style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {esPiezaPedida(piece.origin) && <Insignia tono="info" icono="encargo">Pedido</Insignia>}
            {piece.counts_for_quota && <Insignia tono="ok" icono="estrella">Suscriptor</Insignia>}
            {atrasada && <Insignia tono="aviso" icono="aviso">Atrasada</Insignia>}
          </span>
        </div>
      </div>

      <div>
        {it.posts.map((p) => <ContentPostRow key={p.id} post={p} pieceId={piece.id} onCambio={(np) => onPost(piece.id, np)} />)}
        {it.posts.length === 0 && <p style={{ margin: 0, fontSize: 13, color: "var(--txt-3)" }}>Esta pieza no tiene redes para publicar.</p>}
      </div>

      {it.delivery && <EntregaPieza delivery={it.delivery} onEntregada={onEntregada} />}
    </article>
  );
}

/** El video de un suscriptor se entrega A MANO (§15): se baja y se marca entregado. Sin WhatsApp. */
function EntregaPieza({ delivery, onEntregada }: { delivery: NonNullable<ContentDayItem["delivery"]>; onEntregada: () => void }) {
  const [ocupado, setOcupado] = useState(false);
  const [err, setErr] = useState("");
  async function marcar() {
    setOcupado(true); setErr("");
    try { await cerrarTarea(delivery.task_id, true, null); onEntregada(); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo marcar como entregado")); }
    finally { setOcupado(false); }
  }
  return (
    <div style={{ borderTop: "1px solid var(--stroke)", paddingTop: 10, display: "grid", gap: 8 }}>
      <b style={{ fontSize: 13.5 }}>{ENTREGA_A_MANO}</b>
      <EntregaDescarga downloadUrl={delivery.download_url} />
      <div>
        <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} disabled={ocupado} onClick={() => void marcar()}>
          <Ic n="si" s={15} /> {ocupado ? "Guardando…" : "Marcar entregado"}
        </button>
      </div>
      {err && <Aviso tono="error">{err}</Aviso>}
    </div>
  );
}
