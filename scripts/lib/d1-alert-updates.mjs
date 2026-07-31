const DEFAULT_MAX_PARAMS = 99;

export function buildUpdateStatement(updates) {
  if (updates.length === 0) {
    throw new Error("Cannot build a subscriber update statement without updates");
  }

  const lastZoneCases = [];
  const lastAlertCases = [];
  const wherePlaceholders = [];
  const params = [];

  for (const update of updates) {
    lastZoneCases.push("WHEN ? THEN ?");
    params.push(update.id, update.zone);
  }

  for (const update of updates) {
    if (update.alerted) {
      lastAlertCases.push("WHEN ? THEN ?");
      params.push(update.id, update.alertedAt);
    }
  }

  for (const update of updates) {
    wherePlaceholders.push("?");
    params.push(update.id);
  }

  const lastAlertSql =
    lastAlertCases.length > 0
      ? `last_alert_at = CASE id ${lastAlertCases.join(" ")} ELSE last_alert_at END`
      : "last_alert_at = last_alert_at";

  return {
    sql: `UPDATE subscribers
          SET last_zone = CASE id ${lastZoneCases.join(" ")} END,
              ${lastAlertSql}
          WHERE id IN (${wherePlaceholders.join(", ")})`,
    params,
  };
}

export function batchUpdateStatements(updates, maxParams = DEFAULT_MAX_PARAMS) {
  if (!Number.isInteger(maxParams) || maxParams < 1) {
    throw new Error("maxParams must be a positive integer");
  }

  const statements = [];
  let batch = [];

  for (const update of updates) {
    const candidate = [...batch, update];
    if (buildUpdateStatement(candidate).params.length <= maxParams) {
      batch = candidate;
      continue;
    }

    if (batch.length === 0) {
      throw new Error(`A subscriber update exceeds the D1 parameter limit of ${maxParams}`);
    }
    statements.push(buildUpdateStatement(batch));
    batch = [update];

    if (buildUpdateStatement(batch).params.length > maxParams) {
      throw new Error(`A subscriber update exceeds the D1 parameter limit of ${maxParams}`);
    }
  }

  if (batch.length > 0) statements.push(buildUpdateStatement(batch));
  return statements;
}

export function extractD1Results(response, body) {
  const results = Array.isArray(body?.result) ? body.result : [];
  const nestedFailure = results.length === 0 || results.some((result) => result?.success !== true);
  if (!response.ok || body?.success !== true || nestedFailure) {
    throw new Error(`D1 query failed: ${response.status} ${JSON.stringify(body)}`);
  }
  return results[0]?.results ?? [];
}
