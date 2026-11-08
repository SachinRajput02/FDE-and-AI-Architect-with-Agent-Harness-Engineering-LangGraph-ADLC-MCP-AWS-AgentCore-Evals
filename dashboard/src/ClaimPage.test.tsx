import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import type { Claim } from "./api";
import { ClaimPage } from "./ClaimPage";
import { claim, fakeBackend, handlers, policy, steps } from "./testing";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const awaiting: Claim = {
  ...claim,
  status: "awaiting_signoff",
  decision: {
    decision: "approve",
    payout: 1500,
    reason: "Covered.",
    policy_section: "5. Baggage",
    decided_at: "",
  },
};

it("shows what the agent did", async () => {
  fakeBackend({
    "/api/claims/CLM-1001": { ...claim, status: "in_progress" },
    "/api/claims/CLM-1001/steps": steps,
    "/api/policies/POL-2001": policy,
  });
  render(<ClaimPage claimId="CLM-1001" />);
  expect(await screen.findByText("get_claim({})")).toBeDefined();
  expect(screen.getByText("Calls")).toBeDefined();
  expect(screen.getByText("Says")).toBeDefined();
  expect(screen.getByText("Approved, $420.00.")).toBeDefined();
});

it("says when the agent has not started", async () => {
  fakeBackend({
    "/api/claims/CLM-1001": claim,
    "/api/claims/CLM-1001/steps": [],
  });
  render(<ClaimPage claimId="CLM-1001" />);
  expect(
    await screen.findByText("The agent has not worked on this claim yet."),
  ).toBeDefined();
});

it("signs off a payout over the limit", async () => {
  const fetch = fakeBackend({
    "/api/claims/CLM-1001": awaiting,
    "/api/claims/CLM-1001/steps": [],
    "/api/handlers": handlers,
    "POST /api/claims/CLM-1001/sign-off": { ...awaiting, status: "decided" },
  });
  render(<ClaimPage claimId="CLM-1001" />);
  const button = await screen.findByRole("button", {
    name: "Sign off and pay $1,500.00",
  });
  expect(
    await screen.findByRole("option", { name: "Dana Whitfield" }),
  ).toBeDefined();
  expect(screen.queryByRole("option", { name: "Sam Trainee" })).toBeNull();
  expect((button as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(button);
  await vi.waitFor(() => {
    expect(fetch).toHaveBeenCalledWith(
      "/api/claims/CLM-1001/sign-off",
      expect.objectContaining({ body: '{"handler_id":"HND-01"}' }),
    );
  });
  await vi.waitFor(() => {
    expect(
      fetch.mock.calls.filter(([url]) => url === "/api/claims/CLM-1001"),
    ).toHaveLength(2);
  });
});

it("shows why a sign-off was refused", async () => {
  fakeBackend({
    "/api/claims/CLM-1001": awaiting,
    "/api/claims/CLM-1001/steps": [],
    "/api/handlers": handlers,
    "POST /api/claims/CLM-1001/sign-off": new Response(
      JSON.stringify({ detail: "Claim CLM-1001 is not waiting for sign-off" }),
      { status: 409 },
    ),
  });
  render(<ClaimPage claimId="CLM-1001" />);
  await screen.findByRole("option", { name: "Dana Whitfield" });
  fireEvent.change(screen.getByRole("combobox"), {
    target: { value: "HND-01" },
  });
  fireEvent.click(screen.getByRole("button", { name: /Sign off/ }));
  expect((await screen.findByRole("alert")).textContent).toContain(
    "is not waiting for sign-off",
  );
});

it("polls while the claim is open", async () => {
  vi.useFakeTimers({ shouldAdvanceTime: true });
  const fetch = fakeBackend({
    "/api/claims/CLM-1001": { ...claim, status: "in_progress" },
    "/api/claims/CLM-1001/steps": steps,
  });
  render(<ClaimPage claimId="CLM-1001" />);
  await screen.findByText("get_claim({})");
  await vi.advanceTimersByTimeAsync(2100);
  expect(
    fetch.mock.calls.filter(([url]) => url === "/api/claims/CLM-1001/steps")
      .length,
  ).toBeGreaterThan(1);
  vi.useRealTimers();
});
