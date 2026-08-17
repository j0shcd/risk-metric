import { describe, expect, it } from "vitest";

import { DCA_EVIDENCE } from "./dcaEvidence";

describe("DCA evidence snapshot", () => {
  it("keeps the published verdicts and four-year horizon explicit", () => {
    expect(DCA_EVIDENCE.tests).toHaveLength(3);
    expect(DCA_EVIDENCE.tests.map((test) => test.verdict)).toEqual([
      "Not supported",
      "Historically promising",
      "Not supported",
    ]);
    expect(DCA_EVIDENCE.tests.find((test) => test.id === "signal")?.stats).toContainEqual([
      "Horizon",
      "48 months",
    ]);
    expect(DCA_EVIDENCE.safeguards).toContain(
      "Future-score and future-price mutations cannot change earlier trades.",
    );
  });
});
