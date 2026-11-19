// La portada de diseño en la ficha pública (docs/portada-diseno.md): qué va arriba y qué queda en «Fotos del local».
import test from "node:test";
import assert from "node:assert/strict";
import { fotosDeFicha } from "../lib/portada-diseno";
import type { GaleriaFoto } from "../lib/data-pure";

const f = (id: string, url = `/f/${id}.jpg`): GaleriaFoto => ({ id, url, thumb_url: `/t/${id}.jpg` });
const base = { portada_url: "/p/original.jpg", portada_thumb_url: "/p/original-t.jpg", portada_pos: 30 };

test("sin diseño todo queda como hoy: la original arriba con su encuadre y la galería intacta", () => {
  const galeria = [f("a"), f("b")];
  const r = fotosDeFicha({ ...base, portada_diseno_url: null }, galeria);
  assert.equal(r.portada, "/p/original.jpg");
  assert.equal(r.posicion, 30);
  assert.equal(r.fotos, galeria, "es la misma lista, sin tocarla");
  assert.deepEqual(fotosDeFicha(base, galeria), r, "campo ausente = null");
  assert.equal(fotosDeFicha({ ...base, portada_diseno_url: "  " }, galeria).portada, "/p/original.jpg", "vacío no cuenta");
});

test("sin diseño y sin portada: arriba no hay portada (FichaGaleria usa la primera de la galería)", () => {
  const r = fotosDeFicha({ portada_url: null }, [f("a")]);
  assert.equal(r.portada, null);
  assert.equal(r.posicion, null);
  assert.deepEqual(r.fotos.map((x) => x.id), ["a"]);
});

test("con diseño: va de principal, sin encuadre, y la original es la PRIMERA de la galería", () => {
  const r = fotosDeFicha({ ...base, portada_diseno_url: "/d/diseno.jpg" }, [f("a"), f("b")]);
  assert.equal(r.portada, "/d/diseno.jpg");
  assert.equal(r.posicion, null, "el diseño ya viene encuadrado");
  assert.deepEqual(r.fotos.map((x) => x.url), ["/p/original.jpg", "/f/a.jpg", "/f/b.jpg"]);
  assert.equal(r.fotos[0].thumb_url, "/p/original-t.jpg");
});

test("con diseño y la original ya en la galería: se mueve al frente, no se duplica", () => {
  const r = fotosDeFicha({ ...base, portada_diseno_url: "/d/diseno.jpg" }, [f("a"), f("o", "/p/original.jpg"), f("b")]);
  assert.deepEqual(r.fotos.map((x) => x.id), ["o", "a", "b"]);
  assert.equal(r.fotos.filter((x) => x.url === "/p/original.jpg").length, 1);
});

test("con diseño y la original ya primera: queda igual", () => {
  const r = fotosDeFicha({ ...base, portada_diseno_url: "/d/diseno.jpg" }, [f("o", "/p/original.jpg"), f("a")]);
  assert.deepEqual(r.fotos.map((x) => x.id), ["o", "a"]);
});

test("con diseño y galería vacía: la original es la única foto de abajo", () => {
  const r = fotosDeFicha({ ...base, portada_diseno_url: "/d/diseno.jpg" }, []);
  assert.deepEqual(r.fotos.map((x) => x.url), ["/p/original.jpg"]);
});

test("no muta la galería que recibe", () => {
  const galeria = [f("a")];
  fotosDeFicha({ ...base, portada_diseno_url: "/d/diseno.jpg" }, galeria);
  assert.equal(galeria.length, 1);
});

test("diseño sin foto original (no debería pasar): se muestra el diseño y la galería sigue igual", () => {
  const galeria = [f("a")];
  const r = fotosDeFicha({ portada_url: null, portada_diseno_url: "/d/diseno.jpg" }, galeria);
  assert.equal(r.portada, "/d/diseno.jpg");
  assert.equal(r.fotos, galeria);
});
