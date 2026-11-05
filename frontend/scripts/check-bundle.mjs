// `npm run check:bundle` — corre DESPUÉS de `npm run build`.
//
// Falla (exit 1) si el bundle del navegador (.next/static) trae algo de la base:
//   - "rest/v1": la ruta de PostgREST que arma supabase-js (si aparece, el
//     cliente de la base se coló en un componente cliente);
//   - "eyJhbGciOiJIUzI1NiIs": el encabezado HS256 de cualquier JWT (la anon key);
//   - los valores literales de SUPABASE_URL / SUPABASE_ANON_KEY (y de sus
//     NEXT_PUBLIC_*) si están en el entorno del build.
//
// Por qué importa: con la URL y la anon key en el bundle cualquiera se baja el
// catálogo entero hablando directo con db.uruku.bo. Los datos se leen en el
// servidor (lib/data.ts es `server-only`); el navegador usa /api/lectura.
//
// Para que la prueba no pase en vacío, buildeá con valores de mentira:
//   NEXT_PUBLIC_SUPABASE_URL=https://db.ejemplo.test \
//   NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIs.prueba npm run build
import { readdirSync, readFileSync, statSync, existsSync } from "node:fs";
import { join } from "node:path";

const dist = process.env.NEXT_DIST_DIR || ".next";
const raiz = join(process.cwd(), dist, "static");

if (!existsSync(raiz)) {
  console.error(`check:bundle: no existe ${raiz}. Corré primero \`npm run build\`.`);
  process.exit(2);
}

const patrones = ["rest/v1", "eyJhbGciOiJIUzI1NiIs"];
for (const v of [
  process.env.SUPABASE_URL, process.env.SUPABASE_INTERNAL_URL, process.env.SUPABASE_ANON_KEY,
  process.env.NEXT_PUBLIC_SUPABASE_URL, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY,
]) {
  if (v && v.trim().length >= 8) patrones.push(v.trim());
}

function* archivos(dir) {
  for (const nombre of readdirSync(dir)) {
    const ruta = join(dir, nombre);
    if (statSync(ruta).isDirectory()) yield* archivos(ruta);
    else if (/\.(js|css|map|json|html|txt)$/.test(nombre)) yield ruta;
  }
}

const hallazgos = [];
let revisados = 0;
for (const ruta of archivos(raiz)) {
  revisados++;
  const texto = readFileSync(ruta, "utf8");
  for (const p of patrones) {
    if (texto.includes(p)) hallazgos.push({ ruta, patron: p.length > 24 ? `${p.slice(0, 12)}…` : p });
  }
}

if (hallazgos.length > 0) {
  console.error(`check:bundle: FALLA — datos de la base en el bundle del navegador (${hallazgos.length}):`);
  for (const h of hallazgos) console.error(`  ${h.ruta}  ->  ${h.patron}`);
  process.exit(1);
}
console.log(`check:bundle: OK — ${revisados} archivos de ${dist}/static sin rastro de la base.`);
