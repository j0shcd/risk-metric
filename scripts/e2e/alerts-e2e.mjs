// Run from the repo root: node scripts/e2e/alerts-e2e.mjs
// Offline only: real handlers and sender, SQLite D1, captured Resend requests.
// Each scenario owns a temporary DB. Sender children use that same DB file and
// a synthetic, fully hashed release under their temporary working directory.
// No production modules, repository data, credentials, or services are changed.
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync, execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { DatabaseSync } from "node:sqlite";
import { fileURLToPath } from "node:url";
import * as subscribe from "../../web/functions/api/subscribe.js";
import * as confirm from "../../web/functions/api/confirm.js";
import * as unsubscribe from "../../web/functions/api/unsubscribe.js";
import { hashToken } from "../../web/functions/api/_lib/tokens.mjs";
import { REQUIRED_RELEASE_ARTIFACTS } from "../lib/release-integrity.mjs";

const scriptPath = fileURLToPath(import.meta.url);
const repo = path.resolve(path.dirname(scriptPath), "../..");
const senderUrl = new URL("../send-alerts.mjs", import.meta.url).href;
const site = "https://alerts-e2e.invalid";
const d1Url = "https://api.cloudflare.com/client/v4/accounts/e2e-account/d1/database/e2e-db/query";
const fakeEnv = {
  CLOUDFLARE_API_TOKEN: "offline-test-token",
  CLOUDFLARE_ACCOUNT_ID: "e2e-account",
  D1_DATABASE_ID: "e2e-db",
  RESEND_API_KEY: "offline-resend-key",
  ALERT_TOKEN_ENCRYPTION_KEY: "offline-encryption-key",
  SITE_URL: site,
  ALERT_FROM_EMAIL: "Risk Metric <alerts@example.invalid>",
  ALLOW_LEGACY_PLAINTEXT_TOKENS: "false",
};

function execute(db, sql, params = []) {
  const statement = db.prepare(sql);
  if (statement.columns().length) {
    return { success: true, results: statement.all(...params), meta: { changes: 0 } };
  }
  const { changes } = statement.run(...params);
  return { success: true, results: [], meta: { changes: Number(changes) } };
}

function d1Binding(db) {
  return {
    prepare(sql) {
      const bound = (params) => ({
        bind: (...values) => bound(values),
        first: async () => db.prepare(sql).get(...params) ?? null,
        run: async () => execute(db, sql, params),
        all: async () => execute(db, sql, params),
      });
      return bound([]);
    },
    // None of the current Pages handlers use batch; fail visibly if that changes.
  };
}

function interceptFetch(db, record) {
  return async (input, init) => {
    const request = new Request(input, init);
    assert.equal(request.method, "POST", `Unexpected fetch method: ${request.method}`);
    if (request.url === d1Url) {
      assert.equal(request.headers.get("authorization"), `Bearer ${fakeEnv.CLOUDFLARE_API_TOKEN}`);
      const { sql, params } = await request.json();
      try {
        return Response.json({ success: true, result: [execute(db, sql, params)], errors: [] });
      } catch (error) {
        return Response.json({ success: false, result: [], errors: [{ message: error.message }] }, { status: 400 });
      }
    }
    if (request.url === "https://api.resend.com/emails") {
      assert.equal(request.headers.get("authorization"), `Bearer ${fakeEnv.RESEND_API_KEY}`);
      const { to, subject, html, from } = await request.json();
      assert.equal(from, fakeEnv.ALERT_FROM_EMAIL);
      assert.equal(typeof to, "string");
      assert.equal(typeof subject, "string");
      assert.equal(typeof html, "string");
      record({ to, subject, html, headers: Object.fromEntries(request.headers) });
      return Response.json({ id: "offline-resend-id" });
    }
    throw new Error(`Offline harness blocked unexpected fetch: ${request.url}`);
  };
}

// The production entry point starts main() without exporting/awaiting it.
// A child process lets its asynchronous work settle naturally, then exposes its
// real exit status. Install the interceptor before importing the unchanged file.
if (process.argv[2] === "--sender-worker") {
  const [, , , dbPath, mailPath] = process.argv;
  const db = new DatabaseSync(dbPath);
  globalThis.fetch = interceptFetch(db, (email) => {
    fs.appendFileSync(mailPath, `${JSON.stringify(email)}\n`);
  });
  process.once("exit", () => db.close());
  await import(senderUrl);
} else {
  await runScenarios();
}

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(",")}]`;
  if (value && typeof value === "object") {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}:${canonical(value[key])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

function sha(value) {
  return createHash("sha256").update(value).digest("hex");
}

function writeRelease(root, risk, releaseLabel) {
  const releaseRoot = path.join(root, "data/web/v2");
  fs.mkdirSync(releaseRoot, { recursive: true });
  const date = new Date().toISOString().slice(0, 10);
  const modelIdentity = { fixture: "alerts-e2e", release: releaseLabel };
  // Ancillary artifacts are synthetic: the production sender validates their
  // integrity and release identity, but only consumes the snapshot's risk/date.
  const payloads = Object.fromEntries(REQUIRED_RELEASE_ARTIFACTS
    .filter((name) => name !== "manifest.json")
    .map((name) => [name, {
      artifact: name,
      ...(name === "latest_snapshot.json" ? { date, dca_risk: risk } : {}),
    }]));
  const contentDigests = Object.fromEntries(Object.entries(payloads)
    .map(([name, payload]) => [name, sha(canonical(payload))]));
  const releaseBasis = { content_digests: contentDigests, model_identity: modelIdentity };
  const releaseId = `web-v2-${sha(canonical(releaseBasis))}`;
  const integrity = {};
  for (const [name, payload] of Object.entries(payloads)) {
    const content = `${canonical({ release_id: releaseId, ...payload })}\n`;
    fs.writeFileSync(path.join(releaseRoot, name), content);
    integrity[name] = { bytes: Buffer.byteLength(content), sha256: sha(content) };
  }
  fs.writeFileSync(path.join(releaseRoot, "manifest.json"), JSON.stringify({
    release_id: releaseId,
    artifacts: REQUIRED_RELEASE_ARTIFACTS,
    integrity,
    release_basis: releaseBasis,
  }));
  return releaseId;
}

function request(url, body) {
  return new Request(url, body === undefined ? undefined : {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(body),
  });
}

function emailLink(email, endpoint) {
  const links = [...email.html.matchAll(/href="([^"]+)"/g)]
    .map((match) => new URL(match[1].replaceAll("&amp;", "&")));
  const link = links.find((url) => url.pathname === `/api/${endpoint}`);
  assert.ok(link, `Missing ${endpoint} link in ${email.subject}`);
  assert.equal(link.origin, site);
  assert.ok(link.searchParams.get("token"), `Missing ${endpoint} token`);
  return link;
}

async function runScenarios() {
  const currentSchema = fs.readFileSync(path.join(repo, "infra/d1/schema.sql"), "utf8");
  const oldSchema = execFileSync("git", ["show", "198d3aa:infra/d1/schema.sql"], { cwd: repo, encoding: "utf8" });
  const migration = fs.readFileSync(path.join(repo, "infra/d1/migrations/0003_alert_watch.sql"), "utf8");
  const allEmails = [];
  let failures = 0;

  async function scenario(name, fn, legacy = false) {
    const root = fs.mkdtempSync(path.join(os.tmpdir(), "risk-alerts-e2e-"));
    const dbPath = path.join(root, "alerts.sqlite");
    const db = new DatabaseSync(dbPath);
    const originalFetch = globalThis.fetch;
    const emails = [];
    const record = (email) => {
      emails.push(email);
      allEmails.push({ scenario: name.split(" ")[0], ...email });
    };
    try {
      db.exec(legacy ? oldSchema : currentSchema);
      globalThis.fetch = interceptFetch(db, record);
      const env = { ...fakeEnv, DB: d1Binding(db) };
      const row = () => db.prepare("SELECT * FROM subscribers").get();
      async function signup(watch = "both", buyThreshold = 0.25, sellThreshold = 0.75) {
        const before = emails.length;
        const response = await subscribe.onRequestPost({ env, request: new Request(`${site}/api/subscribe`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: "reader@example.invalid", watch, buyThreshold, sellThreshold }),
        }) });
        assert.equal(response.status, 200);
        assert.equal((await response.json()).ok, true);
        assert.equal(emails.length, before + 1, "Subscribe must send exactly one confirmation");
        assert.equal(emails.at(-1).to, "reader@example.invalid");
        return emails.at(-1);
      }
      async function activate(email) {
        const link = emailLink(email, "confirm");
        const before = { ...row() };
        const landing = await confirm.onRequestGet({ env, request: request(link) });
        assert.equal(landing.status, 200);
        const html = await landing.text();
        assert.match(html, /<form method="post" action="\/api\/confirm">/);
        assert.ok(html.includes(`value="${link.searchParams.get("token")}"`));
        assert.deepEqual({ ...row() }, before, "GET confirmation must not change the subscription");
        const response = await confirm.onRequestPost({ env, request: request(link, { token: link.searchParams.get("token") }) });
        assert.equal(response.status, 200);
        const text = await response.text();
        assert.match(text, /You're subscribed|Thresholds updated/);
        assert.equal(row().status, "active");
        assert.equal(row().confirm_token_hash, null);
        return text;
      }
      function send(risk, label) {
        const releaseId = writeRelease(root, risk, label);
        const mailPath = path.join(root, "sender-emails.ndjson");
        fs.writeFileSync(mailPath, "");
        const child = spawnSync(process.execPath, [scriptPath, "--sender-worker", dbPath, mailPath], {
          cwd: root,
          // Never inherit real credentials, NODE_OPTIONS, or preloads.
          env: { ...fakeEnv },
          encoding: "utf8",
          timeout: 30_000,
        });
        const sent = fs.readFileSync(mailPath, "utf8").trim().split("\n").filter(Boolean).map(JSON.parse);
        sent.forEach(record);
        assert.ifError(child.error);
        assert.equal(child.status, 0, `Sender failed:\n${child.stdout}\n${child.stderr}`);
        assert.match(child.stdout, /alerts: \d+ active subscribers, \d+ zone changes, \d+ emails sent/);
        for (const email of sent) {
          assert.equal(email.to, "reader@example.invalid");
          assert.doesNotMatch(email.html, /dca_risk|accumulate/i);
          emailLink(email, "unsubscribe");
          assert.ok(email.headers["idempotency-key"].includes(releaseId));
        }
        return sent;
      }
      function alert(risk, label, subject) {
        const sent = send(risk, label);
        assert.equal(sent.length, subject ? 1 : 0, `Unexpected email count for risk ${risk}`);
        if (subject) assert.equal(sent[0].subject, subject);
        return sent[0];
      }
      await fn({ db, env, emails, row, signup, activate, send, alert });
      console.log(`PASS ${name}`);
    } catch (error) {
      failures += 1;
      console.log(`FAIL ${name}: ${error.stack}`);
    } finally {
      globalThis.fetch = originalFetch;
      db.close();
      fs.rmSync(root, { recursive: true, force: true });
    }
  }

  const low20 = "Bitcoin risk reading is 20, at or below your low mark of 25";
  const high80 = "Bitcoin risk reading is 80, at or above your high mark of 75";

  await scenario("a. fresh schema, watch both, confirmation, low/high, idempotency", async ({ db, row, signup, activate, alert }) => {
    const clause = "drops to 25 or below, or rises to 75 or above";
    const email = await signup();
    assert.equal(email.subject, "Confirm your risk alerts");
    assert.ok(email.html.includes(clause));
    assert.equal(row().status, "pending");
    assert.ok((await activate(email)).includes(clause), "Confirmed landing must describe both thresholds");
    assert.equal(row().watch, "both");
    const first = alert(0.2, "a-low", low20);
    assert.equal(row().last_zone, "buy");
    alert(0.2, "a-low");
    // Also exercise ledger idempotency if a retry lost the last_zone update.
    db.prepare("UPDATE subscribers SET last_zone = NULL").run();
    alert(0.2, "a-low");
    assert.equal(db.prepare("SELECT count(*) AS n FROM alert_deliveries WHERE status = 'sent'").get().n, 1);
    assert.equal(first.headers["idempotency-key"].endsWith(":1:buy"), true);
    alert(0.8, "a-high", high80);
    assert.equal(row().last_zone, "sell");
  });

  await scenario("b. watch high accepts reversed ignored mark; risk zero stays silent", async ({ row, signup, activate, alert }) => {
    const email = await signup("high", 0.25, 0.1);
    assert.match(email.html, /rises to 10 or above/);
    assert.doesNotMatch(email.html, /drops to/);
    await activate(email);
    assert.equal(row().watch, "high");
    alert(0, "b-zero");
    alert(0.5, "b-high", "Bitcoin risk reading is 50, at or above your high mark of 10");
  });

  await scenario("c. watch low ignores high readings and sends low alert", async ({ signup, activate, alert }) => {
    const email = await signup("low");
    assert.match(email.html, /drops to 25 or below/);
    assert.doesNotMatch(email.html, /rises to/);
    await activate(email);
    alert(1, "c-high");
    alert(0.1, "c-low", "Bitcoin risk reading is 10, at or below your low mark of 25");
  });

  await scenario("d. active update keeps old watch until confirmation, then applies new marks", async ({ db, row, signup, activate, alert }) => {
    await activate(await signup());
    // Advance persisted cooldown timestamps, without changing production clocks.
    db.prepare("UPDATE subscribers SET last_confirmation_sent_at = ?").run(new Date(Date.now() - 16 * 60_000).toISOString());
    const email = await signup("low", 0.35, 0.2);
    assert.equal(email.subject, "Confirm your new risk alert thresholds");
    assert.match(email.html, /drops to 35 or below/);
    assert.doesNotMatch(email.html, /rises to/);
    assert.equal(row().watch, "both");
    assert.equal(row().buy_threshold, 0.25);
    assert.equal(row().pending_watch, "low");
    alert(0.8, "d-before", high80);
    assert.match(await activate(email), /drops to 35 or below/);
    assert.equal(row().watch, "low");
    assert.equal(row().buy_threshold, 0.35);
    assert.equal(row().sell_threshold, 0.2);
    for (const key of ["pending_watch", "pending_buy_threshold", "pending_sell_threshold"]) assert.equal(row()[key], null);
    alert(0.8, "d-after-high");
    alert(0.3, "d-after-low", "Bitcoin risk reading is 30, at or below your low mark of 35");
  });

  await scenario("e. unsubscribe GET is safe, POST disables subsequent alerts", async ({ env, row, signup, activate, alert }) => {
    await activate(await signup());
    const email = alert(0.2, "e-low", low20);
    const link = emailLink(email, "unsubscribe");
    const before = { ...row() };
    const landing = await unsubscribe.onRequestGet({ env, request: request(link) });
    assert.equal(landing.status, 200);
    const html = await landing.text();
    assert.match(html, /<form method="post" action="\/api\/unsubscribe">/);
    assert.ok(html.includes(`value="${link.searchParams.get("token")}"`));
    assert.deepEqual({ ...row() }, before);
    const response = await unsubscribe.onRequestPost({ env, request: request(link, { token: link.searchParams.get("token") }) });
    assert.equal(response.status, 200);
    assert.match(await response.text(), /You're unsubscribed/);
    assert.equal(row().status, "unsubscribed");
    assert.equal(row().unsubscribe_token_hash, null);
    alert(0.8, "e-unsubscribed-high");
    alert(0.1, "e-unsubscribed-low");
  });

  async function insertLegacy(db) {
    const columns = db.prepare("PRAGMA table_info(subscribers)").all().map((column) => column.name);
    for (const column of ["confirm_token_hash", "unsubscribe_token_hash", "last_confirmation_sent_at", "confirmation_claimed_at"]) {
      assert.ok(columns.includes(column), `198d3aa lacks 0002 column ${column}`);
    }
    assert.ok(!columns.includes("watch"));
    assert.ok(!columns.includes("pending_watch"));
    const now = new Date().toISOString();
    db.prepare(`INSERT INTO subscribers (email, buy_threshold, sell_threshold, status,
      unsubscribe_token_hash, created_at, confirmed_at) VALUES (?, ?, ?, 'active', ?, ?, ?)`)
      .run("reader@example.invalid", 0.25, 0.75, await hashToken("old-unsubscribe-token"), now, now);
  }

  await scenario("f1. pre-0003 sender self-migrates and defaults existing subscriber to both", async ({ db, row, alert }) => {
    await insertLegacy(db);
    alert(0.2, "f1-low", low20);
    assert.equal(row().watch, "both");
    assert.equal(row().pending_watch, null);
    alert(0.8, "f1-high", high80);
  }, true);

  await scenario("f2. explicit 0003 migration defaults existing subscriber to both", async ({ db, row }) => {
    await insertLegacy(db);
    db.exec(migration);
    assert.equal(row().watch, "both");
    assert.equal(row().pending_watch, null);
  }, true);

  await scenario("f3. pre-0003 subscribe fails as documented (expected error)", async ({ db, env, emails }) => {
    assert.throws(() => db.prepare("SELECT watch FROM subscribers"), /no such column: watch/);
    await assert.rejects(() => subscribe.onRequestPost({ env, request: new Request(`${site}/api/subscribe`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "reader@example.invalid", watch: "both", buyThreshold: 0.25, sellThreshold: 0.75 }),
    }) }), (error) => {
      assert.match(error.message, /table subscribers has no column named watch/);
      console.log(`EXPECTED pre-0003 subscribe error: ${error.message}`);
      return true;
    });
    assert.equal(emails.length, 0);
    assert.equal(db.prepare("SELECT count(*) AS n FROM subscribers").get().n, 0);
  }, true);

  await scenario("g. invalid watch and reversed both thresholds return 400", async ({ env, db, emails }) => {
    for (const input of [
      { watch: "sideways", buyThreshold: 0.25, sellThreshold: 0.75 },
      { watch: "both", buyThreshold: 0.6, sellThreshold: 0.4 },
    ]) {
      const response = await subscribe.onRequestPost({ env, request: new Request(`${site}/api/subscribe`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: "reader@example.invalid", ...input }),
      }) });
      assert.equal(response.status, 400);
      assert.equal((await response.json()).ok, false);
    }
    assert.equal(emails.length, 0);
    assert.equal(db.prepare("SELECT count(*) AS n FROM subscribers").get().n, 0);
  });

  console.log(`Captured email subjects (${allEmails.length}):`);
  allEmails.forEach((email, index) => console.log(`EMAIL ${index + 1} [${email.scenario}] ${email.subject}`));
  console.log(`${failures ? "FAIL" : "PASS"} alerts E2E: ${9 - failures}/9 scenarios passed`);
  if (failures) process.exitCode = 1;
}
