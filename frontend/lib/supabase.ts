import "server-only";
import { createClient } from "@supabase/supabase-js";

// SÓLO SERVIDOR. Este módulo (y lib/data.ts, lib/ficha-data.ts,
// lib/saber-revisado.ts) llevan `import "server-only"`: si un componente
// cliente los importa, el build falla. Así la URL de la base y la anon key
// nunca llegan al bundle del navegador, y nadie puede bajarse el catálogo
// entero hablando directo con PostgREST (db.uruku.bo/rest/v1/...).
//
// El navegador lee datos por `lib/data-client.ts` -> `/api/lectura` (route
// handler de Next, que sí corre acá, en el servidor).
//
// Variables (de SERVIDOR, sin el prefijo NEXT_PUBLIC_):
//   SUPABASE_URL           URL pública de PostgREST.
//   SUPABASE_INTERNAL_URL  Si el contenedor alcanza la base por otro host
//                          (host.docker.internal), tiene prioridad.
//   SUPABASE_ANON_KEY      La anon key (RLS la limita igual que antes).
// Mientras no estén seteadas se usan las NEXT_PUBLIC_SUPABASE_URL /
// NEXT_PUBLIC_SUPABASE_ANON_KEY de siempre, para no romper el deploy actual.
// Ojo: esas dos se hornean en el build; las nuevas se leen en runtime.
const url =
  process.env.SUPABASE_INTERNAL_URL ||
  process.env.SUPABASE_URL ||
  process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.SUPABASE_ANON_KEY || process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  // No tiramos error en build para permitir levantar sin .env; las queries fallan suave.
  console.warn("Faltan SUPABASE_URL / SUPABASE_ANON_KEY (o NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY)");
}

export const supabase = createClient(url ?? "http://localhost", anonKey ?? "anon", {
  auth: { persistSession: false },
  // NUNCA CACHEAR. Next parchea `fetch` en el servidor y guarda respuestas
  // aunque la ruta sea dinámica: /cambio y /planes siguieron mostrando la
  // cotización del 15 de agosto una hora después de cargar la de hoy,
  // mientras el home la mostraba bien. Una cotización, un plan o una oferta
  // que se lee de la base tiene que ser la de AHORA; el costo de no cachear
  // es una consulta a PostgREST por render, que es lo que ya se paga en el
  // resto del sitio.
  global: { fetch: (input, init) => fetch(input, { ...init, cache: "no-store" }) },
});

export const hasSupabase = Boolean(url && anonKey);
