// Las secciones del panel y cómo se agrupan en el menú lateral.
//
// FUENTE ÚNICA (docs/admin-rediseno.md): el menú, la URL (`/admin?s=<id>`), el
// tablero (cada «Para hacer» lleva a una sección) y la decisión de qué hace
// cada sección con la ciudad elegida salen de acá. Una sección nueva se agrega
// en este archivo y en ningún otro lugar se lista.

import type { NombreIcono } from "@/components/ic";
import type { ModoCiudad } from "@/components/admin-ciudad";

export type SeccionAdmin =
  | "inicio"
  | "negocios" | "calles" | "lugares" | "importados" | "adornos" | "cambio-numero"
  | "publicaciones" | "whatsapp" | "difusion" | "reclamos"
  | "catalogo" | "rubros" | "revision-rubros"
  | "cargas"
  | "planes" | "suscripciones" | "pagos" | "vencimientos"
  | "monitoreo" | "kpis" | "demanda" | "compradores"
  | "equipo" | "manuales" | "ayuda";

export type DefSeccion = {
  id: SeccionAdmin;
  label: string;
  icono: NombreIcono;
  /** El permiso que pide EL BACKEND para lo que muestra la sección (mirá su
   *  endpoint en moderacion.py). Sin él, la ve todo el panel. Antes varias
   *  (Monitoreo, KPIs, Pagos, Reclamos…) no lo decían: un moderador las veía
   *  en el menú y adentro le daba error. */
  permiso?: string;
  /** Qué hace con la ciudad de la barra de arriba (ver `MODO_CIUDAD` de antes):
   *  filtra / global / pendiente (todavía muestra todas y la barra lo avisa). */
  ciudad: ModoCiudad;
};

export type GrupoMenu = { titulo: string | null; secciones: DefSeccion[] };

export const MENU: GrupoMenu[] = [
  { titulo: null, secciones: [
    { id: "inicio", label: "Inicio", icono: "inicio", ciudad: "filtra" },
  ] },
  { titulo: "Comercios", secciones: [
    { id: "negocios", label: "Negocios", icono: "comercios", permiso: "moderar", ciudad: "filtra" },
    { id: "calles", label: "Calles y horarios", icono: "reloj", permiso: "moderar", ciudad: "filtra" },
    { id: "lugares", label: "Lugares", icono: "mercado", permiso: "lugares", ciudad: "filtra" },
    { id: "importados", label: "Importados", icono: "descargar", permiso: "datos", ciudad: "filtra" },
    { id: "adornos", label: "Adornos", icono: "destacado", permiso: "lugares", ciudad: "filtra" },
    { id: "cambio-numero", label: "Cambios de número", icono: "telefono", permiso: "panel", ciudad: "pendiente" },
  ] },
  { titulo: "Contenido", secciones: [
    { id: "publicaciones", label: "Publicaciones", icono: "ofertas", permiso: "moderar", ciudad: "pendiente" },
    { id: "whatsapp", label: "Recepción", icono: "whatsapp", permiso: "whatsapp", ciudad: "pendiente" },
    { id: "difusion", label: "Difusión", icono: "novedades", permiso: "difusion", ciudad: "pendiente" },
    { id: "reclamos", label: "Reclamos", icono: "dax", permiso: "panel", ciudad: "pendiente" },
  ] },
  { titulo: "Catálogo", secciones: [
    { id: "catalogo", label: "Catálogo", icono: "documentos", permiso: "datos", ciudad: "pendiente" },
    { id: "rubros", label: "Rubros", icono: "cartel", permiso: "rubros", ciudad: "global" },
    { id: "revision-rubros", label: "Revisar rubros", icono: "editar", permiso: "rubros", ciudad: "pendiente" },
  ] },
  { titulo: "Campo", secciones: [
    { id: "cargas", label: "Cargas", icono: "ruta", permiso: "equipo", ciudad: "filtra" },
  ] },
  { titulo: "Negocio", secciones: [
    { id: "planes", label: "Planes", icono: "estrella", permiso: "planes", ciudad: "global" },
    { id: "suscripciones", label: "Suscripciones", icono: "calendario", permiso: "pagos", ciudad: "pendiente" },
    { id: "pagos", label: "Pagos", icono: "pagos", permiso: "pagos", ciudad: "pendiente" },
    { id: "vencimientos", label: "Vencimientos", icono: "aviso", permiso: "moderar", ciudad: "global" },
  ] },
  { titulo: "Análisis", secciones: [
    { id: "monitoreo", label: "Monitoreo", icono: "explorar", permiso: "datos", ciudad: "pendiente" },
    { id: "kpis", label: "KPIs", icono: "estrella", permiso: "datos", ciudad: "pendiente" },
    { id: "demanda", label: "Demanda", icono: "buscar", permiso: "datos", ciudad: "pendiente" },
    { id: "compradores", label: "Compradores", icono: "gente", permiso: "datos", ciudad: "global" },
  ] },
  { titulo: "Equipo", secciones: [
    { id: "equipo", label: "Equipo", icono: "usuario", permiso: "equipo", ciudad: "pendiente" },
    // Sin permiso: los manuales no son secretos y cualquiera del panel los manda.
    // (La lista de agentes sí pide `equipo`: si falta, se ve la versión genérica.)
    { id: "manuales", label: "Manuales", icono: "documento", ciudad: "global" },
    { id: "ayuda", label: "Ayuda", icono: "ayuda", permiso: "ayuda", ciudad: "pendiente" },
  ] },
];

export const SECCIONES: DefSeccion[] = MENU.flatMap((g) => g.secciones);

export function defSeccion(id: SeccionAdmin): DefSeccion {
  return SECCIONES.find((s) => s.id === id) ?? SECCIONES[0];
}

/** Lo que viene en `?s=`: si no es una sección conocida, el Inicio. */
export function seccionDeUrl(s: string | null | undefined): SeccionAdmin {
  return SECCIONES.some((x) => x.id === s) ? (s as SeccionAdmin) : "inicio";
}
