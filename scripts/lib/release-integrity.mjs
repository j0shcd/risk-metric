import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";

function digest(content) {
  return crypto.createHash("sha256").update(content).digest("hex");
}

export const REQUIRED_RELEASE_ARTIFACTS = [
  "category_breakdowns_btc.json",
  "category_breakdowns_total_market.json",
  "diagnostics.json",
  "history_core.json",
  "latest_snapshot.json",
  "manifest.json",
  "metric_breakdowns_btc.json",
  "metric_breakdowns_total_market.json",
  "prospective_evidence.json",
];

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function canonicalDigest(value) {
  return digest(canonicalJson(value));
}

export function validateRelease(root) {
  const manifestPath = path.join(root, "manifest.json");
  const manifest = JSON.parse(fs.readFileSync(manifestPath, "utf8"));
  if (typeof manifest.release_id !== "string" || manifest.release_id.length === 0) {
    throw new Error("manifest.json missing release_id");
  }
  if (!manifest.integrity || typeof manifest.integrity !== "object") {
    throw new Error("manifest.json missing integrity metadata");
  }

  const artifacts = manifest.artifacts ?? [];
  if (
    artifacts.length !== new Set(artifacts).size
    || canonicalJson([...artifacts].sort()) !== canonicalJson(REQUIRED_RELEASE_ARTIFACTS)
  ) {
    throw new Error("manifest.json artifact set does not match required web v2 artifacts");
  }
  const actualEntries = fs.readdirSync(root).sort();
  if (canonicalJson(actualEntries) !== canonicalJson(REQUIRED_RELEASE_ARTIFACTS)) {
    throw new Error("release directory contains missing or unexpected artifacts");
  }
  const expectedIntegrity = REQUIRED_RELEASE_ARTIFACTS.filter((name) => name !== "manifest.json").sort();
  if (canonicalJson(Object.keys(manifest.integrity).sort()) !== canonicalJson(expectedIntegrity)) {
    throw new Error("manifest.json integrity set does not match required artifacts");
  }

  const contentDigests = {};
  for (const artifact of artifacts) {
    if (artifact === "manifest.json") continue;
    const artifactPath = path.join(root, artifact);
    if (!fs.existsSync(artifactPath)) throw new Error(`release artifact missing: ${artifact}`);
    const content = fs.readFileSync(artifactPath);
    const expected = manifest.integrity[artifact];
    if (!expected || expected.bytes !== content.byteLength || expected.sha256 !== digest(content)) {
      throw new Error(`release artifact integrity mismatch: ${artifact}`);
    }
    const payload = JSON.parse(content.toString("utf8"));
    if (payload.release_id !== manifest.release_id) {
      throw new Error(`release_id mismatch: ${artifact}`);
    }
    const { release_id, ...canonicalPayload } = payload;
    contentDigests[artifact] = canonicalDigest(canonicalPayload);
  }
  const releaseBasis = manifest.release_basis ?? {};
  if (canonicalJson(releaseBasis.content_digests) !== canonicalJson(contentDigests)) {
    throw new Error("manifest canonical content digests do not match artifacts");
  }
  const expectedReleaseId = `web-v2-${canonicalDigest({
    content_digests: contentDigests,
    model_identity: releaseBasis.model_identity ?? {},
  })}`;
  if (manifest.release_id !== expectedReleaseId) throw new Error("release_id does not match canonical release basis");
  return manifest;
}

export function loadValidatedAlertRelease(root, now = new Date()) {
  const manifest = validateRelease(root);
  const snapshot = JSON.parse(fs.readFileSync(path.join(root, "latest_snapshot.json"), "utf8"));
  if (snapshot.release_id !== manifest.release_id) throw new Error("alert snapshot release_id mismatch");
  return { manifest, snapshot, now };
}
