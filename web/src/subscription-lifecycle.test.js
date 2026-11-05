import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../functions/api/_lib/resend.mjs", () => ({
  sendEmail: vi.fn(async () => ({})),
}));

import { onRequestPost as subscribe } from "../functions/api/subscribe.js";
import { sendEmail } from "../functions/api/_lib/resend.mjs";
import { onRequestPost as confirm, onRequestGet as confirmLanding } from "../functions/api/confirm.js";
import { onRequestGet as unsubscribeLanding, onRequestPost as unsubscribe } from "../functions/api/unsubscribe.js";

function request(body) {
  return new Request("https://risk.example/api/subscribe", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

describe("subscription lifecycle", () => {
  beforeEach(() => vi.clearAllMocks());

  it("rotates the unsubscribe token and clears the alert zone on resubscription", async () => {
    const calls = [];
    const env = {
      RESEND_API_KEY: "test-key",
      DB: {
        prepare(sql) {
          return {
            bind(...params) {
              calls.push({ sql, params });
              return {
                first: async () => ({ id: 7, status: "unsubscribed", unsubscribe_token: "old-token" }),
                run: async () => ({ success: true, meta: { changes: 1 } }),
              };
            },
          };
        },
      },
    };

    const response = await subscribe({
      request: request({ email: "user@example.com", buyThreshold: 0.2, sellThreshold: 0.8, website: "" }),
      env,
    });

    expect(response.status).toBe(200);
    const update = calls.find((call) => call.sql.includes("last_zone = NULL"));
    expect(update.sql).toContain("unsubscribe_token = NULL, unsubscribe_token_hash = ?");
    expect(update.params[2]).toBe("both");
    expect(update.sql).toContain("pending_watch = NULL");
    expect(update.params[3]).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(update.params[4]).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(update.params[5]).toBe(7);
    const limiterBuckets = calls
      .filter((call) => call.sql.includes("INSERT OR IGNORE INTO confirmation_send_limits"))
      .map((call) => call.params[0]);
    expect(limiterBuckets.some((bucket) => bucket.includes(":domain:"))).toBe(true);
    expect(limiterBuckets.some((bucket) => bucket.endsWith(":global"))).toBe(true);
  });

  function fakeD1(existing = null) {
    const calls = [];
    const env = {
      RESEND_API_KEY: "test-key",
      DB: {
        prepare(sql) {
          return {
            bind(...params) {
              calls.push({ sql, params });
              return {
                first: async () => existing,
                run: async () => ({ success: true, meta: { changes: 1 } }),
              };
            },
          };
        },
      },
    };
    return { calls, env };
  }

  it.each([
    ["high", "rises to 75 or above"],
    ["low", "drops to 25 or below"],
    ["both", "drops to 25 or below, or rises to 75 or above"],
    [undefined, "drops to 25 or below, or rises to 75 or above"],
  ])("stores watch %s with real thresholds and the matching confirmation clause", async (watch, clause) => {
    const { env, calls } = fakeD1();
    const response = await subscribe({
      request: request({ email: "user@example.com", watch, buyThreshold: 0.25, sellThreshold: 0.75, website: "" }), env,
    });
    expect(response.status).toBe(200);
    const insert = calls.find(({ sql }) => sql.includes("INSERT OR IGNORE INTO subscribers"));
    expect(insert.sql).toContain("buy_threshold, sell_threshold, watch");
    expect(insert.params.slice(0, 4)).toEqual(["user@example.com", 0.25, 0.75, watch ?? "both"]);
    const html = sendEmail.mock.calls[0][0].html;
    expect(html).toContain(`You asked for an email when the Bitcoin risk reading (0 to 100) ${clause}.`);
    expect(html).not.toMatch(/dca_risk|accumulate|sell threshold|0\.25|0\.75/);
  });

  it.each(["invalid", "", null, 1])("rejects invalid watch %s before touching D1", async (watch) => {
    const { env, calls } = fakeD1();
    const response = await subscribe({ request: request({ email: "user@example.com", watch, buyThreshold: 0.25, sellThreshold: 0.75 }), env });
    expect(response.status).toBe(400);
    expect((await response.json()).error).toBe('Watch must be "both", "high", or "low".');
    expect(calls).toHaveLength(0);
    expect(sendEmail).not.toHaveBeenCalled();
  });

  it("stages watch for an active subscriber and applies and clears it on confirmation", async () => {
    const subscriber = { id: 7, status: "active", buy_threshold: 0.2, sell_threshold: 0.8, watch: "both" };
    const { env, calls } = fakeD1(subscriber);
    const response = await subscribe({
      request: request({ email: "user@example.com", watch: "high", buyThreshold: 0.25, sellThreshold: 0.75, website: "" }), env,
    });
    expect(response.status).toBe(200);
    const staged = calls.find(({ sql }) => sql.includes("pending_buy_threshold = ?"));
    expect(staged.sql).toContain("pending_sell_threshold = ?, pending_watch = ?");
    expect(staged.params.slice(0, 3)).toEqual([0.25, 0.75, "high"]);
    expect(staged.params[4]).toBe(7);
    expect(staged.sql).not.toMatch(/SET buy_threshold/);
    expect(sendEmail.mock.calls[0][0].html).toContain("reading (0 to 100) rises to 75 or above.");
    Object.assign(subscriber, { pending_buy_threshold: staged.params[0], pending_sell_threshold: staged.params[1], pending_watch: staged.params[2] });
    const confirmed = await confirm({ request: request({ token: "confirmation-token" }), env });
    expect(confirmed.status).toBe(200);
    expect(await confirmed.text()).toContain("You'll get an email when the reading rises to 75 or above.");
    const applied = calls.find(({ sql }) => sql.includes("SET buy_threshold = ?"));
    expect(applied.params.slice(0, 3)).toEqual([0.25, 0.75, "high"]);
    expect(applied.sql).toContain("pending_buy_threshold = NULL, pending_sell_threshold = NULL, pending_watch = NULL");
    expect(applied.sql).toContain("last_zone = NULL");
  });

  it.each([
    ["both", "drops to 25 or below, or rises to 75 or above"],
    ["high", "rises to 75 or above"],
    ["low", "drops to 25 or below"],
  ])("confirmation displays the applied %s watch for new subscribers", async (watch, clause) => {
    const { env } = fakeD1({ id: 7, status: "pending", watch, buy_threshold: 0.25, sell_threshold: 0.75, pending_buy_threshold: null, pending_sell_threshold: null, pending_watch: null });
    const response = await confirm({ request: request({ token: "confirmation-token" }), env });
    const html = await response.text();
    expect(html).toContain(`You'll get an email when the reading ${clause}.`);
    expect(html).not.toMatch(/0\.25|0\.75|dca_risk|accumulate|sell threshold/);
  });

  it("GET only renders an unsubscribe landing page and POST consumes the token", async () => {
    const calls = [];
    const env = {
      DB: {
        prepare(sql) {
          return {
            bind(...params) {
              calls.push({ sql, params });
              return { run: async () => ({ meta: { changes: 1 } }) };
            },
          };
        },
      },
    };

    const landing = await unsubscribeLanding({
      request: new Request("https://risk.example/api/unsubscribe?token=one-use-token"),
      env,
    });
    expect(landing.status).toBe(200);
    expect(await landing.text()).toContain('method="post"');
    expect(calls).toHaveLength(0);

    const response = await unsubscribe({
      request: new Request("https://risk.example/api/unsubscribe", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token: "one-use-token" }),
      }),
      env,
    });
    expect(response.status).toBe(200);
    expect(calls[0].sql).toContain("unsubscribe_token_hash = NULL");
    expect(calls[0].params[0]).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(calls[0].params[1]).toBe("");
  });

  it("GET only renders a confirmation landing page", async () => {
    const env = {
      DB: { prepare: vi.fn(() => { throw new Error("GET must not touch D1"); }) },
    };
    const response = await confirmLanding({
      request: new Request("https://risk.example/api/confirm?token=one-use-token"),
      env,
    });
    expect(response.status).toBe(200);
    expect(await response.text()).toContain('method="post"');
    expect(env.DB.prepare).not.toHaveBeenCalled();
  });

  it("returns the generic response without sending inside the address cooldown", async () => {
    const calls = [];
    const env = {
      DB: {
        prepare(sql) {
          calls.push(sql);
          return {
            bind() {
              return {
                first: async () => ({ id: 7, status: "active", last_confirmation_sent_at: new Date().toISOString() }),
                run: async () => ({ meta: { changes: 0 } }),
              };
            },
          };
        },
      },
    };
    const response = await subscribe({
      request: request({ email: "user@example.com", buyThreshold: 0.2, sellThreshold: 0.8, website: "" }),
      env,
    });
    expect(await response.json()).toEqual({ ok: true, message: "Check your inbox to confirm your subscription." });
    expect(calls).toHaveLength(2);
  });
});
