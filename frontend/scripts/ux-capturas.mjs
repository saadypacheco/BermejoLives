// Captura las pantallas clave de uruku.bo como las ve una persona: celular y
// escritorio. Para el análisis de UX se mira lo que se ve, no el código.
import { chromium, devices } from "playwright";
import { mkdir } from "node:fs/promises";

const BASE = "https://uruku.bo";
const OUT = "C:/Users/User/AppData/Local/Temp/claude/c--repos-proyectosClaude-Bermejo/efbfd232-097a-44c7-8862-9bc633a76e66/scratchpad/ux";
await mkdir(OUT, { recursive: true });

const rutas = [
  ["home", "/"],
  ["buscar-vacio", "/buscar?ciudad=bermejo"],
  ["buscar-q", "/buscar?q=zapatillas&ciudad=bermejo"],
  ["buscar-mapa", "/buscar?q=zapatillas&ciudad=bermejo&vista=mapa"],
  ["software", "/software"],
];

const browser = await chromium.launch();

// Celular: pantalla completa (scroll entero) y también el primer pantallazo.
const tel = await browser.newContext({ ...devices["Pixel 7"] });
const p = await tel.newPage();
let slug = "";
for (const [id, ruta] of rutas) {
  await p.goto(BASE + ruta, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(ruta.includes("mapa") ? 4000 : 2200);
  await p.screenshot({ path: `${OUT}/m-${id}-fold.png` });
  await p.screenshot({ path: `${OUT}/m-${id}-full.png`, fullPage: true });
  if (id === "buscar-q" && !slug) {
    const hrefs = await p.locator('a[href^="/comercios/"]').evaluateAll(
      (as) => as.map((a) => a.getAttribute("href")));
    slug = (hrefs[0] || "").replace("/comercios/", "").split("#")[0];
  }
  console.log("m", id);
}
if (slug) {
  await p.goto(`${BASE}/comercios/${slug}`, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(2200);
  await p.screenshot({ path: `${OUT}/m-comercio-fold.png` });
  await p.screenshot({ path: `${OUT}/m-comercio-full.png`, fullPage: true });
  console.log("m comercio", slug);
}
await tel.close();

// Escritorio: sólo el primer pantallazo del home y la búsqueda.
const esc = await browser.newContext({ viewport: { width: 1366, height: 768 } });
const d = await esc.newPage();
for (const [id, ruta] of [["home", "/"], ["buscar-q", "/buscar?q=zapatillas&ciudad=bermejo"]]) {
  await d.goto(BASE + ruta, { waitUntil: "domcontentloaded" });
  await d.waitForTimeout(2200);
  await d.screenshot({ path: `${OUT}/d-${id}.png` });
  console.log("d", id);
}
await browser.close();
console.log("slug usado:", slug);
