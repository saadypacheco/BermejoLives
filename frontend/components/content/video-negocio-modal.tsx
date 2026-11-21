"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Cargando, ErrorConReintento, SinConexion, useOnline } from "@/components/content/content-ui";
import { BancoDelComercio } from "@/components/content/content-bank-panel";
import {
  apiBancoAdmin, chequeoDePedido, mensajeContent, pedirVideo,
  type ContentMerchantResponse, type RequestCheck,
} from "@/lib/content";
import { faseVideoNegocio } from "@/lib/content-pure";

type Chequeo = RequestCheck & { merchant?: ContentMerchantResponse };

/**
 * El botón «Video» de cada negocio en Admin › Comercios (docs/contenido-redes-tecnico.md §17.3).
 *
 * Es el mismo pedido que «Pedir un video» de Contenido para redes, pero con el negocio ya elegido y
 * con lo que falta resuelto AHÍ MISMO: si no tiene la autorización o le faltan fotos, abajo aparece su
 * Banco de contenido (autorización + subida) y «Revisar de nuevo». Si ya tiene un video armándose o
 * listo, lo dice y lleva a Revisión en vez de pedir otro igual.
 *
 * La autorización se sigue pidiendo siempre: es lo que cubre a URUKU si un negocio reclama.
 */
export function VideoNegocioModal({ comercio, onCerrar, onIrARevision }: {
  comercio: { id: string; nombre: string };
  onCerrar: () => void;
  /** Lleva a Admin › Contenido para redes (Revisión), donde se ve, se corrige, se aprueba y se descarga. */
  onIrARevision: () => void;
}) {
  const online = useOnline();
  const caja = useRef<HTMLDivElement>(null);
  const vez = useRef(0);
  const [chequeo, setChequeo] = useState<Chequeo | null>(null);
  const [cargando, setCargando] = useState(true);
  const [errChequeo, setErrChequeo] = useState("");
  const [pidiendo, setPidiendo] = useState(false);
  const [errPedido, setErrPedido] = useState("");
  // Con un video que ya existe, «Armar otro» muestra igual el botón de pedir.
  const [otro, setOtro] = useState(false);
  // Ya se pidió en esta ventana: el botón no vuelve aunque la relectura falle (si no, un segundo toque duplica).
  const [pedido, setPedido] = useState(false);

  // Escape cierra, el fondo no scrollea y el foco entra a la hoja (igual que «Pedir un video»).
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") onCerrar(); };
    document.addEventListener("keydown", alTeclear);
    const previo = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    caja.current?.focus();
    return () => { document.removeEventListener("keydown", alTeclear); document.body.style.overflow = previo; };
  }, [onCerrar]);

  const revisar = useCallback(async () => {
    const n = ++vez.current;
    setCargando(true); setErrChequeo("");
    try {
      const r = await chequeoDePedido(comercio.id);
      if (n === vez.current) { setChequeo(r); setOtro(false); }
    } catch (ex) {
      if (n === vez.current) setErrChequeo(mensajeContent(ex, "No se pudo revisar el negocio"));
    } finally {
      if (n === vez.current) setCargando(false);
    }
  }, [comercio.id]);

  useEffect(() => { void revisar(); }, [revisar]);

  async function pedir() {
    if (pidiendo) return;
    setPidiendo(true); setErrPedido("");
    try {
      await pedirVideo({ kind: "comercio", comercio_id: comercio.id });
      setPedido(true);
      await revisar();          // pasa a «se está armando»
    } catch (ex) {
      setErrPedido(mensajeContent(ex, "No se pudo pedir el video"));
    } finally {
      setPidiendo(false);
    }
  }

  const fase = chequeo ? faseVideoNegocio(chequeo) : null;
  const tono = !fase ? "info"
    : fase.fase === "puede" || fase.fase === "listo" ? "ok"
    : fase.fase === "armando" ? "info"
    : fase.fase === "faltan_fotos" || fase.fase === "falta_autorizacion" ? "aviso" : "error";
  const estadoPrevio = chequeo?.last_piece?.status;
  const conVideoViejo = fase?.fase === "listo";
  const mostrarPedir = !pedido && (fase?.fase === "puede" || (conVideoViejo && otro && chequeo?.ok));
  // Revisión tiene lo que se arma y lo que espera revisión; lo aprobado está en «Paquete del día».
  // Lo publicado ya no tiene nada que hacer en el panel.
  const irAlPanel = fase?.fase === "armando" || estadoPrevio === "ready_for_review"
    || estadoPrevio === "approved" || estadoPrevio === "failed";
  const mostrarBanco = fase?.fase === "falta_autorizacion" || fase?.fase === "faltan_fotos";
  const m = chequeo?.merchant;

  return (
    <div onClick={onCerrar}
         style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,.6)", display: "flex",
                  alignItems: "flex-end", justifyContent: "center" }}>
      <div ref={caja} role="dialog" aria-modal="true" aria-label={`Video de ${comercio.nombre}`} tabIndex={-1}
           onClick={(e) => e.stopPropagation()}
           style={{ background: "var(--bg)", color: "var(--txt)", width: "100%", maxWidth: 640, maxHeight: "92dvh", overflowY: "auto",
                    borderRadius: "18px 18px 0 0", border: "1px solid var(--stroke-2)", padding: "16px 16px calc(20px + env(safe-area-inset-bottom, 0px))",
                    display: "grid", gap: 14, alignContent: "start", outline: "none" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <h3 style={{ margin: 0, fontSize: 18, display: "flex", alignItems: "center", gap: 8 }}>
            <Ic n="video" s={18} /> Video de {comercio.nombre || "este negocio"}
          </h3>
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={onCerrar}>
            <Ic n="cerrar" s={15} /> Cerrar
          </button>
        </div>

        <SinConexion />
        {cargando && !chequeo && <Cargando texto="Revisando autorización, fotos y videos…" />}
        {errChequeo && <ErrorConReintento mensaje={errChequeo} onReintentar={() => void revisar()} />}
        {fase && <Aviso tono={tono}>{fase.texto}</Aviso>}
        {errPedido && <Aviso tono="error">{errPedido}</Aviso>}
        {pedido && fase?.fase !== "armando" && <Aviso tono="ok">Video pedido: se está armando.</Aviso>}

        {fase && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {mostrarPedir && (
              <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE}
                      disabled={pidiendo || !online} onClick={() => void pedir()}>
                <Ic n="video" s={15} /> {pidiendo ? "Pidiendo…" : "Generar el video"}
              </button>
            )}
            {irAlPanel && (
              <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} onClick={onIrARevision}>
                <Ic n="listo" s={15} /> Ir a Contenido para redes
              </button>
            )}
            {conVideoViejo && chequeo?.ok && !otro && !pedido && (
              <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => setOtro(true)}>
                <Ic n="mas" s={15} /> Armar otro
              </button>
            )}
            {(mostrarBanco || fase.fase === "armando" || pedido) && (
              <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE}
                      disabled={cargando} onClick={() => void revisar()}>
                <Ic n="reloj" s={15} /> {cargando ? "Revisando…" : "Revisar de nuevo"}
              </button>
            )}
          </div>
        )}

        {fase?.fase === "armando" && (
          <p style={{ margin: 0, fontSize: 12.5, color: "var(--txt-3)", lineHeight: 1.45 }}>
            En Contenido para redes › Revisión se corrigen los textos, se aprueba y se descarga para subirlo a las redes de URUKU.
          </p>
        )}

        {/* Lo que falta, acá mismo: la autorización y la subida de fotos del Banco de contenido. */}
        {mostrarBanco && m && (
          <div className="panel-card glass" style={{ padding: 14 }}>
            <BancoDelComercio
              key={m.id}
              comercioId={m.id} api={apiBancoAdmin}
              titulo={m.nombre}
              detalle={[m.rubro, m.calle, m.ciudad_nombre].filter(Boolean).join(" · ")}
              suscriptor={m.is_subscriber}
              consentInicial={m.social_consent}
              fotosEnFicha={m.gallery_photos} />
          </div>
        )}
        {mostrarBanco && chequeo && !m && (
          <Aviso tono="info">Cargá la autorización y las fotos en Admin › Banco de contenido y después tocá «Revisar de nuevo».</Aviso>
        )}
      </div>
    </div>
  );
}
