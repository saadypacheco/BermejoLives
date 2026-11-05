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
 * DINÁMICA a propósito (`force-dynamic`): «De turno ahora» depende de la hora del
 * pedido, y bajo ISR quedaba congelado hasta 5 minutos —o, en el borde del cambio
 * de las 08:00, mostraba la farmacia equivocada—. No lee cookies (la ciudad viene
 * en la URL y el marco recibe `fixedCity`), así que no hay nada más que la haga
 * dinámica: es esta directiva. Por eso el título y la descripción NO llevan nombres
 * de farmacias: son los mismos a cualquier hora y ningún proxy ni caché los puede
 * dejar viejos. Los nombres están en el cuerpo, calculados en cada pedido.
 */
export const dynamic = "force-dynamic";

type Props = { params: Promise<{ city: string }> };

/** Ciudad + turnos. `null` en `turnos` = no se pudo leer: se LANZA en vez de dar un
 *  404 o un «no hay turnos» que mentirían. */
async function cargar(slug: string) {
  const ciudad = await cargarCiudad(slug);
  if (!ciudad) return null;
  const { ahora, turnos } = await cargarTurnos(ciudad.id, 30);
  if (turnos === null) throw new Error(`No se pudo leer el rol de turnos de ${slug}`);
  return { ciudad, ahora, turnos };
}

export async function generateMetadata(props: Props): Promise<Metadata> {
  const params = await props.params;
  const datos = await cargar(params.city);
  if (!datos || datos.turnos.length === 0) return { title: "No encontrada", robots: { index: false, follow: false } };
  // Sin turnos en la llamada (`[]`): título y descripción genéricos, sin nombres.
  return metaFarmaciasTurno(datos.ciudad.nombre, [], datos.ahora, `/${datos.ciudad.slug}/farmacias-de-turno`);
}

export default async function FarmaciasDeTurnoCiudadPage(props: Props) {
  const params = await props.params;
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
