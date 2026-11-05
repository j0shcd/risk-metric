const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function normalizeEmail(email) {
  return typeof email === "string" ? email.trim().toLowerCase() : "";
}

export function isValidEmail(email) {
  const normalized = normalizeEmail(email);
  return normalized.length <= 254 && emailPattern.test(normalized);
}

export function parseThreshold(value) {
  if (typeof value === "number") return value;
  if (typeof value === "string" && value.trim() !== "") return Number(value);
  return Number.NaN;
}

// The two marks only need to be ordered when both are watched. A high-only
// subscriber may set the high mark below the (ignored) low mark, and vice versa.
export function validateThresholds(buyThreshold, sellThreshold, watch = "both") {
  const buy = parseThreshold(buyThreshold);
  const sell = parseThreshold(sellThreshold);

  if (!Number.isFinite(buy) || !Number.isFinite(sell)) {
    return { ok: false, error: "Thresholds must be finite numbers." };
  }

  if (!(buy >= 0 && buy <= 1 && sell >= 0 && sell <= 1)) {
    return { ok: false, error: "Thresholds must be between 0 and 1." };
  }

  if (watch === "both" && !(buy < sell)) {
    return { ok: false, error: "Thresholds must satisfy buyThreshold < sellThreshold." };
  }

  return { ok: true, buyThreshold: buy, sellThreshold: sell };
}

export function validateSubscribeInput(input) {
  if (!input || typeof input !== "object") {
    return { ok: false, error: "Invalid JSON body." };
  }

  const email = normalizeEmail(input.email);
  if (!isValidEmail(email)) {
    return { ok: false, error: "Enter a valid email address." };
  }

  const watch = input.watch === undefined ? "both" : input.watch;
  if (!["both", "high", "low"].includes(watch)) {
    return { ok: false, error: 'Watch must be "both", "high", or "low".' };
  }

  const thresholds = validateThresholds(input.buyThreshold, input.sellThreshold, watch);
  if (!thresholds.ok) return thresholds;

  return {
    ok: true,
    watch,
    email,
    buyThreshold: thresholds.buyThreshold,
    sellThreshold: thresholds.sellThreshold,
    website: typeof input.website === "string" ? input.website : "",
  };
}
