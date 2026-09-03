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
  /** Lo que vio una persona en el local. Dato humano: no lo pisa la IA. */
  prod_obs_human?: string | null;
  /** Lo que detectó la IA en las fotos. Reemplazable. */
  prod_det_ia?: string | null;
  subcategoria?: string | null;
  logo_url: string | null;
  portada_url: string | null;
  whatsapp: string | null;
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
  acepta_reservas?: boolean;
  zona_id: string | null;
  rubro_id: string | null;
  rubro_slug?: string | null;
  rubro_nombre?: string | null;
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
  /** false = punto de la ciudad, no negocio (baños, taxis, trámites). No se le
   *  reclama WhatsApp ni productos, y su ficha no ofrece "Ver ofertas".
   *  Opcional: los rubros cargados antes de la 0083 no lo traen, y ausente
   *  significa comercial — que es el caso de los 44 que ya existían. */
  comercial?: boolean;
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
  /** De dónde saca el mapa base ESTA ciudad. NULL → la del código.
   *  Se cambia con un `update`, sin deploy: es lo que faltó el día que CARTO
   *  cortó y hubo que tocar ocho archivos. */
  tiles_url?: string | null;
  tiles_atribucion?: string | null;
  tiles_tipo?: string | null;
  /** Fondo del hero y foto secundaria. NULL → el frontend usa las por defecto,
   *  así una ciudad recién abierta se ve bien aunque todavía no tenga material. */
  hero_url?: string | null;
  foto_url?: string | null;
};

export type ResultadoBusqueda = {
  id: string;
  slug: string;
  nombre: string;
  descripcion: string | null;
  logo_url: string | null;
  portada_url: string | null;
  /** La versión de 200px. La tarjeta la dibuja a 300 y el globo del mapa a 220,
   *  así que la grande —de 1280px y hasta 330 KB— era diez veces más peso para
   *  verse igual. Con treinta resultados por página eso son varios megas de
   *  datos móviles. La agrega la 0078. */
  portada_thumb_url: string | null;
  whatsapp: string;
  direccion: string | null;
  lat: number | null;
  lng: number | null;
  modalidad: "mayorista" | "minorista" | "ambos";
  rubro_slug: string | null;
  /** Lo que la IA vio en la vidriera ("zapatilla urbana"). Es lo que distingue
   *  a un resultado de otro dentro de la misma búsqueda. */
  subcategoria: string | null;
  /** Cuántos coinciden EN TOTAL, no cuántos vinieron en esta página. Viaja
   *  repetido en cada fila; es el mismo número en todas. */
  total?: number;
  rubro_nombre: string | null;
  zona_nombre: string | null;
  rating: number;
  verificado: boolean;
  ofertas: number;
  /** Quién ocupa la primera vista del mapa cuando no hay filtro puesto. La
   *  0077 los agregó al RPC; `destacado` se marca a mano y `plan` lo pone la
   *  suscripción. */
  destacado?: boolean;
  plan?: string | null;
  /** Lo que vende el local. `prod_obs_human` lo anotó una persona en el
   *  recorrido y `prod_det_ia` lo leyó el modelo de la vidriera; los dos
   *  alimentan el índice de búsqueda desde la 0047, pero recién la 0074 los
   *  devuelve. Ver `productosDe` en lib/productos.ts. */
  prod_obs_human: string | null;
  prod_det_ia: string | null;
  /** `buscar_comercios` ya lo devolvía; el tipo no lo declaraba, así que el dato
   *  llegaba a la pantalla y se tiraba. Sirve para decir "abierto ahora", que es
   *  lo que decide si vale la pena caminar hasta ahí. */
  horario: string | null;
  rank: number;
};

export type FiltrosBusqueda = {
  q?: string;
  rubro?: string;
  /** El chip de refinamiento elegido. Filtra sobre los resultados de la
   *  búsqueda, no sobre el catálogo entero. */
  subcategoria?: string;
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

// Producto real: vive en Reservalo. Encontralo solo guarda la referencia
// (producto_ref, migración 0015) — título/precio son caché de display, `url`
// es el link directo a la ficha en Reservalo.
export type Producto = {
  id: string;
  comercio_id: string;
  nombre: string;
  precio: number | null;
  moneda: "BOB" | "USD" | "ARS";
  url: string | null;
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
  descuento_pct: number | null;
  vence_el: string | null;
  /** 'explorador' = la foto la sacó URUKU en la calle, el comercio no la mandó. */
  origen?: string | null;
  /** A quién le escribe el comprador por ESTA oferta. La vista ya lo resuelve:
   *  el del explorador si lo hay, el del comercio si no. La pantalla no tiene
   *  que saber que existe un explorador, sólo a qué número mandar. */
  contacto_whatsapp?: string | null;
  contacto_es_uruku?: boolean | null;
};

/** "2026-07-31" → "31/07". Devuelve "" si no hay fecha válida. */
export function vencimientoFmt(vence: string | null | undefined): string {
  if (!vence) return "";
  const [, m, d] = vence.split("-");
  return d && m ? `${d}/${m}` : "";
}

export const MONEDA_LABEL: Record<string, string> = { BOB: "Bs", USD: "USD", ARS: "$" };

export function precioFmt(precio: number | null, moneda: string): string {
  if (precio == null) return "";
  const m = MONEDA_LABEL[moneda] ?? moneda;
  return m === "Bs" ? `${precio} Bs` : `${m} ${precio}`;
}

/** El WhatsApp al que va la consulta por una oferta, y qué decirle.
 *
 * Cuando la subió el explorador, la consulta la recibe URUKU y no el comercio:
 * hay que nombrarle el local, porque del otro lado hay una sola persona
 * atendiendo consultas de muchos negocios y "hola, ¿tenés esto?" no le alcanza
 * para saber de qué está hablando.
 */
export function contactoDeOferta(o: {
  titulo: string | null; comercio_nombre: string; comercio_whatsapp: string;
  contacto_whatsapp?: string | null; contacto_es_uruku?: boolean | null;
}): { href: string; esUruku: boolean } {
  const que = o.titulo ?? "esta oferta";
  const esUruku = Boolean(o.contacto_es_uruku);
  const numero = o.contacto_whatsapp || o.comercio_whatsapp;
  const mensaje = esUruku
    ? `Hola URUKU, me interesa "${que}" de ${o.comercio_nombre}. ¿Sigue disponible?`
    : `Hola, me interesa ${que}`;
  return { href: waLink(numero, mensaje), esUruku };
}

export function waLink(numero: string, mensaje: string): string {
  return `https://wa.me/${numero}?text=${encodeURIComponent(mensaje)}`;
}
