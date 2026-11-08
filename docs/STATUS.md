# Status

The claims pilot, in progress: see `docs/PLAN.md`.

## Built

- `backend/`: FastAPI and SQLite. `backend/db.py` builds the database at `backend/undercover.db` (or `UNDERCOVER_DB`) from `data/`, leaving out the evaluation and security sets. The read API: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions` and `list_handlers`.
- The claim workflow: `start_claim`, `record_step`, `list_steps`, `record_decision`, `pay_claim` and `sign_off_claim`. A claim is `waiting`, `in_progress`, `awaiting_signoff` or `decided`. `pay_claim` pays only the approved payout, once, and refuses any payout over the $1,000 limit in `data/company.json`. A handler's sign-off releases that payment.
- `agent/`: the UnderCover Agent, `create_agent` on OpenRouter. `run(claim_id, thread_id)` fetches its instructions from the backend (`backend/instructions.md`), starts the claim, and records every tool call, tool result and reply as a step. Its tools reach the backend only over HTTP, and its two writes, `record_decision` and `pay_claim`, are fixed to the claim it is working.
- `dashboard/` and `e2e/`: still the hello-world skeleton.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173. The backend builds the database on first start.
- `npm run reset` rebuilds the database from `data/`, putting every claim back to waiting.
- `uv run -m agent CLM-1001` runs the agent on one claim (or several), and `uv run -m agent queue` on every waiting claim. The backend must be running.
- `npm run check` runs every check.
