import { defineConfig, devices } from "@playwright/test";
import { BASE_URL } from "./tests/e2e/helpers.js";

export default defineConfig({
  testDir: "tests/e2e",
  testMatch: "**/*.spec.js",
  fullyParallel: true,
  reporter: "list",
  use: { baseURL: BASE_URL, trace: "retain-on-failure" },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: {
    command: "node tests/e2e/helpers.js",
    url: BASE_URL,
    reuseExistingServer: !process.env.CI,
  },
});
