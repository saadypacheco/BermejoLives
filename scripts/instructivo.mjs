/**
 * Arma el PDF del instructivo de un agente de campo.
 *
 *   node scripts/instructivo.mjs --nombre Carlos --ciudad "La Paz" \
 *        --mail carlos@uruku.bo --genero m
 *
 * Sale en `docs/URUKU-Instructivo-<Nombre>.pdf`.
 *
 * SE CORRE EN LA MÁQUINA DE DESARROLLO, no en el VPS. El servidor sirve el
 * sitio y nada más: no tiene node, ni el navegador que imprime el PDF, ni
 * falta que los tenga. El PDF se arma acá y se manda por WhatsApp.
 *
 * POR QUÉ EXISTE
 * ==============
 * El instructivo es el mismo para todos: lo que cambia son la ciudad, el
 * correo y una concordancia («parado» / «parada»). Antes se copiaba el HTML
 * por persona, y cada corrección dejaba un archivo nuevo al lado del anterior:
 * se llegó a cuatro instructivos distintos en docs/ y ninguna forma de saber
 * cuál mandar. Con una sola plantilla, una corrección entra para los ocho
 * agentes.
 *
 * Playwright no es dependencia de este repo —el sitio no lo usa— así que se
 * toma del repo vecino que ya lo tiene instalado. Si se mueve, la ruta se
 * cambia acá y en ningún otro lado.
 */
import { readFileSync, writeFileSync, existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const FUENTE = resolve(RAIZ, "docs/instructivo-agente-fuente");

// Playwright vive en el repo de al lado. Se busca por ahí y no se instala nada
// en este: un repo de producción no necesita un navegador headless.
const VECINOS = ["../MentorComercial", "../apops"];

function arg(nombre, obligatorio = true) {
  const i = process.argv.indexOf(`--${nombre}`);
  const v = i > 0 ? process.argv[i + 1] : undefined;
  if (!v && obligatorio) {
    console.error(`Falta --${nombre}.\n\n` +
      `  node scripts/instructivo.mjs --nombre Carlos --ciudad "La Paz" --mail carlos@uruku.bo --genero m\n`);
    process.exit(1);
  }
  return v;
}

const nombre = arg("nombre");
const ciudad = arg("ciudad");
const mail = arg("mail");
const genero = (arg("genero", false) ?? "f").toLowerCase();

if (!/^[^@\s]+@uruku\.bo$/.test(mail)) {
  // Las cuentas del equipo son todas @uruku.bo. Un correo mal escrito en el
  // instructivo se descubre cuando la persona ya está en la calle y no puede
  // entrar, así que acá corta.
  console.error(`El correo «${mail}» no es una cuenta @uruku.bo. Revisá cómo está escrito.`);
  process.exit(1);
}
if (!["m", "f"].includes(genero)) {
  console.error('--genero tiene que ser "m" o "f" (define «parado» o «parada»).');
  process.exit(1);
}

const plantilla = readFileSync(resolve(FUENTE, "plantilla.html"), "utf8");
const valores = {
  CIUDAD: ciudad,
  CIUDAD_MAYUS: ciudad.toLocaleUpperCase("es"),
  MAIL: mail,
  PARADO: genero === "m" ? "parado" : "parada",
};

let html = plantilla;
for (const [clave, valor] of Object.entries(valores)) {
  html = html.replaceAll(`{{${clave}}}`, valor);
}
// LOGIN_PNG se llena más abajo, cuando ya está la captura.
const sinLlenar = [...html.matchAll(/\{\{([A-Z_]+)\}\}/g)].map((m) => m[1]).filter((x) => x !== "LOGIN_PNG");
if (sinLlenar.length) {
  console.error(`La plantilla tiene marcas que este script no conoce: ${[...new Set(sinLlenar)].join(", ")}`);
  process.exit(1);
}

// El HTML armado se deja al lado de las capturas, que se referencian relativas.
const htmlPath = resolve(FUENTE, `doc-${nombre.toLowerCase()}.html`);

const base = VECINOS.map((v) => resolve(RAIZ, v)).find((d) => existsSync(resolve(d, "node_modules/playwright")));
if (!base) {
  console.error(`No encontré Playwright en ${VECINOS.join(" ni ")}.\n` +
    `El HTML quedó armado en ${htmlPath}: se puede imprimir a PDF desde el navegador.`);
  process.exit(1);
}
const { chromium } = createRequire(resolve(base, "package.json"))("playwright");

const pdfPath = resolve(RAIZ, `docs/URUKU-Instructivo-${nombre}.pdf`);
const navegador = await chromium.launch();
try {
  // LA CAPTURA DEL LOGIN SE SACA CON EL CORREO DE ESTE AGENTE.
  // Antes era un PNG fijo, y el de Carlos mostraba a Claudia escrita en el
  // campo al lado de un texto que decía otra cosa: lo primero que ve alguien
  // en su primer día, contradiciéndose consigo mismo. Se saca del sitio de
  // verdad, así que además no envejece cuando la pantalla cambia.
  const loginPng = `1-login-${nombre.toLowerCase()}.png`;
  // Al ancho de un celular de verdad, que es donde el agente va a ver esto. A
  // 420 px el título desborda la tarjeta y la captura sale cortada al medio de
  // una palabra.
  const cap = await navegador.newPage({ viewport: { width: 390, height: 760 }, deviceScaleFactor: 2 });
  try {
    await cap.goto("https://uruku.bo/publicar", { waitUntil: "networkidle", timeout: 30000 });
    await cap.fill('input[type="email"]', mail);
    await cap.fill('input[type="password"]', "........");
    await cap.screenshot({ path: resolve(FUENTE, loginPng) });
    html = html.replaceAll("{{LOGIN_PNG}}", loginPng);
    console.log(`captura del login: ${loginPng}`);
  } catch (e) {
    // Sin internet o con el sitio caído, el instructivo sale igual con la
    // captura genérica: vale más un PDF con una pantalla de ejemplo que
    // ninguno.
    html = html.replaceAll("{{LOGIN_PNG}}", "1-login.png");
    console.warn(`No pude sacar la captura del login: ${e.message}. Va la genérica.`);
  } finally {
    await cap.close();
  }
  writeFileSync(htmlPath, html);

  const pagina = await navegador.newPage();
  await pagina.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle" });
  // Poppins viene de Google Fonts: sin esperarla, el PDF sale en Arial y el
  // instructivo deja de verse de URUKU.
  await pagina.evaluate(() => document.fonts.ready);
  // Que ninguna hoja se pase de A4. Es la comprobación que faltó la primera
  // vez: una hoja 2 mm más larga que la página manda su pie solo a una hoja
  // siguiente, y el instructivo sale con una página en blanco al final. No se
  // ve hasta que alguien abre el PDF.
  // La medida se toma con la ventana del TAMAÑO DE LA HOJA (A4 a 96 dpi) y en
  // modo impresión: con la ventana por defecto, más ancha, el texto ocupa
  // menos renglones y todo parece entrar.
  await pagina.emulateMedia({ media: "print" });
  await pagina.setViewportSize({ width: 794, height: 1123 });
  const hojas = await pagina.evaluate(() => {
    const porMm = 1123 / 297;
    return [...document.querySelectorAll(".pag")].map((e, i) => ({
      n: i + 1,
      mm: +(e.getBoundingClientRect().height / porMm).toFixed(1),
      titulo: e.querySelector("h1")?.textContent.trim().slice(0, 40) ?? "",
    }));
  });
  const pasadas = hojas.filter((h) => h.mm > 297);
  if (pasadas.length) {
    console.error("Hay hojas más largas que A4 (297 mm). Cada una va a dejar una página en blanco:");
    for (const h of pasadas) console.error(`  hoja ${h.n} (${h.titulo}): ${h.mm} mm`);
    console.error("Sacá un par de renglones de esa hoja en plantilla.html y volvé a correrlo.");
    process.exit(1);
  }

  await pagina.pdf({
    path: pdfPath, format: "A4", printBackground: true,
    margin: { top: 0, right: 0, bottom: 0, left: 0 },
  });
  console.log(hojas.map((h) => `hoja ${h.n}: ${h.mm} mm`).join(" · "));
} finally {
  await navegador.close();
}

console.log(`${pdfPath}\n  ${ciudad} · ${mail} · «${valores.PARADO}»`);
