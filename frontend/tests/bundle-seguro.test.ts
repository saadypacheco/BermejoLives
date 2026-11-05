// El navegador no puede importar los módulos que hablan con la base.
//
// lib/supabase.ts, lib/data.ts, lib/ficha-data.ts y lib/saber-revisado.ts son
// `server-only`; los componentes cliente leen datos por lib/data-client.ts. Este
// test lo vigila sin compilar nada: ningún archivo con "use client" importa esos
// módulos (el build ya fallaría, pero acá el mensaje es claro y corre en `npm test`).
// La prueba de verdad, sobre el bundle compilado, es `npm run check:bundle`.
import test from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, resolve } from "node:path";

const RAIZ = process.cwd();   // `npm test` corre en frontend/
const SOLO_SERVIDOR = ["supabase", "data", "ficha-data", "saber-revisado"];

function* fuentes(dir: string): Generator<string> {
  for (const nombre of readdirSync(dir)) {
    const ruta = join(dir, nombre);
    if (statSync(ruta).isDirectory()) yield* fuentes(ruta);
    else if (/\.(ts|tsx)$/.test(nombre)) yield ruta;
  }
}

test("los módulos que leen la base declaran `server-only`", () => {
  for (const m of SOLO_SERVIDOR) {
    const txt = readFileSync(resolve(RAIZ, "lib", `${m}.ts`), "utf8");
    assert.match(txt, /import "server-only";/, `lib/${m}.ts tiene que importar "server-only"`);
  }
});

test("ningún componente cliente importa los módulos que leen la base", () => {
  const malos: string[] = [];
  const importa = new RegExp(`from\\s+["'](?:@/lib|\\.{1,2}(?:/\\.\\.)*/lib|\\.)/(?:${SOLO_SERVIDOR.join("|")})["']`);
  for (const base of ["app", "components", "lib"]) {
    for (const ruta of fuentes(resolve(RAIZ, base))) {
      const txt = readFileSync(ruta, "utf8");
      const cliente = /^\s*(?:\/\/[^\n]*\n|\/\*[\s\S]*?\*\/\s*)*["']use client["']/.test(txt);
      if (cliente && importa.test(txt)) malos.push(ruta.replace(RAIZ, ""));
    }
  }
  assert.deepEqual(malos, [], "estos componentes cliente importan módulos server-only");
});

test("ningún archivo de lib/ lee SUPABASE en el navegador (data-client y data-pure no importan supabase)", () => {
  for (const m of ["data-client", "data-pure"]) {
    const txt = readFileSync(resolve(RAIZ, "lib", `${m}.ts`), "utf8");
    assert.doesNotMatch(txt, /@supabase\/(?:supabase|postgrest)-js|@\/lib\/supabase|@\/lib\/data"/, `lib/${m}.ts no puede tocar la base`);
  }
});
