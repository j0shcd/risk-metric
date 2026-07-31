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

export function validateThresholds(buyThreshold, sellThreshold) {
  const buy = parseThreshold(buyThreshold);
  const sell = parseThreshold(sellThreshold);

  if (!Number.isFinite(buy) || !Number.isFinite(sell)) {
    return { ok: false, error: "Thresholds must be finite numbers." };
  }

  if (!(buy >= 0 && buy < sell && sell <= 1)) {
    return { ok: false, error: "Thresholds must satisfy 0 <= buyThreshold < sellThreshold <= 1." };
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

  const thresholds = validateThresholds(input.buyThreshold, input.sellThreshold);
  if (!thresholds.ok) return thresholds;

  return {
    ok: true,
    email,
    buyThreshold: thresholds.buyThreshold,
    sellThreshold: thresholds.sellThreshold,
    website: typeof input.website === "string" ? input.website : "",
  };
}
