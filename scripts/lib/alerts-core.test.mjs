import assert from "node:assert/strict";
import test from "node:test";
import { buildAlertEmail, computeZone, dispatchAlerts, evaluateTransition } from "./alerts-core.mjs";

test("computeZone uses inclusive buy and sell boundaries", () => {
  assert.equal(computeZone(0, 0, 1), "buy");
  assert.equal(computeZone(0.25, 0.25, 0.75), "buy");
  assert.equal(computeZone(0.2501, 0.25, 0.75), "neutral");
  assert.equal(computeZone(0.7499, 0.25, 0.75), "neutral");
  assert.equal(computeZone(0.75, 0.25, 0.75), "sell");
  assert.equal(computeZone(1, 0, 1), "sell");
});

test("evaluateTransition sends only on changed buy or sell zones", () => {
  assert.deepEqual(evaluateTransition(null, "buy"), {
    previousZone: "neutral",
    newZone: "buy",
    changed: true,
    shouldAlert: true,
  });
  assert.equal(evaluateTransition("buy", "buy").shouldAlert, false);
  assert.deepEqual(evaluateTransition("buy", "neutral"), {
    previousZone: "buy",
    newZone: "neutral",
    changed: true,
    shouldAlert: false,
  });
  assert.equal(evaluateTransition("neutral", "sell").shouldAlert, true);
  assert.equal(evaluateTransition("sell", "neutral").shouldAlert, false);
  assert.equal(evaluateTransition("sell", "sell").changed, false);
});

test("buildAlertEmail includes threshold, dashboard, and unsubscribe link", () => {
  const subscriber = {
    buy_threshold: 0.25,
    sell_threshold: 0.75,
    unsubscribe_token: "unsubscribe-token",
  };

  const buy = buildAlertEmail({
    subscriber,
    risk: 0.18,
    date: "2026-07-15",
    zone: "buy",
    siteUrl: "https://example.com/",
  });
  assert.match(buy.subject, /0\.18/);
  assert.match(buy.subject, /0\.25/);
  assert.match(buy.html, /2026-07-15/);
  assert.match(buy.html, /https:\/\/example\.com\/api\/unsubscribe\?token=unsubscribe-token/);

  const sell = buildAlertEmail({
    subscriber,
    risk: 0.8,
    date: "2026-07-15",
    zone: "sell",
    siteUrl: "https://example.com",
  });
  assert.match(sell.subject, /0\.80/);
  assert.match(sell.subject, /0\.75/);
  assert.match(sell.html, /sell threshold/);
});

test("dispatchAlerts keeps last_zone unchanged when a send fails so the next run retries", async () => {
  const subscribers = [
    { id: 1, email: "ok@example.com", buy_threshold: 0.25, sell_threshold: 0.75, last_zone: null, unsubscribe_token: "t1" },
    { id: 2, email: "broken@example.com", buy_threshold: 0.25, sell_threshold: 0.75, last_zone: null, unsubscribe_token: "t2" },
    { id: 3, email: "rearmed@example.com", buy_threshold: 0.1, sell_threshold: 0.75, last_zone: "buy", unsubscribe_token: "t3" },
    { id: 4, email: "steady@example.com", buy_threshold: 0.05, sell_threshold: 0.1, last_zone: "sell", unsubscribe_token: "t4" },
  ];

  const result = await dispatchAlerts({
    risk: 0.18,
    date: "2026-07-15",
    subscribers,
    siteUrl: "https://example.com",
    send: async ({ to }) => {
      if (to === "broken@example.com") throw new Error("resend down");
    },
    now: () => "2026-07-15T06:00:00Z",
  });

  // Subscriber 1: entered buy zone, email sent, zone recorded.
  // Subscriber 2: send failed — must NOT appear in updates, so tomorrow retries.
  // Subscriber 3: buy → neutral is silent but still re-arms last_zone.
  // Subscriber 4: sell → sell (0.18 >= 0.1), unchanged, untouched.
  assert.deepEqual(result.updates, [
    { id: 1, zone: "buy", alerted: true, alertedAt: "2026-07-15T06:00:00Z" },
    { id: 3, zone: "neutral", alerted: false },
  ]);
  assert.equal(result.failures.length, 1);
  assert.equal(result.failures[0].id, 2);
  assert.equal(result.emailsSent, 1);
  assert.equal(result.zoneChanges, 3);
});

test("dispatchAlerts records an already-sent release delivery without resending", async () => {
  let sends = 0;
  const result = await dispatchAlerts({
    risk: 0.2,
    date: "2026-07-16",
    subscribers: [
      { id: 1, email: "user@example.com", buy_threshold: 0.25, sell_threshold: 0.75, last_zone: null },
    ],
    siteUrl: "https://example.com",
    prepare: async () => ({ skip: true, sentAt: "2026-07-16T06:00:00Z" }),
    send: async () => { sends += 1; },
    now: () => "2026-07-16T06:01:00Z",
  });

  assert.equal(sends, 0);
  assert.equal(result.emailsSent, 0);
  assert.deepEqual(result.updates, [
    { id: 1, zone: "buy", alerted: true, alertedAt: "2026-07-16T06:00:00Z" },
  ]);
});
