// El carrusel de productos y los productos frecuentes (lib/home-productos-pure.ts).
import test from "node:test";
import assert from "node:assert/strict";
import {
  MIN_PRODUCTOS_CARGADOS, precioDeProducto, productosDelLocal, productosFrecuentes, tarjetasDeLocales, tarjetasDeProductos,
  type FilaProducto, type LocalConProductos,
} from "../lib/home-productos-pure";

const fila = (n: number, extra: Partial<FilaProducto> = {}): FilaProducto => ({
  id: `p${n}`, nombre: `Producto ${n}`, precio: 100 + n, moneda: "BOB", foto_url: `https://x/p${n}.jpg`,
  comercio: { slug: `local-${n}`, nombre: `Local ${n}` }, ...extra,
});
const local = (n: number, obs: string | null, ia: string | null = null, foto: string | null = `https://x/l${n}.jpg`): LocalConProductos => ({
  id: `c${n}`, slug: `local-${n}`, nombre: `Local ${n}`, portada_thumb_url: foto, prod_obs_human: obs, prod_det_ia: ia,
});

test("precioDeProducto: sólo si está cargado", () => {
  assert.equal(precioDeProducto(120, "BOB"), "Bs 120");
  assert.equal(precioDeProducto("12.5", "BOB"), "Bs 12,50");
  assert.equal(precioDeProducto(15, "USD"), "USD 15");
  assert.equal(precioDeProducto(null, "BOB"), null);
  assert.equal(precioDeProducto(0, "BOB"), null);
  assert.equal(precioDeProducto("abc", "BOB"), null);
});

test("con 4 o más productos con foto, la tarjeta lleva foto, nombre, precio (si hay), comercio y enlace a la ficha", () => {
  const t = tarjetasDeProductos([fila(1), fila(2, { precio: null }), fila(3), fila(4)]);
  assert.equal(t.length, 4);
  assert.deepEqual(t[0], { id: "p1", href: "/comercios/local-1#ficha-encontrar", foto: "https://x/p1.jpg", titulo: "Producto 1", precio: "Bs 101", comercio: "Local 1" });
  assert.equal(t[1].precio, null);
});

test("con menos de 4 productos útiles (o sin foto), no se usa la tabla: hay respaldo", () => {
  assert.equal(MIN_PRODUCTOS_CARGADOS, 4);
  assert.deepEqual(tarjetasDeProductos([fila(1), fila(2), fila(3)]), []);
  assert.deepEqual(tarjetasDeProductos([fila(1), fila(2), fila(3), fila(4, { foto_url: null })]), []);
  assert.deepEqual(tarjetasDeProductos([fila(1), fila(2), fila(3), fila(4, { comercio: null })]), []);
});

test("hasta 12 tarjetas de la tabla, en el orden que vienen (los más nuevos primero)", () => {
  const t = tarjetasDeProductos(Array.from({ length: 20 }, (_, i) => fila(i + 1)));
  assert.equal(t.length, 12);
  assert.equal(t[0].id, "p1");
});

test("productosDelLocal: los primeros productos; lo que leyó la IA antes que lo que escribió el comerciante (sin moderar)", () => {
  assert.deepEqual(productosDelLocal(local(1, "Zapatillas, botines", "Sandalias, medias")), ["Sandalias", "medias", "Zapatillas"]);
  assert.deepEqual(productosDelLocal(local(1, null, "Celulares; cargadores")), ["Celulares", "cargadores"]);
  assert.deepEqual(productosDelLocal(local(1, null, null)), []);
});

test("respaldo: sólo locales con foto y productos, con los 2-3 primeros y el nombre del comercio", () => {
  const sinAzar = () => 0.999; // Fisher-Yates con este valor deja el orden como está
  const t = tarjetasDeLocales([
    local(1, "Zapatillas, botines, sandalias, medias"),
    local(2, "Celulares", null, null),        // sin foto: no
    local(3, null, null),                      // sin productos: no
    local(4, null, "Cargadores, fundas"),
  ], sinAzar);
  assert.deepEqual(t.map((x) => x.id), ["c1", "c4"]);
  assert.equal(t[0].titulo, "Zapatillas, botines, sandalias");
  assert.equal(t[0].comercio, "Local 1");
  assert.equal(t[0].href, "/comercios/local-1#ficha-encontrar");
  assert.equal(t[0].precio, null);
});

test("respaldo: hasta 12, mezclados (cambia el orden con otro azar y no se repite ninguno)", () => {
  const locales = Array.from({ length: 30 }, (_, i) => local(i + 1, "Ropa"));
  const a = tarjetasDeLocales(locales, () => 0.999);
  const b = tarjetasDeLocales(locales, () => 0);
  assert.equal(a.length, 12);
  assert.equal(b.length, 12);
  assert.notDeepEqual(a.map((x) => x.id), b.map((x) => x.id));
  assert.equal(new Set(b.map((x) => x.id)).size, 12);
});

test("sin ninguna de las dos cosas, no hay tarjetas (el carrusel no aparece)", () => {
  assert.deepEqual(tarjetasDeLocales([local(1, null, null), local(2, "Ropa", null, null)]), []);
  assert.deepEqual(tarjetasDeLocales([]), []);
});

test("productosFrecuentes: los más repetidos, en minúscula, sin repetir y con empates por orden alfabético (ver también el filtro de seguridad)", () => {
  const f = productosFrecuentes([
    { prod_obs_human: "Zapatillas, Ropa", prod_det_ia: "zapatillas" },   // un local cuenta una sola vez por producto
    { prod_obs_human: "ZAPATILLAS, Celulares", prod_det_ia: null },
    { prod_obs_human: "Ropa", prod_det_ia: "Cargadores" },
    { prod_obs_human: "Zapatillas", prod_det_ia: null },
  ]);
  assert.deepEqual(f.slice(0, 2), ["zapatillas", "ropa"]);
  assert.ok(f.includes("cargadores"), "lo que detectó la IA se conserva aunque sea de un solo local");
  assert.ok(!f.includes("celulares"), "un texto del comerciante en UN solo local no llega a la portada");
  assert.equal(new Set(f).size, f.length);
  for (const p of f) assert.equal(p, p.toLowerCase());
});

test("productosFrecuentes: hasta 12 y sin frases largas", () => {
  const muchos = Array.from({ length: 40 }, (_, i) => ({ prod_obs_human: null, prod_det_ia: `producto${String.fromCharCode(97 + (i % 26))}${i}` }));
  assert.equal(productosFrecuentes(muchos).length, 12);
  assert.deepEqual(productosFrecuentes([{ prod_obs_human: null, prod_det_ia: "Venta de todo tipo de artículos para el hogar y la oficina" }]), []);
  assert.deepEqual(productosFrecuentes([]), []);
});
