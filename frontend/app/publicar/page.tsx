"use client";

import { useEffect, useRef, useState } from "react";
import {
  agenteLogin, getAgenteToken, clearAgente, altaComercioCampo,
  misComercios, miComercio, eliminarComercioAgente, type ComercioAgente,
  listarLugares, crearLugar, editarLugar, subirPortadaLugar, subirVideoLugar, type Lugar,
  getAgenteEmail, ciudadDelAgente,
} from "@/lib/campo";
import { duracionVideo } from "@/lib/upload";
import { CapturaWhatsapp } from "@/components/captura-whatsapp";
import { CompletarComercio, apiGaleriaCampo } from "@/components/completar-comercio";
import { GaleriaUploader } from "@/components/galeria-uploader";
import { getCiudades, getRubros } from "@/lib/data";
import type { Ciudad, Rubro } from "@/lib/types";
import { Pin, User, Arrow, Edit } from "@/components/icons";
import { comprimirImagen } from "@/lib/imagen";
import { useObjectUrl } from "@/lib/object-url";
import { medirMemoria } from "@/lib/memoria";
import { AdminMap } from "@/components/admin-map";
import { geoErrorMsg, metros } from "@/lib/geo";
import { YaCargadosAca, RADIO_YA_CARGADO_M, type EstadoLista } from "@/components/ya-cargados-aca";
import { aCercanos, cercanosGuardados, listaEnMemoria, olvidarLista, recordarLista, type ComercioCercano } from "@/lib/campo-cache";
import { PermisoUbicacion } from "@/components/permiso-ubicacion";
import { Ic } from "@/components/ic";
import { ClaveUnaVez } from "@/components/clave-una-vez";
import { encolarAlta, sincronizarPendientes, listarPendientes,
         descartarPendiente, esIrrecuperable, type AltaPendiente } from "@/lib/offline-altas";

const AVISO_CLAVE_AGENTE = "Dásela en mano al dueño: es para entrar a su panel. No la anotes en el volante.";

type ClavePorEntregar = { nombre: string; clave: string };

/** Las claves de altas que subieron DESPUÉS (estaban guardadas sin señal). El
 *  servidor las entrega sólo en la respuesta de la subida: si no se ven acá, no
 *  hay otra oportunidad. Quedan en pantalla hasta que se marcan como entregadas. */
function ClavesPorEntregar({ claves, onEntregada }: { claves: ClavePorEntregar[]; onEntregada: (clave: string) => void }) {
  if (claves.length === 0) return null;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10, marginBottom: 12 }}>
      {claves.map((c) => (
        <ClaveUnaVez key={c.clave + c.nombre} compacta clave={c.clave} titulo={`Clave de ${c.nombre}`}
          aviso={`Se subió recién. ${AVISO_CLAVE_AGENTE}`} onListo={() => onEntregada(c.clave)} textoListo="Ya se la di al dueño" />
      ))}
    </div>
  );
}

// Prefijo telefónico según país
// Prefijo telefónico para wa.me. Argentina lleva el 9 de móvil (549…): sin él
// el link no abre ningún chat. Bermejo es frontera, así que hay comercios
// con número de los dos países y el prefijo tiene que poder cambiarse a mano.
const PREFIJO: Record<string, string> = { Bolivia: "591", Argentina: "549" };

// ─────────────────────────────────────────────
export default function CampoPage() {
  const [authed, setAuthed] = useState(false);
  const [vista, setVista] = useState<"form" | "lista">("form");
  // A qué entrar en «Comercios de mi ciudad»: abrir un comercio para editarlo
  // (desde el aviso «ya cargado» del alta) o con un filtro puesto.
  const [destino, setDestino] = useState<DestinoLista | null>(null);
  useEffect(() => {
    setAuthed(Boolean(getAgenteToken()));
    // Entrada directa desde el shortcut de la PWA (mantener apretado el ícono).
    // Se lee de window en vez de useSearchParams para no arrastrar un Suspense.
    if (new URLSearchParams(window.location.search).get("vista") === "mis-comercios") {
      setVista("lista");
    }
  }, []);
  if (!authed) return <Login onOk={() => setAuthed(true)} />;
  const onLogout = () => { clearAgente(); olvidarLista(); setAuthed(false); };
  const irALista = (d: DestinoLista | null = null) => { setDestino(d); setVista("lista"); };
  if (vista === "lista") return <MisComercios destino={destino} onVolver={() => { setDestino(null); setVista("form"); }} onLogout={onLogout} />;
  return <FormCampo onLogout={onLogout} onVerMisComercios={irALista} />;
}

// ─────────────────────────────────────────────
function normTxtA(s: string): string {
  return s.toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
}
// Motivos por los que un comercio del agente está incompleto (para completarlo).
function agenteIncompleto(c: ComercioAgente): string[] {
  const r: string[] = [];
  const nombre = (c.nombre ?? "").trim();
  const rubroNombre = (c.rubros?.nombre ?? "").trim();
  if (!nombre || nombre.toLowerCase() === "comercio" || (!!rubroNombre && nombre.toLowerCase() === rubroNombre.toLowerCase())) r.push("sin nombre");
  if (!c.portada_url) r.push("sin foto");
  if (!c.whatsapp && !c.telefono) r.push("sin contacto");
  if (!c.rubros) r.push("sin rubro");
  return r;
}

type FiltroAg = "cerca" | "todos" | "pendientes" | "verificados" | "incompletos" | "sinhorario";

/** Adónde llevar al agente al abrir «Comercios de mi ciudad». */
type DestinoLista = { editarId?: string; filtro?: FiltroAg };

/** «Sin horario» = el campo vacío, el mismo criterio que usa el admin. */
function sinHorario(c: ComercioAgente): boolean {
  return !(c.horario ?? "").trim();
}

/** Hasta dónde llega «cerca mío»: media cuadra para cada lado. Más que esto y
 *  en una galería aparecen los sesenta puestos del pasillo de al lado. */
const RADIO_CERCA_M = 120;
type OrdenAg = "recientes" | "alfabetico" | "estado";

function MisComercios({ destino, onVolver, onLogout }: { destino: DestinoLista | null; onVolver: () => void; onLogout: () => void }) {
  // Arranca con lo último que se vio (si hay) y se actualiza al llegar la lista.
  const [items, setItems] = useState<ComercioAgente[] | null>(() => listaEnMemoria());
  const [rubros, setRubros] = useState<Rubro[]>([]);
  const [err, setErr] = useState("");
  // El comercio que se está completando. Sólo el id: el comercio en sí se busca
  // en `items` cada vez, así lo que se guarda se ve al instante en «Le falta» y
  // en la lista (y el comercio sale del filtro «Sin horario» sin recargar nada).
  const [editando, setEditando] = useState<{ id: string; abrirEn: "horario" | "arriba" } | null>(null);
  const [lugares, setLugares] = useState<Lugar[]>([]);
  // Dónde estaba la lista al abrir un comercio: se vuelve exactamente ahí. Al
  // recorrer una cuadra comercio por comercio, perder el lugar es perder el hilo.
  const scrollLista = useRef(0);
  const restaurarScroll = useRef(false);
  const [borrando, setBorrando] = useState<string | null>(null);
  const [q, setQ] = useState("");
  const [filtro, setFiltro] = useState<FiltroAg>(destino?.filtro && destino.filtro !== "cerca" ? destino.filtro : "todos");
  // Un solo comercio a la vista: el que se eligió con «Es este» en el alta. La
  // lista de la ciudad tiene cientos y el elegido podría quedar fuera de las
  // primeras 50; así se llega a él con un toque, sin buscarlo.
  const [enfocado, setEnfocado] = useState<string | null>(destino?.editarId ?? null);
  // DÓNDE ESTOY PARADO. Es lo que convierte la lista en una herramienta de
  // vereda: el agente ve los locales de esa cuadra —los haya cargado él o el
  // otro agente de la ciudad—, se los muestra al comerciante y corrige ahí
  // mismo lo que esté mal. Sin esto hay que acordarse del nombre para buscarlo.
  const emailAgente = getAgenteEmail();
  const [aqui, setAqui] = useState<{ lat: number; lng: number } | null>(null);
  const [geoErr, setGeoErr] = useState("");
  const [buscandoGeo, setBuscandoGeo] = useState(false);

  function ubicarme(activar = true) {
    if (!("geolocation" in navigator)) { setGeoErr("Este teléfono no da la ubicación."); return; }
    setGeoErr(""); setBuscandoGeo(true);
    navigator.geolocation.getCurrentPosition(
      (p) => { setAqui({ lat: p.coords.latitude, lng: p.coords.longitude }); setBuscandoGeo(false); if (activar) setFiltro("cerca"); },
      // El permiso denegado se DICE. Un botón que no hace nada parece roto.
      (e) => { setBuscandoGeo(false); setGeoErr(e.code === 1
        ? "Diste que no al permiso de ubicación. Activalo en el candado de la barra de direcciones y volvé a tocar."
        : "No se pudo tomar la ubicación. Probá al aire libre."); },
      { enableHighAccuracy: true, timeout: 12000, maximumAge: 30000 },
    );
  }
  const [orden, setOrden] = useState<OrdenAg>("recientes");
  const [vista, setVista] = useState<"lista" | "mapa">("lista");
  const [limitVis, setLimitVis] = useState(50);

  const [fresca, setFresca] = useState(false);   // ya llegó la lista del servidor (no sólo la de memoria)
  const abiertoRef = useRef(false);
  const cargar = () => misComercios()
    .then((xs) => { recordarLista(xs); setItems(xs); setErr(""); setFresca(true); })
    .catch((e) => setErr(e instanceof Error ? e.message : "Error"));
  useEffect(() => {
    cargar(); getRubros().then(setRubros);
    // «Ver los N» del alta: entra con «Acá» puesto, que es lo que pide el GPS.
    if (destino?.filtro === "cerca") ubicarme();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  // Mantiene la lista guardada al día cuando se edita o se da de baja uno.
  useEffect(() => { if (items) recordarLista(items); }, [items]);
  // «Es este»: apenas llega la lista se abre el editor de ese comercio.
  useEffect(() => {
    if (!destino?.editarId || !items || abiertoRef.current) return;
    const c = items.find((x) => x.id === destino.editarId);
    if (c) { abiertoRef.current = true; setEditando({ id: c.id, abrirEn: "arriba" }); }
    // Recién cuando llegó la lista del servidor se puede decir que ya no está
    // (baja o de otra ciudad): se muestra la lista normal.
    else if (fresca) { abiertoRef.current = true; setEnfocado(null); }
  }, [items, fresca, destino]);
  useEffect(() => { setLimitVis(50); }, [filtro, q, orden]);

  async function eliminar(c: ComercioAgente) {
    if (!window.confirm(`¿Dar de baja "${c.nombre}"? Deja de aparecer en URUKU, pero el registro no se borra.`)) return;
    setBorrando(c.id);
    try { await eliminarComercioAgente(c.id); setItems((prev) => prev?.filter((x) => x.id !== c.id) ?? prev); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo eliminar"); }
    finally { setBorrando(null); }
  }

  const todos = items ?? [];
  // El comercio que se está completando, siempre en su última versión.
  const comercioEdit = editando ? todos.find((x) => x.id === editando.id) ?? null : null;

  function abrir(c: ComercioAgente) {
    scrollLista.current = window.scrollY;
    // Desde «Sin horario» la pantalla abre con el horario a la vista.
    setEditando({ id: c.id, abrirEn: filtro === "sinhorario" ? "horario" : "arriba" });
  }
  function cerrar() { restaurarScroll.current = true; setEditando(null); }
  // Al volver, la lista reaparece donde estaba. En un efecto y no justo después
  // del setState: recién acá el DOM de la lista ya volvió a tener altura.
  useEffect(() => {
    if (!editando && restaurarScroll.current) { restaurarScroll.current = false; window.scrollTo(0, scrollLista.current); }
  }, [editando]);
  // Los mercados/galerías para el selector, de la ciudad del comercio abierto.
  const ciudadEdit = comercioEdit?.ciudades?.slug ?? ciudadDelAgente ?? "bermejo";
  useEffect(() => {
    if (!editando) return;
    let vivo = true;
    listarLugares(ciudadEdit).then((l) => { if (vivo) setLugares(l); }).catch(() => {});
    return () => { vivo = false; };
  }, [editando?.id, ciudadEdit]); // eslint-disable-line react-hooks/exhaustive-deps

  const nVerificados = todos.filter((c) => c.verificado).length;
  const nPend = todos.length - nVerificados;
  const nIncompletos = todos.filter((c) => agenteIncompleto(c).length > 0).length;
  const nSinHorario = todos.filter(sinHorario).length;

  // A: filtro por estado → B: incompletos → búsqueda multi-campo → G: orden
  const porEstado = filtro === "todos" ? todos
    : filtro === "pendientes" ? todos.filter((c) => !c.verificado)
    : filtro === "verificados" ? todos.filter((c) => c.verificado)
    : filtro === "sinhorario" ? todos.filter(sinHorario)
    : todos.filter((c) => agenteIncompleto(c).length > 0);
  const nq = normTxtA(q.trim());
  const buscadas = enfocado ? todos.filter((c) => c.id === enfocado)
    : !nq ? porEstado : porEstado.filter((c) =>
    [c.nombre, c.direccion, c.whatsapp, c.telefono, c.rubros?.nombre].map((x) => normTxtA(x ?? "")).join(" ").includes(nq));
  const filtradas = [...buscadas].sort((a, b) => {
    if (orden === "alfabetico") return (a.nombre ?? "").localeCompare(b.nombre ?? "");
    if (orden === "estado") return Number(a.verificado) - Number(b.verificado);
    return (b.created_at ?? "").localeCompare(a.created_at ?? "");
  });
  // «Cerca» ordena por distancia, no por fecha: lo primero de la lista tiene
  // que ser el local que el agente tiene delante.
  const conDistancia = aqui
    ? filtradas
        .map((c) => ({ c, d: c.lat != null && c.lng != null ? metros(aqui.lat, aqui.lng, c.lat, c.lng) : Infinity }))
        .sort((x, y) => x.d - y.d)
    : filtradas.map((c) => ({ c, d: Infinity }));
  const listaFinal = filtro === "cerca" ? conDistancia.filter((x) => x.d <= RADIO_CERCA_M) : conDistancia;
  const visibles = (filtro === "cerca" ? listaFinal : conDistancia).slice(0, limitVis).map((x) => x.c);
  const distanciaDe = new Map(conDistancia.map((x) => [x.c.id, x.d]));

  const nCerca = aqui ? conDistancia.filter((x) => x.d <= RADIO_CERCA_M).length : 0;
  const chips: { key: FiltroAg; label: React.ReactNode; n: number; amber?: boolean }[] = [
    { key: "cerca", label: <><Ic n="ubicacion" s={13} /> {buscandoGeo ? "Ubicando…" : "Acá"}</>, n: nCerca },
    { key: "todos", label: "Todos", n: todos.length },
    { key: "pendientes", label: "Pendientes", n: nPend },
    { key: "verificados", label: "Verificados", n: nVerificados },
    { key: "incompletos", label: "Incompletos", n: nIncompletos, amber: true },
    { key: "sinhorario", label: <><Ic n="reloj" s={13} /> Sin horario</>, n: nSinHorario, amber: true },
  ];

  return (
    <div className="campo-wrap">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <span className="eyebrow"><Pin style={{ width: 13, height: 13 }} /> Comercios de mi ciudad</span>
          {items && <div style={{ fontSize: 12, color: "var(--neon)" }}>{items.length} en total</div>}
        </div>
        <button className="link-more" onClick={onLogout} style={{ padding: "6px 12px" }}>Salir</button>
      </div>

      {/* LA PANTALLA «Completar comercio» ocupa el lugar de la lista. La lista no
          se desmonta, se esconde: así sus filtros, la búsqueda y dónde estaba
          parado siguen ahí al volver. */}
      {comercioEdit && editando && (
        <CompletarComercio
          key={comercioEdit.id}
          comercio={comercioEdit} rubros={rubros} lugares={lugares}
          abrirEn={editando.abrirEn}
          onVolver={cerrar}
          onGuardado={(patch) => setItems((prev) => prev?.map((x) => (x.id === comercioEdit.id ? { ...x, ...patch } : x)) ?? prev)}
        />
      )}

      <div style={{ display: comercioEdit ? "none" : undefined }}>
      <div style={{ display: "flex", gap: 8, marginBottom: 12 }}>
        <button className="link-more" style={{ display: "flex", alignItems: "center", gap: 6 }} onClick={onVolver}>
          <Arrow style={{ width: 15, height: 15, transform: "rotate(180deg)" }} /> Volver
        </button>
        <button className="btn btn-ghost" style={{ flex: 1 }} onClick={onVolver}>+ Cargar otro comercio</button>
      </div>

      {/* Buscador (A) + orden (G) + vista lista/mapa (D) */}
      <div style={{ display: "flex", gap: 8, marginBottom: 10, flexWrap: "wrap", alignItems: "center" }}>
        <input className="adm-input" style={{ flex: 1, minWidth: 160 }} value={q} onChange={(e) => { setQ(e.target.value); setEnfocado(null); }}
          placeholder="Buscar por nombre, dirección, teléfono…" />
        <select className="adm-input" style={{ width: "auto" }} value={orden} onChange={(e) => setOrden(e.target.value as OrdenAg)}>
          <option value="recientes">Recientes</option>
          <option value="alfabetico">A → Z</option>
          <option value="estado">Pendientes primero</option>
        </select>
        <div style={{ display: "flex", border: "1px solid var(--stroke)", borderRadius: 8, overflow: "hidden" }}>
          {(["lista", "mapa"] as const).map((v) => (
            <button key={v} onClick={() => setVista(v)}
              style={{ padding: "8px 12px", fontSize: 13, border: "none",
                background: vista === v ? "rgba(57,255,158,.12)" : "transparent",
                color: vista === v ? "var(--neon)" : "var(--txt-2)", fontWeight: vista === v ? 700 : 400 }}>
              {v === "lista" ? "Lista" : "Mapa"}
            </button>
          ))}
        </div>
      </div>

      {/* Filtros por estado (B: incluye Incompletos) */}
      <div style={{ display: "flex", gap: 6, marginBottom: 14, flexWrap: "wrap" }}>
        {/* La ubicación se pide al tocar «Acá», no al abrir la pantalla: un
            permiso que salta solo al entrar se rechaza, y después hay que
            explicarle a alguien cómo desbloquearlo desde el candado. */}
        {chips.map(({ key, label, n, amber }) => {
          const activo = filtro === key;
          const col = amber ? "var(--amber)" : "var(--neon)";
          return (
            <button key={key} onClick={() => { setEnfocado(null); if (key === "cerca" && !aqui) ubicarme(); else setFiltro(key); }}
              style={{ padding: "5px 12px", borderRadius: 20, border: "1px solid", fontSize: 12.5,
                borderColor: activo ? col : "var(--stroke)",
                background: activo ? "rgba(57,255,158,.10)" : "transparent",
                color: activo ? col : "var(--txt-2)", fontWeight: activo ? 700 : 400 }}>
              {label} ({n})
            </button>
          );
        })}
      </div>

      {enfocado && (
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, marginBottom: 12, padding: "9px 12px", borderRadius: 12, border: "1px solid var(--neon)", background: "rgba(57,255,158,.08)", fontSize: 13 }}>
          <span><Ic n="comercios" s={14} /> Completando el comercio que ya estaba cargado.</span>
          <button type="button" className="link-more" style={{ flexShrink: 0, minHeight: 36 }} onClick={() => setEnfocado(null)}>Ver todos</button>
        </div>
      )}
      {filtro === "sinhorario" && !enfocado && (
        <p style={{ color: "var(--txt-3)", fontSize: 12.5, margin: "0 0 12px" }}>
          {aqui
            ? <><Ic n="reloj" s={12} /> Ordenados por distancia: completá el horario caminando la cuadra.</>
            : <>
                Para completarlos caminando la cuadra, ordenalos por distancia.{" "}
                <button type="button" className="link-more" style={{ minHeight: 36, padding: "0 4px" }} disabled={buscandoGeo} onClick={() => ubicarme(false)}>
                  <Ic n="ubicacion" s={12} /> {buscandoGeo ? "Ubicando…" : "Usar mi ubicación"}
                </button>
              </>}
        </p>
      )}
      {geoErr && <p style={{ color: "var(--pink)", fontSize: 12.5, margin: "0 0 12px" }}><Ic n="aviso" s={12} /> {geoErr}</p>}

      {err && <p style={{ color: "var(--pink)", fontSize: 13 }}>{err}</p>}
      {!items && !err && <p style={{ color: "var(--txt-3)" }}>Cargando…</p>}
      {items && items.length === 0 && <p style={{ color: "var(--txt-3)" }}>Todavía no cargaste ningún comercio.</p>}
      {items && items.length > 0 && filtradas.length === 0 && <p style={{ color: "var(--txt-3)" }}>Sin resultados para ese filtro/búsqueda.</p>}

      {/* Vista MAPA (D): tocá un pin y se abre «Completar comercio» (ideal para los sin nombre).
          Mientras hay un comercio abierto el mapa se desmonta: Leaflet no se
          lleva bien con un contenedor escondido. */}
      {vista === "mapa" ? (
        comercioEdit ? null : (
          <AdminMap
            comercios={filtradas.map((c) => ({ id: c.id, nombre: c.nombre, lat: c.lat, lng: c.lng, rubro_slug: c.rubros?.slug ?? null, incompleto: agenteIncompleto(c).length > 0, lugar_id: c.lugar_id, lugar_nombre: c.lugares?.nombre ?? null, lugar_lat: c.lugares?.lat ?? null, lugar_lng: c.lugares?.lng ?? null, lugar_portada_thumb: c.lugares?.portada_thumb_url ?? null }))}
            onSelect={(id) => { const c = todos.find((x) => x.id === id); if (c) abrir(c); }}
          />
        )
      ) : (
        <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
          {visibles.map((c) => {
            const motivos = agenteIncompleto(c);
            return (
            <div key={c.id} className="glass" style={{ padding: 14, borderRadius: 14, display: "flex", flexDirection: "column", gap: 10 }}>
              <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
                <div style={{ width: 48, height: 48, borderRadius: 10, overflow: "hidden", background: "var(--panel)", flexShrink: 0, display: "grid", placeItems: "center", fontSize: 20 }}>
                  {(c.portada_thumb_url || c.portada_url) ? <img src={(c.portada_thumb_url || c.portada_url) as string} alt="" style={{ width: "100%", height: "100%", objectFit: "cover" }} /> : <Ic n="comercios" s={22} />}
                </div>
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ fontWeight: 700, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{c.nombre || "Sin nombre"}</div>
                  <div style={{ fontSize: 12.5, color: "var(--txt-3)" }}>{c.rubros?.nombre ?? "Sin rubro"}{c.lugares?.nombre ? ` · ${c.lugares.nombre}${c.puesto ? ` #${c.puesto}` : ""}` : c.calle ? ` · ${c.calle}` : c.direccion ? ` · ${c.direccion}` : ""}</div>
                  {/* A cuántos pasos está. Es lo que permite reconocer en la
                      vereda cuál de los tres locales de ropa es éste. */}
                  {aqui && Number.isFinite(distanciaDe.get(c.id) ?? Infinity) && (
                    <div style={{ fontSize: 11.5, color: "var(--neon)", fontWeight: 700 }}>
                      a {Math.round(distanciaDe.get(c.id) as number)} m
                    </div>
                  )}
                  {/* De quién es la ficha: con dos agentes por ciudad, saber si
                      la cargó el otro evita «esto no lo hice yo, ¿lo toco?». */}
                  {/* De otra ciudad: lo cargó él fuera de su zona. Sin esto,
                      ver un comercio de Bermejo en la lista de un agente de
                      Santa Cruz parece un error del sistema. */}
                  {c.ciudades?.slug && ciudadDelAgente && c.ciudades.slug !== ciudadDelAgente && (
                    <div style={{ fontSize: 11, color: "var(--amber)", fontWeight: 700 }}>
                      <Ic n="ubicacion" s={12} /> {c.ciudades.nombre} — fuera de tu ciudad
                    </div>
                  )}
                  {c.cargado_por && c.cargado_por !== emailAgente && (
                    <div style={{ fontSize: 11, color: "var(--txt-3)" }}>cargado por {c.cargado_por.split("@")[0]}</div>
                  )}
                </div>
                <span style={{ fontSize: 11, fontWeight: 700, padding: "3px 9px", borderRadius: 999, color: c.verificado ? "var(--neon)" : "var(--amber)", background: c.verificado ? "rgba(57,255,158,.12)" : "rgba(255,176,32,.12)" }}>
                  {c.verificado ? "Verificado" : "Pendiente"}
                </span>
              </div>
              {motivos.length > 0 && (
                <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
                  {motivos.map((m) => (
                    <span key={m} style={{ fontSize: 11, color: "var(--amber)", border: "1px dashed var(--amber)", padding: "1px 7px", borderRadius: 10 }}><Ic n="aviso" s={11} /> {m}</span>
                  ))}
                </div>
              )}
              <div style={{ display: "flex", gap: 8 }}>
                {/* Un toque y se abre «Completar comercio». En «Sin horario» el
                    botón dice lo que va a pasar: abre con el horario a la vista. */}
                <button className="btn btn-sm" style={{ flex: 1, minHeight: 44, border: "1px solid var(--stroke)" }} onClick={() => abrir(c)}>
                  {filtro === "sinhorario"
                    ? <><Ic n="reloj" s={14} /> Cargar horario</>
                    : <><Edit style={{ width: 14, height: 14 }} /> Editar</>}
                </button>
                <button className="btn btn-sm" style={{ flex: 1, border: "1px solid var(--stroke)", color: "var(--pink)" }} disabled={borrando === c.id} onClick={() => eliminar(c)}>
                  {borrando === c.id ? "Eliminando…" : "Eliminar"}
                </button>
              </div>
            </div>
            );
          })}
          {filtradas.length > limitVis && (
            <button className="btn btn-ghost" onClick={() => setLimitVis((n) => n + 50)}>
              Ver más ({filtradas.length - limitVis} restantes)
            </button>
          )}
        </div>
      )}
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
function Login({ onOk }: { onOk: () => void }) {
  // Vacío, no precargado. Había un correo de prueba fijo acá y el navegador lo
  // mostraba como si fuera el del agente: se tipeaba la contraseña correcta
  // sobre el usuario equivocado y el rechazo no decía cuál de los dos estaba
  // mal. Con el campo vacío, el que entra pone los dos y sabe qué puso.
  const [email, setEmail] = useState("");
  const [pass, setPass]   = useState("");
  const [err, setErr]     = useState("");

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    try { await agenteLogin(email, pass); onOk(); }
    catch { setErr("Credenciales incorrectas. ¿Backend corriendo?"); }
  }

  return (
    <div className="campo-wrap">
      <span className="eyebrow"><User style={{ width: 14, height: 14 }} /> Agente de campo</span>
      <h1 style={{ fontSize: 26, margin: "8px 0 4px" }}>URUKU · Carga de comercios</h1>
      <p style={{ color: "var(--txt-3)", marginBottom: 20, fontSize: 14 }}>Ingresá para registrar comercios, hoteles, casas de cambio y más.</p>
      <form onSubmit={submit} className="glass" style={{ padding: 20, borderRadius: 16, display: "flex", flexDirection: "column", gap: 12 }}>
        <input className="adm-input" type="email" inputMode="email" autoCapitalize="none"
                 autoCorrect="off" spellCheck={false} autoComplete="username"
                 value={email} onChange={(e) => setEmail(e.target.value)} placeholder="tunombre@uruku.bo" />
        <input className="adm-input" type="password" value={pass} onChange={(e) => setPass(e.target.value)} placeholder="Contraseña" />
        {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
        <button className="btn btn-primary" type="submit">Entrar</button>
      </form>
    </div>
  );
}

/** «Completar comercio» al final del alta. El comercio recién creado no está en
 *  la lista que ya tiene la pantalla, así que se pide ESE comercio solo (no la
 *  ciudad entera: con la señal de la calle eso fallaba) y de ahí en adelante es
 *  la misma pantalla de siempre. Si igual no se puede abrir, la galería se
 *  muestra suelta: las fotos del local se sacan ahora o no se sacan. */
function CompletarTrasAlta({ comercioId, whatsapp, rubros, lugares }: {
  comercioId: string; whatsapp: string | null; rubros: Rubro[]; lugares: Lugar[];
}) {
  const [c, setC] = useState<ComercioAgente | null>(null);
  const [err, setErr] = useState("");
  const [cargando, setCargando] = useState(true);

  const cargar = () => {
    setCargando(true); setErr("");
    miComercio(comercioId)
      .then(setC)
      .catch((e) => setErr(e instanceof TypeError || !navigator.onLine
        ? "Sin conexión: no se pudo abrir la pantalla para completar. El comercio ya está guardado."
        : e instanceof Error ? e.message : "No se pudo cargar"))
      .finally(() => setCargando(false));
  };
  useEffect(() => { cargar(); /* eslint-disable-next-line react-hooks/exhaustive-deps */ }, [comercioId]);

  const caja: React.CSSProperties = { textAlign: "left", marginBottom: 12, padding: 12, borderRadius: 12, background: "var(--panel)", border: "1px solid var(--stroke)", fontSize: 13 };
  if (!c) {
    return (
      <div style={caja}>
        {cargando && <span style={{ color: "var(--txt-3)" }}><Ic n="reloj" s={13} /> Preparando «Completar comercio»…</span>}
        {err && (
          <div role="alert" style={{ color: "var(--pink)" }}>
            <Ic n="aviso" s={13} /> {err}{" "}
            <button type="button" className="link-more" style={{ minHeight: 44 }} disabled={cargando} onClick={cargar}>Reintentar</button>
          </div>
        )}
        {err && (
          <div style={{ marginTop: 12 }}>
            <div className="campo-lbl">Fotos y videos del local</div>
            <GaleriaUploader comercioId={comercioId} api={apiGaleriaCampo(comercioId)} />
          </div>
        )}
      </div>
    );
  }
  // El número puede haberse cargado en la tarjeta de arriba después de bajar el comercio.
  const visto: ComercioAgente = { ...c, whatsapp: c.whatsapp || whatsapp };
  return (
    <div style={{ marginBottom: 12 }}>
      <CompletarComercio
        comercio={visto} rubros={rubros} lugares={lugares} sinWhatsapp
        onGuardado={(patch) => setC((prev) => (prev ? { ...prev, ...patch } : prev))}
      />
    </div>
  );
}

// ─────────────────────────────────────────────
const EMPTY = { nombre: "", cel: "", modalidad: "mayorista", direccion: "", prodObs: "" };

// Editor del mercado/galería (nombre + tipo + foto de portada + video de recorrido).
// El agente está parado ahí: es el mejor momento para la portada y el recorrido.
function MercadoEditor({ lugar, onClose, onSaved }: { lugar: Lugar; onClose: () => void; onSaved: (l: Lugar) => void }) {
  const [nombre, setNombre] = useState(lugar.nombre);
  const [tipo, setTipo] = useState(lugar.tipo || "mercado");
  const [portadaThumb, setPortadaThumb] = useState(lugar.portada_thumb_url ?? lugar.portada_url ?? null);
  const [videoUrl, setVideoUrl] = useState(lugar.video_url ?? null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  async function guardarNombre() {
    if (!nombre.trim()) { setErr("El nombre no puede quedar vacío"); return; }
    setBusy(true); setErr(""); setMsg("");
    try { const l = await editarLugar(lugar.id, { nombre: nombre.trim(), tipo }); onSaved(l); setMsg("Guardado"); }
    catch (e) { setErr(e instanceof Error ? e.message : "Error"); }
    finally { setBusy(false); }
  }
  async function onPortada(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
    setBusy(true); setErr(""); setMsg("");
    try {
      const comp = await comprimirImagen(file);
      const l = await subirPortadaLugar(lugar.id, comp);
      setPortadaThumb(l.portada_thumb_url ?? l.portada_url ?? null); onSaved(l); setMsg("Foto subida");
    } catch (e) { setErr(e instanceof Error ? e.message : "No se pudo subir la foto"); }
    finally { setBusy(false); }
  }
  async function onVideo(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]; e.target.value = ""; if (!file) return;
    setErr(""); setMsg("");
    if (file.size > 50 * 1024 * 1024) { setErr("El video supera los 50 MB"); return; }
    const dur = await duracionVideo(file);
    if (dur > 60) { setErr(`El video dura ${dur}s — máximo 60s`); return; }
    setBusy(true);
    try { const l = await subirVideoLugar(lugar.id, file); setVideoUrl(l.video_url ?? null); onSaved(l); setMsg("Video subido"); }
    catch (e) { setErr(e instanceof Error ? e.message : "No se pudo subir el video"); }
    finally { setBusy(false); }
  }

  return (
    <div className="glass" style={{ padding: 12, borderRadius: 12, display: "flex", flexDirection: "column", gap: 10, border: "1px solid rgba(139,92,246,.4)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <b style={{ fontSize: 13.5 }}>Editar mercado / galería</b>
        <button type="button" className="link-more" onClick={onClose}>Cerrar</button>
      </div>
      <input className="adm-input" value={nombre} onChange={(e) => setNombre(e.target.value)} placeholder="Nombre" />
      <select className="adm-input" value={tipo} onChange={(e) => setTipo(e.target.value)}>
        <option value="mercado">Mercado</option>
        <option value="galeria">Galería</option>
        <option value="paseo">Paseo comercial</option>
        <option value="shopping">Shopping</option>
        <option value="referencia">Referencia (plaza, terminal…)</option>
      </select>
      <button type="button" className="btn btn-ghost" disabled={busy} onClick={guardarNombre}>Guardar nombre / tipo</button>
      <div style={{ display: "flex", gap: 10 }}>
        <label className="btn btn-ghost" style={{ flex: 1, textAlign: "center", cursor: "pointer" }}>
          <Ic n="foto" s={15} /> {portadaThumb ? "Cambiar portada" : "Foto de portada"}
          <input type="file" accept="image/*" capture="environment" hidden onChange={onPortada} />
        </label>
        <label className="btn btn-ghost" style={{ flex: 1, textAlign: "center", cursor: "pointer" }}>
          <Ic n="videos" s={15} /> {videoUrl ? "Cambiar recorrido" : "Video recorrido"}
          <input type="file" accept="video/*" capture="environment" hidden onChange={onVideo} />
        </label>
      </div>
      {(portadaThumb || videoUrl) && (
        <div style={{ display: "flex", gap: 10 }}>
          {portadaThumb && <img src={portadaThumb} alt="" style={{ width: 70, height: 70, objectFit: "cover", borderRadius: 8 }} />}
          {videoUrl && <video src={videoUrl} muted playsInline preload="metadata" style={{ width: 70, height: 70, objectFit: "cover", borderRadius: 8, background: "#000" }} />}
        </div>
      )}
      {busy && <span style={{ fontSize: 12, color: "var(--txt-3)" }}>Subiendo…</span>}
      {msg && <span style={{ fontSize: 12, color: "var(--neon)" }}>{msg}</span>}
      {err && <span style={{ fontSize: 12, color: "var(--pink)" }}>{err}</span>}
    </div>
  );
}

// Ciudad más cercana a un punto GPS (distancia euclidiana simple, alcanza para elegir entre pocas ciudades).
function ciudadMasCercana(ciudades: Ciudad[], lat: number, lng: number): Ciudad | null {
  const conCoords = ciudades.filter((c) => c.lat != null && c.lng != null);
  if (conCoords.length === 0) return null;
  let mejor = conCoords[0];
  let mejorDist = Infinity;
  for (const c of conCoords) {
    const d = (c.lat! - lat) ** 2 + (c.lng! - lng) ** 2;
    if (d < mejorDist) { mejorDist = d; mejor = c; }
  }
  return mejor;
}

function FormCampo({ onLogout, onVerMisComercios }: { onLogout: () => void; onVerMisComercios: (d?: DestinoLista) => void }) {
  const [ciudades, setCiudades] = useState<Ciudad[]>([]);
  const [rubros,   setRubros]   = useState<Rubro[]>([]);

  const [f, setF]               = useState({ ...EMPTY });
  const set = (k: keyof typeof EMPTY, v: string) => setF((s) => ({ ...s, [k]: v }));

  const [ciudadSlug,  setCiudadSlug]  = useState("bermejo");
  const [prefijo,     setPrefijo]     = useState("591");

  // Lugares (mercados/galerías): dónde está el puesto, opcional
  const [lugares,     setLugares]     = useState<Lugar[]>([]);
  const [lugarId,     setLugarId]     = useState("");
  const [puesto,      setPuesto]      = useState("");
  const [nuevoLugar,  setNuevoLugar]  = useState("");
  const [creandoLugar,setCreandoLugar]= useState(false);
  // "Modo mercado": recuerda el lugar recién cargado para seguir con el próximo puesto
  const [subioLugar,  setSubioLugar]  = useState<{ id: string; nombre: string } | null>(null);
  const [ultimoPuesto,setUltimoPuesto]= useState("");
  const [editMercado, setEditMercado] = useState(false);

  const [coords,      setCoords]      = useState<{ lat: number; lng: number; acc: number } | null>(null);
  const [geoMsg,      setGeoMsg]      = useState("");
  const [foto,        setFoto]        = useState<File | null>(null);
  // El File a previsualizar, no la URL: el hook la crea y la REVOCA sola. Antes
  // era un string y `setPreview("")` borraba el string pero dejaba la URL viva,
  // anclando la foto original en memoria hasta cerrar la pestaña.
  const [previewFile, setPreviewFile] = useState<File | null>(null);
  const preview = useObjectUrl(previewFile);
  const [comprimiendo,setComprimiendo]= useState(false);
  const [consent,     setConsent]     = useState(true);
  const [saving,      setSaving]      = useState(false);
  const [done,        setDone]        = useState<string | null>(null);
  const [doneOffline, setDoneOffline] = useState(false);
  // Por qué quedó guardado sin subir. Vacío = de verdad no había señal.
  const [doneMotivo,  setDoneMotivo]  = useState("");
  // Código del local recién dado de alta: hay que dictárselo o anotárselo al
  // dueño en el momento — es lo que le permite mandar ofertas por WhatsApp sin
  // tener número cargado, sin login y sin haber pagado.
  const [doneCodigo,  setDoneCodigo]  = useState<string | null>(null);
  // La clave de entrada del dueño (`clave_inicial`): viene SÓLO en la respuesta
  // del alta. Se muestra una vez, para dársela en mano; nunca va al volante.
  const [doneClave,   setDoneClave]   = useState<string | null>(null);
  // Claves de altas guardadas sin señal que subieron después (en memoria: no se
  // guarda un secreto en el celular).
  const [clavesSync,  setClavesSync]  = useState<ClavePorEntregar[]>([]);
  const [altaId,      setAltaId]      = useState<string | null>(null);
  // El número que quedó cargado, venga del formulario o de la pantalla
  // siguiente. Null = todavía no hay ninguno.
  const [whatsappCargado, setWhatsappCargado] = useState<string | null>(null);
  const [count,       setCount]       = useState(0);
  const [err,         setErr]         = useState("");

  // Cola offline: altas guardadas sin señal que se suben cuando vuelve internet.
  const [pendientes,   setPendientes]   = useState(0);
  const [sincronizando, setSincronizando] = useState(false);
  // Se cuenta LEYENDO la cola, no con una consulta aparte que puede fallar sola.
  //
  // Antes era `contarPendientes().then(setPendientes).catch(() => {})`: si esa
  // consulta fallaba, el error se descartaba, el contador quedaba en cero y el
  // bloque entero desaparecía de la pantalla — con las altas todavía guardadas
  // en el celular. El agente veía una pantalla limpia y daba por hecho que se
  // habían subido. En este lugar, no ver nada tiene que significar que no hay
  // nada, y para eso hay que leer lo que hay.
  const refrescarPend = () =>
    listarPendientes()
      .then((xs) => { setPendientes(xs.length); setErrCola(""); })
      .catch((e) => {
        setPendientes(-1);   // -1 = no se pudo saber. NO es cero.
        setErrCola(e instanceof Error ? e.message : "No se pudo leer la cola del celular");
      });
  // Resultado del último intento manual. Sin esto el botón falla en silencio: se
  // reintenta, todo rebota, el contador no baja y no hay nada en pantalla que
  // explique por qué.
  const [syncMsg, setSyncMsg] = useState("");
  const [detallePend, setDetallePend] = useState<AltaPendiente[] | null>(null);
  const [errCola, setErrCola] = useState("");

  async function verPendientes() {
    if (detallePend) { setDetallePend(null); return; }
    setDetallePend(await listarPendientes());
  }

  async function descartar(rec: AltaPendiente) {
    const nombre = rec.campos.nombre || "este comercio";
    if (!window.confirm(`¿Descartar "${nombre}"? No se puede recuperar.`)) return;
    await descartarPendiente(rec.id);
    setDetallePend(await listarPendientes());
    refrescarPend();
  }

  async function sincronizar(manual = false) {
    if (sincronizando) return;
    setSincronizando(true);
    if (manual) setSyncMsg("");
    try {
      const r = await sincronizarPendientes(refrescarPend);
      if (r.claves.length > 0) setClavesSync((prev) => [...prev, ...r.claves]);
      if (!manual) return;
      if (r.sinSenal) setSyncMsg("El celular está sin conexión — se suben solas cuando vuelva.");
      else if (r.fallas === 0 && r.subidas > 0) setSyncMsg(`Subieron ${r.subidas}.`);
      else if (r.fallas > 0) {
        setSyncMsg(`${r.subidas > 0 ? `Subieron ${r.subidas}. ` : ""}Fallaron ${r.fallas}: ${r.errores.join(" · ")}`);
      }
    } catch (ex) {
      if (manual) setSyncMsg(ex instanceof Error ? ex.message : "No se pudo sincronizar");
    } finally {
      setSincronizando(false);
      refrescarPend();
    }
  }
  useEffect(() => {
    refrescarPend();
    sincronizar();                                  // intento al abrir
    const onOnline = () => sincronizar();
    window.addEventListener("online", onOnline);    // y al volver la señal
    return () => window.removeEventListener("online", onOnline);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);


  useEffect(() => {
    getCiudades().then(setCiudades);
    getRubros().then(setRubros);
  }, []);

  // Los comercios ya cargados, para avisar «ya está» al tomar el GPS. Arranca con
  // lo que haya en memoria o guardado en el celular y se actualiza con la lista
  // del servidor; sin señal queda lo guardado. Nunca bloquea el alta.
  const [cercanos, setCercanos] = useState<ComercioCercano[] | null>(null);
  const [estadoLista, setEstadoLista] = useState<EstadoLista>("cargando");
  const refrescarCercanos = () => {
    misComercios()
      .then((xs) => { recordarLista(xs); setCercanos(aCercanos(xs)); setEstadoLista("fresca"); })
      // Sin señal (o sesión vencida): se queda con lo que había.
      .catch(() => setEstadoLista((e) => (e === "fresca" ? e : cercanosGuardados() ? "guardada" : "sin-datos")));
  };
  useEffect(() => {
    setCercanos(cercanosGuardados());
    refrescarCercanos();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const avisoRef = useRef<HTMLDivElement>(null);
  const hayYaCargados = !!coords && !!cercanos && cercanos.some((c) => metros(coords.lat, coords.lng, c.lat, c.lng) <= RADIO_YA_CARGADO_M);
  // El bloque aparece arriba del formulario: si el agente ya había bajado hasta
  // el GPS, se lo trae a la vista para que no se pierda el aviso.
  useEffect(() => {
    if (hayYaCargados) avisoRef.current?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }, [hayYaCargados]);

  // «Es este»: se abandona el alta y se abre ese comercio para completarlo. Si
  // ya había escrito o sacado la foto, se pregunta antes de tirarlo.
  function esEste(id: string) {
    const hayAlgo = !!f.nombre.trim() || !!foto || !!f.direccion.trim() || !!f.prodObs.trim() || !!puesto.trim();
    if (hayAlgo && !window.confirm("Vas a dejar esta carga sin guardar para completar el comercio que ya estaba. ¿Seguir?")) return;
    onVerMisComercios({ editarId: id });
  }

  // Mercados/galerías de la ciudad (para el selector "¿está dentro de un mercado?")
  useEffect(() => { listarLugares(ciudadSlug).then(setLugares).catch(() => {}); }, [ciudadSlug]);

  async function crearNuevoLugar() {
    const nombre = nuevoLugar.trim();
    if (!nombre) return;
    setCreandoLugar(true);
    setErr("");
    try {
      const lugar = await crearLugar({ nombre, ciudad_slug: ciudadSlug, lat: coords?.lat ?? null, lng: coords?.lng ?? null });
      setLugares((prev) => [...prev, lugar].sort((a, b) => a.nombre.localeCompare(b.nombre)));
      setLugarId(lugar.id);
      setNuevoLugar("");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "No se pudo crear el mercado");
    } finally {
      setCreandoLugar(false);
    }
  }

  // El rubro ya no se elige ni se sugiere en el campo: se deduce en el servidor
  // del texto cargado, y después la IA lo recalcula desde las fotos. Sacar la
  // llamada acá evita además un request en zonas sin señal.
  function ubicar() {
    setGeoMsg("Obteniendo ubicación…");
    if (!navigator.geolocation) { setGeoMsg("Este dispositivo no tiene GPS disponible."); return; }
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const lat = pos.coords.latitude, lng = pos.coords.longitude;
        setCoords({ lat, lng, acc: Math.round(pos.coords.accuracy) });
        setGeoMsg("");
        const cercana = ciudadMasCercana(ciudades, lat, lng);
        if (cercana) {
          setCiudadSlug(cercana.slug);
          setPrefijo(PREFIJO[cercana.pais] ?? "591");
        }
      },
      (e) => setGeoMsg(geoErrorMsg(e)),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  }

  async function onFoto(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0] ?? null;
    if (!file) { setFoto(null); setPreviewFile(null); return; }
    setPreviewFile(file);          // vista previa inmediata, sin esperar la compresión
    setComprimiendo(true);
    const comprimida = await comprimirImagen(file);
    setComprimiendo(false);
    setFoto(comprimida);
    // Se pasa a previsualizar la COMPRIMIDA y se suelta la original. Mostrar la
    // de 12 MP obliga al navegador a decodificarla entera para dibujar una
    // miniatura: son otros ~48 MB además de los del archivo, por foto.
    setPreviewFile(comprimida);
  }

  async function guardar(e: React.FormEvent) {
    e.preventDefault();
    setErr("");
    const cel = f.cel.replace(/\D/g, "");
    // Alta mínima: solo la ubicación es obligatoria. Nombre, WhatsApp, descripción y
    // foto son opcionales (locales sin contacto → quedan como punto en el mapa).
    if (!coords) { setErr("Falta la ubicación — tocá \"Usar mi ubicación actual\"."); return; }
    if (comprimiendo) { setErr("Esperá a que termine de comprimir la foto."); return; }

    setSaving(true);
    const campos: Record<string, string> = {
      ciudad_slug: ciudadSlug, modalidad: f.modalidad,
      lat: String(coords.lat), lng: String(coords.lng), consentimiento: String(consent),
      // La hora real del «Guardar», del reloj del celular. Sin esto, lo cargado
      // sin señal llega todo junto y el admin lo ve como si fuera de un solo
      // minuto. Si va a la cola, esta hora viaja con el registro.
      capturado_en: new Date().toISOString(),
    };
    if (f.nombre.trim()) campos.nombre = f.nombre.trim();
    if (cel) campos.whatsapp = prefijo + cel;
    if (f.prodObs.trim()) campos.prod_obs_human = f.prodObs.trim();
    if (f.direccion.trim()) campos.direccion = f.direccion.trim();
    if (lugarId && lugarId !== "__nuevo__") campos.lugar_id = lugarId;
    if (puesto.trim()) campos.puesto = puesto.trim();
    const lugarActual = (lugarId && lugarId !== "__nuevo__") ? lugares.find((l) => l.id === lugarId) ?? null : null;
    // Sin chips en el formulario: el backend deduce los rubros del texto y la IA
    // los recalcula desde las fotos. "otros" es sólo el punto de partida.
    const rubroList = ["otros"];
    const online = typeof navigator === "undefined" || navigator.onLine;

    try {
      if (!online) throw new Error("__offline__");
      const fd = new FormData();
      Object.entries(campos).forEach(([k, v]) => fd.append(k, v));
      rubroList.forEach((r) => fd.append("rubro_slugs", r));
      if (foto) fd.append("foto", foto);
      const r = await altaComercioCampo(fd);
      setDone(r.comercio.nombre);
      setDoneCodigo(r.comercio.codigo_formateado ?? null);
      setDoneClave(r.clave_inicial ?? null);
      setAltaId(r.comercio.id);
      setWhatsappCargado(campos.whatsapp ?? null);
      setCount((c) => c + 1);
      // Con ?debugmem=1 imprime el heap después de cada alta. Es la única forma
      // de saber si "quedó estable" en el celular del agente y no en una laptop
      // con 16 GB, que es donde nunca falló.
      medirMemoria("comercio guardado");
      setSubioLugar(lugarActual ? { id: lugarActual.id, nombre: lugarActual.nombre } : null);
      setUltimoPuesto(puesto);
      listarLugares(ciudadSlug).then(setLugares).catch(() => {});   // refresca el conteo del mercado
      refrescarCercanos();   // el que acaba de entrar tiene que contar para el próximo aviso
    } catch (ex) {
      // Falló la subida → guardar OFFLINE igual, así el alta NUNCA se pierde.
      //
      // Antes esto sólo encolaba si parecía un problema de red, y además la
      // pantalla decía "sin conexión" pasara lo que pasara. Con un backend
      // roto el agente se pasó una hora buscando señal con el celular
      // perfecto. Ahora se encola siempre y se distingue el motivo real.
      const esRed = !online || ex instanceof TypeError || /__offline__|fetch|network|Failed/i.test(String(ex));
      const motivo = ex instanceof Error ? ex.message : String(ex);
      {
        try {
          await encolarAlta(campos, rubroList, foto);
          setDone(campos.nombre ?? "Comercio");
          setDoneOffline(true);
          setDoneMotivo(esRed ? "" : motivo);
          setCount((c) => c + 1);
          // Con ?debugmem=1 imprime el heap después de cada alta. Es la única forma
          // de saber si "quedó estable" en el celular del agente y no en una laptop
          // con 16 GB, que es donde nunca falló.
          medirMemoria("comercio guardado");
          setSubioLugar(lugarActual ? { id: lugarActual.id, nombre: lugarActual.nombre } : null);
          setUltimoPuesto(puesto);
          refrescarPend();
        } catch {
          setErr("No se pudo guardar ni siquiera offline. Reintentá.");
        }
      }
    } finally {
      setSaving(false);
    }
  }

  function limpiar() {
    setF({ ...EMPTY });
    setCoords(null); setGeoMsg(""); setFoto(null); setPreviewFile(null); setConsent(true);
    setNuevoLugar(""); setEditMercado(false); setDone(null); setDoneOffline(false); setDoneMotivo(""); setDoneCodigo(null); setDoneClave(null); setAltaId(null); setWhatsappCargado(null); setErr("");
  }
  function otro() {
    limpiar();
    setLugarId(""); setPuesto(""); setSubioLugar(null);   // sale del mercado (a la calle u otro)
  }
  // Sigue cargando en el MISMO mercado: mantiene el lugar y sugiere el próximo N° de puesto.
  function otroPuestoAca() {
    limpiar();
    setLugarId(subioLugar?.id ?? "");
    const m = ultimoPuesto.trim().match(/^(\d+)$/);
    setPuesto(m ? String(parseInt(m[1], 10) + 1) : "");
  }

  if (done) {
    const ciudadActual = ciudades.find((c) => c.slug === ciudadSlug);
    return (
      // Compacta a propósito: el agente está parado en la vereda con el dueño
      // enfrente, y todo lo que quede abajo del pliegue es algo que no va a
      // hacer. Se achicó el aire (padding 60→14, emoji 48→30, títulos), NO el
      // contenido: el código, el WhatsApp y la galería siguen todos acá.
      <div className="campo-wrap" style={{ textAlign: "center", paddingTop: 14 }}>
        <div style={{ lineHeight: 1, color: doneOffline ? "var(--amber)" : "var(--neon)" }}><Ic n={doneOffline ? "reloj" : "listo"} s={30} /></div>
        <h1 style={{ fontSize: 19, margin: "6px 0 2px" }}>¡{done} {doneOffline ? "guardado sin conexión" : "cargado"}!</h1>
        {/* Las dos líneas de estado en una: decían poco cada una y ocupaban
            dos renglones enteros. */}
        <p style={{ color: "var(--txt-3)", fontSize: 12.5, lineHeight: 1.4, marginBottom: 12 }}>
          {doneOffline
            ? (doneMotivo
                ? `Guardado en el celular, pero NO por falta de señal: ${doneMotivo}`
                : "Se sube solo cuando haya señal.")
            : `${ciudadActual ? `${ciudadActual.nombre} · ` : ""}Pendiente de verificar.`}
          {` · Llevás ${count}`}{pendientes > 0 ? ` · ${pendientes} sin subir` : ""}
        </p>

        <ClavesPorEntregar claves={clavesSync} onEntregada={(c) => setClavesSync((prev) => prev.filter((x) => x.clave !== c))} />

        {/* LA CLAVE, grande y primero: es lo único que no se puede recuperar
            después. El servidor sólo guarda el hash. */}
        {doneClave && (
          <div style={{ marginBottom: 12 }}>
            <ClaveUnaVez compacta clave={doneClave} titulo="Clave de entrada del dueño" aviso={AVISO_CLAVE_AGENTE} />
          </div>
        )}
        {doneOffline && (
          <p style={{ color: "var(--amber)", fontSize: 12, margin: "0 0 12px" }}>
            <Ic n="reloj" s={13} /> La clave del dueño aparece acá cuando este comercio se suba.
          </p>
        )}

        {doneCodigo && (
          <div style={{ marginBottom: 12, padding: "10px 12px", borderRadius: 12, background: "var(--panel)", border: "2px solid var(--neon)" }}>
            {/* El código y su explicación en una fila: el número grande manda y
                el texto va al lado, no debajo. Gana un bloque de tres renglones. */}
            <div style={{ display: "flex", alignItems: "center", gap: 10, textAlign: "left" }}>
              <div style={{ fontSize: 24, fontWeight: 800, letterSpacing: 2, color: "var(--neon)", fontFamily: "monospace", whiteSpace: "nowrap" }}>
                {doneCodigo}
              </div>
              <p style={{ color: "var(--txt-3)", fontSize: 11.5, lineHeight: 1.35, margin: 0 }}>
                Dejáselo al dueño: con esto manda ofertas por WhatsApp desde
                cualquier celular, sin cuenta.
              </p>
            </div>
            <button
              className="btn btn-ghost"
              style={{ width: "100%", marginTop: 8, padding: "7px 12px", fontSize: 13 }}
              onClick={() => {
                const texto = `Tu código de URUKU es ${doneCodigo}. Mandá tus ofertas por WhatsApp escribiendo ese código en el mensaje.`;
                navigator.clipboard?.writeText(texto).catch(() => {});
              }}
            >
              Copiar mensaje para el dueño
            </button>
          </div>
        )}

        {/* El WhatsApp va ACÁ y no en el formulario: el agente releva el local
            primero y recién después se pone a hablar con la persona, así que el
            número aparece al final de esa charla. Va antes de la galería porque
            es lo que se pide cara a cara, mientras el otro está enfrente. */}
        {altaId && (
          <CapturaWhatsapp
            comercioId={altaId}
            nombre={done}
            prefijoInicial={prefijo}
            valorInicial={whatsappCargado}
            onGuardado={(n) => setWhatsappCargado(n)}
          />
        )}

        {/* «COMPLETAR COMERCIO»: la misma pantalla que se abre desde la lista y
            desde «Es este». Reemplaza a la segunda pasada suelta y a la galería
            que iban acá: horario, qué vende, fotos, redes, catálogo… Va después
            del WhatsApp porque es la charla que sigue, y se queda en la pantalla
            del alta —sin «Volver»— porque el agente todavía está con el dueño. */}
        {altaId && <CompletarTrasAlta comercioId={altaId} whatsapp={whatsappCargado} rubros={rubros} lugares={lugares} />}

        {subioLugar && (
          <button className="btn btn-primary" style={{ width: "100%", marginBottom: 8, padding: "9px 12px", background: "#6d28d9", borderColor: "#6d28d9", color: "#fff" }} onClick={otroPuestoAca}>
            <Ic n="mas" s={15} /> Otro puesto en {subioLugar.nombre}
          </button>
        )}
        <button className={subioLugar ? "btn btn-ghost" : "btn btn-primary"} style={{ width: "100%", marginBottom: 8, padding: "9px 12px" }} onClick={otro}>Cargar otro comercio {subioLugar ? "(a la calle / otro)" : ""}</button>
        <button className="link-more" onClick={() => onVerMisComercios()}>Ver mis comercios cargados</button>
      </div>
    );
  }


  return (
    <div className="campo-wrap">
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 14 }}>
        <div>
          <span className="eyebrow"><Pin style={{ width: 13, height: 13 }} /> Carga de comercios</span>
          {count > 0 && <div style={{ fontSize: 12, color: "var(--neon)" }}>{count} cargados hoy</div>}
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          {/* Siempre disponible, aunque el contador diga cero: es la única forma
              de distinguir "no hay nada guardado" de "no pude leerlo". */}
          <button className="link-more" onClick={verPendientes} style={{ padding: "6px 12px" }}
                  title="Lo que quedó guardado en este celular sin subir">Sin subir</button>
          <button className="link-more" onClick={() => onVerMisComercios()} style={{ padding: "6px 12px" }}>Mis comercios</button>
          <button className="link-more" onClick={onLogout} style={{ padding: "6px 12px" }}>Salir</button>
        </div>
      </div>

      <ClavesPorEntregar claves={clavesSync} onEntregada={(c) => setClavesSync((prev) => prev.filter((x) => x.clave !== c))} />

      {detallePend !== null && pendientes === 0 && !errCola && (
        <div style={{ background: "var(--panel)", border: "1px solid var(--stroke)", borderRadius: 12,
                      padding: "10px 12px", marginBottom: 12, fontSize: 13 }}>
          {detallePend.length === 0
            ? "No hay nada sin subir en este celular."
            : `Hay ${detallePend.length} sin subir.`}
          <button type="button" className="link-more" style={{ marginLeft: 8, padding: 0 }}
                  onClick={() => setDetallePend(null)}>Ocultar</button>
        </div>
      )}

      {(pendientes > 0 || pendientes === -1 || !!errCola) && (
        <div style={{ background: "rgba(240,160,40,.12)", border: "1px solid rgba(240,160,40,.45)", color: "var(--amber)", borderRadius: 12, padding: "10px 12px", marginBottom: 12, fontSize: 13 }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10 }}>
            <span>
              {pendientes === -1
                ? "No se pudo leer lo que hay guardado en este celular"
                : `${pendientes} guardado${pendientes > 1 ? "s" : ""} sin conexión — se sube${pendientes > 1 ? "n" : ""} con señal`}
            </span>
            <button type="button" className="btn btn-ghost" style={{ padding: "5px 12px", whiteSpace: "nowrap" }} disabled={sincronizando} onClick={() => sincronizar(true)}>
              {sincronizando ? "Subiendo…" : "Sincronizar"}
            </button>
          </div>
          {errCola && (
            <div style={{ marginTop: 8, fontSize: 12.5, lineHeight: 1.45 }}>
              {errCola} · <b>No borres los datos del sitio</b>: las altas pueden
              seguir guardadas y aún se pueden recuperar.
            </div>
          )}
          {syncMsg && (
            <div style={{ marginTop: 8, paddingTop: 8, borderTop: "1px solid rgba(240,160,40,.3)", fontSize: 12.5, lineHeight: 1.45, wordBreak: "break-word" }}>
              {syncMsg}
            </div>
          )}
          <button type="button" className="link-more" style={{ color: "var(--amber)", marginTop: 6, padding: 0 }} onClick={verPendientes}>
            {detallePend ? "Ocultar" : "Ver cuáles son"}
          </button>
          {detallePend && (
            <div style={{ marginTop: 8, borderTop: "1px solid rgba(240,160,40,.3)", paddingTop: 8 }}>
              {detallePend.map((rec) => {
                const roto = esIrrecuperable(rec);
                return (
                  <div key={rec.id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, padding: "5px 0", fontSize: 12.5 }}>
                    <div style={{ minWidth: 0 }}>
                      <div style={{ fontWeight: 600 }}>{rec.campos.nombre || "(sin nombre)"}</div>
                      <div style={{ opacity: 0.8 }}>
                        {new Date(rec.creado).toLocaleString("es-BO")}
                        {roto && " · sin GPS: no va a entrar nunca"}
                      </div>
                      {/* Las coordenadas a la vista: si una falla por "falta la
                          ubicación" pero acá se ven, el problema está en el envío
                          y no en el dato. Sin esto hay que adivinar. */}
                      <div style={{ opacity: 0.65, fontFamily: "monospace", fontSize: 11 }}>
                        {rec.campos.lat && rec.campos.lng
                          ? `${Number(rec.campos.lat).toFixed(5)}, ${Number(rec.campos.lng).toFixed(5)}`
                          : "sin coordenadas"}
                        {rec.foto ? " · con foto" : " · sin foto"}
                      </div>
                    </div>
                    {/* Se puede descartar CUALQUIERA, no sólo las rotas: si una
                        se traba por lo que sea, tiene que haber forma de sacarla
                        de la cola sin borrar los datos del navegador. */}
                    <button type="button" className="link-more" style={{ color: "var(--pink)", flexShrink: 0, padding: 0 }} onClick={() => descartar(rec)}>
                      Descartar
                    </button>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      <form onSubmit={guardar} style={{ display: "flex", flexDirection: "column", gap: 14 }}>

        {/* Banner "modo mercado": el lugar queda fijado hasta que el agente salga */}
        {lugarId && lugarId !== "__nuevo__" && (() => {
          const l = lugares.find((x) => x.id === lugarId);
          return (
            <>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 10, background: "rgba(109,40,217,.14)", border: "1px solid rgba(139,92,246,.45)", color: "#c4b5fd", borderRadius: 12, padding: "9px 12px", fontSize: 13 }}>
                <span><Ic n="galeria" s={14} /> Cargando en <b>{l?.nombre ?? "mercado"}</b>{l?.n_comercios ? ` · ya llevás ${l.n_comercios}` : ""}</span>
                <div style={{ display: "flex", gap: 10, flexShrink: 0 }}>
                  <button type="button" className="link-more" style={{ color: "#c4b5fd" }} onClick={() => setEditMercado((v) => !v)}><Ic n="editar" s={13} /> Editar</button>
                  <button type="button" className="link-more" style={{ color: "#c4b5fd" }} onClick={() => { setLugarId(""); setPuesto(""); setEditMercado(false); }}>Salir</button>
                </div>
              </div>
              {editMercado && l && (
                <MercadoEditor lugar={l} onClose={() => setEditMercado(false)}
                  onSaved={(nl) => setLugares((prev) => prev.map((x) => (x.id === nl.id ? { ...x, ...nl } : x)))} />
              )}
            </>
          );
        })()}

        {/* ── Aviso «ya cargado»: arriba de todo, antes de que se llene nada.
            Sólo aparece con el GPS tomado; si no hay ninguno cerca es una
            línea discreta, y nunca frena el guardado. ── */}
        {coords && (
          <div ref={avisoRef}>
            <YaCargadosAca
              lat={coords.lat} lng={coords.lng} acc={coords.acc}
              lista={cercanos} estado={estadoLista}
              onEsEste={esEste}
              onVerTodos={() => onVerMisComercios({ filtro: "cerca" })}
            />
          </div>
        )}

        {/* ── Nombre ── */}
        <input className="adm-input" value={f.nombre} onChange={(e) => set("nombre", e.target.value)} placeholder="Nombre del cartel (si no tiene, dejalo vacío)" />

        {/* El WhatsApp, la modalidad, la galería, los productos y la
            referencia salieron de acá el 2/10 y están en la pantalla
            siguiente. El motivo: el agente carga PARADO en la vereda, con el
            dueño atendiendo, y una pantalla larga hace que se saltee la mitad
            — incluida la foto, que es lo único que no se puede pedir después
            por teléfono. La primera pasada deja lo que sólo se puede tomar
            estando ahí: foto, GPS y rubro. El resto es la segunda visita. */}

        {/* ── GPS ── */}
        <div>
          <label className="campo-lbl">Ubicación (parado en la puerta) *</label>
          <button type="button" className={`btn ${coords ? "btn-ghost" : "btn-primary"}`} style={{ width: "100%" }} onClick={ubicar}>
            <Pin style={{ width: 17, height: 17 }} /> {coords ? "Ubicación tomada — tomar de nuevo" : "Usar mi ubicación actual"}
          </button>
          {coords && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}><Ic n="ubicacion" s={12} /> {coords.lat.toFixed(5)}, {coords.lng.toFixed(5)} (±{coords.acc} m)</div>}
          {geoMsg && <PermisoUbicacion mensaje={geoMsg} onPedir={ubicar} motivo="Para ubicar el comercio en el mapa" />}
        </div>

        {/* ── Foto ── */}
        <div>
          <label className="campo-lbl">Foto del local (portada, opcional)</label>
          <label className="foto-drop">
            {preview ? <img src={preview} alt="" /> : <span><Ic n="foto" s={16} /> Sacar foto / elegir</span>}
            <input type="file" accept="image/*" capture="environment" onChange={onFoto} hidden />
          </label>
          {comprimiendo && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>Comprimiendo foto…</div>}
          {!comprimiendo && foto && <div style={{ fontSize: 12, color: "var(--txt-3)", marginTop: 6 }}>{(foto.size / 1024).toFixed(0)} KB</div>}
          <div style={{ fontSize: 12, color: "var(--neon)", marginTop: 8 }}><Ic n="foto" s={13} /> Después de guardar vas a poder sumar <b>más fotos y videos</b> del local.</div>
        </div>

        <label style={{ display: "flex", gap: 10, alignItems: "center", fontSize: 13.5, color: "var(--txt-2)" }}>
          <input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
          El dueño aceptó aparecer en URUKU
        </label>

        {err && <span style={{ color: "var(--pink)", fontSize: 13 }}>{err}</span>}
        <button className="btn btn-primary" type="submit" disabled={saving} style={{ width: "100%", padding: 16 }}>
          {saving ? "Guardando…" : "Guardar comercio"}
        </button>
      </form>
      <div style={{ height: 40 }} />
    </div>
  );
}
