import { authFetch } from "@/lib/api";
import {
  leerCoverDesign, leerEstado, leerGalleryItem,
  type Objetivo, type PhotoStyleState, type Resultado,
} from "@/lib/fotos-estilo-pure";

/**
 * Cliente de las fotos con estilo URUKU (docs/fotos-estilo-uruku.md §5). Una función por ruta, todas con
 * `authFetch` (Bearer del admin; un error del servidor llega como `Error` con el `detail` en español).
 * Las que suben un archivo mandan `multipart/form-data` con el campo `foto`: el navegador pone el
 * `Content-Type` con el boundary, por eso acá no se fija.
 *
 * Los tipos y la lectura tolerante del JSON viven en `lib/fotos-estilo-pure.ts` (se prueban sin red).
 */
export type { Method, Objetivo, PhotoStyleState, Resultado } from "@/lib/fotos-estilo-pure";

const JSON_HEADERS = { "Content-Type": "application/json" };

function base(comercioId: string): string {
  return `/admin/comercio/${encodeURIComponent(comercioId)}`;
}

/** La ruta de la propuesta/diseño del objetivo: `/portada-diseno` o `/fotos/{id}/diseno`. */
function rutaDiseno(comercioId: string, o: Objetivo): string {
  return o.tipo === "cover"
    ? `${base(comercioId)}/portada-diseno`
    : `${base(comercioId)}/fotos/${encodeURIComponent(o.id)}/diseno`;
}

async function leer(res: Response, o: Objetivo): Promise<Resultado> {
  const json: unknown = await res.json().catch(() => ({}));
  return o.tipo === "cover"
    ? { tipo: "cover", data: leerCoverDesign(json) }
    : { tipo: "foto", data: leerGalleryItem(json) };
}

/** `GET /admin/comercio/{id}/fotos-estilo`: la portada, la galería, el estado de la IA y las instrucciones. */
export async function getFotosEstilo(comercioId: string): Promise<PhotoStyleState> {
  const res = await authFetch(`${base(comercioId)}/fotos-estilo`);
  return leerEstado(await res.json().catch(() => ({})));
}

/** Arma una PROPUESTA con `free` (plantilla) o `gemini` (IA, paga). Con `gemini` puede tardar hasta un minuto. */
export async function armarEstilo(comercioId: string, o: Objetivo, method: "free" | "gemini"): Promise<Resultado> {
  const res = await authFetch(rutaDiseno(comercioId, o), { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ method }) });
  return leer(res, o);
}

/** «Subir imagen hecha afuera» (ChatGPT): el archivo pasa por la misma plantilla y queda como propuesta `external`. */
export async function subirImagenExterna(comercioId: string, o: Objetivo, archivo: File): Promise<Resultado> {
  const datos = new FormData();
  datos.append("foto", archivo);
  const res = await authFetch(`${rutaDiseno(comercioId, o)}/externa`, { method: "POST", body: datos });
  return leer(res, o);
}

/** «Usar en la ficha»: la propuesta pasa a ser pública. 400 si no hay propuesta. */
export async function usarEstilo(comercioId: string, o: Objetivo): Promise<Resultado> {
  return leer(await authFetch(rutaDiseno(comercioId, o), { method: "PUT" }), o);
}

/** «Descartar»: la propuesta queda vacía; lo que ya está en la ficha no se toca. */
export async function descartarEstilo(comercioId: string, o: Objetivo): Promise<Resultado> {
  return leer(await authFetch(`${rutaDiseno(comercioId, o)}/propuesta`, { method: "DELETE" }), o);
}

/** «Volver a la original»: la ficha vuelve a mostrar la foto sin diseño. */
export async function quitarEstilo(comercioId: string, o: Objetivo): Promise<Resultado> {
  return leer(await authFetch(rutaDiseno(comercioId, o), { method: "DELETE" }), o);
}

export type UsosPorComercio = { comercio_id: string; nombre: string; images: number; cost_usd: number };
export type UsesSummary = { desde: string; hasta: string; images: number; cost_usd: number; by_merchant: UsosPorComercio[] };

/** `GET /admin/fotos-estilo/usos` (permiso `pagos`): lo gastado con IA en un rango de días (AAAA-MM-DD). */
export async function getUsosFotosEstilo(desde: string, hasta: string): Promise<UsesSummary> {
  const q = new URLSearchParams({ desde, hasta });
  const res = await authFetch(`/admin/fotos-estilo/usos?${q.toString()}`);
  const d: Partial<UsesSummary> = await res.json().catch(() => ({}));
  return {
    desde: d.desde ?? desde, hasta: d.hasta ?? hasta,
    images: Number(d.images ?? 0), cost_usd: Number(d.cost_usd ?? 0),
    by_merchant: Array.isArray(d.by_merchant) ? d.by_merchant : [],
  };
}
