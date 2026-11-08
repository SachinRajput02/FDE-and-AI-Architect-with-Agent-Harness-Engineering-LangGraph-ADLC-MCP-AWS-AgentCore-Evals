import type { Claim, Policy } from "./api";
import { decisionLabels, label, money } from "./format";
import { SignOff } from "./SignOff";
import { StatusChip } from "./StatusChip";
import { Steps } from "./Steps";
import { useJson } from "./useJson";

function DecisionPanel({ claim }: Readonly<{ claim: Claim }>) {
  const { decision, payment, sign_off } = claim;
  if (!decision) {
    return (
      <section className="panel">
        <h2>Decision</h2>
        <p className="muted">The agent has not decided this claim yet.</p>
      </section>
    );
  }
  return (
    <section className="panel" aria-label="Decision">
      <h2>
        {decisionLabels[decision.decision]}
        {decision.decision === "approve" && (
          <span className="mono"> {money(decision.payout)}</span>
        )}
      </h2>
      <p>{decision.reason}</p>
      <p className="muted">Policy wording: {decision.policy_section}</p>
      {decision.decision === "approve" && (
        <p>
          {payment ? `Paid ${money(payment.amount)}` : "Not paid yet"}
          {sign_off && `, signed off by ${sign_off.handler_name}`}
        </p>
      )}
    </section>
  );
}

function PolicyPanel({ policyId }: Readonly<{ policyId: string }>) {
  const { data: policy } = useJson<Policy>(`/api/policies/${policyId}`, false);
  if (!policy) return null;
  return (
    <section className="panel">
      <h2>Policy</h2>
      <dl>
        <dt>Policy</dt>
        <dd className="mono">{policy.policy_id}</dd>
        <dt>Plan</dt>
        <dd>{policy.plan_details.name}</dd>
        <dt>Add-ons</dt>
        <dd>
          {policy.add_on_details.map((add_on) => add_on.name).join(", ") ||
            "None"}
        </dd>
        <dt>Trip</dt>
        <dd>
          {policy.trip.destination},{" "}
          <span className="mono">{policy.trip.departs_on}</span> to{" "}
          <span className="mono">{policy.trip.returns_on}</span>
        </dd>
        <dt>Travelers</dt>
        <dd>{policy.travelers.join(", ")}</dd>
        <dt>Purchased</dt>
        <dd className="mono">{policy.purchased_on}</dd>
      </dl>
    </section>
  );
}

function ClaimDetails({ claim }: Readonly<{ claim: Claim }>) {
  return (
    <>
      <section className="panel">
        <h2>The customer&apos;s story</h2>
        <p className="story">{claim.story}</p>
        <p className="muted">
          {claim.incident_location},{" "}
          <span className="mono">{claim.incident_date}</span>. Submitted{" "}
          <span className="mono">{claim.submitted_on}</span>.
        </p>
      </section>
      <section className="panel">
        <h2>Items claimed</h2>
        <table>
          <tbody>
            {claim.items.map((item) => (
              <tr key={item.description}>
                <td>{item.description}</td>
                <td>{label(item.category)}</td>
                <td className="number mono">{money(item.amount)}</td>
              </tr>
            ))}
            <tr className="total">
              <td>Total claimed</td>
              <td />
              <td className="number mono">{money(claim.amount_claimed)}</td>
            </tr>
          </tbody>
        </table>
      </section>
      <section className="panel">
        <h2>Documents</h2>
        {claim.documents.map((document) => (
          <article key={document.name} className="document">
            <h3>{document.name}</h3>
            <p>{document.content}</p>
          </article>
        ))}
      </section>
    </>
  );
}

export function ClaimPage({ claimId }: Readonly<{ claimId: string }>) {
  const {
    data: claim,
    error,
    reload,
  } = useJson<Claim>(`/api/claims/${claimId}`, true);

  if (error)
    return (
      <p role="alert">
        Could not load {claimId}. {error}
      </p>
    );
  if (!claim) return <p>Loading {claimId}</p>;

  return (
    <>
      <a href="#/">Back to the queue</a>
      <div className="title">
        <h1>
          <span className="mono">{claim.claim_id}</span> {claim.summary}
        </h1>
        <StatusChip status={claim.status} />
      </div>
      <p className="muted">
        {claim.customer_name}, {label(claim.claim_type)}
      </p>
      <div className="columns">
        <div className="stack">
          {claim.status === "awaiting_signoff" && (
            <SignOff claim={claim} onSignedOff={reload} />
          )}
          <DecisionPanel claim={claim} />
          <ClaimDetails claim={claim} />
        </div>
        <div className="stack">
          <Steps claimId={claim.claim_id} />
          <PolicyPanel policyId={claim.policy_id} />
        </div>
      </div>
    </>
  );
}
