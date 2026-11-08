"""The UnderCover backend."""

import json
import sqlite3
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel

from backend import db

INSTRUCTIONS = Path(__file__).parent / "instructions.md"


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    if not db.path().exists():
        db.seed(db.path())
    yield


app = FastAPI(title="UnderCover", lifespan=lifespan)


def database() -> Iterator[sqlite3.Connection]:
    connection = db.connect()
    try:
        with connection:
            yield connection
    finally:
        connection.close()


Db = Annotated[sqlite3.Connection, Depends(database)]


class Item(BaseModel):
    description: str
    category: str
    amount: float


class Document(BaseModel):
    name: str
    type: str
    content: str


class ClaimSummary(BaseModel):
    claim_id: str
    customer_name: str
    claim_type: str
    summary: str
    amount_claimed: float
    submitted_on: str
    status: str


class Decision(BaseModel):
    decision: str
    payout: float
    reason: str
    policy_section: str
    decided_at: str


class Payment(BaseModel):
    amount: float
    paid_at: str


class SignOff(BaseModel):
    handler_id: str
    handler_name: str
    signed_at: str


class Claim(ClaimSummary):
    policy_id: str
    customer_id: str
    incident_date: str
    incident_location: str
    story: str
    items: list[Item]
    documents: list[Document]
    decision: Decision | None
    payment: Payment | None
    sign_off: SignOff | None


class Handler(BaseModel):
    handler_id: str
    name: str
    role: str
    can_approve_over_limit: bool


class Text(BaseModel):
    text: str


class StepIn(BaseModel):
    kind: Literal["tool_call", "tool_result", "reply"]
    text: str


class Step(StepIn):
    step_id: int
    created_at: str


class DecisionIn(BaseModel):
    decision: Literal["approve", "decline", "refer"]
    payout: float
    reason: str
    policy_section: str


class PaymentIn(BaseModel):
    amount: float


class SignOffIn(BaseModel):
    handler_id: str


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def approval_limit(connection: sqlite3.Connection) -> float:
    return json.loads(document(connection, "company"))["payout_approval_limit"]


def set_status(connection: sqlite3.Connection, claim_id: str, status: str) -> None:
    connection.execute(
        "UPDATE claims SET status = ? WHERE claim_id = ?", (status, claim_id)
    )


def find(connection: sqlite3.Connection, table: str, key: str, value: str) -> Any:
    row = connection.execute(
        f"SELECT data FROM {table} WHERE {key} = ?",  # noqa: S608
        (value,),
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"Not found: {value}")
    return json.loads(row["data"])


def document(connection: sqlite3.Connection, name: str) -> str:
    return connection.execute(
        "SELECT content FROM documents WHERE name = ?", (name,)
    ).fetchone()["content"]


def customer_names(connection: sqlite3.Connection) -> dict[str, str]:
    rows = connection.execute("SELECT data FROM customers").fetchall()
    customers = [json.loads(row["data"]) for row in rows]
    return {customer["customer_id"]: customer["name"] for customer in customers}


def claim_row(connection: sqlite3.Connection, claim_id: str) -> sqlite3.Row:
    row = connection.execute(
        "SELECT * FROM claims WHERE claim_id = ?", (claim_id,)
    ).fetchone()
    if row is None:
        raise HTTPException(404, f"No claim {claim_id}")
    return row


def record(connection: sqlite3.Connection, table: str, claim_id: str) -> Any:
    row = connection.execute(
        f"SELECT * FROM {table} WHERE claim_id = ?",  # noqa: S608
        (claim_id,),
    ).fetchone()
    return None if row is None else dict(row)


def full_claim(connection: sqlite3.Connection, claim_id: str) -> Claim:
    row = claim_row(connection, claim_id)
    data = json.loads(row["data"])
    sign_off = record(connection, "sign_offs", claim_id)
    if sign_off:
        handler = find(connection, "handlers", "handler_id", sign_off["handler_id"])
        sign_off["handler_name"] = handler["name"]
    return Claim(
        **data,
        status=row["status"],
        customer_name=customer_names(connection)[data["customer_id"]],
        decision=record(connection, "decisions", claim_id),
        payment=record(connection, "payments", claim_id),
        sign_off=sign_off,
    )


@app.get("/api/health", operation_id="health")
def health() -> dict[str, str]:
    """Check that the backend is running."""
    return {"status": "ok"}


@app.get("/api/claims", operation_id="list_claims")
def list_claims(connection: Db) -> list[ClaimSummary]:
    """List every claim in the queue with where it stands."""
    names = customer_names(connection)
    rows = connection.execute("SELECT * FROM claims ORDER BY claim_id").fetchall()
    claims = []
    for row in rows:
        data = json.loads(row["data"])
        claims.append(
            ClaimSummary(
                **data,
                status=row["status"],
                customer_name=names[data["customer_id"]],
            )
        )
    return claims


@app.get("/api/claims/{claim_id}", operation_id="get_claim")
def get_claim(claim_id: str, connection: Db) -> Claim:
    """Get one claim in full, with its decision, payment and sign-off."""
    return full_claim(connection, claim_id)


@app.get("/api/policies/{policy_id}", operation_id="get_policy")
def get_policy(policy_id: str, connection: Db) -> dict[str, Any]:
    """Get a policy with its plan's limits and the add-ons it includes."""
    policy = find(connection, "policies", "policy_id", policy_id)
    plans = json.loads(document(connection, "plans"))
    policy["plan_details"] = next(
        plan for plan in plans["plans"] if plan["plan"] == policy["plan"]
    )
    policy["deductible_applies_to"] = plans["deductible_applies_to"]
    policy["add_on_details"] = [
        add_on for add_on in plans["add_ons"] if add_on["add_on"] in policy["add_ons"]
    ]
    return policy


@app.get("/api/customers/{customer_id}/history", operation_id="get_claim_history")
def get_claim_history(customer_id: str, connection: Db) -> list[dict[str, Any]]:
    """Get a customer's earlier claims, without their personal details."""
    return find(connection, "customers", "customer_id", customer_id)["previous_claims"]


@app.get("/api/policy-wording", operation_id="get_policy_wording")
def get_policy_wording(connection: Db) -> Text:
    """Get the policy wording, the contract with the customer."""
    return Text(text=document(connection, "policy_wording"))


@app.get("/api/instructions", operation_id="get_instructions")
def get_instructions() -> Text:
    """Get the UnderCover Agent's instructions."""
    return Text(text=INSTRUCTIONS.read_text(encoding="utf-8"))


@app.get("/api/handlers", operation_id="list_handlers")
def list_handlers(connection: Db) -> list[Handler]:
    """List the claims handlers."""
    rows = connection.execute("SELECT data FROM handlers ORDER BY handler_id")
    return [Handler(**json.loads(row["data"])) for row in rows]


@app.post("/api/claims/{claim_id}/start", operation_id="start_claim")
def start_claim(claim_id: str, connection: Db) -> Claim:
    """Mark a waiting claim as in progress."""
    if claim_row(connection, claim_id)["status"] != "waiting":
        raise HTTPException(409, f"Claim {claim_id} is not waiting")
    set_status(connection, claim_id, "in_progress")
    return full_claim(connection, claim_id)


@app.post("/api/claims/{claim_id}/steps", operation_id="record_step")
def record_step(claim_id: str, step: StepIn, connection: Db) -> Step:
    """Record a step the agent took on a claim."""
    claim_row(connection, claim_id)
    created_at = now()
    cursor = connection.execute(
        "INSERT INTO steps (claim_id, kind, text, created_at) VALUES (?, ?, ?, ?)",
        (claim_id, step.kind, step.text, created_at),
    )
    return Step(
        step_id=cursor.lastrowid or 0,
        kind=step.kind,
        text=step.text,
        created_at=created_at,
    )


@app.get("/api/claims/{claim_id}/steps", operation_id="list_steps")
def list_steps(claim_id: str, connection: Db) -> list[Step]:
    """List the steps the agent has taken on a claim, oldest first."""
    claim_row(connection, claim_id)
    rows = connection.execute(
        "SELECT step_id, kind, text, created_at FROM steps"
        " WHERE claim_id = ? ORDER BY step_id",
        (claim_id,),
    )
    return [Step(**dict(row)) for row in rows]


@app.post("/api/claims/{claim_id}/decision", operation_id="record_decision")
def record_decision(claim_id: str, decision: DecisionIn, connection: Db) -> Claim:
    """Record the decision on a claim in progress, with the payout if approved."""
    if claim_row(connection, claim_id)["status"] != "in_progress":
        raise HTTPException(409, f"Claim {claim_id} is not in progress")
    if decision.decision == "approve" and decision.payout <= 0:
        raise HTTPException(422, "An approval needs a payout above $0.00")
    if decision.decision != "approve" and decision.payout != 0:
        raise HTTPException(422, "Only an approval has a payout")
    connection.execute(
        "INSERT INTO decisions VALUES (?, ?, ?, ?, ?, ?)",
        (
            claim_id,
            decision.decision,
            round(decision.payout, 2),
            decision.reason,
            decision.policy_section,
            now(),
        ),
    )
    over_limit = decision.payout > approval_limit(connection)
    set_status(connection, claim_id, "awaiting_signoff" if over_limit else "decided")
    return full_claim(connection, claim_id)


@app.post("/api/claims/{claim_id}/payment", operation_id="pay_claim")
def pay_claim(claim_id: str, payment: PaymentIn, connection: Db) -> Claim:
    """Pay an approved claim its payout, if it needs no sign-off."""
    claim = full_claim(connection, claim_id)
    if claim.decision is None or claim.decision.decision != "approve":
        raise HTTPException(409, f"Claim {claim_id} has not been approved")
    if claim.payment is not None:
        raise HTTPException(409, f"Claim {claim_id} has already been paid")
    if round(payment.amount, 2) != claim.decision.payout:
        raise HTTPException(
            409,
            f"The amount must be the approved payout, ${claim.decision.payout:,.2f}",
        )
    limit = approval_limit(connection)
    if claim.decision.payout > limit:
        raise HTTPException(
            409,
            f"A payout over ${limit:,.2f} needs a handler's sign-off,"
            " and the handler's sign-off releases the payment",
        )
    connection.execute(
        "INSERT INTO payments VALUES (?, ?, ?)",
        (claim_id, claim.decision.payout, now()),
    )
    return full_claim(connection, claim_id)


@app.post("/api/claims/{claim_id}/sign-off", operation_id="sign_off_claim")
def sign_off_claim(claim_id: str, sign_off: SignOffIn, connection: Db) -> Claim:
    """Sign off a payout over the limit as a handler, which releases the payment."""
    claim = full_claim(connection, claim_id)
    if claim.status != "awaiting_signoff" or claim.decision is None:
        raise HTTPException(409, f"Claim {claim_id} is not waiting for sign-off")
    handler = find(connection, "handlers", "handler_id", sign_off.handler_id)
    if not handler["can_approve_over_limit"]:
        raise HTTPException(403, f"{handler['name']} cannot approve over the limit")
    signed_at = now()
    connection.execute(
        "INSERT INTO sign_offs VALUES (?, ?, ?)",
        (claim_id, sign_off.handler_id, signed_at),
    )
    connection.execute(
        "INSERT INTO payments VALUES (?, ?, ?)",
        (claim_id, claim.decision.payout, signed_at),
    )
    set_status(connection, claim_id, "decided")
    return full_claim(connection, claim_id)
