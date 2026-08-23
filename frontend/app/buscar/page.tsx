import { Suspense } from "react";
import { UrukuShell } from "@/components/uruku-shell";
import { BuscarClient } from "@/components/buscar-client";

export const dynamic = "force-dynamic";

export default function BuscarPage() {
  return (
    <UrukuShell activeCat="Todos">
      {/* BuscarClient lee los parámetros de la URL con useSearchParams para
          reaccionar cuando la barra de categorías navega. El App Router exige
          un límite de Suspense alrededor de cualquier componente que lo use. */}
      <Suspense fallback={null}>
        <BuscarClient />
      </Suspense>
    </UrukuShell>
  );
}
