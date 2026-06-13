import { NextResponse } from "next/server";
import { supabase, hasSupabase } from "@/lib/supabase";

// Health-check para debug remoto (lesson KB api-health-endpoint).
export async function GET() {
  let db = "not-configured";
  if (hasSupabase) {
    const { error } = await supabase.from("zonas").select("id").limit(1);
    db = error ? error.message : "connected";
  }
  return NextResponse.json({
    status: db === "connected" || db === "not-configured" ? "ok" : "degraded",
    service: "bermejo-frontend",
    timestamp: new Date().toISOString(),
    supabase: db,
    env: process.env.VERCEL_ENV ?? "development",
  });
}
