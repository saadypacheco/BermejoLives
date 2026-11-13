// La lista de accesos de la fila de servicios del home y de los resultados (components/accesos-ciudad.tsx).
// Está acá, sin React, para poder probarla con `npm test`: qué accesos salen según la ciudad.
import type { NombreIcono } from "@/components/ic";
import { HREF_PARA_VISITAR } from "./para-visitar";

export type Acceso = { i: NombreIcono; t: string; href: string };

const SERVICIOS: Acceso[] = [
  { i: "banos", t: "Baños", href: "/buscar?rubro=banos&vista=mapa" },
  { i: "farmacia", t: "Farmacias", href: "/buscar?rubro=farmacia&vista=mapa" },
  { i: "cajeros", t: "Cajeros", href: "/buscar?rubro=cajeros&vista=mapa" },
  { i: "estacionamiento", t: "Estacionamiento", href: "/buscar?rubro=estacionamiento&vista=mapa" },
  { i: "cambio", t: "Casas de cambio", href: "/cambio" },
  { i: "taxis", t: "Taxis", href: "/buscar?rubro=taxis&vista=mapa" },
  { i: "wifi", t: "WiFi", href: "/buscar?rubro=wifi&vista=mapa" },
  { i: "policia", t: "Policía", href: "/buscar?rubro=emergencias&vista=mapa" },
  { i: "transporte", t: "Transporte", href: "/guia#transporte" },
  { i: "frontera", t: "Frontera", href: "/guia#frontera" },
];

/** Sin guía (ciudad que no es de frontera): se van los dos accesos a la guía
 *  del paso, y el cambio deja de ser una página para ser un rubro del mapa. */
const SIN_GUIA: Acceso[] = SERVICIOS
  .filter((c) => !c.href.startsWith("/guia"))
  .map((c) => (c.href === "/cambio" ? { ...c, t: "Cambio", href: "/buscar?rubro=cambio&vista=mapa" } : c));

/** «Para visitar» (lugares turísticos, 0196): se suma antes del transporte y la frontera, y sólo si la ciudad
 *  tiene el par (ciudad, rubro). Va sin números. */
const PARA_VISITAR: Acceso = { i: "para-visitar", t: "Para visitar", href: HREF_PARA_VISITAR };

/** La fila de accesos de la ciudad: con guía (frontera) o sin ella, y con «Para visitar» si la ciudad lo tiene. */
export function listaAccesos(conGuia: boolean, paraVisitar: boolean): Acceso[] {
  const base = conGuia ? SERVICIOS : SIN_GUIA;
  if (!paraVisitar) return base;
  // Antes de «Transporte» y «Frontera» (las guías); si no hay guías, al final.
  const i = base.findIndex((c) => c.href.startsWith("/guia"));
  return i < 0 ? [...base, PARA_VISITAR] : [...base.slice(0, i), PARA_VISITAR, ...base.slice(i)];
}
