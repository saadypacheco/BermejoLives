import type { Config } from "tailwindcss";

// Tokens del diseño dark premium de Bermejo (mismos que el prototipo).
const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#060911",
        "bg-1": "#0a0e18",
        "bg-2": "#0e1320",
        blue: "#2e6bff",
        "blue-soft": "#5b8bff",
        neon: "#39ff9e",
        "neon-dim": "#1fd17e",
        purple: "#9b5cff",
        pink: "#ff4d8d",
        orange: "#ff8a3d",
        amber: "#ffc23d",
        wa: "#25d366",
        txt: "#eef2fb",
        "txt-2": "#aab3c8",
        "txt-3": "#6b7488",
      },
    },
  },
  plugins: [],
};

export default config;
