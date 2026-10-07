/**
 * El Markdown de los manuales (`content/manuales/*.md`), convertido a una
 * estructura que `components/manual/manual-vista.tsx` dibuja como elementos de
 * React.
 *
 * POR QUÉ UN PARSER PROPIO Y NO UNA LIBRERÍA
 * ==========================================
 * El sitio no suma dependencias por un puñado de títulos y listas, y lo que
 * necesitamos es un subconjunto CHICO y cerrado (docs/manuales.md §1):
 *
 *   #, ##, ###           títulos
 *   párrafos             renglones seguidos = un párrafo
 *   -  y  1.             listas (con una sangría se anidan)
 *   **negrita** *cursiva* `código`
 *   | tablas |
 *   > nota               recuadro destacado
 *   ---                  salto de página al imprimir
 *   {{NOMBRE}} {{CIUDAD}} {{MAIL}}   marcas que se completan al mostrar
 *
 * NADA DE HTML. El resultado son nodos de datos; quien los dibuja crea
 * elementos de React y el texto se escapa solo. No hay `dangerouslySetInnerHTML`
 * en ningún lado de este camino, así que ni un `<script>` pegado en un .md
 * puede ejecutarse: se vería como texto.
 *
 * TOLERANTE. Lo que no se reconoce se muestra como párrafo; un `**` sin cerrar
 * es un `**` literal. Ninguna entrada hace tirar una excepción: si algo
 * inesperado pasara, `parsearManual` devuelve el texto como párrafos.
 */

/** Las marcas que el agente.md deja para completar. */
export type ClaveMarca = "NOMBRE" | "CIUDAD" | "MAIL";
const MARCAS: readonly ClaveMarca[] = ["NOMBRE", "CIUDAD", "MAIL"];

export type Inline =
  | { t: "texto"; v: string }
  | { t: "negrita"; c: Inline[] }
  | { t: "cursiva"; c: Inline[] }
  | { t: "codigo"; c: Inline[] }
  | { t: "marca"; k: ClaveMarca };

export type ItemLista = { c: Inline[]; sub: Bloque[] };

export type Bloque =
  | { t: "h1" | "h2" | "h3"; c: Inline[] }
  | { t: "p"; c: Inline[] }
  | { t: "ul" | "ol"; items: ItemLista[]; inicio: number }
  | { t: "tabla"; cab: Inline[][] | null; filas: Inline[][][]; alin: ("izq" | "centro" | "der" | null)[] }
  | { t: "nota"; c: Bloque[] }
  | { t: "salto" };

// ─────────────────────────────────────────────────────────── en línea ──

/** Junta textos vecinos: `["a", "b"]` → `["ab"]`. Deja el arreglo sin
 *  fragmentos sueltos, que es lo que hace falta para limpiar espacios. */
function fusionar(xs: Inline[]): Inline[] {
  const out: Inline[] = [];
  for (const x of xs) {
    const ult = out[out.length - 1];
    if (x.t === "texto" && ult && ult.t === "texto") ult.v += x.v;
    else if (!(x.t === "texto" && x.v === "")) out.push(x.t === "texto" ? { ...x } : x);
  }
  return out;
}

const PROFUNDIDAD_MAX = 4;

/** Marcas `{{X}}` y texto, sin formato: lo que va adentro de un `código`. */
function soloMarcas(s: string): Inline[] {
  const out: Inline[] = [];
  const re = /\{\{([A-Z_]+)\}\}/g;
  let desde = 0;
  let m: RegExpExecArray | null;
  while ((m = re.exec(s))) {
    const k = m[1] as ClaveMarca;
    if (!MARCAS.includes(k)) continue;   // una llave que no es nuestra queda como texto
    if (m.index > desde) out.push({ t: "texto", v: s.slice(desde, m.index) });
    out.push({ t: "marca", k });
    desde = m.index + m[0].length;
  }
  if (desde < s.length) out.push({ t: "texto", v: s.slice(desde) });
  return fusionar(out);
}

/** Un texto con `**negrita**`, `*cursiva*`, `` `código` `` y `{{MARCAS}}`. */
export function parsearInline(s: string, profundidad = 0): Inline[] {
  if (profundidad > PROFUNDIDAD_MAX) return soloMarcas(s);
  const out: Inline[] = [];
  let buf = "";
  const vaciar = () => { if (buf) { out.push({ t: "texto", v: buf }); buf = ""; } };
  let i = 0;
  while (i < s.length) {
    const c = s[i];
    // Una barra escapa el símbolo que sigue: `\*` es un asterisco, no cursiva.
    if (c === "\\" && i + 1 < s.length && "\\*`{}|_#>-".includes(s[i + 1])) {
      buf += s[i + 1]; i += 2; continue;
    }
    if (c === "`") {
      const fin = s.indexOf("`", i + 1);
      if (fin > i + 1) {
        vaciar();
        out.push({ t: "codigo", c: soloMarcas(s.slice(i + 1, fin)) });
        i = fin + 1; continue;
      }
    }
    if (c === "*" && s[i + 1] === "*") {
      const fin = s.indexOf("**", i + 2);
      if (fin > i + 2) {
        vaciar();
        out.push({ t: "negrita", c: parsearInline(s.slice(i + 2, fin), profundidad + 1) });
        i = fin + 2; continue;
      }
    }
    if (c === "*" && s[i + 1] !== "*" && s[i + 1] !== " " && s[i + 1] !== undefined) {
      // La cursiva cierra en el próximo `*` suelto (no el primero de un `**`).
      let fin = -1;
      for (let j = i + 1; j < s.length; j++) {
        if (s[j] === "\\") { j++; continue; }
        if (s[j] === "*" && s[j + 1] !== "*" && s[j - 1] !== " " && s[j - 1] !== "*") { fin = j; break; }
      }
      if (fin > i + 1) {
        vaciar();
        out.push({ t: "cursiva", c: parsearInline(s.slice(i + 1, fin), profundidad + 1) });
        i = fin + 1; continue;
      }
    }
    if (c === "{" && s[i + 1] === "{") {
      const m = /^\{\{([A-Z_]+)\}\}/.exec(s.slice(i));
      if (m && MARCAS.includes(m[1] as ClaveMarca)) {
        vaciar();
        out.push({ t: "marca", k: m[1] as ClaveMarca });
        i += m[0].length; continue;
      }
    }
    buf += c; i++;
  }
  vaciar();
  return fusionar(out);
}

// ─────────────────────────────────────────────────────────── bloques ──

const RE_TITULO = /^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$/;
const RE_SALTO = /^\s{0,3}(?:-{3,}|\*{3,}|_{3,})\s*$/;
const RE_VINIETA = /^(\s*)[-*+]\s+(.*)$/;
const RE_NUMERO = /^(\s*)(\d{1,3})[.)]\s+(.*)$/;
const RE_NOTA = /^\s{0,3}>\s?(.*)$/;
const RE_TABLA = /^\s*\|/;
const RE_SEPARADOR_TABLA = /^\s*\|?\s*:?-{1,}:?\s*(\|\s*:?-{1,}:?\s*)*\|?\s*$/;

function sangria(s: string): number {
  let n = 0;
  for (const ch of s) { if (ch === " ") n++; else if (ch === "\t") n += 4; else break; }
  return n;
}

/** ¿Esta línea abre un bloque propio (o sea, corta un párrafo)? */
function abreBloque(l: string): boolean {
  if (RE_TITULO.test(l) || RE_SALTO.test(l) || RE_NOTA.test(l) || RE_TABLA.test(l)) return true;
  if (RE_VINIETA.test(l)) return true;
  const n = RE_NUMERO.exec(l);
  return !!n && n[2].length <= 2;
}

/** Las celdas de un renglón de tabla. Respeta `\|` y los `|` adentro de un `código`. */
function celdas(linea: string): string[] {
  let s = linea.trim();
  if (s.startsWith("|")) s = s.slice(1);
  if (s.endsWith("|") && !s.endsWith("\\|")) s = s.slice(0, -1);
  const out: string[] = [];
  let actual = "";
  let enCodigo = false;
  for (let i = 0; i < s.length; i++) {
    const c = s[i];
    if (c === "\\" && s[i + 1] === "|") { actual += "|"; i++; continue; }
    if (c === "`") enCodigo = !enCodigo;
    if (c === "|" && !enCodigo) { out.push(actual.trim()); actual = ""; continue; }
    actual += c;
  }
  out.push(actual.trim());
  return out;
}

function alineacion(celda: string): "izq" | "centro" | "der" | null {
  const c = celda.trim();
  const ini = c.startsWith(":"), fin = c.endsWith(":");
  if (ini && fin) return "centro";
  if (fin) return "der";
  if (ini) return "izq";
  return null;
}

/** Una lista que empieza en `lineas[i]`; devuelve el bloque y la línea donde sigue. */
function parsearLista(lineas: string[], i: number, profundidad: number): [Bloque, number] {
  const primera = lineas[i];
  const num = RE_NUMERO.exec(primera);
  const ordenada = !!num && !RE_VINIETA.test(primera);
  const base = sangria(primera);
  const items: ItemLista[] = [];
  const inicio = ordenada && num ? parseInt(num[2], 10) : 1;
  const esItem = (l: string): { ord: boolean; ind: number; txt: string } | null => {
    const v = RE_VINIETA.exec(l);
    if (v) return { ord: false, ind: sangria(l), txt: v[2] };
    const n = RE_NUMERO.exec(l);
    if (n) return { ord: true, ind: sangria(l), txt: n[3] };
    return null;
  };

  while (i < lineas.length) {
    const it = esItem(lineas[i]);
    if (!it || it.ord !== ordenada || it.ind > base + 1 || it.ind < base - 1) break;
    const textos = [it.txt.trim()];
    i++;
    // La sublista (más sangrada) y las líneas de continuación del ítem.
    const subLineas: string[] = [];
    while (i < lineas.length) {
      const l = lineas[i];
      if (l.trim() === "") {
        // Una línea en blanco sigue adentro del ítem sólo si lo que viene está sangrado.
        const prox = lineas.slice(i + 1).find((x) => x.trim() !== "");
        if (prox !== undefined && sangria(prox) > base + 1 && subLineas.length > 0) { subLineas.push(l); i++; continue; }
        break;
      }
      const otro = esItem(l);
      if (otro && otro.ind <= base + 1) break;            // el ítem siguiente (o el cierre de la lista)
      if (sangria(l) <= base && abreBloque(l)) break;     // un título, una tabla…
      if (otro || sangria(l) > base + 1) { subLineas.push(l); i++; continue; }
      if (subLineas.length === 0) { textos.push(l.trim()); i++; continue; }   // sigue el texto del ítem
      break;
    }
    let sub: Bloque[] = [];
    if (subLineas.some((x) => x.trim() !== "")) {
      if (profundidad < PROFUNDIDAD_MAX) {
        // Se le quita la sangría del ítem y se lee como Markdown común.
        sub = parsearBloques(subLineas.map((x) => x.slice(Math.min(sangria(x), base + 2))), profundidad + 1);
      } else {
        textos.push(subLineas.map((x) => x.trim()).join(" "));
      }
    }
    items.push({ c: parsearInline(textos.join(" ")), sub });
    // Entre ítems puede haber una línea en blanco: la lista sigue si lo próximo es otro ítem.
    let j = i;
    while (j < lineas.length && lineas[j].trim() === "") j++;
    if (j > i && j < lineas.length) {
      const prox = esItem(lineas[j]);
      if (prox && prox.ord === ordenada && prox.ind >= base - 1 && prox.ind <= base + 1) i = j;
    }
  }
  return [{ t: ordenada ? "ol" : "ul", items, inicio }, i];
}

function parsearBloques(lineas: string[], profundidad = 0): Bloque[] {
  const out: Bloque[] = [];
  let i = 0;
  while (i < lineas.length) {
    const l = lineas[i];
    if (l.trim() === "") { i++; continue; }

    if (RE_SALTO.test(l)) { out.push({ t: "salto" }); i++; continue; }

    const t = RE_TITULO.exec(l);
    if (t) {
      const nivel = Math.min(t[1].length, 3);
      out.push({ t: (`h${nivel}` as "h1" | "h2" | "h3"), c: parsearInline(t[2]) });
      i++; continue;
    }

    if (RE_NOTA.test(l)) {
      const interior: string[] = [];
      while (i < lineas.length) {
        const m = RE_NOTA.exec(lineas[i]);
        if (!m) break;
        interior.push(m[1]); i++;
      }
      const hijos = profundidad < PROFUNDIDAD_MAX ? parsearBloques(interior, profundidad + 1) : interior.map((x): Bloque => ({ t: "p", c: parsearInline(x) }));
      if (hijos.length) out.push({ t: "nota", c: hijos });
      continue;
    }

    if (RE_TABLA.test(l)) {
      const filasCrudas: string[][] = [];
      while (i < lineas.length && RE_TABLA.test(lineas[i])) { filasCrudas.push(celdas(lineas[i])); i++; }
      let cab: string[] | null = null;
      let alin: ("izq" | "centro" | "der" | null)[] = [];
      let cuerpo = filasCrudas;
      if (filasCrudas.length >= 2 && RE_SEPARADOR_TABLA.test(filasCrudas[1].join("|"))) {
        cab = filasCrudas[0];
        alin = filasCrudas[1].map(alineacion);
        cuerpo = filasCrudas.slice(2);
      }
      const ancho = Math.max(cab?.length ?? 0, ...cuerpo.map((f) => f.length), 1);
      const rellenar = (f: string[]) => Array.from({ length: ancho }, (_, k) => parsearInline(f[k] ?? ""));
      out.push({
        t: "tabla",
        cab: cab ? rellenar(cab) : null,
        filas: cuerpo.map(rellenar),
        alin: Array.from({ length: ancho }, (_, k) => alin[k] ?? null),
      });
      continue;
    }

    if (RE_VINIETA.test(l) || RE_NUMERO.test(l)) {
      const [b, sig] = parsearLista(lineas, i, profundidad);
      out.push(b);
      i = sig > i ? sig : i + 1;   // nunca quedarse en el mismo renglón
      continue;
    }

    // Párrafo: renglones seguidos hasta una línea en blanco o el inicio de otro bloque.
    const partes = [l.trim()];
    i++;
    while (i < lineas.length && lineas[i].trim() !== "" && !abreBloque(lineas[i])) { partes.push(lineas[i].trim()); i++; }
    out.push({ t: "p", c: parsearInline(partes.join(" ")) });
  }
  return out;
}

/** El Markdown de un manual, como bloques. Nunca lanza: ante cualquier cosa
 *  inesperada devuelve el texto como párrafos. */
export function parsearManual(md: string): Bloque[] {
  const texto = md.replace(/^﻿/, "").replace(/\r\n?/g, "\n");
  try {
    return parsearBloques(texto.split("\n"));
  } catch {
    return texto.split(/\n{2,}/).filter((p) => p.trim()).map((p): Bloque => ({ t: "p", c: [{ t: "texto", v: p.trim() }] }));
  }
}

// ──────────────────────────────────────────── marcas y portada ──

export type ValoresMarca = Record<ClaveMarca, string>;

/** Lo que se muestra cuando no vino el dato (`/manual/agente` a secas). */
export const MARCAS_POR_DEFECTO: ValoresMarca = { NOMBRE: "", CIUDAD: "tu ciudad", MAIL: "tu correo" };

/** Reemplaza las marcas por sus valores. Si una marca queda vacía (el nombre,
 *  cuando no se pasó) se la quita sin dejar «Hola , …»: se sacan los dobles
 *  espacios y el espacio que quedó antes de una coma o un punto. */
export function aplicarMarcas(xs: Inline[], v: ValoresMarca): Inline[] {
  let hayVacia = false;
  const plano = (nodos: Inline[]): Inline[] => nodos.map((n): Inline => {
    if (n.t === "marca") { if (!v[n.k]) hayVacia = true; return { t: "texto", v: v[n.k] }; }
    if (n.t === "texto") return n;
    return { ...n, c: plano(n.c) };
  });
  const lleno = fusionar(plano(xs));
  if (!hayVacia) return lleno;
  return lleno.map((n): Inline => (n.t === "texto"
    ? { t: "texto", v: n.v.replace(/ {2,}/g, " ").replace(/ +([,.;:!?])/g, "$1") }
    : n));
}

/** ¿El bloque nombra la marca dada? (para esconder, en la portada, «Para {{NOMBRE}}» cuando no hay nombre). */
export function usaMarca(xs: Inline[], k: ClaveMarca): boolean {
  return xs.some((n) => (n.t === "marca" ? n.k === k : n.t === "texto" ? false : usaMarca(n.c, k)));
}

/** El texto plano de un fragmento, para el título de la pestaña. */
export function textoPlano(xs: Inline[]): string {
  return xs.map((n) => (n.t === "texto" ? n.v : n.t === "marca" ? "" : textoPlano(n.c))).join("");
}

/** La portada: el primer `#` y lo que le sigue pegado (párrafos y notas) hasta
 *  el primer título, lista, tabla o salto. El resto es el cuerpo. Si el manual
 *  no empieza con un `#`, no hay portada y todo es cuerpo. */
export function separarPortada(bloques: Bloque[]): { portada: Bloque[]; cuerpo: Bloque[] } {
  const h1 = bloques.findIndex((b) => b.t === "h1");
  if (h1 === -1 || bloques.slice(0, h1).some((b) => b.t !== "salto")) return { portada: [], cuerpo: bloques };
  let fin = h1 + 1;
  while (fin < bloques.length && (bloques[fin].t === "p" || bloques[fin].t === "nota")) fin++;
  let sigue = fin;
  while (sigue < bloques.length && bloques[sigue].t === "salto") sigue++;   // el `---` que cierra la portada ya está implícito
  return { portada: bloques.slice(h1, fin), cuerpo: bloques.slice(sigue) };
}
