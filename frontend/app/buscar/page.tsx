"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { Nav } from "@/components/nav";
import { MapResults } from "@/components/map-results";
import { buscarComercios, getRubros, getZonas } from "@/lib/data";
import { type ResultadoBusqueda, type Rubro, type Zona, MODALIDAD_LABEL, comoLlegarHref, waLink } from "@/lib/types";
import { WhatsApp, Pin, Search, Verified } from "@/components/icons";

const MODALIDADES = [
  { key: "", label: "Todos" },
  { key: "mayorista", label: "Mayorista" },
  { key: "minorista", label: "Minorista" },
  { key: "ambos", label: "Ambos" },
];

export default function BuscarPage() {
  const [q, setQ] = useState("");
  const [rubro, setRubro] = useState("");
  const [modalidad, setModalidad] = useState("");
  const [zona, setZona] = useState("");
  const [precioMax, setPrecioMax] = useState("");
  const [ciudad, setCiudad] = useState("");
  const [vista, setVista] = useState<"lista" | "mapa">("lista");
  const [results, setResults] = useState<ResultadoBusqueda[]>([]);
  const [rubros, setRubros] = useState<Rubro[]>([]);
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [loading, setLoading] = useState(true);
  const [hayMas, setHayMas] = useState(false);
  const [cargandoMas, setCargandoMas] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout>>();
  const PAGE = 24;

  const filtros = { q, rubro, modalidad, zona, ciudad, precioMax: precioMax ? Number(precioMax) : undefined };

  useEffect(() => {
    getRubros().then(setRubros);
    getZonas().then(setZonas);
    const c = new URLSearchParams(window.location.search).get("ciudad");
    if (c) setCiudad(c);
  }, []);

  // Buscar con debounce ante cualquier cambio de filtro / texto
  useEffect(() => {
    clearTimeout(debounce.current);
    setLoading(true);
    debounce.current = setTimeout(async () => {
      const r = await buscarComercios(filtros, PAGE, 0);
      setResults(r);
      setHayMas(r.length === PAGE);
      setLoading(false);
    }, 280);
    return () => clearTimeout(debounce.current);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, rubro, modalidad, zona, ciudad, precioMax]);

  async function cargarMas() {
    setCargandoMas(true);
    const more = await buscarComercios(filtros, PAGE, results.length);
    setResults((prev) => [...prev, ...more]);
    setHayMas(more.length === PAGE);
    setCargandoMas(false);
  }

  return (
    <>
      <Nav active="buscar" />
      <div className="wrap" style={{ paddingTop: 28 }}>
        <span className="eyebrow"><Search style={{ width: 14, height: 14 }} /> Buscador de Bermejo</span>
        <h1 style={{ fontSize: 30, margin: "8px 0 4px" }}>¿Qué estás buscando?</h1>
        <p style={{ color: "var(--txt-2)", margin: "0 0 18px" }}>
          Buscá por producto, comercio o rubro. Resultados con WhatsApp y cómo llegar.
        </p>

        {/* Barra de búsqueda */}
        <div className="search-bar glass">
          <Search style={{ width: 20, height: 20, color: "var(--txt-3)" }} />
          <input
            autoFocus
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Ej: zapatillas, iphone, perfume, gomería, restaurante…"
          />
        </div>

        {/* Ciudad fija (viene del mapa de Bolivia) */}
        {ciudad && (
          <div style={{ marginTop: 12 }}>
            <span className="pill" style={{ background: "rgba(57,255,158,.12)", border: "1px solid rgba(57,255,158,.3)", color: "var(--neon)", fontWeight: 700, padding: "7px 13px", borderRadius: 999, display: "inline-flex", alignItems: "center", gap: 7 }}>
              <Pin style={{ width: 14, height: 14 }} /> {ciudad.charAt(0).toUpperCase() + ciudad.slice(1)} · ciudad fija
            </span>
          </div>
        )}

        {/* Filtros */}
        <div className="filtros">
          <select className="adm-input fsel" value={rubro} onChange={(e) => setRubro(e.target.value)}>
            <option value="">Todos los rubros</option>
            {rubros.map((r) => (<option key={r.slug} value={r.slug}>{r.nombre}</option>))}
          </select>
          <select className="adm-input fsel" value={zona} onChange={(e) => setZona(e.target.value)}>
            <option value="">Todas las zonas</option>
            {zonas.map((z) => (<option key={z.slug} value={z.slug}>{z.nombre}</option>))}
          </select>
          <input
            className="adm-input fsel"
            type="number"
            inputMode="numeric"
            value={precioMax}
            onChange={(e) => setPrecioMax(e.target.value)}
            placeholder="Precio máx."
          />
          <div className="seg fseg">
            {MODALIDADES.map((m) => (
              <button key={m.key} className={modalidad === m.key ? "active" : ""} onClick={() => setModalidad(m.key)}>{m.label}</button>
            ))}
          </div>
        </div>

        {/* Header de resultados + toggle vista */}
        <div className="section-head" style={{ marginTop: 22, marginBottom: 16 }}>
          <div>
            <h2 style={{ fontSize: 18 }}>
              {loading ? "Buscando…" : `${results.length} comercio${results.length === 1 ? "" : "s"}`}
            </h2>
          </div>
          <div className="seg" style={{ maxWidth: 220 }}>
            <button className={vista === "lista" ? "active" : ""} onClick={() => setVista("lista")}>Lista</button>
            <button className={vista === "mapa" ? "active" : ""} onClick={() => setVista("mapa")}>Mapa</button>
          </div>
        </div>

        {/* Resultados */}
        {vista === "mapa" ? (
          <MapResults results={results} />
        ) : (
          <div className="result-grid">
            {!loading && results.length === 0 && (
              <p style={{ color: "var(--txt-3)" }}>No encontramos comercios con esos filtros. Probá con otra palabra o quitá filtros.</p>
            )}
            {results.map((r) => (
              <article className="rescard" key={r.id}>
                <Link href={`/comercios/${r.slug}`} className="rescover">
                  <img src={r.portada_url ?? r.logo_url ?? "https://picsum.photos/seed/x/400/240"} alt={r.nombre} />
                  {r.logo_url && <img className="reslogo" src={r.logo_url} alt="" />}
                </Link>
                <div className="resbody">
                  <h4>
                    <Link href={`/comercios/${r.slug}`}>{r.nombre}</Link>
                    {r.verificado && <span className="pverif"><Verified style={{ width: 14, height: 14 }} /></span>}
                  </h4>
                  <div className="resmeta">
                    <span className="pill" style={{ color: "var(--blue-soft)" }}>{MODALIDAD_LABEL[r.modalidad] ?? r.modalidad}</span>
                    {r.rubro_nombre && <span className="pill">{r.rubro_nombre}</span>}
                    {r.ofertas > 0 && <span className="pill" style={{ color: "var(--neon)" }}>{r.ofertas} ofertas</span>}
                  </div>
                  {r.direccion && <div className="resdir"><Pin style={{ width: 13, height: 13 }} />{r.direccion}</div>}
                  <div className="resact">
                    <a className="btn btn-wa btn-sm" href={waLink(r.whatsapp, `Hola, te vi en Encontralo`)} target="_blank" rel="noopener">
                      <WhatsApp style={{ width: 15, height: 15 }} /> WhatsApp
                    </a>
                    <a className="btn btn-ghost btn-sm" href={comoLlegarHref(r)} target="_blank" rel="noopener">
                      <Pin style={{ width: 15, height: 15 }} /> Cómo llegar
                    </a>
                  </div>
                </div>
              </article>
            ))}
          </div>
        )}

        {vista === "lista" && hayMas && (
          <div style={{ textAlign: "center", marginTop: 22 }}>
            <button className="btn btn-ghost" onClick={cargarMas} disabled={cargandoMas}>
              {cargandoMas ? "Cargando…" : "Cargar más"}
            </button>
          </div>
        )}

        <div style={{ height: 50 }} />
      </div>
    </>
  );
}
