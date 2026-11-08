import { useState, type SubmitEvent } from "react";
import { postJson, type Claim, type Handler } from "./api";
import { money } from "./format";
import { useJson } from "./useJson";

export function SignOff({
  claim,
  onSignedOff,
}: Readonly<{ claim: Claim; onSignedOff: () => void }>) {
  const { data: handlers } = useJson<Handler[]>("/api/handlers", false);
  const [handlerId, setHandlerId] = useState("");
  const [error, setError] = useState<string>();
  const payout = claim.decision?.payout ?? 0;
  const eligible = handlers?.filter(
    (handler) => handler.can_approve_over_limit,
  );

  const submit = (event: SubmitEvent) => {
    event.preventDefault();
    postJson(`/api/claims/${claim.claim_id}/sign-off`, {
      handler_id: handlerId,
    }).then(onSignedOff, (reason: unknown) => {
      setError(String(reason));
    });
  };

  return (
    <section className="panel" aria-label="Sign-off">
      <h2>Sign-off needed</h2>
      <p>
        The agent approved a payout of {money(payout)}. A payout over $1,000.00
        is paid only once a handler signs off.
      </p>
      <form onSubmit={submit}>
        <label>
          Handler{" "}
          <select
            value={handlerId}
            required
            onChange={(event) => {
              setHandlerId(event.target.value);
            }}
          >
            <option value="">Choose a handler</option>
            {eligible?.map((handler) => (
              <option key={handler.handler_id} value={handler.handler_id}>
                {handler.name}
              </option>
            ))}
          </select>
        </label>
        <button type="submit" disabled={!handlerId}>
          Sign off and pay {money(payout)}
        </button>
        {error && <p role="alert">{error}</p>}
      </form>
    </section>
  );
}
