// Tests de la lógica pura de precios y vencimientos (lib/precios-pure.ts):
// «≈ $ ARS» junto al precio en Bs y la tira «Vencen hoy» en hora de Bolivia.
import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import {
  arsAproximado, diasHastaVencer, etiquetaVence, hoyEnBolivia, miles, ofertasPorVencer, precioArsTexto,
  ofertaVigente, soloVigentes, tituloVencen, venceHoy,
} from "../lib/precios-pure";

// 1.000 ARS = 6,8 Bs → 0,0068 Bs por peso (así lo entrega `tasasDe`).
const ARS_POR_BS = 6.8 / 1000;

/* ─── ≈ pesos argentinos ─────────────────────────────────────────────────── */

test("arsAproximado convierte Bs a pesos con el cambio del día y redondea a 10", () => {
  // 100 / 0,0068 = 14.705,88 → 14.710
  assert.equal(arsAproximado(100, "BOB", ARS_POR_BS), 14710);
  assert.equal(arsAproximado(220, "BOB", ARS_POR_BS), 32350);
});

test("arsAproximado no muestra nada si no hay cambio cargado", () => {
  assert.equal(arsAproximado(100, "BOB", null), null);
  assert.equal(arsAproximado(100, "BOB", undefined), null);
  assert.equal(arsAproximado(100, "BOB", 0), null);
  assert.equal(arsAproximado(100, "BOB", Number.NaN), null);
  assert.equal(precioArsTexto(100, "BOB", null), null);
});

test("arsAproximado sólo convierte precios en bolivianos", () => {
  assert.equal(arsAproximado(100, "USD", ARS_POR_BS), null);
  assert.equal(arsAproximado(100, "ARS", ARS_POR_BS), null);
});

test("arsAproximado ignora precios vacíos o inválidos", () => {
  assert.equal(arsAproximado(null, "BOB", ARS_POR_BS), null);
  assert.equal(arsAproximado(0, "BOB", ARS_POR_BS), null);
  assert.equal(arsAproximado(-5, "BOB", ARS_POR_BS), null);
  assert.equal(arsAproximado(Number.NaN, "BOB", ARS_POR_BS), null);
});

test("arsAproximado nunca devuelve 0 para un precio chico", () => {
  // Bs 0,01 son menos de 2 pesos: no puede decir «≈ $ 0».
  const r = arsAproximado(0.01, "BOB", ARS_POR_BS);
  assert.ok(r != null && r >= 1);
});

test("miles separa con punto, sin depender del idioma del equipo", () => {
  assert.equal(miles(0), "0");
  assert.equal(miles(950), "950");
  assert.equal(miles(14710), "14.710");
  assert.equal(miles(1234567), "1.234.567");
});

test("precioArsTexto arma «≈ $ 14.710 ARS»", () => {
  assert.equal(precioArsTexto(100, "BOB", ARS_POR_BS), "≈ $ 14.710 ARS");
});

/* ─── Hora de Bolivia ────────────────────────────────────────────────────── */

test("hoyEnBolivia usa UTC-4: a las 23:00 de Bermejo el servidor (UTC) ya está en el día siguiente", () => {
  // 2026-11-05 23:00 en Bolivia = 2026-11-06 03:00 UTC
  assert.equal(hoyEnBolivia(new Date("2026-11-06T03:00:00Z")), "2026-11-05");
  // Recién pasada la medianoche boliviana (00:30 = 04:30 UTC) ya es el día nuevo.
  assert.equal(hoyEnBolivia(new Date("2026-11-06T04:30:00Z")), "2026-11-06");
  // A las 03:59 UTC todavía es de noche en Bolivia.
  assert.equal(hoyEnBolivia(new Date("2026-11-06T03:59:59Z")), "2026-11-05");
  assert.equal(hoyEnBolivia(new Date("2026-11-06T04:00:00Z")), "2026-11-06");
});

test("hoyEnBolivia cruza bien el fin de mes y de año", () => {
  assert.equal(hoyEnBolivia(new Date("2026-12-31T20:00:00Z")), "2026-12-31");
  assert.equal(hoyEnBolivia(new Date("2027-01-01T04:00:00Z")), "2027-01-01");
});

test("una oferta que vence hoy sigue vigente de noche aunque el servidor (UTC) ya esté en mañana", () => {
  const nocheEnBermejo = new Date("2026-11-06T02:00:00Z");   // 22:00 del 5/11 en Bolivia
  assert.equal(venceHoy("2026-11-05", nocheEnBermejo), true);
  assert.equal(diasHastaVencer("2026-11-05", nocheEnBermejo), 0);
  // Con la hora de UTC a secas habría dicho que ya venció (-1).
  assert.equal(etiquetaVence("2026-11-05", nocheEnBermejo), "Vence hoy");
});

test("diasHastaVencer: hoy, mañana, vencida y sin fecha", () => {
  const ahora = new Date("2026-11-05T15:00:00Z");   // 11:00 en Bolivia
  assert.equal(diasHastaVencer("2026-11-05", ahora), 0);
  assert.equal(diasHastaVencer("2026-11-06", ahora), 1);
  assert.equal(diasHastaVencer("2026-11-10", ahora), 5);
  assert.equal(diasHastaVencer("2026-11-04", ahora), -1);
  assert.equal(diasHastaVencer(null, ahora), null);
  assert.equal(diasHastaVencer("", ahora), null);
  assert.equal(diasHastaVencer("31/07", ahora), null);
});

test("diasHastaVencer cuenta días de calendario entre meses", () => {
  const ahora = new Date("2026-11-30T15:00:00Z");
  assert.equal(diasHastaVencer("2026-12-01", ahora), 1);
  assert.equal(diasHastaVencer("2026-12-02", ahora), 2);
});

test("etiquetaVence sólo habla de hoy y de mañana", () => {
  const ahora = new Date("2026-11-05T15:00:00Z");
  assert.equal(etiquetaVence("2026-11-05", ahora), "Vence hoy");
  assert.equal(etiquetaVence("2026-11-06", ahora), "Vence mañana");
  assert.equal(etiquetaVence("2026-11-07", ahora), null);
  assert.equal(etiquetaVence("2026-11-04", ahora), null);
  assert.equal(etiquetaVence(null, ahora), null);
});

/* ─── La tira «Vencen hoy» ───────────────────────────────────────────────── */

const AHORA = new Date("2026-11-05T15:00:00Z");
const of = (id: string, vence_el: string | null) => ({ id, vence_el });

test("ofertasPorVencer deja las de hoy y mañana, las de hoy primero, y descarta el resto", () => {
  const lista = [
    of("a", "2026-11-06"), of("b", null), of("c", "2026-11-05"), of("d", "2026-11-04"),
    of("e", "2026-11-09"), of("f", "2026-11-05"), of("g", "2026-11-06"),
  ];
  assert.deepEqual(ofertasPorVencer(lista, AHORA).map((o) => o.id), ["c", "f", "a", "g"]);
});

test("ofertasPorVencer respeta el máximo y devuelve vacío si no hay nada por vencer", () => {
  const muchas = Array.from({ length: 12 }, (_, i) => of(String(i), "2026-11-05"));
  assert.equal(ofertasPorVencer(muchas, AHORA, 5).length, 5);
  assert.deepEqual(ofertasPorVencer([of("x", null), of("y", "2026-12-01")], AHORA), []);
  assert.deepEqual(ofertasPorVencer([], AHORA), []);
});

test("tituloVencen promete sólo lo que hay", () => {
  assert.equal(tituloVencen([of("a", "2026-11-05")], AHORA), "Vencen hoy");
  assert.equal(tituloVencen([of("a", "2026-11-06")], AHORA), "Vencen mañana");
  assert.equal(tituloVencen([of("a", "2026-11-05"), of("b", "2026-11-06")], AHORA), "Vencen hoy y mañana");
});

/* ─── Ofertas vencidas fuera de «Ofertas destacadas» ─────────────────────── */

test("ofertaVigente: sin fecha vale; hasta el último día vale; después de ese día no", () => {
  // 2026-11-05 15:00 UTC = 11:00 en Bolivia.
  const ahora = new Date("2026-11-05T15:00:00Z");
  assert.equal(ofertaVigente(null, ahora), true);
  assert.equal(ofertaVigente("2026-11-05", ahora), true);   // vence hoy: vigente
  assert.equal(ofertaVigente("2026-11-06", ahora), true);
  assert.equal(ofertaVigente("2026-11-04", ahora), false);  // venció ayer
});

test("ofertaVigente usa la fecha de Bolivia y no la del servidor (UTC)", () => {
  // 2026-11-06 01:00 UTC sigue siendo 5 de noviembre a las 21:00 en Bolivia.
  const ahora = new Date("2026-11-06T01:00:00Z");
  assert.equal(ofertaVigente("2026-11-05", ahora), true);
  assert.equal(ofertaVigente("2026-11-04", ahora), false);
});

test("soloVigentes saca las vencidas y conserva el orden", () => {
  const ahora = new Date("2026-11-05T15:00:00Z");
  const items = [
    { id: "a", vence_el: "2026-11-01" }, { id: "b", vence_el: null },
    { id: "c", vence_el: "2026-11-05" }, { id: "d", vence_el: "2026-10-31" },
  ];
  assert.deepEqual(soloVigentes(items, ahora).map((o) => o.id), ["b", "c"]);
});

/* ─── Reglas de marca ────────────────────────────────────────────────────── */

test("los archivos del incremento no llevan emojis (AGENTS.md §6)", () => {
  const EMOJI = /[\u{1F300}-\u{1FAFF}\u{2600}-\u{27BF}\u{2B06}\u{2B05}\u{2B07}\u{FE0F}]/u;
  for (const f of [
    "lib/precios-pure.ts", "components/precio-ars.tsx", "components/oferta-card.tsx",
    "components/install-prompt.tsx", "components/videos-uruku.tsx", "components/tarjetas-promo.tsx",
  ]) {
    const texto = readFileSync(resolve(process.cwd(), f), "utf8");
    assert.ok(!EMOJI.test(texto), `${f} tiene un emoji`);
  }
});
