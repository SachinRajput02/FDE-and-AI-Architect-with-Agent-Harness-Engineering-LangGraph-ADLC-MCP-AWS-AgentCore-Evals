import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { App } from "./App";
import { claim, fakeBackend, policy, summary } from "./testing";

beforeEach(() => {
  window.location.hash = "";
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

it("shows the queue with counts of each status", async () => {
  fakeBackend({
    "/api/claims": [
      summary,
      { ...summary, claim_id: "CLM-1002", status: "decided" },
    ],
  });
  render(<App />);
  expect(await screen.findByRole("link", { name: "CLM-1002" })).toBeDefined();
  expect(screen.getAllByText("$420.00")).toHaveLength(2);
  expect(screen.getAllByText("Trip delay")).toHaveLength(2);
  const counts = screen.getByRole("list", { name: "Claims by status" });
  const items = within(counts).getAllByRole("listitem");
  expect(items.map((item) => item.textContent)).toEqual([
    "1Waiting",
    "0In progress",
    "0Waiting for sign-off",
    "1Decided",
  ]);
});

it("says when the queue cannot load", async () => {
  fakeBackend({});
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Could not load the queue",
  );
});

it("opens a claim in full", async () => {
  fakeBackend({
    "/api/claims/CLM-1001": claim,
    "/api/policies/POL-2001": policy,
    "/api/claims/CLM-1001/steps": [],
  });
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  expect(await screen.findByText(claim.story)).toBeDefined();
  expect(screen.getByText("$245.00")).toBeDefined();
  expect(screen.getByText("Hotel receipt")).toBeDefined();
  expect(
    screen.getByText("The agent has not decided this claim yet."),
  ).toBeDefined();
  expect(await screen.findByText("UnderCover Premium")).toBeDefined();
  expect(screen.getByText("None")).toBeDefined();
});

it("shows a paid approval", async () => {
  fakeBackend({
    "/api/claims/CLM-1001": {
      ...claim,
      status: "decided",
      decision: {
        decision: "approve",
        payout: 1500,
        reason: "The delay is covered.",
        policy_section: "3. Trip Delay",
        decided_at: "",
      },
      payment: { amount: 1500, paid_at: "" },
      sign_off: {
        handler_id: "HND-01",
        handler_name: "Dana Whitfield",
        signed_at: "",
      },
    },
    "/api/policies/POL-2001": {
      ...policy,
      add_on_details: [
        { add_on: "electronics_plus", name: "Electronics Plus" },
      ],
    },
    "/api/claims/CLM-1001/steps": [],
  });
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  const decision = await screen.findByRole("region", { name: "Decision" });
  expect(decision.textContent).toContain("Approved $1,500.00");
  expect(decision.textContent).toContain("The delay is covered.");
  expect(decision.textContent).toContain("Policy wording: 3. Trip Delay");
  expect(decision.textContent).toContain(
    "Paid $1,500.00, signed off by Dana Whitfield",
  );
  expect(await screen.findByText("Electronics Plus")).toBeDefined();
});

it("shows a decline without a payout", async () => {
  fakeBackend({
    "/api/claims/CLM-1001": {
      ...claim,
      status: "decided",
      decision: {
        decision: "decline",
        payout: 0,
        reason: "Not covered.",
        policy_section: "9. General exclusions",
        decided_at: "",
      },
    },
    "/api/claims/CLM-1001/steps": [],
  });
  window.location.hash = "#/claims/CLM-1001";
  render(<App />);
  const decision = await screen.findByRole("region", { name: "Decision" });
  expect(decision.textContent).toContain("Declined");
  expect(decision.textContent).not.toContain("$");
});

it("says when a claim cannot load", async () => {
  fakeBackend({});
  window.location.hash = "#/claims/CLM-9999";
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Could not load CLM-9999",
  );
});

it("shows the agent's instructions, read only", async () => {
  fakeBackend({
    "/api/instructions": { text: "You are the UnderCover Agent." },
  });
  window.location.hash = "#/instructions";
  render(<App />);
  expect(
    await screen.findByText("You are the UnderCover Agent."),
  ).toBeDefined();
  expect(screen.queryByRole("textbox")).toBeNull();
});

it("says when the instructions cannot load", async () => {
  fakeBackend({});
  window.location.hash = "#/instructions";
  render(<App />);
  expect((await screen.findByRole("alert")).textContent).toContain(
    "Could not load the instructions",
  );
});

it("follows the address as it changes", async () => {
  fakeBackend({
    "/api/claims": [summary],
    "/api/instructions": { text: "Instructions here." },
  });
  render(<App />);
  expect(await screen.findByText("Claims queue")).toBeDefined();
  window.location.hash = "#/instructions";
  window.dispatchEvent(new HashChangeEvent("hashchange"));
  expect(await screen.findByText("Instructions here.")).toBeDefined();
});
