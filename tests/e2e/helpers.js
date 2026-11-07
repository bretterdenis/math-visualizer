// Shared e2e harness: a tiny static server for src/, a CDN stub, a Tauri
// bridge stub, and an `openApp` helper. Reusable by any Playwright spec in
// tests/e2e/.
//
// Run directly (`node tests/e2e/helpers.js`) to serve src/ on DEFAULT_PORT;
// playwright.config.js uses this as its webServer command.

import http from "node:http";
import { readFile } from "node:fs/promises";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
export const SRC_DIR = path.resolve(here, "../../src");
export const DEFAULT_PORT = 4173;
export const BASE_URL = `http://127.0.0.1:${DEFAULT_PORT}`;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".png": "image/png",
  ".svg": "image/svg+xml",
  ".json": "application/json",
};

/** Serves `root` over HTTP. Resolves with the listening server. */
export function startStaticServer({ root = SRC_DIR, port = DEFAULT_PORT, host = "127.0.0.1" } = {}) {
  const server = http.createServer(async (req, res) => {
    try {
      let rel = decodeURIComponent(new URL(req.url, "http://localhost").pathname);
      if (rel.endsWith("/")) rel += "index.html";
      const filePath = path.resolve(root, "." + rel);
      if (filePath !== root && !filePath.startsWith(root + path.sep)) {
        res.writeHead(403).end("forbidden");
        return;
      }
      const body = await readFile(filePath);
      res.writeHead(200, {
        "Content-Type": MIME[path.extname(filePath)] ?? "application/octet-stream",
        "Cache-Control": "no-store",
      });
      res.end(body);
    } catch {
      res.writeHead(404).end("not found");
    }
  });
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(port, host, () => resolve(server));
  });
}

/**
 * The page loads mathjs, plotly, and katex from jsDelivr. Those requests are
 * answered locally with empty bodies so the tests do not depend on the CDN
 * being reachable. The scroll layout does not depend on those libraries.
 */
export async function stubCdn(page) {
  await page.route(/^https:\/\/(cdn\.jsdelivr\.net|cdnjs\.cloudflare\.com|unpkg\.com)\//, (route) => {
    const isCss = route.request().url().endsWith(".css");
    route.fulfill({ status: 200, contentType: isCss ? "text/css" : "text/javascript", body: "" });
  });
}

/** Default library: enough topics and functions to make the library list tall. */
export function makeTopics(count = 25, perTopic = 3) {
  return Array.from({ length: count }, (_, i) => ({
    name: `Topic ${i + 1}`,
    functions: Array.from({ length: perTopic }, (_, j) => ({
      id: `t${i + 1}-f${j + 1}`,
      title: `Function ${i + 1}.${j + 1}`,
      subtitle: "",
      description: "",
      kind: "2d",
      variables: ["x"],
      domain: {},
      traces: [{ expr: "sin(x)", label: "sin(x)" }],
      created_at: "",
    })),
  }));
}

/**
 * Replaces window.__TAURI__ before the app's module runs, so `invoke` answers
 * locally: no API key prompt, and `list_topics` returns the given topics.
 */
export async function stubTauri(page, topics) {
  await page.addInitScript((topicsArg) => {
    window.__TAURI__ = {
      core: {
        invoke: async (cmd) => {
          if (cmd === "has_api_key") return true;
          if (cmd === "list_topics") return topicsArg;
          return null;
        },
      },
    };
  }, topics);
}

/**
 * Opens the app at `/` with the CDN and Tauri bridge stubbed. Optionally sets
 * the viewport. Resolves with an array that collects uncaught page errors.
 */
export async function openApp(page, { viewport, topics = makeTopics() } = {}) {
  const pageErrors = [];
  page.on("pageerror", (err) => pageErrors.push(String(err)));
  if (viewport) await page.setViewportSize(viewport);
  await stubCdn(page);
  await stubTauri(page, topics);
  await page.goto("/");
  // main.js renders the library once list_topics resolves.
  await page.waitForFunction(() => document.querySelector("#library-list")?.childElementCount > 0);
  return pageErrors;
}

// Run as a script: serve src/ on the fixed port (used by playwright.config.js).
if (process.argv[1] && pathToFileURL(path.resolve(process.argv[1])).href === import.meta.url) {
  await startStaticServer();
  console.log(`Serving ${SRC_DIR} at ${BASE_URL}`);
}
