// Los manuales de uso (docs/manuales.md): qué manuales hay, cómo se llaman y
// adónde se entra. Lo comparten las páginas /manual/<tipo>, la sección
// «Manuales» del admin y los enlaces de Mi comercio y de la app del agente:
// un manual nuevo se agrega acá y en `content/manuales/<tipo>.md`.

export const TIPOS_MANUAL = ["agente", "admin", "comercio"] as const;
export type TipoManual = (typeof TIPOS_MANUAL)[number];

export function esTipoManual(s: string): s is TipoManual {
  return (TIPOS_MANUAL as readonly string[]).includes(s);
}

/** El nombre del manual: va en el pie de cada hoja y en el nombre del PDF. */
export const TITULO_MANUAL: Record<TipoManual, string> = {
  agente: "Manual del agente",
  admin: "Manual del admin",
  comercio: "Manual del comerciante",
};

/** Los datos con los que se personaliza el manual del agente. */
export type DatosAgente = { nombre?: string | null; ciudad?: string | null; mail?: string | null };

/** `/manual/agente?nombre=…&ciudad=…&mail=…`; lo que no viene, no se pone (y el
 *  manual dice «tu ciudad», «tu correo»). */
export function rutaManualAgente(d: DatosAgente = {}): string {
  const q: string[] = [];
  const poner = (k: string, v?: string | null) => { const t = (v ?? "").trim(); if (t) q.push(`${k}=${encodeURIComponent(t)}`); };
  poner("nombre", d.nombre); poner("ciudad", d.ciudad); poner("mail", d.mail);
  return `/manual/agente${q.length ? `?${q.join("&")}` : ""}`;
}
