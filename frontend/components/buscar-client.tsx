"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { MapResults } from "@/components/map-results";
import { CLAVE_ULTIMA_BUSQUEDA } from "@/components/volver-a-resultados";
import { APAGADAS, buscarComercios, getFiltrosDisponibles, getOfertasDeComercios, getRefinamientos, getRubros, getZonas, type FiltrosDisponibles } from "@/lib/data";
import { type FeedItem, type ResultadoBusqueda, type Rubro, type Zona, MODALIDAD_LABEL, precioFmt, comoLlegarHref, waLink } from "@/lib/types";
import { productosDe } from "@/lib/productos";
import { ReservaBarra } from "@/components/reserva-barra";
import { WhatsApp, Pin, Search, Verified } from "@/components/icons";
import { FilterChip, OptionList } from "@/components/filter-chips";
import { HorarioBadge } from "@/components/horario-badge";
import { registrarLead, logBusqueda } from "@/lib/campo";


export function BuscarClient({ ciudadInicial = "", tilesCiudad = null }: {
  ciudadInicial?: string;
  /** De dónde saca el mapa base esta ciudad. NULL = la del código. */
  tilesCiudad?: { tiles_url?: string | null; tiles_atribucion?: string | null } | null;
}) {
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
  // Timer propio para el registro: el de la búsqueda es corto a propósito y el
  // de la medición tiene que ser largo. Compartirlos obliga a elegir uno mal.
  const logTimer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
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
  // PRIMERAS: lo que se pide para pintar la pantalla. Diez entran de sobra en
  // el primer scroll y llegan mucho antes que treinta — que era el tamaño de
  // página anterior y hacía esperar por veinte tarjetas que nadie estaba
  // mirando todavía.
  //
  // PAGE: el tamaño de cada lote que sigue llegando SOLO, por detrás, mientras
  // la persona ya está leyendo. No hay que apretar nada.
  const PRIMERAS = 10;
  const PAGE = 30;
  // Hasta dónde sigue solo. Más allá de esto queda el botón: mil tarjetas en el
  // DOM de un celular de gama baja no es "cargar en background", es trabarlo.
  const TOPE_AUTO = 90;
  /** A partir de cuántos resultados vale la pena mostrar el conteo de cada chip.
   *
   *  Debajo de esto los números son de un dígito y cuentan lo que no hay: sobre
   *  78 resultados de "comida", el chip decía "hamburguesería 2". Arriba, en
   *  cambio, el número es lo que hace útil al chip — sin búsqueda son los rubros
   *  de la ciudad entera ("almacén 62", "bazar 42") y ahí el conteo dice a
   *  dónde ir.
   *
   *  Es un solo número y se cambia acá. Cuando la ciudad esté cargada de verdad
   *  va a poder bajar. */
  const MIN_PARA_CONTAR = 150;

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
  /** Si el ESTADO ya tiene lo que decía la URL. El efecto que la escribe no
   *  puede correr antes; el porqué está abajo, donde se usa.
   *
   *  Va como estado y no como ref, y eso es el arreglo entero. Con una ref no
   *  servía: los dos efectos corren en el MISMO commit y en orden, así que el
   *  de lectura la ponía en true y el de escritura —que va después— ya la
   *  encontraba puesta, con el estado todavía viejo. El guard no frenaba nada.
   *
   *  Como estado, cambiarla obliga a un render nuevo, y recién en ESE el efecto
   *  de escritura corre con la búsqueda ya cargada. */
  const [urlLeida, setUrlLeida] = useState(false);

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
    // `of=1` es el enlace de "Ofertas" del menú, que antes iba a /mapa.
    setSoloOfertas(g("of") === "1");
    // Recién ahora el efecto de abajo puede escribir la URL. Ver el porqué allá.
    setUrlLeida(true);
  }, [sp]);

  // La URL se LEE antes de escribirse, y esto no es una precaución: es una
  // carrera que se perdía siempre.
  //
  // En el montaje corren los dos efectos en el mismo commit. El de arriba mete
  // `q` en el estado, pero un `setState` dentro de un efecto no cambia el
  // estado que ven los efectos YA programados de ese mismo commit: el de abajo
  // corría con `q = ""`, armaba "ciudad=bermejo" y hacía `router.replace`.
  //
  // Resultado: entrabas a /buscar?q=zapatillas&ciudad=bermejo y la URL se
  // reescribía sola como /buscar?ciudad=bermejo antes de que llegaras a ver
  // nada. El enlace estaba bien; se pisaba al llegar. Y se notó recién ahora
  // porque hasta el "Volver a resultados" nadie entraba a esta pantalla con
  // una búsqueda en la dirección.
  //
  // El primer intento de arreglo usó una ref puesta al final del efecto de
  // lectura, y no sirvió por la misma razón que causa el bug: los dos efectos
  // son del mismo commit y corren en orden, así que la ref ya estaba en true.
  // Tiene que ser ESTADO — cambiarla fuerza un render nuevo, y sólo ahí el
  // estado tiene la búsqueda.
  // La URL refleja SIEMPRE lo que se está viendo. Sin esto, la dirección
  // quedaba con la primera búsqueda para siempre: no se podía compartir ni
  // guardar una búsqueda, el botón "atrás" sacaba de la pantalla en vez de
  // deshacer un filtro, y al recargar volvía un estado que contradecía lo que
  // había en la pantalla.
  useEffect(() => {
    if (!urlLeida) return;
    const p = new URLSearchParams();
    if (q.trim()) p.set("q", q.trim());
    if (rubro) p.set("rubro", rubro);
    if (subcategoria) p.set("sub", subcategoria);
    if (modalidad) p.set("modalidad", modalidad);
    if (zona) p.set("zona", zona);
    if (ciudad) p.set("ciudad", ciudad);
    if (precioMax) p.set("precio_max", precioMax);
    if (vista === "mapa") p.set("vista", "mapa");
    if (soloOfertas) p.set("of", "1");
    const nueva = p.toString();
    // Sólo se escribe si de verdad cambió: si no, este efecto y el que LEE la
    // URL se despiertan mutuamente sin parar.
    if (nueva !== sp.toString()) {
      router.replace(nueva ? `/buscar?${nueva}` : "/buscar", { scroll: false });
    }
    // Y se guarda para el "Volver a resultados" de la ficha. Va acá y no en el
    // enlace de cada tarjeta: la dirección de un negocio se comparte por
    // WhatsApp, y con la búsqueda pegada el que abre el enlace volvería a una
    // búsqueda que nunca hizo.
    try { sessionStorage.setItem(CLAVE_ULTIMA_BUSQUEDA, nueva); } catch { /* modo privado */ }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    // `urlLeida` va en las dependencias: sin él, el efecto no vuelve a correr
    // cuando pasa a true y una URL que no cambia nada más nunca se escribiría.
  }, [urlLeida, q, rubro, subcategoria, modalidad, zona, ciudad, precioMax, vista, soloOfertas]);

  useEffect(() => {
    clearTimeout(debounce.current);
    setLoading(true);
    // Se marca al desmontar o al cambiar la búsqueda. Sin esto, los lotes que
    // seguían viniendo por detrás de la búsqueda ANTERIOR se agregaban a la
    // lista de la nueva: escribías "pan", llegaban diez panaderías, seguías
    // tecleando "pantalón" y abajo aparecían las panaderías igual.
    let cancelado = false;
    debounce.current = setTimeout(async () => {
      const r = await buscarComercios(filtros, PRIMERAS, 0);
      setResults(r);
      // El total viaja en cada fila; sin resultados, es cero.
      setTotal(r.length ? (r[0].total ?? r.length) : 0);
      // Los chips se piden SIN el refinamiento activo: si se pidieran con él,
      // al tocar uno desaparecerían todos los demás y no habría forma de
      // cambiar de opinión sin borrar la búsqueda.
      // No se piden si los chips están apagados: es una consulta más por cada
      // tecleo, sobre una conexión que en Bermejo no sobra, para dibujar algo
      // que no se muestra.
      if (!APAGADAS.filtrosBuscador) {
        getRefinamientos({ ...filtros, subcategoria: "" }).then(setRefinamientos).catch(() => {});
      }
      // Se guarda el id de la búsqueda para atárselo al contacto si la persona
      // termina escribiéndole a alguno de estos comercios.
      // El registro NO va acá adentro, aunque los resultados ya estén.
      //
      // Este efecto corre a los 280ms de dejar de teclear, que es lo correcto
      // para BUSCAR y desastroso para MEDIR: escribir "surtidor" dejaba cuatro
      // búsquedas registradas —"surtidr", "surtu", "sutu", "surut"— y todas
      // caían en "buscado sin resultado", que es la lista que dice a qué rubros
      // salir a buscar comercios. La lista más valiosa del panel quedaba llena
      // de tecleo.
      //
      // Se espera un segundo más. Si la persona seguía escribiendo, el efecto
      // vuelve a correr, el cleanup cancela este timer y el fragmento no se
      // registra nunca.
      clearTimeout(logTimer.current);
      if (q.trim().length >= 3) {
        logTimer.current = setTimeout(() => {
          // El TOTAL, no las diez de la primera página: `resultados` es lo que
          // el panel lee para saber qué se buscó y no se encontró, y con el
          // tamaño de página ahí ese número mediría cuánto pedimos, no cuánto
          // hay.
          logBusqueda(q, r.length ? (r[0].total ?? r.length) : 0, r.map((c) => c.id))
            .then(setBusquedaId);
        }, 900);
      } else {
        setBusquedaId(null);
      }
      setHayMas(r.length === PRIMERAS);
      setLoading(false);

      // Y el resto sigue llegando SOLO, mientras la persona ya está leyendo las
      // primeras diez. Nadie aprieta nada: cuando llega al final del scroll, lo
      // que sigue ya está.
      //
      // Se corta en TOPE_AUTO y ahí queda el botón. Traer los 282 de "moda y
      // ropa" al DOM de un celular de gama baja no es cargar en background: es
      // trabarlo, y encima para mostrar tarjetas que nadie va a mirar.
      let acumulado = r;
      while (!cancelado && acumulado.length >= PRIMERAS && acumulado.length < TOPE_AUTO) {
        const lote = await buscarComercios(filtros, PAGE, acumulado.length);
        if (cancelado) return;
        acumulado = [...acumulado, ...lote];
        setResults(acumulado);
        setHayMas(lote.length === PAGE);
        if (lote.length < PAGE) break;
      }
    }, 280);
    return () => {
      cancelado = true;
      clearTimeout(debounce.current);
      clearTimeout(logTimer.current);
    };
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

  // Sin fila de filtros activos y sin "Limpiar todo": el buscador se lee de una
  // sola pasada, como el de Google. Lo que está filtrando ya se ve donde se
  // eligió —el texto en el buscador, la subcategoría en su chip encendido,
  // rubro / zona / precio / tipo en la etiqueta del propio filtro—, y cada uno
  // se saca desde ahí. Un botón que borra siete cosas a la vez es más rápido de
  // apretar por error que de rehacer.

  /** Si la persona ya pidió algo. El contador de resultados aparece sólo acá:
   *  en la pantalla vacía es de donde se lo sacó, y con razón. */
  const hayBusqueda = Boolean(q.trim() || rubro || subcategoria || modalidad || zona
                              || precioMax || soloOfertas);

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
      {!APAGADAS.filtrosBuscador && refinamientos.length > 0 ? (
        <div className="uk-chips">
          {refinamientos.map((rf) => (
            <button type="button" key={rf.subcategoria}
                    className={`uk-chip ${subcategoria === rf.subcategoria ? "active" : ""}`}
                    onClick={() => setSubcategoria(subcategoria === rf.subcategoria ? "" : rf.subcategoria)}>
              {rf.subcategoria}
              {/* El número, sólo cuando hay de dónde elegir. Es la misma regla
                  por la que el total salió de la barra: un número chico no
                  informa, delata. Buscabas "comida" y el chip decía
                  "hamburguesería 2" — el comprador no aprende nada útil y se
                  entera de que el directorio está casi vacío, que es lo que no
                  conviene contar en la etapa de captación.

                  El chip se queda igual: sigue siendo la forma de afinar
                  "comida" a "hamburguesería". Lo que se va es el conteo. */}
              {total != null && total >= MIN_PARA_CONTAR && (
                <span style={{ opacity: .6 }}> {rf.n}</span>
              )}
            </button>
          ))}
        </div>
      ) : null}


      {/* Los filtros y el interruptor Lista/Mapa comparten fila: eran dos
          renglones y arriba del mapa cada renglón se paga en mapa cortado.

          El total de comercios se fue de acá. Decir "887" antes de que alguien
          busque no le sirve al comprador —no le dice si ESTÁ lo que quiere— y
          en la etapa de captación es un número que no conviene mostrar. */}
      <div className="uk-resbar">
        {/* Los filtros están apagados mientras el catálogo crece
            (APAGADAS.filtrosBuscador). Un filtro sirve cuando hay demasiado y
            hace falta cortar; con lo que hay hoy, afinar "ropa" a "ropa
            femenina 25" no ayuda a decidir, sólo muestra qué poco hay de cada
            cosa. Queda el buscador, el total y la lista. */}
        {!APAGADAS.filtrosBuscador ? (
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
        ) : <span />}
        {/* Cuántos hay, pero SÓLO cuando alguien ya buscó algo.
            El total salió de acá porque decir "887" antes de que la persona
            pida nada no le contesta ninguna pregunta. Después de buscar es al
            revés: la lista trae 30 por página y sin este número "comida" se lee
            como que hay treinta comercios de comida, cuando hay 78. La pantalla
            decía menos de lo que el buscador encontraba. */}
        {/* Siempre que haya una búsqueda, aunque el número sea chico y aunque
            entren todos en pantalla. Es distinto del conteo de los chips: aquél
            cuenta lo que NO hay —"hamburguesería 2" delata el catálogo vacío—
            y éste contesta la pregunta que la persona acaba de hacer. "4
            resultados" es una respuesta; no decir nada, no. */}
        {hayBusqueda && total != null && (
          <span className="uk-total-res">
            {total === 1 ? "1 resultado" : `${total} resultados`}
          </span>
        )}

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
        <MapResults
          results={
            soloOfertas
              ? (resultsMapa ?? results).filter((r) => r.ofertas > 0)
              : (resultsMapa ?? results)
          }
          hayFiltro={Boolean(q.trim() || rubro || subcategoria || modalidad || zona || precioMax || soloOfertas)}
          ciudad={tilesCiudad}
        />
        </>
      ) : (
        <div className="uk-res-grid">
          {!loading && shown.length === 0 && (
            <p className="uk-empty">No encontramos comercios con esos filtros. Probá con otra palabra o quitá filtros.</p>
          )}
          {shown.map((r) => {
            // La miniatura, no la grande: la tarjeta la muestra a ~300px.
            const cover = r.portada_thumb_url ?? r.portada_url ?? r.logo_url;
            const { terminos, resto } = productosDe([r.prod_obs_human, r.prod_det_ia], q);
            const susOfertas = ofertas.get(r.id) ?? [];
            return (
              <article className="uk-rescard" key={r.id}>
                {/* Horizontal y no en columna: entran el doble de resultados en
                    la misma pantalla de celular. En la vertical, la foto se
                    llevaba media pantalla por comercio y comparar tres locales
                    —que es lo que hace cualquiera antes de comprar— eran tres
                    scrolls completos. */}
                <Link href={`/comercios/${r.slug}`} className="uk-rescover">
                  {/* El encuadre lo eligió una persona desde el panel. Sin
                      ajustar va al centro, que es lo que hacía siempre — de una
                      foto vertical de vidriera, el centro suele ser la mitad de
                      abajo del toldo y la mitad de arriba de la puerta. */}
                  {cover
                    ? <img src={cover} alt={r.nombre} loading="lazy" decoding="async"
                           style={r.portada_pos != null
                             ? { objectPosition: `center ${r.portada_pos}%` } : undefined} />
                    : <span className="uk-rescover-sin" aria-hidden>🏪</span>}
                  {/* Una sola chapa arriba de la foto, y la oferta le gana al
                      horario: "¡Oferta!" mueve a alguien a entrar, "Abierto" lo
                      confirma cuando ya decidió. Dos chapas encimadas sobre una
                      foto de 110px no se leen ninguna. */}
                  {susOfertas.length > 0
                    ? <span className="uk-resbadge oferta">¡Oferta!</span>
                    : r.horario ? <HorarioBadge horario={r.horario} /> : null}
                </Link>

                <div className="uk-resbody">
                  <div className="uk-restop">
                    <h4>
                      <Link href={`/comercios/${r.slug}`}>{r.nombre}</Link>
                      {r.verificado && <span className="uk-verif"><Verified style={{ width: 15, height: 15 }} /></span>}
                    </h4>
                  </div>

                  <div className="uk-resmeta">
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
                    <span className="uk-pill blue">{MODALIDAD_LABEL[r.modalidad] ?? r.modalidad}</span>
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

                  {/* El precio de la oferta más barata, en la tarjeta. Es el
                      dato que hace entrar y estaba a dos toques de distancia,
                      dentro de la ficha. Sin precio no se inventa un "desde":
                      muchos acá no lo publican porque se les mueve con el
                      cambio del día. */}
                  {(() => {
                    const conPrecio = susOfertas.filter((o) => o.precio != null);
                    if (conPrecio.length === 0) return null;
                    const barata = conPrecio.reduce((a, b) => (a.precio! <= b.precio! ? a : b));
                    return (
                      <Link className="uk-resdesde" href={`/comercios/${r.slug}#ofertas`}>
                        {barata.titulo ? `${barata.titulo} · ` : ""}
                        <b>{precioFmt(barata.precio!, barata.moneda)}</b>
                      </Link>
                    );
                  })()}

                  {r.direccion && <div className="uk-resdir"><Pin style={{ width: 13, height: 13 }} />{r.direccion}</div>}

                  {/* Los dos contactos como íconos y la ficha como botón: los
                      tres entraban en un renglón sólo así, y son las tres cosas
                      que alguien hace desde acá. */}
                  <div className="uk-resact">
                    <a className="uk-resic" title="WhatsApp" aria-label="WhatsApp"
                       href={waLink(r.whatsapp, `Hola, te vi en URUKU`)} target="_blank" rel="noopener"
                       onClick={() => registrarLead(r.id, "whatsapp", busquedaId)}>
                      <WhatsApp style={{ width: 17, height: 17 }} />
                    </a>
                    {/* "Cómo llegar" también es un contacto: nadie pide
                        indicaciones para un local al que no piensa ir. Sin
                        registrarlo, el comercio que se descubre por el mapa y
                        se visita caminando figuraba con cero. */}
                    <a className="uk-resic" title="Cómo llegar" aria-label="Cómo llegar"
                       href={comoLlegarHref(r)} target="_blank" rel="noopener"
                       onClick={() => registrarLead(r.id, "mapa", busquedaId)}>
                      <Pin style={{ width: 17, height: 17 }} />
                    </a>
                    {/* A la ficha se llegaba sólo por la foto o por el nombre, sin
                        que nada lo dijera. Los dos botones que sí se veían sacan
                        del sitio (WhatsApp, Maps), así que lo único que muestra
                        horario, redes y ofertas era lo único sin puerta. */}
                    <Link className="uk-resficha" href={r.ofertas > 0 ? `/comercios/${r.slug}#ofertas` : `/comercios/${r.slug}`}>
                      {r.ofertas > 0 ? `Ver ${r.ofertas} ${r.ofertas === 1 ? "oferta" : "ofertas"}` : "Ver negocio"} →
                    </Link>
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

      <ReservaBarra />
    </div>
  );
}
