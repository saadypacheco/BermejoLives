/**
 * Capturas de pantalla para los manuales y los videos, contra la DEMO local.
 *
 *   python scripts/demo/demo.py up                 # la demo con datos ficticios
 *   node scripts/capturas-manual.mjs               # todas
 *   node scripts/capturas-manual.mjs --solo admin/1   # sólo las que matcheen (perfil/id, regex)
 *   node scripts/capturas-manual.mjs --base        # usa docs/manuales/capturas-base.json
 *
 * Lee docs/manuales/capturas.json (o capturas-base.json si no existe / con --base):
 *   [{ perfil, id, ruta, viewport: "mobile"|"desktop"|"ambos", pasos, descripcion }]
 * y deja frontend/public/manuales/capturas/<perfil>/<id>-mobile.png y/o -desktop.png
 * (mobile 390×844 escala 2; desktop 1440×900).
 *
 * `pasos` puede ser texto (para la persona) o una lista de acciones simples
 * ({clic}, {titulo}, {ver}, {llenar, valor}, {esperar}, {scroll}, {pausa}). Lo que
 * necesita algo especial está en HANDLERS, por `perfil/id`.
 *
 * SÓLO CONTRA LA DEMO: entra con usuarios de demo y algunas capturas escriben
 * (generar una clave, cargar un local). Nunca apuntarlo a QA ni a producción.
 *
 * Playwright no es dependencia del repo: se toma de un repo vecino (como
 * scripts/instructivo.mjs) o de la variable PLAYWRIGHT_DIR.
 */
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";

const RAIZ = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const RUN = resolve(RAIZ, "scripts/demo/.run");
const SALIDA = resolve(RAIZ, "frontend/public/manuales/capturas");
const BASE = (process.env.DEMO_FRONT || "http://localhost:3990").replace(/\/$/, "");
const API = (process.env.DEMO_API || "http://localhost:8990").replace(/\/$/, "");

const arg = (n) => { const i = process.argv.indexOf(`--${n}`); return i > 0 ? (process.argv[i + 1] ?? true) : undefined; };
const SOLO = arg("solo") ? new RegExp(arg("solo")) : null;

// ── Playwright del vecino
const VECINOS = [process.env.PLAYWRIGHT_DIR, "../MentorComercial", "../apops", "../reservalo"].filter(Boolean);
const dirPw = VECINOS.map((v) => resolve(RAIZ, v)).find((d) => existsSync(resolve(d, "node_modules/playwright")));
if (!dirPw) {
  console.error(`No encontré Playwright en ${VECINOS.join(", ")}. Poné PLAYWRIGHT_DIR=<repo con node_modules/playwright>.`);
  process.exit(1);
}
const { chromium } = createRequire(resolve(dirPw, "package.json"))("playwright");

// ── la lista
const fCapturas = resolve(RAIZ, "docs/manuales/capturas.json");
const fBase = resolve(RAIZ, "docs/manuales/capturas-base.json");
const fuente = arg("base") || !existsSync(fCapturas) ? fBase : fCapturas;
if (!existsSync(fuente)) { console.error(`No existe ${fuente}.`); process.exit(1); }
const LISTA = JSON.parse(readFileSync(fuente, "utf8"));
const fDatos = resolve(RUN, "demo-datos.json");
if (!existsSync(fDatos)) { console.error("Falta scripts/demo/.run/demo-datos.json: corré `python scripts/demo/demo.py up`."); process.exit(1); }
const D = JSON.parse(readFileSync(fDatos, "utf8"));

function resolverRuta(ruta) {
  const c = D.comercio_prueba;
  return ruta
    .replace(/<slug-con-estrella-y-ofertas>|<slug-con-chatbot>|<slug-del-comercio-de-prueba>|<slug>/g, c.slug)
    .replace(/\/novedades\/uruku\/<id>/, `/novedades/uruku/${D.novedad_uruku_id}`)
    .replace(/<id>/g, c.id)
    .replace(/<nombre>/g, encodeURIComponent(c.nombre));
}

// ── sesiones (storageState armado con el login de la API)
const post = async (p, b) => {
  const r = await fetch(API + p, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(b) });
  if (!r.ok) throw new Error(`${p} → ${r.status} ${await r.text()}`);
  return r.json();
};
const LOGIN = {
  anon: async () => [],
  admin: async () => [["bermejo_admin_token", (await post("/auth/login", { email: D.panel.admin, password: D.panel.clave })).access_token]],
  moderador: async () => [["bermejo_admin_token", (await post("/auth/login", { email: D.panel.moderador, password: D.panel.clave })).access_token]],
  revisor: async () => [["bermejo_admin_token", (await post("/auth/login", { email: D.panel.revisor, password: D.panel.clave })).access_token]],
  publicador: async () => [["bermejo_publicador_token", (await post("/auth/publicador/login", { email: D.panel.publicador, password: D.panel.clave })).access_token]],
  agente: async () => [["bermejo_agente_token", (await post("/auth/campo/login", { email: D.panel.agente, password: D.panel.clave })).access_token]],
  vendedor: async () => {
    const d = await post("/auth/comercio/ingresar", { whatsapp: D.comercio_prueba.whatsapp, clave: D.comercio_prueba.clave });
    return [["bermejo_comercio_token", d.access_token], ["bermejo_comercio", JSON.stringify(d.comercio)]];
  },
  comprador: async () => {
    const d = await post("/auth/usuario/ingresar", { whatsapp: D.comprador.whatsapp, clave: D.comprador.clave });
    return [["bermejo_usuario_token", d.access_token], ["bermejo_usuario", JSON.stringify(d.usuario)]];
  },
};
const ESTADOS = {};
async function estado(sesion) {
  if (!ESTADOS[sesion]) {
    const kv = await LOGIN[sesion]();
    const st = {
      cookies: [{ name: "ciudad", value: "bermejo", domain: new URL(BASE).hostname, path: "/", expires: -1, httpOnly: false, secure: false, sameSite: "Lax" }],
      origins: [{ origin: BASE, localStorage: [["uk-theme", "dark"], ...kv].map(([name, value]) => ({ name, value })) }],
    };
    writeFileSync(resolve(RUN, `estado-${sesion}.json`), JSON.stringify(st, null, 1));
    ESTADOS[sesion] = st;
  }
  return ESTADOS[sesion];
}

// ── helpers de pasos
function helpers(p, ctx) {
  const visible = (loc) => loc.filter({ visible: true }).first();
  const h = {
    p, ctx,
    async clic(t, { exact = false, timeout = 10000, n = 0 } = {}) {
      const rx = typeof t === "string" ? t : t;
      const loc = p.getByRole("button", { name: rx, exact })
        .or(p.getByRole("link", { name: rx, exact }))
        .or(p.getByRole("tab", { name: rx, exact }))
        .or(p.getByText(rx, { exact }));
      const el = n ? loc.filter({ visible: true }).nth(n) : visible(loc);
      await el.scrollIntoViewIfNeeded({ timeout }).catch(() => {});
      await el.click({ timeout });
      await h.pausa(700);
    },
    async titulo(t, { n = 0, timeout = 10000 } = {}) {
      const loc = p.locator(`[title="${t}"], [aria-label="${t}"]`).filter({ visible: true }).nth(n);
      await loc.scrollIntoViewIfNeeded({ timeout }).catch(() => {});
      await loc.click({ timeout });
      await h.pausa(700);
    },
    async ver(t, { exact = false, bloque = "start", timeout = 10000 } = {}) {
      const el = visible(p.getByText(t, { exact }));
      await el.waitFor({ timeout });
      await el.evaluate((e, b) => {
        e.scrollIntoView({ block: b });
        if (b !== "start") return;
        // Que no quede debajo de una cabecera fija (la del sitio o la del modal).
        for (let a = e.parentElement; a; a = a.parentElement) {
          const st = getComputedStyle(a);
          if (/(auto|scroll)/.test(st.overflowY) && a.scrollHeight > a.clientHeight) { a.scrollTop -= 90; return; }
        }
        window.scrollBy(0, -90);
      }, bloque);
      await h.pausa(500);
    },
    async esperar(t, timeout = 15000) { await visible(p.getByText(t)).waitFor({ timeout }); },
    async llenar(campo, valor) {
      const loc = p.getByPlaceholder(campo).or(p.getByLabel(campo));
      await visible(loc).fill(String(valor));
      await h.pausa(300);
    },
    async scroll(px) { await p.mouse.wheel(0, px); await h.pausa(600); },
    async arriba() { await p.evaluate(() => window.scrollTo(0, 0)); await h.pausa(300); },
    pausa: (ms) => p.waitForTimeout(ms),
    async carga() { await esperarCarga(p); },
    async archivo(boton, ruta = resolve(RUN, "fotos", D.comercio_prueba.slug, "galeria-1.jpg")) {
      const [fc] = await Promise.all([p.waitForEvent("filechooser", { timeout: 10000 }), h.clic(boton)]);
      await fc.setFiles(ruta);
      await h.pausa(1500);
    },
  };
  return h;
}

async function esperarCarga(p) {
  // El sitio consulta /version y manda métricas cada tanto: «networkidle» puede no llegar nunca.
  await p.waitForLoadState("networkidle", { timeout: 6000 }).catch(() => {});
  await p.waitForFunction(() => [...document.images].every((i) => i.complete), null, { timeout: 8000 }).catch(() => {});
  // Mapas: que haya teselas cargadas y ninguna a medio bajar.
  await p.waitForFunction(() => !document.querySelector(".leaflet-container")
    || (document.querySelector(".leaflet-tile-loaded") && !document.querySelector(".leaflet-tile-loading")),
  null, { timeout: 20000 }).catch(() => {});
  await p.waitForTimeout(700);
}

/** Mientras dure la captura, la galería «está llena»: el GET dice límite = cantidad y subir da el 409 del tope. */
async function galeriaLlena(ctx) {
  await ctx.route(new RegExp(`^${API.replace(/[.:/]/g, "\\$&")}/.*fotos.*`), async (route) => {
    const req = route.request();
    if (req.method() === "GET") {
      const r = await route.fetch();
      let j; try { j = await r.json(); } catch { return route.fulfill({ response: r }); }
      if (j && Array.isArray(j.items)) j.limite = j.items.length;
      return route.fulfill({ response: r, json: j });
    }
    if (req.method() === "POST") {
      return route.fulfill({ status: 409, json: { detail: {
        mensaje: "Llegaste al tope de fotos de tu plan.", codigo: "tope_fotos", limite: 8, precio_extra: 5, moneda: "BOB",
        mas_vieja: { id: "demo", url: `${API}/fotos/${D.comercio_prueba.slug}/galeria-1.jpg` } } } });
    }
    return route.continue();
  });
}

const ACA = { latitude: D.agente_aca.lat, longitude: D.agente_aca.lng };
const LEJOS = { latitude: -22.7405, longitude: -64.3470 };   // sin locales cargados alrededor

// ── lo especial de cada captura. sesion: quién está logueado (por defecto el perfil).
const H = {
  // ─────────── ADMIN (desktop)
  "admin/01-ingreso": { sesion: "anon", hacer: (h) => h.esperar("Entrar") },
  "admin/02-sin-permiso": { sesion: "moderador", hacer: (h) => h.esperar("No tenés permiso") },
  "admin/03-ciudad": { hacer: async (h) => {
    // Un <select> nativo no se dibuja abierto en la captura: se muestra como lista.
    await h.p.locator("header select, select").first().evaluate((s) => {
      // Se dibuja la lista abierta al lado del selector, como la muestra el navegador.
      const r = s.getBoundingClientRect();
      const caja = document.createElement("div");
      Object.assign(caja.style, { position: "fixed", top: `${r.bottom + 2}px`, left: `${r.left}px`, width: `${r.width}px`,
        background: "#fff", color: "#111", font: "14px system-ui, sans-serif", borderRadius: "6px", zIndex: 9999,
        boxShadow: "0 12px 32px rgba(0,0,0,.55)", padding: "4px 0", maxHeight: "560px", overflow: "hidden" });
      for (const o of s.options) {
        const f = document.createElement("div");
        f.textContent = o.text;
        Object.assign(f.style, { padding: "6px 12px", background: o.selected ? "#1e66f5" : "transparent", color: o.selected ? "#fff" : (o.disabled ? "#999" : "#111") });
        caja.appendChild(f);
      }
      document.body.appendChild(caja);
    });
  } },
  "admin/04-inicio": { hacer: (h) => h.esperar("Actualizado") },
  "admin/05-inicio-graficos": { hacer: async (h) => { await h.esperar("Actualizado"); await h.ver("Altas por día"); } },
  "admin/06-negocios-lista": { hacer: (h) => h.esperar("negocios bajados") },
  "admin/07-negocios-incompletos": { hacer: async (h) => { await h.clic(/^Incompletos/); await h.ver(/^Incompletos/); } },
  "admin/08-negocios-mapa": { hacer: async (h) => { await h.esperar("negocios bajados"); await h.clic("Mapa", { exact: true }); await h.carga(); await mapaALaVista(h); } },
  "admin/09-editar-negocio": { hacer: async (h) => { await buscarNegocio(h, D.comercio_prueba.nombre); await h.titulo("Editar"); await h.esperar("Editar negocio"); } },
  "admin/10-editar-fotos": { hacer: async (h) => { await buscarNegocio(h, D.comercio_prueba.nombre); await h.titulo("Editar"); await h.ver("Fotos del local", { bloque: "start" }); } },
  "admin/11-editar-lo-que-suma": { hacer: async (h) => {
    await buscarNegocio(h, D.comercio_prueba.nombre); await h.titulo("Editar");
    await h.clic("Lo que suma", { exact: true });
    await h.ver("Lo que suma", { exact: true });
  } },
  "admin/12-generar-clave": { hacer: async (h) => {
    await buscarNegocio(h, D.comercio_clave_admin.nombre); await h.titulo("Editar");
    await h.clic("Generar clave nueva"); await h.clic("Sí, generar clave nueva"); await h.esperar("Clave nueva"); await h.ver("Clave nueva", { bloque: "center" });
  } },
  "admin/13-solo-lectura": { sesion: "revisor", hacer: async (h) => { await buscarNegocio(h, D.comercio_prueba.nombre); await h.titulo("Editar"); await h.esperar("Sólo lectura"); } },
  "admin/14-dar-de-baja": { hacer: async (h) => { await buscarNegocio(h, D.comercio_prueba.nombre); await h.p.getByRole("button", { name: "Dar de baja" }).first().hover(); } },
  "admin/15-dados-de-baja": { hacer: async (h) => { await h.clic("Dados de baja", { exact: true }); await h.esperar("dados de baja"); } },
  "admin/16-calles-horarios": { hacer: (h) => h.esperar(/sin horario/) },
  "admin/17-calles-horario-calle": { hacer: async (h) => { await h.p.getByText(/\d+ comercios?/).first().click(); await h.pausa(800); await h.ver("rubros de esta calle", { bloque: "start" }).catch(() => {}); } },
  "admin/18-calles-zonas": { hacer: async (h) => { await h.clic("Mapa", { exact: true }); await h.esperar("km recorridos"); await h.carga(); } },
  "admin/19-calles-mapa": { hacer: async (h) => { await h.clic("Mapa", { exact: true }); await h.clic("Calles", { exact: true }); await h.carga(); } },
  "admin/20-calles-ficha": { hacer: async (h) => { await h.clic("Mapa", { exact: true }); await h.clic("Calles", { exact: true }); await h.carga(); await clicCalleDelMapa(h); await h.ver("Cobertura", { bloque: "center" }); } },
  "admin/21-lugares": { hacer: async (h) => { await h.clic("Galería Comercial Central"); await h.clic("Dibujar manzana").catch(() => {}); await h.carga(); } },
  "admin/22-importados": { hacer: async (h) => { await h.clic("Sin revisar").catch(() => {}); await h.carga(); } },
  "admin/23-adornos": { hacer: async (h) => { await h.clic("Lapacho").catch(() => {}); await h.carga(); await clicMarcador(h); } },
  "admin/24-cambio-numero": { hacer: (h) => h.esperar("Aprobar") },
  "admin/25-publicaciones-pendientes": { hacer: (h) => h.esperar("Cola de aprobación") },
  "admin/26-publicaciones-ia": { hacer: async (h) => { await h.esperar("Cola de aprobación"); await h.ver(/IA sugiere/, { bloque: "center" }); } },
  "admin/27-publicaciones-bajar": { hacer: async (h) => { await h.clic(/^Publicadas/); await h.clic("Bajar", { exact: true }); await h.esperar("Motivo de la baja"); } },
  "admin/28-recepcion": { hacer: (h) => h.esperar(/Para mirar/) },
  "admin/29-difusion": { hacer: (h) => h.esperar("Difusión a las redes") },
  "admin/30-reclamos": { hacer: async (h) => { await h.clic("Responder"); await h.esperar("Enviar"); } },
  "admin/31-catalogo": { hacer: async (h) => { await h.clic(/Ver sólo los vacíos/); } },
  "admin/32-rubros": { hacer: async (h) => { await h.clic("Resolver", { exact: true }); await h.esperar("Es un rubro nuevo"); } },
  "admin/33-revision-rubros": { hacer: async (h) => { await h.clic(/^No cierran/).catch(() => {}); await h.esperar("Editar los rubros", 60000); } },
  "admin/34-editar-rubros": { hacer: async (h) => { await h.clic(/^No cierran/).catch(() => {}); await h.esperar("Editar los rubros", 60000); await h.clic("Editar los rubros"); await h.esperar("Va a quedar así"); } },
  "admin/35-cargas-historial": { hacer: (h) => h.esperar("Historial") },
  "admin/36-cargas-dia": { hacer: async (h) => { await h.esperar("Historial"); await h.ver("Historial"); await h.p.locator("table tbody tr").first().click(); await h.pausa(1200); await h.carga(); await h.ver("El día", { exact: true }).catch(() => {}); } },
  "admin/37-planes": { hacer: (h) => h.esperar("Precio/mes") },
  "admin/38-suscripciones": { hacer: (h) => h.esperar("Interesado") },
  "admin/39-suscripciones-plan": { hacer: async (h) => { await h.clic("Plan", { exact: true }); await h.esperar("Plan del comercio"); } },
  "admin/40-suscripciones-pago": { hacer: async (h) => { await h.clic("+ Pago"); await h.esperar("Registrar pago"); } },
  "admin/41-suscripciones-confiable": { hacer: async (h) => { await h.titulo("Confiable y números autorizados"); await h.esperar("Comercio confiable"); } },
  "admin/42-pagos": { hacer: (h) => h.esperar("Confirmar 1 mes") },
  "admin/43-vencimientos": { hacer: async (h) => { await h.clic("+ Agregar"); } },
  "admin/44-monitoreo": { hacer: (h) => h.esperar("Visitas al sitio") },
  "admin/45-kpis": { hacer: async (h) => { await h.clic("Últimos 30 días").catch(() => {}); await h.esperar("Comercios activos"); } },
  "admin/46-demanda": { hacer: async (h) => { await h.clic("30 días", { exact: true }); await h.esperar("Qué busca la gente"); } },
  "admin/47-compradores": { hacer: (h) => h.esperar("Por grupo") },
  "admin/48-equipo-personas": { hacer: (h) => h.esperar("El equipo") },
  "admin/49-equipo-roles": { hacer: async (h) => { await h.clic("Roles y permisos"); } },
  "admin/50-manuales": { hacer: (h) => h.esperar("Manual del agente") },
  "admin/51-ayuda": { hacer: async (h) => { await h.clic("Preguntas y saber local").catch(() => {}); await h.esperar("Sin respuesta"); } },
  "admin/52-contenido": { sesion: "publicador", hacer: (h) => h.esperar("Novedades de URUKU") },
  "admin/53-contenido-novedad": { sesion: "publicador", hacer: async (h) => { await h.ver("Feria de primavera"); await editarNovedad(h, "Feria de primavera"); await h.esperar("Guardar cambios"); } },

  // ─────────── VENDEDOR (mobile)
  "vendedor/01-ingreso": { sesion: "anon", hacer: (h) => h.esperar("Entrar") },
  "vendedor/02-ingreso-whatsapp": { sesion: "anon", hacer: async (h) => {
    await h.clic(/Primera vez o te olvidaste la clave/); await h.llenar(/celular/i, D.comercio_prueba.whatsapp);
    await h.clic("Continuar"); await h.esperar("Confirmar por WhatsApp");
  } },
  "vendedor/03-clave-nueva": { sesion: "anon", geo: LEJOS, hacer: altaAutoregistro },
  "vendedor/04-mi-negocio": { hacer: (h) => h.esperar("Mi negocio") },
  "vendedor/05-aviso-pago": { hacer: (h) => h.esperar("Pagar ahora") },
  "vendedor/06-tu-clave": { hacer: async (h) => { await h.ver("Tu clave", { exact: true }); await h.clic("Generar clave nueva"); await h.esperar("Sí, generar clave nueva"); await h.ver("Sí, generar clave nueva", { bloque: "center" }); } },
  "vendedor/07-editar-informacion": { hacer: async (h) => { await h.clic("Editar información"); await h.carga(); } },
  "vendedor/08-lo-que-suma": { hacer: async (h) => { await h.clic("Editar información"); await h.ver(/lo que suma a tu negocio/i); } },
  "vendedor/09-cambie-de-numero": { sesion: "anon", hacer: async (h) => {
    await h.llenar(/Nombre de tu negocio/i, D.comercio_prueba.nombre); await h.clic("Buscar", { exact: true });
    await h.clic(D.comercio_prueba.nombre, { n: 0 }); await h.esperar(/Tu WhatsApp nuevo/i);
  } },
  "vendedor/10-fotos-videos": { hacer: async (h) => { await menu(h, "Fotos y videos"); await h.carga(); } },
  "vendedor/11-tope-fotos": { antes: galeriaLlena, hacer: async (h) => { await menu(h, "Fotos y videos"); await h.carga(); await h.archivo("+ Foto"); await h.esperar("Llegaste al tope de fotos"); } },
  "vendedor/12-mis-ofertas": { hacer: async (h) => { await menu(h, "Mis ofertas"); await h.carga(); } },
  "vendedor/13-editar-publicacion": { hacer: async (h) => { await menu(h, "Mis ofertas"); await h.clic("Editar", { exact: true }); await h.esperar("Editar publicación"); } },
  "vendedor/14-asistente": { hacer: (h) => h.esperar("Una oferta") },
  "vendedor/15-asistente-confirmar": { hacer: asistenteOferta },
  "vendedor/16-contactos": { hacer: async (h) => { await menu(h, "Contactos"); await h.carga(); } },
  "vendedor/17-estadisticas": { hacer: async (h) => { await menu(h, "Estadísticas"); await h.carga(); } },
  "vendedor/18-mensajes-chatbot": { hacer: async (h) => { await menu(h, "Mensajes"); await h.carga(); } },
  "vendedor/19-suscripcion": { hacer: async (h) => { await h.clic("Ver planes"); await h.carga(); } },
  "vendedor/20-ficha-publica": { sesion: "anon" },

  // ─────────── COMPRADOR (mobile)
  "comprador/01-ciudad": { sesion: "anon", hacer: async (h) => { await h.p.getByRole("button", { name: /Bermejo/ }).first().click(); await h.pausa(800); } },
  "comprador/02-inicio": { sesion: "anon" },
  "comprador/03-inicio-servicios": { sesion: "anon", hacer: (h) => h.ver("Servicios útiles") },
  "comprador/04-buscar-resultados": { sesion: "anon", hacer: (h) => h.esperar(/resultado/) },
  "comprador/05-buscar-servicio": { sesion: "anon" },
  "comprador/06-cerca-de-mi": { sesion: "anon", sinGeo: true },
  "comprador/06b-cerca-de-mi-lista": { sesion: "anon", hacer: async (h) => { await h.p.waitForSelector(".uk-res-grid article", { timeout: 30000 }); await h.carga(); } },
  "comprador/07-mapa": { sesion: "anon", hacer: async (h) => { await h.carga(); await clicMarcador(h); } },
  "comprador/08-ficha": { sesion: "anon" },
  "comprador/09-ficha-fotos": { sesion: "anon", hacer: (h) => h.ver("Fotos del local") },
  "comprador/10-ficha-oferta": { sesion: "anon", hacer: async (h) => {
    await h.ver("Fotos del local"); await h.clic(/^Ofertas \(\d+\)/); await h.pausa(600);
    await h.p.getByRole("button", { name: /Jeans tiro alto/ }).or(h.p.getByAltText(/Jeans tiro alto/)).first().click(); await h.pausa(1200);
  } },
  "comprador/11-ficha-informacion": { sesion: "anon", hacer: (h) => h.ver("Información del negocio") },
  "comprador/12-dato-incorrecto": { sesion: "anon" },
  "comprador/13-preguntame": { sesion: "anon", hacer: async (h) => { await h.clic("Preguntame"); await h.esperar(/Soy Dax/); } },
  "comprador/14-chatbot-local": { sesion: "anon", hacer: async (h) => { await h.clic("Preguntame"); await h.esperar(/Preguntale a/); } },
  "comprador/15-reservas": { sesion: "anon", hacer: async (h) => {
    await h.ir(`/comercios/${D.comercio_prueba.slug}`);
    await h.ver("Fotos del local"); await h.clic(/^Ofertas \(\d+\)/);
    await h.p.getByRole("button", { name: /Jeans tiro alto/ }).or(h.p.getByAltText(/Jeans tiro alto/)).first().click(); await h.pausa(800);
    await h.clic("Reservar", { exact: true }); await h.ir("/reservas"); await h.esperar("Tu reserva");
  } },
  "comprador/16-ofertas": { sesion: "anon" },
  "comprador/17-novedades": { sesion: "anon" },
  "comprador/18-novedad-uruku": { sesion: "anon" },
  "comprador/19-turno-inicio": { sesion: "anon", hacer: (h) => h.ver(/Farmacias de turno hoy/, { bloque: "center" }) },
  "comprador/20-farmacias-turno": { sesion: "anon" },
  "comprador/21-guia": { sesion: "anon", hacer: async (h) => { await h.p.locator("summary, button[aria-expanded]").first().click().catch(() => {}); await h.pausa(600); await h.arriba(); } },
  "comprador/22-cambio": { sesion: "anon", hacer: async (h) => { const i = h.p.locator("input[inputmode=decimal], input[type=number]").first(); await i.fill("100"); await h.pausa(600); await i.evaluate((e) => e.scrollIntoView({ block: "start" })); } },
  "comprador/23-entrar": { sesion: "anon", hacer: async (h) => {
    await h.clic(/Primera vez o te olvidaste la clave/); await h.llenar(/celular/i, "70000000");
    await h.clic("Continuar"); await h.esperar("Confirmar por WhatsApp");
  } },
  "comprador/24-perfil": { sesion: "comprador", hacer: (h) => h.esperar("Cerrar sesión") },
  "comprador/25-guardados": { sesion: "comprador", hacer: (h) => h.esperar(/guardados/i) },
  "comprador/26-te-contesto": { sesion: "anon", antes: async (ctx) => {
    await ctx.addInitScript(([id, cid]) => {
      if (!localStorage.getItem("uk-contactos-pendientes")) {
        localStorage.setItem("uk-contactos-pendientes", JSON.stringify([{ id, comercioId: cid, nombre: "Boutique Ejemplo", en: Date.now() - 5 * 60 * 1000 }]));
      }
    }, [D.lead_demo_id, D.comercio_prueba.id]);
  }, hacer: (h) => h.esperar(/Te contestó/) },

  // ─────────── AGENTE (mobile)
  "agente/01-login": { sesion: "anon", hacer: (h) => h.esperar("Entrar") },
  "agente/02-que-hay-aca": { hacer: (h) => h.esperar(/Cargados a menos de/) },
  "agente/03-ficha-local": { hacer: async (h) => { await abrirFichaCercana(h); } },
  "agente/04-ubicacion-aproximada": { geo: D.farmacia_aproximada && { latitude: D.farmacia_aproximada.lat, longitude: D.farmacia_aproximada.lng }, hacer: async (h) => {
    await h.esperar(/Cargados a menos de/);
    await h.p.locator(`[aria-label="Abrir la ficha de ${D.farmacia_aproximada.nombre}"], [title="Abrir la ficha de ${D.farmacia_aproximada.nombre}"]`).first().click().catch(() => h.clic(D.farmacia_aproximada.nombre));
    await h.pausa(800); await h.clic("Tomar el GPS acá"); await h.esperar("Sí, estoy en la puerta"); await h.ver("Sí, estoy en la puerta", { bloque: "center" });
  } },
  "agente/05-mapa-calles": { hacer: async (h) => { await h.esperar(/Cargados a menos de/); await interruptorCalles(h); await h.esperar("km recorridos"); } },
  "agente/06-ficha-calle": { hacer: async (h) => {
    await h.esperar(/Cargados a menos de/); await interruptorCalles(h);
    await h.p.locator('[aria-label^="Ver la calle"], [title^="Ver la calle"]').first().click(); await h.pausa(800); await h.esperar("Cobertura"); await h.ver("Cobertura", { bloque: "center" });
  } },
  "agente/07-alta-formulario": { geo: LEJOS, hacer: async (h) => { await h.clic("Cargar un local nuevo acá"); await h.esperar("Guardar comercio"); } },
  "agente/08-ya-cargados-cerca": { geo: "comercio", hacer: async (h) => { await h.clic("Cargar un local nuevo acá"); await h.esperar("Ya cargados acá cerca"); } },
  "agente/09-alta-guardada": { geo: LEJOS, hacer: async (h) => {
    await h.clic("Cargar un local nuevo acá");
    await h.llenar(/Nombre del cartel/i, `Demo ${new Date().toISOString().slice(5, 16).replace(/[-T:]/g, "")}`);
    await subirFoto(h, /Foto del local/);
    await h.p.getByText(/El dueño aceptó aparecer/).first().click(); await h.pausa(400);
    await h.clic("Guardar comercio"); await h.esperar("Clave del comercio", 30000); await h.arriba();
  } },
  "agente/10-completar-le-falta": { hacer: async (h) => { await abrirFichaCercana(h, true); await h.clic("Completar", { exact: true }); await h.esperar("Completar comercio"); } },
  "agente/11-completar-fotos": { hacer: async (h) => { await abrirFichaCercana(h); await h.clic("Completar", { exact: true }); await h.p.locator("#cc-fotos").evaluate((e) => { e.scrollIntoView({ block: "start" }); window.scrollBy(0, -20); }); await h.carga(); } },
  "agente/12-tope-fotos": { antes: galeriaLlena, hacer: async (h) => { await abrirFichaCercana(h); await h.clic("Completar", { exact: true }); await h.ver("Llegaste al tope", { bloque: "center" }); } },
  "agente/13-completar-lo-que-suma": { hacer: async (h) => { await abrirFichaCercana(h); await h.clic("Completar", { exact: true }); await h.ver("Lo que suma", { exact: true }); } },
  "agente/14-ofrecer": { hacer: async (h) => { await abrirFichaCercana(h); await h.ver("Mostrale cómo se ven otros"); } },
  "agente/15-interes-anotado": { hacer: async (h) => {
    await abrirFichaCercana(h); await h.ver("Le interesa un plan"); await h.clic("Le interesa un plan").catch(() => {});
    await h.clic("Destacado", { exact: true }); await h.clic("Anotar interés"); await h.esperar(/Anotado: le interesa/); await h.ver(/Anotado: le interesa/, { bloque: "center" });
  } },
  "agente/16-comercios-mi-ciudad": { hacer: (h) => h.esperar("Comercios de mi ciudad") },
  "agente/17-sin-horario": { hacer: async (h) => { await h.clic(/^Sin horario/); await h.esperar("Cargar horario"); } },
  "agente/18-mis-comercios-mapa": { hacer: async (h) => { await h.clic("Mapa", { exact: true }); await h.carga(); } },
  "agente/19-sin-conexion": { geo: LEJOS, hacer: async (h) => {
    await h.clic("Cargar un local nuevo acá");
    await h.llenar(/Nombre del cartel/i, "Puesto sin señal (demo)");
    await h.p.getByText(/El dueño aceptó aparecer/).first().click();
    await h.ctx.setOffline(true);
    await h.clic("Guardar comercio"); await h.pausa(1500);
    await h.clic("Cargar otro comercio"); await h.esperar(/guardado sin conexión/);
    await h.arriba();
  } },
};

// ── pasos compuestos
async function mapaALaVista(h, margen = 150) {
  // Con la rueda del mouse sobre el contenido: el panel scrollea dentro de su propio contenedor.
  const r = await h.p.locator(".leaflet-container").first().boundingBox();
  if (r && r.y > margen) {
    const vp = h.p.viewportSize();
    await h.p.mouse.move(vp.width / 2, 120);
    await h.p.mouse.wheel(0, r.y - margen);
    await h.pausa(800);
  }
  await h.carga();
}
/** Una entrada del menú de Mi comercio: en el celular vive detrás del botón «Menú». */
async function menu(h, item) {
  const directo = h.p.getByRole("button", { name: item, exact: true }).or(h.p.getByRole("link", { name: item, exact: true })).filter({ visible: true });
  if (!(await directo.count())) { await h.clic("Menú", { exact: true }); }
  await h.clic(item, { exact: true });
  await h.carga();
}
async function buscarNegocio(h, nombre) {
  await h.esperar("negocios bajados");
  await h.llenar(/Buscar por nombre/, nombre);
  await h.pausa(1200);
}
async function clicCalleDelMapa(h) {
  // Un clic de verdad sobre el trazo de la calle más cerca del centro del mapa (en la mitad de su largo).
  const pt = await h.p.evaluate(() => {
    const map = document.querySelector(".leaflet-container")?.getBoundingClientRect();
    if (!map) return null;
    const cx = map.left + map.width / 2, cy = map.top + map.height / 2;
    let mejor = null;
    for (const path of document.querySelectorAll("path.leaflet-interactive")) {
      const largo = path.getTotalLength?.();
      if (!largo) continue;
      const q = path.getPointAtLength(largo / 2), m = path.getScreenCTM();
      const x = q.x * m.a + q.y * m.c + m.e, y = q.x * m.b + q.y * m.d + m.f;
      const d = Math.hypot(x - cx, y - cy);
      if (x > map.left && x < map.right && y > map.top && y < Math.min(map.bottom, innerHeight) && (!mejor || d < mejor.d)) mejor = { x, y, d };
    }
    if (mejor) return mejor;
    // Las calles se pintan en un <canvas> (crearRendererCalles): se busca el píxel pintado más cerca del centro.
    const cv = document.querySelector(".leaflet-overlay-pane canvas");
    if (!cv) return null;
    const r = cv.getBoundingClientRect(), ctx = cv.getContext("2d");
    const { data, width, height } = ctx.getImageData(0, 0, cv.width, cv.height);
    const ex = cv.width / r.width, ey = cv.height / r.height;
    const ccx = (cx - r.left) * ex, ccy = (cy - r.top) * ey;
    for (let rad = 0; rad < 300; rad += 2) {
      for (let a = 0; a < 360; a += 6) {
        const x = Math.round(ccx + rad * Math.cos(a * Math.PI / 180)), y = Math.round(ccy + rad * Math.sin(a * Math.PI / 180));
        if (x < 0 || y < 0 || x >= width || y >= height) continue;
        const i = (y * width + x) * 4;
        if (data[i + 3] > 220) {
          const sx = r.left + x / ex, sy = r.top + y / ey;
          if (sy < innerHeight - 5) return { x: sx, y: sy, d: rad };
        }
      }
    }
    return null;
  });
  if (pt) await h.p.mouse.click(pt.x, pt.y);
  await h.pausa(1200);
  return !!pt;
}
async function clicMarcador(h) {
  // El mapa a la vista y un pin que abra su globo (los grupos de pines sólo acercan).
  await h.p.locator(".leaflet-container").first().evaluate((e) => { e.scrollIntoView({ block: "start" }); window.scrollBy(0, -70); });
  await h.pausa(600);
  const m = h.p.locator(".leaflet-marker-icon").filter({ visible: true });
  const n = await m.count();
  for (let k = 0; k < Math.min(n, 8); k++) {
    await m.nth((Math.floor(n / 2) + k) % n).click({ force: true }).catch(() => {});
    await h.pausa(900);
    if (await h.p.locator(".leaflet-popup").count()) break;
  }
  await h.carga();
}
async function interruptorCalles(h) {
  await h.p.getByRole("switch", { name: /Calles/ }).or(h.p.getByRole("button", { name: /^Calles/ })).first().click();
  await h.pausa(1200); await h.carga();
}
async function abrirFichaCercana(h, incompleto = false) {
  await h.esperar(/Cargados a menos de/);
  const fichas = h.p.locator('[aria-label^="Abrir la ficha de"], [title^="Abrir la ficha de"]');
  await fichas.first().waitFor({ timeout: 15000 });
  await fichas.nth(incompleto ? Math.min(1, (await fichas.count()) - 1) : 0).click();
  await h.pausa(1000); await h.carga();
}
async function subirFoto(h, boton) {
  const input = h.p.locator('input[type=file]').first();
  await input.setInputFiles(resolve(RUN, "fotos", D.comercio_prueba.slug, "portada.jpg")).catch(async () => { await h.archivo(boton); });
  await h.pausa(1500);
}
async function editarNovedad(h, titulo) {
  const card = h.p.locator("div, li, article").filter({ hasText: titulo }).filter({ has: h.p.getByRole("button", { name: "Editar" }) }).last();
  await card.getByRole("button", { name: "Editar" }).first().click();
  await h.pausa(1000);
}
async function altaAutoregistro(h) {
  // El alta crea un comercio ficticio nuevo en la demo (y muestra su clave una sola vez).
  const sufijo = new Date().toISOString().slice(5, 16).replace(/[-T:]/g, "");
  await h.llenar("Nombre del comercio", "Almacén Doña Rosa");
  await h.llenar(/^WhatsApp/, `5917${String(Date.now()).slice(-7)}`);
  await h.llenar(/Contanos con tus palabras/, "Ropa y calzado para toda la familia");
  await h.clic("Usar mi ubicación actual"); await h.pausa(1500);
  await h.p.locator("input[type=file]").first().setInputFiles(resolve(RUN, "fotos", D.comercio_prueba.slug, "portada.jpg"));
  await h.pausa(1500);
  await h.clic(/Crear cuenta y publicar/);
  await h.esperar("Tu clave para entrar", 30000);
  await h.ver("Tu clave para entrar", { bloque: "center" });
}
async function asistenteOferta(h) {
  await h.clic("Una oferta");
  const responder = async (texto) => {
    const caja = h.p.getByPlaceholder(/Escribí tu respuesta/).or(h.p.locator("textarea, input:not([type=file]):not([type=hidden])")).filter({ visible: true }).last();
    await caja.fill(texto); await caja.press("Enter"); await h.pausa(900);
  };
  await responder("Camperas de jean");
  await responder("220");
  await responder("Talles S a XL, varios colores");
  await responder("no");
  await h.esperar(/Enviar a moderación|Publicar en vivo/);
}

// ── correr
const VIEWPORTS = {
  mobile: { viewport: { width: 390, height: 844 }, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
  desktop: { viewport: { width: 1440, height: 900 }, deviceScaleFactor: 1 },
};

async function capturar(browser, item, vp) {
  const clave = `${item.perfil}/${item.id}`;
  const esp = H[clave] || {};
  const sesion = esp.sesion || item.perfil;
  let geo = esp.geo || ACA;
  if (geo === "comercio") geo = { latitude: D.agente_aca.lat, longitude: D.agente_aca.lng };
  const ctx = await browser.newContext({
    ...VIEWPORTS[vp], locale: "es-BO", timezoneId: "America/La_Paz", colorScheme: "dark",
    storageState: await estado(sesion),
    ...(esp.sinGeo ? {} : { geolocation: geo, permissions: ["geolocation"] }),
  });
  ctx.on("page", (pg) => { if (pg.url() !== "about:blank" && !pg.url().startsWith(BASE)) pg.close().catch(() => {}); });
  await ctx.route(/^https?:\/\/(wa\.me|api\.whatsapp\.com|www\.tiktok\.com)/, (r) => r.abort());
  if (esp.antes) await esp.antes(ctx);
  const p = await ctx.newPage();
  p.on("dialog", (d) => d.dismiss().catch(() => {}));
  const h = helpers(p, ctx);
  h.ir = async (ruta) => {
    // La primera visita a una ruta la compila next dev: puede tardar; se reintenta una vez.
    try { await p.goto(BASE + ruta, { waitUntil: "domcontentloaded", timeout: 90000 }); }
    catch { await p.goto(BASE + ruta, { waitUntil: "domcontentloaded", timeout: 120000 }); }
    await esperarCarga(p);
  };
  try {
    await h.ir(resolverRuta(item.ruta));
    if (Array.isArray(item.pasos)) await pasosSimples(h, item.pasos);
    if (esp.hacer) await esp.hacer(h);
    await esperarCarga(p);
    const dir = resolve(SALIDA, item.perfil);
    mkdirSync(dir, { recursive: true });
    const archivo = resolve(dir, `${item.id}-${vp}.png`);
    await p.screenshot({ path: archivo });
    return { ok: true, archivo };
  } catch (e) {
    // Cómo quedó la pantalla cuando falló: para ver qué texto o botón no estaba.
    mkdirSync(resolve(RUN, "fallas"), { recursive: true });
    await p.screenshot({ path: resolve(RUN, "fallas", `${item.perfil}-${item.id}-${vp}.png`) }).catch(() => {});
    return { ok: false, error: e.message.split("\n")[0] };
  } finally {
    await ctx.close();
  }
}

async function pasosSimples(h, pasos) {
  for (const a of pasos) {
    if (a.clic) await h.clic(a.clic, { exact: !!a.exact });
    else if (a.titulo) await h.titulo(a.titulo);
    else if (a.ver) await h.ver(a.ver);
    else if (a.llenar) await h.llenar(a.llenar, a.valor ?? "");
    else if (a.esperar) await h.esperar(a.esperar);
    else if (a.scroll) await h.scroll(a.scroll);
    else if (a.pausa) await h.pausa(a.pausa);
  }
}

const browser = await chromium.launch();
const resultados = [];
const items = LISTA.filter((it) => !SOLO || SOLO.test(`${it.perfil}/${it.id}`));
console.log(`${items.length} capturas de ${fuente.replace(RAIZ, ".")} contra ${BASE}`);
for (const it of items) {
  const vps = it.viewport === "ambos" ? ["mobile", "desktop"] : [it.viewport || "mobile"];
  for (const vp of vps) {
    const r = await capturar(browser, it, vp);
    resultados.push({ perfil: it.perfil, id: it.id, vp, ...r });
    console.log(`${r.ok ? "✓" : "✗"} ${it.perfil}/${it.id}-${vp}${r.ok ? "" : "  " + r.error}`);
  }
}
await browser.close();

const fallas = resultados.filter((r) => !r.ok);
const porPerfil = {};
for (const r of resultados.filter((r) => r.ok)) porPerfil[r.perfil] = (porPerfil[r.perfil] || 0) + 1;
console.log(`\nListo: ${resultados.length - fallas.length}/${resultados.length} en ${SALIDA.replace(RAIZ, ".")}`);
console.log(Object.entries(porPerfil).map(([k, v]) => `  ${k}: ${v}`).join("\n"));
if (fallas.length) console.log(`Fallaron:\n${fallas.map((f) => `  ${f.perfil}/${f.id}-${f.vp}: ${f.error}`).join("\n")}`);
writeFileSync(resolve(RUN, "capturas-resultado.json"), JSON.stringify(resultados, null, 1));
process.exit(fallas.length ? 2 : 0);
