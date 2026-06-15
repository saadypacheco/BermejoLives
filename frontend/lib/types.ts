export type Zona = {
  id: string;
  slug: string;
  nombre: string;
  descripcion: string | null;
  color: string | null;
  icono: string | null;
};

export type Comercio = {
  id: string;
  slug: string;
  nombre: string;
  descripcion: string | null;
  logo_url: string | null;
  portada_url: string | null;
  whatsapp: string;
  telefono: string | null;
  email: string | null;
  tiktok_url: string | null;
  facebook_url: string | null;
  instagram_url: string | null;
  sitio_web: string | null;
  direccion: string | null;
  lat: number | null;
  lng: number | null;
  como_llegar: string | null;
  plan: "gratis" | "pro" | "premium";
  modalidad: "mayorista" | "minorista" | "ambos";
  verificado: boolean;
  rating: number;
  destacado: boolean;
  zona_id: string | null;
  rubro_id: string | null;
  ciudad_id: string | null;
  // Campos fronterizos (migration 0011)
  monedas_aceptadas: string[] | null;
  envios_internacionales: boolean;
  origen_importacion: string[] | null;
  pedido_minimo: string | null;
  tiene_factura: boolean;
  horario: string | null;
  tiene_stock: boolean;
};

export type Rubro = {
  id: string;
  slug: string;
  nombre: string;
  icono: string | null;
};

export type Ciudad = {
  id: string;
  slug: string;
  nombre: string;
  departamento: string;
  lat: number | null;
  lng: number | null;
  es_frontera: boolean;
  activa: boolean;
  orden: number;
  pais: string;
};

export type ResultadoBusqueda = {
  id: string;
  slug: string;
  nombre: string;
  descripcion: string | null;
  logo_url: string | null;
  portada_url: string | null;
  whatsapp: string;
  direccion: string | null;
  lat: number | null;
  lng: number | null;
  modalidad: "mayorista" | "minorista" | "ambos";
  rubro_slug: string | null;
  rubro_nombre: string | null;
  zona_nombre: string | null;
  rating: number;
  verificado: boolean;
  ofertas: number;
  rank: number;
};

export type FiltrosBusqueda = {
  q?: string;
  rubro?: string;
  modalidad?: string;
  zona?: string;
  ciudad?: string;
  precioMin?: number;
  precioMax?: number;
};

export function comoLlegarHref(c: { lat: number | null; lng: number | null; direccion: string | null }): string {
  if (c.lat != null && c.lng != null) {
    return `https://www.google.com/maps/search/?api=1&query=${c.lat},${c.lng}`;
  }
  return `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent((c.direccion ?? "Bermejo") + ", Bolivia")}`;
}

export const MODALIDAD_LABEL: Record<string, string> = {
  mayorista: "Mayorista",
  minorista: "Minorista",
  ambos: "Mayorista y minorista",
};

// Lista de rubros (refleja el seed de la migración 0005). El registro la usa sin
// depender de la red; se puede reemplazar por una lectura a Supabase más adelante.
export const RUBROS: { slug: string; nombre: string }[] = [
  { slug: "importadora", nombre: "Importadora" },
  { slug: "moda", nombre: "Moda y calzado" },
  { slug: "tecnologia", nombre: "Tecnología" },
  { slug: "gastronomia", nombre: "Restaurante / Comida" },
  { slug: "servicios", nombre: "Servicios" },
  { slug: "gomeria", nombre: "Gomería / Repuestos" },
  { slug: "farmacia", nombre: "Farmacia / Salud" },
  { slug: "hogar", nombre: "Hogar y electrodom." },
  { slug: "belleza", nombre: "Belleza y estética" },
  { slug: "mercado", nombre: "Mercado / Abarrotes" },
  { slug: "otros", nombre: "Otros" },
];

export type Producto = {
  id: string;
  comercio_id: string;
  nombre: string;
  descripcion: string | null;
  precio: number | null;
  moneda: "BOB" | "USD" | "ARS";
  foto_url: string | null;
  tiktok_url: string | null;
  destacado: boolean;
};

export type FeedItem = {
  id: string;
  tipo: "oferta" | "video" | "novedad";
  titulo: string | null;
  descripcion: string | null;
  precio: number | null;
  moneda: "BOB" | "USD" | "ARS";
  imagen_url: string | null;
  tiktok_url: string | null;
  approved_at: string | null;
  created_at: string;
  comercio_id: string;
  comercio_slug: string;
  comercio_nombre: string;
  comercio_logo: string | null;
  comercio_whatsapp: string;
  comercio_verificado: boolean;
  zona_nombre: string | null;
};

export const MONEDA_LABEL: Record<string, string> = { BOB: "Bs", USD: "USD", ARS: "$" };

export function precioFmt(precio: number | null, moneda: string): string {
  if (precio == null) return "";
  const m = MONEDA_LABEL[moneda] ?? moneda;
  return m === "Bs" ? `${precio} Bs` : `${m} ${precio}`;
}

export function waLink(numero: string, mensaje: string): string {
  return `https://wa.me/${numero}?text=${encodeURIComponent(mensaje)}`;
}
