"""Authentication primitives for the compliance-triangle SaaS (stdlib only).

Security posture (honest about what this is and isn't)
------------------------------------------------------
* Passwords: PBKDF2-HMAC-SHA256 with a per-user 16-byte random salt. No
  plaintext is ever stored, and comparison uses ``hmac.compare_digest`` to
  avoid timing leaks.
* Sessions: opaque 32-byte URL-safe tokens stored server-side with an expiry,
  so a logout actually invalidates the token (unlike a stateless JWT).
* API keys: long-lived ``ct_``-prefixed tokens for programmatic access.
* Iterations are configurable via ``COMPLIANCE_TRIANGLE_PBKDF2_ITERS`` purely
  so the test-suite can run quickly; production uses the 200k default.

This is a portfolio-grade implementation, not a substitute for a hardened
identity provider (no MFA, no email verification, no password reset).
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import time
from typing import Tuple

DEFAULT_ITERATIONS = 200_000
SALT_BYTES = 16
SESSION_TTL_SECONDS = 7 * 24 * 3600  # 7 days
MIN_PASSWORD_LENGTH = 8

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _iterations() -> int:
    raw = os.environ.get("COMPLIANCE_TRIANGLE_PBKDF2_ITERS")
    if not raw:
        return DEFAULT_ITERATIONS
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_ITERATIONS


def hash_password(password: str) -> str:
    """Return an encoded ``pbkdf2_sha256$iters$salt_hex$hash_hex`` string."""
    iters = _iterations()
    salt = secrets.token_bytes(SALT_BYTES)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iters)
    return f"pbkdf2_sha256${iters}${salt.hex()}${dk.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    """Constant-time check of ``password`` against an encoded hash."""
    if not password or not encoded:
        return False
    try:
        algo, iters_s, salt_hex, dk_hex = encoded.split("$")
        if algo != "pbkdf2_sha256":
            return False
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"),
                                 bytes.fromhex(salt_hex), int(iters_s))
        return hmac.compare_digest(dk.hex(), dk_hex)
    except (ValueError, TypeError):
        return False


def new_session_token() -> str:
    return secrets.token_urlsafe(32)


def new_api_key() -> str:
    """Programmatic key. The ``ct_`` prefix makes leaked keys greppable."""
    return "ct_" + secrets.token_urlsafe(24)


def session_expiry(ttl: int = SESSION_TTL_SECONDS) -> float:
    return time.time() + ttl


def valid_email(email: str) -> bool:
    return bool(email) and bool(_EMAIL_RE.match(email.strip()))


def validate_password(password: str) -> Tuple[bool, str]:
    """Minimal password policy. Returns ``(ok, message)``."""
    if not password or len(password) < MIN_PASSWORD_LENGTH:
        return False, f"密码至少需要 {MIN_PASSWORD_LENGTH} 位字符"
    if len(password) > 200:
        return False, "密码过长（上限 200 位）"
    return True, ""


def public_user(row) -> dict:
    """Strip secrets before a user record crosses the API boundary."""
    return {
        "id": int(row["id"]),
        "email": row["email"],
        "display_name": row["display_name"] or "",
        "plan": row["plan"],
        "monthly_quota": int(row["monthly_quota"]),
        "created_at": row["created_at"],
    }
