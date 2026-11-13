import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { UrukuShell } from "@/components/uruku-shell";
import { Ic, type NombreIcono } from "@/components/ic";
import { JsonLd } from "@/components/json-ld";
import { WaLeadLink } from "@/components/wa-lead-link";
import "@/app/styles/turismo.css";
import "@/app/styles/ficha-seo.css";
import {
  absoluteUrl, breadcrumbNode, businessPath, cityPath, collectionPageNode, jsonLdGraph, robotsFor, touristDestinationNode,
} from "@/lib/seo";
import { BRAND_NAME } from "@/lib/marca";
import { HREF_PARA_VISITAR, RUBRO_PARA_VISITAR } from "@/lib/para-visitar";
import { cargarVisitaCiudad, resumenDe } from "@/lib/turismo-ciudad";
import {
  RUBRO_BEBIDAS, RUBRO_HOSPEDAJE, RUBRO_RESTAURANTES, RUBRO_TURISMO, SUBCAT_BODEGA, bajadaVisita, contactoDe,
  mostrarVisitaCiudad, navegacionTurismo, rutaRubro, rutaTurismo, tieneRubro, tituloPaginaTurismo, type LocalTurismo,
} from "@/lib/turismo-ciudad-pure";
import { cargarCiudad, cargarPares } from "../_datos";
import CategoriaPage, { generateMetadata as metadataCategoria } from "../[category]/page";

/**
 * /{ciudad}/turismo — «{Ciudad} para el que la visita» (docs/turismo-home-y-repetidos.md §3).
 *
 * ISR como /{ciudad}: se arma una vez y se reusa una hora, a pedido (`generateStaticParams` vacío: el build no
 * depende de la base). Ciudad inexistente o inactiva → 404. Si una lectura FALLA la página lanza (ver
 * `lib/turismo-ciudad.ts`): nunca se cachea un 404 ni una lista vacía nacidos de un error.
 *
 * Son LISTAS, no un mapa, porque acá están los que no tienen punto: los guías de turismo y las radio móviles.
 * Las listas por rubro que ya existen (visitar, dormir, comer, vinos) se enlazan, no se repiten.
 *
 * COLISIÓN CON EL RUBRO `turismo`: esta ruta fija le gana a `/{ciudad}/[category]` con category = «turismo» (el
 * rubro de los guías y las agencias). Si la ciudad NO tiene lugares para visitar pero sí ese rubro, la página es
 * la lista del rubro de siempre (se delega en `CategoriaPage`): ninguna ciudad pierde su página de turismo.
 *
 * NUNCA un número de comercios acá (ni «22 guías»): sólo nombres.
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

export async function generateMetadata(props: Props): Promise<Metadata> {
  const params = await props.params;
  const ciudad = await cargarCiudad(params.city);
  if (!ciudad) return { title: "No encontrada", robots: { index: false, follow: false } };
  const pares = await cargarPares();
  if (!mostrarVisitaCiudad(pares, ciudad.slug)) {
    // Sin lugares para visitar: es la página del rubro «turismo» de siempre (o un 404).
    return metadataCategoria({ params: Promise.resolve({ city: params.city, category: RUBRO_TURISMO }) });
  }
  const titulo = `${tituloPaginaTurismo(ciudad.nombre)} | ${BRAND_NAME}`;
  const descripcion = `Qué visitar en ${ciudad.nombre}, guías de turismo autorizados, agencias, y dónde dormir, comer y moverte. Con el WhatsApp de cada uno.`;
  const url = absoluteUrl(rutaTurismo(ciudad.slug));
  return {
    title: { absolute: titulo },
    description: descripcion,
    alternates: { canonical: url },
    robots: robotsFor(true),
    openGraph: { title: titulo, description: descripcion, url, siteName: BRAND_NAME, type: "website", locale: "es_BO" },
    twitter: { card: "summary_large_image", title: titulo, description: descripcion },
  };
}

/** Una lista de locales con sus botones: WhatsApp si tiene, llamar si tiene teléfono, y la ficha. */
function ListaLocales({ locales, conTipo = false }: { locales: readonly LocalTurismo[]; conTipo?: boolean }) {
  return (
    <ul className="uk-tur-lista">
      {locales.map((l) => {
        const c = contactoDe(l);
        const tipo = (l.subcategoria ?? "").trim();
        return (
          <li key={l.id} className="uk-tur-item">
            <div>
              <Link href={businessPath(l.slug)} className="uk-tur-nombre">{l.nombre}</Link>
              {conTipo && tipo && <span className="uk-tur-sub">{tipo}</span>}
            </div>
            <div className="uk-tur-acciones">
              {c.whatsapp && (
                <WaLeadLink className="uk-tur-btn wa" comercioId={l.id} whatsapp={c.whatsapp} nombre={l.nombre}
                            mensaje={`Hola ${l.nombre}, te contacto desde URUKU`}>
                  <Ic n="whatsapp" s={18} peso="fill" /> WhatsApp
                </WaLeadLink>
              )}
              {c.llamar && (
                <a className="uk-tur-btn" href={c.llamar}><Ic n="telefono" s={18} /> Llamar</a>
              )}
              <Link href={businessPath(l.slug)} className="uk-tur-btn ghost" aria-label={`Ver la ficha de ${l.nombre}`}>
                Ver ficha
              </Link>
            </div>
          </li>
        );
      })}
    </ul>
  );
}

function Seccion({ id, icono, titulo, bajada, children }: {
  id: string; icono: NombreIcono; titulo: string; bajada: string; children: React.ReactNode;
}) {
  return (
    <section id={id} className="uk-container uk-tur-sec" aria-labelledby={`${id}-h`}>
      <h2 id={`${id}-h`}><span className="ic"><Ic n={icono} s={26} /></span> {titulo}</h2>
      <p>{bajada}</p>
      {children}
    </section>
  );
}

function Enlace({ id, icono, titulo, detalle, href }: { id: string; icono: NombreIcono; titulo: string; detalle: string; href: string }) {
  return (
    <li id={id} className="uk-tur-sec-enlace">
      <Link href={href} className="uk-tur-enlace">
        <span className="ic"><Ic n={icono} s={30} /></span>
        <span><b>{titulo}</b><small>{detalle}</small></span>
        <Ic n="seguir" s={20} className="ir" />
      </Link>
    </li>
  );
}

export default async function TurismoPage(props: Props) {
  const params = await props.params;
  const ciudad = await cargarCiudad(params.city);
  if (!ciudad) notFound();
  const pares = await cargarPares();

  if (!mostrarVisitaCiudad(pares, ciudad.slug)) {
    // Sin lugares para visitar no hay «Visitá»: 404, salvo que la ciudad tenga el rubro `turismo` (ver arriba).
    if (!tieneRubro(pares, ciudad.slug, RUBRO_TURISMO)) notFound();
    return CategoriaPage({ params: Promise.resolve({ city: params.city, category: RUBRO_TURISMO }) });
  }

  const datos = await cargarVisitaCiudad(ciudad.slug);
  const resumen = resumenDe(datos) ?? { guias: false, agencias: false, moverse: false };
  const nav = navegacionTurismo(ciudad.slug, pares, resumen);
  const nombre = ciudad.nombre;
  const hayDormir = tieneRubro(pares, ciudad.slug, RUBRO_HOSPEDAJE);
  const hayComer = tieneRubro(pares, ciudad.slug, RUBRO_RESTAURANTES);
  const hayVinos = tieneRubro(pares, ciudad.slug, RUBRO_BEBIDAS);

  const ruta = rutaTurismo(ciudad.slug);
  const jsonLd = jsonLdGraph([
    breadcrumbNode([
      { name: BRAND_NAME, path: "/" },
      { name: nombre, path: cityPath(ciudad.slug) },
      { name: tituloPaginaTurismo(nombre) },
    ]),
    touristDestinationNode({
      nombre, departamento: ciudad.departamento, pais: ciudad.pais, path: ruta, lat: ciudad.lat, lng: ciudad.lng,
      description: bajadaVisita(nombre),
    }),
    {
      ...collectionPageNode({
        name: tituloPaginaTurismo(nombre),
        path: ruta,
        description: `Lugares para visitar, guías de turismo, agencias y transporte de ${nombre}.`,
        // Los lugares primero (itemListNode corta en 100); sin cantidades (ningún número al público).
        items: [...datos.todosLosLugares, ...datos.agencias, ...datos.moverse, ...datos.guias]
          .map((l) => ({ name: l.nombre, path: businessPath(l.slug) })),
      }),
      about: { "@id": `${absoluteUrl(ruta)}#destino` },
    },
  ]);

  return (
    <UrukuShell fixedCity={ciudad} showCatnav={false}>
      <JsonLd data={jsonLd} />

      <header className="uk-visita uk-visita-pag">
        <span className="uk-visita-sol" aria-hidden="true" />
        <div className="uk-container uk-visita-in">
          <nav aria-label="Migas de pan" className="uk-migas">
            <ol>
              <li><Link href="/">{BRAND_NAME}</Link></li>
              <li><Link href={cityPath(ciudad.slug)}>{nombre}</Link></li>
              <li><span aria-current="page">Turismo</span></li>
            </ol>
          </nav>
          <p className="uk-visita-eyebrow"><Ic n="turismo" s={16} /> Para el que nos visita</p>
          <h1 className="uk-visita-h">{nombre} <span>para el que la visita</span></h1>
          <p className="uk-visita-bajada">{bajadaVisita(nombre)}</p>
          {nav.length > 0 && (
            <nav aria-label="En esta página">
              <ul className="uk-tur-nav">
                {nav.map((n) => <li key={n.id}><a href={`#${n.id}`}>{n.t}</a></li>)}
              </ul>
            </nav>
          )}
        </div>
      </header>

      <section id="visitar" className="uk-container uk-tur-sec" aria-labelledby="visitar-h">
        <h2 id="visitar-h"><span className="ic"><Ic n="para-visitar" s={26} /></span> Qué visitar</h2>
        <p>Plazas, miradores, museos, iglesias y excursiones, con su ubicación en el mapa.</p>
        <ul className="uk-tur-enlaces">
          <Enlace id="visitar-lista" icono="para-visitar" titulo="Todos los lugares para visitar" detalle="La lista, con cada ficha" href={`/${ciudad.slug}/${RUBRO_PARA_VISITAR}`} />
          <Enlace id="visitar-mapa" icono="mapa" titulo="Verlos en el mapa" detalle="Para ubicarte y armar el recorrido" href={HREF_PARA_VISITAR} />
        </ul>
      </section>

      {datos.guias.length > 0 && (
        <Seccion id="guias" icono="visita_guia" titulo="Guías de turismo autorizados"
                 bajada="Escribile directo por WhatsApp o llamá para coordinar el recorrido, el día y el punto de encuentro.">
          <ListaLocales locales={datos.guias} />
        </Seccion>
      )}

      {datos.agencias.length > 0 && (
        <Seccion id="agencias" icono="turismo" titulo="Agencias y operadoras"
                 bajada="Paseos, excursiones y paquetes: consultá fechas y qué incluye con cada una.">
          <ListaLocales locales={datos.agencias} conTipo />
        </Seccion>
      )}

      {(hayDormir || hayComer || hayVinos) && (
        <section className="uk-container uk-tur-sec" aria-labelledby="mas-h">
          <h2 id="mas-h"><span className="ic"><Ic n="ciudad" s={26} /></span> Para tu estadía</h2>
          <p>Dónde dormir, qué probar y dónde brindar. Cada lista tiene la ficha de cada lugar con su contacto.</p>
          <ul className="uk-tur-enlaces cuatro">
            {hayDormir && <Enlace id="dormir" icono="hospedaje" titulo="Dónde dormir" detalle="Hoteles y alojamientos" href={rutaRubro(ciudad.slug, RUBRO_HOSPEDAJE)} />}
            {hayComer && <Enlace id="comer" icono="restaurantes" titulo="Dónde comer" detalle="Restaurantes y comida típica" href={rutaRubro(ciudad.slug, RUBRO_RESTAURANTES)} />}
            {hayVinos && <Enlace id="vinos" icono="visita_vino" titulo="Bodegas y vinos" detalle="Para conocer y comprar" href={`/buscar?rubro=${RUBRO_BEBIDAS}&sub=${encodeURIComponent(SUBCAT_BODEGA)}`} />}
          </ul>
        </section>
      )}

      {datos.moverse.length > 0 && (
        <Seccion id="moverse" icono="taxis" titulo="Cómo moverse"
                 bajada="Radio móviles y traslados a los alrededores. Llamá o escribí para pedir tu viaje.">
          <ListaLocales locales={datos.moverse} conTipo />
        </Seccion>
      )}

      <div className="uk-container uk-tur-pie">
        <Link href={cityPath(ciudad.slug)} className="uk-pill" style={{ minHeight: 44, fontSize: 15 }}>
          <Ic n="ciudad" s={20} tono="marca" /> Todo lo de {nombre}
        </Link>
      </div>
    </UrukuShell>
  );
}
