import { beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("../functions/api/_lib/resend.mjs", () => ({
  sendEmail: vi.fn(async () => ({})),
}));

import { onRequestPost as subscribe } from "../functions/api/subscribe.js";
import { onRequestGet as confirmLanding } from "../functions/api/confirm.js";
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
    expect(update.params[2]).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(update.params[3]).toMatch(/^[A-Za-z0-9_-]{43}$/);
    expect(update.params[4]).toBe(7);
    const limiterBuckets = calls
      .filter((call) => call.sql.includes("INSERT OR IGNORE INTO confirmation_send_limits"))
      .map((call) => call.params[0]);
    expect(limiterBuckets.some((bucket) => bucket.includes(":domain:"))).toBe(true);
    expect(limiterBuckets.some((bucket) => bucket.endsWith(":global"))).toBe(true);
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
