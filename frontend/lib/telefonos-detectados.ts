// Cliente de «Teléfonos en fotos» (docs/telefonos-en-fotos.md › API). Sólo panel interno:
// va con el token del admin (`authFetch`). `authFetch` ya lanza ante cualquier HTTP de
// error con `status` y `detail` colgados, que es lo que usa el panel para distinguir un 409.
import { authFetch } from "@/lib/api";
import {
  MAX_LOTE, construirQuery, normalizarLote, normalizarPagina, normalizarResumen, partirEnLotes, unirResultadosLote,
  type ComoAplicar, type FiltroTelefonos, type PaginaTelefonos, type ResultadoLote, type ResumenTelefonos,
} from "@/lib/telefonos-detectados-pure";

export * from "@/lib/telefonos-detectados-pure";

const BASE = "/admin/telefonos-detectados";
const JSON_HEADERS = { "Content-Type": "application/json" };

export async function listarTelefonos(f: FiltroTelefonos): Promise<PaginaTelefonos> {
  const res = await authFetch(`${BASE}?${construirQuery(f)}`);
  return normalizarPagina(await res.json().catch(() => ({})));
}

export async function resumenTelefonos(): Promise<ResumenTelefonos> {
  const res = await authFetch(`${BASE}/resumen`);
  return normalizarResumen(await res.json().catch(() => ({})));
}

/** Escribe el número en la ficha. Si el comercio ya tenía otro valor el backend contesta
 *  409 (error con `status === 409`); se reenvía con `reemplazar: true` si la persona confirma. */
export async function aplicarTelefono(id: string, como: ComoAplicar, reemplazar = false): Promise<void> {
  await authFetch(`${BASE}/${encodeURIComponent(id)}/aplicar`, {
    method: "POST",
    headers: JSON_HEADERS,
    body: JSON.stringify(reemplazar ? { como, reemplazar: true } : { como }),
  });
}

export async function descartarTelefono(id: string): Promise<void> {
  await authFetch(`${BASE}/${encodeURIComponent(id)}/descartar`, { method: "POST" });
}

/** «Usar como WhatsApp los marcados». El backend admite hasta 100 ids por pedido: si
 *  hay más, se manda en tandas y se juntan los resultados. */
export async function aplicarLote(ids: readonly string[]): Promise<ResultadoLote> {
  const partes: ResultadoLote[] = [];
  const tandas = partirEnLotes(ids, MAX_LOTE);
  for (let i = 0; i < tandas.length; i++) {
    try {
      const res = await authFetch(`${BASE}/aplicar-lote`, {
        method: "POST",
        headers: JSON_HEADERS,
        body: JSON.stringify({ ids: tandas[i] }),
      });
      partes.push(normalizarLote(await res.json().catch(() => ({}))));
    } catch (ex) {
      // Si falla la primera tanda no hay nada que mostrar: se propaga el error. Si falla una
      // posterior, las anteriores YA se aplicaron: se devuelven y el resto queda como saltado.
      if (partes.length === 0) throw ex;
      const motivo = ex instanceof Error ? ex.message : "error";
      partes.push({ aplicados: [], saltados: tandas.slice(i).flat().map((id) => ({ id, motivo })) });
      break;
    }
  }
  return unirResultadosLote(partes);
}
