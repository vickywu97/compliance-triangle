"""Tests for the authentication primitives (password hashing, sessions, keys).

Password hashing is deliberately slowed down in production (200k PBKDF2
iterations); the suite drops it to a token value so tests stay fast. The
security properties under test (constant-time compare, per-user salt, no
plaintext) are independent of the iteration count.
"""
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ.setdefault("COMPLIANCE_TRIANGLE_PBKDF2_ITERS", "1000")

from compliance_triangle.server import auth  # noqa: E402


class TestPasswordHashing(unittest.TestCase):
    def test_correct_password_verifies(self):
        encoded = auth.hash_password("correct horse battery")
        self.assertTrue(auth.verify_password("correct horse battery", encoded))

    def test_wrong_password_fails(self):
        encoded = auth.hash_password("correct horse battery")
        self.assertFalse(auth.verify_password("wrong password", encoded))

    def test_salt_is_per_user(self):
        """Same password must not produce the same hash twice."""
        a = auth.hash_password("same-password-123")
        b = auth.hash_password("same-password-123")
        self.assertNotEqual(a, b)
        self.assertTrue(auth.verify_password("same-password-123", a))
        self.assertTrue(auth.verify_password("same-password-123", b))

    def test_no_plaintext_in_encoded(self):
        encoded = auth.hash_password("supersecret12345")
        self.assertNotIn("supersecret12345", encoded)
        self.assertTrue(encoded.startswith("pbkdf2_sha256$"))

    def test_malformed_hash_is_rejected_not_raised(self):
        for bad in ("", "garbage", "pbkdf2_sha256$only$three", "md5$1$aa$bb"):
            self.assertFalse(auth.verify_password("whatever", bad))

    def test_empty_inputs_are_false(self):
        self.assertFalse(auth.verify_password("", auth.hash_password("x12345678")))
        self.assertFalse(auth.verify_password("x12345678", ""))


class TestTokens(unittest.TestCase):
    def test_session_tokens_are_unique(self):
        tokens = {auth.new_session_token() for _ in range(100)}
        self.assertEqual(len(tokens), 100)

    def test_api_key_has_greppable_prefix(self):
        key = auth.new_api_key()
        self.assertTrue(key.startswith("ct_"), key)
        self.assertGreater(len(key), 20)

    def test_session_expiry_is_in_the_future(self):
        import time
        self.assertGreater(auth.session_expiry(), time.time())


class TestValidation(unittest.TestCase):
    def test_valid_emails(self):
        for e in ("a@b.com", "first.last@sub.example.org"):
            self.assertTrue(auth.valid_email(e), e)

    def test_invalid_emails(self):
        for e in ("", "nope", "a@b", "@b.com", "a@@b.com", "a b@c.com"):
            self.assertFalse(auth.valid_email(e), e)

    def test_password_policy_rejects_short(self):
        ok, msg = auth.validate_password("short")
        self.assertFalse(ok)
        self.assertIn("8", msg)

    def test_password_policy_accepts_long_enough(self):
        ok, _ = auth.validate_password("abcd12345")
        self.assertTrue(ok)

    def test_password_policy_rejects_absurd_length(self):
        ok, _ = auth.validate_password("x" * 500)
        self.assertFalse(ok)


class TestPublicUser(unittest.TestCase):
    def test_password_hash_never_leaves_the_server(self):
        row = {
            "id": 7, "email": "a@b.com", "display_name": "A", "plan": "free",
            "monthly_quota": 50, "created_at": 0.0,
            "password_hash": "pbkdf2_sha256$1000$deadbeef$cafe",
        }
        public = auth.public_user(row)
        self.assertNotIn("password_hash", public)
        self.assertNotIn("pbkdf2_sha256", str(public))
        self.assertEqual(public["email"], "a@b.com")
        self.assertEqual(public["id"], 7)


if __name__ == "__main__":
    unittest.main()
