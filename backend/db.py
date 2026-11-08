"""The UnderCover database: SQLite, built from the business data in data/."""

import json
import os
import sqlite3
from contextlib import closing
from pathlib import Path
from typing import Any

DATA = Path(__file__).parent.parent / "data"
DEFAULT_PATH = Path(__file__).parent / "undercover.db"

SCHEMA = """
CREATE TABLE claims (
    claim_id TEXT PRIMARY KEY, status TEXT NOT NULL, data TEXT NOT NULL
);
CREATE TABLE policies (policy_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE customers (customer_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE handlers (handler_id TEXT PRIMARY KEY, data TEXT NOT NULL);
CREATE TABLE documents (name TEXT PRIMARY KEY, content TEXT NOT NULL);
CREATE TABLE decisions (
    claim_id TEXT PRIMARY KEY, decision TEXT NOT NULL, payout REAL NOT NULL,
    reason TEXT NOT NULL, policy_section TEXT NOT NULL, decided_at TEXT NOT NULL
);
CREATE TABLE payments (
    claim_id TEXT PRIMARY KEY, amount REAL NOT NULL, paid_at TEXT NOT NULL
);
CREATE TABLE sign_offs (
    claim_id TEXT PRIMARY KEY, handler_id TEXT NOT NULL, signed_at TEXT NOT NULL
);
CREATE TABLE steps (
    step_id INTEGER PRIMARY KEY AUTOINCREMENT, claim_id TEXT NOT NULL,
    kind TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL
);
"""


def path() -> Path:
    """Return the database's path: UNDERCOVER_DB, or backend/undercover.db."""
    return Path(os.getenv("UNDERCOVER_DB", DEFAULT_PATH))


def connect() -> sqlite3.Connection:
    """Open the database."""
    connection = sqlite3.connect(path(), check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


def load(name: str) -> Any:
    """Read one of the JSON files in data/."""
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def seed(target: Path) -> None:
    """Build a fresh database at target from the queue and records in data/."""
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)
    with closing(sqlite3.connect(target)) as connection, connection:
        connection.executescript(SCHEMA)
        for claim in load("claims.json"):
            claim.pop("status")
            connection.execute(
                "INSERT INTO claims VALUES (?, 'waiting', ?)",
                (claim["claim_id"], json.dumps(claim)),
            )
        for table, key, name in [
            ("policies", "policy_id", "policies.json"),
            ("customers", "customer_id", "customers.json"),
            ("handlers", "handler_id", "handlers.json"),
        ]:
            connection.executemany(
                f"INSERT INTO {table} VALUES (?, ?)",  # noqa: S608
                [(row[key], json.dumps(row)) for row in load(name)],
            )
        connection.executemany(
            "INSERT INTO documents VALUES (?, ?)",
            [
                ("company", (DATA / "company.json").read_text(encoding="utf-8")),
                ("plans", (DATA / "plans.json").read_text(encoding="utf-8")),
                (
                    "policy_wording",
                    (DATA / "policy_wording.md").read_text(encoding="utf-8"),
                ),
            ],
        )


if __name__ == "__main__":
    seed(path())
    print(f"Seeded {path()}")
