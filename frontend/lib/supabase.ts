import { createClient } from "@supabase/supabase-js";

// Solo claves PÚBLICAS en el frontend. service_role nunca acá (lesson KB).
// En Docker, el código de SERVIDOR (dentro del contenedor) alcanza Supabase por
// SUPABASE_INTERNAL_URL (host.docker.internal); el NAVEGADOR usa la URL pública
// (localhost). En local sin Docker, ambos caen a NEXT_PUBLIC_SUPABASE_URL.
const publicUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
const url =
  typeof window === "undefined"
    ? process.env.SUPABASE_INTERNAL_URL || publicUrl
    : publicUrl;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;

if (!url || !anonKey) {
  // No tiramos error en build para permitir levantar sin .env; las queries fallan suave.
  console.warn("Faltan NEXT_PUBLIC_SUPABASE_URL / NEXT_PUBLIC_SUPABASE_ANON_KEY");
}

export const supabase = createClient(url ?? "http://localhost", anonKey ?? "anon", {
  auth: { persistSession: false },
});

export const hasSupabase = Boolean(url && anonKey);
