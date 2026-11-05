import fs from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { buildPublicApi } from "../src/publicApi.js";

const dataRoot = new URL("../public/data/", import.meta.url);
const read = async (url) => JSON.parse(await fs.readFile(url, "utf8"));
const manifest = await read(new URL("v2/manifest.json", dataRoot));
const releaseId = manifest.release_id;
if (!/^web-v2-[a-f0-9]{64}$/.test(releaseId ?? "")) throw new Error("Invalid published release_id");
const releaseRoot = new URL(`releases/${releaseId}/`, dataRoot);
const [historyCore, latestSnapshot] = await Promise.all([
  read(new URL("history_core.json", releaseRoot)),
  read(new URL("latest_snapshot.json", releaseRoot)),
]);
const { latest, history } = buildPublicApi({ manifest, historyCore, latestSnapshot });
const output = new URL("../public/api/v1/", import.meta.url);
await fs.mkdir(output, { recursive: true });
await fs.writeFile(new URL("latest.json", output), `${JSON.stringify(latest, null, 2)}\n`);
await fs.writeFile(new URL("history.json", output), `${JSON.stringify(history)}\n`);
console.log(`[build-public-api] ${releaseId} -> ${fileURLToPath(output)}`);
