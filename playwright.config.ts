import { defineConfig } from "@playwright/test";

const backendPort = 8001;
const dashboardPort = 5174;

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  use: { baseURL: `http://localhost:${String(dashboardPort)}` },
  webServer: [
    {
      command: `uv run -m backend.db && uv run -m uvicorn backend.main:app --port ${String(backendPort)}`,
      url: `http://127.0.0.1:${String(backendPort)}/api/health`,
      env: { UNDERCOVER_DB: "e2e/.data/e2e.db" },
    },
    {
      command: `npx vite dashboard --port ${String(dashboardPort)} --strictPort`,
      url: `http://localhost:${String(dashboardPort)}`,
      env: { BACKEND_URL: `http://127.0.0.1:${String(backendPort)}` },
    },
  ],
});
