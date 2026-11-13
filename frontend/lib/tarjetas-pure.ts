// «Cargar tarjetas» (docs/carga-tarjetas.md): la parte pura de la pantalla, sin red ni
// navegador, para poder probarla con `npm test`.
//
// Acá viven: la validación de los archivos antes de subirlos (el backend vuelve a
// validar; esto evita mandar 200 MB para que digan que no), el texto del estado de la
// ubicación, qué campos cambiaron para el PATCH y la regla de cuándo se puede promover.

import { RUBRO_PARA_VISITAR } from "./para-visitar";

export const MAX_ARCHIVOS = 20;
export const MAX_BYTES = 10 * 1024 * 1024;
export const TIPOS_FOTO = ["image/jpeg", "image/png", "image/webp"] as const;
/** Para el `accept` del input: tipos y extensiones (algunos celulares no informan el tipo). */
export const ACCEPT_FOTOS = "image/jpeg,image/png,image/webp,.jpg,.jpeg,.png,.webp";

export const MSG_SIN_RUTAS = "Esta versión del servidor todavía no tiene la carga de tarjetas";

export type ArchivoLike = { name: string; size: number; type: string };
export type ErrorArchivo = { archivo: string; motivo: string };

function mb(bytes: number): string {
  return (bytes / (1024 * 1024)).toLocaleString("es-BO", { maximumFractionDigits: 1 });
}

/** Algunos teléfonos mandan el tipo vacío: se acepta por extensión. */
export function tipoPermitido(f: ArchivoLike): boolean {
  if ((TIPOS_FOTO as readonly string[]).includes(f.type)) return true;
  if (f.type) return false;
  return /\.(jpe?g|png|webp)$/i.test(f.name);
}

/** Separa lo que se puede subir de lo que no, con el motivo de cada rechazo.
 *  `yaElegidos` cuenta contra el tope de 20: se pueden sumar fotos de a tandas. */
export function validarArchivos<T extends ArchivoLike>(
  nuevos: readonly T[], yaElegidos = 0,
): { validos: T[]; errores: ErrorArchivo[] } {
  const validos: T[] = [];
  const errores: ErrorArchivo[] = [];
  for (const f of nuevos) {
    if (!tipoPermitido(f)) {
      errores.push({ archivo: f.name, motivo: "No es JPEG, PNG ni WebP" });
    } else if (f.size <= 0) {
      errores.push({ archivo: f.name, motivo: "El archivo está vacío" });
    } else if (f.size > MAX_BYTES) {
      errores.push({ archivo: f.name, motivo: `Pesa ${mb(f.size)} MB y el máximo es ${mb(MAX_BYTES)} MB` });
    } else if (yaElegidos + validos.length >= MAX_ARCHIVOS) {
      errores.push({ archivo: f.name, motivo: `Sólo se suben hasta ${MAX_ARCHIVOS} fotos por vez` });
    } else {
      validos.push(f);
    }
  }
  return { validos, errores };
}

// ── Respuesta de la subida ───────────────────────────────────────────────────

export type ResumenCarga = { leidas: number; problemas: number; texto: string };

/** «N tarjetas leídas · M con problemas». */
export function resumenCarga(items: readonly unknown[] | null | undefined, errores: readonly unknown[] | null | undefined): ResumenCarga {
  const leidas = items?.length ?? 0;
  const problemas = errores?.length ?? 0;
  const t = `${leidas} ${leidas === 1 ? "tarjeta leída" : "tarjetas leídas"}`;
  const p = `${problemas} con ${problemas === 1 ? "problema" : "problemas"}`;
  return { leidas, problemas, texto: `${t} · ${p}` };
}

/** Lee `errores` de la respuesta sin confiar en su forma. */
export function erroresDeRespuesta(r: unknown): ErrorArchivo[] {
  const lista = (r as { errores?: unknown } | null)?.errores;
  if (!Array.isArray(lista)) return [];
  return lista.map((e) => {
    const o = (e ?? {}) as { archivo?: unknown; motivo?: unknown };
    return {
      archivo: typeof o.archivo === "string" && o.archivo ? o.archivo : "(sin nombre)",
      motivo: typeof o.motivo === "string" && o.motivo ? o.motivo : "No se pudo leer",
    };
  });
}

/** ¿La ruta no existe en este servidor (todavía no se desplegó el backend de tarjetas)? */
export function esRutaAusente(e: unknown): boolean {
  const s = (e as { status?: number } | null)?.status;
  return s === 404 || s === 405;
}

/** El mensaje de un error de la pantalla: el texto de «versión vieja» si la ruta no existe. */
export function mensajeError(e: unknown, porDefecto: string): string {
  if (esRutaAusente(e)) return MSG_SIN_RUTAS;
  if (e instanceof Error && e.message) return e.message;
  return porDefecto;
}

// ── Ubicación ────────────────────────────────────────────────────────────────

export type EstadoUbicacion = "aproximada" | "confirmada" | "no_encontrada";
export type Tono = "ok" | "aviso" | "error";

export function chipUbicacion(u: string | null | undefined): { texto: string; tono: Tono; icono: "listo" | "aviso" | "ubicacion" } {
  switch (u) {
    case "confirmada": return { texto: "Ubicación confirmada", tono: "ok", icono: "listo" };
    case "aproximada": return { texto: "Ubicación aproximada: confirmá el punto", tono: "aviso", icono: "aviso" };
    case "no_encontrada": return { texto: "No se encontró la dirección: marcá el punto", tono: "error", icono: "aviso" };
    // Un valor nuevo que este front no conoce: se dice tal cual, sin inventar un estado.
    default: return { texto: "Ubicación sin dato: marcá el punto", tono: "aviso", icono: "ubicacion" };
  }
}

export function tienePunto(i: { lat: number | null; lng: number | null }): boolean {
  return typeof i.lat === "number" && typeof i.lng === "number" && Number.isFinite(i.lat) && Number.isFinite(i.lng);
}

/** Resultado de «Buscar la dirección» en texto para quien revisa. */
export function textoUbicar(r: { encontrado?: boolean; display_name?: string | null }): string {
  if (!r.encontrado) return "No se encontró esa dirección. Probá con otra o marcá el punto en el mapa.";
  return r.display_name
    ? `Encontrada: ${r.display_name}. Es aproximada: confirmá el punto.`
    : "Encontrada. Es aproximada: confirmá el punto.";
}

// ── Formulario ↔ PATCH ───────────────────────────────────────────────────────

// `subcategoria` y `horario` son de los lugares para visitar (docs/lugares-turismo.md): en el resto de las filas no
// se tocan, así que el parche no los manda.
export const CAMPOS_EDITABLES = ["nombre", "direccion", "telefono", "whatsapp", "website", "email", "rubro_slug", "subcategoria", "horario"] as const;
export type CampoEditable = (typeof CAMPOS_EDITABLES)[number];
export type FormTarjeta = Record<CampoEditable, string>;
export type PatchTarjeta = Partial<Record<CampoEditable, string>> & { lat?: number; lng?: number };

type FilaConCampos = Partial<Record<CampoEditable, string | null>>;

/** El formulario arranca con lo que tiene la fila; lo vacío es "". */
export function formDeItem(i: FilaConCampos): FormTarjeta {
  const f = {} as FormTarjeta;
  for (const c of CAMPOS_EDITABLES) f[c] = i[c] ?? "";
  return f;
}

/** Sólo los campos que cambiaron (comparados sin espacios en los bordes). Vacío = no hay nada que guardar.
 *  Un campo que se vació va como "" (se borra el dato leído por error). */
export function diffPatch(i: FilaConCampos, form: FormTarjeta): PatchTarjeta {
  const out: PatchTarjeta = {};
  for (const c of CAMPOS_EDITABLES) {
    const antes = (i[c] ?? "").trim();
    const ahora = (form[c] ?? "").trim();
    if (antes !== ahora) out[c] = ahora;
  }
  return out;
}

export function hayCambios(p: PatchTarjeta): boolean {
  return Object.keys(p).length > 0;
}

// ── Promover ─────────────────────────────────────────────────────────────────

/** Se promueve sólo con punto, nombre y lo editado ya guardado (el backend copia lo guardado,
 *  no lo que está a medio escribir en pantalla). `motivo` es lo que se le dice a quien revisa. */
export function puedePromover(
  i: { lat: number | null; lng: number | null },
  form: Pick<FormTarjeta, "nombre">,
  sinGuardar: boolean,
): { ok: boolean; motivo: string } {
  if (sinGuardar) return { ok: false, motivo: "Guardá los cambios antes de promover" };
  if (!tienePunto(i)) return { ok: false, motivo: "Falta el punto en el mapa: buscá la dirección o marcalo" };
  if (!form.nombre.trim()) return { ok: false, motivo: "Falta el nombre del negocio" };
  return { ok: true, motivo: "" };
}

// ── Listado ──────────────────────────────────────────────────────────────────

export type FuenteFiltro = "todas" | "osm" | "tarjeta" | "turismo" | "turismo-visitar";

/** El valor del query param `fuente`; con «todas» no se manda. «Turismo › Para visitar» es `fuente=turismo` + `rubro`. */
export function paramFuente(f: FuenteFiltro): string | undefined {
  if (f === "todas") return undefined;
  return f === "turismo-visitar" ? "turismo" : f;
}

/** El valor del query param `rubro` (slug exacto): sólo el filtro «Turismo › Para visitar» lo manda. */
export function paramRubroImportados(f: FuenteFiltro): string | undefined {
  return f === "turismo-visitar" ? RUBRO_PARA_VISITAR : undefined;
}

/** Sólo `fuente === "tarjeta"` tiene la ficha de revisión de tarjetas. */
export function esTarjeta(i: { fuente: string }): boolean {
  return i.fuente === "tarjeta";
}

/** Tienen la ficha editable (campos, mapa, promover): las tarjetas y lo traído de la página de turismo
 *  (docs/importar-turismo.md). La de turismo es la misma ficha pero sin foto. */
export function usaFichaEditable(i: { fuente: string }): boolean {
  return i.fuente === "tarjeta" || i.fuente === "turismo";
}

/** La primera `http(s)://...` del texto leído: en turismo es la página de origen. null si no hay.
 *  Se le sacan los signos que suelen pegarse al final de una URL en un texto corrido. */
export function urlDeOrigen(texto: string | null | undefined): string | null {
  if (!texto) return null;
  const m = /https?:\/\/[^\s<>"']+/i.exec(texto);
  if (!m) return null;
  const url = m[0].replace(/[.,;:!?)\]]+$/, "");
  try {
    const u = new URL(url);
    return u.protocol === "http:" || u.protocol === "https:" ? u.href : null;
  } catch {
    return null;
  }
}

/** Enlace al panel de negocios para ver el comercio con el que se repite. */
export const ENLACE_NEGOCIOS = "/admin?s=negocios";
