import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const sourceRoot = path.resolve(__dirname, "../../data/web/v2");
const targetBase = path.resolve(__dirname, "../public/data");
const targetRoot = path.resolve(__dirname, "../public/data/v2");

fs.rmSync(targetBase, { force: true, recursive: true });
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

const manifest = JSON.parse(fs.readFileSync(path.join(sourceRoot, "manifest.json"), "utf8"));
if (/^web-v2-[a-f0-9]{64}$/.test(String(manifest.release_id))) {
  const immutableRoot = path.resolve(targetBase, "releases", manifest.release_id);
  fs.cpSync(sourceRoot, immutableRoot, { recursive: true });
  console.log(`[sync-web-data] Synced ${sourceRoot} -> ${targetRoot} and ${immutableRoot}`);
} else {
  console.warn(`[sync-web-data] Synced legacy release without immutable path: ${sourceRoot} -> ${targetRoot}`);
}
