"""Run the UnderCover Agent from the command line."""

import argparse
from uuid import uuid4

from agent.main import run, waiting_claims


def main(argv: list[str] | None = None) -> None:
    """Run the agent on the claims named, or on every waiting claim."""
    parser = argparse.ArgumentParser(
        prog="uv run -m agent",
        description="Run the UnderCover Agent on claims in the queue.",
    )
    parser.add_argument(
        "claims", nargs="+", help="claim ids such as CLM-1001, or 'queue'"
    )
    args = parser.parse_args(argv)
    claim_ids = waiting_claims() if args.claims == ["queue"] else args.claims
    for claim_id in claim_ids:
        print(f"{claim_id}: {run(claim_id, str(uuid4()))}\n", flush=True)


if __name__ == "__main__":
    main()
