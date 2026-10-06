/**
 * La lista de comercios de la ciudad del agente, guardada para reusarla.
 *
 * La pide `/campo/mis-comercios` (la pantalla «Comercios de mi ciudad») y la
 * necesita también el formulario de alta, que avisa «ya está cargado» al tomar
 * el GPS. Las dos pantallas se desmontan al cambiar de una a otra, así que sin
 * esto cada cambio volvería a bajar la lista entera, y sin señal el aviso
 * quedaría vacío justo donde más falta hace.
 *
 *  - En memoria: la lista completa, para que «Comercios de mi ciudad» abra al
 *    instante con lo último que se vio.
 *  - En el celular (localStorage): sólo lo mínimo para reconocer un local
 *    (nombre, rubro, punto y miniatura). Es una lista de LOCALES, sin números
 *    de contacto, y alcanza para el aviso sin conexión.
 *
 * Todo el acceso al almacenamiento va en try/catch: en modo privado o con el
 * sitio bloqueado puede tirar, y el aviso es una ayuda, nunca un requisito.
 */
import type { ComercioAgente } from "@/lib/campo";

export type ComercioCercano = {
  id: string; nombre: string; lat: number; lng: number;
  rubro: string | null; thumb: string | null;
};

const CLAVE = "uruku_campo_cercanos_v1";

let enMemoria: ComercioAgente[] | null = null;

export function listaEnMemoria(): ComercioAgente[] | null {
  return enMemoria;
}

/** Sólo los que tienen punto en el mapa: sin él no hay distancia que calcular. */
export function aCercanos(items: ComercioAgente[]): ComercioCercano[] {
  const r: ComercioCercano[] = [];
  for (const c of items) {
    if (c.lat == null || c.lng == null) continue;
    r.push({
      id: c.id, nombre: c.nombre ?? "", lat: c.lat, lng: c.lng,
      rubro: c.rubros?.nombre ?? null, thumb: c.portada_thumb_url || c.portada_url || null,
    });
  }
  return r;
}

/** Guarda la lista recién bajada (o editada) en memoria y en el celular. */
export function recordarLista(items: ComercioAgente[]): void {
  enMemoria = items;
  try { localStorage.setItem(CLAVE, JSON.stringify(aCercanos(items))); } catch { /* sin almacenamiento: sigue en memoria */ }
}

/** Lo último que quedó guardado en el celular, o null si no hay nada. */
export function cercanosGuardados(): ComercioCercano[] | null {
  if (enMemoria) return aCercanos(enMemoria);
  try {
    const raw = localStorage.getItem(CLAVE);
    return raw ? (JSON.parse(raw) as ComercioCercano[]) : null;
  } catch { return null; }
}

/** Al salir: la lista es de la ciudad de ESTE agente. En un celular compartido
 *  no tiene que quedar a la vista del que entre después. */
export function olvidarLista(): void {
  enMemoria = null;
  try { localStorage.removeItem(CLAVE); } catch { /* nada que borrar */ }
}
