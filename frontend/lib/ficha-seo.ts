/**
 * Textos de la ficha de un comercio para buscadores e IA (docs/visibilidad-buscadores-ia.md §3.5).
 *
 * Funciones PURAS (sin red, sin cookies): la ficha (`app/comercios/[slug]/page.tsx`)
 * y su imagen de vista previa (`opengraph-image.tsx`) arman título, descripción y
 * «qué podés encontrar» con ESTO, para que no discrepen. Imports relativos: los
 * tests unitarios (`npm test`) lo cargan con Node sin Next.
 */

/** Sin emoji adelante: «👟 Calzado» → «Calzado» (misma regla que `sinEmoji` de lib/rubros). */
function limpiarRubro(nombre: string | null | undefined): string {
  const n = (nombre ?? "").trim();
  if (!n) return "";
  return n.replace(/^[^\p{L}\p{N}]+/u, "").trim() || n;
}

/** Minúsculas y sin tildes: para comparar «Frazada» con «frazadá» y con «FRAZADA». */
function clave(s: string): string {
  return s.normalize("NFD").replace(/[̀-ͯ]/g, "").toLowerCase().trim();
}

/** Corta en el último espacio antes de `max` y agrega «…» si cortó. */
export function cortarEnPalabra(texto: string, max: number): string {
  const t = texto.replace(/\s+/g, " ").trim();
  if (t.length <= max) return t;
  const corte = t.slice(0, max);
  const ult = corte.lastIndexOf(" ");
  return `${(ult > max * 0.5 ? corte.slice(0, ult) : corte).replace(/[\s,;:.\-–—]+$/, "")}…`;
}

/**
 * «Qué podés encontrar acá» (§3.5): lo que cargó una persona primero
 * (`prod_obs_human`), después lo que leyó la IA de la foto (`prod_det_ia`), sin
 * repetidos (sin tildes ni mayúsculas), tope 20. Los textos vienen separados por
 * coma, punto y coma o «·». Sin datos, `[]`: la sección no se dibuja.
 */
export function productosDeFicha(
  prodObsHuman: string | null | undefined, prodDetIa: string | null | undefined, max = 20,
): string[] {
  const vistos = new Set<string>();
  const out: string[] = [];
  for (const texto of [prodObsHuman, prodDetIa]) {
    for (const crudo of (texto ?? "").split(/[,;·\n]/)) {
      const t = crudo.replace(/\s+/g, " ").trim();
      // Una «etiqueta» de 1 letra o de una oración entera no es un producto.
      if (t.length < 2 || t.length > 60) continue;
      const k = clave(t);
      if (vistos.has(k)) continue;
      vistos.add(k);
      out.push(t);
      if (out.length >= max) return out;
    }
  }
  return out;
}

/**
 * El «qué» del comercio: `subcategoria || rubro` si el rubro no es `otros`; vacío
 * si el nombre ya lo contiene (no se repite «Farmacia Ángeles — Farmacia») o si
 * no hay nada que decir. Nunca «Otros (a clasificar)».
 */
export function queEsElComercio(c: {
  nombre: string; rubro_slug?: string | null; rubro_nombre?: string | null; subcategoria?: string | null;
}): string {
  const sub = (c.subcategoria ?? "").trim();
  const rubro = c.rubro_slug && c.rubro_slug !== "otros" ? limpiarRubro(c.rubro_nombre) : "";
  const que = sub || rubro;
  if (!que) return "";
  return clave(c.nombre).includes(clave(que)) ? "" : que;
}

/** `{Nombre} — {qué} en {Ciudad} | URUKU` (la marca una sola vez). */
export function tituloFicha(nombre: string, que: string, ciudad: string): string {
  return `${nombre.trim()}${que ? ` — ${que}` : ""} en ${ciudad} | URUKU`;
}

/**
 * La descripción de la ficha (§3.5, punto 4):
 *   con `descripcion`: la descripción (cortada en palabra, ≤ 155) + « En {calle}, {Ciudad}.»
 *   con productos:     «{Nombre} en {Ciudad}: vende {productos}.»
 *   sin nada:          «{Nombre}, {qué} en {Ciudad} ({Departamento}). Ubicación en el mapa y cómo llegar.»
 * «WhatsApp» sólo se nombra si el comercio lo tiene.
 */
export function descripcionFicha(o: {
  nombre: string; que: string; ciudad: string; departamento: string;
  descripcion?: string | null; calle?: string | null; productos?: readonly string[]; conWhatsapp?: boolean;
}): string {
  const nombre = o.nombre.trim();
  const desc = (o.descripcion ?? "").trim();
  const calle = (o.calle ?? "").trim();
  const wa = o.conWhatsapp ? " Contacto por WhatsApp." : "";
  if (desc) {
    const base = cortarEnPalabra(desc, 155);
    const fin = /[.!?…]$/.test(base) ? "" : ".";
    return `${base}${fin}${calle ? ` En ${calle}, ${o.ciudad}.` : ` En ${o.ciudad}.`}${wa}`;
  }
  const vende = (o.productos ?? []).slice(0, 6).join(", ");
  if (vende) return `${nombre} en ${o.ciudad}: vende ${vende}.${wa}`;
  return `${nombre}, ${o.que ? `${o.que} ` : ""}en ${o.ciudad} (${o.departamento}). Ubicación en el mapa y cómo llegar.${wa}`;
}
