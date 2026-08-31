import { supabase, hasSupabase } from "@/lib/supabase";
import type { Adorno } from "@/lib/adornos";
import type { Comercio, FeedItem, Producto, Zona, Rubro, Ciudad, ResultadoBusqueda, FiltrosBusqueda } from "@/lib/types";

// Diagnóstico temporal (self-host, 2026-07-10): supabase-js a veces no
// tira un PostgrestError normal (message/code/details) sino una excepción
// de red cruda con otra forma — volcamos todo lo que tenga para no seguir
// a ciegas.
function logSupaError(tag: string, error: unknown) {
  const e = error as any;
  console.warn(
    `${tag}:`,
    "name=", e?.name,
    "message=", e?.message,
    "code=", e?.code,
    "details=", e?.details,
    "cause=", e?.cause,
    "str=", String(error),
    "json=", (() => { try { return JSON.stringify(error); } catch { return "[no serializable]"; } })(),
  );
}

export async function buscarComercios(f: FiltrosBusqueda, limit = 24, offset = 0): Promise<ResultadoBusqueda[]> {
  if (!hasSupabase) return [];
  const { data, error } = await supabase.rpc("buscar_comercios", {
    q: f.q || null,
    p_rubro: f.rubro || null,
    p_modalidad: f.modalidad || null,
    p_zona: f.zona || null,
    p_precio_min: f.precioMin ?? null,
    p_precio_max: f.precioMax ?? null,
    p_ciudad: f.ciudad || null,
    p_limit: limit,
    p_offset: offset,
    p_subcategoria: f.subcategoria || null,
  });
  if (error) {
    console.warn("buscar_comercios error:", error.message);
    return [];
  }
  return (data ?? []) as ResultadoBusqueda[];
}


/**
 * Qué filtros tienen datos detrás. Un filtro que no filtra es peor que uno que
 * no está: la persona lo toca, no cambia nada, y deja de confiar en los demás.
 *
 * Medido el 27/8 sobre 680 comercios: **ninguno tenía horario cargado**, así
 * que "Abierto ahora" —construido, visible y en la lista de hechos— no podía
 * dar un resultado correcto nunca. No fallaba: no hacía nada, que es la forma
 * de romperse más difícil de ver.
 *
 * Son consultas de conteo puro (`head: true`), sin traer filas. Van una vez al
 * cargar la pantalla y cuestan prácticamente nada.
 */
export type FiltrosDisponibles = { horario: boolean; zona: boolean; ofertas: boolean };

const NINGUNO: FiltrosDisponibles = { horario: false, zona: false, ofertas: false };

export async function getFiltrosDisponibles(): Promise<FiltrosDisponibles> {
  if (!hasSupabase) return NINGUNO;
  const cuenta = async (armar: (q: any) => any): Promise<number> => {
    try {
      const { count } = await armar(
        supabase.from("comercios").select("id", { count: "exact", head: true }).eq("activo", true));
      return count ?? 0;
    } catch { return 0; }
  };
  try {
    // "Tipo" (mayorista/minorista) NO se mide: queda siempre visible por
    // decisión del producto. Es un filtro que la gente entiende y busca aunque
    // hoy el reparto esté desbalanceado.
    const [conHorario, conZona, ofertas] = await Promise.all([
      cuenta((q) => q.not("horario", "is", null).neq("horario", "")),
      cuenta((q) => q.not("zona_id", "is", null)),
      (async () => {
        try {
          const { count } = await supabase.from("publicaciones")
            .select("id", { count: "exact", head: true }).eq("estado", "aprobado");
          return count ?? 0;
        } catch { return 0; }
      })(),
    ]);
    return { horario: conHorario > 0, zona: conZona > 0, ofertas: ofertas > 0 };
  } catch {
    // Ante un error se muestran todos: esconder filtros por una consulta caída
    // sería peor que mostrar uno de más.
    return { horario: true, zona: true, ofertas: true };
  }
}

/**
 * Los chips de refinamiento de una búsqueda: qué subcategorías hay entre sus
 * resultados. Se calculan en la base, sobre el mismo filtro que trajo los
 * resultados, así no pueden ofrecer algo que la búsqueda no muestra.
 */
export async function getRefinamientos(f: FiltrosBusqueda): Promise<{ subcategoria: string; n: number }[]> {
  if (!hasSupabase) return [];
  const { data, error } = await supabase.rpc("refinamientos_busqueda", {
    q: f.q || null,
    p_rubro: f.rubro || null,
    p_modalidad: f.modalidad || null,
    p_zona: f.zona || null,
    p_ciudad: f.ciudad || null,
  });
  if (error) { console.warn("refinamientos_busqueda:", error.message); return []; }
  return (data ?? []) as { subcategoria: string; n: number }[];
}

export async function getCiudades(): Promise<Ciudad[]> {
  if (hasSupabase) {
    const { data } = await supabase.from("ciudades").select("*").order("orden");
    if (data) return data as Ciudad[];
  }
  return DEMO_CIUDADES;
}

const DEMO_CIUDADES: Ciudad[] = [
  { id: "1", slug: "bermejo",     nombre: "Bermejo",    departamento: "Tarija",     lat: -22.7361, lng: -64.3433, es_frontera: true,  activa: true,  orden: 1,  pais: "Bolivia" },
  { id: "2", slug: "yacuiba",     nombre: "Yacuiba",    departamento: "Tarija",     lat: -22.0146, lng: -63.6775, es_frontera: true,  activa: false, orden: 2,  pais: "Bolivia" },
  { id: "3", slug: "villazon",    nombre: "Villazón",   departamento: "Potosí",     lat: -22.0866, lng: -65.5942, es_frontera: true,  activa: false, orden: 3,  pais: "Bolivia" },
  { id: "4", slug: "santa-cruz",  nombre: "Santa Cruz", departamento: "Santa Cruz", lat: -17.7833, lng: -63.1821, es_frontera: false, activa: false, orden: 10, pais: "Bolivia" },
  { id: "5", slug: "la-paz",      nombre: "La Paz",     departamento: "La Paz",     lat: -16.5,    lng: -68.15,   es_frontera: false, activa: false, orden: 11, pais: "Bolivia" },
  { id: "6", slug: "la-quiaca",   nombre: "La Quiaca",  departamento: "Jujuy",      lat: -22.1027, lng: -65.5983, es_frontera: true,  activa: false, orden: 20, pais: "Argentina" },
  { id: "7", slug: "jujuy",       nombre: "Jujuy",      departamento: "Jujuy",      lat: -24.1858, lng: -65.2995, es_frontera: false, activa: false, orden: 22, pais: "Argentina" },
  { id: "8", slug: "salta",       nombre: "Salta",      departamento: "Salta",      lat: -24.7821, lng: -65.4232, es_frontera: false, activa: false, orden: 23, pais: "Argentina" },
];

export async function getRubros(): Promise<Rubro[]> {
  if (hasSupabase) {
    const { data } = await supabase.from("rubros").select("*").eq("activo", true).order("orden");
    if (data) return data as Rubro[];
  }
  return [];
}

/**
 * Capa de lectura del catálogo. Si Supabase no está configurado, devuelve
 * datos demo para que el front se vea aún sin backend (degradación suave).
 */

export async function getFeed(limit = 8): Promise<FeedItem[]> {
  if (hasSupabase) {
    const { data, error } = await supabase
      .from("feed_publico")
      .select("*")
      .limit(limit);
    if (error) logSupaError("getFeed", error);
    if (!error && data) return data as FeedItem[];
  } else {
    console.warn("getFeed: hasSupabase=false — faltan NEXT_PUBLIC_SUPABASE_URL/ANON_KEY");
  }
  return DEMO_FEED.slice(0, limit);
}

/** Las ofertas de UN comercio: las que mandó por WhatsApp y están aprobadas.
 *
 * Sale de `feed_publico`, la misma vista que el feed de la portada, no de
 * `producto_ref` — ésa es la tabla del catálogo de Reservalo, que quedó sin uso
 * y además exige `url` no nula, así que filtraba justamente lo que llega por
 * WhatsApp (que no tiene link a ningún lado).
 *
 * Sin Supabase devuelve vacío y no el feed de demostración: poner ofertas
 * inventadas bajo el nombre de un comercio real es peor que no mostrar nada. */
export async function getOfertasComercio(comercioId: string, limit = 24): Promise<FeedItem[]> {
  if (!hasSupabase) return [];
  const { data, error } = await supabase
    .from("feed_publico")
    .select("*")
    .eq("comercio_id", comercioId)
    .limit(limit);
  if (error) { logSupaError("getOfertasComercio", error); return []; }
  return (data ?? []) as FeedItem[];
}

/** Las ofertas de VARIOS comercios de una sola consulta, agrupadas por comercio.
 *
 * Una consulta por tarjeta serían treinta pedidos por página de resultados. Y
 * pedirlas junto con la búsqueda tampoco sirve: `buscar_comercios` devuelve una
 * fila por comercio, así que las ofertas viajarían repetidas o aplastadas en un
 * contador — que es lo que hay hoy y por eso no se pueden mostrar.
 *
 * Ante un error devuelve el mapa vacío: la tarjeta sin tira de ofertas se ve
 * bien y sigue sirviendo. Que falle esto no puede vaciar el buscador. */
export async function getOfertasDeComercios(ids: string[], porComercio = 3): Promise<Map<string, FeedItem[]>> {
  const mapa = new Map<string, FeedItem[]>();
  if (!hasSupabase || ids.length === 0) return mapa;
  const { data, error } = await supabase
    .from("feed_publico")
    .select("*")
    .in("comercio_id", ids);
  if (error) { logSupaError("getOfertasDeComercios", error); return mapa; }
  for (const o of (data ?? []) as FeedItem[]) {
    const suyas = mapa.get(o.comercio_id) ?? [];
    // El corte va acá y no en la consulta: un `limit` global se llevaría las
    // primeras N ofertas de la página entera y dejaría comercios sin ninguna.
    if (suyas.length < porComercio) suyas.push(o);
    mapa.set(o.comercio_id, suyas);
  }
  return mapa;
}

export async function getComercios(): Promise<Comercio[]> {
  if (hasSupabase) {
    const { data, error } = await supabase.from("comercios").select("*").eq("destacado", true).limit(10);
    if (error) logSupaError("getComercios", error);
    if (data) return data as Comercio[];
  } else {
    console.warn("getComercios: hasSupabase=false — faltan NEXT_PUBLIC_SUPABASE_URL/ANON_KEY");
  }
  return DEMO_COMERCIOS;
}

export type ComercioMapa = {
  id: string; slug: string; nombre: string;
  lat: number | null; lng: number | null;
  logo_url: string | null; portada_url: string | null; portada_thumb_url: string | null; whatsapp: string | null;
  telefono: string | null; verificado: boolean; destacado: boolean; rating: number;
  direccion: string | null; descripcion: string | null; prod_obs_human: string | null; prod_det_ia: string | null; subcategoria: string | null; horario: string | null;
  como_llegar: string | null; rubro_slug: string | null; plan: string | null;
  /** TODOS los rubros del comercio, no sólo el principal. El mapa filtra por
   *  acá: un local que vende neumáticos Y zapatillas tiene que aparecer en las
   *  dos categorías, que es el motivo de existir de `comercio_rubros`. */
  rubro_slugs: string[];
  ficha_activa: boolean;   // muestra "Más información": suscripción al día (paga_hasta vigente, no suspendido)
  // Lugar (mercado/galería) al que pertenece, si está adentro de uno
  lugar_id: string | null; puesto: string | null;
  lugar_nombre: string | null; lugar_lat: number | null; lugar_lng: number | null;
  lugar_portada_thumb_url: string | null; lugar_video_url: string | null;
  lugar_poligono: [number, number][] | null;
};

// Bbox alrededor del centro de una ciudad (±grados). Usado para acotar el mapa
// a la ciudad seleccionada sin traer todo el país.
/**
 * Trae TODAS las filas de una consulta, de a páginas.
 *
 * POR QUÉ EXISTE
 * ==============
 *
 * El mapa pedía `.limit(250)` con 270 comercios activos: veinte no aparecían
 * nunca y nada lo decía. No hay error, no hay hueco visible — devuelve 250 y se
 * lee como la lista completa. Es la misma forma de fallar que el embed roto que
 * devuelve [] y el script que informaba "0 sin respaldo" cuando había 37.
 *
 * Subir el número no arregla la clase de error, sólo mueve el techo: al llegar
 * a 500 vuelve a pasar y nadie se entera. Por eso se pagina hasta que la
 * consulta se queda sin filas, y si además hay un tope del servidor
 * (PostgREST tiene su propio max-rows) el aviso queda en la consola.
 */
async function traerTodo<T>(
  hacerConsulta: (desde: number, hasta: number) => any,
  que: string,
  porPagina = 1000,
  techo = 20000,
): Promise<T[]> {
  const todo: T[] = [];
  for (let desde = 0; desde < techo; desde += porPagina) {
    const { data, error } = await hacerConsulta(desde, desde + porPagina - 1);
    if (error) { logSupaError(`traerTodo (${que})`, error); break; }
    const lote = (data ?? []) as T[];
    todo.push(...lote);
    if (lote.length < porPagina) return todo;      // se acabaron las filas
  }
  console.warn(
    `traerTodo (${que}): se alcanzó el techo de ${techo} filas. ` +
    `Puede haber datos sin traer — revisar antes de confiar en esta lista.`);
  return todo;
}

export function bboxCiudad(lat: number, lng: number, dLat = 0.16, dLng = 0.20) {
  return { latMin: lat - dLat, latMax: lat + dLat, lngMin: lng - dLng, lngMax: lng + dLng };
}

// Comercios geolocalizados para el mapa (+ auspiciantes/destacados).
// Acotado al área de la CIUDAD seleccionada (bbox) y SIN join (el embed era
// lentísimo sobre la tabla con el import OSM masivo). El rubro se resuelve aparte.
export async function getComerciosMapa(
  ciudad?: { lat: number | null; lng: number | null } | null,
): Promise<ComercioMapa[]> {
  const c0 = ciudad?.lat != null && ciudad?.lng != null
    ? bboxCiudad(ciudad.lat, ciudad.lng)
    : { latMin: -22.90, latMax: -22.58, lngMin: -64.52, lngMax: -64.16 }; // Bermejo por defecto
  if (hasSupabase) {
    const [data, { data: rubros, error: errorRubros }, { data: lugs }, rels] = await Promise.all([
      traerTodo<any>((desde, hasta) => supabase
        .from("comercios")
        .select("id, slug, nombre, lat, lng, logo_url, portada_url, portada_thumb_url, whatsapp, telefono, verificado, destacado, rating, direccion, descripcion, horario, como_llegar, plan, paga_hasta, suspendido, rubro_id, lugar_id, puesto, prod_obs_human, prod_det_ia, subcategoria")
        .eq("activo", true)
        .not("lat", "is", null)
        .gte("lat", c0.latMin).lte("lat", c0.latMax)
        .gte("lng", c0.lngMin).lte("lng", c0.lngMax)
        .order("id")
        .range(desde, hasta), "comercios del mapa"),
      supabase.from("rubros").select("id, slug"),
      supabase.from("lugares").select("id, nombre, tipo, lat, lng, portada_thumb_url, video_url, poligono").eq("activo", true),
      // Todos los rubros de cada comercio. Sin esto el mapa sólo conoce el
      // principal, y filtrar por "Calzado" dejaba afuera a los locales que
      // venden calzado pero tienen otro rubro como principal.
      //
      // Paginado por lo mismo que los comercios: con un tope fijo, pasarlo no
      // rompe el mapa sino los FILTROS, que es peor — el local aparece pero
      // desaparece al tocar su categoría, y eso no se lee como un error.
      traerTodo<any>((desde, hasta) => supabase
        .from("comercio_rubros").select("comercio_id, rubro_id")
        .order("comercio_id").range(desde, hasta), "rubros por comercio"),
    ]);
    if (errorRubros) logSupaError("getComerciosMapa (rubros)", errorRubros);
    if (data) {
      const slugById = new Map((rubros ?? []).map((r: any) => [r.id, r.slug]));
      const lugById = new Map((lugs ?? []).map((l: any) => [l.id, l]));
      const rubrosDe = new Map<string, string[]>();
      for (const r of (rels ?? []) as any[]) {
        const slug = slugById.get(r.rubro_id);
        if (!slug || slug === "otros") continue;
        const lista = rubrosDe.get(r.comercio_id) ?? [];
        lista.push(slug);
        rubrosDe.set(r.comercio_id, lista);
      }
      // Gracia de 10 días: tras vencer el pago, la ficha sigue 10 días antes de pasar a "solo mapa".
      const graceISO = new Date(Date.now() - 10 * 86400000).toISOString().slice(0, 10);
      return (data as any[]).map((c) => {
        const lg = c.lugar_id ? lugById.get(c.lugar_id) : null;
        return {
          id: c.id, slug: c.slug, nombre: c.nombre, lat: c.lat, lng: c.lng,
          logo_url: c.logo_url, portada_url: c.portada_url, portada_thumb_url: c.portada_thumb_url ?? null, whatsapp: c.whatsapp, telefono: c.telefono,
          verificado: c.verificado, destacado: c.destacado, rating: c.rating,
          direccion: c.direccion, descripcion: c.descripcion, prod_obs_human: c.prod_obs_human ?? null, prod_det_ia: c.prod_det_ia ?? null, subcategoria: c.subcategoria ?? null, horario: c.horario, como_llegar: c.como_llegar,
          rubro_slug: slugById.get(c.rubro_id) ?? null, plan: c.plan ?? null,
          rubro_slugs: rubrosDe.get(c.id) ?? [],
          ficha_activa: !c.suspendido && !!c.paga_hasta && String(c.paga_hasta).slice(0, 10) >= graceISO,
          lugar_id: c.lugar_id ?? null, puesto: c.puesto ?? null,
          lugar_nombre: lg?.nombre ?? null, lugar_lat: lg?.lat ?? null, lugar_lng: lg?.lng ?? null,
          lugar_portada_thumb_url: lg?.portada_thumb_url ?? null, lugar_video_url: lg?.video_url ?? null,
          lugar_poligono: (lg?.poligono as [number, number][] | undefined) ?? null,
        };
      });
    }
  } else {
    console.warn("getComerciosMapa: hasSupabase=false — faltan NEXT_PUBLIC_SUPABASE_URL/ANON_KEY");
  }
  return DEMO_COMERCIOS.map((c) => ({
    id: c.id, slug: c.slug, nombre: c.nombre, lat: c.lat, lng: c.lng,
    logo_url: c.logo_url, portada_url: c.portada_url, portada_thumb_url: null, whatsapp: c.whatsapp, telefono: c.telefono,
    verificado: c.verificado, destacado: c.destacado, rating: c.rating,
    direccion: c.direccion, descripcion: c.descripcion, prod_obs_human: null, prod_det_ia: null, subcategoria: null, horario: c.horario, como_llegar: c.como_llegar,
    rubro_slug: null, plan: c.plan, ficha_activa: c.plan !== "gratis",
    rubro_slugs: [],
    lugar_id: null, puesto: null, lugar_nombre: null, lugar_lat: null, lugar_lng: null,
    lugar_portada_thumb_url: null, lugar_video_url: null, lugar_poligono: null,
  }));
}

export type LugarPublico = { id: string; nombre: string; tipo: string; portada_thumb_url: string | null; n_comercios: number };

/** Mercados/galerías activos con al menos un comercio, para el home. */
export async function getLugaresPublicos(limit = 12): Promise<LugarPublico[]> {
  if (!hasSupabase) return [];
  const { data } = await supabase
    .from("lugares")
    .select("id, nombre, tipo, portada_thumb_url, comercios(count)")
    .eq("activo", true)
    .order("nombre");
  return (data ?? [])
    .map((l: any) => ({ id: l.id, nombre: l.nombre, tipo: l.tipo, portada_thumb_url: l.portada_thumb_url ?? null, n_comercios: l.comercios?.[0]?.count ?? 0 }))
    .filter((l) => l.n_comercios > 0)
    .slice(0, limit);
}

export async function getComercioBySlug(slug: string): Promise<Comercio | null> {
  if (hasSupabase) {
    const { data } = await supabase.from("comercios").select("*").eq("slug", slug).limit(1);
    const comercio = data?.[0] as Comercio | undefined;
    if (!comercio) return null;
    // Query chica aparte (no embed) — mismo motivo que getComerciosMapa: el
    // embed sobre "comercios" es lento por el import OSM masivo de esa tabla.
    if (comercio.rubro_id) {
      const { data: rubro } = await supabase.from("rubros").select("slug, nombre").eq("id", comercio.rubro_id).limit(1);
      if (rubro?.[0]) { comercio.rubro_slug = rubro[0].slug; comercio.rubro_nombre = rubro[0].nombre; }
    }
    return comercio;
  }
  return DEMO_COMERCIOS.find((c) => c.slug === slug) ?? DEMO_COMERCIOS[0];
}

// Contenido de la home Inicio (migración 0032): cotizaciones, clima, videos promo.
export type Cotizacion = { clave: string; etiqueta: string; detalle: string | null; valor: number | null; unidad: string | null };
export type Clima = { temp_c: number | null; descripcion: string | null; icono: string | null };
export type VideoPromo = { id: string; titulo: string | null; url: string };

export async function getCotizaciones(): Promise<Cotizacion[]> {
  if (!hasSupabase) return [];
  const { data } = await supabase.from("cotizaciones").select("clave, etiqueta, detalle, valor, unidad, orden").order("orden");
  const rows = (data as Cotizacion[]) ?? [];
  // Dedup por clave prefiriendo la fila con valor: si hay duplicados (una con valor y
  // otra en null), sin orden estable cada fetch agarraba una distinta → el hero mostraba
  // "s/d" y la barra superior el valor. Así ambos leen siempre la fila con dato.
  const porClave = new Map<string, Cotizacion>();
  for (const r of rows) {
    const prev = porClave.get(r.clave);
    if (!prev || (prev.valor == null && r.valor != null)) porClave.set(r.clave, r);
  }
  return [...porClave.values()];
}
export async function getClima(): Promise<Clima | null> {
  if (!hasSupabase) return null;
  const { data } = await supabase.from("clima").select("temp_c, descripcion, icono").eq("id", 1).limit(1);
  return (data?.[0] as Clima) ?? null;
}
export type Red = { clave: string; etiqueta: string; url: string | null };
export async function getRedes(): Promise<Red[]> {
  if (!hasSupabase) return [];
  const { data } = await supabase.from("redes_sociales").select("clave, etiqueta, url, orden").order("orden");
  return (data as Red[]) ?? [];
}

export async function getVideosPromo(limit = 8): Promise<VideoPromo[]> {
  if (!hasSupabase) return [];
  const { data } = await supabase.from("videos_promocionales").select("id, titulo, url, orden").eq("activo", true).order("orden").limit(limit);
  return (data as VideoPromo[]) ?? [];
}

// Videos recientes de comercios ("Recorrimos Bermejo" en la home Inicio).
export type VideoRecap = { id: string; url: string; comercio_slug: string; comercio_nombre: string; portada_thumb_url: string | null };
export async function getVideosRecientes(limit = 8): Promise<VideoRecap[]> {
  if (!hasSupabase) return [];
  const { data: vids } = await supabase
    .from("comercio_videos").select("id, url, comercio_id").order("created_at", { ascending: false }).limit(limit);
  if (!vids || vids.length === 0) return [];
  const ids = [...new Set((vids as any[]).map((v) => v.comercio_id))];
  const { data: coms } = await supabase.from("comercios").select("id, slug, nombre, portada_thumb_url").in("id", ids);
  const byId = new Map((coms ?? []).map((c: any) => [c.id, c]));
  return (vids as any[]).map((v) => {
    const c = byId.get(v.comercio_id) ?? {};
    return { id: v.id, url: v.url, comercio_slug: c.slug ?? "", comercio_nombre: c.nombre ?? "", portada_thumb_url: c.portada_thumb_url ?? null };
  }).filter((v) => v.comercio_slug);
}

// Galería del comercio (migración 0030): fotos con thumb + videos. Lectura
// pública (anon) — las tarjetas usan el thumb, la ficha amplía a la grande.
export type GaleriaFoto = { id: string; url: string; thumb_url: string | null };
export type GaleriaVideo = { id: string; url: string; duracion_seg: number | null };
export async function getGaleriaComercio(comercioId: string): Promise<{ fotos: GaleriaFoto[]; videos: GaleriaVideo[] }> {
  if (!hasSupabase) return { fotos: [], videos: [] };
  const [{ data: fotos }, { data: videos }] = await Promise.all([
    supabase.from("comercio_fotos").select("id, url, thumb_url").eq("comercio_id", comercioId).order("orden"),
    supabase.from("comercio_videos").select("id, url, duracion_seg").eq("comercio_id", comercioId).order("orden"),
  ]);
  return { fotos: (fotos as GaleriaFoto[]) ?? [], videos: (videos as GaleriaVideo[]) ?? [] };
}

// Productos reales del comercio: viven en Reservalo. Acá leemos la referencia
// (producto_ref, migración 0015) — solo lo publicado y con link a Reservalo.
export async function getProductos(comercioId: string): Promise<Producto[]> {
  if (hasSupabase) {
    const { data } = await supabase
      .from("producto_ref")
      .select("id, comercio_id, titulo, precio, moneda, url")
      .eq("comercio_id", comercioId)
      .eq("estado", "publicado")
      .not("url", "is", null);
    if (data) return data.map((d) => ({ id: d.id, comercio_id: d.comercio_id, nombre: d.titulo, precio: d.precio, moneda: d.moneda, url: d.url })) as Producto[];
  }
  return [];
}

export async function getZonas(): Promise<Zona[]> {
  if (hasSupabase) {
    const { data } = await supabase.from("zonas").select("*").order("orden");
    if (data) return data as Zona[];
  }
  return DEMO_ZONAS;
}

/* ----------------- DATOS DEMO (fallback sin Supabase) ----------------- */
const img = (s: string, w: number, h: number) => `https://picsum.photos/seed/${s}/${w}/${h}`;

export const DEMO_ZONAS: Zona[] = [
  { id: "1", slug: "importadoras", nombre: "Zona Importadoras", descripcion: null, color: "#9b5cff", icono: "box" },
  { id: "2", slug: "zona-moda", nombre: "Zona Moda", descripcion: null, color: "#2e6bff", icono: "shirt" },
  { id: "3", slug: "tecnologia", nombre: "Zona Tecnología", descripcion: null, color: "#39ff9e", icono: "cpu" },
  { id: "4", slug: "galerias", nombre: "Galerías", descripcion: null, color: "#ff4d8d", icono: "building" },
  { id: "5", slug: "gastronomia", nombre: "Gastronomía", descripcion: null, color: "#ffc23d", icono: "utensils" },
];

const _demoCampos = { ciudad_id: null, monedas_aceptadas: null, envios_internacionales: false, origen_importacion: null, pedido_minimo: null, tiene_factura: false, horario: null, tiene_stock: true };

export const DEMO_COMERCIOS: Comercio[] = [
  { ..._demoCampos, id: "c1", slug: "importadora-abc", nombre: "Importadora ABC", descripcion: "Electrónica y tecnología a precio de frontera. Mayorista y minorista.", logo_url: img("abclogo", 200, 200), portada_url: "/comercios2.png", whatsapp: "59170000001", telefono: "+591 3 0000001", email: null, tiktok_url: "https://tiktok.com/@importadora.abc", facebook_url: "https://facebook.com/importadoraabc", instagram_url: "https://instagram.com/importadora.abc", sitio_web: "https://importadoraabc.com", direccion: "Galería Central, Local 14 · Bermejo", lat: -22.7361, lng: -64.3433, como_llegar: null, plan: "premium", modalidad: "mayorista", rubro_id: null, verificado: true, rating: 4.9, destacado: true, zona_id: "1" },
  { ..._demoCampos, id: "c2", slug: "moda-bermejo", nombre: "Moda Bermejo", descripcion: "Las últimas tendencias en ropa y calzado.", logo_url: img("modalogo", 200, 200), portada_url: "/comercios3.png", whatsapp: "59170000002", telefono: null, email: null, tiktok_url: "https://tiktok.com/@moda.bermejo", facebook_url: "https://facebook.com/modabermejo", instagram_url: null, sitio_web: null, direccion: "Av. Comercio 245 · Bermejo", lat: null, lng: null, como_llegar: null, plan: "pro", modalidad: "ambos", rubro_id: null, verificado: true, rating: 4.8, destacado: true, zona_id: "2" },
  { ..._demoCampos, id: "c3", slug: "tecno-store", nombre: "Tecno Store", descripcion: "Computadoras, celulares y accesorios.", logo_url: img("teclogo", 200, 200), portada_url: "/comercios4.png", whatsapp: "59170000003", telefono: null, email: null, tiktok_url: null, facebook_url: "https://facebook.com/tecnostore", instagram_url: "https://instagram.com/tecnostore", sitio_web: null, direccion: "Galería Tecnológica, Local 8 · Bermejo", lat: null, lng: null, como_llegar: null, plan: "pro", modalidad: "minorista", rubro_id: null, verificado: false, rating: 4.7, destacado: true, zona_id: "3" },
  { ..._demoCampos, id: "c4", slug: "perfumeria-vip", nombre: "Perfumería VIP", descripcion: "Perfumes importados originales.", logo_url: img("perflogo", 200, 200), portada_url: "/comercios6.png", whatsapp: "59170000004", telefono: null, email: null, tiktok_url: "https://tiktok.com/@perfumeria.vip", facebook_url: null, instagram_url: "https://instagram.com/perfumeria.vip", sitio_web: null, direccion: "Centro Comercial, Local 3 · Bermejo", lat: null, lng: null, como_llegar: null, plan: "premium", modalidad: "minorista", rubro_id: null, verificado: true, rating: 4.9, destacado: true, zona_id: "4" },
  { ..._demoCampos, id: "c5", slug: "calzados-top", nombre: "Calzados Top", descripcion: "Calzado de cuero legítimo.", logo_url: img("calzlogo", 200, 200), portada_url: "/comercio5.png", whatsapp: "59170000005", telefono: null, email: null, tiktok_url: null, facebook_url: "https://facebook.com/calzadostop", instagram_url: null, sitio_web: null, direccion: "Galería Norte, Local 22 · Bermejo", lat: null, lng: null, como_llegar: null, plan: "gratis", modalidad: "ambos", rubro_id: null, verificado: false, rating: 4.6, destacado: true, zona_id: "2" },
];

export const DEMO_FEED: FeedItem[] = [
  { id: "f1", tipo: "oferta", titulo: "iPhone 13 128GB", descripcion: "Sellado, garantía. Precio de frontera.", precio: 499, moneda: "USD", imagen_url: img("iphone13", 700, 440), tiktok_url: null, approved_at: null, created_at: "", comercio_id: "c1", comercio_slug: "importadora-abc", comercio_nombre: "Importadora ABC", comercio_logo: img("abclogo", 80, 80), comercio_whatsapp: "59170000001", comercio_verificado: true, zona_nombre: "Zona Importadoras", descuento_pct: 20, vence_el: "2026-07-31" },
  { id: "f1b", tipo: "oferta", titulo: 'Smart TV 55" 4K', descripcion: "Última generación.", precio: 399, moneda: "USD", imagen_url: img("tv55", 700, 440), tiktok_url: null, approved_at: null, created_at: "", comercio_id: "c1", comercio_slug: "importadora-abc", comercio_nombre: "Importadora ABC", comercio_logo: img("abclogo", 80, 80), comercio_whatsapp: "59170000001", comercio_verificado: true, zona_nombre: "Zona Importadoras", descuento_pct: 15, vence_el: "2026-07-15" },
  { id: "f2", tipo: "oferta", titulo: "Zapatillas Nike Air", descripcion: "Nuevas, todos los talles.", precio: 120, moneda: "BOB", imagen_url: img("nike", 700, 440), tiktok_url: null, approved_at: null, created_at: "", comercio_id: "c2", comercio_slug: "moda-bermejo", comercio_nombre: "Moda Bermejo", comercio_logo: img("modalogo", 80, 80), comercio_whatsapp: "59170000002", comercio_verificado: true, zona_nombre: "Zona Moda", descuento_pct: 10, vence_el: "2026-07-20" },
  { id: "f3", tipo: "video", titulo: "Unboxing Smart TV", descripcion: "Mirá la review completa.", precio: null, moneda: "BOB", imagen_url: img("tvbox", 700, 440), tiktok_url: "https://tiktok.com/@tecnostore/video/123", approved_at: null, created_at: "", comercio_id: "c3", comercio_slug: "tecno-store", comercio_nombre: "Tecno Store", comercio_logo: img("teclogo", 80, 80), comercio_whatsapp: "59170000003", comercio_verificado: false, zona_nombre: "Zona Tecnología", descuento_pct: null, vence_el: null },
  { id: "f4", tipo: "oferta", titulo: "Perfume 212 VIP", descripcion: "Original importado.", precio: 250, moneda: "BOB", imagen_url: img("perfume", 700, 440), tiktok_url: null, approved_at: null, created_at: "", comercio_id: "c4", comercio_slug: "perfumeria-vip", comercio_nombre: "Perfumería VIP", comercio_logo: img("perflogo", 80, 80), comercio_whatsapp: "59170000004", comercio_verificado: true, zona_nombre: "Centro", descuento_pct: null, vence_el: null },
];

/**
 * Los adornos del mapa: chalanas, lapachos y banderas ubicados a mano desde el
 * admin.
 *
 * Falla en silencio devolviendo lista vacía. Es decoración: si la tabla todavía
 * no existe o la consulta se cae, el mapa tiene que dibujarse igual con sus
 * comercios. Quedarse sin un lapacho no es un problema; quedarse sin el mapa sí.
 */
export async function getAdornosMapa(): Promise<Adorno[]> {
  if (!hasSupabase) return [];
  try {
    const { data } = await supabase
      .from("mapa_adornos")
      // `variante` NO es opcional acá aunque sólo la usen las banderas: sin
      // ella todas se dibujarían con el color por defecto y el mapa mostraría
      // la bandera equivocada, que es peor que no mostrar ninguna.
      .select("id, tipo, variante, lat, lng, giro, escala")
      .eq("activo", true);
    return (data ?? []) as Adorno[];
  } catch {
    return [];
  }
}
