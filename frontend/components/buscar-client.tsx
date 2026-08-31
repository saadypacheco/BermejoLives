"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { MapResults } from "@/components/map-results";
import { buscarComercios, getFiltrosDisponibles, getOfertasDeComercios, getRefinamientos, getRubros, getZonas, type FiltrosDisponibles } from "@/lib/data";
import { type FeedItem, type ResultadoBusqueda, type Rubro, type Zona, MODALIDAD_LABEL, precioFmt, comoLlegarHref, waLink } from "@/lib/types";
import { productosDe } from "@/lib/productos";
import { ReservarBoton } from "@/components/reservar-boton";
import { ReservaBarra } from "@/components/reserva-barra";
import { WhatsApp, Pin, Search, Verified } from "@/components/icons";
import { FilterChip, OptionList } from "@/components/filter-chips";
import { HorarioBadge } from "@/components/horario-badge";
import { registrarLead, logBusqueda } from "@/lib/campo";


export function BuscarClient({ ciudadInicial = "" }: { ciudadInicial?: string }) {
  const [q, setQ] = useState("");
  const [rubro, setRubro] = useState("");
  // El chip de refinamiento elegido, y los que hay para ofrecer. Salen de los
  // resultados de ESTA búsqueda, no de una lista fija.
  const [subcategoria, setSubcategoria] = useState("");
  const [refinamientos, setRefinamientos] = useState<{ subcategoria: string; n: number }[]>([]);
  const [total, setTotal] = useState<number | null>(null);
  const router = useRouter();
  const [modalidad, setModalidad] = useState("");
  const [zona, setZona] = useState("");
  const [precioMax, setPrecioMax] = useState("");
  // Arranca en la ciudad del selector; el parámetro ?ciudad= de la URL la pisa.
  const [ciudad, setCiudad] = useState(ciudadInicial);
  const [soloOfertas, setSoloOfertas] = useState(false);
  const [vista, setVista] = useState<"lista" | "mapa">("lista");
  // El mapa necesita TODOS los que coinciden, no la página cargada. La lista
  // disimula el recorte porque tiene "Ver más"; el mapa no: se veían diez pines
  // sobre un contador que decía 790.
  const [resultsMapa, setResultsMapa] = useState<ResultadoBusqueda[] | null>(null);
  const [cargandoMapa, setCargandoMapa] = useState(false);
  const [results, setResults] = useState<ResultadoBusqueda[]>([]);
  // Las ofertas van aparte de la búsqueda: `buscar_comercios` da una fila por
  // comercio y no tiene dónde meterlas salvo como contador.
  const [ofertas, setOfertas] = useState<Map<string, FeedItem[]>>(new Map());
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

  const filtros = { q, rubro, subcategoria, modalidad, zona, ciudad, precioMax: precioMax ? Number(precioMax) : undefined };

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
    // Texto y categoría SE COMBINAN: "zapatillas" dentro de "Calzado". Antes se
    // borraban entre sí para que no quedara un filtro invisible activo; ahora
    // eso lo resuelve la línea de pastillas, que muestra TODO lo que está
    // filtrando y deja sacarlo de a uno.
    setQ(g("q") ?? "");
    setRubro(g("rubro") ?? "");
    setSubcategoria(g("sub") ?? "");
    setModalidad(g("modalidad") ?? "");
    if (g("vista") === "mapa") setVista("mapa");
  }, [sp]);

  // La URL refleja SIEMPRE lo que se está viendo. Sin esto, la dirección
  // quedaba con la primera búsqueda para siempre: no se podía compartir ni
  // guardar una búsqueda, el botón "atrás" sacaba de la pantalla en vez de
  // deshacer un filtro, y al recargar volvía un estado que contradecía lo que
  // había en la pantalla.
  useEffect(() => {
    const p = new URLSearchParams();
    if (q.trim()) p.set("q", q.trim());
    if (rubro) p.set("rubro", rubro);
    if (subcategoria) p.set("sub", subcategoria);
    if (modalidad) p.set("modalidad", modalidad);
    if (zona) p.set("zona", zona);
    if (ciudad) p.set("ciudad", ciudad);
    if (precioMax) p.set("precio_max", precioMax);
    if (vista === "mapa") p.set("vista", "mapa");
    const nueva = p.toString();
    // Sólo se escribe si de verdad cambió: si no, este efecto y el que LEE la
    // URL se despiertan mutuamente sin parar.
    if (nueva !== sp.toString()) {
      router.replace(nueva ? `/buscar?${nueva}` : "/buscar", { scroll: false });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [q, rubro, subcategoria, modalidad, zona, ciudad, precioMax, vista]);

  useEffect(() => {
    clearTimeout(debounce.current);
    setLoading(true);
    debounce.current = setTimeout(async () => {
      const r = await buscarComercios(filtros, PAGE, 0);
      setResults(r);
      // El total viaja en cada fila; sin resultados, es cero.
      setTotal(r.length ? (r[0].total ?? r.length) : 0);
      // Los chips se piden SIN el refinamiento activo: si se pidieran con él,
      // al tocar uno desaparecerían todos los demás y no habría forma de
      // cambiar de opinión sin borrar la búsqueda.
      getRefinamientos({ ...filtros, subcategoria: "" }).then(setRefinamientos).catch(() => {});
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
  }, [q, rubro, subcategoria, modalidad, zona, ciudad, precioMax]);

  // Se piden de a 500 (el tope de la función) hasta que se acaben. Con 790
  // comercios son dos vueltas; el tope de 4000 es un freno de seguridad para
  // que un filtro roto no descargue la base entera al celular de alguien.
  useEffect(() => {
    if (vista !== "mapa") return;
    let cancelado = false;
    (async () => {
      setCargandoMapa(true);
      const todo: ResultadoBusqueda[] = [];
      for (let desde = 0; desde < 4000; desde += 500) {
        const lote = await buscarComercios(filtros, 500, desde);
        todo.push(...lote);
        if (lote.length < 500) break;
      }
      if (!cancelado) { setResultsMapa(todo); setCargandoMapa(false); }
    })().catch(() => { if (!cancelado) setCargandoMapa(false); });
    return () => { cancelado = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [vista, q, rubro, subcategoria, modalidad, zona, ciudad, precioMax]);

  async function cargarMas() {
    setCargandoMas(true);
    const more = await buscarComercios(filtros, PAGE, results.length);
    setResults((prev) => [...prev, ...more]);
    setHayMas(more.length === PAGE);
    setCargandoMas(false);
  }

  const zonaNom = zonas.find((z) => z.slug === zona)?.nombre;
  const shown = soloOfertas ? results.filter((r) => r.ofertas > 0) : results;

  // Se piden sólo las de los comercios que ya tienen ofertas: el contador viene
  // en la misma búsqueda, así que preguntar por los 800 sería preguntar por 799
  // vacíos. `join` en la dependencia y no el array: el array es nuevo en cada
  // render y dispararía la consulta para siempre.
  const conOfertas = shown.filter((r) => r.ofertas > 0).map((r) => r.id);
  const claveOfertas = conOfertas.join(",");
  useEffect(() => {
    if (!claveOfertas) { setOfertas(new Map()); return; }
    let vigente = true;
    getOfertasDeComercios(claveOfertas.split(","))
      .then((m) => { if (vigente) setOfertas(m); })
      .catch(() => {});
    return () => { vigente = false; };
  }, [claveOfertas]);
  const catChips = [{ slug: "", nombre: "Todos" }, ...rubros];
  const rubroElegido = rubro ? rubros.find((x) => x.slug === rubro)?.nombre ?? null : null;

  function limpiarTodo() {
    setQ(""); setRubro(""); setSubcategoria(""); setModalidad("");
    setZona(""); setPrecioMax(""); setSoloOfertas(false);
  }

  const activos: { clave: string; texto: string; quitar: () => void }[] = [
    q.trim() && { clave: "q", texto: `“${q.trim()}”`, quitar: () => setQ("") },
    rubroElegido && { clave: "rubro", texto: rubroElegido, quitar: () => setRubro("") },
    subcategoria && { clave: "sub", texto: subcategoria, quitar: () => setSubcategoria("") },
    modalidad && { clave: "mod", texto: MODALIDAD_LABEL[modalidad] ?? modalidad, quitar: () => setModalidad("") },
    zonaNom && { clave: "zona", texto: zonaNom, quitar: () => setZona("") },
    precioMax && { clave: "precio", texto: `hasta ${precioMax}`, quitar: () => setPrecioMax("") },
    soloOfertas && { clave: "ofertas", texto: "Con ofertas", quitar: () => setSoloOfertas(false) },
  ].filter(Boolean) as { clave: string; texto: string; quitar: () => void }[];

  return (
    <div className="uk-container uk-buscar">
      <form className="uk-search-live" onSubmit={(e) => e.preventDefault()}>
        <Search style={{ width: 20, height: 20 }} />
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar locales o servicios…" aria-label="Buscar" />
      </form>

      {/* Con una búsqueda escrita, los chips son las SUBCATEGORÍAS que hay entre
          esos resultados. Sin búsqueda, son los rubros — ahí el chip es un menú
          de secciones del sitio y tiene sentido que sea fijo.

          El problema que arregla: buscabas "zapatillas americanas" y los chips
          ofrecían "Óptica" y "Joyería", que son secciones del catálogo y no
          formas de afinar lo que pediste. */}
      {refinamientos.length > 0 ? (
        <div className="uk-chips">
          {refinamientos.map((rf) => (
            <button type="button" key={rf.subcategoria}
                    className={`uk-chip ${subcategoria === rf.subcategoria ? "active" : ""}`}
                    onClick={() => setSubcategoria(subcategoria === rf.subcategoria ? "" : rf.subcategoria)}>
              {rf.subcategoria} <span style={{ opacity: .6 }}>{rf.n}</span>
            </button>
          ))}
        </div>
      ) : null}

      <div className="uk-filters">
        <FilterChip icon="🏷" label="Categoría" value={rubroElegido ?? undefined} active={!!rubro}>
          {(close) => <OptionList items={catChips} sel={rubro} onPick={(v) => { setRubro(v); setSubcategoria(""); close(); }} />}
        </FilterChip>

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
      </div>

      {/* Qué está filtrando, en un solo lugar y con la × para sacarlo.
          Reemplaza al "Todos" ambiguo: había uno en la fila de rubros que
          significaba "todas las categorías" y otro en la de refinamientos que
          significaba "todas las subcategorías de esta búsqueda" — mismo texto,
          mismo aspecto, mismo lugar, distinto efecto. */}
      {activos.length > 0 && (
        <div className="uk-activos">
          <span className="uk-activos-tit">Mostrando</span>
          {activos.map((a) => (
            <button type="button" key={a.clave} className="uk-activo" onClick={a.quitar}>
              {a.texto} <span aria-hidden>×</span>
              <span className="sr-only">Quitar filtro {a.texto}</span>
            </button>
          ))}
          {activos.length > 1 && (
            <button type="button" className="uk-activos-limpiar" onClick={limpiarTodo}>
              Limpiar todo
            </button>
          )}
        </div>
      )}

      <div className="uk-resbar">
        {/* El total REAL, no cuántos se cargaron. Antes decía "30 comercios"
            habiendo 400, y pasaba a "60" al tocar "Ver más". */}
        <b>{loading ? "Buscando…" : `${total ?? shown.length} comercio${(total ?? shown.length) === 1 ? "" : "s"}`}</b>
        <div className="uk-seg">
          <button className={vista === "lista" ? "active" : ""} onClick={() => setVista("lista")}>Lista</button>
          <button className={vista === "mapa" ? "active" : ""} onClick={() => setVista("mapa")}>Mapa</button>
        </div>
      </div>

      {vista === "mapa" ? (
        <>
        {cargandoMapa && (
          <div style={{ padding: "6px 0", fontSize: 12.5, color: "var(--uk-ink-soft)" }}>
            Cargando los {total ?? ""} comercios en el mapa…
          </div>
        )}
        <MapResults results={
          soloOfertas
            ? (resultsMapa ?? results).filter((r) => r.ofertas > 0)
            : (resultsMapa ?? results)
        } />
        </>
      ) : (
        <div className="uk-res-grid">
          {!loading && shown.length === 0 && (
            <p className="uk-empty">No encontramos comercios con esos filtros. Probá con otra palabra o quitá filtros.</p>
          )}
          {shown.map((r) => {
            const cover = r.portada_url ?? r.logo_url;
            const { terminos, resto } = productosDe([r.prod_obs_human, r.prod_det_ia], q);
            const susOfertas = ofertas.get(r.id) ?? [];
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
                    {rubroElegido && <span className="uk-pill">{rubroElegido}</span>}
                    {/* La subcategoría dice mucho más que el rubro amplio:
                        "zapatilla urbana" contra "Calzado". */}
                    {r.subcategoria
                      ? <span className="uk-pill">{r.subcategoria}</span>
                      : !rubroElegido && r.rubro_nombre && <span className="uk-pill">{r.rubro_nombre}</span>}
                    {r.horario && <HorarioBadge horario={r.horario} />}
                  </div>
                  {/* Qué vende: primero lo que coincide con lo buscado y
                      resaltado. Contesta "¿por qué me aparece este local?" sin
                      que el comprador tenga que entrar a averiguarlo. */}
                  {terminos.length > 0 && (
                    <p className="uk-resprod">
                      {terminos.map((t, i) => (
                        <span key={t.texto} className={t.coincide ? "coincide" : undefined}>
                          {t.texto}{i < terminos.length - 1 ? ", " : ""}
                        </span>
                      ))}
                      {resto > 0 && <span className="mas"> +{resto}</span>}
                    </p>
                  )}
                  {r.direccion && <div className="uk-resdir"><Pin style={{ width: 13, height: 13 }} />{r.direccion}</div>}
                  {/* La tira sólo existe si el comercio publicó algo. Hoy no
                      la ve casi nadie y va apareciendo a medida que publiquen —
                      que es justamente lo que hace visible el premio de
                      publicar, sin tener que explicárselo a nadie.
                      Acá va "Reservar" cuando exista: se reserva una oferta, no
                      un local. */}
                  {susOfertas.length > 0 && (
                    <div className="uk-resofertas">
                      {susOfertas.map((o) => (
                        <Link key={o.id} className="uk-resoferta" href={`/comercios/${r.slug}#ofertas`}>
                          {o.imagen_url
                            ? <img src={o.imagen_url} alt={o.titulo ?? ""} loading="lazy" decoding="async" />
                            : <span className="sinfoto" />}
                          <b>{o.titulo ?? "Oferta"}</b>
                          {o.contacto_es_uruku && <span className="uk-marca-uruku">URUKU</span>}
                          {/* Sin precio no decimos "consultar": mandar a
                              preguntar por WhatsApp no es comparar. */}
                          {o.precio != null && <span className="precio">{precioFmt(o.precio, o.moneda)}</span>}
                          <ReservarBoton oferta={o} />
                        </Link>
                      ))}
                      {r.ofertas > susOfertas.length && (
                        <Link className="uk-resoferta mas" href={`/comercios/${r.slug}#ofertas`}>
                          +{r.ofertas - susOfertas.length}<br />más
                        </Link>
                      )}
                    </div>
                  )}
                  <div className="uk-resact">
                    <a className="uk-btn-wa" href={waLink(r.whatsapp, `Hola, te vi en URUKU`)} target="_blank" rel="noopener" onClick={() => registrarLead(r.id, "whatsapp", busquedaId)}>
                      <WhatsApp style={{ width: 15, height: 15 }} /> WhatsApp
                    </a>
                    {/* "Cómo llegar" también es un contacto: nadie pide
                        indicaciones para un local al que no piensa ir. Sin
                        registrarlo, el comercio que se descubre por el mapa y
                        se visita caminando figuraba con cero. */}
                    <a className="uk-btn-ghost" href={comoLlegarHref(r)} target="_blank" rel="noopener"
                       onClick={() => registrarLead(r.id, "mapa", busquedaId)}>
                      <Pin style={{ width: 15, height: 15 }} /> Cómo llegar
                    </a>
                  </div>
                  {/* A la ficha se llegaba sólo por la foto o por el nombre, sin
                      que nada lo dijera. Los dos botones que sí se veían sacan
                      del sitio (WhatsApp, Maps), así que lo único que muestra
                      horario, redes y ofertas era lo único sin puerta.
                      Cuando hay ofertas, el enlace las nombra: es lo que el
                      comprador vino a ver, y lleva directo a esa sección. */}
                  <Link className="uk-resficha" href={r.ofertas > 0 ? `/comercios/${r.slug}#ofertas` : `/comercios/${r.slug}`}>
                    {r.ofertas > 0 ? `Ver ${r.ofertas} ${r.ofertas === 1 ? "oferta" : "ofertas"} y datos del negocio` : "Ver datos del negocio"} →
                  </Link>
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

      <ReservaBarra />
    </div>
  );
}
