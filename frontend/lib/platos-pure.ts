// Platos típicos (docs/home-ciudades.md §15): lo puro de la página `/{ciudad}/sabores` y de la sección «Platos típicos»
// del panel, sin red ni React, para probarlo con `npm test`.

export type TipoPlato = "plato" | "reposteria" | "bebida";
export type EstadoPlato = "pendiente" | "aprobado" | "rechazado";

/** Una fila de `platos_tipicos`. Sólo nombre, texto propio y el enlace de la fuente: nunca el texto ni las fotos de la nota. */
export type PlatoTipico = {
  id: string;
  ciudad_id: string;
  tipo: TipoPlato;
  nombre: string;
  descripcion: string;
  fuente_url: string | null;
  estado: EstadoPlato;
  activo: boolean;
  updated_at: string | null;
};

/** Las secciones de la página, en su orden, con la ilustración de cada tipo (`components/ilustraciones`). */
export const SECCIONES_PLATOS: readonly { tipo: TipoPlato; titulo: string; bajada: string }[] = [
  { tipo: "plato", titulo: "Platos", bajada: "Lo que se come en la mesa de todos los días y en las fiestas" },
  { tipo: "reposteria", titulo: "Repostería", bajada: "Dulces y postres de la tradición" },
  { tipo: "bebida", titulo: "Bebidas", bajada: "Para brindar y para acompañar la comida" },
];

/** La fuente que se cita al pie de la página. */
export const FUENTE_PLATOS = { nombre: "Turismo de Tarija", url: "https://tarijaturismo.com" } as const;

export const ESTADOS_PLATO: readonly { key: EstadoPlato; label: string }[] = [
  { key: "pendiente", label: "Pendientes" },
  { key: "aprobado", label: "Aprobados" },
  { key: "rechazado", label: "Rechazados" },
];

export const NOMBRE_TIPO_PLATO: Record<TipoPlato, string> = { plato: "Plato", reposteria: "Repostería", bebida: "Bebida" };

export function esTipoPlato(x: unknown): x is TipoPlato {
  return x === "plato" || x === "reposteria" || x === "bebida";
}

export function esEstadoPlato(x: unknown): x is EstadoPlato {
  return x === "pendiente" || x === "aprobado" || x === "rechazado";
}

/** Lo que vino de la base como `PlatoTipico`, o `null` si le falta algo (una fila rota no tumba la página). */
export function platoDeFila(f: unknown): PlatoTipico | null {
  if (typeof f !== "object" || f === null) return null;
  const r = f as Record<string, unknown>;
  if (typeof r.id !== "string" || typeof r.nombre !== "string" || !r.nombre.trim()) return null;
  if (!esTipoPlato(r.tipo) || !esEstadoPlato(r.estado)) return null;
  return {
    id: r.id,
    ciudad_id: typeof r.ciudad_id === "string" ? r.ciudad_id : "",
    tipo: r.tipo,
    nombre: r.nombre.trim(),
    descripcion: typeof r.descripcion === "string" ? r.descripcion.trim() : "",
    fuente_url: typeof r.fuente_url === "string" && r.fuente_url.trim() ? r.fuente_url.trim() : null,
    estado: r.estado,
    activo: r.activo !== false,
    updated_at: typeof r.updated_at === "string" ? r.updated_at : null,
  };
}

export type SeccionPlatos = { tipo: TipoPlato; titulo: string; bajada: string; platos: PlatoTipico[] };

/** Los platos de la página agrupados por tipo, cada grupo por nombre; los tipos sin platos no aparecen. Sólo
 *  los aprobados y activos (la base ya filtra, pero esta es la regla de la página). */
export function agruparPlatos(platos: readonly PlatoTipico[]): SeccionPlatos[] {
  const visibles = platos.filter((p) => p.estado === "aprobado" && p.activo);
  return SECCIONES_PLATOS
    .map((s) => ({ ...s, platos: visibles.filter((p) => p.tipo === s.tipo).sort((a, b) => a.nombre.localeCompare(b.nombre, "es")) }))
    .filter((s) => s.platos.length > 0);
}

// ── El panel ────────────────────────────────────────────────────────────────

/** Lo que se edita de un plato en el panel. */
export type EdicionPlato = { nombre: string; descripcion: string };

export type CambiosPlato = Partial<Pick<PlatoTipico, "nombre" | "descripcion" | "estado" | "activo">>;

export const MAX_NOMBRE_PLATO = 120;
export const MAX_DESCRIPCION_PLATO = 600;

/** Los campos que de verdad cambiaron (lo que se manda en el PATCH), sin espacios de más. `null` = no se puede guardar
 *  (el nombre no puede quedar vacío), con el motivo en `error`. Sin cambios devuelve `{}`. */
export function cambiosDeEdicion(original: PlatoTipico, e: EdicionPlato): { cambios: CambiosPlato; error: string | null } {
  const nombre = e.nombre.trim();
  const descripcion = e.descripcion.trim();
  if (!nombre) return { cambios: {}, error: "El nombre no puede quedar vacío." };
  if (nombre.length > MAX_NOMBRE_PLATO) return { cambios: {}, error: `El nombre admite hasta ${MAX_NOMBRE_PLATO} caracteres.` };
  if (descripcion.length > MAX_DESCRIPCION_PLATO) return { cambios: {}, error: `El texto admite hasta ${MAX_DESCRIPCION_PLATO} caracteres.` };
  const cambios: CambiosPlato = {};
  if (nombre !== original.nombre) cambios.nombre = nombre;
  if (descripcion !== original.descripcion) cambios.descripcion = descripcion;
  return { cambios, error: null };
}

/** ¿Se puede aprobar? Sin texto propio no: la página mostraría un nombre pelado. Rechazar y editar siempre se puede. */
export function puedeAprobarPlato(p: Pick<PlatoTipico, "nombre" | "descripcion">): boolean {
  return p.nombre.trim() !== "" && p.descripcion.trim() !== "";
}

/** La dirección de la página de sabores de una ciudad. */
export const rutaSabores = (ciudadSlug: string): string => `/${ciudadSlug}/sabores`;

/** Las subcategorías de restaurantes que cuentan como comida típica (cómo las guarda la importación de turismo:
 *  `boliviana-regional-criolla` → «Comida boliviana»; las otras por si las carga alguien a mano). El buscador filtra por UNA. */
export const SUBCATEGORIAS_COMIDA_TIPICA: readonly string[] = ["Comida boliviana", "Regional", "Criolla"];

/** A dónde lleva «Dónde comer comida típica ›»: los restaurantes de la primera subcategoría típica que la ciudad tenga; si
 *  ninguna, todos los restaurantes; y si la ciudad no tiene restaurantes, a ningún lado (`null`: el botón no sale). */
export function hrefDondeComer(subcategoriaConLocales: string | null, hayRestaurantes: boolean): string | null {
  if (subcategoriaConLocales) return `/buscar?rubro=restaurantes&sub=${encodeURIComponent(subcategoriaConLocales)}&vista=mapa`;
  return hayRestaurantes ? "/buscar?rubro=restaurantes&vista=mapa" : null;
}
