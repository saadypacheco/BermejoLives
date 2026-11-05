// Páginas legales (/terminos, /privacidad): lo que se saca del borrador antes
// de publicar, que el texto del dueño quede tal cual, y que la copia de
// content/legal/ no se desvíe de docs/legal/.
import test from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { resolve } from "node:path";
import { LEGAL, TIPOS_LEGAL, pendientesLegal, prepararLegal } from "../lib/legal-pure";

const RAIZ = process.cwd();   // `npm test` corre en frontend/
const leer = (archivo: string) => readFileSync(resolve(RAIZ, "content", "legal", archivo), "utf8");

const BORRADOR = [
  "# Título del documento",
  "",
  "> **Borrador para revisión de un abogado.**",
  "",
  "**Pendientes [completar] antes de publicar:**",
  "1. Algo.",
  "",
  "---",
  "",
  "## 1. Primera",
  "",
  "Texto <!-- inv: A1 --> del cuerpo. [Revisar H-01: borrar antes] Sigue.",
  "",
  "[Nota interna: no publicar esto.]",
  "",
  "Dato **[completar: titular]** pendiente.",
  "",
  "---",
  "",
  "## Notas para el abogado (sacar al publicar)",
  "- Ley 453: [Lexivox](https://example.test).",
].join("\r\n");

test("prepararLegal saca el borrador, los comentarios, las notas internas y la sección del abogado", () => {
  const t = prepararLegal(BORRADOR);
  assert.match(t, /^# Título del documento\n/);
  assert.match(t, /## 1\. Primera/);
  assert.doesNotMatch(t, /Borrador|Pendientes|<!--|Nota interna|Revisar|abogado|Lexivox|\r/);
  assert.match(t, /Texto {1,2}del cuerpo\. {1,2}Sigue\./);
});

test("prepararLegal deja los [completar] del cuerpo y pendientesLegal los lista", () => {
  const t = prepararLegal(BORRADOR);
  assert.deepEqual(pendientesLegal(t), ["[completar: titular]"]);
});

test("prepararLegal no toca un texto sin borrador", () => {
  const limpio = "# Hola\n\n## 1. Uno\n\nTexto.\n";
  assert.equal(prepararLegal(limpio), limpio);
});

for (const tipo of TIPOS_LEGAL) {
  test(`${tipo}: el documento real se prepara sin restos de borrador`, () => {
    const t = prepararLegal(leer(LEGAL[tipo].archivo));
    assert.match(t, /^# /);
    assert.doesNotMatch(t, /Borrador para revisión|Pendientes \[completar\]|<!--|\[Nota interna|\[Revisar|Notas para el abogado|Fuentes legales/);
    assert.match(t, /^## 1\. /m);
  });

  test(`${tipo}: content/legal es copia exacta de docs/legal (si docs/ está a mano)`, () => {
    const origen = resolve(RAIZ, "..", "docs", "legal", LEGAL[tipo].archivo);
    if (!existsSync(origen)) return;   // p. ej. dentro de la imagen de Docker
    const norm = (s: string) => s.split("\r\n").join("\n");
    assert.equal(norm(leer(LEGAL[tipo].archivo)), norm(readFileSync(origen, "utf8")),
      `copiá docs/legal/${LEGAL[tipo].archivo} a frontend/content/legal/`);
  });
}

test("los términos prohíben la extracción masiva o automatizada y su reuso comercial sin permiso escrito", () => {
  const t = prepararLegal(leer(LEGAL.terminos.archivo));
  assert.match(t, /Extracción masiva o automatizada/);
  assert.match(t, /permiso escrito/);
});

test("los archivos legales nuevos no llevan emojis (AGENTS.md §6)", () => {
  const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{FE0F}]/u;
  for (const f of ["lib/legal-pure.ts", "components/legal/pagina-legal.tsx", "app/terminos/page.tsx", "app/privacidad/page.tsx"]) {
    assert.ok(!EMOJI.test(readFileSync(resolve(RAIZ, f), "utf8")), `${f} tiene un emoji`);
  }
});
