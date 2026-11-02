import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { UrukuShell } from "@/components/uruku-shell";
import { Ic, IcRubro } from "@/components/ic";
import { JsonLd } from "@/components/json-ld";
import {
  absoluteUrl, breadcrumbNode, categoryPath, cityHasIndexablePage, cityPath, collectionPageNode, indexablePagesOfCity,
  jsonLdGraph, robotsFor,
} from "@/lib/seo";
import { BRAND_NAME } from "@/lib/marca";
import { cargarCiudad, cargarPares, ciudadTieneTurnos } from "./_datos";

/**
 * /{ciudad} — la página de una ciudad: qué rubros tiene y a dónde seguir.
 *
 * Spec: docs/visibilidad-buscadores-ia.md §3.1 y §3.3 (tarea FB1). ISR: se
 * arma una vez y se reusa una hora, a pedido (`generateStaticParams` vacío: el
 * build no depende de la base). Ciudad inexistente, inactiva o con un slug de forma
 * inválida → 404 (sin tocar la base); activa sin ningún rubro indexable → 200 con
 * `noindex, follow`. Si una lectura FALLA la página lanza (ver `_datos.ts`): nunca
 * se cachea un 404 o un `noindex` nacido de un error.
 *
 * NUNCA un número de comercios acá (ni «12 farmacias», ni `numberOfItems`):
 * sólo nombres de rubro.
 */
export const revalidate = 3600;
export const dynamicParams = true;
// force-static: el cliente de datos (lib/supabase.ts) pide todo con `cache: "no-store"`
// y, durante la generación estática (build e ISR), Next lo toma como «página
// dinámica» y la saca del ISR. Con `force-static` no: la página se arma una vez
// y se reusa hasta `revalidate`. Es seguro porque el marco recibe la ciudad por
// `fixedCity` y no lee cookies.
export const dynamic = "force-static";

// Sin pre-render: el build no puede depender de la base (ya se cayó una vez).
export async function generateStaticParams(): Promise<{ city: string }[]> {
  return [];
}

type Props = { params: { city: string } };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const ciudad = await cargarCiudad(params.city);
  if (!ciudad) return { title: "No encontrada", robots: { index: false, follow: false } };
  const pares = await cargarPares();
  const titulo = `Comercios de ${ciudad.nombre} | ${BRAND_NAME}`;
  const descripcion = `Comercios y servicios de ${ciudad.nombre} (${ciudad.departamento}): qué vende cada local, dónde queda y cómo llegar.`;
  const url = absoluteUrl(cityPath(ciudad.slug));
  return {
    title: { absolute: titulo },
    description: descripcion,
    alternates: { canonical: url },
    robots: robotsFor(cityHasIndexablePage(pares, ciudad.slug)),
    openGraph: { title: titulo, description: descripcion, url, siteName: BRAND_NAME, type: "website", locale: "es_BO" },
    twitter: { card: "summary_large_image", title: titulo, description: descripcion },
  };
}

export default async function CiudadPage({ params }: Props) {
  const ciudad = await cargarCiudad(params.city);
  if (!ciudad) notFound();
  const [pares, conTurnos] = await Promise.all([cargarPares(), ciudadTieneTurnos(ciudad.id)]);
  // `null` = no se pudo leer el rol de turnos: lanza en vez de congelar la hora sin el enlace.
  if (conTurnos === null) throw new Error(`No se pudo leer el rol de turnos de ${ciudad.slug}`);

  // Todos los rubros con comercios en la ciudad (también los que todavía no
  // alcanzan para indexarse: son útiles para la persona), por nombre.
  const rubros = pares
    .filter((p) => p.city_slug === ciudad.slug)
    .sort((a, b) => a.category_name.localeCompare(b.category_name, "es"));
  const conGuia = ciudad.guia_activa ?? ciudad.slug === "bermejo";

  const jsonLd = jsonLdGraph([
    breadcrumbNode([{ name: BRAND_NAME, path: "/" }, { name: ciudad.nombre }]),
    collectionPageNode({
      name: `Comercios de ${ciudad.nombre}`,
      path: cityPath(ciudad.slug),
      description: `Rubros de comercios y servicios de ${ciudad.nombre}, ${ciudad.departamento}.`,
      items: indexablePagesOfCity(pares, ciudad.slug).map((p) => ({
        name: `${p.category_name} en ${ciudad.nombre}`, path: categoryPath(ciudad.slug, p.category_slug),
      })),
    }),
  ]);

  const enlaces: { href: string; texto: string; ic: "guia" | "cambio" | "turno_farmacia" | "ofertas" | "novedades" | "mapa" }[] = [
    ...(conGuia ? [{ href: "/guia", texto: "Guía del que cruza", ic: "guia" as const }] : []),
    ...(ciudad.es_frontera ? [{ href: "/cambio", texto: "Cambio del día", ic: "cambio" as const }] : []),
    ...(conTurnos ? [{ href: `/${ciudad.slug}/farmacias-de-turno`, texto: "Farmacias de turno", ic: "turno_farmacia" as const }] : []),
    { href: "/ofertas", texto: "Ofertas", ic: "ofertas" },
    { href: "/novedades", texto: "Novedades", ic: "novedades" },
    { href: "/buscar?vista=mapa", texto: "Mapa de comercios", ic: "mapa" },
  ];

  return (
    <UrukuShell fixedCity={ciudad} showCatnav={false}>
      <JsonLd data={jsonLd} />
      <div className="uk-container uk-section">
        <nav aria-label="Migas de pan" className="uk-meta" style={{ marginBottom: 12 }}>
          <Link href="/">{BRAND_NAME}</Link><span aria-hidden="true">›</span><span aria-current="page">{ciudad.nombre}</span>
        </nav>

        <h1 style={{ margin: "0 0 10px", fontSize: 30, lineHeight: 1.2 }}>Comercios de {ciudad.nombre}, {ciudad.departamento}</h1>
        <p style={{ margin: "0 0 28px", maxWidth: 720, fontSize: 16, lineHeight: 1.55, color: "var(--uk-ink-soft)" }}>
          {ciudad.nombre} en {BRAND_NAME}, la guía de comercios y servicios de Bolivia: qué vende cada local,
          dónde queda y cómo llegar.
        </p>

        <section aria-labelledby="rubros-h">
          <h2 id="rubros-h" style={{ margin: "0 0 14px", fontSize: 22 }}>Qué podés encontrar en {ciudad.nombre}</h2>
          {rubros.length === 0 ? (
            <div className="uk-turno-aviso" role="status">
              <Ic n="dato" s={20} />
              <span>Todavía estamos cargando los comercios de {ciudad.nombre}. Mientras tanto, probá la <Link href="/buscar">búsqueda</Link>.</span>
            </div>
          ) : (
            <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexWrap: "wrap", gap: 10 }}>
              {rubros.map((r) => (
                <li key={r.category_slug}>
                  <Link href={categoryPath(ciudad.slug, r.category_slug)} className="uk-pill"
                        style={{ minHeight: 44, fontSize: 15 }}>
                    <IcRubro slug={r.category_slug} s={20} tono="marca" /> {r.category_name}
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </section>

        <section aria-labelledby="mas-h" style={{ marginTop: 32 }}>
          <h2 id="mas-h" style={{ margin: "0 0 14px", fontSize: 22 }}>Más de {ciudad.nombre}</h2>
          <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexWrap: "wrap", gap: 10 }}>
            {enlaces.map((e) => (
              <li key={e.href}>
                <Link href={e.href} className="uk-pill" style={{ minHeight: 44, fontSize: 15 }}>
                  <Ic n={e.ic} s={20} tono="marca" /> {e.texto}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      </div>
    </UrukuShell>
  );
}
