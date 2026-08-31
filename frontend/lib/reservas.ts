/** El carrito de reservas del comprador. Vive en su celular, sin cuenta.
 *
 * Pedir login antes de reservar es exactamente donde se pierde a la gente, y
 * más acá: el login de URUKU manda a WhatsApp y hay que volver. El número se
 * pide al CONFIRMAR, cuando dar el número le sirve a quien lo da porque quiere
 * que le avisen.
 *
 * Es un carrito POR COMERCIO. La reserva se manda al WhatsApp de ese local, así
 * que un carrito mezclado no se podría mandar a ningún lado — y se entiende
 * solo, porque el comprador va a caminar a dos lugares distintos.
 */
import type { FeedItem } from "@/lib/types";

const CLAVE = "uruku_reservas";
const EVENTO = "uruku:reservas";

export type ItemReserva = {
  id: string;
  titulo: string | null;
  precio: number | null;
  moneda: string;
  imagen_url: string | null;
  comercio_id: string;
  comercio_slug: string;
  comercio_nombre: string;
  comercio_whatsapp: string;
  agregado_at: string;
};

/** Copia de los datos, no una referencia a la oferta.
 *
 * Si el comerciante borra o edita la publicación, el carrito del comprador
 * tiene que seguir mostrando lo que él eligió. Un carrito que cambia solo
 * mientras la persona decide es peor que uno desactualizado. */
export function itemDeOferta(o: FeedItem): ItemReserva {
  return {
    id: o.id,
    titulo: o.titulo,
    precio: o.precio,
    moneda: o.moneda,
    imagen_url: o.imagen_url,
    comercio_id: o.comercio_id,
    comercio_slug: o.comercio_slug,
    comercio_nombre: o.comercio_nombre,
    comercio_whatsapp: o.comercio_whatsapp,
    agregado_at: new Date().toISOString(),
  };
}

/** Nunca lanza. En navegación privada `localStorage` tira al leer, y que
 *  reviente el carrito no puede tumbar la pantalla entera. */
export function leerReservas(): ItemReserva[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = localStorage.getItem(CLAVE);
    const arr = raw ? JSON.parse(raw) : [];
    return Array.isArray(arr) ? (arr as ItemReserva[]) : [];
  } catch {
    return [];
  }
}

function guardar(items: ItemReserva[]): void {
  try {
    localStorage.setItem(CLAVE, JSON.stringify(items));
  } catch {
    /* cuota llena o modo privado: el carrito de esta sesión sigue en pantalla */
  }
  // Los botones, la barra flotante y la página del carrito viven en árboles de
  // React distintos. Sin este aviso, agregar algo en el buscador dejaba la
  // barra diciendo el número viejo hasta recargar.
  window.dispatchEvent(new CustomEvent(EVENTO));
}

export function estaReservado(ofertaId: string): boolean {
  return leerReservas().some((i) => i.id === ofertaId);
}

/** Agrega o saca. Devuelve si quedó agregado. */
export function alternarReserva(item: ItemReserva): boolean {
  const items = leerReservas();
  const i = items.findIndex((x) => x.id === item.id);
  if (i >= 0) {
    items.splice(i, 1);
    guardar(items);
    return false;
  }
  items.push(item);
  guardar(items);
  return true;
}

export function quitarReserva(ofertaId: string): void {
  guardar(leerReservas().filter((i) => i.id !== ofertaId));
}

export function vaciarComercio(comercioId: string): void {
  guardar(leerReservas().filter((i) => i.comercio_id !== comercioId));
}

export type GrupoReserva = {
  comercio_id: string;
  comercio_slug: string;
  comercio_nombre: string;
  comercio_whatsapp: string;
  items: ItemReserva[];
};

/** Agrupado por comercio, en el orden en que se empezó cada reserva. */
export function porComercio(items = leerReservas()): GrupoReserva[] {
  const mapa = new Map<string, GrupoReserva>();
  for (const it of items) {
    const g = mapa.get(it.comercio_id) ?? {
      comercio_id: it.comercio_id,
      comercio_slug: it.comercio_slug,
      comercio_nombre: it.comercio_nombre,
      comercio_whatsapp: it.comercio_whatsapp,
      items: [],
    };
    g.items.push(it);
    mapa.set(it.comercio_id, g);
  }
  return [...mapa.values()];
}

/** Avisa cuando el carrito cambia, en esta pestaña y en las otras. */
export function alCambiar(fn: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const enOtraPestania = (e: StorageEvent) => { if (e.key === CLAVE) fn(); };
  window.addEventListener(EVENTO, fn);
  window.addEventListener("storage", enOtraPestania);
  return () => {
    window.removeEventListener(EVENTO, fn);
    window.removeEventListener("storage", enOtraPestania);
  };
}
