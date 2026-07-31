#!/usr/bin/env node
import path from "node:path";
import { validateRelease } from "./lib/release-integrity.mjs";

for (const root of process.argv.slice(2)) {
  const manifest = validateRelease(path.resolve(root));
  console.log(`[release] ${root}: ${manifest.release_id} valid`);
}

if (process.argv.length === 2) {
  throw new Error("Usage: node scripts/validate-web-release.mjs <release-root> [...]");
}
