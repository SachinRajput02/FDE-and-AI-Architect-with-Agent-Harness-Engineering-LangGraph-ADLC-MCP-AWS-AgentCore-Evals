export type Status = "waiting" | "in_progress" | "awaiting_signoff" | "decided";

export interface ClaimSummary {
  claim_id: string;
  customer_name: string;
  claim_type: string;
  summary: string;
  amount_claimed: number;
  submitted_on: string;
  status: Status;
}

export interface Item {
  description: string;
  category: string;
  amount: number;
}

export interface ClaimDocument {
  name: string;
  type: string;
  content: string;
}

export interface Decision {
  decision: "approve" | "decline" | "refer";
  payout: number;
  reason: string;
  policy_section: string;
  decided_at: string;
}

export interface Claim extends ClaimSummary {
  policy_id: string;
  customer_id: string;
  incident_date: string;
  incident_location: string;
  story: string;
  items: Item[];
  documents: ClaimDocument[];
  decision: Decision | null;
  payment: { amount: number; paid_at: string } | null;
  sign_off: {
    handler_id: string;
    handler_name: string;
    signed_at: string;
  } | null;
}

export interface Policy {
  policy_id: string;
  plan: string;
  add_ons: string[];
  purchased_on: string;
  trip: {
    destination: string;
    departs_on: string;
    returns_on: string;
    trip_cost: number;
  };
  travelers: string[];
  plan_details: { name: string; deductible: number };
  add_on_details: { add_on: string; name: string }[];
}

export interface Step {
  step_id: number;
  kind: "tool_call" | "tool_result" | "reply";
  text: string;
  created_at: string;
}

export interface Handler {
  handler_id: string;
  name: string;
  role: string;
  can_approve_over_limit: boolean;
}

async function read<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const body = (await response.json()) as { detail: string };
    throw new Error(body.detail);
  }
  return (await response.json()) as T;
}

export async function getJson<T>(url: string): Promise<T> {
  return read<T>(await fetch(url));
}

export async function postJson<T>(url: string, body: object): Promise<T> {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return read<T>(response);
}
