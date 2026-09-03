import { Suspense } from "react";
import { UrukuShell } from "@/components/uruku-shell";
import { BuscarClient } from "@/components/buscar-client";
import { ciudadActual } from "@/lib/ciudad-server";

export const dynamic = "force-dynamic";

export default async function BuscarPage() {
  // El buscador arranca parado en la ciudad elegida. Sin esto devolvía comercios
  // de todas: alguien que eligió Santa Cruz buscaba y recibía locales de Bermejo,
  // lo que contradice lo único que acababa de decir.
  const { ciudad } = await ciudadActual();
  // Sin el buscador del header ni la barra de categorías: esta página ya trae
  // los suyos, en vivo. Con los dos, la pantalla mostraba dos cajas de texto y
  // dos filas de chips haciendo lo mismo.
  return (
    <UrukuShell activeCat="Todos" showSearch={false} showCatnav={false}>
      {/* BuscarClient lee los parámetros de la URL con useSearchParams para
          reaccionar cuando la barra de categorías navega. El App Router exige
          un límite de Suspense alrededor de cualquier componente que lo use. */}
      <Suspense fallback={null}>
        {/* `tilesCiudad` va aparte del slug: es de dónde saca el mapa base ESTA
            ciudad (migración 0068), el dato que permite cambiar de proveedor
            con un UPDATE en vez de un deploy. Se perdió al unificar /mapa con
            /buscar —el mapa viejo lo recibía y el de resultados no—, así que
            durante unos días la columna existía y no la miraba nadie. */}
        <BuscarClient
          ciudadInicial={ciudad?.slug ?? ""}
          tilesCiudad={ciudad ? { tiles_url: ciudad.tiles_url ?? null, tiles_atribucion: ciudad.tiles_atribucion ?? null } : null}
        />
      </Suspense>
    </UrukuShell>
  );
}
