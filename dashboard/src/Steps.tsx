import type { Status, Step } from "./api";
import { useJson } from "./useJson";

const kindLabels: Record<Step["kind"], string> = {
  tool_call: "Calls",
  tool_result: "Result",
  reply: "Says",
};

export function Steps({
  claimId,
  status,
}: Readonly<{ claimId: string; status: Status }>) {
  const { data: steps } = useJson<Step[]>(
    `/api/claims/${claimId}/steps`,
    status !== "decided",
  );
  return (
    <section className="panel" aria-label="Agent steps">
      <h2>What the agent did</h2>
      {steps?.length ? (
        <ol className="steps">
          {steps.map((step) => (
            <li key={step.step_id} className={`step step-${step.kind}`}>
              <span className="step-kind">{kindLabels[step.kind]}</span>
              <span className="step-text">{step.text}</span>
            </li>
          ))}
        </ol>
      ) : (
        <p className="muted">The agent has not worked on this claim yet.</p>
      )}
    </section>
  );
}
