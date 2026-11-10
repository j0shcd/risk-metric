import { fireEvent, render, screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import TrackRecord from "./TrackRecord";
import { DCA_EVIDENCE, DCA_PERIODS } from "./dcaEvidence";

const units = (value) => value.toLocaleString("en-US", { minimumFractionDigits: 8, maximumFractionDigits: 8 });
describe("interactive Track record", () => {
  it("starts at the latest four-year period with equal fully deployed budgets", () => {
    render(<TrackRecord />);
    expect(screen.getByLabelText("Historical period")).toHaveValue("2022-11-30");
    expect(screen.getAllByRole("option")).toHaveLength(96);
    expect(screen.getByLabelText("Monthly contribution (USD)")).toHaveValue(100);
    expect(screen.getByText(/Both strategies spend/)).toHaveTextContent("$4,800.00");
    expect(screen.getByText(/Across 96/)).toHaveTextContent("19.22% less BTC");
    expect(screen.getByText(/Both receive the same/)).toHaveTextContent("0.20%");
    expect(screen.queryByText(/It passed once|Historically promising/)).not.toBeInTheDocument();
    const term = screen.getByText("Evidence type");
    expect(term.tagName).toBe("DT");
    expect(term.nextElementSibling).toHaveTextContent(DCA_EVIDENCE.evidenceTier);
    expect(DCA_EVIDENCE.evidenceTier).toBe("Retrospective reconstruction");
    const rows = document.querySelectorAll(".bb-research-table tbody tr");
    expect(rows.length).toBeGreaterThan(0);
    rows.forEach((row) => {
      expect(row.querySelector("th")).toHaveTextContent(/.+/);
      expect(row.querySelectorAll("td")[0]).toHaveAttribute("data-label", "Median vs Fixed DCA");
      expect(row.querySelectorAll("td")[1]).toHaveAttribute("data-label", "Periods ahead");
    });
  });

  it("updates both BTC balances and ending values when the period or amount changes", () => {
    render(<TrackRecord />);
    const period = DCA_PERIODS[0];
    fireEvent.change(screen.getByLabelText("Historical period"), { target: { value: period.start } });
    fireEvent.change(screen.getByLabelText("Monthly contribution (USD)"), { target: { value: "250.25" } });
    const results = screen.getByRole("group", { name: "Selected period results" });
    expect(within(results).getByText(units(period.fixedBtc*250.25))).toHaveTextContent("BTC");
    expect(within(results).getByText(units(period.scoreBtc*250.25))).toHaveTextContent("BTC");
    expect(within(results).getByText("Worth $78,009.63 at the Nov 2018 close")).toBeInTheDocument();
    expect(within(results).getByText("Worth $23,233.14 at the Nov 2018 close")).toBeInTheDocument();
    expect(screen.getByText(/Both strategies spend/)).toHaveTextContent("$12,012.00");
    expect(screen.getByText(/Its contribution money/)).toHaveTextContent("20.8 months");
    expect(screen.getByText(/Score-based buying accumulated/)).toHaveTextContent("70.22% less BTC");
  });

  it("shows a positive historical period without changing the overall verdict", () => {
    render(<TrackRecord />);
    const period = DCA_PERIODS.find((p) => p.delta > 0);
    fireEvent.change(screen.getByLabelText("Historical period"), { target: { value: period.start } });
    expect(screen.getByText(/Score-based buying accumulated/)).toHaveTextContent("more BTC");
    expect(screen.getByText(/Across 96/)).toHaveTextContent("19.22% less BTC");
  });

  it("removes stale results for invalid input and recovers without resetting the period", () => {
    render(<TrackRecord />);
    const input = screen.getByLabelText("Monthly contribution (USD)");
    for (const value of ["", "0", "-1", "1.001", "1000001"]) {
      fireEvent.change(input, { target: { value } });
      expect(input).toHaveAttribute("aria-invalid", "true");
      expect(screen.getByRole("alert")).toBeInTheDocument();
      expect(screen.queryByRole("group", { name: "Selected period results" })).not.toBeInTheDocument();
    }
    fireEvent.change(input, { target: { value: ".01" } });
    expect(screen.getByRole("group", { name: "Selected period results" })).toBeInTheDocument();
    expect(screen.getByLabelText("Historical period")).toHaveValue("2022-11-30");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });
});
