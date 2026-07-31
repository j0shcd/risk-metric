export function computeZone(risk, buyThreshold, sellThreshold) {
  if (risk <= buyThreshold) return "buy";
  if (risk >= sellThreshold) return "sell";
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
  return Number(risk).toFixed(2);
}

export function buildAlertEmail({ subscriber, risk, date, zone, siteUrl }) {
  const dashboardUrl = siteUrl.replace(/\/+$/, "");
  const unsubscribeUrl = `${dashboardUrl}/api/unsubscribe?token=${encodeURIComponent(subscriber.unsubscribe_token)}`;
  const riskText = formatRisk(risk);

  if (zone === "buy") {
    return {
      subject: `Risk alert: dca_risk ${riskText} - at/below your accumulate threshold (${subscriber.buy_threshold})`,
      html: `
        <p>dca_risk is ${riskText}${date ? ` for ${escapeHtml(date)}` : ""}.</p>
        <p>It is at or below your accumulate threshold of ${escapeHtml(subscriber.buy_threshold)}.</p>
        <p><a href="${escapeHtml(dashboardUrl)}">Open the dashboard</a></p>
        <p><a href="${escapeHtml(unsubscribeUrl)}">Unsubscribe</a></p>
      `,
    };
  }

  return {
    subject: `Risk alert: dca_risk ${riskText} - at/above your sell threshold (${subscriber.sell_threshold})`,
    html: `
      <p>dca_risk is ${riskText}${date ? ` for ${escapeHtml(date)}` : ""}.</p>
      <p>It is at or above your sell threshold of ${escapeHtml(subscriber.sell_threshold)}.</p>
      <p><a href="${escapeHtml(dashboardUrl)}">Open the dashboard</a></p>
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
    const zone = computeZone(risk, subscriber.buy_threshold, subscriber.sell_threshold);
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
