import "server-only";
import { PostgrestClient } from "@supabase/postgrest-js";

// SÓLO SERVIDOR. Este módulo (y lib/data.ts, lib/ficha-data.ts,
// lib/saber-revisado.ts) llevan `import "server-only"`: si un componente
// cliente los importa, el build falla. Así la URL de la base y la anon key
// nunca llegan al bundle del navegador, y nadie puede bajarse el catálogo
// entero hablando directo con PostgREST (db.uruku.bo/rest/v1/...).
//
// El navegador lee datos por `lib/data-client.ts` -> `/api/lectura` (route
// handler de Next, que sí corre acá, en el servidor).
//
// Cliente: `PostgrestClient` de @supabase/postgrest-js (la parte de supabase-js
// que habla con PostgREST). Sólo usamos `.from()` y `.rpc()`; no hay Auth,
// Storage ni Realtime, así que no hace falta el cliente completo.
//
// Variables (de SERVIDOR, sin el prefijo NEXT_PUBLIC_):
//   SUPABASE_INTERNAL_URL  URL de PostgREST por la RED INTERNA de Docker, tal
//                          cual la atiende PostgREST, SIN `/rest/v1`
//                          (prod: http://buscadonde-postgrest:3000). Si el
//                          origen sí lleva prefijo (el Kong del Supabase local
//                          de desarrollo), el prefijo va incluido en la variable
//                          (http://host.docker.internal:54421/rest/v1).
//                          Tiene prioridad sobre las demás.
//   SUPABASE_URL           URL PÚBLICA de PostgREST (respaldo). Es la raíz
//                          (https://db.uruku.bo): acá se le agrega `/rest/v1`,
//                          que el Traefik de prod saca antes de reenviar.
//   SUPABASE_ANON_KEY      La anon key (RLS la limita igual que antes).
// Mientras no estén seteadas se usan las NEXT_PUBLIC_SUPABASE_URL /
// NEXT_PUBLIC_SUPABASE_ANON_KEY de siempre, para no romper un deploy viejo.
// Ojo: las páginas estáticas leen la base DURANTE EL BUILD, así que las
// variables tienen que estar también como build args (docker-compose.prod.yml);
// en el build se usa SUPABASE_URL (pública) si está, ver `enBuild` más abajo.
const internalUrl = process.env.SUPABASE_INTERNAL_URL?.trim().replace(/\/+$/, "");
const publicUrl = (process.env.SUPABASE_URL || process.env.NEXT_PUBLIC_SUPABASE_URL)?.trim().replace(/\/+$/, "");
const anonKey = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

// EN EL BUILD manda la URL pública: `docker build` (BuildKit) no entra a las redes del compose, así
// que `buscadonde-postgrest` no resuelve ahí. Sin esto las páginas estáticas (sitemap, /que-es-uruku,
// /comprar-en-bermejo) se arman SIN datos y quedan así hasta su primera revalidación (1 h a 1 día).
// En runtime (`next start`) manda la red interna, que es lo que importa.
const enBuild = process.env.NEXT_PHASE === "phase-production-build";
const restUrlPublica = publicUrl ? `${publicUrl}/rest/v1` : undefined;
const restUrl = (enBuild && restUrlPublica) || internalUrl || restUrlPublica;

if (!restUrl || !anonKey) {
  // No tiramos error en build para permitir levantar sin .env; las queries fallan suave.
  console.warn("Faltan SUPABASE_INTERNAL_URL o SUPABASE_URL / SUPABASE_ANON_KEY (o NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY)");
}

const clave = anonKey ?? "anon";

export const supabase = new PostgrestClient(restUrl ?? "http://localhost/rest/v1", {
  // Lo mismo que mandaba supabase-js: la anon key como `apikey` y como Bearer.
  headers: { apikey: clave, Authorization: `Bearer ${clave}` },
  // NUNCA CACHEAR. Next parchea `fetch` en el servidor y guarda respuestas
  // aunque la ruta sea dinámica: /cambio y /planes siguieron mostrando la
  // cotización del 15 de agosto una hora después de cargar la de hoy,
  // mientras el home la mostraba bien. Una cotización, un plan o una oferta
  // que se lee de la base tiene que ser la de AHORA; el costo de no cachear
  // es una consulta a PostgREST por render, que es lo que ya se paga en el
  // resto del sitio.
  fetch: (input, init) => fetch(input, { ...init, cache: "no-store" }),
});

export const hasSupabase = Boolean(restUrl && anonKey);
