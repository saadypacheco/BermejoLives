"use client";

// ABM de "lugares" (mercados / galerías / paseos / referencias) desde el admin, con
// mapa: tocás el mapa para UBICAR uno nuevo o MOVER el seleccionado. Sirve para
// pre-cargar los ~20 puntos conocidos de Bermejo antes de salir al campo.
import { useEffect, useRef, useState } from "react";
import { loadLeaflet, escapeHtml } from "@/lib/mapa-visual";
import { adminListLugares, adminCrearLugar, adminUpdateLugar, adminDeleteLugar, type LugarAdmin } from "@/lib/api";

const BERMEJO: [number, number] = [-22.7361, -64.3433];
const TIPOS: [string, string][] = [
  ["mercado", "Mercado"], ["galeria", "Galería"], ["paseo", "Paseo"], ["shopping", "Shopping"], ["referencia", "Referencia"],
];

export function LugaresEditor() {
  const elRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<any>(null);
  const layerRef = useRef<any>(null);
  const draftRef = useRef<any>(null);
  const polyRef = useRef<any>(null);
  const dibujandoRef = useRef(false);
  const LRef = useRef<any>(null);
  const [lugares, setLugares] = useState<LugarAdmin[]>([]);
  const [selId, setSelId] = useState<string | null>(null);
  const [nombre, setNombre] = useState("");
  const [tipo, setTipo] = useState("mercado");
  const [pos, setPos] = useState<{ lat: number; lng: number } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");
  const [dibujando, setDibujando] = useState(false);
  const [poly, setPoly] = useState<[number, number][]>([]);
  dibujandoRef.current = dibujando;

  async function cargar() { setLugares(await adminListLugares().catch(() => [])); }
  useEffect(() => { cargar(); }, []);

  useEffect(() => {
    let cancelled = false;
    loadLeaflet().then((L) => {
      if (cancelled || !elRef.current || mapRef.current) return;
      LRef.current = L;
      const map = L.map(elRef.current, { attributionControl: false }).setView(BERMEJO, 15);
      mapRef.current = map;
      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", { maxZoom: 19, updateWhenIdle: true, keepBuffer: 2 }).addTo(map);
      layerRef.current = L.layerGroup().addTo(map);
      map.on("click", (e: any) => {
        if (dibujandoRef.current) setPoly((p) => [...p, [e.latlng.lat, e.latlng.lng]]);
        else setPos({ lat: e.latlng.lat, lng: e.latlng.lng });
      });
      setTimeout(() => map.invalidateSize(), 60);
      pintar();
    });
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => { pintar(); /* eslint-disable-next-line */ }, [lugares, selId]);
  useEffect(() => { pintarDraft(); /* eslint-disable-next-line */ }, [pos]);
  useEffect(() => { pintarPoly(); /* eslint-disable-next-line */ }, [poly, dibujando]);

  function pintar() {
    const L = LRef.current, layer = layerRef.current;
    if (!L || !layer) return;
    layer.clearLayers();
    for (const l of lugares) {
      if (l.lat == null || l.lng == null) continue;
      const sel = l.id === selId;
      const html = `<div class="ukpinlugar" style="${sel ? "outline:2px solid #39ff9e;outline-offset:2px;" : ""}"><span>🏬</span><b>${escapeHtml(l.nombre)}</b>${l.n_comercios ? `<i>${l.n_comercios}</i>` : ""}</div>`;
      const m = L.marker([l.lat, l.lng], { icon: L.divIcon({ className: "", html, iconSize: null as any, iconAnchor: [15, 16] }) }).addTo(layer);
      m.on("click", () => seleccionar(l));
    }
  }
  function pintarDraft() {
    const L = LRef.current, map = mapRef.current;
    if (!L || !map) return;
    if (draftRef.current) { map.removeLayer(draftRef.current); draftRef.current = null; }
    if (pos) {
      const icon = L.divIcon({ className: "", html: `<div class="here-dot" style="background:#39ff9e"></div>`, iconSize: [18, 18], iconAnchor: [9, 9] });
      draftRef.current = L.marker([pos.lat, pos.lng], { icon, zIndexOffset: 1000 }).addTo(map);
    }
  }

  function pintarPoly() {
    const L = LRef.current, map = mapRef.current;
    if (!L || !map) return;
    if (polyRef.current) { map.removeLayer(polyRef.current); polyRef.current = null; }
    if (poly.length >= 2) {
      polyRef.current = L.polygon(poly, {
        color: "#8b5cf6", weight: 2, fillColor: "#8b5cf6",
        fillOpacity: dibujando ? 0.1 : 0.18, dashArray: dibujando ? "5 5" : undefined,
      }).addTo(map);
    }
  }

  function seleccionar(l: LugarAdmin) {
    setSelId(l.id); setNombre(l.nombre); setTipo(l.tipo || "mercado");
    setPos(l.lat != null && l.lng != null ? { lat: l.lat, lng: l.lng } : null);
    setPoly((l.poligono as [number, number][]) ?? []); setDibujando(false); setErr("");
    if (l.lat != null && l.lng != null) mapRef.current?.panTo([l.lat, l.lng]);
  }
  function nuevo() { setSelId(null); setNombre(""); setTipo("mercado"); setPos(null); setPoly([]); setDibujando(false); setErr(""); }

  function dibujarManzana() { setDibujando(true); setPoly([]); setErr(""); }
  function deshacer() { setPoly((p) => p.slice(0, -1)); }
  async function guardarManzana() {
    if (!selId) return;
    if (poly.length < 3) { setErr("Marcá al menos 3 esquinas de la manzana"); return; }
    setBusy(true); setErr("");
    try { await adminUpdateLugar(selId, { poligono: poly }); setDibujando(false); await cargar(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Error"); }
    finally { setBusy(false); }
  }
  async function borrarManzana() {
    if (!selId) return;
    setBusy(true); setErr("");
    try { await adminUpdateLugar(selId, { poligono: [] }); setPoly([]); setDibujando(false); await cargar(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Error"); }
    finally { setBusy(false); }
  }

  async function guardar() {
    if (!nombre.trim()) { setErr("Falta el nombre"); return; }
    if (!pos && !selId) { setErr("Tocá el mapa para ubicar el lugar"); return; }
    setBusy(true); setErr("");
    try {
      if (selId) await adminUpdateLugar(selId, { nombre: nombre.trim(), tipo, lat: pos?.lat ?? null, lng: pos?.lng ?? null });
      else await adminCrearLugar({ nombre: nombre.trim(), tipo, lat: pos?.lat ?? null, lng: pos?.lng ?? null });
      await cargar(); nuevo();
    } catch (e) { setErr(e instanceof Error ? e.message : "Error"); }
    finally { setBusy(false); }
  }
  async function borrar() {
    if (!selId) return;
    if (!window.confirm("¿Borrar este lugar? Los comercios quedan (sin lugar).")) return;
    setBusy(true);
    try { await adminDeleteLugar(selId); await cargar(); nuevo(); }
    catch (e) { setErr(e instanceof Error ? e.message : "Error"); }
    finally { setBusy(false); }
  }

  return (
    <div className="panel-card glass">
      <div className="ph">
        <h3>Lugares (mercados / galerías / referencias)</h3>
        <span style={{ color: "var(--txt-3)", fontSize: 13 }}>{lugares.length} cargados · tocá el mapa para ubicar/mover</span>
      </div>

      <div style={{ padding: 16, display: "flex", flexDirection: "column", gap: 10 }}>
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input className="adm-input" style={{ flex: 2, minWidth: 180 }} value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre (ej: Mercado Central)" />
          <select className="adm-input" style={{ width: "auto" }} value={tipo} onChange={(e) => setTipo(e.target.value)}>
            {TIPOS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button className="btn btn-primary" disabled={busy} onClick={guardar}>{selId ? "Guardar cambios" : "Agregar"}</button>
          {selId && <button className="btn btn-ghost" onClick={nuevo}>Nuevo</button>}
          {selId && <button className="btn btn-ghost" style={{ color: "var(--pink)" }} disabled={busy} onClick={borrar}>Borrar</button>}
        </div>
        <div style={{ fontSize: 12.5, color: dibujando ? "#c4b5fd" : pos ? "var(--neon)" : "var(--amber)" }}>
          {dibujando
            ? `✏️ Tocá las esquinas de la manzana (${poly.length} marcadas)`
            : pos ? `📍 Ubicación: ${pos.lat.toFixed(5)}, ${pos.lng.toFixed(5)} (tocá el mapa para mover)` : "Tocá el mapa para ubicar el lugar."}
          {selId && !dibujando && " · Editando uno existente."}
        </div>

        {/* Fase 2: polígono de la manzana (solo sobre un lugar existente) */}
        {selId && (
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", fontSize: 13 }}>
            {!dibujando ? (
              <>
                <button className="btn btn-ghost" onClick={dibujarManzana}>✏️ Dibujar manzana</button>
                {poly.length >= 3 && <span style={{ color: "var(--txt-3)" }}>Manzana: {poly.length} esquinas</span>}
                {poly.length >= 3 && <button className="btn btn-ghost" style={{ color: "var(--pink)" }} disabled={busy} onClick={borrarManzana}>Borrar manzana</button>}
              </>
            ) : (
              <>
                <button className="btn btn-ghost" disabled={!poly.length} onClick={deshacer}>↶ Deshacer</button>
                <button className="btn btn-primary" disabled={busy || poly.length < 3} onClick={guardarManzana}>Guardar manzana</button>
                <button className="btn btn-ghost" onClick={() => setDibujando(false)}>Cancelar</button>
              </>
            )}
          </div>
        )}
        {err && <div style={{ color: "var(--pink)", fontSize: 13 }}>{err}</div>}
        <div ref={elRef} style={{ height: 420, borderRadius: 12, overflow: "hidden", border: "1px solid var(--border)" }} />
      </div>

      {lugares.map((l) => (
        <button key={l.id} onClick={() => seleccionar(l)}
          style={{ display: "flex", width: "100%", alignItems: "center", gap: 10, padding: "10px 16px", borderTop: "1px solid var(--border)", background: l.id === selId ? "rgba(57,255,158,.06)" : "transparent", border: "none", borderTopStyle: "solid", cursor: "pointer", textAlign: "left", color: "var(--txt)" }}>
          <span style={{ fontSize: 16 }}>🏬</span>
          <span style={{ flex: 1, minWidth: 0 }}>
            <b style={{ fontSize: 14 }}>{l.nombre}</b>
            <span style={{ color: "var(--txt-3)", fontSize: 12 }}> · {l.tipo}{l.n_comercios ? ` · ${l.n_comercios} puestos` : ""}{l.lat == null ? " · sin ubicación" : ""}</span>
          </span>
        </button>
      ))}
    </div>
  );
}
