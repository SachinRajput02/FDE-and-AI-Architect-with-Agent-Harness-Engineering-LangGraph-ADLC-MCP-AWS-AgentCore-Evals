from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from agent import __main__ as cli
from agent import main
from backend import db
from backend.main import INSTRUCTIONS, app


class StubModel(GenericFakeChatModel):
    """A chat model that gives scripted replies in place of a real model."""

    def bind_tools(self, tools, **kwargs):
        return self


class RecordingStub(StubModel):
    """A stub model that keeps the system prompt it was given."""

    system_prompts: list[str] = []

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        self.system_prompts.append(messages[0].text)
        return super()._generate(messages, stop, run_manager, **kwargs)


@pytest.fixture(autouse=True)
def backend(tmp_path, monkeypatch):
    monkeypatch.setenv("UNDERCOVER_DB", str(tmp_path / "test.db"))
    db.seed(db.path())
    monkeypatch.setattr(main, "backend", lambda: TestClient(app))
    return TestClient(app)


def calls(*tool_calls):
    return AIMessage(
        content="",
        tool_calls=[
            {"name": name, "args": args, "id": str(index)}
            for index, (name, args) in enumerate(tool_calls)
        ],
    )


def decision(payout):
    return (
        "record_decision",
        {
            "decision": "approve",
            "payout": payout,
            "reason": "The delay is covered.",
            "policy_section": "3. Trip Delay",
        },
    )


def stub(*replies):
    return StubModel(messages=iter(replies))


def test_run_approves_and_pays(backend):
    replies = [
        calls(("get_claim", {})),
        calls(("get_policy", {"policy_id": "POL-2001"})),
        calls(
            ("get_claim_history", {"customer_id": "CUS-3001"}),
            ("get_policy_wording", {}),
        ),
        calls(decision(420.0)),
        calls(("pay_claim", {"amount": 420.0})),
        AIMessage(content="Approved, $420.00."),
    ]
    assert main.run("CLM-1001", "thread-1", stub(*replies)) == "Approved, $420.00."
    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "decided"
    assert claim["payment"]["amount"] == 420.0
    steps = backend.get("/api/claims/CLM-1001/steps").json()
    assert [step["kind"] for step in steps[:2]] == ["tool_call", "tool_result"]
    assert steps[0]["text"] == "get_claim({})"
    assert steps[1]["text"].startswith("get_claim: {")
    assert steps[-1] == {**steps[-1], "kind": "reply", "text": "Approved, $420.00."}
    assert all(len(step["text"]) <= main.STEP_LENGTH for step in steps)


def test_payment_over_the_limit_is_refused(backend):
    replies = [
        calls(decision(1500.0)),
        calls(("pay_claim", {"amount": 1500.0})),
        AIMessage(content="Approved, waiting for sign-off."),
    ]
    main.run("CLM-1001", "thread-1", stub(*replies))
    claim = backend.get("/api/claims/CLM-1001").json()
    assert claim["status"] == "awaiting_signoff"
    assert claim["payment"] is None
    results = [
        step["text"]
        for step in backend.get("/api/claims/CLM-1001/steps").json()
        if step["kind"] == "tool_result"
    ]
    assert results[-1].startswith("pay_claim: Refused (409): A payout over $1,000.00")


def test_system_prompt_is_the_instructions():
    model = RecordingStub(messages=iter([AIMessage(content="Done.")]))
    main.run("CLM-1001", "thread-1", model)
    assert model.system_prompts == [INSTRUCTIONS.read_text(encoding="utf-8")]


def test_steps_from_messages():
    message = AIMessage(
        content="Checking.", tool_calls=[{"name": "get_claim", "args": {}, "id": "1"}]
    )
    assert main.steps(message) == [
        ("reply", "Checking."),
        ("tool_call", "get_claim({})"),
    ]
    result = ToolMessage(content="ok", name="get_claim", tool_call_id="1")
    assert main.steps(result) == [("tool_result", "get_claim: ok")]
    assert main.steps(HumanMessage(content="hi")) == []


def test_waiting_claims(backend):
    backend.post("/api/claims/CLM-1001/start")
    waiting = main.waiting_claims()
    assert len(waiting) == 24
    assert "CLM-1001" not in waiting


def test_agent_reaches_data_only_through_the_backend():
    for source in Path("agent").glob("*.py"):
        text = source.read_text(encoding="utf-8")
        assert "evals" not in text
        assert "data/" not in text
        assert "from backend" not in text


def test_model_name(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    monkeypatch.delenv("MODEL_NAME", raising=False)
    assert main.model().model_name == "openai/gpt-6-luna"
    monkeypatch.setenv("MODEL_NAME", "openrouter/free")
    assert main.model().model_name == "openrouter/free"


def test_cli_runs_named_claims(monkeypatch, capsys):
    ran = []
    monkeypatch.setattr(
        cli, "run", lambda claim_id, thread_id: ran.append(claim_id) or "Done."
    )
    cli.main(["CLM-1001", "CLM-1002"])
    assert ran == ["CLM-1001", "CLM-1002"]
    assert "CLM-1001: Done." in capsys.readouterr().out


def test_cli_runs_the_queue(monkeypatch):
    ran = []
    monkeypatch.setattr(
        cli, "run", lambda claim_id, thread_id: ran.append(claim_id) or ""
    )
    cli.main(["queue"])
    assert len(ran) == 25


def test_cli_help(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    assert "uv run -m agent" in capsys.readouterr().out
