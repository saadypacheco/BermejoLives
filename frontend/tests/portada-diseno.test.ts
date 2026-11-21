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

// ---- Galería con diseño (docs/fotos-estilo-uruku.md §3) ----

const fd = (id: string, url = `/f/${id}.jpg`): GaleriaFoto => ({
  id, url, thumb_url: `/t/${id}.jpg`, diseno_url: `/d/${id}.jpg`, diseno_thumb_url: `/d/${id}-t.jpg`,
});

test("galería con diseño: la grilla usa la miniatura de diseño y la ampliada el diseño", () => {
  const r = fotosDeFicha({ ...base, portada_diseno_url: null }, [f("a"), fd("b")]);
  assert.deepEqual(r.fotos.map((x) => x.url), ["/f/a.jpg", "/d/b.jpg"]);
  assert.deepEqual(r.fotos.map((x) => x.thumb_url), ["/t/a.jpg", "/d/b-t.jpg"]);
  assert.deepEqual(r.fotos.map((x) => x.id), ["a", "b"]);
});

test("galería con diseño sin miniatura de diseño: la grilla usa el diseño, nunca la miniatura de la foto real", () => {
  const sinThumb: GaleriaFoto = { id: "b", url: "/f/b.jpg", thumb_url: "/t/b.jpg", diseno_url: "/d/b.jpg", diseno_thumb_url: null };
  const r = fotosDeFicha(base, [sinThumb]);
  assert.equal(r.fotos[0].url, "/d/b.jpg");
  assert.equal(r.fotos[0].thumb_url, null, "el grid cae a `url`, que es el diseño");
});

test("galería: diseño vacío o en blanco cuenta como sin diseño", () => {
  const raro: GaleriaFoto = { id: "b", url: "/f/b.jpg", thumb_url: "/t/b.jpg", diseno_url: "  ", diseno_thumb_url: "/x.jpg" };
  const galeria = [raro];
  const r = fotosDeFicha(base, galeria);
  assert.equal(r.fotos, galeria, "sin diseños la lista es la misma");
  assert.equal(r.fotos[0].url, "/f/b.jpg");
});

test("galería con diseño no muta la lista que recibe", () => {
  const original = fd("a");
  const galeria = [original];
  fotosDeFicha(base, galeria);
  assert.equal(original.url, "/f/a.jpg");
  assert.equal(galeria[0], original);
});

test("portada con diseño y la original en la galería CON diseño propio: se busca por la url real, va primera y no se duplica", () => {
  const galeria = [f("a"), fd("o", "/p/original.jpg"), f("b")];
  const r = fotosDeFicha({ ...base, portada_diseno_url: "/d/portada.jpg" }, galeria);
  assert.equal(r.portada, "/d/portada.jpg");
  assert.deepEqual(r.fotos.map((x) => x.id), ["o", "a", "b"]);
  assert.equal(r.fotos.length, 3);
  assert.equal(r.fotos[0].url, "/d/o.jpg", "la galería muestra su versión con diseño");
  assert.equal(r.fotos.filter((x) => x.id === "o").length, 1);
  assert.equal(r.fotos.some((x) => x.id === "portada-original"), false, "la portada original no entra otra vez como foto aparte");
});

test("portada con diseño y la original fuera de la galería, que sí tiene diseños: la original va primera, sin diseño", () => {
  const r = fotosDeFicha({ ...base, portada_diseno_url: "/d/portada.jpg" }, [fd("a"), f("b")]);
  assert.deepEqual(r.fotos.map((x) => x.id), ["portada-original", "a", "b"]);
  assert.equal(r.fotos[0].url, "/p/original.jpg");
  assert.equal(r.fotos[1].url, "/d/a.jpg");
});

test("sin portada de diseño y con la original en la galería con diseño: arriba la original, abajo su diseño", () => {
  const r = fotosDeFicha(base, [fd("o", "/p/original.jpg")]);
  assert.equal(r.portada, "/p/original.jpg");
  assert.equal(r.posicion, 30);
  assert.equal(r.fotos[0].url, "/d/o.jpg");
});
