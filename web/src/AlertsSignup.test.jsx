import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { forwardRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AlertsSignupPanel } from "./App";

vi.mock("react-chartjs-2", () => ({
  Line: forwardRef(({ data }, ref) => (
    <div ref={ref} data-testid="chart">{data?.datasets?.[0]?.label || "chart"}</div>
  )),
}));

function renderPanel() {
  return render(<AlertsSignupPanel strategyBuy={0.25} strategySell={0.75} />);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AlertsSignupPanel", () => {
  it("prefills thresholds from the strategy", () => {
    renderPanel();
    expect(screen.getByLabelText(/accumulate at\/below/i)).toHaveValue(0.25);
    expect(screen.getByLabelText(/sell at\/above/i)).toHaveValue(0.75);
  });

  it("rejects an accumulate threshold at or above the sell threshold without calling the API", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    renderPanel();
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.co" } });
    fireEvent.change(screen.getByLabelText(/accumulate at\/below/i), { target: { value: "0.8" } });
    fireEvent.click(screen.getByRole("button", { name: /subscribe/i }));
    expect(screen.getByRole("status")).toHaveTextContent(/accumulate < sell/i);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("posts the subscription and shows the server message", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, message: "Check your inbox to confirm your subscription." }),
    });
    renderPanel();
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /subscribe/i }));

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(/check your inbox/i);
    });
    expect(fetchSpy).toHaveBeenCalledWith(
      "/api/subscribe",
      expect.objectContaining({ method: "POST" }),
    );
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(body).toEqual({
      email: "user@example.com",
      buyThreshold: 0.25,
      sellThreshold: 0.75,
      website: "",
    });
  });

  it("shows the server error when the API rejects the request", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      json: async () => ({ ok: false, error: "Invalid email address." }),
    });
    renderPanel();
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /subscribe/i }));

    await waitFor(() => {
      expect(screen.getByRole("status")).toHaveTextContent(/invalid email address/i);
    });
  });
});
