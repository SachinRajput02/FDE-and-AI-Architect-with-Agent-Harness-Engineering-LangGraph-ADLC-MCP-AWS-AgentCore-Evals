import { vi } from "vitest";
import type { Claim, ClaimSummary, Handler, Policy, Step } from "./api";

export const summary: ClaimSummary = {
  claim_id: "CLM-1001",
  customer_name: "Maya Patel",
  claim_type: "trip_delay",
  summary: "Flight home canceled by the airline",
  amount_claimed: 420,
  submitted_on: "2026-06-24",
  status: "waiting",
};

export const claim: Claim = {
  ...summary,
  policy_id: "POL-2001",
  customer_id: "CUS-3001",
  incident_date: "2026-06-18",
  incident_location: "Rome, Italy",
  story: "My flight home from Rome was canceled.",
  items: [
    {
      description: "Airport hotel, one night",
      category: "accommodation",
      amount: 245,
    },
    { description: "Dinner and breakfast", category: "meals", amount: 95 },
    { description: "Taxis", category: "transport", amount: 80 },
  ],
  documents: [
    { name: "Hotel receipt", type: "receipt", content: "Hotel Aurelia." },
  ],
  decision: null,
  payment: null,
  sign_off: null,
};

export const policy: Policy = {
  policy_id: "POL-2001",
  plan: "premium",
  add_ons: [],
  purchased_on: "2026-04-22",
  trip: {
    destination: "Rome, Italy",
    departs_on: "2026-06-10",
    returns_on: "2026-06-18",
    trip_cost: 3100,
  },
  travelers: ["Maya Patel"],
  plan_details: { name: "UnderCover Premium", deductible: 50 },
  add_on_details: [],
};

export const handlers: Handler[] = [
  {
    handler_id: "HND-01",
    name: "Dana Whitfield",
    role: "Senior Claims Handler",
    can_approve_over_limit: true,
  },
  {
    handler_id: "HND-09",
    name: "Sam Trainee",
    role: "Trainee",
    can_approve_over_limit: false,
  },
];

export const steps: Step[] = [
  { step_id: 1, kind: "tool_call", text: "get_claim({})", created_at: "" },
  { step_id: 2, kind: "reply", text: "Approved, $420.00.", created_at: "" },
];

export type Routes = Record<string, unknown>;

export function fakeBackend(routes: Routes) {
  const fetch = vi.fn((url: string, init?: RequestInit) => {
    const key = init?.method === "POST" ? `POST ${url}` : url;
    if (!(key in routes)) {
      return Promise.resolve(
        new Response(JSON.stringify({ detail: `Not found: ${key}` }), {
          status: 404,
        }),
      );
    }
    const body = routes[key];
    if (body instanceof Response) return Promise.resolve(body);
    return Promise.resolve(new Response(JSON.stringify(body)));
  });
  vi.stubGlobal("fetch", fetch);
  return fetch;
}
