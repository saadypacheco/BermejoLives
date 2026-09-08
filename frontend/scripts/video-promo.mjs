// Arma el video de 30 segundos para el comerciante, desde el sitio real.
//
// POR QUÉ ASÍ Y NO GRABANDO LA PANTALLA A MANO
// ============================================
// Las tomas del sitio salen de uruku.bo en vivo, así que muestran los comercios
// que hay de verdad. Un video hecho con pantallas de mentira envejece el día que
// alguien entra y ve otra cosa — y en una ciudad chica alguien entra.
//
// Cada escena se compone en HTML —la captura arriba, el texto abajo— y se
// fotografía. Poner el texto con ffmpeg significa pelear con el escapado de
// fuentes en Windows para conseguir menos control; el navegador ya sabe
// componer texto y es el que dibuja el resto del sitio.
//
// LO QUE ESTO NO HACE, Y CONVIENE SABERLO
// =======================================
// No filma la calle (carteles, vidrieras, gente caminando) ni anima el tecleo.
// Sale un video de placas, que sirve para el estado de WhatsApp. La versión
// fuerte es grabar la pantalla del celular usando el sitio de verdad —el dedo
// escribiendo "zapatillas" y los resultados apareciendo— y montar encima estas
// mismas placas. Cinco minutos con el teléfono.
//
// SE CORRE EN LA MÁQUINA DE DESARROLLO, NO EN EL VPS
// ==================================================
// El servidor no tiene Node ni ffmpeg —el frontend se construye adentro de
// Docker— y no conviene instalarlos: serían 150 MB de navegador headless más
// las librerías de sistema que pide Chromium, en una máquina que sólo tiene que
// servir el sitio.
//
// Da igual desde dónde se ejecute: el script entra a uruku.bo por internet,
// como cualquier visitante.
//
// USO (en la PC, dentro del repo)
//   cd frontend
//   npm i --no-save playwright && npx playwright install chromium
//   node scripts/video-promo.mjs
//   (BASE=https://encontralo.store node scripts/video-promo.mjs  → contra QA)
//
// Deja las placas en frontend/video-promo/ y el video en video-promo/uruku.mp4

import { chromium, devices } from "playwright";
import { mkdir, writeFile } from "node:fs/promises";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import path from "node:path";

const run = promisify(execFile);
const BASE = (process.env.BASE || "https://uruku.bo").replace(/\/$/, "");
const OUT = "video-promo";
const BUSQUEDA = process.env.BUSQUEDA || "zapatillas";
const CIUDAD = process.env.CIUDAD || "bermejo";

// El guion, tal cual está en docs/publicidad-uruku.md. Si cambia allá, cambia
// acá: son el mismo video y separarlos es cómo se termina grabando una cosa
// distinta de la que se aprobó.
const GUION = [
  { id: "1", seg: 4, texto: "Su cartel dice el nombre de su local.", captura: null },
  { id: "2", seg: 4, texto: "La gente busca <b>lo que vende</b>.", captura: "buscar-vacio" },
  { id: "3", seg: 6, texto: `En URUKU lo encuentran buscando “${BUSQUEDA}”.`, captura: "buscar" },
  { id: "4", seg: 6, texto: "Su ficha, con su horario y su WhatsApp.", captura: "ficha" },
  { id: "5", seg: 5, texto: "El cliente le escribe directo.<br><b>Sin comisión.</b>", captura: "mapa" },
  { id: "6", seg: 5, texto: "Su negocio ya está.<br><b>Búsquelo en uruku.bo</b>", captura: null },
];

/** Un comercio real Y CON WHATSAPP, para la toma de la ficha.
 *
 *  El primero de la lista no sirve: muchos comercios se cargaron desde la calle
 *  sin número —de los 67 de la última salida, 43 no lo tienen— y la placa dice
 *  "su WhatsApp". Mostrar una ficha sin el botón verde justo cuando el texto lo
 *  nombra es peor que no mostrar la ficha.
 *
 *  Se prueban los primeros candidatos hasta encontrar uno que lo tenga. */
async function primerSlug(page) {
  if (process.env.SLUG) return process.env.SLUG;
  // `domcontentloaded` y no `networkidle`: el buscador sigue trayendo lotes por
  // detrás mientras la persona lee, así que la red no queda quieta nunca y la
  // espera vencía a los 30 segundos.
  await page.goto(`${BASE}/buscar?q=${encodeURIComponent(BUSQUEDA)}&ciudad=${CIUDAD}`,
                  { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(2500);
  const hrefs = await page.locator('a[href^="/comercios/"]').evaluateAll(
    (as) => [...new Set(as.map((a) => a.getAttribute("href")))].slice(0, 8));

  for (const href of hrefs) {
    const slug = href.replace("/comercios/", "").split("#")[0];
    await page.goto(`${BASE}/comercios/${slug}`, { waitUntil: "domcontentloaded" });
    await page.waitForTimeout(1200);
    if (await page.locator(".uk-ficha-wa").count()) return slug;
    console.log(`  (salteado ${slug}: no tiene WhatsApp cargado)`);
  }
  return hrefs.length ? hrefs[0].replace("/comercios/", "").split("#")[0] : "";
}

/** La placa: la captura del sitio arriba, el texto abajo, el logo al pie. */
function placa(texto, capturaB64) {
  return `<!doctype html><meta charset="utf-8"><style>
    *{margin:0;padding:0;box-sizing:border-box}
    body{width:1080px;height:1920px;background:linear-gradient(180deg,#06171b,#0b2027 60%,#061418);
      font-family:system-ui,-apple-system,"Segoe UI",sans-serif;color:#e9f3f0;
      display:flex;flex-direction:column;align-items:center;justify-content:center;gap:70px;padding:90px 70px}
    .cap{width:620px;border-radius:38px;overflow:hidden;box-shadow:0 40px 120px rgba(0,0,0,.6);
      border:8px solid #12343c}
    .cap img{width:100%;display:block}
    .txt{font-size:62px;line-height:1.25;text-align:center;font-weight:600;max-width:900px}
    .txt b{color:#39ff9e;font-weight:800}
    .pie{position:absolute;bottom:90px;font-size:40px;letter-spacing:.35em;font-weight:800;color:#9db4b3}
  </style>
  ${capturaB64 ? `<div class="cap"><img src="data:image/png;base64,${capturaB64}"></div>` : ""}
  <div class="txt">${texto}</div>
  <div class="pie">URUKU.BO</div>`;
}

const main = async () => {
  await mkdir(OUT, { recursive: true });
  const browser = await chromium.launch();

  // Las capturas del sitio, en tamaño de celular: es como lo va a ver quien mire
  // el video, y una captura de escritorio adentro de un video vertical se ve
  // como otra cosa.
  const tel = await browser.newContext({ ...devices["iPhone 13"] });
  const page = await tel.newPage();
  const slug = await primerSlug(page);
  if (!slug) console.warn("! No se encontró ningún comercio: la toma de ficha va a quedar vacía.");

  // El scroll no es un detalle: en la ficha, el botón de WhatsApp queda abajo
  // del pliegue en un celular, y la placa dice justamente "su WhatsApp". Una
  // promo que promete algo que no se ve en la foto es peor que no mostrarlo.
  const rutas = {
    "buscar-vacio": [`/buscar?ciudad=${CIUDAD}`, 0],
    "buscar": [`/buscar?q=${encodeURIComponent(BUSQUEDA)}&ciudad=${CIUDAD}`, 0],
    "ficha": [`/comercios/${slug}`, 430],
    "mapa": [`/buscar?q=${encodeURIComponent(BUSQUEDA)}&ciudad=${CIUDAD}&vista=mapa`, 0],
  };
  const capturas = {};
  for (const [id, [ruta, scroll]] of Object.entries(rutas)) {
    await page.goto(BASE + ruta, { waitUntil: "domcontentloaded" });
    // El cartel de "Instalá URUKU" tapa el encabezado. Es correcto en el sitio
    // y no tiene nada que hacer en una promo: se oculta sólo para la foto.
    await page.addStyleTag({ content: ".install-banner{display:none !important}" });
    // El mapa pinta los pines después de cargar los tiles; sin esta espera sale
    // el recuadro gris, que es peor que no mostrar el mapa.
    await page.waitForTimeout(ruta.includes("vista=mapa") ? 4000 : 1800);
    if (scroll) { await page.mouse.wheel(0, scroll); await page.waitForTimeout(700); }
    capturas[id] = (await page.screenshot()).toString("base64");
    console.log(`  captura ${id}`);
  }
  await tel.close();

  // Las placas, a resolución de video vertical.
  const lienzo = await browser.newContext({ viewport: { width: 1080, height: 1920 },
                                            deviceScaleFactor: 1 });
  const p2 = await lienzo.newPage();
  const frames = [];
  for (const escena of GUION) {
    await p2.setContent(placa(escena.texto, escena.captura ? capturas[escena.captura] : null));
    await p2.waitForTimeout(250);
    const archivo = path.join(OUT, `escena-${escena.id}.png`);
    await p2.screenshot({ path: archivo });
    frames.push({ archivo, seg: escena.seg });
    console.log(`  placa ${escena.id} (${escena.seg}s)`);
  }
  await browser.close();

  // ffmpeg concat: cada placa dura lo que dice el guion. El último archivo se
  // repite porque concat ignora la duración de la última entrada.
  const lista = frames.map((f) => `file '${path.basename(f.archivo)}'\nduration ${f.seg}`).join("\n")
    + `\nfile '${path.basename(frames.at(-1).archivo)}'\n`;
  await writeFile(path.join(OUT, "lista.txt"), lista);

  const salida = path.join(OUT, "uruku.mp4");
  await run("ffmpeg", ["-y", "-f", "concat", "-safe", "0", "-i", "lista.txt",
                       "-vf", "fps=30,format=yuv420p", "-c:v", "libx264", "-preset", "medium",
                       "-crf", "20", path.basename(salida)], { cwd: OUT });
  console.log(`\nListo: ${salida}  (${GUION.reduce((a, b) => a + b.seg, 0)}s)`);
};

main().catch((e) => { console.error(e); process.exit(1); });
