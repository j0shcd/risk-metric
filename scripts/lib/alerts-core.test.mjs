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

test("computeZone respects the watched side at both endpoints", async () => {
  assert.equal(computeZone(0, 0.25, 0.75, "high"), "neutral");
  assert.equal(computeZone(1, 0.25, 0.75, "low"), "neutral");
  assert.equal(computeZone(0, 0.25, 0.75, "both"), "buy");
  assert.equal(computeZone(1, 0.25, 0.75, "both"), "sell");
  assert.equal(computeZone(0.75, 0.25, 0.75, "high"), "sell");
  assert.equal(computeZone(0.25, 0.25, 0.75, "low"), "buy");
  for (const [watch, risk] of [["high", 0], ["low", 1]]) {
    let sends = 0;
    const result = await dispatchAlerts({
      risk,
      subscribers: [{ id: 1, watch, buy_threshold: 0.25, sell_threshold: 0.75, last_zone: null }],
      siteUrl: "https://example.com",
      send: async () => { sends += 1; },
      now: () => "2026-11-05T06:00:00Z",
    });
    assert.equal(sends, 0);
    assert.equal(result.emailsSent, 0);
    assert.deepEqual(result.updates, []);
  }
});

test("buildAlertEmail uses whole-number readings and low/high marks", () => {
  const subscriber = { buy_threshold: 0.25, sell_threshold: 0.75, unsubscribe_token: "unsubscribe-token" };
  for (const [zone, risk, n, direction, mark, threshold] of [
    ["buy", 0.184, 18, "at or below", "low", 25],
    ["sell", 0.806, 81, "at or above", "high", 75],
  ]) {
    const email = buildAlertEmail({ subscriber, risk, date: "2026-07-15", zone, siteUrl: "https://example.com/" });
    assert.equal(email.subject, `Bitcoin risk reading is ${n}, ${direction} your ${mark} mark of ${threshold}`);
    assert.match(email.html, new RegExp(`<p>The Bitcoin risk reading for 2026-07-15 is ${n} out of 100.</p>`));
    assert.ok(email.html.includes(`<p>That is ${direction} the ${mark} mark of ${threshold} you asked to hear about.</p>`));
    assert.ok(email.html.includes("<p>The reading describes how today compares with history. It is not a signal to buy or sell.</p>"));
    assert.match(email.html, />Open Risk Metric<\/a>/);
    assert.match(email.html, /https:\/\/example\.com\/api\/unsubscribe\?token=unsubscribe-token/);
    assert.doesNotMatch(email.subject + email.html, /dca_risk|accumulate|sell threshold|0\.25|0\.75|0\.18|0\.80/);
  }
  const noDate = buildAlertEmail({ subscriber, risk: 0.18, zone: "buy", siteUrl: "https://example.com" });
  assert.ok(noDate.html.includes("<p>The Bitcoin risk reading is 18 out of 100.</p>"));
  const escaped = buildAlertEmail({ subscriber, risk: 0.18, date: '<bad & "date">', zone: "buy", siteUrl: "https://example.com" });
  assert.ok(escaped.html.includes("&lt;bad &amp; &quot;date&quot;&gt;"));
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
