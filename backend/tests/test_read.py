from pathlib import Path

from fastapi.testclient import TestClient

from backend import db
from backend.main import INSTRUCTIONS, app


def test_health(client):
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_list_claims(client):
    claims = client.get("/api/claims").json()
    assert len(claims) == 25
    assert {claim["status"] for claim in claims} == {"waiting"}
    assert claims[0] == {
        "claim_id": "CLM-1001",
        "customer_name": "Maya Patel",
        "claim_type": "trip_delay",
        "summary": "Flight home canceled by the airline, rebooked the next morning",
        "amount_claimed": 420.0,
        "submitted_on": "2026-06-24",
        "status": "waiting",
    }


def test_security_claim_stays_out_of_the_queue(client):
    claim_ids = {claim["claim_id"] for claim in client.get("/api/claims").json()}
    assert "CLM-1901" not in claim_ids
    assert client.get("/api/claims/CLM-1901").status_code == 404


def test_backend_never_reads_the_answer_key():
    for source in Path("backend").glob("*.py"):
        assert "evals" not in source.read_text(encoding="utf-8")


def test_get_claim(client):
    claim = client.get("/api/claims/CLM-1001").json()
    assert claim["story"].startswith("My flight home from Rome")
    assert len(claim["items"]) == 3
    assert claim["documents"][0]["type"] == "carrier_report"
    assert claim["decision"] is None
    assert claim["payment"] is None
    assert claim["sign_off"] is None


def test_get_claim_not_found(client):
    response = client.get("/api/claims/CLM-9999")
    assert response.status_code == 404
    assert response.json() == {"detail": "No claim CLM-9999"}


def test_get_policy(client):
    policy = client.get("/api/policies/POL-2001").json()
    assert policy["plan"] == "premium"
    assert policy["plan_details"]["deductible"] == 50.0
    assert policy["plan_details"]["trip_delay_max"] == 800.0
    assert policy["deductible_applies_to"] == ["baggage", "emergency_medical"]
    assert policy["add_on_details"] == []


def test_get_policy_with_add_ons(client):
    policies = db.load("policies.json")
    policy_id = next(policy for policy in policies if policy["add_ons"])["policy_id"]
    policy = client.get(f"/api/policies/{policy_id}").json()
    assert [add_on["add_on"] for add_on in policy["add_on_details"]] == policy[
        "add_ons"
    ]


def test_get_policy_not_found(client):
    assert client.get("/api/policies/POL-0000").status_code == 404


def test_get_claim_history(client):
    history = client.get("/api/customers/CUS-3001/history").json()
    assert [claim["claim_id"] for claim in history] == ["CLM-0412"]
    text = str(history)
    for private in ["maya.patel@example.com", "555", "Wayne Street", "1988-03-14"]:
        assert private not in text


def test_get_policy_wording(client):
    text = client.get("/api/policy-wording").json()["text"]
    assert text == (db.DATA / "policy_wording.md").read_text(encoding="utf-8")


def test_get_instructions(client):
    text = client.get("/api/instructions").json()["text"]
    assert text == INSTRUCTIONS.read_text(encoding="utf-8")


def test_list_handlers(client):
    handlers = client.get("/api/handlers").json()
    assert [handler["handler_id"] for handler in handlers] == [
        "HND-01",
        "HND-02",
        "HND-03",
    ]
    assert "email" not in handlers[0]


def test_seeds_on_startup(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "new" / "startup.db"))
    with TestClient(app) as client:
        assert len(client.get("/api/claims").json()) == 25


def test_every_operation_is_documented_with_no_optional_inputs():
    schema = app.openapi()
    for path in schema["paths"].values():
        for operation in path.values():
            assert operation["operationId"]
            description = operation["description"]
            assert description
            assert "\n" not in description
            for parameter in operation.get("parameters", []):
                assert parameter["required"]
            body = operation.get("requestBody")
            if body:
                ref = body["content"]["application/json"]["schema"]["$ref"]
                model = schema["components"]["schemas"][ref.split("/")[-1]]
                assert set(model["required"]) == set(model["properties"])
