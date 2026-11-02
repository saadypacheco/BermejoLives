"use client";

import { useEffect, useRef, useState } from "react";
import { Ic } from "@/components/ic";
import { Aviso, BTN_GRANDE, Cargando } from "@/components/content/content-ui";
import { buscarComerciosBanco, mensajeContent, type ContentMerchantResponse } from "@/lib/content";

/**
 * El buscador de comercio del Banco de contenido: se elige UNA vez y se sacan o
 * suben todas las fotos que se quieran (§9.2). Arriba van los «Recientes» (los
 * últimos comercios donde subió quien pregunta).
 *
 * Busca con una pausa de 300 ms para no pegarle al servidor en cada letra.
 */
export function ContentMerchantPicker({ onElegir }: { onElegir: (m: ContentMerchantResponse) => void }) {
  const [q, setQ] = useState("");
  const [items, setItems] = useState<ContentMerchantResponse[]>([]);
  const [recientes, setRecientes] = useState<ContentMerchantResponse[]>([]);
  const [cargando, setCargando] = useState(true);
  const [err, setErr] = useState("");
  // Sólo vale la respuesta del ÚLTIMO pedido: si llegan desordenadas, no pisa la nueva.
  const vez = useRef(0);

  async function buscar(texto: string) {
    const n = ++vez.current;
    setCargando(true); setErr("");
    try {
      const r = await buscarComerciosBanco(texto);
      if (n !== vez.current) return;
      setItems(r.items); setRecientes(r.recent);
    } catch (ex) {
      if (n === vez.current) setErr(mensajeContent(ex, "No se pudo buscar comercios"));
    } finally {
      if (n === vez.current) setCargando(false);
    }
  }

  useEffect(() => {
    const t = setTimeout(() => { void buscar(q); }, q ? 300 : 0);
    return () => clearTimeout(t);
  }, [q]);   // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <div style={{ display: "grid", gap: 12 }}>
      <label style={{ display: "grid", gap: 4, fontSize: 12.5 }}>
        <span style={{ color: "var(--txt-3)" }}>Buscar comercio</span>
        <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Ic n="buscar" s={18} />
          <input className="adm-input" type="search" inputMode="search" autoComplete="off" style={{ flex: 1, minHeight: 48 }}
                 value={q} onChange={(e) => setQ(e.target.value)} placeholder="Nombre del comercio…" />
        </span>
      </label>

      {recientes.length > 0 && !q && (
        <div>
          <div style={{ fontSize: 12, color: "var(--txt-3)", fontWeight: 700, marginBottom: 6 }}>Recientes</div>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            {recientes.map((m) => (
              <button key={m.id} type="button" className="chip" style={{ ...BTN_GRANDE, cursor: "pointer", fontSize: 13, padding: "6px 14px", borderRadius: 999, border: "1px solid var(--stroke)" }} onClick={() => onElegir(m)}>
                {m.nombre}
              </button>
            ))}
          </div>
        </div>
      )}

      {err && <Aviso tono="error" accion={<button type="button" className="btn btn-ghost btn-sm" style={BTN_GRANDE} onClick={() => void buscar(q)}>Reintentar</button>}>{err}</Aviso>}
      {cargando && !err && <Cargando texto="Buscando…" />}

      {!cargando && !err && items.length === 0 && (
        <p style={{ margin: 0, fontSize: 14, color: "var(--txt-3)" }}>
          {q ? "No encontramos comercios con ese nombre." : "Todavía no hay comercios para mostrar."}
        </p>
      )}

      <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 8 }}>
        {items.map((m) => (
          <li key={m.id}>
            <button type="button" onClick={() => onElegir(m)} className="glass"
                    style={{ ...BTN_GRANDE, width: "100%", textAlign: "left", padding: "10px 14px", borderRadius: 12, cursor: "pointer",
                             border: "1px solid var(--stroke)", display: "grid", gap: 2, color: "inherit" }}>
              <b style={{ fontSize: 15 }}>{m.nombre}</b>
              <span style={{ fontSize: 12.5, color: "var(--txt-3)" }}>
                {[m.rubro, m.calle, m.ciudad_nombre].filter(Boolean).join(" · ")}
                {m.is_subscriber ? " · Suscriptor" : ""}
              </span>
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
