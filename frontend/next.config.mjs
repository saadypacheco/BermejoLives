import { readFileSync } from "node:fs";

// Versión del producto horneada en el bundle. package.json es la versión
// semántica; GIT_SHA/APP_ENV los pasa el build (ARG del Dockerfile) y la
// fecha se toma del momento del build.
const pkg = JSON.parse(readFileSync(new URL("./package.json", import.meta.url), "utf8"));
const buildTime = new Date().toISOString();

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  env: {
    NEXT_PUBLIC_APP_VERSION: pkg.version,
    NEXT_PUBLIC_GIT_SHA: process.env.GIT_SHA || "dev",
    NEXT_PUBLIC_BUILD_TIME: buildTime,
    NEXT_PUBLIC_ENV_LABEL: process.env.APP_ENV || "",
  },
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "picsum.photos" },
      { protocol: "https", hostname: "i.pravatar.cc" },
      { protocol: "https", hostname: "images.unsplash.com" },
    ],
  },
};

export default nextConfig;
