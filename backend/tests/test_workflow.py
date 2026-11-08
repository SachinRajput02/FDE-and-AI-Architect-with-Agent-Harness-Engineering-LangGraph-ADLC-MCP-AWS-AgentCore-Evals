import json

import pytest

from backend import db


def start(client, claim_id="CLM-1001"):
    return client.post(f"/api/claims/{claim_id}/start")


def decide(client, decision="approve", payout=420.0, claim_id="CLM-1001"):
    return client.post(
        f"/api/claims/{claim_id}/decision",
        json={
            "decision": decision,
            "payout": payout,
            "reason": "Covered by Trip Delay.",
            "policy_section": "3. Trip Delay",
        },
    )


def pay(client, amount, claim_id="CLM-1001"):
    return client.post(f"/api/claims/{claim_id}/payment", json={"amount": amount})


def sign_off(client, handler_id="HND-01", claim_id="CLM-1001"):
    return client.post(
        f"/api/claims/{claim_id}/sign-off", json={"handler_id": handler_id}
    )


def test_start_claim(client):
    assert start(client).json()["status"] == "in_progress"
    response = start(client)
    assert response.status_code == 409
    assert start(client, "CLM-9999").status_code == 404


def test_steps(client):
    assert client.get("/api/claims/CLM-1001/steps").json() == []
    for kind, text in [("tool_call", "get_claim()"), ("reply", "Approved.")]:
        response = client.post(
            "/api/claims/CLM-1001/steps", json={"kind": kind, "text": text}
        )
        assert response.status_code == 200
    steps = client.get("/api/claims/CLM-1001/steps").json()
    assert [(step["kind"], step["text"]) for step in steps] == [
        ("tool_call", "get_claim()"),
        ("reply", "Approved."),
    ]
    assert steps[0]["step_id"] < steps[1]["step_id"]
    assert steps[0]["created_at"]


def test_step_needs_a_known_kind_and_claim(client):
    response = client.post(
        "/api/claims/CLM-1001/steps", json={"kind": "other", "text": "x"}
    )
    assert response.status_code == 422
    assert client.get("/api/claims/CLM-9999/steps").status_code == 404


def test_decision_needs_a_claim_in_progress(client):
    assert decide(client).status_code == 409


@pytest.mark.parametrize(
    ("decision", "payout"), [("decline", 10.0), ("refer", 5.0), ("approve", 0.0)]
)
def test_decision_payout_must_fit_the_decision(client, decision, payout):
    start(client)
    assert decide(client, decision, payout).status_code == 422
    assert client.get("/api/claims/CLM-1001").json()["status"] == "in_progress"


@pytest.mark.parametrize("decision", ["decline", "refer"])
def test_decline_or_refer(client, decision):
    start(client)
    claim = decide(client, decision, 0).json()
    assert claim["status"] == "decided"
    assert claim["decision"]["decision"] == decision
    assert claim["decision"]["policy_section"] == "3. Trip Delay"
    response = pay(client, 0)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 has not been approved"


def test_pay_undecided_claim(client):
    assert pay(client, 420).status_code == 409


def test_approve_and_pay_under_the_limit(client):
    start(client)
    claim = decide(client).json()
    assert claim["status"] == "decided"
    assert claim["payment"] is None
    claim = pay(client, 420.0).json()
    assert claim["payment"]["amount"] == 420.0
    response = pay(client, 420.0)
    assert response.status_code == 409
    assert response.json()["detail"] == "Claim CLM-1001 has already been paid"


def test_pay_must_match_the_approved_payout(client):
    start(client)
    decide(client)
    response = pay(client, 1420.0)
    assert response.status_code == 409
    assert (
        response.json()["detail"] == "The amount must be the approved payout, $420.00"
    )


def test_payout_over_the_limit_waits_for_sign_off(client):
    start(client)
    claim = decide(client, payout=1500.0).json()
    assert claim["status"] == "awaiting_signoff"
    response = pay(client, 1500.0)
    assert response.status_code == 409
    assert "needs a handler's sign-off" in response.json()["detail"]
    assert client.get("/api/claims/CLM-1001").json()["payment"] is None


def test_payout_at_the_limit_needs_no_sign_off(client):
    start(client)
    assert decide(client, payout=1000.0).json()["status"] == "decided"
    assert pay(client, 1000.0).status_code == 200


def test_sign_off_releases_the_payment(client):
    start(client)
    decide(client, payout=1500.0)
    claim = sign_off(client).json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 1500.0
    assert claim["sign_off"]["handler_name"] == "Dana Whitfield"
    assert sign_off(client).status_code == 409
    assert pay(client, 1500.0).status_code == 409


def test_sign_off_needs_a_claim_waiting_for_it(client):
    start(client)
    decide(client)
    assert sign_off(client).status_code == 409


def test_sign_off_needs_a_handler_who_can(client):
    handler = {
        "handler_id": "HND-99",
        "name": "Sam Trainee",
        "role": "Trainee",
        "email": "sam@undercover.example",
        "can_approve_over_limit": False,
    }
    with db.connect() as connection:
        connection.execute(
            "INSERT INTO handlers VALUES (?, ?)", ("HND-99", json.dumps(handler))
        )
    start(client)
    decide(client, payout=1500.0)
    assert sign_off(client, "HND-00").status_code == 404
    response = sign_off(client, "HND-99")
    assert response.status_code == 403
    assert client.get("/api/claims/CLM-1001").json()["status"] == "awaiting_signoff"
