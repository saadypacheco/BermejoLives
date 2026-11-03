"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { useAdminCiudad, nombreCiudad } from "@/components/admin-ciudad";
import { Aviso, BTN_GRANDE, Cargando, ErrorConReintento, Insignia, SinConexion, useOnline } from "@/components/content/content-ui";
import { ContentMerchantPicker } from "@/components/content/content-merchant-picker";
import { miCiudad } from "@/lib/api";
import {
  chequeoDePedido, mensajeContent, opcionesDePedido, pedirVideo,
  type ContentMerchantResponse, type RequestCheck, type RubroOpcion,
} from "@/lib/content";
import { armarPedidoDeVideo, opcionDeRubro, resumenRequestCheck } from "@/lib/content-pure";

type Modo = "comercio" | "rubro";

/**
 * «Pedir un video» (§17.4): una hoja que se abre sobre el panel con dos opciones.
 *  · Un negocio: se busca por código URUKU-XXXX o por nombre; ANTES de pedir se
 *    muestra si tiene autorización y cuántas fotos sirven.
 *  · Un rubro: una ciudad y uno de sus rubros (se deshabilita el que no llega a 4
 *    comercios con autorización y foto).
 * El 422/429 del backend se muestra tal cual. En el celular sube desde abajo y
 * ocupa todo el ancho; en la compu es una caja centrada.
 */
export function ContentRequestModal({ onCerrar, onPedido }: { onCerrar: () => void; onPedido: () => void }) {
  const [modo, setModo] = useState<Modo>("comercio");
  const [listo, setListo] = useState(false);          // ya se pidió: se muestra el «Listo»
  const online = useOnline();
  const caja = useRef<HTMLDivElement>(null);

  // Escape cierra, el fondo no scrollea y el foco entra a la hoja.
  useEffect(() => {
    const alTeclear = (e: KeyboardEvent) => { if (e.key === "Escape") onCerrar(); };
    document.addEventListener("keydown", alTeclear);
    const previo = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    caja.current?.focus();
    return () => { document.removeEventListener("keydown", alTeclear); document.body.style.overflow = previo; };
  }, [onCerrar]);

  const alPedir = useCallback(() => { setListo(true); onPedido(); }, [onPedido]);

  return (
    <div onClick={onCerrar}
         style={{ position: "fixed", inset: 0, zIndex: 1000, background: "rgba(0,0,0,.6)", display: "flex",
                  alignItems: "flex-end", justifyContent: "center" }}>
      <div ref={caja} role="dialog" aria-modal="true" aria-label="Pedir un video" tabIndex={-1} onClick={(e) => e.stopPropagation()}
           style={{ background: "var(--bg)", color: "var(--txt)", width: "100%", maxWidth: 560, maxHeight: "92dvh", overflowY: "auto",
                    borderRadius: "18px 18px 0 0", border: "1px solid var(--stroke-2)", padding: "16px 16px calc(20px + env(safe-area-inset-bottom, 0px))",
                    display: "grid", gap: 14, alignContent: "start", outline: "none" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
          <h3 style={{ margin: 0, fontSize: 18 }}>Pedir un video</h3>
          <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={onCerrar}>
            <Ic n="cerrar" s={15} /> Cerrar
          </button>
        </div>

        <SinConexion />

        {listo ? (
          <div style={{ display: "grid", gap: 12 }}>
            <Aviso tono="ok">Listo: el video se está armando, aparece en Revisión en unos minutos.</Aviso>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} onClick={onCerrar}>Cerrar</button>
              <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => setListo(false)}>
                <Ic n="mas" s={15} /> Pedir otro
              </button>
            </div>
          </div>
        ) : (
          <>
            <div role="tablist" aria-label="Qué video querés pedir" style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <button type="button" role="tab" aria-selected={modo === "comercio"} onClick={() => setModo("comercio")}
                      className={`btn btn-sm ${modo === "comercio" ? "btn-primary" : "btn-ghost"}`} style={BTN_GRANDE}>
                <Ic n="comercios" s={15} /> Un negocio
              </button>
              <button type="button" role="tab" aria-selected={modo === "rubro"} onClick={() => setModo("rubro")}
                      className={`btn btn-sm ${modo === "rubro" ? "btn-primary" : "btn-ghost"}`} style={BTN_GRANDE}>
                <Ic n="catalogo" s={15} /> Un rubro
              </button>
            </div>
            {modo === "comercio"
              ? <PedirDeNegocio online={online} onPedido={alPedir} />
              : <PedirDeRubro online={online} onPedido={alPedir} />}
          </>
        )}
      </div>
    </div>
  );
}

/** El botón de pedir con su error (422/429 tal cual) y su «Pidiendo…». */
function usePedido(onPedido: () => void) {
  const [pidiendo, setPidiendo] = useState(false);
  const [err, setErr] = useState("");
  const pedir = useCallback(async (body: Parameters<typeof pedirVideo>[0] | null) => {
    if (!body || pidiendo) return;
    setPidiendo(true); setErr("");
    try { await pedirVideo(body); onPedido(); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudo pedir el video")); }
    finally { setPidiendo(false); }
  }, [pidiendo, onPedido]);
  return { pidiendo, err, pedir, limpiar: () => setErr("") };
}

function PedirDeNegocio({ online, onPedido }: { online: boolean; onPedido: () => void }) {
  const [comercio, setComercio] = useState<ContentMerchantResponse | null>(null);
  const [chequeo, setChequeo] = useState<RequestCheck | null>(null);
  const [cargando, setCargando] = useState(false);
  const [errChequeo, setErrChequeo] = useState("");
  const { pidiendo, err, pedir, limpiar } = usePedido(onPedido);
  const vez = useRef(0);

  const revisar = useCallback(async (c: ContentMerchantResponse) => {
    const n = ++vez.current;
    setCargando(true); setErrChequeo(""); setChequeo(null);
    try {
      const r = await chequeoDePedido(c.id);
      if (n === vez.current) setChequeo(r);
    } catch (ex) {
      if (n === vez.current) setErrChequeo(mensajeContent(ex, "No se pudo revisar el comercio"));
    } finally {
      if (n === vez.current) setCargando(false);
    }
  }, []);

  function elegir(c: ContentMerchantResponse) { limpiar(); setComercio(c); void revisar(c); }
  function otro() { vez.current++; limpiar(); setComercio(null); setChequeo(null); setErrChequeo(""); setCargando(false); }

  if (!comercio) {
    return (
      <div style={{ display: "grid", gap: 8 }}>
        <p style={{ margin: 0, fontSize: 13, color: "var(--txt-3)", lineHeight: 1.45 }}>
          Buscá el negocio por su código (URUKU-XXXX) o por su nombre. Antes de pedir te mostramos si tiene autorización y fotos.
        </p>
        <ContentMerchantPicker onElegir={elegir} placeholder="Código URUKU-XXXX o nombre…" />
      </div>
    );
  }

  const resumen = chequeo ? resumenRequestCheck(chequeo) : null;
  const pedido = armarPedidoDeVideo("comercio", { comercioId: comercio.id });
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <div className="glass" style={{ padding: "10px 14px", borderRadius: 12, border: "1px solid var(--stroke)", display: "grid", gap: 2 }}>
        <b style={{ fontSize: 15 }}>{comercio.nombre}</b>
        <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>
          {[comercio.rubro, comercio.calle, comercio.ciudad_nombre].filter(Boolean).join(" · ")}
        </span>
      </div>

      {cargando && <Cargando texto="Revisando autorización y fotos…" />}
      {errChequeo && <ErrorConReintento mensaje={errChequeo} onReintentar={() => void revisar(comercio)} />}
      {resumen && <Aviso tono={resumen.tono}>{resumen.texto}</Aviso>}
      {err && <Aviso tono="error">{err}</Aviso>}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE}
                disabled={!chequeo?.ok || pidiendo || !online} onClick={() => void pedir(pedido)}>
          <Ic n="video" s={15} /> {pidiendo ? "Pidiendo…" : "Pedir el video"}
        </button>
        <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={otro} disabled={pidiendo}>
          <Ic n="volver" s={15} /> Elegir otro negocio
        </button>
      </div>
    </div>
  );
}

function PedirDeRubro({ online, onPedido }: { online: boolean; onPedido: () => void }) {
  const { ciudades, sinCiudades, slug: slugPanel } = useAdminCiudad();
  // Sólo las ciudades abiertas: un video de una ciudad sin comercios no tiene sentido.
  const abiertas = ciudades.filter((c) => c.activa);
  const [ciudad, setCiudad] = useState<string>(() => {
    const propia = slugPanel ?? miCiudad();
    return propia && abiertas.some((c) => c.slug === propia) ? propia : "";
  });
  const [rubros, setRubros] = useState<RubroOpcion[] | null>(null);
  const [cargando, setCargando] = useState(false);
  const [errRubros, setErrRubros] = useState("");
  const [rubro, setRubro] = useState("");
  const { pidiendo, err, pedir, limpiar } = usePedido(onPedido);
  const vez = useRef(0);

  const cargar = useCallback(async (c: string) => {
    const n = ++vez.current;
    setRubros(null); setRubro(""); setErrRubros("");
    if (!c) { setCargando(false); return; }
    setCargando(true);
    try {
      const r = await opcionesDePedido(c);
      if (n === vez.current) setRubros(r);
    } catch (ex) {
      if (n === vez.current) setErrRubros(mensajeContent(ex, "No se pudieron cargar los rubros"));
    } finally {
      if (n === vez.current) setCargando(false);
    }
  }, []);

  useEffect(() => { void cargar(ciudad); }, [ciudad, cargar]);

  const pedido = armarPedidoDeVideo("rubro", { ciudadSlug: ciudad, rubroSlug: rubro });
  const hayElegibles = !!rubros?.some((r) => r.eligible);
  return (
    <div style={{ display: "grid", gap: 12 }}>
      <p style={{ margin: 0, fontSize: 13, color: "var(--txt-3)", lineHeight: 1.45 }}>
        Un repaso con un comercio de cada lugar (de 4 a 6), por ejemplo «zapatillas en Bermejo». Sólo entran los que tienen autorización y una foto que sirve.
      </p>

      {sinCiudades && <Aviso tono="aviso">No se pudieron cargar las ciudades. Recargá el panel.</Aviso>}
      <label style={{ display: "grid", gap: 4, fontSize: 12.5 }}>
        <span style={{ color: "var(--txt-3)" }}>Ciudad</span>
        <select className="adm-input" style={{ minHeight: 48 }} value={ciudad}
                onChange={(e) => { limpiar(); setCiudad(e.target.value); }}>
          <option value="">Elegí una ciudad…</option>
          {abiertas.map((c) => <option key={c.slug} value={c.slug}>{nombreCiudad(c)}</option>)}
        </select>
      </label>

      {cargando && <Cargando texto="Cargando rubros…" />}
      {errRubros && <ErrorConReintento mensaje={errRubros} onReintentar={() => void cargar(ciudad)} />}
      {ciudad && rubros && rubros.length === 0 && (
        <p style={{ margin: 0, fontSize: 14, color: "var(--txt-3)" }}>Esa ciudad todavía no tiene rubros con comercios.</p>
      )}
      {rubros && rubros.length > 0 && !hayElegibles && (
        <Aviso tono="aviso">Ningún rubro de esa ciudad llega al mínimo de comercios con autorización y foto.</Aviso>
      )}

      {rubros && rubros.length > 0 && (
        <div role="radiogroup" aria-label="Rubro" style={{ display: "grid", gap: 8 }}>
          {rubros.map((r) => {
            const o = opcionDeRubro(r);
            const elegido = rubro === r.slug;
            return (
              <button key={r.slug} type="button" role="radio" aria-checked={elegido} disabled={o.deshabilitada}
                      onClick={() => { limpiar(); setRubro(r.slug); }} className="glass"
                      style={{ ...BTN_GRANDE, textAlign: "left", padding: "10px 14px", borderRadius: 12, color: "inherit",
                               cursor: o.deshabilitada ? "not-allowed" : "pointer", opacity: o.deshabilitada ? 0.6 : 1,
                               border: `1px solid ${elegido ? "var(--neon)" : "var(--stroke)"}`,
                               display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, flexWrap: "wrap" }}>
                <span style={{ display: "grid", gap: 2 }}>
                  <b style={{ fontSize: 15 }}>{o.texto}</b>
                  {o.ayuda && <span style={{ fontSize: 12, color: "var(--txt-3)" }}>{o.ayuda}</span>}
                </span>
                {elegido && <Insignia tono="ok" icono="si">Elegido</Insignia>}
                {o.deshabilitada && <Insignia tono="info" icono="aviso">No alcanza</Insignia>}
              </button>
            );
          })}
        </div>
      )}

      {err && <Aviso tono="error">{err}</Aviso>}

      <div>
        <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE}
                disabled={!pedido || pidiendo || !online} onClick={() => void pedir(pedido)}>
          <Ic n="video" s={15} /> {pidiendo ? "Pidiendo…" : "Pedir el video"}
        </button>
      </div>
    </div>
  );
}
