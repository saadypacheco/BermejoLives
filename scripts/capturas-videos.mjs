// Captura las pantallas principales de URUKU + Reservalo para los videos promo.
// Genera PNG en mobile (390x844, iPhone) y desktop (1440x900), nombrados por
// escena para que matcheen 1:1 con el storyboard de docs/videos-promo.md.
//
// Uso:
//   npm i -D playwright && npx playwright install chromium
//   BASE=https://uruku.bo SLUG=<slug-de-una-ficha> node scripts/capturas-videos.mjs
//   (QA:  BASE=https://encontralo.store ...)
//
// SLUG: el slug de un comercio real para la toma de "ficha". Si no lo pasás,
// intenta tomar el primero del buscador. Las pantallas con login (mi-comercio,
// admin de la tienda) NO se capturan solas — grabalas a mano logueado.

import { chromium, devices } from "playwright";
import { mkdir } from "node:fs/promises";

const BASE = (process.env.BASE || "https://uruku.bo").replace(/\/$/, "");
const SLUG = process.env.SLUG || "";
const OUT = "capturas";

// Escenas públicas: [id, ruta, esperaExtraMs]. El id define el nombre del PNG.
const escenas = [
  ["01-home", "/", 1500],
  ["02-mapa", "/mapa", 2500],           // el mapa tarda en pintar los pines
  ["03-buscar", "/buscar", 2000],
  ["04-ficha", `/comercios/${SLUG}`, 1800],   // requiere SLUG
  ["05-tienda", "/tienda", 1800],
  ["06-tienda-productos", "/tienda/productos", 1800],
];

const viewports = {
  mobile: devices["iPhone 13"],
  desktop: { viewport: { width: 1440, height: 900 } },
};

async function main() {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch();

  // Si no hay SLUG, intento sacar uno del buscador para la toma de ficha.
  let slug = SLUG;
  if (!slug) {
    const ctx = await browser.newContext();
    const page = await ctx.newPage();
    try {
      await page.goto(`${BASE}/buscar`, { waitUntil: "networkidle", timeout: 30000 });
      const href = await page.getAttribute('a[href^="/comercios/"]', "href").catch(() => null);
      if (href) slug = href.split("/comercios/")[1];
    } catch {}
    await ctx.close();
    if (slug) console.log(`SLUG detectado para la ficha: ${slug}`);
    else console.log("⚠ No pude detectar un SLUG — la toma 04-ficha se saltea.");
  }

  for (const [modo, cfg] of Object.entries(viewports)) {
    const ctx = await browser.newContext({ ...cfg, colorScheme: "light" });
    const page = await ctx.newPage();
    for (const [id, ruta, espera] of escenas) {
      const path = ruta.includes("/comercios/") ? (slug ? `/comercios/${slug}` : null) : ruta;
      if (!path) continue;
      const url = `${BASE}${path}`;
      try {
        await page.goto(url, { waitUntil: "networkidle", timeout: 40000 });
        await page.waitForTimeout(espera);
        const file = `${OUT}/${id}-${modo}.png`;
        await page.screenshot({ path: file });
        console.log(`✓ ${file}`);
      } catch (e) {
        console.log(`✗ ${id}-${modo} (${url}): ${e.message}`);
      }
    }
    await ctx.close();
  }

  await browser.close();
  console.log(`\nListo. PNG en ./${OUT}/  (mobile + desktop por escena)`);
}

main().catch((e) => { console.error(e); process.exit(1); });
