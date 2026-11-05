// Una página legal (/terminos, /privacidad) del lado del servidor: lee el
// Markdown de `content/legal/<archivo>`, le saca lo que no se publica
// (lib/legal-pure.ts) y lo dibuja con el mismo armado que «Qué es URUKU»
// (parser y vista de los manuales: sin HTML crudo, el texto se escapa solo).
//
// El .md se lee durante `next build` (las rutas son estáticas) y queda adentro
// del HTML generado: en producción no se abre ningún archivo.

import { readFile } from "node:fs/promises";
import path from "node:path";
import "@/app/styles/manual.css";
import { ManualVista } from "@/components/manual/manual-vista";
import { LEGAL, prepararLegal, type TipoLegal } from "@/lib/legal-pure";
import { MARCAS_POR_DEFECTO, parsearManual } from "@/lib/manual-md";

export async function PaginaLegal({ tipo }: { tipo: TipoLegal }) {
  const { archivo, titulo } = LEGAL[tipo];
  let md: string;
  try {
    md = await readFile(path.join(process.cwd(), "content", "legal", archivo), "utf8");
  } catch {
    // Sin el archivo no hay documento que mostrar: que el build lo diga en vez
    // de publicar una página vacía.
    throw new Error(`Falta content/legal/${archivo}`);
  }
  const bloques = parsearManual(prepararLegal(md));
  return (
    <div className="mn-root" data-tipo="legal">
      <ManualVista bloques={bloques} v={MARCAS_POR_DEFECTO} etiqueta={titulo} />
    </div>
  );
}
