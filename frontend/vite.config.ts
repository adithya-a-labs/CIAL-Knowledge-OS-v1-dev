import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "path";

const port = Number(process.env.PORT ?? 5173);
const basePath = process.env.BASE_PATH ?? "/";
const buildOutDir = process.env.BUILD_OUT_DIR ?? path.resolve(import.meta.dirname, "dist/public");
const apiProxyTarget = process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000";

export default defineConfig({
  base: basePath,
  define: {
    // Built assets always use the same-origin /api contract. Local Vite
    // sessions reach FastAPI through the loopback proxy configured below.
    "import.meta.env.VITE_API_BASE_URL": JSON.stringify(""),
  },
  plugins: [
    react(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "src"),
    },
    dedupe: ["react", "react-dom"],
  },
  root: path.resolve(import.meta.dirname),
  build: {
    outDir: buildOutDir,
    emptyOutDir: true,
  },
  server: {
    port,
    strictPort: true,
    host: "127.0.0.1",
    allowedHosts: ["localhost", "127.0.0.1"],
    fs: {
      strict: true,
    },
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: false,
      },
    },
  },
  preview: {
    port,
    host: "127.0.0.1",
    allowedHosts: ["localhost", "127.0.0.1"],
    proxy: {
      "/api": {
        target: apiProxyTarget,
        changeOrigin: false,
      },
    },
  },
});
