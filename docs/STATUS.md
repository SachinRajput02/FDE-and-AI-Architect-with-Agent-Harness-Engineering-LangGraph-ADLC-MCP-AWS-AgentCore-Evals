# Status

The claims pilot, in progress: see `docs/PLAN.md`.

## Built

- `backend/`: FastAPI and SQLite. `backend/db.py` builds the database at `backend/undercover.db` (or `UNDERCOVER_DB`) from `data/`, leaving out the evaluation and security sets. The read API: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions` and `list_handlers`.
- `agent/`, `dashboard/` and `e2e/`: still the hello-world skeleton.

## Running it

- `npm run dev` starts the backend on port 8000 and the dashboard on port 5173. The backend builds the database on first start.
- `npm run reset` rebuilds the database from `data/`, putting every claim back to waiting.
- `npm run check` runs every check.
