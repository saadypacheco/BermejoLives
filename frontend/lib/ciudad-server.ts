import { cookies } from "next/headers";
import { getCiudades } from "@/lib/data";
import { resolveCiudad, CIUDAD_COOKIE } from "@/lib/ciudad";
import type { Ciudad } from "@/lib/types";

/** Ciudad seleccionada (cookie) para renderizar en el servidor. Default: 1ª activa. */
export async function ciudadActual(): Promise<{ ciudad: Ciudad | null; ciudades: Ciudad[] }> {
  const ciudades = await getCiudades();
  const slug = cookies().get(CIUDAD_COOKIE)?.value;
  return { ciudad: resolveCiudad(ciudades, slug), ciudades };
}
