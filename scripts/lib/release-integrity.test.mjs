import assert from "node:assert/strict";
import crypto from "node:crypto";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import { appendProspectiveArchive, uploadArchiveIfConfigured } from "../archive-release.mjs";
import { REQUIRED_RELEASE_ARTIFACTS, validateRelease } from "./release-integrity.mjs";

function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function sha(value) {
  return crypto.createHash("sha256").update(value).digest("hex");
}

function fixture() {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "risk-release-"));
  const identity = { code_identity: "test", config_sha256: "config" };
  const canonicalPayloads = {};
  for (const name of REQUIRED_RELEASE_ARTIFACTS) {
    if (name === "manifest.json") continue;
    const content = name === "prospective_evidence.json"
      ? { normalized_inputs: { metric: { raw: 1 } }, provenance: {}, model_identity: identity, score: {} }
      : { artifact: name, ...(name === "latest_snapshot.json" ? { date: "2026-07-16", dca_risk: 0.5 } : {}) };
    canonicalPayloads[name] = {
      generated_at: "2026-07-16T06:00:00Z",
      schema_version: "2.0.0",
      version: "v2",
      ...content,
    };
  }
  const contentDigests = Object.fromEntries(
    Object.entries(canonicalPayloads).map(([name, payload]) => [name, sha(canonicalJson(payload))]),
  );
  const releaseId = `web-v2-${sha(canonicalJson({ content_digests: contentDigests, model_identity: identity }))}`;
  const integrity = {};
  for (const [name, payload] of Object.entries(canonicalPayloads)) {
    const content = `${canonicalJson({
      release_id: releaseId,
      ...payload,
    })}\n`;
    fs.writeFileSync(path.join(root, name), content);
    integrity[name] = { bytes: Buffer.byteLength(content), sha256: sha(content) };
  }
  fs.writeFileSync(path.join(root, "manifest.json"), canonicalJson({
    release_id: releaseId,
    generated_at: "2026-07-16T06:00:00Z",
    artifacts: REQUIRED_RELEASE_ARTIFACTS,
    integrity,
    release_basis: { content_digests: contentDigests, model_identity: identity },
  }));
  return root;
}

test("validateRelease rejects mixed, modified, and unexpected artifacts", () => {
  const root = fixture();
  assert.match(validateRelease(root).release_id, /^web-v2-[a-f0-9]{64}$/);
  fs.appendFileSync(path.join(root, "latest_snapshot.json"), " ");
  assert.throws(() => validateRelease(root), /integrity mismatch/);
  fs.writeFileSync(path.join(root, "latest_snapshot.json"), fs.readFileSync(path.join(fixture(), "latest_snapshot.json")));
  fs.writeFileSync(path.join(root, "unexpected.json"), "{}");
  assert.throws(() => validateRelease(root), /unexpected artifacts/);
});

test("prospective archive deduplicates releases, rejects collisions, and enforces budget", () => {
  const root = fixture();
  const archivePath = path.join(os.tmpdir(), `risk-archive-${crypto.randomUUID()}.ndjson`);
  const first = appendProspectiveArchive({ releaseRoot: root, archivePath, budgetBytes: 100_000 });
  const second = appendProspectiveArchive({ releaseRoot: root, archivePath, budgetBytes: 100_000 });
  assert.equal(first.appended, true);
  assert.equal(second.appended, false);
  const archived = JSON.parse(fs.readFileSync(archivePath, "utf8").trim());
  assert.deepEqual(archived.normalized_inputs, { metric: { raw: 1 } });
  const tampered = { ...archived, content_digests: { ...archived.content_digests, "latest_snapshot.json": "different" } };
  fs.writeFileSync(archivePath, `${JSON.stringify(tampered)}\n`);
  assert.throws(() => appendProspectiveArchive({ releaseRoot: root, archivePath, budgetBytes: 100_000 }), /collision/);
  assert.throws(
    () => appendProspectiveArchive({ releaseRoot: root, archivePath: `${archivePath}.tiny`, budgetBytes: 1 }),
    /budget exceeded/,
  );
});

test("archive upload boundary is a no-op without configuration", async () => {
  assert.deepEqual(await uploadArchiveIfConfigured({ archivePath: "unused", env: {} }), {
    uploaded: false,
    reason: "not_configured",
  });
});

test("archive upload approves exact HTTPS origin before reading or sending credentials", async () => {
  for (const [url, origin] of [
    ["http://archive.example/upload", "https://archive.example"],
    ["https://archive.example/upload", undefined],
    ["https://attacker.example/upload", "https://archive.example"],
    ["https://archive.example.evil/upload", "https://archive.example"],
    ["https://user:secret@archive.example/upload", "https://archive.example"],
    ["https://archive.example/upload#secret", "https://archive.example"],
    ["https://archive.example/upload", "https://archive.example/path"],
    ["https://archive.example/upload", "https://archive.example?token=secret"],
  ]) {
    let called = false;
    await assert.rejects(uploadArchiveIfConfigured({
      archivePath: "must-not-be-read",
      env: { RELEASE_ARCHIVE_UPLOAD_URL: url, RELEASE_ARCHIVE_UPLOAD_ALLOWED_ORIGIN: origin,
        RELEASE_ARCHIVE_UPLOAD_TOKEN: "dummy-token" },
      fetchImpl: async () => { called = true; throw new Error("must not send"); },
    }), /HTTPS|approved/);
    assert.equal(called, false);
  }
});

test("archive upload is bounded, never follows redirects and cancels response bodies", async (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "risk-upload-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const archivePath = path.join(root, "archive.ndjson");
  fs.writeFileSync(archivePath, '{}\n');
  const env = { RELEASE_ARCHIVE_UPLOAD_URL: "https://archive.example/upload",
    RELEASE_ARCHIVE_UPLOAD_ALLOWED_ORIGIN: "https://archive.example",
    RELEASE_ARCHIVE_UPLOAD_TOKEN: "dummy-token" };
  let calls = 0;
  let cancelled = false;
  const result = await uploadArchiveIfConfigured({ archivePath, env, fetchImpl: async (url, options) => {
    calls++;
    assert.equal(url, env.RELEASE_ARCHIVE_UPLOAD_URL);
    assert.equal(options.redirect, "error");
    assert.equal(options.headers.Authorization, "Bearer dummy-token");
    assert.equal(options.body.toString(), '{}\n');
    assert.equal(options.signal.aborted, false);
    return { ok: true, body: { cancel: async () => { cancelled = true; } } };
  } });
  assert.deepEqual(result, { uploaded: true });
  assert.equal(calls, 1);
  assert.equal(cancelled, true);
  await assert.rejects(uploadArchiveIfConfigured({ archivePath, env, timeoutMs: 5,
    fetchImpl: async (_url, options) => new Promise((_resolve, reject) => {
      options.signal.addEventListener("abort", () => reject(new Error("dummy timeout")), { once: true });
    }),
  }), /deadline/);
  await assert.rejects(uploadArchiveIfConfigured({ archivePath, env, fetchImpl: async () => ({ ok: false }) }), /failed/);
  // Redirect rejection is the fetch contract, independently asserted above.
  await assert.rejects(uploadArchiveIfConfigured({ archivePath, env,
    fetchImpl: async () => { throw new Error("redirect to secret-destination?token=dummy-token"); },
  }), error => error.message === "archive upload failed or exceeded its deadline");
  const symlink = path.join(root, "link");
  fs.symlinkSync(archivePath, symlink);
  await assert.rejects(uploadArchiveIfConfigured({ archivePath: symlink, env,
    fetchImpl: async () => { assert.fail("symlink must not reach transport"); },
  }));
});

test("oversized archive is withheld before allocation or transport", async (t) => {
  const root = fs.mkdtempSync(path.join(os.tmpdir(), "risk-upload-budget-"));
  t.after(() => fs.rmSync(root, { recursive: true, force: true }));
  const archivePath = path.join(root, "archive.ndjson");
  fs.writeFileSync(archivePath, '{}\n');
  // No huge file/fixture: only the trusted metadata result is made oversized.
  const original = fs.fstatSync;
  const stat = t.mock.method(fs, "fstatSync", fd => {
    const info = original(fd);
    info.size = 250_000_001;
    return info;
  });
  await assert.rejects(uploadArchiveIfConfigured({ archivePath,
    env: { RELEASE_ARCHIVE_UPLOAD_URL: "https://archive.example/upload",
      RELEASE_ARCHIVE_UPLOAD_ALLOWED_ORIGIN: "https://archive.example" },
    fetchImpl: async () => { assert.fail("oversized archive must not reach transport"); },
  }), /exceeds budget/);
  assert.equal(stat.mock.callCount(), 1);
});
