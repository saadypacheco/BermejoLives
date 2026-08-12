import { UrukuShell } from "@/components/uruku-shell";
import { BuscarClient } from "@/components/buscar-client";

export const dynamic = "force-dynamic";

export default function BuscarPage() {
  return (
    <UrukuShell activeCat="Todos">
      <BuscarClient />
    </UrukuShell>
  );
}
