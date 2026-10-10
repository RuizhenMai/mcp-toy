import hashlib
import os
import sqlite3
from contextlib import contextmanager

# On Railway the volume is mounted at RAILWAY_VOLUME_MOUNT_PATH (/data).
# Locally we fall back to a file next to the code.
DB_PATH = os.getenv(
    "DB_PATH",
    os.path.join(os.getenv("RAILWAY_VOLUME_MOUNT_PATH", "."), "app.db"),
)

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id                 INTEGER PRIMARY KEY,
    stripe_customer_id TEXT NOT NULL UNIQUE,
    email              TEXT,
    api_key_hash       TEXT NOT NULL UNIQUE,
    status             TEXT NOT NULL DEFAULT 'active',
    created_at         TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS email_log (
    id                   INTEGER PRIMARY KEY,
    account_id           INTEGER NOT NULL REFERENCES accounts(id),
    stripe_event_id      TEXT NOT NULL UNIQUE,
    reported_to_stripe   INTEGER NOT NULL DEFAULT 0,
    created_at           TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS email_log_account_created
    ON email_log (account_id, created_at);
"""


def hash_key(api_key: str) -> str:
    """API keys are random, so a plain SHA-256 is enough; never store raw keys."""
    return hashlib.sha256(api_key.encode()).hexdigest()


@contextmanager
def connect(path: str | None = None):
    conn = sqlite3.connect(path or DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        with conn:  # commit on success, rollback on error
            yield conn
    finally:
        conn.close()


def init_db(path: str | None = None) -> None:
    with connect(path) as conn:
        conn.executescript(SCHEMA)


def create_account(
    stripe_customer_id: str,
    email: str | None,
    api_key: str,
    path: str | None = None,
) -> int:
    with connect(path) as conn:
        cur = conn.execute(
            "INSERT INTO accounts (stripe_customer_id, email, api_key_hash) "
            "VALUES (?, ?, ?)",
            (stripe_customer_id, email, hash_key(api_key)),
        )
        return cur.lastrowid


def get_account_by_key(api_key: str, path: str | None = None):
    with connect(path) as conn:
        return conn.execute(
            "SELECT * FROM accounts WHERE api_key_hash = ?",
            (hash_key(api_key),),
        ).fetchone()


def set_status(
    stripe_customer_id: str, status: str, path: str | None = None
) -> None:
    with connect(path) as conn:
        conn.execute(
            "UPDATE accounts SET status = ? WHERE stripe_customer_id = ?",
            (status, stripe_customer_id),
        )


def record_send(
    account_id: int, stripe_event_id: str, path: str | None = None
) -> None:
    with connect(path) as conn:
        conn.execute(
            "INSERT INTO email_log (account_id, stripe_event_id) VALUES (?, ?)",
            (account_id, stripe_event_id),
        )


def mark_reported(stripe_event_id: str, path: str | None = None) -> None:
    with connect(path) as conn:
        conn.execute(
            "UPDATE email_log SET reported_to_stripe = 1 "
            "WHERE stripe_event_id = ?",
            (stripe_event_id,),
        )


def count_sends_since(
    account_id: int, since: str, path: str | None = None
) -> int:
    """`since` is a UTC 'YYYY-MM-DD HH:MM:SS' string, matching CURRENT_TIMESTAMP."""
    with connect(path) as conn:
        return conn.execute(
            "SELECT COUNT(*) FROM email_log "
            "WHERE account_id = ? AND created_at >= ?",
            (account_id, since),
        ).fetchone()[0]
