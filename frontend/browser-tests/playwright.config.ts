import { defineConfig } from "@playwright/test";

const baseURL = process.env.NASHORDAQ_BROWSER_URL;
const outputDir = process.env.NASHORDAQ_BROWSER_RESULTS;
if (!baseURL || !outputDir) {
  throw new Error("Use pnpm run test:browser --runtime docker|podman.");
}

export default defineConfig({
  testDir: ".",
  testMatch: "demo.spec.ts",
  outputDir,
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  retries: 0,
  reporter: "list",
  use: {
    baseURL,
    browserName: "chromium",
    headless: true,
    viewport: { width: 1440, height: 1000 },
    trace: "off",
    video: "off",
    screenshot: "off",
  },
});
