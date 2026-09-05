"""Tests for the SQLite persistence layer.

The riskiest property here is **tenant isolation**: one user must never be able
to read or delete another user's verification history. That is asserted
explicitly rather than assumed.
"""
import os
import sqlite3
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ.setdefault("COMPLIANCE_TRIANGLE_PBKDF2_ITERS", "1000")

from compliance_triangle.server import auth, store  # noqa: E402


class StoreTestCase(unittest.TestCase):
    def setUp(self):
        self.conn = store.connect(":memory:")
        self.uid_a = store.create_user(self.conn, "a@example.com",
                                       auth.hash_password("password-a1"), "A")
        self.uid_b = store.create_user(self.conn, "b@example.com",
                                       auth.hash_password("password-b2"), "B")

    def tearDown(self):
        self.conn.close()


class TestUsers(StoreTestCase):
    def test_email_lookup_is_case_insensitive(self):
        self.assertIsNotNone(store.get_user_by_email(self.conn, "A@Example.com"))
        self.assertIsNotNone(store.get_user_by_email(self.conn, "a@example.com"))

    def test_duplicate_email_is_rejected(self):
        with self.assertRaises(sqlite3.IntegrityError):
            store.create_user(self.conn, "a@example.com", "x", "dupe")

    def test_default_quota_applied(self):
        user = store.get_user_by_id(self.conn, self.uid_a)
        self.assertEqual(user["monthly_quota"], store.DEFAULT_MONTHLY_QUOTA)
        self.assertEqual(user["plan"], "free")

    def test_update_user_changes_only_allowed_columns(self):
        store.update_user(self.conn, self.uid_a, monthly_quota=5,
                          password_hash="HACKED")
        user = store.get_user_by_id(self.conn, self.uid_a)
        self.assertEqual(user["monthly_quota"], 5)
        self.assertNotEqual(user["password_hash"], "HACKED")


class TestSessions(StoreTestCase):
    def test_round_trip(self):
        tok = auth.new_session_token()
        store.create_session(self.conn, self.uid_a, tok, auth.session_expiry())
        user = store.get_session_user(self.conn, tok)
        self.assertIsNotNone(user)
        self.assertEqual(user["email"], "a@example.com")

    def test_logout_invalidates_immediately(self):
        tok = auth.new_session_token()
        store.create_session(self.conn, self.uid_a, tok, auth.session_expiry())
        store.delete_session(self.conn, tok)
        self.assertIsNone(store.get_session_user(self.conn, tok))

    def test_expired_session_is_rejected(self):
        tok = auth.new_session_token()
        store.create_session(self.conn, self.uid_a, tok, auth.session_expiry(ttl=-1))
        self.assertIsNone(store.get_session_user(self.conn, tok))

    def test_purge_removes_only_expired(self):
        live = auth.new_session_token()
        dead = auth.new_session_token()
        store.create_session(self.conn, self.uid_a, live, auth.session_expiry())
        store.create_session(self.conn, self.uid_a, dead, auth.session_expiry(ttl=-1))
        removed = store.purge_expired_sessions(self.conn)
        self.assertEqual(removed, 1)
        self.assertIsNotNone(store.get_session_user(self.conn, live))
        self.assertIsNone(store.get_session_user(self.conn, dead))

    def test_unknown_token_resolves_to_none(self):
        self.assertIsNone(store.get_session_user(self.conn, "not-a-token"))
        self.assertIsNone(store.get_session_user(self.conn, ""))


class TestApiKeys(StoreTestCase):
    def test_create_resolve_revoke(self):
        key = auth.new_api_key()
        store.create_api_key(self.conn, self.uid_a, key, "ci")
        self.assertEqual(store.resolve_api_key(self.conn, key)["id"], self.uid_a)
        self.assertTrue(store.revoke_api_key(self.conn, self.uid_a, key))
        self.assertIsNone(store.resolve_api_key(self.conn, key))

    def test_other_user_cannot_revoke(self):
        key = auth.new_api_key()
        store.create_api_key(self.conn, self.uid_a, key, "ci")
        self.assertFalse(store.revoke_api_key(self.conn, self.uid_b, key))
        self.assertIsNotNone(store.resolve_api_key(self.conn, key))

    def test_listing_is_scoped_to_owner(self):
        store.create_api_key(self.conn, self.uid_a, auth.new_api_key(), "a1")
        store.create_api_key(self.conn, self.uid_b, auth.new_api_key(), "b1")
        self.assertEqual(len(store.list_api_keys(self.conn, self.uid_a)), 1)
        self.assertEqual(len(store.list_api_keys(self.conn, self.uid_b)), 1)


class TestAnalyses(StoreTestCase):
    def _save(self, uid, text="依据《公司法》第142条。"):
        return store.save_analysis(self.conn, uid, "verify", "t", text, "",
                                   "2026-08-01", "", {"counts": {"🟢": 1}})

    def test_round_trip_including_result_json(self):
        aid = self._save(self.uid_a)
        row = store.get_analysis(self.conn, self.uid_a, aid)
        self.assertIsNotNone(row)
        self.assertEqual(row["kind"], "verify")
        self.assertIn("🟢", row["result_json"])

    def test_owner_sees_own_history(self):
        self._save(self.uid_a)
        self.assertEqual(len(store.list_analyses(self.conn, self.uid_a)), 1)

    def test_other_user_cannot_read(self):
        """Tenant isolation: B must not see A's analysis."""
        aid = self._save(self.uid_a)
        self.assertIsNone(store.get_analysis(self.conn, self.uid_b, aid))
        self.assertEqual(len(store.list_analyses(self.conn, self.uid_b)), 0)

    def test_other_user_cannot_delete(self):
        aid = self._save(self.uid_a)
        self.assertFalse(store.delete_analysis(self.conn, self.uid_b, aid))
        self.assertIsNotNone(store.get_analysis(self.conn, self.uid_a, aid))

    def test_delete_removes_for_owner(self):
        aid = self._save(self.uid_a)
        self.assertTrue(store.delete_analysis(self.conn, self.uid_a, aid))
        self.assertIsNone(store.get_analysis(self.conn, self.uid_a, aid))

    def test_history_is_newest_first(self):
        self._save(self.uid_a, "first")
        self._save(self.uid_a, "second")
        rows = store.list_analyses(self.conn, self.uid_a)
        self.assertEqual(len(rows), 2)
        self.assertGreaterEqual(rows[0]["created_at"], rows[1]["created_at"])


class TestUsage(StoreTestCase):
    def test_starts_at_zero(self):
        user = store.get_user_by_id(self.conn, self.uid_a)
        self.assertEqual(store.usage_summary(self.conn, user)["used"], 0)

    def test_increment_accumulates(self):
        store.increment_usage(self.conn, self.uid_a)
        store.increment_usage(self.conn, self.uid_a)
        self.assertEqual(store.get_usage(self.conn, self.uid_a), 2)

    def test_usage_is_per_user(self):
        store.increment_usage(self.conn, self.uid_a)
        self.assertEqual(store.get_usage(self.conn, self.uid_a), 1)
        self.assertEqual(store.get_usage(self.conn, self.uid_b), 0)

    def test_summary_reports_remaining(self):
        user = store.get_user_by_id(self.conn, self.uid_a)
        store.increment_usage(self.conn, self.uid_a, amount=3)
        s = store.usage_summary(self.conn, user)
        self.assertEqual(s["used"], 3)
        self.assertEqual(s["quota"], user["monthly_quota"])
        self.assertEqual(s["remaining"], user["monthly_quota"] - 3)

    def test_remaining_never_goes_negative(self):
        user = store.get_user_by_id(self.conn, self.uid_a)
        store.increment_usage(self.conn, self.uid_a, amount=user["monthly_quota"] + 10)
        self.assertEqual(store.usage_summary(self.conn, user)["remaining"], 0)

    def test_period_is_year_month(self):
        self.assertRegex(store.period_of(), r"^\d{4}-\d{2}$")


if __name__ == "__main__":
    unittest.main()
