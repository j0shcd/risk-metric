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

export const ARCHIVE_UPLOAD_TIMEOUT_MS = 30_000;

export async function uploadArchiveIfConfigured({
  archivePath, env = process.env, fetchImpl = fetch,
  timeoutMs = ARCHIVE_UPLOAD_TIMEOUT_MS,
}) {
  if (!env.RELEASE_ARCHIVE_UPLOAD_URL) return { uploaded: false, reason: "not_configured" };
  // URL and approved origin are independent deployment settings. Never log either:
  // signed URLs, userinfo and query strings can contain credentials.
  let endpoint;
  let approved;
  try {
    endpoint = new URL(env.RELEASE_ARCHIVE_UPLOAD_URL);
    approved = new URL(env.RELEASE_ARCHIVE_UPLOAD_ALLOWED_ORIGIN);
  } catch {
    throw new Error("archive upload requires an HTTPS URL and approved origin");
  }
  if (endpoint.protocol !== "https:" || approved.protocol !== "https:"
      || endpoint.username || endpoint.password || endpoint.hash
      || approved.username || approved.password || approved.hash || approved.search
      || approved.pathname !== "/" || endpoint.origin !== approved.origin) {
    throw new Error("archive upload destination is outside the approved HTTPS origin");
  }
  if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > ARCHIVE_UPLOAD_TIMEOUT_MS) {
    throw new Error("invalid archive upload deadline");
  }
  // Read at most the existing archive budget from one regular-file descriptor.
  // This also bounds growth between stat and read without following a symlink.
  const fd = fs.openSync(archivePath, fs.constants.O_RDONLY | fs.constants.O_NOFOLLOW | fs.constants.O_NONBLOCK);
  let body;
  try {
    const info = fs.fstatSync(fd);
    if (!info.isFile() || info.size > ARCHIVE_BUDGET_BYTES) throw new Error("archive upload file exceeds budget or is not regular");
    body = Buffer.alloc(info.size);
    let offset = 0;
    while (offset < body.length) {
      const count = fs.readSync(fd, body, offset, body.length - offset, offset);
      if (!count) throw new Error("archive changed while preparing upload");
      offset += count;
    }
    const after = fs.fstatSync(fd);
    if (after.size !== info.size || after.mtimeMs !== info.mtimeMs || after.ctimeMs !== info.ctimeMs) {
      throw new Error("archive changed while preparing upload");
    }
  } finally {
    fs.closeSync(fd);
  }
  const headers = { "Content-Type": "application/x-ndjson" };
  if (env.RELEASE_ARCHIVE_UPLOAD_TOKEN) headers.Authorization = `Bearer ${env.RELEASE_ARCHIVE_UPLOAD_TOKEN}`;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchImpl(endpoint.href, {
      method: "PUT", redirect: "error", signal: controller.signal, headers, body,
    });
    try {
      if (!response.ok) throw new Error("archive upload returned a non-success response");
    } finally {
      // Do not buffer an untrusted response body or leave a connection running.
      await response.body?.cancel();
    }
    return { uploaded: true };
  } catch {
    throw new Error("archive upload failed or exceeded its deadline");
  } finally {
    clearTimeout(timer);
    controller.abort();
  }
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
