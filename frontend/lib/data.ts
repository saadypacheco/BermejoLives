import { supabase, hasSupabase } from "@/lib/supabase";
import type { Comercio, FeedItem, Producto, Zona, Rubro, Ciudad, ResultadoBusqueda, FiltrosBusqueda } from "@/lib/types";

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
  });
  if (error) {
    console.warn("buscar_comercios error:", error.message);
    return [];
  }
  return (data ?? []) as ResultadoBusqueda[];
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
    if (!error && data) return data as FeedItem[];
  }
  return DEMO_FEED.slice(0, limit);
}

export async function getComercios(): Promise<Comercio[]> {
  if (hasSupabase) {
    const { data } = await supabase.from("comercios").select("*").eq("destacado", true).limit(10);
    if (data) return data as Comercio[];
  }
  return DEMO_COMERCIOS;
}

export type ComercioMapa = {
  id: string; slug: string; nombre: string;
  lat: number | null; lng: number | null;
  logo_url: string | null; portada_url: string | null; whatsapp: string;
  telefono: string | null; verificado: boolean; destacado: boolean; rating: number;
  direccion: string | null; descripcion: string | null; horario: string | null;
  como_llegar: string | null; rubro_slug: string | null;
};

// Comercios geolocalizados para el mapa de la Home (+ auspiciantes/destacados).
// Acotado al área de Bermejo (bbox) y SIN join (el embed era lentísimo sobre la
// tabla con el import OSM masivo). El rubro se resuelve con una query chica aparte.
export async function getComerciosMapa(): Promise<ComercioMapa[]> {
  if (hasSupabase) {
    const [{ data }, { data: rubros }] = await Promise.all([
      supabase
        .from("comercios")
        .select("id, slug, nombre, lat, lng, logo_url, portada_url, whatsapp, telefono, verificado, destacado, rating, direccion, descripcion, horario, como_llegar, rubro_id")
        .eq("activo", true)
        .not("lat", "is", null)
        .gte("lat", -22.90).lte("lat", -22.58)
        .gte("lng", -64.52).lte("lng", -64.16)
        .limit(250),
      supabase.from("rubros").select("id, slug"),
    ]);
    if (data) {
      const slugById = new Map((rubros ?? []).map((r: any) => [r.id, r.slug]));
      return (data as any[]).map((c) => ({
        id: c.id, slug: c.slug, nombre: c.nombre, lat: c.lat, lng: c.lng,
        logo_url: c.logo_url, portada_url: c.portada_url, whatsapp: c.whatsapp, telefono: c.telefono,
        verificado: c.verificado, destacado: c.destacado, rating: c.rating,
        direccion: c.direccion, descripcion: c.descripcion, horario: c.horario, como_llegar: c.como_llegar,
        rubro_slug: slugById.get(c.rubro_id) ?? null,
      }));
    }
  }
  return DEMO_COMERCIOS.map((c) => ({
    id: c.id, slug: c.slug, nombre: c.nombre, lat: c.lat, lng: c.lng,
    logo_url: c.logo_url, portada_url: c.portada_url, whatsapp: c.whatsapp, telefono: c.telefono,
    verificado: c.verificado, destacado: c.destacado, rating: c.rating,
    direccion: c.direccion, descripcion: c.descripcion, horario: c.horario, como_llegar: c.como_llegar,
    rubro_slug: null,
  }));
}

export async function getComercioBySlug(slug: string): Promise<Comercio | null> {
  if (hasSupabase) {
    const { data } = await supabase.from("comercios").select("*").eq("slug", slug).limit(1);
    if (data && data[0]) return data[0] as Comercio;
  }
  return DEMO_COMERCIOS.find((c) => c.slug === slug) ?? DEMO_COMERCIOS[0];
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
