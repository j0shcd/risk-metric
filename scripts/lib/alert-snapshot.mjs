export function validateSnapshot(snapshot, now = new Date()) {
  const risk = Number(snapshot?.dca_risk);
  if (snapshot?.dca_risk === null || snapshot?.dca_risk === "" || !Number.isFinite(risk) || risk < 0 || risk > 1) {
    throw new Error("latest_snapshot.json missing finite dca_risk in [0,1]");
  }

  if (!/^\d{4}-\d{2}-\d{2}$/.test(String(snapshot?.date))) {
    throw new Error("latest_snapshot.json missing a valid date");
  }
  const snapshotDate = new Date(`${snapshot.date}T00:00:00Z`);
  if (!Number.isFinite(snapshotDate.getTime()) || snapshotDate.toISOString().slice(0, 10) !== snapshot.date) {
    throw new Error("latest_snapshot.json missing a valid date");
  }
  const today = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()));
  const ageDays = Math.floor((today - snapshotDate) / 86_400_000);
  if (ageDays < 0) {
    throw new Error(`latest_snapshot.json is future-dated (${snapshot.date})`);
  }
  if (ageDays > 2) {
    throw new Error(`latest_snapshot.json is stale (${snapshot.date})`);
  }

  return { risk, date: snapshot.date };
}
