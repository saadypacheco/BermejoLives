// Instalar la app: detección del navegador, plan y enlace intent:// (lib/instalar-app).
import test from "node:test";
import assert from "node:assert/strict";
import {
  detectarPlataforma, planInstalacion, intentAbrirEnChrome, instruccionManual, nombreNavegador,
} from "../lib/instalar-app";

const UA = {
  chromeAndroid: "Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.6478.122 Mobile Safari/537.36",
  samsung: "Mozilla/5.0 (Linux; Android 14; SAMSUNG SM-A546E) AppleWebKit/537.36 (KHTML, like Gecko) SamsungBrowser/25.0 Chrome/121.0.0.0 Mobile Safari/537.36",
  edgeAndroid: "Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36 EdgA/126.0.2592.80",
  firefoxAndroid: "Mozilla/5.0 (Android 14; Mobile; rv:128.0) Gecko/128.0 Firefox/128.0",
  operaAndroid: "Mozilla/5.0 (Linux; Android 14; SM-A546E) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Mobile Safari/537.36 OPR/82.0.0.0",
  instagram: "Mozilla/5.0 (Linux; Android 14; SM-A546E; wv) AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 Chrome/126.0.0.0 Mobile Safari/537.36 Instagram 330.0.0.0",
  iphoneSafari: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
  iphoneChrome: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) CriOS/126.0.6478.153 Mobile/15E148 Safari/604.1",
  iphoneFirefox: "Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) FxiOS/127.0 Mobile/15E148 Safari/605.1.15",
  ipadComoMac: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
  chromeWindows: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
  edgeWindows: "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36 Edg/126.0.0.0",
  firefoxWindows: "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
  safariMac: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
};

test("detecta los navegadores de Android", () => {
  assert.deepEqual(detectarPlataforma(UA.chromeAndroid), { sistema: "android", navegador: "chrome" });
  assert.deepEqual(detectarPlataforma(UA.samsung), { sistema: "android", navegador: "samsung" });
  assert.deepEqual(detectarPlataforma(UA.edgeAndroid), { sistema: "android", navegador: "edge" });
  assert.deepEqual(detectarPlataforma(UA.firefoxAndroid), { sistema: "android", navegador: "firefox" });
  assert.deepEqual(detectarPlataforma(UA.operaAndroid), { sistema: "android", navegador: "opera" });
});

test("Brave se reconoce por navigator.brave, no por el UA", () => {
  assert.equal(detectarPlataforma(UA.chromeAndroid).navegador, "chrome");
  assert.deepEqual(detectarPlataforma(UA.chromeAndroid, { brave: true }), { sistema: "android", navegador: "brave" });
});

test("los navegadores incrustados (Instagram, Facebook) no cuentan como Chrome", () => {
  assert.equal(detectarPlataforma(UA.instagram).navegador, "webview");
  assert.equal(detectarPlataforma(UA.chromeAndroid + " FBAV/450.0").navegador, "webview");
});

test("detecta iPhone/iPad y su navegador", () => {
  assert.deepEqual(detectarPlataforma(UA.iphoneSafari), { sistema: "ios", navegador: "safari" });
  assert.deepEqual(detectarPlataforma(UA.iphoneChrome), { sistema: "ios", navegador: "ios-otro" });
  assert.deepEqual(detectarPlataforma(UA.iphoneFirefox), { sistema: "ios", navegador: "ios-otro" });
});

test("el iPad que se presenta como Mac se reconoce por la pantalla táctil", () => {
  assert.equal(detectarPlataforma(UA.ipadComoMac, { maxTouchPoints: 5 }).sistema, "ios");
  assert.equal(detectarPlataforma(UA.ipadComoMac, { maxTouchPoints: 0 }).sistema, "escritorio");
  assert.equal(detectarPlataforma(UA.ipadComoMac).sistema, "escritorio");
});

test("detecta los navegadores de compu", () => {
  assert.deepEqual(detectarPlataforma(UA.chromeWindows), { sistema: "escritorio", navegador: "chrome" });
  assert.deepEqual(detectarPlataforma(UA.edgeWindows), { sistema: "escritorio", navegador: "edge" });
  assert.deepEqual(detectarPlataforma(UA.firefoxWindows), { sistema: "escritorio", navegador: "firefox" });
  assert.deepEqual(detectarPlataforma(UA.safariMac), { sistema: "escritorio", navegador: "safari" });
  assert.deepEqual(detectarPlataforma(""), { sistema: "escritorio", navegador: "otro" });
});

test("plan: Android + Chrome usa el diálogo nativo si lo tiene", () => {
  const p = detectarPlataforma(UA.chromeAndroid);
  assert.equal(planInstalacion(p, true), "nativo");
  assert.equal(planInstalacion(p, false), "manual");
});

test("plan: Android con otro navegador manda a Chrome AUNQUE tenga el diálogo nativo", () => {
  for (const ua of [UA.samsung, UA.edgeAndroid, UA.firefoxAndroid, UA.operaAndroid, UA.instagram]) {
    const p = detectarPlataforma(ua);
    assert.equal(planInstalacion(p, true), "abrir-chrome", ua);
    assert.equal(planInstalacion(p, false), "abrir-chrome", ua);
  }
  assert.equal(planInstalacion(detectarPlataforma(UA.chromeAndroid, { brave: true }), true), "abrir-chrome");
});

test("plan: iPhone da la instrucción de Safari; compu usa el diálogo o la instrucción", () => {
  assert.equal(planInstalacion(detectarPlataforma(UA.iphoneSafari), false), "ios");
  assert.equal(planInstalacion(detectarPlataforma(UA.iphoneChrome), true), "ios");
  assert.equal(planInstalacion(detectarPlataforma(UA.chromeWindows), true), "nativo");
  assert.equal(planInstalacion(detectarPlataforma(UA.chromeWindows), false), "manual");
  assert.equal(planInstalacion(detectarPlataforma(UA.firefoxWindows), false), "manual");
});

test("el intent de Chrome lleva el host, la ruta, el paquete y el respaldo codificado", () => {
  const url = "https://uruku.bo/ofertas?ciudad=tarija&q=a b";
  const intent = intentAbrirEnChrome(url);
  assert.ok(intent);
  assert.ok(intent.startsWith("intent://uruku.bo/ofertas?ciudad=tarija&q=a%20b#Intent;"));
  assert.ok(intent.includes(";scheme=https;"));
  assert.ok(intent.includes(";package=com.android.chrome;"));
  assert.ok(intent.endsWith(";end"));
  const respaldo = intent.match(/S\.browser_fallback_url=([^;]*);end/)?.[1];
  assert.equal(respaldo, encodeURIComponent("https://uruku.bo/ofertas?ciudad=tarija&q=a%20b"));
  // El respaldo codificado no puede traer `;` ni `#` crudos: romperían el intent.
  assert.ok(!/[;#]/.test(respaldo ?? ""));
});

test("el intent de la raíz y de un puerto de prueba", () => {
  assert.equal(
    intentAbrirEnChrome("https://uruku.bo/"),
    "intent://uruku.bo/#Intent;scheme=https;package=com.android.chrome;S.browser_fallback_url=https%3A%2F%2Furuku.bo%2F;end",
  );
  assert.ok(intentAbrirEnChrome("http://localhost:3003/x")?.startsWith("intent://localhost:3003/x#Intent;scheme=http;"));
});

test("el intent rechaza lo que no es http(s)", () => {
  assert.equal(intentAbrirEnChrome("javascript:alert(1)"), null);
  assert.equal(intentAbrirEnChrome("nada"), null);
  assert.equal(intentAbrirEnChrome(""), null);
});

test("hay instrucción y nombre para cada caso", () => {
  for (const ua of Object.values(UA)) {
    const p = detectarPlataforma(ua, { maxTouchPoints: 5 });
    assert.ok(instruccionManual(p).length > 10);
    assert.ok(nombreNavegador(p.navegador).length > 2);
  }
  assert.match(instruccionManual(detectarPlataforma(UA.samsung)), /Agregar página a/);
  assert.match(instruccionManual(detectarPlataforma(UA.iphoneSafari)), /Agregar a inicio/);
});
