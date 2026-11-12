// Qué abre el enlace de WhatsApp del comercio (lib/catalogo.tipoEnlaceWa): decide el botón y el QR de la ficha.
import test from "node:test";
import assert from "node:assert/strict";
import { enlaceCanal, tipoEnlaceWa } from "../lib/catalogo";

test("grupo, canal o chat según el enlace", () => {
  assert.equal(tipoEnlaceWa(enlaceCanal("https://chat.whatsapp.com/AbCdEf123")), "grupo");
  assert.equal(tipoEnlaceWa(enlaceCanal("https://whatsapp.com/channel/0029Va")), "canal");
  assert.equal(tipoEnlaceWa(enlaceCanal("https://www.whatsapp.com/channel/0029Va")), "canal");
  assert.equal(tipoEnlaceWa(enlaceCanal("https://wa.me/59170000000")), "chat");
  assert.equal(tipoEnlaceWa(enlaceCanal("https://ejemplo.com/grupo")), null);
  assert.equal(tipoEnlaceWa(null), null);
});
