import { supabase, hasSupabase } from "@/lib/supabase";
import type { Comercio, FeedItem, Producto, Zona, Rubro, Ciudad, ResultadoBusqueda, FiltrosBusqueda } from "@/lib/types";

export async function buscarComercios(f: FiltrosBusqueda): Promise<ResultadoBusqueda[]> {
  if (!hasSupabase) return [];
  const { data, error } = await supabase.rpc("buscar_comercios", {
    q: f.q || null,
    p_rubro: f.rubro || null,
    p_modalidad: f.modalidad || null,
    p_zona: f.zona || null,
    p_precio_min: f.precioMin ?? null,
    p_precio_max: f.precioMax ?? null,
    p_ciudad: f.ciudad || null,
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
  { id: "1", slug: "bermejo", nombre: "Bermejo", departamento: "Tarija", lat: -22.7361, lng: -64.3433, es_frontera: true, activa: true, orden: 1 },
  { id: "2", slug: "yacuiba", nombre: "Yacuiba", departamento: "Tarija", lat: -22.0146, lng: -63.6775, es_frontera: true, activa: false, orden: 2 },
  { id: "3", slug: "villazon", nombre: "Villazón", departamento: "Potosí", lat: -22.0866, lng: -65.5942, es_frontera: true, activa: false, orden: 3 },
  { id: "4", slug: "santa-cruz", nombre: "Santa Cruz", departamento: "Santa Cruz", lat: -17.7833, lng: -63.1821, es_frontera: false, activa: false, orden: 10 },
  { id: "5", slug: "la-paz", nombre: "La Paz", departamento: "La Paz", lat: -16.5, lng: -68.15, es_frontera: false, activa: false, orden: 11 },
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

export async function getComercioBySlug(slug: string): Promise<Comercio | null> {
  if (hasSupabase) {
    const { data } = await supabase.from("comercios").select("*").eq("slug", slug).limit(1);
    if (data && data[0]) return data[0] as Comercio;
  }
  return DEMO_COMERCIOS.find((c) => c.slug === slug) ?? DEMO_COMERCIOS[0];
}

export async function getProductos(comercioId: string): Promise<Producto[]> {
  if (hasSupabase) {
    const { data } = await supabase.from("productos").select("*").eq("comercio_id", comercioId);
    if (data) return data as Producto[];
  }
  return DEMO_PRODUCTOS;
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

export const DEMO_COMERCIOS: Comercio[] = [
  { id: "c1", slug: "importadora-abc", nombre: "Importadora ABC", descripcion: "Electrónica y tecnología a precio de frontera. Mayorista y minorista.", logo_url: img("abclogo", 200, 200), portada_url: "/comercios2.png", whatsapp: "59170000001", telefono: "+591 3 0000001", email: null, tiktok_url: "https://tiktok.com/@importadora.abc", facebook_url: "https://facebook.com/importadoraabc", instagram_url: "https://instagram.com/importadora.abc", sitio_web: "https://importadoraabc.com", direccion: "Galería Central, Local 14 · Bermejo", lat: -22.7361, lng: -64.3433, como_llegar: null, plan: "premium", modalidad: "mayorista", rubro_id: null, verificado: true, rating: 4.9, destacado: true, zona_id: "1" },
  { id: "c2", slug: "moda-bermejo", nombre: "Moda Bermejo", descripcion: "Las últimas tendencias en ropa y calzado.", logo_url: img("modalogo", 200, 200), portada_url: "/comercios3.png", whatsapp: "59170000002", telefono: null, email: null, tiktok_url: "https://tiktok.com/@moda.bermejo", facebook_url: "https://facebook.com/modabermejo", instagram_url: null, sitio_web: null, direccion: "Av. Comercio 245 · Bermejo", lat: null, lng: null, como_llegar: null, plan: "pro", modalidad: "ambos", rubro_id: null, verificado: true, rating: 4.8, destacado: true, zona_id: "2" },
  { id: "c3", slug: "tecno-store", nombre: "Tecno Store", descripcion: "Computadoras, celulares y accesorios.", logo_url: img("teclogo", 200, 200), portada_url: "/comercios4.png", whatsapp: "59170000003", telefono: null, email: null, tiktok_url: null, facebook_url: "https://facebook.com/tecnostore", instagram_url: "https://instagram.com/tecnostore", sitio_web: null, direccion: "Galería Tecnológica, Local 8 · Bermejo", lat: null, lng: null, como_llegar: null, plan: "pro", modalidad: "minorista", rubro_id: null, verificado: false, rating: 4.7, destacado: true, zona_id: "3" },
  { id: "c4", slug: "perfumeria-vip", nombre: "Perfumería VIP", descripcion: "Perfumes importados originales.", logo_url: img("perflogo", 200, 200), portada_url: "/comercios6.png", whatsapp: "59170000004", telefono: null, email: null, tiktok_url: "https://tiktok.com/@perfumeria.vip", facebook_url: null, instagram_url: "https://instagram.com/perfumeria.vip", sitio_web: null, direccion: "Centro Comercial, Local 3 · Bermejo", lat: null, lng: null, como_llegar: null, plan: "premium", modalidad: "minorista", rubro_id: null, verificado: true, rating: 4.9, destacado: true, zona_id: "4" },
  { id: "c5", slug: "calzados-top", nombre: "Calzados Top", descripcion: "Calzado de cuero legítimo.", logo_url: img("calzlogo", 200, 200), portada_url: "/comercio5.png", whatsapp: "59170000005", telefono: null, email: null, tiktok_url: null, facebook_url: "https://facebook.com/calzadostop", instagram_url: null, sitio_web: null, direccion: "Galería Norte, Local 22 · Bermejo", lat: null, lng: null, como_llegar: null, plan: "gratis", modalidad: "ambos", rubro_id: null, verificado: false, rating: 4.6, destacado: true, zona_id: "2" },
];

export const DEMO_PRODUCTOS: Producto[] = [
  { id: "p1", comercio_id: "c1", nombre: "iPhone 13 128GB", descripcion: "Sellado, garantía 6 meses", precio: 499, moneda: "USD", foto_url: img("iphone13", 400, 400), tiktok_url: null, destacado: true },
  { id: "p2", comercio_id: "c1", nombre: 'Smart TV 55" 4K', descripcion: "Última generación", precio: 399, moneda: "USD", foto_url: img("tv55", 400, 400), tiktok_url: null, destacado: true },
  { id: "p3", comercio_id: "c1", nombre: "Notebook Gamer", descripcion: "Stock limitado", precio: 650, moneda: "USD", foto_url: img("laptop", 400, 400), tiktok_url: null, destacado: false },
  { id: "p4", comercio_id: "c1", nombre: "AirPods Pro", descripcion: "Originales", precio: 120, moneda: "USD", foto_url: img("airpods", 400, 400), tiktok_url: null, destacado: false },
];

export const DEMO_FEED: FeedItem[] = [
  { id: "f1", tipo: "oferta", titulo: "iPhone 13 128GB", descripcion: "Sellado, garantía. Precio de frontera.", precio: 499, moneda: "USD", imagen_url: img("iphone13", 700, 440), tiktok_url: null, approved_at: null, created_at: "", comercio_id: "c1", comercio_slug: "importadora-abc", comercio_nombre: "Importadora ABC", comercio_logo: img("abclogo", 80, 80), comercio_whatsapp: "59170000001", comercio_verificado: true, zona_nombre: "Zona Importadoras" },
  { id: "f2", tipo: "oferta", titulo: "Zapatillas Nike Air", descripcion: "Nuevas, todos los talles.", precio: 120, moneda: "BOB", imagen_url: img("nike", 700, 440), tiktok_url: null, approved_at: null, created_at: "", comercio_id: "c2", comercio_slug: "moda-bermejo", comercio_nombre: "Moda Bermejo", comercio_logo: img("modalogo", 80, 80), comercio_whatsapp: "59170000002", comercio_verificado: true, zona_nombre: "Zona Moda" },
  { id: "f3", tipo: "video", titulo: "Unboxing Smart TV", descripcion: "Mirá la review completa.", precio: null, moneda: "BOB", imagen_url: img("tvbox", 700, 440), tiktok_url: "https://tiktok.com/@tecnostore/video/123", approved_at: null, created_at: "", comercio_id: "c3", comercio_slug: "tecno-store", comercio_nombre: "Tecno Store", comercio_logo: img("teclogo", 80, 80), comercio_whatsapp: "59170000003", comercio_verificado: false, zona_nombre: "Zona Tecnología" },
  { id: "f4", tipo: "oferta", titulo: "Perfume 212 VIP", descripcion: "Original importado.", precio: 250, moneda: "BOB", imagen_url: img("perfume", 700, 440), tiktok_url: null, approved_at: null, created_at: "", comercio_id: "c4", comercio_slug: "perfumeria-vip", comercio_nombre: "Perfumería VIP", comercio_logo: img("perflogo", 80, 80), comercio_whatsapp: "59170000004", comercio_verificado: true, zona_nombre: "Centro" },
];
