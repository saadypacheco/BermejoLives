// Versión del producto, horneada en el build (ver next.config.mjs + Dockerfile).
// - APP_VERSION: semántica, se sube a mano en package.json en cada hito.
// - GIT_SHA: commit exacto con el que se buildeó (discrimina QA vs prod al 100%).
// - BUILD_TIME: fecha/hora del build.
// - ENV_LABEL: "prod" | "qa" (según el deploy).
export const APP_VERSION = process.env.NEXT_PUBLIC_APP_VERSION || "0.0.0";
export const GIT_SHA = process.env.NEXT_PUBLIC_GIT_SHA || "dev";
export const BUILD_TIME = process.env.NEXT_PUBLIC_BUILD_TIME || "";
export const ENV_LABEL = process.env.NEXT_PUBLIC_ENV_LABEL || "";

/** Etiqueta corta para mostrar: "v1.0.0 · prod · 561a5ed · 2026-08-19" */
export function versionLabel(): string {
  const fecha = BUILD_TIME ? BUILD_TIME.slice(0, 10) : "";
  return [
    `v${APP_VERSION}`,
    ENV_LABEL || null,
    GIT_SHA,
    fecha || null,
  ].filter(Boolean).join(" · ");
}
