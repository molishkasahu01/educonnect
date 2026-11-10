import { defineConfig } from "@playwright/test";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

function resolveChromiumPath(): string | undefined {
  if (process.env.PLAYWRIGHT_EXECUTABLE_PATH) {
    return process.env.PLAYWRIGHT_EXECUTABLE_PATH;
  }
  const candidates = [
    path.join(
      os.homedir(),
      ".cache/ms-playwright/chromium_headless_shell-1248/chrome-headless-shell-linux64/chrome-headless-shell"
    ),
    path.join(
      os.homedir(),
      ".cache/ms-playwright/chromium-1248/chrome-linux64/chrome"
    ),
    "/usr/bin/chromium",
  ];
  for (const p of candidates) {
    if (fs.existsSync(p)) return p;
  }
  return undefined;
}

const executablePath = resolveChromiumPath();

export default defineConfig({
  testDir: "./tests/e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  use: {
    baseURL: process.env.E2E_BASE_URL || "http://127.0.0.1:3010",
    headless: true,
    screenshot: "only-on-failure",
    launchOptions: executablePath ? { executablePath } : undefined,
  },
});
