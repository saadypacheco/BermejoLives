"use client";

import { useCallback, useEffect, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Cargando, ErrorConReintento, Insignia, SinConexion, useOnline } from "@/components/content/content-ui";
import { misPermisos } from "@/lib/api";
import { cambiarInterruptor, listarInterruptores, mensajeContent, type CostSwitch } from "@/lib/content";
import { bodyDeInterruptor, estadoDeInterruptor, tienePermiso } from "@/lib/content-pure";

/**
 * «Servicios con costo» (§17.2, §17.4): todo lo que gasta plata nace APAGADO y se
 * prende acá. Prender abre una confirmación con el costo y una casilla «Entiendo
 * que tiene costo»; apagar no pide nada. Sólo el permiso `equipo` tiene los
 * botones: el resto ve el estado y nada más (el backend también lo exige).
 */
export function ContentCostSwitches({ onCambio }: { onCambio?: () => void }) {
  const [items, setItems] = useState<CostSwitch[] | null>(null);
  const [err, setErr] = useState("");
  const puede = tienePermiso(misPermisos(), "equipo");

  const cargar = useCallback(async () => {
    setErr("");
    try { setItems(await listarInterruptores()); }
    catch (ex) { setErr(mensajeContent(ex, "No se pudieron cargar los servicios con costo")); setItems((x) => x ?? []); }
  }, []);

  useEffect(() => { void cargar(); }, [cargar]);

  return (
    <section className="panel-card glass" style={{ padding: 16, display: "grid", gap: 12 }} aria-label="Servicios con costo">
      <div>
        <h3 style={{ margin: "0 0 4px", fontSize: 17, display: "flex", alignItems: "center", gap: 8 }}>
          <Ic n="pagos" s={18} /> Servicios con costo
        </h3>
        <p style={{ margin: 0, fontSize: 13, color: "var(--txt-3)", lineHeight: 1.45 }}>
          Todo lo que gasta plata arranca apagado. Con el servicio apagado el contenido sigue funcionando con textos fijos.
        </p>
      </div>

      <SinConexion />
      {items === null && <Cargando texto="Cargando servicios…" />}
      {err && <ErrorConReintento mensaje={err} onReintentar={() => void cargar()} />}
      {items && items.length === 0 && !err && (
        <p style={{ margin: 0, fontSize: 14, color: "var(--txt-3)" }}>No hay servicios con costo para mostrar.</p>
      )}
      {items && items.map((it) => (
        <Interruptor key={it.key} it={it} puede={puede} onCambio={() => { void cargar(); onCambio?.(); }} />
      ))}
      {items && items.length > 0 && !puede && (
        <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>
          <Ic n="seguridad" s={13} /> Sólo quien tiene el permiso de equipo puede prender o apagar un servicio.
        </span>
      )}
    </section>
  );
}

function Interruptor({ it, puede, onCambio }: { it: CostSwitch; puede: boolean; onCambio: () => void }) {
  const estado = estadoDeInterruptor(it.enabled);
  const online = useOnline();
  const [confirmando, setConfirmando] = useState(false);
  const [entiendo, setEntiendo] = useState(false);
  const [ocupado, setOcupado] = useState(false);
  const [err, setErr] = useState("");

  async function cambiar(enabled: boolean) {
    if (ocupado) return;
    setOcupado(true); setErr("");
    try {
      await cambiarInterruptor(it.key, bodyDeInterruptor(enabled, entiendo));
      setConfirmando(false); setEntiendo(false);
      onCambio();
    } catch (ex) {
      setErr(mensajeContent(ex, "No se pudo cambiar el servicio"));
    } finally {
      setOcupado(false);
    }
  }

  return (
    <div style={{ display: "grid", gap: 8, padding: 12, borderRadius: 12, border: "1px solid var(--stroke)" }}>
      <div style={{ display: "flex", gap: 8, alignItems: "center", justifyContent: "space-between", flexWrap: "wrap" }}>
        <b style={{ fontSize: 15 }}>{it.label}</b>
        <Insignia tono={estado.tono} icono={estado.icono}>{estado.texto}</Insignia>
      </div>
      <dl style={{ margin: 0, display: "grid", gap: 6, fontSize: 13, lineHeight: 1.45 }}>
        <div><dt style={{ display: "inline", fontWeight: 700 }}>Qué hace: </dt><dd style={{ display: "inline", margin: 0, color: "var(--txt-2)" }}>{it.what}</dd></div>
        <div><dt style={{ display: "inline", fontWeight: 700 }}>Cuánto cuesta: </dt><dd style={{ display: "inline", margin: 0, color: "var(--txt-2)" }}>{it.cost}</dd></div>
        <div><dt style={{ display: "inline", fontWeight: 700 }}>Si está apagado: </dt><dd style={{ display: "inline", margin: 0, color: "var(--txt-2)" }}>{it.off_means}</dd></div>
      </dl>
      {it.updated_by && it.updated_at && (
        <span style={{ fontSize: 12, color: "var(--txt-3)" }}>Último cambio: {it.updated_by}, {new Date(it.updated_at).toLocaleString("es-BO")}</span>
      )}

      {puede && !confirmando && (
        <div>
          {it.enabled ? (
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={ocupado || !online} onClick={() => void cambiar(false)}>
              <Ic n="cerrar" s={15} /> {ocupado ? "Apagando…" : "Apagar"}
            </button>
          ) : (
            <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} disabled={!online}
                    onClick={() => { setErr(""); setEntiendo(false); setConfirmando(true); }}>
              <Ic n="pagos" s={15} /> Prender
            </button>
          )}
        </div>
      )}

      {puede && confirmando && (
        <div role="group" aria-label={`Confirmar que se prende ${it.label}`} style={{ display: "grid", gap: 10 }}>
          <Aviso tono="aviso">Prender «{it.label}» tiene costo: {it.cost}.</Aviso>
          <label style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 14, minHeight: 44, cursor: "pointer" }}>
            <input type="checkbox" checked={entiendo} onChange={(e) => setEntiendo(e.target.checked)}
                   style={{ width: 22, height: 22, flex: "none", marginTop: 1 }} />
            <span>Entiendo que tiene costo</span>
          </label>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button type="button" className="btn btn-primary btn-sm" style={BTN_GRANDE} disabled={!entiendo || ocupado || !online} onClick={() => void cambiar(true)}>
              <Ic n="si" s={15} /> {ocupado ? "Prendiendo…" : "Sí, prender"}
            </button>
            <button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} disabled={ocupado}
                    onClick={() => { setConfirmando(false); setEntiendo(false); setErr(""); }}>
              Cancelar
            </button>
          </div>
        </div>
      )}

      {err && <Aviso tono="error">{err}</Aviso>}
    </div>
  );
}
