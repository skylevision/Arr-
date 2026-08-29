import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Das Frontend wird ins Image kompiliert und von FastAPI ausgeliefert.
// Im Entwicklungsmodus zeigt der Proxy auf ein lokal laufendes Backend.
export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: { outDir: "dist", assetsDir: "assets", sourcemap: false },
  server: {
    proxy: { "/api": { target: "http://127.0.0.1:8099", changeOrigin: true } },
  },
});
