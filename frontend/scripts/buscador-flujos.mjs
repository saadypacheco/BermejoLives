// Flujos del buscador de resultados con red lenta y celular emulado.
//
// Cubre lo que se rompió alguna vez: una respuesta vieja pisando la lista
// (lotes de fondo, "Cargar más"), el rubro invisible, ir al mapa y volver, y
// lo tecleado que se borraba al cambiar la URL.
//
//   npm run build && npx next start -p 3011 &
//   node scripts/buscador-flujos.mjs                 # contra el build local
//   node scripts/buscador-flujos.mjs https://uruku.bo  # contra prod
//
// Necesita playwright (está instalado sin guardar en package.json).
import { chromium, devices } from "playwright";
const BASE = process.argv[2] || "http://127.0.0.1:3011";
const b = await chromium.launch();
const { defaultBrowserType, ...iphone } = devices["iPhone 13"];
let fallas = 0;
function ok(cond, msg) { console.log((cond ? "OK  " : "MAL ") + msg); if (!cond) fallas++; }

async function nueva(lento) {
  const ctx = await b.newContext({ ...iphone, serviceWorkers: "block" });
  const p = await ctx.newPage();
  if (lento) {
    const cdp = await ctx.newCDPSession(p);
    await cdp.send("Network.enable");
    await cdp.send("Network.emulateNetworkConditions", { offline: false, latency: 600, downloadThroughput: 80 * 1024, uploadThroughput: 40 * 1024 });
  }
  const errores = [];
  p.on("request", (r) => { if (r.url().endsWith("/errores") && r.method() === "POST") errores.push(JSON.parse(r.postData() || "{}").mensaje); });
  const rpcs = [];
  p.on("request", (r) => { if (r.url().includes("buscar_comercios")) { const a = JSON.parse(r.postData() || "{}"); rpcs.push(`${a.q ?? "-"}@${a.p_offset}`); } });
  return { ctx, p, errores, rpcs };
}
async function estado(p) {
  const total = ((await p.locator(".uk-total-res").textContent().catch(() => "")) || "").trim();
  const n = await p.locator(".uk-res-grid article").count();
  const primero = await p.locator(".uk-res-grid article a[href^='/comercios/']").first().getAttribute("href").catch(() => "-");
  const caja = await p.inputValue("form.uk-search input").catch(() => "?");
  return { total, n, primero, caja };
}
async function esperarHidratacion(p, rpcs) { const n0 = rpcs.length; await p.waitForFunction(() => document.querySelector(".uk-res-grid article") != null, null, { timeout: 30000 }).catch(() => {}); }
async function buscar(p, texto) { await p.fill("form.uk-search input", texto); await p.tap("form.uk-search button[type=submit]"); }

// 1. "Cargar más" en vuelo y encima buscar rustico (red lenta)
{
  const { ctx, p, errores, rpcs } = await nueva(true);
  await p.goto(`${BASE}/buscar`, { waitUntil: "domcontentloaded" });
  await esperarHidratacion(p, rpcs);
  await p.waitForFunction(() => document.querySelectorAll(".uk-res-grid article").length >= 100, null, { timeout: 60000 }).catch(() => {});
  const btn = p.locator("button:has-text('Cargar más')");
  ok(await btn.count() === 1, `1. hay botón "Cargar más" con la lista de todos (tarjetas=${await p.locator(".uk-res-grid article").count()})`);
  await btn.scrollIntoViewIfNeeded(); await btn.tap();
  await p.evaluate(() => window.scrollTo(0, 0));
  await buscar(p, "Rustico");
  await p.waitForTimeout(12000);
  const e = await estado(p);
  ok(e.total === "2 resultados" && e.n === 2 && e.primero === "/comercios/rustico", `1. Cargar más en vuelo + buscar: ${JSON.stringify(e)} rpcs=${rpcs.join(" ")}`);
  ok(errores.length === 0, `1. sin avisos del vigía (${errores.join(" | ")})`);
  await ctx.close();
}
// 2. Buscar apenas hidrata, con lotes de fondo en vuelo (red lenta)
{
  const { ctx, p, errores, rpcs } = await nueva(true);
  await p.goto(`${BASE}/buscar`, { waitUntil: "domcontentloaded" });
  await esperarHidratacion(p, rpcs);
  await buscar(p, "Rustico");
  await p.waitForTimeout(12000);
  const e = await estado(p);
  ok(e.total === "2 resultados" && e.n === 2 && e.primero === "/comercios/rustico", `2. buscar con lotes en vuelo: ${JSON.stringify(e)} rpcs=${rpcs.join(" ")}`);
  ok(errores.length === 0, `2. sin avisos del vigía`);
  await ctx.close();
}
// 3. Desde el home por rubro, buscar adentro; sacar el chip
{
  const { ctx, p, errores } = await nueva(false);
  await p.goto(`${BASE}/buscar?rubro=ropa`, { waitUntil: "networkidle" });
  await buscar(p, "Rustico");
  await p.waitForTimeout(3000);
  let e = await estado(p);
  const vacio = await p.locator(".uk-empty").textContent().catch(() => "");
  ok(e.n === 0 && vacio.includes("No hay «Rustico»"), `3. rustico en ropa: ${JSON.stringify(e)} · "${vacio.trim().slice(0, 40)}"`);
  await p.tap("button.uk-search-chip");
  await p.waitForTimeout(3000);
  e = await estado(p);
  ok(e.total === "2 resultados" && e.n === 2, `3. sin chip: ${JSON.stringify(e)} url=${p.url().replace(BASE, "")}`);
  ok(errores.length === 0, `3. sin avisos del vigía`);
  await ctx.close();
}
// 4. Buscar, ir al mapa, volver a la lista; luego otra búsqueda
{
  const { ctx, p, errores } = await nueva(false);
  await p.goto(`${BASE}/buscar?q=rustico`, { waitUntil: "networkidle" });
  await p.tap(".uk-seg button:has-text('Mapa')"); await p.waitForTimeout(4000);
  await p.tap(".uk-seg button:has-text('Lista')"); await p.waitForTimeout(1000);
  let e = await estado(p);
  ok(e.total === "2 resultados" && e.n === 2, `4. mapa y vuelta: ${JSON.stringify(e)}`);
  await buscar(p, "Vidrieria"); await p.waitForTimeout(3000);
  e = await estado(p);
  ok(e.total === "1 resultado" && e.n === 1, `4. otra búsqueda: ${JSON.stringify(e)} url=${p.url().replace(BASE, "")}`);
  ok(errores.length === 0, `4. sin avisos del vigía`);
  await ctx.close();
}
// 5. Escribir sin buscar, tocar Mapa: lo escrito no se borra
{
  const { ctx, p } = await nueva(false);
  await p.goto(`${BASE}/buscar?q=rustico`, { waitUntil: "networkidle" });
  await p.fill("form.uk-search input", "rustico sab");
  await p.tap(".uk-seg button:has-text('Mapa')"); await p.waitForTimeout(1500);
  const caja = await p.inputValue("form.uk-search input");
  ok(caja === "rustico sab", `5. lo tecleado sobrevive a un cambio de URL propio: caja="${caja}"`);
  await ctx.close();
}
// 6. LA SECUENCIA QUE FALLABA EN LOS TELÉFONOS: home → un rubro de la barra →
//    esperar la lista entera → sacar el chip → buscar. Las páginas del rubro
//    traían comercios repetidos, React dejaba tarjetas huérfanas en el DOM, y
//    se veía "2 resultados" con veinticinco tarjetas. Se mira el DOM, no sólo
//    el estado, y se escucha el aviso de React por keys repetidas.
{
  const { ctx, p, errores } = await nueva(false);
  const avisosReact = [];
  p.on("console", (m) => { if (/same key|misma key|two children/i.test(m.text())) avisosReact.push(m.text().slice(0, 80)); });
  await p.goto(`${BASE}/`, { waitUntil: "networkidle" });
  await p.tap("nav.uk-catnav a[href='/buscar?rubro=ropa']");
  await p.waitForURL(/buscar/);
  await p.waitForFunction(() => document.querySelectorAll(".uk-res-grid article").length >= 90, null, { timeout: 60000 }).catch(() => {});
  const slugs = await p.locator(".uk-res-grid article a.uk-resficha").evaluateAll((as) => as.map((a) => a.getAttribute("href")));
  ok(new Set(slugs).size === slugs.length, `6. la lista del rubro no repite comercios (${slugs.length} tarjetas, ${new Set(slugs).size} distintas)`);
  await p.tap("button.uk-search-chip");
  await p.waitForTimeout(6000);
  let e = await estado(p);
  const enPantalla = await p.locator(".uk-res-grid article").count();
  ok(enPantalla <= 100, `6. sin el chip, la pantalla tiene ${enPantalla} tarjetas (≤ 100)`);
  await buscar(p, "Rustico");
  await p.waitForTimeout(5000);
  e = await estado(p);
  ok(e.total === "2 resultados" && e.n === 2 && e.primero === "/comercios/rustico", `6. rustico tras sacar el chip: ${JSON.stringify(e)}`);
  ok(avisosReact.length === 0, `6. React no avisó por keys repetidas (${avisosReact.join(" | ") || "ninguno"})`);
  ok(errores.length === 0, `6. sin avisos del vigía (${errores.join(" | ") || "ninguno"})`);
  await ctx.close();
}
// 7. Los accesos del home: un servicio es su rubro, escrito o por el chip
{
  const { ctx, p, errores, rpcs } = await nueva(false);
  // Por el chip: rubro=banos → los baños cargados, con su título.
  await p.goto(`${BASE}/buscar?rubro=banos`, { waitUntil: "networkidle" });
  await esperarHidratacion(p, rpcs);
  await p.waitForTimeout(3000);
  let e = await estado(p);
  const titulo = ((await p.locator(".uk-servicios-cab h2").textContent().catch(() => "")) || "").trim();
  ok(e.n > 0 && /Baños públicos/.test(titulo), `7. rubro=banos: ${e.n} tarjetas, título «${titulo}»`);
  const nombres = await p.locator(".uk-res-grid article a[href^='/comercios/']:not(.uk-resficha):not(.uk-rescover):not(.uk-resdesde)").evaluateAll((as) => as.map((a) => (a.textContent || "").trim().toLowerCase()));
  ok(nombres.every((n) => n === "" || /ba[ñn]o|sanitario/.test(n)), `7. todos los de rubro=banos son baños (${[...new Set(nombres)].filter(Boolean).slice(0, 4).join(", ")})`);
  // Escrito: "baño público" busca por el rubro, no por texto.
  await p.goto(`${BASE}/buscar`, { waitUntil: "networkidle" });
  await esperarHidratacion(p, rpcs);
  const antes = rpcs.length;
  await buscar(p, "baño público");
  await p.waitForTimeout(5000);
  const e2 = await estado(p);
  const pidioRubro = rpcs.slice(antes).some((r) => r.startsWith("-@") || r.startsWith("@"));
  ok(e2.n === e.n && pidioRubro, `7. escrito «baño público»: ${e2.n} tarjetas (= ${e.n} del rubro), rpcs=${rpcs.slice(antes).join(" ")}`);
  // Un servicio sin nada cargado dice que no hay, no "probá otra palabra".
  await p.goto(`${BASE}/buscar?rubro=wifi`, { waitUntil: "networkidle" });
  await p.waitForTimeout(4000);
  const vacio = ((await p.locator(".uk-empty").textContent().catch(() => "")) || "").trim();
  const nWifi = await p.locator(".uk-res-grid article").count();
  ok(nWifi > 0 || /Todavía no cargamos/.test(vacio), `7. rubro=wifi: ${nWifi} tarjetas, vacío=«${vacio.slice(0, 50)}»`);
  // Ofertas sin ofertas: lo dice.
  await p.goto(`${BASE}/buscar?of=1`, { waitUntil: "networkidle" });
  await p.waitForTimeout(8000);
  const nOf = await p.locator(".uk-res-grid article").count();
  const vacioOf = ((await p.locator(".uk-empty").textContent().catch(() => "")) || "").trim();
  ok(nOf > 0 || /Todavía no hay ofertas/.test(vacioOf), `7. of=1: ${nOf} tarjetas, vacío=«${vacioOf.slice(0, 50)}»`);
  ok(errores.length === 0, `7. sin avisos del vigía (${errores.join(" | ") || "ninguno"})`);
  await ctx.close();
}
await b.close();
console.log(fallas ? `${fallas} FALLAS` : "todo ok");
process.exit(fallas ? 1 : 0);
