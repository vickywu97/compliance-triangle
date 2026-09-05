"""End-to-end HTTP tests for the SaaS API (real server, in-memory database).

These exercise the whole stack — routing, auth, quota, persistence — the way a
client would, without mocking. The database is ``:memory:`` so the suite stays
hermetic and repeatable.
"""
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

os.environ.setdefault("COMPLIANCE_TRIANGLE_PBKDF2_ITERS", "1000")

from compliance_triangle.server import store  # noqa: E402
from compliance_triangle.server.app import (  # noqa: E402
    RateLimiter, ServerContext, make_server,
)


class ApiTestCase(unittest.TestCase):
    """Boots one server for the whole class (loading the KB is not free)."""

    @classmethod
    def setUpClass(cls):
        cls.ctx = ServerContext(db_path=":memory:", host="127.0.0.1")
        # Tests issue many requests; don't let the production limiter make them flaky.
        cls.ctx.limiter = RateLimiter(max_calls=100000, window=60)
        cls.server = make_server(cls.ctx, "127.0.0.1", 0)
        cls.port = cls.server.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    # -- helpers ---------------------------------------------------------- #
    def call(self, method, path, body=None, token=None):
        data = json.dumps(body).encode("utf-8") if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if token:
            req.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.status, json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8")
            try:
                return e.code, json.loads(raw)
            except ValueError:
                return e.code, {"error": raw}

    def register(self, email, password="password123"):
        code, body = self.call("POST", "/api/auth/register",
                               {"email": email, "password": password})
        self.assertEqual(code, 201, body)
        return body["token"], body

    def drain_quota(self, user_id):
        """Fill the user's monthly quota so the next call must be rejected."""
        with store.db_lock():
            user = store.get_user_by_id(self.ctx.conn, user_id)
            store.increment_usage(self.ctx.conn, user_id, amount=user["monthly_quota"])


class TestPublicEndpoints(ApiTestCase):
    def test_healthz_reports_kb(self):
        code, body = self.call("GET", "/healthz")
        self.assertEqual(code, 200)
        self.assertTrue(body["ok"])
        self.assertIn("kb_laws", body)

    def test_meta_exposes_kb_and_models(self):
        code, body = self.call("GET", "/api/meta")
        self.assertEqual(code, 200)
        self.assertIn("kb_articles", body)
        self.assertIn("live_models", body)
        self.assertIn("caveats", body)

    def test_unknown_route_is_404(self):
        code, _ = self.call("GET", "/definitely-not-a-route")
        self.assertEqual(code, 404)


class TestAuthFlow(ApiTestCase):
    def test_register_returns_token_and_usage(self):
        code, body = self.call("POST", "/api/auth/register",
                               {"email": "fresh@example.com", "password": "abcd12345"})
        self.assertEqual(code, 201)
        self.assertTrue(body["token"])
        self.assertEqual(body["user"]["email"], "fresh@example.com")
        self.assertEqual(body["usage"]["remaining"], body["usage"]["quota"])

    def test_duplicate_registration_is_409(self):
        self.register("dupe@example.com")
        code, body = self.call("POST", "/api/auth/register",
                               {"email": "dupe@example.com", "password": "abcd12345"})
        self.assertEqual(code, 409)

    def test_invalid_email_is_400(self):
        code, _ = self.call("POST", "/api/auth/register",
                            {"email": "not-an-email", "password": "abcd12345"})
        self.assertEqual(code, 400)

    def test_short_password_is_400(self):
        code, _ = self.call("POST", "/api/auth/register",
                            {"email": "x@y.com", "password": "123"})
        self.assertEqual(code, 400)

    def test_login_succeeds(self):
        self.register("login@example.com", "mysecret123")
        code, body = self.call("POST", "/api/auth/login",
                               {"email": "login@example.com", "password": "mysecret123"})
        self.assertEqual(code, 200)
        self.assertTrue(body["token"])

    def test_wrong_password_is_401_without_leaking_account_existence(self):
        self.register("known@example.com", "mysecret123")
        code, body = self.call("POST", "/api/auth/login",
                               {"email": "known@example.com", "password": "wrongwrong"})
        self.assertEqual(code, 401)
        unknown_code, unknown_body = self.call(
            "POST", "/api/auth/login",
            {"email": "never-registered@example.com", "password": "wrongwrong"})
        self.assertEqual(unknown_code, 401)
        self.assertEqual(body["error"], unknown_body["error"])

    def test_me_requires_auth(self):
        code, _ = self.call("GET", "/api/me")
        self.assertEqual(code, 401)

    def test_logout_invalidates_the_token(self):
        token, _ = self.register("logout@example.com")
        self.assertEqual(self.call("GET", "/api/me", token=token)[0], 200)
        self.assertEqual(self.call("POST", "/api/auth/logout", {}, token=token)[0], 200)
        self.assertEqual(self.call("GET", "/api/me", token=token)[0], 401)

    def test_bogus_token_is_401(self):
        self.assertEqual(self.call("GET", "/api/me", token="garbage")[0], 401)


class TestVerifyEndpoint(ApiTestCase):
    def test_requires_auth(self):
        code, _ = self.call("POST", "/api/verify", {"answer": "《公司法》第142条"})
        self.assertEqual(code, 401)

    def test_rejects_empty_answer(self):
        token, _ = self.register("empty@example.com")
        code, _ = self.call("POST", "/api/verify", {"answer": "   "}, token=token)
        self.assertEqual(code, 400)

    def test_verifies_and_persists(self):
        token, _ = self.register("verify@example.com")
        code, body = self.call(
            "POST", "/api/verify",
            {"answer": "依据《中华人民共和国公司法》第142条，公司不得收购本公司股份。"},
            token=token)
        self.assertEqual(code, 200, body)
        result = body["result"]
        self.assertTrue(result["has_citations"])
        self.assertEqual(result["counts"]["🟢"], 1)
        self.assertEqual(result["items"][0]["article_no"], "142")
        # ...and it landed in the audit trail.
        code, hist = self.call("GET", "/api/analyses", token=token)
        self.assertEqual(code, 200)
        self.assertEqual(len(hist["items"]), 1)

    def test_flags_fabricated_article(self):
        token, _ = self.register("fake@example.com")
        code, body = self.call(
            "POST", "/api/verify",
            {"answer": "依据《中华人民共和国公司法》第99999条，公司可以任意分配利润。"},
            token=token)
        self.assertEqual(code, 200)
        self.assertEqual(body["result"]["counts"]["🔴"], 1)

    def test_flags_repealed_law(self):
        """The headline anti-hallucination case: citing a law that no longer exists."""
        token, _ = self.register("repealed@example.com")
        code, body = self.call(
            "POST", "/api/verify",
            {"answer": "根据《合同法》第52条，该合同无效。", "as_of_date": "2026-08-01"},
            token=token)
        self.assertEqual(code, 200)
        statuses = [i["status"] for i in body["result"]["items"]]
        self.assertIn("TEMPORAL_DEPRECATED", statuses)

    def test_quota_is_consumed(self):
        token, body = self.register("quota@example.com")
        self.assertEqual(body["usage"]["used"], 0)
        self.call("POST", "/api/verify", {"answer": "《公司法》第142条"}, token=token)
        code, me = self.call("GET", "/api/me", token=token)
        self.assertEqual(me["usage"]["used"], 1)


class TestQuotaEnforcement(ApiTestCase):
    def test_over_quota_returns_429(self):
        token, body = self.register("overquota@example.com")
        uid = body["user"]["id"]
        self.drain_quota(uid)
        code, res = self.call("POST", "/api/verify",
                              {"answer": "《公司法》第142条"}, token=token)
        self.assertEqual(code, 429, res)
        self.assertIn("usage", res)
        self.assertEqual(res["usage"]["remaining"], 0)

    def test_quota_is_per_user(self):
        token_a, body_a = self.register("qa@example.com")
        token_b, _ = self.register("qb@example.com")
        self.drain_quota(body_a["user"]["id"])
        self.assertEqual(
            self.call("POST", "/api/verify", {"answer": "《公司法》第142条"},
                      token=token_a)[0], 429)
        self.assertEqual(
            self.call("POST", "/api/verify", {"answer": "《公司法》第142条"},
                      token=token_b)[0], 200)


class TestHistoryAndIsolation(ApiTestCase):
    def test_other_user_cannot_read_someone_elses_analysis(self):
        """Tenant isolation, asserted over HTTP rather than assumed."""
        token_a, _ = self.register("iso-a@example.com")
        token_b, _ = self.register("iso-b@example.com")
        _, created = self.call("POST", "/api/verify",
                               {"answer": "《公司法》第142条"}, token=token_a)
        aid = created["id"]

        self.assertEqual(self.call("GET", f"/api/analyses/{aid}", token=token_a)[0], 200)
        code, _ = self.call("GET", f"/api/analyses/{aid}", token=token_b)
        self.assertEqual(code, 404)

        code, _ = self.call("DELETE", f"/api/analyses/{aid}", token=token_b)
        self.assertEqual(code, 404)
        # ...and A's record survived the attempt.
        self.assertEqual(self.call("GET", f"/api/analyses/{aid}", token=token_a)[0], 200)

    def test_history_is_scoped_to_owner(self):
        token_a, _ = self.register("hist-a@example.com")
        token_b, _ = self.register("hist-b@example.com")
        self.call("POST", "/api/verify", {"answer": "《公司法》第142条"}, token=token_a)
        self.call("POST", "/api/verify", {"answer": "《专利法》第22条"}, token=token_a)
        _, hist_b = self.call("GET", "/api/analyses", token=token_b)
        self.assertEqual(len(hist_b["items"]), 0)
        _, hist_a = self.call("GET", "/api/analyses", token=token_a)
        self.assertEqual(len(hist_a["items"]), 2)

    def test_delete_own_analysis(self):
        token, _ = self.register("del@example.com")
        _, created = self.call("POST", "/api/verify",
                               {"answer": "《公司法》第142条"}, token=token)
        aid = created["id"]
        self.assertEqual(self.call("DELETE", f"/api/analyses/{aid}", token=token)[0], 200)
        self.assertEqual(self.call("GET", f"/api/analyses/{aid}", token=token)[0], 404)

    def test_invalid_id_is_400(self):
        token, _ = self.register("badid@example.com")
        self.assertEqual(self.call("GET", "/api/analyses/abc", token=token)[0], 400)


class TestApiKeys(ApiTestCase):
    def test_created_key_authenticates(self):
        token, _ = self.register("key1@example.com")
        code, body = self.call("POST", "/api/keys", {"label": "ci"}, token=token)
        self.assertEqual(code, 201)
        key = body["key"]
        self.assertTrue(key.startswith("ct_"))
        self.assertEqual(self.call("GET", "/api/me", token=key)[0], 200)

    def test_revoked_key_stops_working(self):
        token, _ = self.register("key2@example.com")
        key = self.call("POST", "/api/keys", {"label": "ci"}, token=token)[1]["key"]
        self.assertEqual(self.call("DELETE", f"/api/keys/{key}", token=token)[0], 200)
        self.assertEqual(self.call("GET", "/api/me", token=key)[0], 401)

    def test_keys_require_auth(self):
        self.assertEqual(self.call("GET", "/api/keys")[0], 401)

    def test_other_user_cannot_revoke(self):
        token_a, _ = self.register("key3a@example.com")
        token_b, _ = self.register("key3b@example.com")
        key = self.call("POST", "/api/keys", {"label": "a"}, token=token_a)[1]["key"]
        self.assertEqual(self.call("DELETE", f"/api/keys/{key}", token=token_b)[0], 404)
        self.assertEqual(self.call("GET", "/api/me", token=key)[0], 200)


class TestLegacyEndpoints(ApiTestCase):
    def test_legacy_verify_works_without_auth(self):
        """Kept for the documented local flow `python -m compliance_triangle.web`."""
        code, body = self.call("POST", "/verify",
                               {"answer": "依据《公司法》第142条。"})
        self.assertEqual(code, 200)
        self.assertIn("counts", body)

    def test_anonymous_analyze_is_gated_in_deployed_mode(self):
        """An /analyze call spends money on an LLM, so it must not be open."""
        ctx = ServerContext.__new__(ServerContext)  # no KB load needed
        ctx.host = "0.0.0.0"
        self.assertFalse(ctx.allow_anon_analyze())
        ctx.host = "127.0.0.1"
        self.assertTrue(ctx.allow_anon_analyze())

    def test_anonymous_analyze_can_be_force_enabled(self):
        ctx = ServerContext.__new__(ServerContext)
        ctx.host = "0.0.0.0"
        os.environ["CT_ALLOW_ANON_ANALYZE"] = "1"
        try:
            self.assertTrue(ctx.allow_anon_analyze())
        finally:
            del os.environ["CT_ALLOW_ANON_ANALYZE"]


class TestStaticAssets(ApiTestCase):
    def test_spa_is_served_and_self_contained(self):
        req = urllib.request.Request(self.base + "/")
        with urllib.request.urlopen(req, timeout=30) as r:
            html = r.read().decode("utf-8")
        self.assertIn('src="/app.js"', html)
        self.assertIn('href="/styles.css"', html)
        for cdn in ("cdn.", "unpkg", "jsdelivr", "googleapis"):
            self.assertNotIn(cdn, html, "SPA must not depend on an external CDN")

    def test_path_traversal_is_blocked(self):
        code, _ = self.call("GET", "/../README.md")
        self.assertIn(code, (403, 404))


if __name__ == "__main__":
    unittest.main()
