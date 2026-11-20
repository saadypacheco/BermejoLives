import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { UrukuShell } from "@/components/uruku-shell";
import { Ic } from "@/components/ic";
import { Ilustracion } from "@/components/ilustraciones";
import { JsonLd } from "@/components/json-ld";
import "@/app/styles/sabores.css";
import { absoluteUrl, breadcrumbNode, cityPath, jsonLdGraph, robotsFor } from "@/lib/seo";
import { BRAND_NAME } from "@/lib/marca";
import { tituloSabores } from "@/lib/planes-ciudad-pure";
import { FUENTE_PLATOS, agruparPlatos, rutaSabores } from "@/lib/platos-pure";
import { cargarCiudad, cargarDondeComer, cargarPares, cargarPlatos } from "../_datos";

/**
 * /{ciudad}/sabores — «Sabores chapacos»: los platos, la repostería y las bebidas típicas de la ciudad
 * (docs/home-ciudades.md §15). Sólo los aprobados en el panel; sin fotos (cada tipo lleva su ilustración propia).
 *
 * ISR de una hora, a pedido (`generateStaticParams` vacío: el build no depende de la base). Ciudad inexistente, o
 * ciudad SIN platos aprobados → 404. Si la lectura FALLA la página lanza (ver `../_datos.ts`): nunca se cachea un
 * 404 nacido de un error.
 *
 * ROUTING: esta ruta fija le gana a `/{ciudad}/[category]` con category = «sabores», igual que `turismo` y
 * `farmacias-de-turno`; ningún rubro se llama así.
 *
 * NUNCA un número (ni «32 platos»). Los textos los escribe URUKU (no se copian los de la fuente); se cita la fuente al pie.
 */
export const revalidate = 3600;
export const dynamicParams = true;
// force-static: ver app/[city]/page.tsx (el cliente de datos pide `no-store` y sin esto Next la saca del ISR).
export const dynamic = "force-static";

// Sin pre-render: el build no puede depender de la base (ya se cayó una vez).
export async function generateStaticParams(): Promise<{ city: string }[]> {
  return [];
}

type Props = { params: Promise<{ city: string }> };

const NO_ENCONTRADA: Metadata = { title: "No encontrada", robots: { index: false, follow: false } };

export async function generateMetadata(props: Props): Promise<Metadata> {
  const params = await props.params;
  const ciudad = await cargarCiudad(params.city);
  if (!ciudad) return NO_ENCONTRADA;
  const platos = await cargarPlatos(ciudad.id);
  if (platos.length === 0) return NO_ENCONTRADA;
  const titulo = `${tituloSabores(ciudad.slug, ciudad.nombre)} | ${BRAND_NAME}`;
  const descripcion = `Los platos, la repostería y las bebidas típicas de ${ciudad.nombre}, y dónde probarlos.`;
  const url = absoluteUrl(rutaSabores(ciudad.slug));
  return {
    title: { absolute: titulo },
    description: descripcion,
    alternates: { canonical: url },
    robots: robotsFor(true),
    openGraph: { title: titulo, description: descripcion, url, siteName: BRAND_NAME, type: "website", locale: "es_BO" },
    twitter: { card: "summary_large_image", title: titulo, description: descripcion },
  };
}

export default async function SaboresPage(props: Props) {
  const params = await props.params;
  const ciudad = await cargarCiudad(params.city);
  if (!ciudad) notFound();
  const platos = await cargarPlatos(ciudad.id);
  const secciones = agruparPlatos(platos);
  if (secciones.length === 0) notFound();

  const pares = await cargarPares();
  const hayRestaurantes = pares.some((p) => p.city_slug === ciudad.slug && p.category_slug === "restaurantes");
  const dondeComer = await cargarDondeComer(ciudad.slug, hayRestaurantes);
  const titulo = tituloSabores(ciudad.slug, ciudad.nombre);

  const jsonLd = jsonLdGraph([
    breadcrumbNode([
      { name: BRAND_NAME, path: "/" },
      { name: ciudad.nombre, path: cityPath(ciudad.slug) },
      { name: titulo },
    ]),
  ]);

  return (
    <UrukuShell fixedCity={ciudad} showCatnav={false}>
      <JsonLd data={jsonLd} />
      <div className="uk-container uk-section uk-sab">
        <nav aria-label="Migas de pan" className="uk-meta" style={{ marginBottom: 12 }}>
          <Link href="/">{BRAND_NAME}</Link><span aria-hidden="true">›</span>
          <Link href={cityPath(ciudad.slug)}>{ciudad.nombre}</Link><span aria-hidden="true">›</span>
          <span aria-current="page">{titulo}</span>
        </nav>

        <h1 className="uk-sab-h">{titulo}</h1>
        <p className="uk-sab-bajada">
          Lo que hay que probar en {ciudad.nombre}: platos de la mesa de todos los días, dulces de la tradición y bebidas para brindar.
        </p>

        {dondeComer && (
          <Link href={dondeComer} className="uk-sab-btn">
            <Ic n="restaurantes" s={20} /> Dónde comer comida típica ›
          </Link>
        )}

        {secciones.map((s) => (
          <section key={s.tipo} className="uk-sab-sec" aria-labelledby={`sab-${s.tipo}`}>
            <h2 id={`sab-${s.tipo}`}>{s.titulo}</h2>
            <p className="uk-sab-sec-bajada">{s.bajada}</p>
            <ul className="uk-sab-lista">
              {s.platos.map((p) => (
                <li key={p.id} className="uk-sab-item">
                  <Ilustracion id={s.tipo} className="uk-sab-dib" />
                  <div className="uk-sab-txt">
                    <h3>{p.nombre}</h3>
                    {p.descripcion && <p>{p.descripcion}</p>}
                  </div>
                </li>
              ))}
            </ul>
          </section>
        ))}

        <p className="uk-sab-fuente">
          Datos: <a href={FUENTE_PLATOS.url} target="_blank" rel="noopener noreferrer">{FUENTE_PLATOS.nombre}</a>. Los textos los escribe {BRAND_NAME}.
        </p>
      </div>
    </UrukuShell>
  );
}
