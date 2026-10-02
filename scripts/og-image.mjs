/**
 * Arma `frontend/public/og-image.png`: la imagen que se ve al compartir
 * uruku.bo y la que acompaña al resultado en Google.
 *
 *   node scripts/og-image.mjs
 *
 * POR QUÉ SE REHACE
 * =================
 * La del kit decía «Todo Bermejo en un solo lugar» y «antes de cruzar». Es el
 * mensaje de UNA ciudad, y es la única imagen que existe: quien busca «uruku»
 * desde La Paz o Santa Cruz veía la marca presentada como el sitio de un
 * pueblo de frontera.
 *
 * No se puede resolver poniendo la ciudad en la imagen: la ciudad vive en una
 * COOKIE y la vista previa la pide un robot, que no manda cookies. Así que la
 * imagen no nombra ninguna. El día que cada ciudad tenga su dirección
 * (uruku.bo/santa-cruz) se podrá hacer una por ciudad desde la URL.
 *
 * SE CORRE EN LA MÁQUINA DE DESARROLLO, no en el VPS, y sólo cuando cambia el
 * mensaje o el logo. El PNG queda commiteado; el sitio no genera nada.
 */
import { readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { tmpdir } from "node:os";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createRequire } from "node:module";

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const VECINOS = ["../MentorComercial", "../apops"];

// Los dos dibujos del manual: la marca horizontal y el símbolo suelto.
const horizontal = readFileSync(resolve(RAIZ, "docs/Uruku-KIT-COMPLETO/2-Logos-y-Dax/uruku-horizontal-color.svg"), "utf8");
const simbolo = readFileSync(resolve(RAIZ, "docs/Uruku-KIT-COMPLETO/2-Logos-y-Dax/uruku-simbolo-color.svg"), "utf8");

const ic = catalogo();

// Mismo diseño que la pieza del kit —fondo cielo→crema, logo arriba, titular
// grande, bajada, tres fichas y el símbolo a la derecha—; lo único que cambia
// es que el titular no nombra una ciudad.
const html = `<!doctype html><html lang="es"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;700;800&display=swap" rel="stylesheet">
<style>
  *{box-sizing:border-box;margin:0}
  body{width:1200px;height:630px;overflow:hidden;font-family:Poppins,Arial,sans-serif;
       background:linear-gradient(165deg,#E3EDFA 0%,#F3F1E6 55%,#FBF7EC 100%);
       color:#214533;display:flex;align-items:center;padding:0 76px;gap:40px}
  .izq{flex:1;min-width:0}
  .logo{height:74px;margin-bottom:42px}
  .logo svg{height:100%;width:auto;display:block}
  h1{font-size:76px;font-weight:800;line-height:1.08;letter-spacing:-.025em}
  h1 em{color:#1D8D52;font-style:normal}
  /* text-wrap balance reparte los renglones: sin esto la bajada dejaba la
     palabra «local.» sola abajo. */
  p{font-size:29px;color:#4E6053;margin-top:24px;text-wrap:balance;max-width:16em}
  .fichas{display:flex;gap:16px;margin-top:40px}
  .f{display:flex;align-items:center;gap:11px;background:#fff;border:1px solid #E6E2D6;
     border-radius:999px;padding:14px 26px;font-size:25px;font-weight:700;color:#1A764C;
     box-shadow:0 6px 18px rgba(33,69,51,.07)}
  .f svg{width:26px;height:26px;flex:0 0 auto}
  .marca{width:290px;flex:0 0 auto}
  .marca svg{width:100%;height:auto;display:block}
</style></head><body>
  <div class="izq">
    <div class="logo">${horizontal}</div>
    <h1>Toda <em>tu ciudad</em><br>en un solo lugar</h1>
    <p>Comercios, ofertas y el WhatsApp de cada local.</p>
    <div class="fichas">
      <span class="f">${ic("comercios")}Comercios</span>
      <span class="f">${ic("ofertas")}Ofertas</span>
      <span class="f">${ic("mapa")}Mapa</span>
    </div>
  </div>
  <div class="marca">${simbolo}</div>
</body></html>`;

/** Un ícono del catálogo del sitio, para que la pieza lleve los mismos dibujos
 *  que las pantallas y no un juego aparte. Se lee del archivo generado
 *  (`npm run iconos`), que es texto plano a propósito. */
function catalogo() {
  const mod = readFileSync(resolve(RAIZ, "frontend/lib/iconos-dibujos.ts"), "utf8");
  const trozo = (desde, hasta) => mod.split(desde)[1].split(hasta)[0].trim().replace(/,$/, "");
  const dibujos = JSON.parse(`[${trozo("DUOTONO: readonly string[] = [", "\n];")}]`);
  // Las claves simples van sin comillas en el archivo generado; JSON las pide.
  const porClave = JSON.parse(`{${trozo("POR_CLAVE: Record<string, number> = {", "\n};").replace(/^(\s*)([a-z0-9_]+):/gm, '$1"$2":')}}`);
  return (clave) =>
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 256 256" fill="#1D8D52">${dibujos[porClave[clave]]}</svg>`;
}

// El HTML intermedio NO va en `public/`: todo lo que está ahí lo publica
// Next tal cual, así que el andamio quedaba servido en uruku.bo. Va al temporal
// del sistema, que es de donde no sale.
const htmlPath = resolve(tmpdir(), "uruku-og-image.html");
writeFileSync(htmlPath, html);

const base = VECINOS.map((v) => resolve(RAIZ, v)).find((d) => {
  try { readFileSync(resolve(d, "node_modules/playwright/package.json")); return true; } catch { return false; }
});
if (!base) { console.error(`No encontré Playwright en ${VECINOS.join(" ni ")}.`); process.exit(1); }
const { chromium } = createRequire(resolve(base, "package.json"))("playwright");

const salida = resolve(RAIZ, "frontend/public/og-image.png");
const navegador = await chromium.launch();
try {
  const pagina = await navegador.newPage({ viewport: { width: 1200, height: 630 } });
  await pagina.goto(pathToFileURL(htmlPath).href, { waitUntil: "networkidle" });
  await pagina.evaluate(() => document.fonts.ready);
  await pagina.screenshot({ path: salida });
} finally {
  await navegador.close();
}
console.log(salida);
