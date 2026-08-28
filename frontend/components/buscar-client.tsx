"use client";

import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { MapResults } from "@/components/map-results";
import { buscarComercios, getFiltrosDisponibles, getRubros, getZonas, type FiltrosDisponibles } from "@/lib/data";
import { type ResultadoBusqueda, type Rubro, type Zona, MODALIDAD_LABEL, comoLlegarHref, waLink } from "@/lib/types";
import { WhatsApp, Pin, Search, Verified } from "@/components/icons";
import { FilterChip, OptionList } from "@/components/filter-chips";
import { registrarLead, logBusqueda } from "@/lib/campo";

const RESERVALO_URL = "/tienda";

export function BuscarClient({ ciudadInicial = "" }: { ciudadInicial?: string }) {
  const [q, setQ] = useState("");
  const [rubro, setRubro] = useState("");
  const [modalidad, setModalidad] = useState("");
  const [zona, setZona] = useState("");
  const [precioMax, setPrecioMax] = useState("");
  // Arranca en la ciudad del selector; el parámetro ?ciudad= de la URL la pisa.
  const [ciudad, setCiudad] = useState(ciudadInicial);
  const [soloOfertas, setSoloOfertas] = useState(false);
  const [vista, setVista] = useState<"lista" | "mapa">("lista");
  const [results, setResults] = useState<ResultadoBusqueda[]>([]);
  const [rubros, setRubros] = useState<Rubro[]>([]);
  // Qué filtros tienen datos detrás. Arranca en `false` y NO se dibuja ninguno
  // hasta saberlo: mostrar un filtro y esconderlo medio segundo después es peor
  // que mostrarlo un poco más tarde.
  const [disp, setDisp] = useState<FiltrosDisponibles | null>(null);
  useEffect(() => { getFiltrosDisponibles().then(setDisp).catch(() => {}); }, []);
  const [zonas, setZonas] = useState<Zona[]>([]);
  const [loading, setLoading] = useState(true);
  const [hayMas, setHayMas] = useState(false);
  const [cargandoMas, setCargandoMas] = useState(false);
  const debounce = useRef<ReturnType<typeof setTimeout>>();
  const sp = useSearchParams();
  // Última búsqueda logueada: se le atan los contactos que salgan de ella.
  const [busquedaId, setBusquedaId] = useState<string | null>(null);
  const PAGE = 30;

  const filtros = { q, rubro, modalidad, zona, ciudad, precioMax: precioMax ? Number(precioMax) : undefined };

  useEffect(() => {
    getRubros().then(setRubros);
    getZonas().then(setZonas);
  }, []);

  // Los parámetros se leen en CADA navegación, no sólo al montar.
  //
  // La barra de categorías de arriba navega a /buscar?rubro=X. Como ya estamos
  // en /buscar, Next no vuelve a montar este componente: sólo cambia la URL. Con
  // la lectura en un efecto de montaje, el estado se quedaba en el filtro
  // anterior y tocar "Calzado" o "Bolsos" devolvía siempre lo mismo — parecía
  // que los filtros no andaban cuando en realidad nunca se enteraban.
  //
  // Se escriben sólo los que vienen en la URL: los chips de acá abajo cambian el
  // estado sin navegar, y pisarlos con un valor vacío los borraría al toque.
  useEffect(() => {
    const g = (k: string) => sp.get(k);
    if (g("ciudad") !== null) setCiudad(g("ciudad")!);
    if (g("zona") !== null) setZona(g("zona")!);
    if (g("precio_max") !== null) setPrecioMax(g("precio_max")!);
    // rubro y q son excluyentes entre sí en la navegación: entrar por una
    // categoría limpia el texto anterior, y buscar texto sale de la categoría.
    // Sin esto quedaba un filtro invisible activo y el resultado no cerraba con
    // lo que la pantalla mostraba.
    if (g("rubro") !== null) { setRubro(g("rubro")!); setQ(""); }
    else if (g("q") !== null) { setQ(g("q")!); setRubro(""); }
  }, [sp]);

  useEffect(() => {
    clearTimeout(debounce.current);
    setLoading(true);
    debounce.current = setTimeout(async () => {
      const r = await buscarComercios(filtros, PAGE, 0);
      setResults(r);
      // Se guarda el id de la búsqueda para atárselo al contacto si la persona
      // termina escribiéndole a alguno de estos comercios.
      if (q.trim()) {
        logBusqueda(q, r.length, r.map((c) => c.id)).then(setBusquedaId);
      } else {
        setBusquedaId(null);
      }
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
  const rubroElegido = rubro ? rubros.find((x) => x.slug === rubro)?.nombre ?? null : null;

  return (
    <div className="uk-container uk-buscar">
      <form className="uk-search-live" onSubmit={(e) => e.preventDefault()}>
        <Search style={{ width: 20, height: 20 }} />
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar locales o servicios…" aria-label="Buscar" />
      </form>

      <div className="uk-chips">
        {catChips.map((c) => (
          <button type="button" key={c.slug || "todos"} className={`uk-chip ${rubro === c.slug ? "active" : ""}`}
                  onClick={() => { setRubro(c.slug); setQ(""); }}>
            {c.nombre}
          </button>
        ))}
      </div>

      <div className="uk-filters">
        {disp?.zona && <FilterChip icon="📍" label="Zona" value={zonaNom} active={!!zona}>
          {(close) => <OptionList items={[{ slug: "", nombre: "Todas las zonas" }, ...zonas]} sel={zona} onPick={(v) => { setZona(v); close(); }} />}
        </FilterChip>}

        {disp?.ofertas && <FilterChip icon="💰" label="Precio" value={precioMax ? `hasta ${precioMax}` : undefined} active={!!precioMax}>
          {(close) => (
            <div style={{ padding: 12, minWidth: 200 }}>
              <input className="adm-input" type="number" inputMode="numeric" value={precioMax} onChange={(e) => setPrecioMax(e.target.value)} placeholder="Precio máximo" />
              <button className="uk-btn-wa" style={{ marginTop: 8, width: "100%" }} onClick={close}>Aplicar</button>
              {precioMax && <button className="uk-btn-ghost" style={{ marginTop: 6, width: "100%" }} onClick={() => { setPrecioMax(""); close(); }}>Quitar</button>}
            </div>
          )}
        </FilterChip>}

        <FilterChip icon="🏪" label="Tipo" value={modalidad ? MODALIDAD_LABEL[modalidad] : undefined} active={!!modalidad}>
          {(close) => <OptionList items={[{ slug: "", nombre: "Todos" }, { slug: "mayorista", nombre: "Mayorista" }, { slug: "minorista", nombre: "Minorista" }, { slug: "ambos", nombre: "Ambos" }]} sel={modalidad} onPick={(v) => { setModalidad(v); close(); }} />}
        </FilterChip>

        {disp?.ofertas && (
          <button type="button" className={`uk-chip ${soloOfertas ? "active" : ""}`} onClick={() => setSoloOfertas((v) => !v)}>Ofertas</button>
        )}
        <a className="uk-chip link" href={`${RESERVALO_URL}/productos${q ? `?search=${encodeURIComponent(q)}` : ""}`}>Productos ↗</a>
      </div>

      <div className="uk-resbar">
        <b>{loading ? "Buscando…" : `${shown.length} comercio${shown.length === 1 ? "" : "s"}`}</b>
        <div className="uk-seg">
          <button className={vista === "lista" ? "active" : ""} onClick={() => setVista("lista")}>Lista</button>
          <button className={vista === "mapa" ? "active" : ""} onClick={() => setVista("mapa")}>Mapa</button>
        </div>
      </div>

      {vista === "mapa" ? (
        <MapResults results={shown} />
      ) : (
        <div className="uk-res-grid">
          {!loading && shown.length === 0 && (
            <p className="uk-empty">No encontramos comercios con esos filtros. Probá con otra palabra o quitá filtros.</p>
          )}
          {shown.map((r) => {
            const cover = r.portada_url ?? r.logo_url;
            return (
              <article className="uk-rescard" key={r.id}>
                <Link href={`/comercios/${r.slug}`} className="uk-rescover">
                  {cover && <img src={cover} alt={r.nombre} loading="lazy" decoding="async" />}
                  {r.logo_url && <img className="uk-reslogo" src={r.logo_url} alt="" />}
                </Link>
                <div className="uk-resbody">
                  <h4>
                    <Link href={`/comercios/${r.slug}`}>{r.nombre}</Link>
                    {r.verificado && <span className="uk-verif"><Verified style={{ width: 15, height: 15 }} /></span>}
                  </h4>
                  <div className="uk-resmeta">
                    <span className="uk-pill blue">{MODALIDAD_LABEL[r.modalidad] ?? r.modalidad}</span>
                    {/* Cuando hay una categoría elegida se muestra ÉSA, no el rubro
                        principal del comercio. Los locales son multi-rubro: uno
                        cuyo principal es "Calzado" puede tener también
                        "Celulares", así que al filtrar por celulares la tarjeta
                        decía "Calzado" y el filtro parecía roto estando bien. */}
                    {rubroElegido
                      ? <span className="uk-pill">{rubroElegido}</span>
                      : r.rubro_nombre && <span className="uk-pill">{r.rubro_nombre}</span>}
                    {r.ofertas > 0 && <span className="uk-pill green">{r.ofertas} ofertas</span>}
                  </div>
                  {r.direccion && <div className="uk-resdir"><Pin style={{ width: 13, height: 13 }} />{r.direccion}</div>}
                  <div className="uk-resact">
                    <a className="uk-btn-wa" href={waLink(r.whatsapp, `Hola, te vi en URUKU`)} target="_blank" rel="noopener" onClick={() => registrarLead(r.id, "whatsapp", busquedaId)}>
                      <WhatsApp style={{ width: 15, height: 15 }} /> WhatsApp
                    </a>
                    <a className="uk-btn-ghost" href={comoLlegarHref(r)} target="_blank" rel="noopener">
                      <Pin style={{ width: 15, height: 15 }} /> Cómo llegar
                    </a>
                  </div>
                </div>
              </article>
            );
          })}
        </div>
      )}

      {vista === "lista" && hayMas && !soloOfertas && (
        <div style={{ textAlign: "center", marginTop: 22 }}>
          <button className="uk-btn-ghost" style={{ maxWidth: 200, margin: "0 auto" }} onClick={cargarMas} disabled={cargandoMas}>
            {cargandoMas ? "Cargando…" : "Cargar más"}
          </button>
        </div>
      )}
    </div>
  );
}
