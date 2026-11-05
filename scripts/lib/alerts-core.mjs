export function computeZone(risk, buyThreshold, sellThreshold, watch = "both") {
  if ((watch === "both" || watch === "low") && risk <= buyThreshold) return "buy";
  if ((watch === "both" || watch === "high") && risk >= sellThreshold) return "sell";
  return "neutral";
}

export function evaluateTransition(lastZone, newZone) {
  const previousZone = lastZone ?? "neutral";
  const changed = previousZone !== newZone;
  return {
    previousZone,
    newZone,
    changed,
    shouldAlert: changed && (newZone === "buy" || newZone === "sell"),
  };
}

export function formatRisk(risk) {
  return String(Math.round(Number(risk) * 100));
}

export function buildAlertEmail({ subscriber, risk, date, zone, siteUrl }) {
  const dashboardUrl = siteUrl.replace(/\/+$/, "");
  const unsubscribeUrl = `${dashboardUrl}/api/unsubscribe?token=${encodeURIComponent(subscriber.unsubscribe_token)}`;
  const riskText = formatRisk(risk);

  const low = zone === "buy";
  const direction = low ? "at or below" : "at or above";
  const mark = low ? "low" : "high";
  const threshold = formatRisk(low ? subscriber.buy_threshold : subscriber.sell_threshold);
  return {
    subject: `Bitcoin risk reading is ${riskText}, ${direction} your ${mark} mark of ${threshold}`,
    html: `
      <p>The Bitcoin risk reading${date ? ` for ${escapeHtml(date)}` : ""} is ${escapeHtml(riskText)} out of 100.</p>
      <p>That is ${direction} the ${mark} mark of ${escapeHtml(threshold)} you asked to hear about.</p>
      <p>The reading describes how today compares with history. It is not a signal to buy or sell.</p>
      <p><a href="${escapeHtml(dashboardUrl)}">Open Risk Metric</a></p>
      <p><a href="${escapeHtml(unsubscribeUrl)}">Unsubscribe</a></p>
    `,
  };
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (char) => {
    const entities = { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" };
    return entities[char];
  });
}

export async function dispatchAlerts({ risk, date, subscribers, siteUrl, prepare = async ({ subscriber }) => ({ subscriber }), send, now }) {
  const updates = [];
  const failures = [];
  let zoneChanges = 0;
  let emailsSent = 0;

  for (const subscriber of subscribers) {
    const zone = computeZone(risk, subscriber.buy_threshold, subscriber.sell_threshold, subscriber.watch);
    const transition = evaluateTransition(subscriber.last_zone, zone);

    if (!transition.changed) continue;

    zoneChanges += 1;
    const update = { id: subscriber.id, zone, alerted: false };

    if (transition.shouldAlert) {
      try {
        const prepared = await prepare({ subscriber, zone });
        if (prepared?.skip) {
          update.alerted = true;
          update.alertedAt = prepared.sentAt ?? now();
          updates.push(update);
          continue;
        }
        const preparedSubscriber = prepared?.subscriber ?? subscriber;
        const email = buildAlertEmail({ subscriber: preparedSubscriber, risk, date, zone, siteUrl });
        const result = await send({
          subscriberId: subscriber.id,
          zone,
          deliveryId: prepared?.deliveryId,
          idempotencyKey: prepared?.idempotencyKey,
          to: subscriber.email,
          ...email,
        });
        if (result?.sent !== false) emailsSent += 1;
        update.alerted = true;
        update.alertedAt = now();
      } catch (error) {
        failures.push({ id: subscriber.id, error });
        // Leave last_zone unchanged so the next run retries this alert.
        continue;
      }
    }

    updates.push(update);
  }

  return { updates, failures, zoneChanges, emailsSent };
}
