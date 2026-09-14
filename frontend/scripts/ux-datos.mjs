// Saca del sitio real lo que la maqueta del home necesita: los rubros tal
// como se muestran, y unos comercios con foto de distintas búsquedas.
import { chromium, devices } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";

const BASE = "https://uruku.bo";
const OUT = process.env.OUT || "ux-datos";
await mkdir(OUT, { recursive: true });

const browser = await chromium.launch();
const ctx = await browser.newContext({ ...devices["Pixel 7"] });
const p = await ctx.newPage();

await p.goto(BASE + "/", { waitUntil: "domcontentloaded" });
await p.waitForTimeout(2000);
const rubros = await p.locator(".uk-chip, [class*='tab']").evaluateAll(
  (els) => [...new Set(els.map((e) => e.textContent.trim()).filter((t) => t && t.length < 40))]);
console.log("rubros:", rubros.slice(0, 40).join(" | "));

const comercios = [];
for (const q of ["zapatillas", "ropa", "ferreteria", "farmacia", "comida", "celulares", "colchones", "perfumeria"]) {
  await p.goto(`${BASE}/buscar?q=${q}&ciudad=bermejo`, { waitUntil: "domcontentloaded" });
  await p.waitForTimeout(2200);
  const cards = await p.locator(".uk-rescard").evaluateAll((cs) => cs.slice(0, 3).map((c) => ({
    nombre: c.querySelector("h4")?.textContent.trim(),
    pills: [...c.querySelectorAll(".uk-pill")].map((x) => x.textContent.trim()),
    dir: c.querySelector(".uk-resdir")?.textContent.trim() || "",
    img: c.querySelector("img")?.getAttribute("src") || "",
    href: c.querySelector("a[href^='/comercios/']")?.getAttribute("href") || "",
  })));
  for (const c of cards) if (c.img && !comercios.find((x) => x.href === c.href)) comercios.push({ q, ...c });
}
await writeFile(`${OUT}/comercios.json`, JSON.stringify(comercios, null, 2));
console.log("comercios:", comercios.length);
for (const c of comercios) console.log(" ", c.q, "|", c.nombre, "|", c.pills.join(", "), "|", c.dir, "|", c.img.slice(0, 80));
await browser.close();
