import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { UrukuShell } from "@/components/uruku-shell";
import { JsonLd } from "@/components/json-ld";
import { FarmaciasTurnoVista, metaFarmaciasTurno } from "@/components/farmacias-turno-vista";
import { breadcrumbNode, cityPath, jsonLdGraph } from "@/lib/seo";
import { BRAND_NAME } from "@/lib/marca";
import { cargarCiudad, cargarTurnos } from "../_datos";

/**
 * /{ciudad}/farmacias-de-turno — la dirección que se indexa de las farmacias de
 * turno (FJ de docs/visibilidad-buscadores-ia.md). La misma pantalla que
 * /farmacias-de-turno, pero con la ciudad en la URL (la de la cookie no la ve un
 * robot). Sólo existe para una ciudad con turnos cargados: el resto da 404.
 *
 * Los turnos cambian a las 08:00 y se leen igual todo el día: 5 minutos de
 * caché. `dynamicParams` deja que cualquier ciudad se arme a pedido.
 */
export const revalidate = 300;
export const dynamicParams = true;
// force-static: el cliente de datos (lib/supabase.ts) pide todo con `cache: "no-store"`
// y, durante la generación estática (build e ISR), Next lo toma como «página
// dinámica» y la saca del ISR. Con `force-static` no: la página se arma una vez
// y se reusa hasta `revalidate`. Es seguro porque el marco recibe la ciudad por
// `fixedCity` y no lee cookies.
export const dynamic = "force-static";

export async function generateStaticParams(): Promise<{ city: string }[]> {
  return [];
}

type Props = { params: { city: string } };

/** Ciudad + turnos. `null` en `turnos` = no se pudo leer: se LANZA (Next no guarda
 *  en caché una página que lanza) en vez de dar un 404 que quedaría fijo 5 minutos
 *  ni un «no hay turnos» que mentiría. */
async function cargar(slug: string) {
  const ciudad = await cargarCiudad(slug);
  if (!ciudad) return null;
  const { ahora, turnos } = await cargarTurnos(ciudad.id, 30);
  if (turnos === null) throw new Error(`No se pudo leer el rol de turnos de ${slug}`);
  return { ciudad, ahora, turnos };
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const datos = await cargar(params.city);
  if (!datos || datos.turnos.length === 0) return { title: "No encontrada", robots: { index: false, follow: false } };
  return metaFarmaciasTurno(datos.ciudad.nombre, datos.turnos, datos.ahora, `/${datos.ciudad.slug}/farmacias-de-turno`);
}

export default async function FarmaciasDeTurnoCiudadPage({ params }: Props) {
  const datos = await cargar(params.city);
  // Sin ciudad, o sin ningún turno cargado → 404 (sólo ciudades con turnos).
  if (!datos || datos.turnos.length === 0) notFound();
  const { ciudad, ahora, turnos } = datos;
  return (
    <UrukuShell fixedCity={ciudad} showCatnav={false}>
      <JsonLd data={jsonLdGraph([
        breadcrumbNode([
          { name: BRAND_NAME, path: "/" },
          { name: ciudad.nombre, path: cityPath(ciudad.slug) },
          { name: "Farmacias de turno" },
        ]),
      ])} />
      <FarmaciasTurnoVista ciudad={ciudad} turnos={turnos} ahora={ahora} />
    </UrukuShell>
  );
}
