#!/usr/bin/env node
import fs from "node:fs";
import path from "node:path";
import { validateRelease } from "./lib/release-integrity.mjs";

export const ARCHIVE_BUDGET_BYTES = 250_000_000;

export function appendProspectiveArchive({ releaseRoot, archivePath, budgetBytes = ARCHIVE_BUDGET_BYTES }) {
  const manifest = validateRelease(releaseRoot);
  const snapshot = JSON.parse(fs.readFileSync(path.join(releaseRoot, "latest_snapshot.json"), "utf8"));
  const prospectiveEvidence = JSON.parse(
    fs.readFileSync(path.join(releaseRoot, "prospective_evidence.json"), "utf8"),
  );
  const record = {
    release_id: manifest.release_id,
    generated_at: manifest.generated_at,
    snapshot,
    normalized_inputs: prospectiveEvidence.normalized_inputs,
    input_content_sha256: prospectiveEvidence.input_content_sha256,
    provenance: prospectiveEvidence.provenance,
    model_identity: manifest.release_basis.model_identity,
    content_digests: manifest.release_basis.content_digests,
  };
  const line = `${JSON.stringify(record)}\n`;
  const existing = fs.existsSync(archivePath) ? fs.readFileSync(archivePath, "utf8") : "";
  const matching = existing.split("\n").filter(Boolean).map((item) => JSON.parse(item)).find(
    (item) => item.release_id === manifest.release_id,
  );
  if (matching) {
    const archivedBasis = JSON.stringify({
      content_digests: matching.content_digests,
      model_identity: matching.model_identity,
    });
    const currentBasis = JSON.stringify({
      content_digests: record.content_digests,
      model_identity: record.model_identity,
    });
    if (archivedBasis !== currentBasis) {
      throw new Error(`release_id collision with different archived content: ${manifest.release_id}`);
    }
    return { appended: false, bytes: Buffer.byteLength(existing), budgetBytes };
  }
  const projectedBytes = Buffer.byteLength(existing) + Buffer.byteLength(line);
  if (projectedBytes > budgetBytes) {
    throw new Error(`release archive budget exceeded: ${projectedBytes} > ${budgetBytes} bytes`);
  }
  fs.mkdirSync(path.dirname(archivePath), { recursive: true });
  fs.appendFileSync(archivePath, line);
  return { appended: true, bytes: projectedBytes, budgetBytes };
}

export async function uploadArchiveIfConfigured({ archivePath, env = process.env, fetchImpl = fetch }) {
  if (!env.RELEASE_ARCHIVE_UPLOAD_URL) return { uploaded: false, reason: "not_configured" };
  const headers = { "Content-Type": "application/x-ndjson" };
  if (env.RELEASE_ARCHIVE_UPLOAD_TOKEN) headers.Authorization = `Bearer ${env.RELEASE_ARCHIVE_UPLOAD_TOKEN}`;
  const response = await fetchImpl(env.RELEASE_ARCHIVE_UPLOAD_URL, {
    method: "PUT",
    headers,
    body: fs.readFileSync(archivePath),
  });
  if (!response.ok) throw new Error(`archive upload failed: ${response.status}`);
  return { uploaded: true };
}

async function main() {
  const releaseRoot = path.resolve(process.argv[2] || "data/web/v2");
  const archivePath = path.resolve(process.argv[3] || "data/web/archive/release_snapshots.ndjson");
  const result = appendProspectiveArchive({ releaseRoot, archivePath });
  const upload = await uploadArchiveIfConfigured({ archivePath });
  console.log(`[archive] ${result.appended ? "appended" : "already present"}; ${result.bytes}/${result.budgetBytes} bytes; upload=${upload.uploaded}`);
}

if (import.meta.url === `file://${process.argv[1]}`) {
  main().catch((error) => {
    console.error(`[archive] ${error.message}`);
    process.exitCode = 1;
  });
}
