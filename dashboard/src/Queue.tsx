import type { ClaimSummary, Status } from "./api";
import { label, money, statusLabels } from "./format";
import { StatusChip } from "./StatusChip";
import { useJson } from "./useJson";

const statuses = Object.keys(statusLabels) as Status[];

export function Queue() {
  const { data: claims, error } = useJson<ClaimSummary[]>("/api/claims", true);

  if (error) return <p role="alert">Could not load the queue. {error}</p>;
  if (!claims) return <p>Loading the queue</p>;

  return (
    <>
      <h1>Claims queue</h1>
      <ul className="counts" aria-label="Claims by status">
        {statuses.map((status) => (
          <li key={status} className="panel">
            <span className="count">
              {claims.filter((claim) => claim.status === status).length}
            </span>
            <StatusChip status={status} />
          </li>
        ))}
      </ul>
      <div className="panel scroll">
        <table>
          <thead>
            <tr>
              <th>Claim</th>
              <th>Customer</th>
              <th>Type</th>
              <th>Summary</th>
              <th className="number">Claimed</th>
              <th>Submitted</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {claims.map((claim) => (
              <tr key={claim.claim_id}>
                <td>
                  <a className="mono" href={`#/claims/${claim.claim_id}`}>
                    {claim.claim_id}
                  </a>
                </td>
                <td>{claim.customer_name}</td>
                <td>{label(claim.claim_type)}</td>
                <td>{claim.summary}</td>
                <td className="number mono">{money(claim.amount_claimed)}</td>
                <td className="mono">{claim.submitted_on}</td>
                <td>
                  <StatusChip status={claim.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
