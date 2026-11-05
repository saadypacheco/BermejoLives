// Las páginas legales (/terminos y /privacidad) salen de los Markdown de
// `content/legal/` (copia EXACTA de `docs/legal/`: la carpeta docs/ no entra en
// el contexto de build del frontend). Esos .md son el documento de trabajo del
// abogado y traen cosas que no se publican; `prepararLegal` las saca y deja el
// texto del dueño tal cual:
//
//   - el bloque de borrador del principio (el aviso «Borrador para revisión…» y
//     la lista de «Pendientes [completar]»), que llega hasta el primer `---`;
//   - los comentarios HTML (`<!-- inv: … -->`, que ni el .md muestra);
//   - la sección final «Notas para el abogado» / «Fuentes legales», que dice
//     «sacar al publicar»;
//   - las notas internas entre corchetes: `[Nota interna: …]` y `[Revisar H-…]`.
//
// NO toca nada más: los `[completar: …]` del cuerpo se quedan (son datos que sólo
// el dueño puede dar; `pendientesLegal` los lista para que no se pasen por alto).

/** Si las páginas legales ya se publican: link en el pie, sitemap e indexables.
 *  En `false` mientras el texto tenga `[completar: …]` (razón social, NIT,
 *  domicilio…): las páginas existen para revisarlas, pero con `noindex` y sin
 *  links. En `true` desde el 5/11/2026, con los datos que completó el dueño. */
export const LEGAL_PUBLICADO = true;

export type TipoLegal = "terminos" | "privacidad";

export const TIPOS_LEGAL: readonly TipoLegal[] = ["terminos", "privacidad"];

export const LEGAL: Record<TipoLegal, { archivo: string; titulo: string; ruta: string; descripcion: string }> = {
  terminos: {
    archivo: "terminos.md",
    titulo: "Términos y condiciones de uso",
    ruta: "/terminos",
    descripcion: "Las reglas para usar URUKU: qué es, cómo se publica, planes, contenidos, moderación y responsabilidades.",
  },
  privacidad: {
    archivo: "politica-privacidad.md",
    titulo: "Política de privacidad",
    ruta: "/privacidad",
    descripcion: "Qué datos guarda URUKU, para qué los usa, con quién los comparte, cuánto los conserva y cómo pedir verlos o borrarlos.",
  },
};

export function prepararLegal(md: string): string {
  let t = md.split("\r\n").join("\n");
  t = t.replace(/<!--[\s\S]*?-->/g, "");

  // Fuera la sección final de notas para el abogado, y el `---` que la separa.
  const notas = t.search(/^## (?:Notas para el abogado|Fuentes legales)\b/m);
  if (notas !== -1) t = t.slice(0, notas).replace(/\n---\s*$/, "");

  // Fuera el bloque de borrador: entre el título y el primer `---` suelto.
  const h1 = t.search(/^# /m);
  if (h1 !== -1) {
    const finTitulo = t.indexOf("\n", h1);
    const corte = t.slice(finTitulo).search(/^---\s*$/m);
    if (finTitulo !== -1 && corte !== -1) {
      const pasaBorrador = t.slice(finTitulo, finTitulo + corte);
      if (/Borrador|Pendientes/.test(pasaBorrador)) {
        const finCorte = t.indexOf("\n", finTitulo + corte + 1);
        t = t.slice(0, finTitulo) + "\n" + (finCorte === -1 ? "" : t.slice(finCorte));
      }
    }
  }

  // Notas internas entre corchetes.
  t = t
    .split("\n")
    .filter((l) => !/^\s*\[Nota interna:[^\]]*\]\s*$/.test(l))
    .join("\n")
    .replace(/[ \t]*\[(?:Revisar|Nota interna)[^\]]*\]/g, "");

  return t.replace(/\n{3,}/g, "\n\n").trim() + "\n";
}

/** Los `[completar: …]` que quedan en el texto ya preparado: lo que falta
 *  que el dueño complete antes de que el documento sea definitivo. */
export function pendientesLegal(textoPreparado: string): string[] {
  return [...textoPreparado.matchAll(/\[completar[^\]]*\]/gi)].map((m) => m[0]);
}
