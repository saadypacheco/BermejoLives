import { cache } from "react";
import {
  getCiudades, getCityCategoryPages, getComercioBySlug, getFuncionesDePlan, getGaleriaComercio,
  getOfertasComercio, getPlanPublico, getTurnosDeFarmacia,
} from "@/lib/data";
import { sinEmoji } from "@/lib/rubros";
import { categoryPageState, isBusinessIndexable } from "@/lib/seo";
import { descripcionFicha, productosDeFicha, queEsElComercio } from "@/lib/ficha-seo";
import type { Ciudad, Comercio } from "@/lib/types";

/**
 * Los datos de la ficha de un comercio (`/comercios/[slug]`). Los usan la página,
 * `generateMetadata` y la imagen de vista previa (`opengraph-image.tsx`).
 *
 * La ruta es ISR con `dynamic = "force-static"` (ver page.tsx): `lib/supabase.ts`
 * manda `cache: "no-store"` en cada lectura (a propósito: /cambio, /planes y el
 * panel tienen que ver el dato de AHORA) y, sin `force-static`, un solo `fetch`
 * así —también los del marco: clima, cotización, redes— tira la ficha a render
 * dinámico («Page changed from static to dynamic at runtime»). Con `force-static`
 * las lecturas se hacen al REGENERAR la página (cada `revalidate` segundos), no
 * en cada visita.
 */

const CIUDAD_RESPALDO: Ciudad = {
  id: "", slug: "bermejo", nombre: "Bermejo", departamento: "Tarija", lat: -22.7361, lng: -64.3433,
  es_frontera: true, activa: true, orden: 1, pais: "Bolivia",
};

/** El comercio y las ciudades: lo mínimo para armar título, descripción e imagen. */
const leerBasico = cache(async (slug: string) => {
  const comercio = await getComercioBySlug(slug);
  if (!comercio) return null;
  return { comercio, ciudades: await getCiudades() };
});

/** Todo lo que lee la página, una sola vez por render. */
const leerFicha = cache(async (slug: string) => {
  const basico = await leerBasico(slug);
  if (!basico) return null;
  const { comercio } = basico;
  const ahora = new Date();
  const [pares, feed, galeria, funcionesPlan, planPublico, turnos] = await Promise.all([
    getCityCategoryPages(),
    getOfertasComercio(comercio.id),
    getGaleriaComercio(comercio.id),
    // Las funciones del plan (decide si la ficha lleva el chatbot del local).
    getFuncionesDePlan((comercio as { plan?: string | null }).plan),
    // La estrella «Verificado por URUKU». Si la lectura falla, sin estrella.
    getPlanPublico(comercio.id),
    // El rol de turnos, sólo para las farmacias. El sello lo decide el navegador.
    comercio.rubro_slug === "farmacia" ? getTurnosDeFarmacia(comercio.id, ahora) : Promise.resolve([]),
  ]);
  return { ...basico, pares, feed, galeria, funcionesPlan, planPublico, turnos };
});

/** Ciudad, rubro, «qué» e indexable de un comercio (lo que comparten la ficha y su imagen). */
function derivar(comercio: Comercio, ciudades: readonly Ciudad[]) {
  // Sin ciudad cargada: Bermejo, la primera (misma regla que siempre).
  const ciudad = ciudades.find((x) => x.id === comercio.ciudad_id)
    ?? ciudades.find((x) => x.slug === CIUDAD_RESPALDO.slug) ?? CIUDAD_RESPALDO;
  const rubroSlug = comercio.rubro_slug ?? null;
  const rubro = sinEmoji(comercio.rubro_nombre);
  const productos = productosDeFicha(comercio.prod_obs_human, comercio.prod_det_ia);
  const que = queEsElComercio({
    nombre: comercio.nombre, rubro_slug: rubroSlug, rubro_nombre: comercio.rubro_nombre, subcategoria: comercio.subcategoria,
  });
  // `activo` y `suspendido` vienen en COLUMNAS_COMERCIO pero no en el tipo `Comercio`.
  const estado = comercio as { activo?: boolean; suspendido?: boolean | null };
  const indexable = isBusinessIndexable({
    nombre: comercio.nombre, rubro_slug: rubroSlug, subcategoria: comercio.subcategoria, descripcion: comercio.descripcion,
    prod_obs_human: comercio.prod_obs_human, prod_det_ia: comercio.prod_det_ia, activo: estado.activo, suspendido: estado.suspendido,
  });
  const descripcion = descripcionFicha({
    nombre: comercio.nombre, que, ciudad: ciudad.nombre, departamento: ciudad.departamento,
    descripcion: comercio.descripcion, calle: comercio.direccion || comercio.calle, productos, conWhatsapp: Boolean(comercio.whatsapp),
  });
  return { ciudad, rubroSlug, rubro, productos, que, indexable, descripcion };
}

/** Lo mínimo para la imagen de vista previa (no pide ofertas, galería ni turnos). */
export const cargarFichaBasica = cache(async (slug: string) => {
  const basico = await leerBasico(slug);
  return basico ? { comercio: basico.comercio, ...derivar(basico.comercio, basico.ciudades) } : null;
});

/** Los datos de la ficha completa: lo leído más lo derivado. */
export const cargarFicha = cache(async (slug: string) => {
  const crudo = await leerFicha(slug);
  if (!crudo) return null;
  const d = derivar(crudo.comercio, crudo.ciudades);
  const estadoPar = d.rubroSlug ? categoryPageState(crudo.pares, d.ciudad.slug, d.rubroSlug) : "missing";
  const ciudadConPaginas = crudo.pares.some((p) => p.city_slug === d.ciudad.slug);
  return { ...crudo, ...d, estadoPar, ciudadConPaginas };
});
