// Revisión de todo el sitio público: cada ruta, en compu y en iPhone.
//
// Por cada página anota lo que una persona no ve pero sufre: errores de
// consola, pedidos que fallaron (4xx/5xx), enlaces internos que dan 404,
// imágenes rotas, scroll horizontal (la página "se corre" en el celular) y
// textos de vacío. Y guarda una captura de cada una para mirarlas después.
//
//   npm run build && npx next start -p 3011 &
//   node scripts/revision-sitio.mjs [base] [carpeta-de-capturas]
//
import { chromium, devices } from "playwright";
import fs from "node:fs";

const BASE = process.argv[2] || "http://127.0.0.1:3011";
const OUT = process.argv[3] || "./revision";
fs.mkdirSync(OUT, { recursive: true });

const RUTAS = [
  "/", "/buscar", "/buscar?q=rustico", "/buscar?rubro=ropa", "/buscar?rubro=banos&vista=mapa", "/buscar?rubro=cambio",
  "/buscar?of=1", "/buscar?cerca=1", "/buscar?q=zzzzqqq", "/guia", "/cambio", "/planes", "/mapa",
  "/comercios/rustico", "/comercios/vidrieria-pacheco", "/comercios/no-existe-zz",
  "/volante/vidrieria-pacheco", "/volante/vidrieria-pacheco/mesa",
  "/guardados", "/perfil", "/autoregistro", "/autoregistro?modo=registro", "/mi-comercio", "/recuperar-negocio",
  "/publicar", "/contenido", "/admin", "/campo", "/reservas", "/software", "/guia-venta", "/bermejo",
  "/proximamente", "/reclamos", "/version", "/ruta-que-no-existe",
];

const b = await chromium.launch();
const { defaultBrowserType, ...iphone } = devices["iPhone 13"];
const informe = [];

async function revisar(ruta, modo) {
  const ctx = await b.newContext(modo === "movil" ? { ...iphone, serviceWorkers: "block" } : { viewport: { width: 1366, height: 768 }, serviceWorkers: "block" });
  const p = await ctx.newPage();
  const consola = [], fallidos = [];
  p.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") consola.push(`${m.type()}: ${m.text().slice(0, 160)}`); });
  p.on("response", (r) => { const s = r.status(); if (s >= 400 && !r.url().includes("/no-existe") && !r.url().includes("ruta-que-no-existe")) fallidos.push(`${s} ${r.url().replace(BASE, "").slice(0, 120)}`); });
  p.on("requestfailed", (r) => { const f = r.failure()?.errorText || ""; if (!/ERR_ABORTED/.test(f)) fallidos.push(`FAIL ${r.url().replace(BASE, "").slice(0, 100)} ${f}`); });
  let status = 0;
  try {
    const res = await p.goto(BASE + ruta, { waitUntil: "networkidle", timeout: 60000 });
    status = res?.status() ?? 0;
  } catch (e) {
    informe.push({ ruta, modo, status: "TIMEOUT", detalle: String(e).slice(0, 120) });
    await ctx.close();
    return;
  }
  await p.waitForTimeout(2500);
  const medidas = await p.evaluate(() => {
    const imgsRotas = [...document.images].filter((i) => i.complete && i.naturalWidth === 0 && i.src && !i.src.startsWith("data:")).map((i) => i.src.slice(0, 100));
    const enlaces = [...new Set([...document.querySelectorAll("a[href^='/']")].map((a) => a.getAttribute("href")))];
    const vacios = [...document.querySelectorAll(".uk-empty, .uk-guia-vacio, [class*='vacio'], [class*='empty']")].map((e) => (e.textContent || "").trim().slice(0, 90));
    const titulo = document.title;
    const h1 = document.querySelector("h1")?.textContent?.trim().slice(0, 80) || "";
    return {
      scrollX: document.documentElement.scrollWidth > window.innerWidth + 1 ? `${document.documentElement.scrollWidth} > ${window.innerWidth}` : "",
      imgsRotas, enlaces, vacios, titulo, h1,
      texto: (document.body.innerText || "").slice(0, 4000),
    };
  });
  const nombre = (modo + ruta).replace(/[^a-z0-9]+/gi, "_").slice(0, 80);
  await p.screenshot({ path: `${OUT}/${nombre}.png`, fullPage: true }).catch(() => {});
  informe.push({ ruta, modo, status, titulo: medidas.titulo, h1: medidas.h1, scrollX: medidas.scrollX, imgsRotas: medidas.imgsRotas,
                 consola: [...new Set(consola)], fallidos: [...new Set(fallidos)], vacios: medidas.vacios, enlaces: medidas.enlaces,
                 undefinedEnTexto: /\bundefined\b|\bNaN\b|\[object Object\]|\bnull\b/.test(medidas.texto) });
  await ctx.close();
}

for (const ruta of RUTAS) {
  await revisar(ruta, "compu");
  await revisar(ruta, "movil");
  const ult = informe.slice(-2);
  for (const r of ult) {
    const avisos = [];
    if (typeof r.status === "number" && r.status >= 400 && !/no-existe/.test(r.ruta)) avisos.push(`HTTP ${r.status}`);
    if (r.status === "TIMEOUT") avisos.push("TIMEOUT");
    if (r.scrollX) avisos.push(`scroll horizontal ${r.scrollX}`);
    if (r.imgsRotas?.length) avisos.push(`${r.imgsRotas.length} img rotas`);
    if (r.consola?.length) avisos.push(`${r.consola.length} consola`);
    if (r.fallidos?.length) avisos.push(`${r.fallidos.length} pedidos fallidos`);
    if (r.undefinedEnTexto) avisos.push("undefined/NaN en el texto");
    console.log(`${avisos.length ? "OJO " : "ok  "} ${r.modo.padEnd(5)} ${r.ruta.padEnd(40)} ${avisos.join(" · ")}`);
  }
}

// Enlaces internos: cada uno, una vez, ¿responde?
const todos = new Set(informe.flatMap((r) => r.enlaces || []));
const rotos = [];
const ctx = await b.newContext({ serviceWorkers: "block" });
const p = await ctx.newPage();
for (const h of todos) {
  if (/^\/(admin|api|_next)/.test(h) || h.startsWith("/#")) continue;
  try {
    const res = await p.goto(BASE + h, { waitUntil: "domcontentloaded", timeout: 30000 });
    if ((res?.status() ?? 0) >= 400) rotos.push(`${res.status()} ${h}`);
  } catch (e) { rotos.push(`ERR ${h}`); }
}
await ctx.close();
console.log(`\nEnlaces internos distintos: ${todos.size}. Rotos: ${rotos.length}`);
for (const r of rotos) console.log("  " + r);

fs.writeFileSync(`${OUT}/informe.json`, JSON.stringify(informe, null, 2));
await b.close();
