// Las capturas del video de 1 minuto (vertical, para reel/estado/TikTok).
//
//   npx next start -p 3011   (con los datos de producción)
//   node scripts/video-capturas.mjs ../video-1min
//
// Cada toma se guarda numerada en el orden del guion (docs/video-1min/guion.md).
// Vertical 1170×2532 (iPhone 13 ×3): entra tal cual en un reel de 1080×1920
// escalando, y se ve nítido en pantalla grande.
import { chromium, devices } from "playwright";
import fs from "node:fs";

const BASE = "http://127.0.0.1:3011";
const OUT = process.argv[2] || "../video-1min";
fs.mkdirSync(OUT, { recursive: true });

const b = await chromium.launch();
const { defaultBrowserType, ...iphone } = devices["iPhone 13"];
const movil = { ...iphone, deviceScaleFactor: 3, serviceWorkers: "block" };

/** Una toma: abre, espera, recorta lo que estorba y guarda. */
async function toma(n, nombre, ruta, opciones = {}) {
  const { scroll = 0, espera = 2500, elemento = null, click = null, ciudad = "bermejo", alto = null } = opciones;
  const ctx = await b.newContext(alto ? { ...movil, viewport: { width: 390, height: alto } } : movil);
  await ctx.addCookies([{ name: "ciudad", value: ciudad, domain: "127.0.0.1", path: "/" }]);
  const p = await ctx.newPage();
  await p.goto(BASE + ruta, { waitUntil: "networkidle" });
  // Fuera el cartel de "Instalá URUKU" y el botón de Ayuda: tapan la toma.
  await p.addStyleTag({ content: ".install-banner, .uk-ayuda-btn, .uk-contesto { display: none !important; }" });
  if (click) { await p.locator(click).first().click().catch(() => {}); }
  await p.waitForTimeout(espera);
  if (scroll) { await p.evaluate((y) => window.scrollTo({ top: y, behavior: "instant" }), scroll); await p.waitForTimeout(700); }
  const archivo = `${OUT}/${String(n).padStart(2, "0")}-${nombre}.png`;
  if (elemento) await p.locator(elemento).first().screenshot({ path: archivo }).catch(() => p.screenshot({ path: archivo }));
  else await p.screenshot({ path: archivo });
  console.log("✓", archivo);
  await ctx.close();
}

// ── 1. El mapa de la ciudad: mil locales, uno al lado del otro
await toma(1, "mapa-ciudad", "/buscar?rubro=ropa&vista=mapa", { espera: 7000 });
// ── 2. Alguien busca lo que vos vendés
await toma(2, "busqueda-zapatillas", "/buscar?q=zapatillas", { espera: 4000 });
// ── 3. …y te encuentra, con tus fotos
await toma(3, "ficha-arriba", "/comercios/rustico", { espera: 3500 });
// ── 4. Tu horario, tu WhatsApp, cómo llegar
await toma(4, "ficha-datos", "/comercios/rustico", { espera: 3000, scroll: 700 });
// ── 5. Tu QR, para la vidriera
await toma(5, "ficha-qr", "/comercios/rustico", { espera: 3000, scroll: 1250 });
// ── 6. Las ofertas del día de toda la ciudad
await toma(6, "ofertas", "/buscar?of=1", { espera: 4000 });
// ── 7. Los servicios: por qué la gente entra todos los días
await toma(7, "home-servicios", "/", { espera: 3500, scroll: 900 });
// ── 8. La guía: el que viene a comprar, primero mira acá
await toma(8, "guia", "/guia", { espera: 3500 });
// ── 9. El cambio del día
await toma(9, "cambio", "/cambio", { espera: 3000 });
// ── 10. Los planes
await toma(10, "planes", "/planes", { espera: 3000, scroll: 250 });
// ── 11. El volante que se le deja al comerciante (papel, horizontal)
{
  const ctx = await b.newContext({ viewport: { width: 1200, height: 900 }, deviceScaleFactor: 2, serviceWorkers: "block" });
  const p = await ctx.newPage();
  await p.goto(`${BASE}/volante/vidrieria-pacheco`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2500);
  await p.locator(".vol-hoja, .vol, main").first().screenshot({ path: `${OUT}/11-volante.png` }).catch(() => p.screenshot({ path: `${OUT}/11-volante.png` }));
  console.log("✓ 11-volante.png");
  await p.goto(`${BASE}/volante/vidrieria-pacheco/mesa`, { waitUntil: "networkidle" });
  await p.waitForTimeout(2500);
  await p.screenshot({ path: `${OUT}/12-tarjeta-mesa.png` });
  console.log("✓ 12-tarjeta-mesa.png");
  await ctx.close();
}
// ── 13-14. Las mismas, en compu (por si el video va horizontal)
{
  const ctx = await b.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, serviceWorkers: "block" });
  await ctx.addCookies([{ name: "ciudad", value: "bermejo", domain: "127.0.0.1", path: "/" }]);
  const p = await ctx.newPage();
  for (const [n, nombre, ruta, espera] of [[13, "compu-home", "/", 4000], [14, "compu-mapa", "/buscar?rubro=ropa&vista=mapa", 8000], [15, "compu-ficha", "/comercios/rustico", 4000]]) {
    await p.goto(BASE + ruta, { waitUntil: "networkidle" });
    await p.addStyleTag({ content: ".install-banner, .uk-ayuda-btn, .uk-contesto { display: none !important; }" });
    await p.waitForTimeout(espera);
    await p.screenshot({ path: `${OUT}/${n}-${nombre}.png` });
    console.log("✓", `${n}-${nombre}.png`);
  }
  await ctx.close();
}

await b.close();
console.log("\nListo. Las capturas están en", OUT);
