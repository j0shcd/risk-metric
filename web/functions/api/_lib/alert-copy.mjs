export function watchClause(watch, buyThreshold, sellThreshold) {
  const low = `drops to ${Math.round(buyThreshold * 100)} or below`;
  const high = `rises to ${Math.round(sellThreshold * 100)} or above`;
  if (watch === "high") return high;
  if (watch === "low") return low;
  return `${low}, or ${high}`;
}
