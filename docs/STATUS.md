# Status

The claims pilot from `docs/SPEC.md` is built, following `docs/PLAN.md`.

## What's built

- `backend/`: FastAPI and SQLite. `backend/db.py` builds the database at `backend/undercover.db` (or the path in `UNDERCOVER_DB`) from the queue and records in `data/`. It leaves out the evaluation and security sets.
  - Reads: `list_claims`, `get_claim`, `get_policy`, `get_claim_history` (earlier claims only, with no personal details), `get_policy_wording`, `get_instructions` and `list_handlers`.
  - The workflow: `start_claim`, `record_step`, `list_steps`, `record_decision`, `pay_claim` and `sign_off_claim`.
  - `pay_claim` pays only the approved payout, and only once. It refuses any payout over the $1,000 limit in `data/company.json` until a handler signs off, and the sign-off releases that payment.
- `agent/`: the UnderCover Agent, LangChain's `create_agent` on OpenRouter, using `openai/gpt-6-luna` with low reasoning effort or the model in `MODEL_NAME`.
  - `run(claim_id, thread_id)` fetches the agent's instructions from the backend, starts the claim, and records every tool call, tool result and reply as a step.
  - Its tools reach the backend only over HTTP. Its two writes, `record_decision` and `pay_claim`, can only act on the claim being worked.
  - The instructions are in `backend/instructions.md`. The agent works from the policy wording alone, not the claims manual.
- `dashboard/`: React, Vite and TypeScript, in the UnderCover brand with light and dark modes.
  - The queue (`#/`), with counts by status.
  - Each claim in full (`#/claims/CLM-1001`): the decision with its reason and policy section, payment, sign-off, policy, and the agent's steps as it works.
  - The agent's instructions, read only (`#/instructions`).
  - Pages refresh every two seconds.
- `e2e/`: Playwright tests of the queue, the live steps, the sign-off and the instructions. They play the agent's part through the API and never call a model. Playwright runs its own backend on port 8001, with a fresh database at `e2e/.data/e2e.db`, and its own dashboard on port 5174.

## Claim states

`waiting` → `in_progress` (the agent has started) → `decided`, or `awaiting_signoff` for an approval over $1,000, which a handler's sign-off moves to `decided`. A referral is `decided`, with the decision `refer`.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard at http://localhost:5173. The backend builds the database on first start.
- `uv run -m agent CLM-1001` runs the agent on one claim, or on several if you name them. `uv run -m agent queue` runs it on every waiting claim. The backend must be running, and `OPENROUTER_API_KEY` must be in `.env`.
- `npm run reset` rebuilds the database from `data/`, putting every claim back to waiting. Use it if a run stops partway and leaves a claim in progress.
- `npm run check` runs every check.

## Not yet done

- The agent's decisions have not been scored against the handlers' decisions in `data/evals/`.
