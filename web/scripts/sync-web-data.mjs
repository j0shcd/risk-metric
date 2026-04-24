import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const sourceRoot = path.resolve(__dirname, "../../data/web/v1");
const targetRoot = path.resolve(__dirname, "../public/data/v1");

fs.rmSync(targetRoot, { force: true, recursive: true });
fs.mkdirSync(targetRoot, { recursive: true });

if (!fs.existsSync(sourceRoot)) {
  console.warn(`[sync-web-data] Source not found at ${sourceRoot}. Created empty ${targetRoot}.`);
  process.exit(0);
}

for (const item of fs.readdirSync(sourceRoot)) {
  const sourcePath = path.join(sourceRoot, item);
  const targetPath = path.join(targetRoot, item);
  const stats = fs.statSync(sourcePath);

  if (stats.isDirectory()) {
    fs.cpSync(sourcePath, targetPath, { recursive: true });
  } else {
    fs.copyFileSync(sourcePath, targetPath);
  }
}

console.log(`[sync-web-data] Synced ${sourceRoot} -> ${targetRoot}`);
