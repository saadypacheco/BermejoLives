import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { UrukuShell } from "@/components/uruku-shell";
import { Ic, IcRubro } from "@/components/ic";
import { JsonLd } from "@/components/json-ld";
import {
  absoluteUrl, breadcrumbNode, businessPath, categoryPageState, categoryPath, cityPath, collectionPageNode,
  jsonLdGraph, robotsFor,
} from "@/lib/seo";
import { BRAND_NAME } from "@/lib/marca";
import { callesFrecuentes, cortarEnPalabra, enLista, parrafoCategoria, productosFrecuentes } from "@/lib/contenido-categoria";
import { productosDe } from "@/lib/productos";
import { cargarCiudad, cargarLocales, cargarPares } from "../_datos";

/**
 * /{ciudad}/{rubro} — los locales de un rubro en una ciudad, con la lista en el
 * HTML del servidor (nombre, calle, qué vende, enlace a la ficha).
 *
 * Spec: docs/visibilidad-buscadores-ia.md §3.1 y §3.3 (tarea FB1). ISR de una
 * hora; los pares que ya existen se pre-renderizan y `dynamicParams` deja que
 * un par nuevo funcione sin redeploy.
 *   - el par no existe (ciudad inactiva, rubro `otros` o inactivo, sin comercios)
 *     → 404; sin `city_category_pages()` (la RPC todavía no está) tampoco hay
 *     pares y todo da 404: nada se indexa a ciegas.
 *   - existe pero con menos de 5 comercios → 200 con `noindex, follow`.
 * NUNCA un número de comercios en el HTML ni en el JSON-LD.
 */
export const revalidate = 3600;
export const dynamicParams = true;
// force-static: el cliente de datos (lib/supabase.ts) pide todo con `cache: "no-store"`
// y, durante la generación estática (build e ISR), Next lo toma como «página
// dinámica» y la saca del ISR. Con `force-static` no: la página se arma una vez
// y se reusa hasta `revalidate`. Es seguro porque el marco recibe la ciudad por
// `fixedCity` y no lee cookies.
export const dynamic = "force-static";

export async function generateStaticParams(): Promise<{ city: string; category: string }[]> {
  return (await cargarPares()).map((p) => ({ city: p.city_slug, category: p.category_slug }));
}

type Props = { params: { city: string; category: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const [ciudad, pares] = await Promise.all([cargarCiudad(params.city), cargarPares()]);
  const estado = ciudad ? categoryPageState(pares, params.city, params.category) : "missing";
  const par = pares.find((p) => p.city_slug === params.city && p.category_slug === params.category);
  if (!ciudad || estado === "missing" || !par) return { title: "No encontrada", robots: { index: false, follow: false } };

  const locales = await cargarLocales(ciudad.slug, par.category_slug);
  const productos = productosFrecuentes(locales, 6);
  const titulo = `${par.category_name} en ${ciudad.nombre} | ${BRAND_NAME}`;
  const descripcion = cortarEnPalabra(
    productos.length > 0
      ? `${par.category_name} en ${ciudad.nombre}: ${enLista(productos)}. Dónde queda cada local y cómo llegar.`
      : `Dónde quedan los locales de ${par.category_name.toLowerCase()} en ${ciudad.nombre} y qué vende cada uno. Ubicación y cómo llegar.`,
  );
  const url = absoluteUrl(categoryPath(ciudad.slug, par.category_slug));
  return {
    title: { absolute: titulo },
    description: descripcion,
    alternates: { canonical: url },
    robots: robotsFor(estado === "index"),
    openGraph: { title: titulo, description: descripcion, url, siteName: BRAND_NAME, type: "website", locale: "es_BO" },
    twitter: { card: "summary_large_image", title: titulo, description: descripcion },
  };
}

export default async function CategoriaPage({ params }: Props) {
  const [ciudad, pares] = await Promise.all([cargarCiudad(params.city), cargarPares()]);
  if (!ciudad || categoryPageState(pares, params.city, params.category) === "missing") notFound();
  const par = pares.find((p) => p.city_slug === ciudad.slug && p.category_slug === params.category);
  if (!par) notFound();

  const locales = await cargarLocales(ciudad.slug, par.category_slug);
  const calles = callesFrecuentes(locales.map((l) => l.calle), 3, 3);
  const productos = productosFrecuentes(locales, 6);
  const rubro = par.category_name;

  const otrosRubros = pares
    .filter((p) => p.city_slug === ciudad.slug && p.category_slug !== par.category_slug)
    .sort((a, b) => a.category_name.localeCompare(b.category_name, "es"));
  // «El mismo rubro en otras ciudades»: sólo las páginas que se indexan.
  const otrasCiudades = pares.filter((p) => p.category_slug === par.category_slug && p.city_slug !== ciudad.slug && p.indexable);

  const jsonLd = jsonLdGraph([
    breadcrumbNode([
      { name: BRAND_NAME, path: "/" },
      { name: ciudad.nombre, path: cityPath(ciudad.slug) },
      { name: rubro },
    ]),
    collectionPageNode({
      name: `${rubro} en ${ciudad.nombre}`,
      path: categoryPath(ciudad.slug, par.category_slug),
      description: parrafoCategoria({ ciudad: ciudad.nombre, rubro, calles, productos }),
      items: locales.map((l) => ({ name: l.nombre, path: businessPath(l.slug) })),
    }),
  ]);

  const chip = { minHeight: 44, fontSize: 15 } as const;

  return (
    <UrukuShell fixedCity={ciudad} showCatnav={false}>
      <JsonLd data={jsonLd} />
      <div className="uk-container uk-section">
        <nav aria-label="Migas de pan" className="uk-meta" style={{ marginBottom: 12 }}>
          <Link href="/">{BRAND_NAME}</Link><span aria-hidden="true">›</span>
          <Link href={cityPath(ciudad.slug)}>{ciudad.nombre}</Link><span aria-hidden="true">›</span>
          <span aria-current="page">{rubro}</span>
        </nav>

        <h1 style={{ margin: "0 0 10px", fontSize: 30, lineHeight: 1.2 }}>{rubro} en {ciudad.nombre}</h1>
        <p style={{ margin: "0 0 26px", maxWidth: 760, fontSize: 16, lineHeight: 1.55, color: "var(--uk-ink-soft)" }}>
          {parrafoCategoria({ ciudad: ciudad.nombre, rubro, calles, productos })}
        </p>

        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "grid", gap: 12 }}>
          {locales.map((l, i) => {
            const vende = productosDe([l.prod_obs_human, l.prod_det_ia], "", 5).terminos.map((t) => t.texto);
            const donde = l.calle || l.direccion;
            return (
              <li key={l.id} style={{ display: "flex", gap: 14, alignItems: "flex-start", padding: 12, background: "var(--uk-surface)", border: "1px solid var(--uk-line)", borderRadius: "var(--uk-radius-sm)" }}>
                {i < 24 && l.portada_thumb_url && (
                  <img src={l.portada_thumb_url} alt="" width={72} height={72} loading="lazy" decoding="async"
                       style={{ width: 72, height: 72, objectFit: "cover", borderRadius: 10, flexShrink: 0, background: "var(--uk-chip)" }} />
                )}
                <div style={{ minWidth: 0, display: "grid", gap: 4 }}>
                  <h2 style={{ margin: 0, fontSize: 17, lineHeight: 1.3 }}>
                    <Link href={businessPath(l.slug)} style={{ color: "var(--uk-green)" }}>{l.nombre}</Link>
                  </h2>
                  {l.subcategoria && <span style={{ fontSize: 14, color: "var(--uk-ink-soft)" }}>{l.subcategoria}</span>}
                  {donde && (
                    <span className="uk-resdir" style={{ fontSize: 14 }}><Ic n="ubicacion" s={16} /> {donde}</span>
                  )}
                  {vende.length > 0 && <span style={{ fontSize: 14 }}>Vende: {vende.join(", ")}</span>}
                  {l.whatsapp && (
                    <span className="uk-resdir" style={{ fontSize: 14 }}><Ic n="whatsapp" s={16} /> Tiene WhatsApp</span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>

        {otrosRubros.length > 0 && (
          <section aria-labelledby="otros-h" style={{ marginTop: 36 }}>
            <h2 id="otros-h" style={{ margin: "0 0 14px", fontSize: 22 }}>Más rubros en {ciudad.nombre}</h2>
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexWrap: "wrap", gap: 10 }}>
              {otrosRubros.map((r) => (
                <li key={r.category_slug}>
                  <Link href={categoryPath(ciudad.slug, r.category_slug)} className="uk-pill" style={chip}>
                    <IcRubro slug={r.category_slug} s={20} tono="marca" /> {r.category_name}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}

        {otrasCiudades.length > 0 && (
          <section aria-labelledby="ciudades-h" style={{ marginTop: 28 }}>
            <h2 id="ciudades-h" style={{ margin: "0 0 14px", fontSize: 22 }}>{rubro} en otras ciudades</h2>
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexWrap: "wrap", gap: 10 }}>
              {otrasCiudades.map((p) => (
                <li key={p.city_slug}>
                  <Link href={categoryPath(p.city_slug, p.category_slug)} className="uk-pill" style={chip}>
                    <Ic n="ubicacion" s={20} tono="marca" /> {p.city_name}
                  </Link>
                </li>
              ))}
            </ul>
          </section>
        )}
      </div>
    </UrukuShell>
  );
}
