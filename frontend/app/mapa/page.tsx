import { redirect } from "next/navigation";

/** /mapa ya no existe como pantalla propia.
 *
 * Había dos pantallas haciendo casi lo mismo y ninguna completa: /mapa tenía el
 * mapa lindo —adornos, banderas, lapachos— pero no buscador, ni filtros, ni
 * total de resultados, ni las tarjetas con productos y ofertas. /buscar tenía
 * todo eso y un mapa pelado. El botón "Ver mapa completo" de /mapa llevaba
 * justamente al mapa MENOS completo de los dos.
 *
 * Ahora los adornos y el modo descubrimiento viven en el mapa de /buscar, y
 * esta ruta sólo redirige: los enlaces viejos, los favoritos y lo que esté
 * compartido por WhatsApp siguen funcionando.
 */
export default function MapaPage({ searchParams }: { searchParams?: { of?: string } }) {
  redirect(searchParams?.of === "1" ? "/buscar?vista=mapa&of=1" : "/buscar?vista=mapa");
}
