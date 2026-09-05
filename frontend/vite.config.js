import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

/**
 * Where is the backend?
 *
 * One source of truth, checked in this order:
 *   1. BACKEND_PORT in the shell that started `npm run dev`
 *   2. SERVER_PORT in the repo-root .env  (same file the backend reads)
 *   3. 8080
 *
 * This exists because "dashboard shows 500 / backend is actually on 8081" is
 * a five-minute debugging detour, and there is no reason to hardcode a port
 * in two places.
 */
function backendPort() {
  if (process.env.BACKEND_PORT) return process.env.BACKEND_PORT;
  const here = path.dirname(fileURLToPath(import.meta.url));
  const envFile = path.resolve(here, "..", ".env");
  try {
    for (const line of fs.readFileSync(envFile, "utf8").split(/\r?\n/)) {
      const m = /^\s*SERVER_PORT\s*=\s*(\d+)\s*$/.exec(line);
      if (m) return m[1];
    }
  } catch {
    /* no .env — fine, use the default */
  }
  return "8080";
}

const target = `http://localhost:${backendPort()}`;
console.log(`[vite] proxying /api -> ${target}`);

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target, changeOrigin: true },
    },
  },
});
