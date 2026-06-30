"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { MapResults } from "@/components/map-results";
import { BottomNav } from "@/components/bottom-nav";
import { buscarComercios, getRubros, getZonas } from "@/lib/data";
import { type ResultadoBusqueda, type Rubro, type Zona, MODALIDAD_LABEL, comoLlegarHref, waLink } from "@/lib/types";
import { WhatsApp, Pin, Search, Verified, User } from "@/components/icons";
import { FilterChip, OptionList } from "@/components/filter-chips";

const RESERVALO_URL = "https://reservalo.store";

export default function BuscarPage() {
  const [q, setQ] = useState("");
  const [rubro, setRubro] = useState("");
  const [modalidad, setModalidad] = useState("");
  const [zona, setZona] = useState("");
  const [precioMax, setPrecioMax] = useState("");
  const [ciudad, setCiudad] = useState("");
  const [soloOfertas, setSoloOfertas] = useState(false);
  const [vista, setVista] = useState<"lista" | "mapa">("lista");
  const [results, setResults] = useState<ResultadoBusqueda[]>([]);
  const [rubros, setRubros] = useState<Rubro[]>([]);
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [loading, setLoading] = useState(true);
  const [hayMas, setHayMas] = useState(false);
  const [cargandoMas, setCargandoMas] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout>>();
  const PAGE = 30;

  const filtros = { q, rubro, modalidad, zona, ciudad, precioMax: precioMax ? Number(precioMax) : undefined };

  useEffect(() => {
    getRubros().then(setRubros);
    getZonas().then(setZonas);
    const sp = new URLSearchParams(window.location.search);
    if (sp.get("ciudad")) setCiudad(sp.get("ciudad")!);
    if (sp.get("q")) setQ(sp.get("q")!);
    if (sp.get("rubro")) setRubro(sp.get("rubro")!);
    if (sp.get("zona")) setZona(sp.get("zona")!);
    if (sp.get("precio_max")) setPrecioMax(sp.get("precio_max")!);
  }, []);

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

  const zonaNom = zonas.find((z) => z.slug === zona)?.nombre;
  const shown = soloOfertas ? results.filter((r) => r.ofertas > 0) : results;

  const catChips = [{ slug: "", nombre: "Todos" }, ...rubros];

  return (
    <div className="bpage">
      {/* Header claro estilo home: marca (vuelve al inicio) + avatar + buscador */}
      <div className="mhead">
        <div className="mtop">
          <Link href="/" className="mbrand">ENCON<i>TRALO</i></Link>
          <Link href="/mi-comercio" className="mavatar" aria-label="Perfil"><User style={{ width: 20, height: 20 }} /></Link>
        </div>
        <form className="msearch" onSubmit={(e) => e.preventDefault()}>
          <Search style={{ width: 20, height: 20, color: "#7a8390" }} />
          <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar locales o servicios…" aria-label="Buscar" />
        </form>
      </div>

      {/* Chips de categoría (texto simple, estilo home) */}
      <div className="mchips">
        {catChips.map((c) => (
          <button type="button" key={c.slug || "todos"} className={`mchip ${rubro === c.slug ? "active" : ""}`} onClick={() => setRubro(c.slug)}>
            {c.nombre}
          </button>
        ))}
      </div>

      {/* Filtros avanzados + accesos, fila compacta */}
      <div className="bfilters">
        <FilterChip icon="📍" label="Zona" value={zonaNom} active={!!zona}>
          {(close) => <OptionList items={[{ slug: "", nombre: "Todas las zonas" }, ...zonas]} sel={zona} onPick={(v) => { setZona(v); close(); }} />}
        </FilterChip>

        <FilterChip icon="💰" label="Precio" value={precioMax ? `hasta ${precioMax}` : undefined} active={!!precioMax}>
          {(close) => (
            <div style={{ padding: 12, minWidth: 200 }}>
              <input className="adm-input" type="number" inputMode="numeric" value={precioMax} onChange={(e) => setPrecioMax(e.target.value)} placeholder="Precio máximo" />
              <button className="btn btn-primary btn-sm" style={{ marginTop: 8, width: "100%" }} onClick={close}>Aplicar</button>
              {precioMax && <button className="btn btn-sm" style={{ marginTop: 6, width: "100%", border: "1px solid var(--stroke)" }} onClick={() => { setPrecioMax(""); close(); }}>Quitar</button>}
            </div>
          )}
        </FilterChip>

        <FilterChip icon="🏪" label="Tipo" value={modalidad ? MODALIDAD_LABEL[modalidad] : undefined} active={!!modalidad}>
          {(close) => <OptionList items={[{ slug: "", nombre: "Todos" }, { slug: "mayorista", nombre: "Mayorista" }, { slug: "minorista", nombre: "Minorista" }, { slug: "ambos", nombre: "Ambos" }]} sel={modalidad} onPick={(v) => { setModalidad(v); close(); }} />}
        </FilterChip>

        <button type="button" className={`mchip ${soloOfertas ? "active" : ""}`} onClick={() => setSoloOfertas((v) => !v)}>Ofertas</button>
        <a className="mchip" href={`${RESERVALO_URL}/productos${q ? `?search=${encodeURIComponent(q)}` : ""}`}>Productos ↗</a>
      </div>

      {/* Cantidad + vista */}
      <div className="resbar">
        <b>{loading ? "Buscando…" : `${shown.length} comercio${shown.length === 1 ? "" : "s"}`}</b>
        <div className="seg" style={{ maxWidth: 200 }}>
          <button className={vista === "lista" ? "active" : ""} onClick={() => setVista("lista")}>Lista</button>
          <button className={vista === "mapa" ? "active" : ""} onClick={() => setVista("mapa")}>Mapa</button>
        </div>
      </div>

      {/* Resultados */}
      <div className="bresults">
        {vista === "mapa" ? (
          <MapResults results={shown} />
        ) : (
          <div className="result-grid">
            {!loading && shown.length === 0 && (
              <p style={{ color: "var(--txt-3)" }}>No encontramos comercios con esos filtros. Probá con otra palabra o quitá filtros.</p>
            )}
            {shown.map((r) => (
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

        {vista === "lista" && hayMas && !soloOfertas && (
          <div style={{ textAlign: "center", marginTop: 22 }}>
            <button className="btn btn-ghost" onClick={cargarMas} disabled={cargandoMas}>
              {cargandoMas ? "Cargando…" : "Cargar más"}
            </button>
          </div>
        )}
      </div>

      <BottomNav active="" />
    </div>
  );
}
