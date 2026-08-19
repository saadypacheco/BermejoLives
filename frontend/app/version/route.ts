import { NextResponse } from "next/server";
import { APP_VERSION, GIT_SHA, BUILD_TIME, ENV_LABEL } from "@/lib/version";

// Endpoint legible por máquina para saber qué build está corriendo en cada
// ambiente sin abrir el navegador:  curl https://encontralo.store/version
export const dynamic = "force-static"; // los valores están horneados en el build

export function GET() {
  return NextResponse.json({
    version: APP_VERSION,
    commit: GIT_SHA,
    buildTime: BUILD_TIME,
    env: ENV_LABEL,
  });
}
