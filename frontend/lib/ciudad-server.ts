import { cookies } from "next/headers";
import { getCiudades } from "@/lib/data";
import { resolveCiudad, CIUDAD_COOKIE } from "@/lib/ciudad";
import type { Ciudad } from "@/lib/types";

/** Ciudad seleccionada (cookie) para renderizar en el servidor. Default: 1ª activa.
 *
 *  `elegida` dice si la ciudad la ELIGIÓ alguien o es el respaldo. La
 *  diferencia importa para lo que leen Google y WhatsApp: un robot no manda
 *  cookies, así que para él la ciudad SIEMPRE es el respaldo —hoy Bermejo— y
 *  el buscador terminó publicando «Todo Bermejo en un solo lugar» como el
 *  lema de URUKU para toda Bolivia. Con este dato, el título que ve el robot
 *  puede no nombrar ninguna ciudad. */
export async function ciudadActual(): Promise<{ ciudad: Ciudad | null; ciudades: Ciudad[]; elegida: boolean }> {
  const ciudades = await getCiudades();
  const slug = cookies().get(CIUDAD_COOKIE)?.value;
  const ciudad = resolveCiudad(ciudades, slug);
  return { ciudad, ciudades, elegida: Boolean(slug && ciudad && ciudad.slug === slug) };
}
