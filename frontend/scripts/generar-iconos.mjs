/**
 * Genera `lib/iconos-dibujos.ts`: el dibujo de cada ícono del catálogo, como
 * texto, en los dos pesos que el sitio usa (duotono y relleno).
 *
 * POR QUÉ EXISTE ESTE PASO
 * ========================
 * `@phosphor-icons/react` publica cada ícono con sus SEIS pesos en un solo
 * módulo, y no hay forma de pedirle uno. Importar los 160 del catálogo le
 * agregaba 106 kB COMPRIMIDOS a todas las páginas del sitio —el build los
 * metía en el layout, así que los pagaba hasta quien entra a leer una ficha—
 * para usar dos de cada seis dibujos. Medido, no estimado.
 *
 * Así que el paquete se usa acá, una vez, en la máquina de desarrollo: se
 * dibuja cada ícono y se guarda el resultado como texto. Al navegador le
 * llegan los dibujos y nada más. Phosphor queda como dependencia de
 * DESARROLLO.
 *
 * Y de paso el mismo texto sirve para los pines del mapa, que Leaflet arma con
 * HTML y no con React (ver `lib/iconos-mapa.ts`).
 *
 * UNA SOLA FUENTE DE VERDAD
 * =========================
 * Las parejas «clave → ícono de Phosphor» NO se repiten acá: se leen de
 * `components/ic.tsx`, que es donde se eligen y donde se las lee.
 *
 * Correr después de tocar el catálogo:  node scripts/generar-iconos.mjs
 */
import { readFileSync, writeFileSync } from "node:fs";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import * as Phosphor from "@phosphor-icons/react/dist/ssr";

const SALTO = "\n";

const ic = readFileSync("components/ic.tsx", "utf8");
const bloque = ic.split("export const ICONOS = {")[1]?.split("} as const;")[0];
if (!bloque) throw new Error("no encontré el bloque ICONOS en components/ic.tsx");

// `"repuestos-autos": "CarProfile"` y `ropa: "TShirt"` — las dos formas.
const pares = [];
for (const m of bloque.matchAll(/(?:"([a-z0-9_-]+)"|\b([a-z0-9_]+))\s*:\s*"([A-Z][A-Za-z0-9]*)"/g)) {
  pares.push([m[1] ?? m[2], m[3]]);
}
if (!pares.length) throw new Error("el bloque ICONOS no tiene pares clave/ícono");

/** Phosphor devuelve el <svg> entero; acá sólo interesa lo de adentro, porque
 *  el <svg> lo pone el componente con su tamaño y su color. */
const dentro = (html) => html.replace(/^<svg[^>]*>/, "").replace(/<\/svg>$/, "");

// QUIÉN NECESITA EL PESO RELLENO
// ==============================
// Duotono lo necesitan todos (es el peso del manual). Relleno sólo lo que se
// dibuja CHICO: los pines del mapa —o sea cualquier rubro— y un puñado de
// marcas de 12 px. Generar relleno para los 160 era mandarle al navegador
// 20 kB de dibujos que nadie pide. Las claves que no están acá y se piden en
// relleno caen en duotono, que a tamaño grande es lo correcto igual.
const visual = readFileSync("lib/mapa-visual.ts", "utf8");
const tablaRubros = visual.split("CATEGORY_STYLE: Record<string, { color: string }> = {")[1]
  ?.split("\n};")[0];
if (!tablaRubros) throw new Error("no encontré CATEGORY_STYLE en lib/mapa-visual.ts");
const conRelleno = new Set([
  "otros", "comercios", "ubicacion", "estrella",
  // Los de components/icons.tsx que van rellenos por tamaño o porque son
  // logos (un logo de marca en duotono no se reconoce).
  "whatsapp", "verificado", "video_play", "guardado",
  "instagram", "facebook", "tiktok", "youtube",
]);
for (const m of tablaRubros.matchAll(/(?:"([a-z0-9-]+)"|\b([a-z0-9_]+))\s*:\s*\{\s*color:/g)) {
  conRelleno.add(m[1] ?? m[2]);
}

const duoDistintos = [];
const relDistintos = [];
const iDuo = new Map();
const iRel = new Map();
const porClave = [];
const porClaveRelleno = [];
const faltan = [];

for (const [clave, nombre] of pares) {
  const Cmp = Phosphor[nombre];
  if (!Cmp) { faltan.push(`${clave} (${nombre} no existe en Phosphor)`); continue; }
  // Varias claves comparten dibujo (ropa y ropa-americana son la misma
  // remera): se guarda una vez y las claves apuntan por número.
  const duo = dentro(renderToStaticMarkup(createElement(Cmp, { weight: "duotone" })));
  if (!iDuo.has(duo)) { iDuo.set(duo, duoDistintos.length); duoDistintos.push(duo); }
  porClave.push([clave, iDuo.get(duo)]);
  if (conRelleno.has(clave)) {
    const rel = dentro(renderToStaticMarkup(createElement(Cmp, { weight: "fill" })));
    if (!iRel.has(rel)) { iRel.set(rel, relDistintos.length); relDistintos.push(rel); }
    porClaveRelleno.push([clave, iRel.get(rel)]);
  }
}

if (!porClave.some(([c]) => c === "otros")) throw new Error("falta la clave «otros», que es el respaldo");
const sinIcono = [...conRelleno].filter((c) => !porClave.some(([k]) => k === c));
if (sinIcono.length) faltan.push(`rubros sin ícono en el catálogo: ${sinIcono.join(", ")}`);

const lista = (xs) => xs.map((x) => `  ${JSON.stringify(x)},`).join(SALTO);
const tabla = (xs) => xs.map(([c, i]) =>
  `  ${/^[a-z0-9_]+$/.test(c) ? c : JSON.stringify(c)}: ${i},`).join(SALTO);

writeFileSync("lib/iconos-dibujos.ts", `// GENERADO por scripts/generar-iconos.mjs — no editar a mano.
// Las parejas clave→ícono viven en components/ic.tsx; qué rubros existen, en
// lib/mapa-visual.ts. Si cambia alguno de los dos hay que volver a correr el
// script, o la clave nueva se dibuja como un paquete.
//
// Es Phosphor pasado a texto en tiempo de desarrollo: así el navegador no
// descarga el paquete entero (ver el comentario largo del generador).

/** Duotono: el peso del manual. Para todo lo que se ve de 16 px para arriba. */
export const DUOTONO: readonly string[] = [
${lista(duoDistintos)}
];

/** Relleno: sólo para lo que se dibuja chico —los pines del mapa y un par de
 *  marcas de 12 px—. Lo que no está acá, en relleno cae en duotono. */
export const RELLENO: readonly string[] = [
${lista(relDistintos)}
];

/** Qué dibujo duotono le toca a cada clave del catálogo. */
export const POR_CLAVE: Record<string, number> = {
${tabla(porClave)}
};

/** Qué dibujo relleno le toca, para las claves que lo tienen. */
export const POR_CLAVE_RELLENO: Record<string, number> = {
${tabla(porClaveRelleno)}
};
`);

const kb = (xs) => (xs.reduce((a, x) => a + x.length, 0) / 1024).toFixed(1);
console.log(`lib/iconos-dibujos.ts: ${porClave.length} claves · duotono ${duoDistintos.length} dibujos ` +
            `(${kb(duoDistintos)} kB) · relleno ${relDistintos.length} (${kb(relDistintos)} kB)`);
if (faltan.length) { console.error("SIN DIBUJO:", faltan.join(", ")); process.exitCode = 1; }
