// Tests de los textos de la ficha (tareas FA/FH, docs/visibilidad-buscadores-ia.md §3.5).
import test from "node:test";
import assert from "node:assert/strict";
import {
  cortarEnPalabra, descripcionFicha, productosDeFicha, queEsElComercio, tituloFicha,
} from "../lib/ficha-seo";

test("productosDeFicha: lo humano primero, sin repetidos (tildes y mayúsculas), tope", () => {
  const r = productosDeFicha("Frazada, almohada; Cobertor", "ALMOHADA, acolchado · frazadá");
  assert.deepEqual(r, ["Frazada", "almohada", "Cobertor", "acolchado"]);
  const muchos = Array.from({ length: 40 }, (_, i) => `producto ${i}`).join(", ");
  assert.equal(productosDeFicha(muchos, null).length, 20);
  assert.deepEqual(productosDeFicha(null, "  "), [], "sin datos, sin sección");
  assert.deepEqual(productosDeFicha("a, x", null), [], "una letra no es un producto");
});

test("queEsElComercio: subcategoría o rubro; nunca «otros»; no repite lo que ya dice el nombre", () => {
  const c = { nombre: "Galería Cortez", rubro_slug: "blanqueria", rubro_nombre: "🛏️ Blanquería" };
  assert.equal(queEsElComercio(c), "Blanquería");
  assert.equal(queEsElComercio({ ...c, subcategoria: "Frazadas" }), "Frazadas");
  assert.equal(queEsElComercio({ nombre: "Otros (a clasificar)", rubro_slug: "otros", rubro_nombre: "Otros (a clasificar)" }), "");
  assert.equal(queEsElComercio({ nombre: "Farmacia Ángeles", rubro_slug: "farmacia", rubro_nombre: "Farmacia" }), "", "el nombre ya lo dice");
  assert.equal(queEsElComercio({ nombre: "Ángeles", rubro_slug: "farmacia", rubro_nombre: "💊 Farmacias" }), "Farmacias");
});

test("tituloFicha: la marca una sola vez", () => {
  assert.equal(tituloFicha("Óptica Sol ", "Óptica", "La Paz"), "Óptica Sol — Óptica en La Paz | URUKU");
  assert.equal(tituloFicha("Kiosco 3", "", "Bermejo"), "Kiosco 3 en Bermejo | URUKU");
  assert.equal(tituloFicha("X", "Y", "Z").match(/URUKU/g)?.length, 1);
});

test("cortarEnPalabra: corta en palabra y respeta el tope", () => {
  const t = "Vendemos frazadas, almohadas, cobertores y toda clase de textiles para el hogar y la familia entera";
  const c = cortarEnPalabra(t, 40);
  assert.ok(c.length <= 41 && c.endsWith("…"), c);
  assert.ok(!/\s…$/.test(c));
  assert.equal(cortarEnPalabra("Corto", 40), "Corto");
});

test("descripcionFicha: tres casos de §3.5", () => {
  const base = { nombre: "Galería Cortez", que: "Blanquería", ciudad: "Bermejo", departamento: "Tarija" };
  const conDesc = descripcionFicha({ ...base, descripcion: "Blanquería y textiles para el hogar", calle: "Avenida Petrolera" });
  assert.equal(conDesc, "Blanquería y textiles para el hogar. En Avenida Petrolera, Bermejo.");
  assert.ok(conDesc.length < 200);
  assert.equal(descripcionFicha({ ...base, productos: ["frazada", "almohada"] }), "Galería Cortez en Bermejo: vende frazada, almohada.");
  assert.equal(descripcionFicha(base), "Galería Cortez, Blanquería en Bermejo (Tarija). Ubicación en el mapa y cómo llegar.");
  assert.ok(!/WhatsApp/.test(conDesc), "sin WhatsApp cargado no se nombra");
  assert.ok(/WhatsApp/.test(descripcionFicha({ ...base, conWhatsapp: true })));
});
