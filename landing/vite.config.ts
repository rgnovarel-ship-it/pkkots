import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  // Chemins relatifs : la page marche quel que soit le dossier où elle est servie.
  base: "./",
  plugins: [react(), tailwindcss()],
  resolve: {
    alias: { "@": path.resolve(import.meta.dirname, "./src") },
  },
});
