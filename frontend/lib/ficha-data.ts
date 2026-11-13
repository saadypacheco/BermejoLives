import "server-only";
import { cache } from "react";
import {
  getCiudades, getCiudadesReales, getCityCategoryPages, getComercioBySlugEstricto, getFuncionesDePlan, getGaleriaComercio,
  getOfertasComercio, getPlanPublico, getTurnosDeFarmacia,
} from "@/lib/data";
import { hasSupabase } from "@/lib/supabase";
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
 *
 * ERROR ≠ NO EXISTE: lo que decide el 404, la ciudad del encabezado y el `noindex`
 * (el comercio y las ciudades) se lee de forma estricta y, si falla,
 * LANZA. Next entonces sigue sirviendo la versión anterior y no guarda el fallo; un
 * `null` o un `[]` por error quedaba fijo 5 minutos como 404 o como «Bermejo».
 */

const CIUDAD_RESPALDO: Ciudad = {
  id: "", slug: "bermejo", nombre: "Bermejo", departamento: "Tarija", lat: -22.7361, lng: -64.3433,
  es_frontera: true, activa: true, orden: 1, pais: "Bolivia",
};

/** Las ciudades; lanza si la base está configurada y la lectura falla (el
 *  respaldo demo de `getCiudades` pondría «Bermejo» fijo en la ficha de otra ciudad). */
async function leerCiudades(): Promise<Ciudad[]> {
  if (!hasSupabase) return getCiudades();
  const ciudades = await getCiudadesReales();
  if (ciudades === null) throw new Error("No se pudieron leer las ciudades");
  return ciudades;
}

/** El comercio y las ciudades: lo mínimo para armar título, descripción e imagen.
 *  `null` sólo si la base confirma que el comercio no existe. */
const leerBasico = cache(async (slug: string) => {
  const comercio = await getComercioBySlugEstricto(slug);
  if (!comercio) return null;
  return { comercio, ciudades: await leerCiudades() };
});

/** Todo lo que lee la página, una sola vez por render. */
const leerFicha = cache(async (slug: string) => {
  const basico = await leerBasico(slug);
  if (!basico) return null;
  const { comercio } = basico;
  const ahora = new Date();
  const [pares, feed, galeria, funcionesPlan, planPublico, turnos] = await Promise.all([
    // Tolerante a propósito: sólo decide si las migas enlazan a /{ciudad} y /{ciudad}/{rubro}
    // (no el 404 ni el `noindex`, que salen de los datos del propio comercio). Así la
    // ficha sigue viva aunque la RPC todavía no esté migrada.
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
  // Rubro no comercial (baño, plaza, museo…): la ficha no habla de «negocio» ni de WhatsApp.
  const lugarPublico = comercio.rubro_comercial === false;
  return { ciudad, rubroSlug, rubro, productos, que, indexable, descripcion, lugarPublico };
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
