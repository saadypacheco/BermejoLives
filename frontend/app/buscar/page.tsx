import type { Metadata } from "next";
import { Suspense } from "react";
import { UrukuShell } from "@/components/uruku-shell";
import { BuscarClient } from "@/components/buscar-client";
import { ciudadActual } from "@/lib/ciudad-server";
import { AccesosCiudad } from "@/components/accesos-ciudad";
import { buscarComerciosOrNull, getRubros } from "@/lib/data";
import { filtrosDeBusqueda, paramsDeUrl, PRIMERAS_BUSQUEDA, type BusquedaInicial } from "@/lib/buscar-filtros";

export const dynamic = "force-dynamic";

// El buscador no se indexa (docs/visibilidad-buscadores-ia.md §3.7): cada consulta
// es una página casi igual a otra. Se rastrea (`follow`) para que los enlaces a las
// fichas sigan contando; lo que se indexa son las fichas y las páginas por ciudad y rubro.
export const metadata: Metadata = {
  title: "Buscar comercios",
  robots: { index: false, follow: true },
};

type Props = { searchParams?: Record<string, string | string[] | undefined> };

export default async function BuscarPage({ searchParams }: Props) {
  // El buscador arranca parado en la ciudad elegida. Sin esto devolvía comercios
  // de todas: alguien que eligió Santa Cruz buscaba y recibía locales de Bermejo,
  // lo que contradice lo único que acababa de decir.
  const { ciudad } = await ciudadActual();
  const rubro = typeof searchParams?.rubro === "string" ? searchParams.rubro : "";
  // LA PRIMERA TANDA VA EN EL HTML. Antes los resultados los armaba sólo el
  // navegador, así que un rastreador (o ChatGPT, o cualquiera sin JavaScript)
  // leía una pantalla sin un solo comercio y la tomaba por vacía. Se pide acá,
  // con la misma consulta que usa el cliente (lib/buscar-filtros.ts), y se le
  // pasa a BuscarClient para que no la repita. Si la base falla (`null`) NO se
  // pasa nada: el cliente carga como siempre, y nunca se publica «no hay
  // comercios» por un error de lectura.
  const params = paramsDeUrl(searchParams, ciudad?.slug ?? "");
  const [filas, rubros] = await Promise.all([
    buscarComerciosOrNull(filtrosDeBusqueda(params), PRIMERAS_BUSQUEDA, 0),
    getRubros().catch(() => []),
  ]);
  const inicial: BusquedaInicial | undefined = filas ? { params, resultados: filas } : undefined;
  // Cada frontera tiene su guía (0124): sin ella, los accesos a la aduana y
  // al paso no van a ninguna parte.
  const conGuia = ciudad ? (ciudad.guia_activa ?? ciudad.slug === "bermejo") : false;
  // SIN el buscador del header —esta pantalla trae el suyo, en vivo, y con los
  // dos había dos cajas de texto— pero CON la barra de rubros y la fila de
  // servicios, que son las dos del home.
  //
  // Estaban apagadas por la misma razón que el buscador: no duplicar. Pero no
  // duplicaban nada: acá la barra de rubros ES el filtro —marca cuál está
  // puesto y deja saltar a otro sin volver al home— y la fila de servicios es
  // más útil en los resultados que en la portada, porque es donde alguien ya
  // encontró lo que buscaba y ahora necesita un baño o un cajero.
  return (
    <UrukuShell showSearch={false}>
      {/* BuscarClient lee los parámetros de la URL con useSearchParams para
          reaccionar cuando la barra de categorías navega. El App Router exige
          un límite de Suspense alrededor de cualquier componente que lo use. */}
      <Suspense fallback={null}>
        {/* `tilesCiudad` va aparte del slug: es de dónde saca el mapa base ESTA
            ciudad (migración 0068), el dato que permite cambiar de proveedor
            con un UPDATE en vez de un deploy. Se perdió al unificar /mapa con
            /buscar —el mapa viejo lo recibía y el de resultados no—, así que
            durante unos días la columna existía y no la miraba nadie. */}
        {/* Las ofertas no tenían ninguna puerta en esta pantalla: el home tiene
            el botón grande del hero y acá no había nada. Con un rubro puesto
            lleva a las ofertas DE ESE rubro, que es lo que se está mirando. */}
        <BuscarClient
          accesos={<AccesosCiudad conGuia={conGuia} ofertas={rubro || true} />}
          inicial={inicial}
          rubrosIniciales={rubros}
          ciudadInicial={ciudad?.slug ?? ""}
          nombreCiudad={ciudad?.nombre ?? ""}
          tilesCiudad={ciudad ? { id: ciudad.id, tiles_url: ciudad.tiles_url ?? null, tiles_atribucion: ciudad.tiles_atribucion ?? null, lat: ciudad.lat, lng: ciudad.lng } : null}
        />
      </Suspense>
    </UrukuShell>
  );
}
