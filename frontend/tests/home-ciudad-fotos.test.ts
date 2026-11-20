// Las fotos de los carruseles (docs/home-ciudades.md §11): la versión «tarjeta», el respaldo y el orden con la calidad.
import test from "node:test";
import assert from "node:assert/strict";
import {
  candidatosCarrusel, fotoDeTarjeta, ordenarCarrusel, prepararCarrusel, type ComercioCarrusel, type ComercioDeLaCiudad,
} from "../lib/home-ciudad-pure";

const com = (id: string, rubro: string, extra: Partial<ComercioDeLaCiudad> = {}): ComercioDeLaCiudad => ({
  id, slug: id, nombre: id, portada_thumb_url: `https://x/${id}-t.jpg`, portada_pos: 30, rubro_slug: rubro, rubro_nombre: rubro,
  horario: "Lun a Dom 8-22", lat: -21.53, lng: -64.73, prod_obs_human: null, prod_det_ia: null, ...extra,
});
const COMERCIALES = new Set(["cafeteria", "panaderia", "calzado"]);

test("fotoDeTarjeta: tarjeta → miniatura; sin ninguna, null", () => {
  const todo = { portada_card_url: "c.jpg", portada_thumb_url: "t.jpg" };
  assert.deepEqual(fotoDeTarjeta(todo), { url: "c.jpg", recortada: true });
  assert.deepEqual(fotoDeTarjeta({ ...todo, portada_card_url: null }), { url: "t.jpg", recortada: false });
  assert.deepEqual(fotoDeTarjeta({ ...todo, portada_card_url: "  " }), { url: "t.jpg", recortada: false });
  assert.deepEqual(fotoDeTarjeta({ portada_thumb_url: "t.jpg" }), { url: "t.jpg", recortada: false });
  assert.equal(fotoDeTarjeta({ portada_thumb_url: null }), null);
  assert.equal(fotoDeTarjeta({ portada_card_url: undefined, portada_thumb_url: "" }), null);
});

test("la portada de diseño (lleva el nombre impreso) NUNCA va en los carruseles, aunque venga en la fila", () => {
  const fila = { portada_card_url: null, portada_diseno_url: "https://x/d.jpg", portada_thumb_url: "https://x/t.jpg" };
  assert.deepEqual(fotoDeTarjeta(fila), { url: "https://x/t.jpg", recortada: false });
  assert.deepEqual(fotoDeTarjeta({ ...fila, portada_card_url: "https://x/c.jpg" }), { url: "https://x/c.jpg", recortada: true });
  assert.equal(fotoDeTarjeta({ ...fila, portada_thumb_url: null }), null, "sin tarjeta ni miniatura no hay foto: el diseño no la reemplaza");
});

test("antes de la migración 0202 (sin las columnas nuevas) todo sigue andando con la miniatura y su encuadre", () => {
  const r = candidatosCarrusel([com("a", "cafeteria")], "manana", "Tarija", COMERCIALES);
  assert.equal(r.items.length, 1);
  assert.equal(r.items[0].foto, "https://x/a-t.jpg");
  assert.equal(r.items[0].fotoPos, 30, "la miniatura sí lleva object-position");
  assert.equal(r.items[0].calidad, null);
});

test("con la foto de tarjeta (ya recortada 4:3) no se aplica el encuadre y viaja la calidad", () => {
  const r = candidatosCarrusel([com("a", "cafeteria", { portada_card_url: "https://x/a-card.jpg", portada_calidad: 72 })], "manana", "Tarija", COMERCIALES);
  assert.equal(r.items[0].foto, "https://x/a-card.jpg");
  assert.equal(r.items[0].fotoPos, null);
  assert.equal(r.items[0].calidad, 72);
});

test("un comercio con tarjeta pero sin miniatura igual puede salir (tiene foto)", () => {
  const r = candidatosCarrusel([com("a", "cafeteria", { portada_thumb_url: null, portada_card_url: "https://x/c.jpg" })], "manana", "Tarija", COMERCIALES);
  assert.deepEqual(r.items.map((i) => i.id), ["a"]);
});

const cand = (id: string, extra: Partial<ComercioCarrusel> = {}): ComercioCarrusel => ({
  id, slug: id, nombre: id, foto: "https://x/f.jpg", fotoPos: null, rubro: "cafeteria", rubroNombre: "Cafetería",
  horario: "Lun a Dom 8-22", horarioEstimado: false, lat: -21.53, lng: -64.73, estrella: false, plan_orden: 0, ...extra,
});
// Miércoles a las 14:00 de Bolivia (el Date ya trae esas horas).
const AHORA = new Date(2026, 10, 18, 14, 0);
const YO = { lat: -21.5300, lng: -64.7300 };

test("orden: abiertos → estrella → calidad (mayor primero) → distancia sólo con «Más cerca»", () => {
  const lista = [
    cand("cerrado-calidad", { horario: "Lun a Dom 16-20", calidad: 99 }),
    cand("abierto-sin-puntaje", { lat: -21.5301 }),
    cand("abierto-calidad-50", { calidad: 50, lat: -21.60 }),
    cand("abierto-calidad-90", { calidad: 90, lat: -21.70 }),
    cand("estrella-calidad-10", { calidad: 10, estrella: true, plan_orden: 1 }),
  ];
  const sinCerca = prepararCarrusel(lista, { abiertos: false, cerca: false, ubicacion: YO, ahora: AHORA });
  assert.deepEqual(sinCerca.map((c) => c.id), ["estrella-calidad-10", "abierto-calidad-90", "abierto-calidad-50", "abierto-sin-puntaje", "cerrado-calidad"]);
});

test("orden: la calidad manda sobre la distancia; la distancia desempata (sólo con «Más cerca»)", () => {
  const lista = [
    cand("lejos-bueno", { calidad: 80, lat: -21.70 }),
    cand("cerca-igual-a", { calidad: 60, lat: -21.5302 }),
    cand("cerca-igual-b", { calidad: 60, lat: -21.5400 }),
    cand("cerca-igual-c", { calidad: 60, lat: -21.5301 }),
  ];
  const conCerca = prepararCarrusel(lista, { abiertos: false, cerca: true, ubicacion: YO, ahora: AHORA });
  assert.deepEqual(conCerca.map((c) => c.id), ["lejos-bueno", "cerca-igual-c", "cerca-igual-a", "cerca-igual-b"]);
  // Sin «Más cerca», empatados por calidad se queda el orden de entrada (no se ordena por distancia).
  const sinCerca = prepararCarrusel(lista, { abiertos: false, cerca: false, ubicacion: YO, ahora: AHORA });
  assert.deepEqual(sinCerca.map((c) => c.id), ["lejos-bueno", "cerca-igual-a", "cerca-igual-b", "cerca-igual-c"]);
  assert.ok(sinCerca.every((c) => c.metros === null));
});

test("orden: sin puntaje va al final de su grupo; el plan estrella más caro va primero", () => {
  const lista = [cand("sin"), cand("bajo", { calidad: 5 }), cand("e1", { estrella: true, plan_orden: 1 }), cand("e2", { estrella: true, plan_orden: 2 })];
  assert.deepEqual(ordenarCarrusel(lista, null, AHORA).map((c) => c.id), ["e2", "e1", "bajo", "sin"]);
});

test("el orden no toca la lista de entrada ni pierde elementos", () => {
  const lista = [cand("a", { calidad: 1 }), cand("b", { calidad: 2 })];
  const antes = lista.map((c) => c.id);
  const r = ordenarCarrusel(lista, null, AHORA);
  assert.deepEqual(lista.map((c) => c.id), antes);
  assert.equal(r.length, 2);
});
