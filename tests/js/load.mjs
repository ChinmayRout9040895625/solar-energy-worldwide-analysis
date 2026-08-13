import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";
import vm from "node:vm";

const here = path.dirname(fileURLToPath(import.meta.url));
export const ROOT = path.resolve(here, "..", "..");
const JS_DIR = path.join(ROOT, "analysis", "dashboard_assets", "js");

/** Run asset scripts in this context and return the SOLAR namespace. */
export function load(...names) {
  for (const name of names) {
    const file = path.join(JS_DIR, name);
    vm.runInThisContext(readFileSync(file, "utf8"), { filename: file });
  }
  return globalThis.SOLAR;
}

/** The payload the dashboard is built from, for cross-language checks. */
export function payload() {
  const file = path.join(ROOT, "output", "data.json");
  return JSON.parse(readFileSync(file, "utf8"));
}
