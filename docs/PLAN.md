# Plan: the claims pilot

This plan builds the pilot in `docs/SPEC.md`: a backend that holds the claims queue, the UnderCover Agent that decides claims through the backend's API, and a dashboard for the handlers. It follows `docs/TECH_STACK.md`, `docs/CODE_STANDARDS.md`, `docs/PROCESS.md` and `docs/BRAND.md`.

## Approach

- **The backend is the system of record and enforces the rules.** The agent and the dashboard only talk to it over HTTP. The $1,000 sign-off rule lives in the backend's `pay_claim` operation, so it holds no matter what the agent says or does.
- **SQLite with the standard library's `sqlite3`.** No ORM: a handful of tables, and the business data stays close to its JSON shape. Claims, policies and customers are stored as JSON documents with a few indexed columns (id, status); decisions, payments, sign-offs and agent steps get their own tables.
- **Seeding.** `backend/db.py` builds the database from the top-level files in `data/`. It reads only `claims.json`, `policies.json`, `customers.json`, `plans.json`, `handlers.json`, `company.json` and `policy_wording.md`, by name. It never reads `data/evals/` or `data/security/`. The database is `backend/undercover.db` (gitignored), or the path in `UNDERCOVER_DB`. The backend seeds it on startup if it is missing, and `npm run reset` rebuilds it.
- **Claim states.** `waiting` (the seed's `open`), `in_progress`, `awaiting_signoff` and `decided`. A referral is `decided` with the decision `refer`.
- **Paying.** The agent records its decision, then pays with a separate operation that takes the amount, as the tech stack asks. `pay_claim` refuses (409) unless the claim was approved, the amount equals the approved payout, it hasn't been paid, and, if the payout is over the limit in `company.json`, a handler has signed off. A sign-off by a handler who `can_approve_over_limit` releases the payment and moves the claim to `decided`.
- **Customer data.** The agent needs the customer's claim history, not their address or phone number, so the API exposes `get_claim_history` and not the full customer record. This keeps personal data out of the prompt.
- **Instructions.** The agent's system prompt lives in `backend/instructions.md` and is served by `get_instructions`. The agent fetches it at the start of each run; the dashboard shows the same text, read only. One copy, so what the team reads is what the agent runs on.
- **Steps.** The agent's runner streams the agent's updates and posts each one (a tool call with its inputs, the tool's result, the final reply) to `record_step`. The dashboard polls the claim's steps every two seconds while it is in progress. Polling is simpler than server-sent events and fast enough for this.
- **Running the agent.** A command line: `uv run -m agent CLM-1001` for one claim, `uv run -m agent queue` for every waiting claim in turn. The dashboard shows the work as it happens. A "Run" button in the dashboard is easy to add later but isn't asked for, and it would tie the backend's process to the model.
- **Model.** `openai/gpt-6-luna` with low reasoning effort, or `MODEL_NAME` if set, as the skeleton already does. Tests always use a stub model.
- **Dashboard.** React with a small hash router (`#/`, `#/claims/CLM-1001`, `#/instructions`) instead of a routing library. Brand fonts from Google Fonts, the brand colors as CSS variables, light and dark modes from `prefers-color-scheme`.
- **End-to-end tests** never call a model. They play the agent's part through the API (start, steps, decision, payment) and check what the dashboard shows. Playwright runs its own backend on port 8001 with a fresh database, and its own dashboard on port 5174, so the tests never touch your dev data. The Vite proxy target comes from `BACKEND_URL`, defaulting to `http://127.0.0.1:8000`.

## The API

Every operation has an `operation_id`, a one-line docstring and no optional inputs.

| Method and path | `operation_id` | Used by |
|---|---|---|
| `GET /api/health` | `health` | checks |
| `GET /api/claims` | `list_claims` | dashboard, agent CLI |
| `GET /api/claims/{claim_id}` | `get_claim` | both: the claim, its decision, payment and sign-off |
| `GET /api/policies/{policy_id}` | `get_policy` | both: the policy with its plan's limits and add-ons |
| `GET /api/customers/{customer_id}/history` | `get_claim_history` | agent |
| `GET /api/policy-wording` | `get_policy_wording` | agent |
| `GET /api/instructions` | `get_instructions` | both |
| `GET /api/handlers` | `list_handlers` | dashboard |
| `POST /api/claims/{claim_id}/start` | `start_claim` | agent runner: `waiting` to `in_progress` |
| `POST /api/claims/{claim_id}/steps` | `record_step` | agent runner |
| `GET /api/claims/{claim_id}/steps` | `list_steps` | dashboard |
| `POST /api/claims/{claim_id}/decision` | `record_decision` | agent: decision, payout, reason, policy section |
| `POST /api/claims/{claim_id}/payment` | `pay_claim` | agent: the amount |
| `POST /api/claims/{claim_id}/sign-off` | `sign_off_claim` | dashboard: the handler id |

`record_decision` takes `decision` (`approve`, `decline` or `refer`), `payout` (0 unless approving), `reason` and `policy_section`. An approval over the limit moves the claim to `awaiting_signoff`; anything else moves it to `decided`.

## Phase 1: Data and the read API

Build the database, the seeding and the operations that read: `list_claims`, `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `get_instructions` (with a placeholder `backend/instructions.md`) and `list_handlers`. Add `npm run reset`, and gitignore the database.

Why first: everything else reads from it, and it settles the shapes the agent and dashboard use.

- [x] `uv run pytest -q backend` passes, with tests on a temporary database per test
- [x] `npm run reset` creates `backend/undercover.db`; `GET /api/claims` returns 25 claims, all `waiting`, each with id, customer name, claim type, amount claimed and submitted date
- [x] `GET /api/claims/CLM-1001` returns the story, items and documents, and `decision`, `payment` and `sign_off` as `null`
- [x] `GET /api/policies/POL-2001` returns the policy with the Premium plan's limits merged in
- [x] `GET /api/customers/CUS-3001/history` returns the earlier claim `CLM-0412` and no email, phone, address or date of birth
- [x] `GET /api/policy-wording` returns the text of `data/policy_wording.md`
- [x] `GET /api/claims/CLM-9999` returns 404
- [x] A test asserts that no claim from `data/security/` (CLM-1901) is in the queue, and `backend/` has no reference to `evals`
- [x] The generated OpenAPI schema has an `operation_id` and a summary on every operation, and no optional parameters (checked by a test)

## Phase 2: The claim workflow and the payment rule

Add `start_claim`, `record_step`, `list_steps`, `record_decision`, `pay_claim` and `sign_off_claim`, with the state changes and the payment rules above.

Why now: the rules are the part that must be right whatever the agent does, so they are built and tested before the agent exists.

- [x] `uv run pytest -q backend` passes with coverage over 80%
- [x] `start_claim` moves a `waiting` claim to `in_progress`, and returns 409 for any other state
- [x] `record_step` and `list_steps` store and return steps in order, with a kind (`tool_call`, `tool_result`, `reply`), a short text and a timestamp
- [x] Declining or referring with a payout above 0 returns 422
- [x] Approving $420.00 moves the claim to `decided`; `pay_claim` with 420.00 records the payment; paying again returns 409
- [x] `pay_claim` with an amount other than the approved payout returns 409
- [x] Approving $1,500.00 moves the claim to `awaiting_signoff`, and `pay_claim` with 1500.00 returns 409 with a message that a handler's sign-off is needed
- [x] `sign_off_claim` by a handler who can't approve over the limit returns 403; by one who can, it records the sign-off and the payment and moves the claim to `decided`
- [x] Paying a declined, referred or undecided claim returns 409

## Phase 3: The UnderCover Agent

Replace the skeleton agent. Tools that wrap the API: `get_claim`, `get_policy`, `get_claim_history`, `get_policy_wording`, `record_decision` and `pay_claim`. `run(claim_id, thread_id)` fetches the instructions, starts the claim, runs `create_agent`, posts each step to the backend and returns the final reply. Write the real instructions in `backend/instructions.md`: read everything, decide from the policy wording alone, work out the payout as section 10 sets out, explain in two or three sentences with the section, record the decision, and pay only an approval at or under the limit. Add `agent/__main__.py` for `uv run -m agent <claim id>` and `uv run -m agent queue`.

Why this way: the agent holds no business rules of its own. It reads and acts through the same API as everyone else, so the backend's checks apply to it.

- [x] `uv run pytest -q agent` passes with coverage over 80%, using a stub model and the backend's `TestClient` on a temporary database
- [x] A stub run on CLM-1001 that reads the claim, approves $420.00 and pays leaves the claim `decided` and paid, with its tool calls, results and reply in `list_steps`
- [x] A stub run that approves $1,500.00 and then tries to pay gets the 409 back as a tool result; the claim stays `awaiting_signoff` and unpaid
- [x] The agent's system prompt equals what `get_instructions` returns (checked by a test)
- [x] The agent's tools reach the backend only through HTTP, and `agent/` has no reference to `data/` or `evals`
- [x] `uv run -m agent --help` prints the usage

## Phase 4: The dashboard: queue, claim and instructions

Replace the skeleton page. The queue: a table of claims with a status chip (waiting, in progress, waiting for sign-off, decided) in Sea Green, Marigold, Coral and Cerulean, with counts of each state. The claim page: the customer's story, the items, the documents, the policy and plan, and the decision with its payout, reason and policy section, plus the payment and sign-off. The instructions page: the agent's instructions, read only. Brand fonts, colors and surfaces; light and dark modes.

Why: it gives the team the first three things the spec asks to see, before the live view adds the fourth.

- [x] `npx vitest run --root dashboard --coverage` passes with coverage over 80%, with `fetch` stubbed
- [x] `npx tsc` and ESLint pass in strict mode, with no `any`
- [x] With `npm run dev`, the Playwright MCP server shows the queue at `http://localhost:5173` with 25 claims, all "Waiting"
- [x] Clicking CLM-1001 shows its story, its three items with amounts like $245.00, its documents and the Premium plan
- [x] The instructions page shows the text of `backend/instructions.md` with no way to edit it
- [x] Screenshots in light and dark mode match the brand: Instrument Sans text, rounded panels with no outline, the page backgrounds `#F0F4F5` and `#04232E`

## Phase 5: Live steps, sign-off and end-to-end tests

On the claim page, show the agent's steps as a timeline, polling every two seconds while the claim is in progress. For a claim waiting for sign-off, show the payout and a sign-off control listing the handlers who can approve over the limit. Move the Vite proxy target to `BACKEND_URL` and set Playwright up with its own backend and database.

Why: this completes what the team needs to see, and the end-to-end tests check the whole path, through the dashboard, without a model.

- [x] `npm run e2e` passes, with tests that:
  - [x] show the queue with 25 claims
  - [x] play an agent run on a claim through the API and see the steps appear on the open claim page without a reload, then the decision and reason
  - [x] approve a claim for $1,500.00 through the API, see "Waiting for sign-off", see that a payment through the API is refused, sign off in the dashboard as a handler who can, and see the claim decided and paid
  - [x] open the instructions page
- [x] The Playwright end-to-end run uses its own database and leaves `backend/undercover.db` unchanged
- [x] `npm run check` passes

## Phase 6: A real run, and the docs

Run the real agent on a few claims and watch it in the dashboard. Fix what the run shows, such as unclear instructions or tool results the model misreads. Update `docs/STATUS.md` with what's built and how to run it, and keep the README short.

Why: the tests prove the plumbing with a stub; this proves it works with the real model. Scoring the agent against the handlers' decisions in `data/evals/` is for the labs, so this phase doesn't open them.

- [ ] `uv run -m agent CLM-1001` runs with the configured model, records a decision with a payout, a two- or three-sentence reason and a policy section, and prints the reply
- [ ] While it runs, the Playwright MCP server shows the claim "In progress" with the steps appearing, then "Decided"
- [ ] `uv run -m agent queue` works through five more waiting claims; any approval over $1,000 is left waiting for sign-off and unpaid
- [ ] `docs/STATUS.md` describes the build, the commands (`npm run dev`, `npm run reset`, `uv run -m agent`) and the claim states
- [ ] `npm run check` passes

## Choices to review

- **Running the agent from the command line, not the dashboard.** Say if you want a "Run" button on waiting claims.
- **Sign-off releases the payment.** A handler's sign-off pays the approved amount, rather than the agent coming back to pay.
- **The agent sees the customer's claim history, not their contact details.**
- **Phase 6 spends a little on the model**, about six claims. Set `MODEL_NAME=openrouter/free` in `.env` to make it free.
