"use client";

import { useCallback, useEffect, useState } from "react";
import {
  listarImportados, promoverImportado, descartarImportado,
  type ComercioImportado,
} from "@/lib/api";
import type { Rubro } from "@/lib/types";

/** Revisión de los comercios traídos de fuentes externas.
 *
 * POR QUÉ ESTO EXISTE COMO PANTALLA APARTE
 * ========================================
 *
 * Lo que trae OpenStreetMap es nombre, punto en el mapa y a veces teléfono.
 * Medido sobre 19.861 negocios de las cinco ciudades: el 0,5% tenía foto y el
 * 1% WhatsApp. Un comercio de URUKU, en cambio, es un local que alguien caminó
 * —con la foto de la vidriera y el rubro deducido de lo que se ve.
 *
 * Si lo importado entrara directo al mapa, el comprador tocaría pines que no
 * llevan a ningún lado y dejaría de confiar en los que sí. Por eso se revisan
 * acá y pasan de a uno.
 */

const ESTADOS = [
  { key: "nuevo", label: "Sin revisar" },
  { key: "promovido", label: "En el mapa" },
  { key: "descartado", label: "Descartados" },
] as const;

export function ImportadosPanel({ rubros }: { rubros: Rubro[] }) {
  const [estado, setEstado] = useState<string>("nuevo");
  const [q, setQ] = useState("");
  const [items, setItems] = useState<ComercioImportado[]>([]);
  const [resumen, setResumen] = useState<{ estado: string; n: number }[]>([]);
  const [cargando, setCargando] = useState(true);
  const [err, setErr] = useState("");
  const [ocultarDup, setOcultarDup] = useState(true);

  const cargar = useCallback(async () => {
    setCargando(true); setErr("");
    try {
      const r = await listarImportados(estado, q || undefined);
      setItems(r.items ?? []);
      setResumen(r.resumen ?? []);
    } catch {
      setErr("No se pudieron cargar los importados");
    } finally {
      setCargando(false);
    }
  }, [estado, q]);

  useEffect(() => { cargar(); }, [cargar]);

  function totalDe(e: string) {
    return resumen.filter((r) => r.estado === e).reduce((a, b) => a + b.n, 0);
  }

  // Los que ya están cargados en URUKU (mismo nombre a menos de 120 m) se
  // esconden por defecto: si no, el que revisa mira doscientas fichas que ya
  // tiene y abandona antes de llegar a las que sirven.
  const visibles = ocultarDup ? items.filter((i) => !i.duplicado_de) : items;
  const nDup = items.length - items.filter((i) => !i.duplicado_de).length;

  return (
    <div>
      <div style={{ marginBottom: 14 }}>
        <p style={{ color: "var(--txt-3)", fontSize: 13, lineHeight: 1.5, marginBottom: 10 }}>
          Negocios traídos de <b>OpenStreetMap</b> (licencia ODbL, con atribución).
          No están en el mapa: pasan de a uno cuando los promovés. Traen nombre y
          ubicación casi siempre, teléfono a veces, y <b>casi nunca foto</b> — ésa
          la saca alguien parado enfrente.
        </p>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", alignItems: "center" }}>
          {ESTADOS.map((e) => (
            <button key={e.key} className={estado === e.key ? "chip chip-on" : "chip"}
                    onClick={() => setEstado(e.key)}>
              {e.label} {totalDe(e.key) > 0 && <b>{totalDe(e.key)}</b>}
            </button>
          ))}
          <input value={q} onChange={(ev) => setQ(ev.target.value)} placeholder="Buscar por nombre…"
                 style={{ padding: "6px 10px", borderRadius: 8, border: "1px solid var(--border)",
                          background: "var(--panel)", color: "var(--txt-1)", fontSize: 13 }} />
        </div>
        {nDup > 0 && estado === "nuevo" && (
          <label style={{ display: "flex", alignItems: "center", gap: 8, marginTop: 10, fontSize: 12.5, color: "var(--txt-3)" }}>
            <input type="checkbox" checked={ocultarDup} onChange={() => setOcultarDup((v) => !v)} />
            Ocultar {nDup} que parecen ya estar cargados
          </label>
        )}
      </div>

      {err && <p style={{ color: "salmon", fontSize: 13 }}>{err}</p>}
      {cargando && <p style={{ color: "var(--txt-3)" }}>Cargando…</p>}
      {!cargando && visibles.length === 0 && (
        <p style={{ color: "var(--txt-3)", fontSize: 13.5 }}>
          Nada acá. Se llena corriendo <code>importar_osm.py</code> con la ciudad.
        </p>
      )}

      {visibles.map((i) => (
        <Fila key={i.id} item={i} rubros={rubros} onCambio={cargar} />
      ))}
    </div>
  );
}

function Fila({ item, rubros, onCambio }: {
  item: ComercioImportado; rubros: Rubro[]; onCambio: () => void;
}) {
  const [rubro, setRubro] = useState(item.rubro_slug ?? "");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const revisable = item.estado === "nuevo";

  async function promover() {
    setBusy(true); setErr("");
    try {
      await promoverImportado(item.id, { rubro_slug: rubro || undefined });
      onCambio();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo");
      setBusy(false);
    }
  }

  async function descartar() {
    const motivo = window.prompt("¿Por qué se descarta? (cerrado, duplicado, no es comercio…)") ?? "";
    if (motivo === null) return;
    setBusy(true);
    try { await descartarImportado(item.id, motivo); onCambio(); }
    catch { setErr("No se pudo descartar"); setBusy(false); }
  }

  return (
    <div style={{ padding: "10px 0", borderBottom: "1px solid var(--border)",
                  display: "flex", gap: 10, alignItems: "flex-start", opacity: busy ? 0.5 : 1 }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontWeight: 600, fontSize: 14 }}>
          {item.nombre}
          {item.duplicado_de && (
            <span title="Hay un comercio cargado con nombre parecido a menos de 120 m"
                  style={{ marginLeft: 8, fontSize: 11, color: "var(--amber)" }}>
              ⚠ ya cargado?
            </span>
          )}
        </div>
        <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 2 }}>
          {item.categoria}
          {item.direccion && ` · ${item.direccion}`}
          {item.telefono && ` · ☎ ${item.telefono}`}
          {item.whatsapp && ` · WA ${item.whatsapp}`}
          {item.horario && ` · ${item.horario}`}
        </div>
        {/* La fuente a la vista, siempre. En seis meses nadie puede distinguir
            un local caminado de uno traído de un mapa abierto si no está
            escrito — y la diferencia importa para la licencia y la confianza. */}
        <div style={{ fontSize: 11, color: "var(--txt-3)", opacity: 0.7, fontFamily: "monospace", marginTop: 2 }}>
          {item.fuente}:{item.fuente_id}
          {item.lat != null && ` · ${item.lat.toFixed(5)}, ${item.lng?.toFixed(5)}`}
          {item.motivo && ` · ${item.motivo}`}
        </div>
        {err && <div style={{ color: "salmon", fontSize: 12, marginTop: 4 }}>{err}</div>}
      </div>

      {revisable && (
        <div style={{ display: "flex", gap: 6, alignItems: "center", flexShrink: 0 }}>
          {/* El rubro se elige acá y no al importar: la categoría de OSM no
              siempre mapea, y un rubro inventado ensucia un filtro para
              siempre. Vacío = "otros". */}
          <select value={rubro} onChange={(e) => setRubro(e.target.value)}
                  style={{ padding: "5px 8px", borderRadius: 8, border: "1px solid var(--border)",
                           background: "var(--panel)", color: "var(--txt-1)", fontSize: 12, maxWidth: 150 }}>
            <option value="">(otros)</option>
            {rubros.map((r) => <option key={r.slug} value={r.slug}>{r.nombre}</option>)}
          </select>
          <button className="btn btn-primary" disabled={busy} onClick={promover}
                  style={{ padding: "5px 12px", fontSize: 12.5, whiteSpace: "nowrap" }}>
            Al mapa
          </button>
          <button className="link-more" disabled={busy} onClick={descartar}
                  style={{ color: "var(--pink)", padding: 0, fontSize: 12.5 }}>
            Descartar
          </button>
        </div>
      )}
    </div>
  );
}
