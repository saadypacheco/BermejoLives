"use client";

import Link from "next/link";
import type { ComponentProps } from "react";
import { conFiltros } from "@/lib/filtros-rapidos";
import { useFiltrosRapidos } from "./use-filtros-rapidos";

/** Un `<Link>` que, si «Abiertos» o «Más cerca» están prendidos, suma `abierto=1` / `cerca=1` cuando va al
 *  buscador o al mapa (docs/home-ciudades.md §3). Los demás enlaces no se tocan. */
export function EnlaceFiltrado({ href, ...resto }: Omit<ComponentProps<typeof Link>, "href"> & { href: string }) {
  const [f] = useFiltrosRapidos();
  return <Link href={conFiltros(href, f)} {...resto} />;
}
