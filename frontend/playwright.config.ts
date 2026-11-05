import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config. Tests live in the top-level ../tests/e2e and drive the running app.
 * The frontend dev server is started automatically; the BACKEND must be running
 * separately (e.g. via start-all.ps1 or docker compose) for auth/run specs to pass.
 */
export default defineConfig({
  testDir: "../tests/e2e",
  timeout: 30_000,
  expect: { timeout: 7_000 },
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "github" : "list",
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },
});
