"""The UnderCover Agent."""

import json
import os
from typing import Any, Literal

import httpx
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool, tool
from langchain_openai import ChatOpenAI
from pydantic import SecretStr

load_dotenv(override=True)

BACKEND_URL = "http://localhost:8000"
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "openai/gpt-6-luna"
STEP_LENGTH = 500


def backend() -> httpx.Client:
    """Return a client for the UnderCover backend."""
    return httpx.Client(base_url=BACKEND_URL, timeout=30)


def call(method: str, path: str, body: dict[str, Any] | None = None) -> str:
    """Call the backend and return its reply, or why it refused, as text."""
    with backend() as client:
        response = client.request(method, path, json=body)
    if response.is_error:
        return f"Refused ({response.status_code}): {response.json()['detail']}"
    return response.text


def claim_tools(claim_id: str) -> list[BaseTool]:
    """Return the agent's tools, with the claim it may act on fixed."""

    @tool
    def get_claim() -> str:
        """Get the claim: the customer's story, the items claimed and documents."""
        return call("GET", f"/api/claims/{claim_id}")

    @tool
    def get_policy(policy_id: str) -> str:
        """Get a policy with its plan's limits, deductible and add-ons."""
        return call("GET", f"/api/policies/{policy_id}")

    @tool
    def get_claim_history(customer_id: str) -> str:
        """Get the customer's earlier claims."""
        return call("GET", f"/api/customers/{customer_id}/history")

    @tool
    def get_policy_wording() -> str:
        """Get the policy wording, the contract that decisions follow."""
        return json.loads(call("GET", "/api/policy-wording"))["text"]

    @tool
    def record_decision(
        decision: Literal["approve", "decline", "refer"],
        payout: float,
        reason: str,
        policy_section: str,
    ) -> str:
        """Record the decision on the claim. The payout is 0 unless approving."""
        body = {
            "decision": decision,
            "payout": payout,
            "reason": reason,
            "policy_section": policy_section,
        }
        return call("POST", f"/api/claims/{claim_id}/decision", body)

    @tool
    def pay_claim(amount: float) -> str:
        """Pay the approved payout on the claim."""
        return call("POST", f"/api/claims/{claim_id}/payment", {"amount": amount})

    return [
        get_claim,
        get_policy,
        get_claim_history,
        get_policy_wording,
        record_decision,
        pay_claim,
    ]


def model() -> ChatOpenAI:
    """Return the model named in MODEL_NAME, or GPT-6 Luna by default."""
    name = os.getenv("MODEL_NAME")
    return ChatOpenAI(
        model=name or DEFAULT_MODEL,
        base_url=OPENROUTER_BASE_URL,
        api_key=SecretStr(os.environ["OPENROUTER_API_KEY"]),
        reasoning_effort=None if name else "low",
    )


def steps(message: BaseMessage) -> list[tuple[str, str]]:
    """Turn one of the agent's messages into the steps the dashboard shows."""
    if isinstance(message, ToolMessage):
        return [("tool_result", f"{message.name}: {message.text}")]
    if not isinstance(message, AIMessage):
        return []
    found = [("reply", str(message.text))] if message.text else []
    for tool_call in message.tool_calls:
        found.append(
            ("tool_call", f"{tool_call['name']}({json.dumps(tool_call['args'])})")
        )
    return found


def record_step(claim_id: str, kind: str, text: str) -> None:
    """Post one step to the backend."""
    body = {"kind": kind, "text": text[:STEP_LENGTH]}
    with backend() as client:
        client.post(f"/api/claims/{claim_id}/steps", json=body).raise_for_status()


def run(claim_id: str, thread_id: str, llm: BaseChatModel | None = None) -> str:
    """Run the agent on one claim, recording each step, and return its reply."""
    with backend() as client:
        instructions = client.get("/api/instructions").raise_for_status().json()
        client.post(f"/api/claims/{claim_id}/start").raise_for_status()
    agent = create_agent(
        llm or model(), tools=claim_tools(claim_id), system_prompt=instructions["text"]
    )
    reply = ""
    for update in agent.stream(
        {"messages": [{"role": "user", "content": f"Please decide claim {claim_id}."}]},
        config={"configurable": {"thread_id": thread_id}},
        stream_mode="updates",
    ):
        for node in update.values():
            for message in node["messages"]:
                for kind, text in steps(message):
                    record_step(claim_id, kind, text)
                    if kind == "reply":
                        reply = text
    return reply


def waiting_claims() -> list[str]:
    """Return the ids of the claims waiting in the queue."""
    with backend() as client:
        claims = client.get("/api/claims").raise_for_status().json()
    return [claim["claim_id"] for claim in claims if claim["status"] == "waiting"]
