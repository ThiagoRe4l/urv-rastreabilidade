import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// O navegador chama /api no mesmo endereço do Vite; o proxy repassa à API.
// No docker compose, API_PROXY_TARGET=http://api:8000.
const alvo = process.env.API_PROXY_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    strictPort: true,
    proxy: { "/api": { target: alvo, changeOrigin: true } },
  },
});
