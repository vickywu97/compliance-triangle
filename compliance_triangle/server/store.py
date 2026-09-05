"""SQLite persistence for the compliance-triangle SaaS (stdlib only).

Design notes
------------
* Zero third-party dependencies — only ``sqlite3`` from the standard library.
* ``:memory:`` is a valid path, which is what the test-suite uses.
* Every public function takes an explicit ``conn`` so callers control
  transaction scope and tests can use an isolated in-memory database.
* Thread safety: the HTTP server is multi-threaded, so all DB access must be
  wrapped in :func:`db_lock` (a process-wide re-entrant lock).

Schema
------
users      — account record + plan quota
sessions   — opaque bearer/session tokens with expiry
api_keys   — long-lived programmatic keys (prefix ``ct_``)
analyses   — persisted verification runs (the product's audit trail)
usage      — per-user, per-month request counter driving the quota gate
"""
from __future__ import annotations

import contextlib
import os
import sqlite3
import threading
import time
from typing import Dict, List, Optional

DEFAULT_DB_DIR = os.path.join(os.path.expanduser("~"), ".compliance_triangle")
DEFAULT_DB_NAME = "saas.db"

# Free-plan default. Deliberately generous for a portfolio demo, and
# overridable per user so the quota gate is testable without waiting a month.
DEFAULT_MONTHLY_QUOTA = 50

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    email          TEXT    UNIQUE NOT NULL,
    password_hash  TEXT    NOT NULL,
    display_name   TEXT    NOT NULL DEFAULT '',
    plan           TEXT    NOT NULL DEFAULT 'free',
    monthly_quota  INTEGER NOT NULL DEFAULT 50,
    created_at     REAL    NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    token      TEXT    PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    created_at REAL    NOT NULL,
    expires_at REAL    NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS api_keys (
    key        TEXT    PRIMARY KEY,
    user_id    INTEGER NOT NULL,
    label      TEXT    NOT NULL DEFAULT '',
    created_at REAL    NOT NULL,
    revoked    INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_apikeys_user ON api_keys(user_id);

CREATE TABLE IF NOT EXISTS analyses (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    kind        TEXT    NOT NULL,          -- 'verify' | 'analyze'
    title       TEXT    NOT NULL DEFAULT '',
    input_text  TEXT    NOT NULL,
    answer_text TEXT    NOT NULL DEFAULT '',
    as_of       TEXT    NOT NULL,
    model       TEXT    NOT NULL DEFAULT '',
    result_json TEXT    NOT NULL,
    created_at  REAL    NOT NULL,
    FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_analyses_user ON analyses(user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS usage (
    user_id INTEGER NOT NULL,
    period  TEXT    NOT NULL,              -- 'YYYY-MM'
    count   INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY(user_id, period)
);
"""

_DB_LOCK = threading.RLock()


@contextlib.contextmanager
def db_lock():
    """Serialise DB access across the multi-threaded HTTP server.

    sqlite3 objects are not thread-safe by default; the server runs one thread
    per request, so every read/write must hold this lock.
    """
    with _DB_LOCK:
        yield


def default_db_path() -> str:
    """Resolve the DB path: ``$COMPLIANCE_TRIANGLE_DB`` or ``~/.compliance_triangle/saas.db``."""
    return (os.environ.get("COMPLIANCE_TRIANGLE_DB")
            or os.path.join(DEFAULT_DB_DIR, DEFAULT_DB_NAME))


def connect(db_path: Optional[str] = None) -> sqlite3.Connection:
    """Open (and initialise) the SQLite database."""
    path = db_path or default_db_path()
    if path != ":memory:":
        parent = os.path.dirname(path)
        if parent:
            os.makedirs(parent, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    init_db(conn)
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Create tables/indexes if missing. Safe to call repeatedly."""
    with db_lock():
        # executescript issues an implicit COMMIT before running.
        conn.executescript(SCHEMA)
        conn.commit()


def period_of(ts: Optional[float] = None) -> str:
    """Current usage period as ``YYYY-MM`` (UTC)."""
    return time.strftime("%Y-%m", time.gmtime(ts if ts is not None else time.time()))


# --------------------------------------------------------------------------- #
# users
# --------------------------------------------------------------------------- #
def create_user(conn: sqlite3.Connection, email: str, password_hash: str,
                display_name: str = "", plan: str = "free",
                monthly_quota: int = DEFAULT_MONTHLY_QUOTA) -> int:
    """Insert a user and return the new ``id``."""
    with db_lock():
        cur = conn.execute(
            "INSERT INTO users (email, password_hash, display_name, plan,"
            " monthly_quota, created_at) VALUES (?,?,?,?,?,?)",
            (email.strip().lower(), password_hash, display_name, plan,
             int(monthly_quota), time.time()),
        )
        conn.commit()
        return int(cur.lastrowid)


def get_user_by_email(conn: sqlite3.Connection, email: str) -> Optional[sqlite3.Row]:
    with db_lock():
        cur = conn.execute("SELECT * FROM users WHERE email = ?",
                           (email.strip().lower(),))
        return cur.fetchone()


def get_user_by_id(conn: sqlite3.Connection, user_id: int) -> Optional[sqlite3.Row]:
    with db_lock():
        cur = conn.execute("SELECT * FROM users WHERE id = ?", (int(user_id),))
        return cur.fetchone()


def update_user(conn: sqlite3.Connection, user_id: int, **fields) -> None:
    """Update allowed user columns (display_name / plan / monthly_quota)."""
    allowed = {"display_name", "plan", "monthly_quota"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    with db_lock():
        sets = ", ".join(f"{c} = ?" for c in cols)
        conn.execute(f"UPDATE users SET {sets} WHERE id = ?",
                     [fields[c] for c in cols] + [int(user_id)])
        conn.commit()


# --------------------------------------------------------------------------- #
# sessions
# --------------------------------------------------------------------------- #
def create_session(conn: sqlite3.Connection, user_id: int, token: str,
                   expires_at: float) -> None:
    with db_lock():
        conn.execute(
            "INSERT INTO sessions (token, user_id, created_at, expires_at)"
            " VALUES (?,?,?,?)", (token, int(user_id), time.time(), expires_at))
        conn.commit()


def get_session_user(conn: sqlite3.Connection, token: str) -> Optional[sqlite3.Row]:
    """Return the user row for a live session token, else ``None``."""
    if not token:
        return None
    with db_lock():
        cur = conn.execute(
            "SELECT u.* FROM sessions s JOIN users u ON u.id = s.user_id"
            " WHERE s.token = ? AND s.expires_at > ?", (token, time.time()))
        return cur.fetchone()


def delete_session(conn: sqlite3.Connection, token: str) -> None:
    with db_lock():
        conn.execute("DELETE FROM sessions WHERE token = ?", (token,))
        conn.commit()


def purge_expired_sessions(conn: sqlite3.Connection) -> int:
    """Delete expired sessions; returns the number removed."""
    with db_lock():
        cur = conn.execute("DELETE FROM sessions WHERE expires_at <= ?",
                           (time.time(),))
        conn.commit()
        return int(cur.rowcount or 0)


# --------------------------------------------------------------------------- #
# api keys
# --------------------------------------------------------------------------- #
def create_api_key(conn: sqlite3.Connection, user_id: int, key: str,
                   label: str = "") -> None:
    with db_lock():
        conn.execute(
            "INSERT INTO api_keys (key, user_id, label, created_at)"
            " VALUES (?,?,?,?)", (key, int(user_id), label, time.time()))
        conn.commit()


def resolve_api_key(conn: sqlite3.Connection, key: str) -> Optional[sqlite3.Row]:
    """Return the owning user for a non-revoked API key, else ``None``."""
    if not key:
        return None
    with db_lock():
        cur = conn.execute(
            "SELECT u.* FROM api_keys k JOIN users u ON u.id = k.user_id"
            " WHERE k.key = ? AND k.revoked = 0", (key,))
        return cur.fetchone()


def list_api_keys(conn: sqlite3.Connection, user_id: int) -> List[sqlite3.Row]:
    with db_lock():
        cur = conn.execute(
            "SELECT key, label, created_at, revoked FROM api_keys"
            " WHERE user_id = ? ORDER BY created_at DESC", (int(user_id),))
        return list(cur.fetchall())


def revoke_api_key(conn: sqlite3.Connection, user_id: int, key: str) -> bool:
    with db_lock():
        cur = conn.execute(
            "UPDATE api_keys SET revoked = 1 WHERE key = ? AND user_id = ?",
            (key, int(user_id)))
        conn.commit()
        return int(cur.rowcount or 0) > 0


# --------------------------------------------------------------------------- #
# analyses (the audit trail)
# --------------------------------------------------------------------------- #
def save_analysis(conn: sqlite3.Connection, user_id: int, kind: str,
                  title: str, input_text: str, answer_text: str,
                  as_of: str, model: str, result: Dict) -> int:
    """Persist one verification run and return its ``id``."""
    import json
    with db_lock():
        cur = conn.execute(
            "INSERT INTO analyses (user_id, kind, title, input_text,"
            " answer_text, as_of, model, result_json, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (int(user_id), kind, title, input_text, answer_text, as_of, model,
             json.dumps(result, ensure_ascii=False), time.time()),
        )
        conn.commit()
        return int(cur.lastrowid)


def list_analyses(conn: sqlite3.Connection, user_id: int, limit: int = 50,
                  offset: int = 0) -> List[sqlite3.Row]:
    """History for one user only (tenant isolation is enforced here)."""
    with db_lock():
        cur = conn.execute(
            "SELECT id, kind, title, as_of, model, created_at,"
            " substr(input_text, 1, 160) AS preview FROM analyses"
            " WHERE user_id = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (int(user_id), int(limit), int(offset)))
        return list(cur.fetchall())


def get_analysis(conn: sqlite3.Connection, user_id: int,
                 analysis_id: int) -> Optional[sqlite3.Row]:
    with db_lock():
        cur = conn.execute("SELECT * FROM analyses WHERE id = ? AND user_id = ?",
                           (int(analysis_id), int(user_id)))
        return cur.fetchone()


def delete_analysis(conn: sqlite3.Connection, user_id: int,
                    analysis_id: int) -> bool:
    with db_lock():
        cur = conn.execute("DELETE FROM analyses WHERE id = ? AND user_id = ?",
                           (int(analysis_id), int(user_id)))
        conn.commit()
        return int(cur.rowcount or 0) > 0


# --------------------------------------------------------------------------- #
# usage / quota
# --------------------------------------------------------------------------- #
def increment_usage(conn: sqlite3.Connection, user_id: int,
                    period: Optional[str] = None, amount: int = 1) -> int:
    """Add to the period counter and return the new total."""
    period = period or period_of()
    with db_lock():
        conn.execute(
            "INSERT INTO usage (user_id, period, count) VALUES (?,?,?)"
            " ON CONFLICT(user_id, period)"
            " DO UPDATE SET count = count + excluded.count",
            (int(user_id), period, int(amount)))
        conn.commit()
        cur = conn.execute("SELECT count FROM usage WHERE user_id = ? AND period = ?",
                           (int(user_id), period))
        row = cur.fetchone()
        return int(row["count"]) if row else 0


def get_usage(conn: sqlite3.Connection, user_id: int,
              period: Optional[str] = None) -> int:
    period = period or period_of()
    with db_lock():
        cur = conn.execute("SELECT count FROM usage WHERE user_id = ? AND period = ?",
                           (int(user_id), period))
        row = cur.fetchone()
        return int(row["count"]) if row else 0


def usage_summary(conn: sqlite3.Connection, user: sqlite3.Row,
                  period: Optional[str] = None) -> Dict:
    """Convenience payload for ``/api/me`` and the frontend usage widget."""
    period = period or period_of()
    used = get_usage(conn, int(user["id"]), period)
    quota = int(user["monthly_quota"])
    return {
        "period": period,
        "used": used,
        "quota": quota,
        "remaining": max(0, quota - used),
        "plan": user["plan"],
    }
