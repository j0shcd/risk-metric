import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { forwardRef } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AlertsSignupPanel } from "./App";
import { validateSubscribeInput } from "../functions/api/_lib/validate.mjs";

vi.mock("react-chartjs-2", () => ({
  Line: forwardRef(({ data }, ref) => (
    <div ref={ref} data-testid="chart">{data?.datasets?.[0]?.label || "chart"}</div>
  )),
}));

// One entry into each zone, so the preview count is predictable.
const SERIES = {
  labels: ["2015-01-01", "2015-01-02", "2015-01-03", "2015-01-04"],
  values: [0.2, 0.5, 0.8, 0.5],
};

function renderPanel() {
  return render(<AlertsSignupPanel dcaSeries={SERIES} />);
}

afterEach(() => {
  vi.restoreAllMocks();
});

describe("AlertsSignupPanel", () => {
  it("defaults to watching both zones and previews how often that fired", () => {
    renderPanel();
    expect(screen.getByRole("radio", { name: /either way/i })).toBeChecked();
    expect(screen.getByTestId("alert-preview")).toHaveTextContent(/2\s+emails since/i);
  });

  it("narrows the preview when only one zone is watched", () => {
    renderPanel();
    fireEvent.click(screen.getByRole("radio", { name: /only when it gets high/i }));
    expect(screen.getByTestId("alert-preview")).toHaveTextContent(/1\s+email since/i);
  });

  it("rejects a low threshold at or above the high threshold without calling the API", () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    renderPanel();
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "a@b.co" } });
    fireEvent.change(screen.getByLabelText(/low at or below/i), { target: { value: "80" } });
    fireEvent.click(screen.getByRole("button", { name: /email me/i }));
    expect(screen.getByTestId("alert-message")).toHaveTextContent(/The low mark has to sit below the high mark./);
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("posts the subscription and shows the server message", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, message: "Check your inbox to confirm your subscription." }),
    });
    renderPanel();
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /email me/i }));

    await waitFor(() => {
      expect(screen.getByText(/check your inbox/i)).toBeInTheDocument();
    });
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(body).toEqual({
      email: "user@example.com",
      watch: "both",
      buyThreshold: 0.25,
      sellThreshold: 0.75,
      website: "",
    });
  });

  it("posts the watch flag with the default mark on the unwatched side", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: true,
      json: async () => ({ ok: true, message: "Check your inbox." }),
    });
    renderPanel();
    fireEvent.click(screen.getByRole("radio", { name: /only when it gets high/i }));
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /email me/i }));

    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(body.watch).toBe("high");
    expect(body.buyThreshold).toBe(0.25);
    expect(body.sellThreshold).toBe(0.75);
  });

  it("shows the server error when the API rejects the request", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue({
      ok: false,
      json: async () => ({ ok: false, error: "Invalid email address." }),
    });
    renderPanel();
    fireEvent.change(screen.getByLabelText(/email/i), { target: { value: "user@example.com" } });
    fireEvent.click(screen.getByRole("button", { name: /email me/i }));

    await waitFor(() => {
      expect(screen.getByText(/invalid email address/i)).toBeInTheDocument();
    });
  });
});

describe("threshold validation", () => {
  it.each(["-1", "101", "25.5", ""])("opens and focuses the offending field for %s", (value) => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    renderPanel();
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.co" } });
    const low = screen.getByLabelText("Low at or below");
    fireEvent.change(low, { target: { value } });
    expect(screen.queryByTestId("alert-preview")).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Email me" }));
    expect(screen.getByText("Use a whole number from 0 to 100.")).toHaveAttribute("id", "threshold-error");
    expect(low).toHaveAttribute("aria-invalid", "true");
    expect(low).toHaveAttribute("aria-describedby", "threshold-error");
    expect(low.closest("details")).toHaveAttribute("open");
    expect(low).toHaveFocus();
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("validates only watched sides and sends a payload the real API validator accepts", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
    renderPanel();
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "a@b.co" } });
    fireEvent.change(screen.getByLabelText("Low at or below"), { target: { value: "90" } });
    fireEvent.change(screen.getByLabelText("High at or above"), { target: { value: "10" } });
    fireEvent.click(screen.getByRole("radio", { name: /only when it gets high/i }));
    expect(screen.queryByLabelText("Low at or below")).not.toBeInTheDocument();
    expect(screen.getByTestId("alert-preview")).toHaveTextContent("1 email");
    fireEvent.click(screen.getByRole("button", { name: "Email me" }));
    await waitFor(() => expect(fetchSpy).toHaveBeenCalled());
    const body = JSON.parse(fetchSpy.mock.calls[0][1].body);
    expect(body).toMatchObject({ watch: "high", buyThreshold: 0.25, sellThreshold: 0.1 });
    // Validate against the server's own rule, not a copy of it.
    expect(validateSubscribeInput(body).ok).toBe(true);
    fireEvent.click(screen.getByRole("radio", { name: /only when it gets low/i }));
    expect(screen.queryByLabelText("High at or above")).not.toBeInTheDocument();
    expect(screen.getByLabelText("Low at or below")).toHaveValue(90);
  });

  it("shows the specific email message", () => {
    renderPanel();
    fireEvent.change(screen.getByLabelText("Email"), { target: { value: "bad" } });
    fireEvent.click(screen.getByRole("button", { name: "Email me" }));
    expect(screen.getByText("That email address does not look right.")).toBeInTheDocument();
  });
});
