"""Tests for the batch compliance self-check feature (verify_batch + report
Markdown/CSV + HTTP endpoints). Pure-function logic is tested directly; the HTTP
layer is exercised end-to-end against a real in-memory server.
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

from compliance_triangle.verify_integration import verify_answer
from compliance_triangle import kb
from compliance_triangle.server.batch_report import (
    verify_batch, parse_lines, MAX_ITEMS,
)
from compliance_triangle.server import store
from compliance_triangle.server.app import RateLimiter, ServerContext, make_server


class TestParseLines(unittest.TestCase):
    def test_prefix_and_blanks(self):
        text = "C1: 依据《公司法》第15条。\n2. 依据《民法典》第525条。\n\n依据《增值税法》第25条。"
        items = parse_lines(text)
        self.assertEqual(len(items), 3)
        self.assertEqual([i["id"] for i in items], ["C1", "C2", "C3"])
        self.assertIn("公司法", items[0]["text"])

    def test_no_prefix(self):
        items = parse_lines("依据《公司法》第15条。\n依据《民法典》第525条。")
        self.assertEqual([i["id"] for i in items], ["C1", "C2"])

    def test_blank(self):
        self.assertEqual(parse_lines("   \n\n"), [])


class TestVerifyBatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.laws = kb.load_kb()
            cls.kb_ok = True
        except Exception:
            cls.laws = None
            cls.kb_ok = False

    def _batch(self, items, as_of="2025-01-01"):
        return verify_batch(items, as_of, self.laws)

    def test_summary_counts(self):
        if not self.kb_ok:
            self.skipTest("KB not loadable in this environment")
        items = [
            {"id": "C1", "text": "依据《公司法》第15条。"},   # GREEN (existence)
            {"id": "C2", "text": "依据《民法典》第525条。"},  # GREEN
            {"id": "C3", "text": "依据《刑法》第9999条。"},   # RED (NOT_FOUND)
            {"id": "C4", "text": "今天天气不错。"},            # neutral (no citation)
        ]
        rep = self._batch(items)
        s = rep["summary"]
        self.assertEqual(s["total"], 4)
        self.assertEqual(s["green"], 2)
        self.assertEqual(s["red"], 1)
        self.assertEqual(s["no_citation"], 1)
        self.assertEqual(s["red_items"], ["C3"])

    def test_report_md_and_csv(self):
        if not self.kb_ok:
            self.skipTest("KB not loadable in this environment")
        items = [{"id": "C1", "text": "依据《公司法》第15条。"}]
        rep = self._batch(items)
        self.assertIn("# 合规自查报告（批量）", rep["report_md"])
        self.assertTrue(rep["report_md"].startswith("# 合规自查报告"))
        self.assertIn("| # | 条款标识 | 结论 | 命中法条 | 风险提示 |", rep["report_md"])
        self.assertTrue(rep["report_csv"].startswith("id,text_excerpt,badge,status,laws,note"))
        # CSV must contain the clause id
        self.assertIn("C1", rep["report_csv"])

    def test_cap_at_max(self):
        if not self.kb_ok:
            self.skipTest("KB not loadable in this environment")
        items = [{"id": f"C{i}", "text": "依据《公司法》第15条。"} for i in range(MAX_ITEMS + 5)]
        rep = self._batch(items)
        self.assertEqual(rep["summary"]["total"], MAX_ITEMS)


class TestVerifyBatchHttp(unittest.TestCase):
    """End-to-end: real server, registered user, /api/verify-batch."""

    @classmethod
    def setUpClass(cls):
        cls.ctx = ServerContext(db_path=":memory:", host="127.0.0.1")
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

    def register(self, email):
        code, body = self.call("POST", "/api/auth/register",
                               {"email": email, "password": "password123"})
        self.assertEqual(code, 201, body)
        return body["token"]

    def test_api_verify_batch(self):
        if not self.ctx.kb_available:
            self.skipTest("KB unavailable")
        token = self.register("batch1@example.com")
        body = {"items": [{"id": "C1", "text": "依据《公司法》第15条。"},
                          {"id": "C2", "text": "依据《刑法》第9999条。"}],
                "as_of_date": "2025-01-01"}
        code, resp = self.call("POST", "/api/verify-batch", body, token=token)
        self.assertEqual(code, 200, resp)
        self.assertIn("report_md", resp)
        self.assertIn("report_csv", resp)
        self.assertEqual(resp["summary"]["total"], 2)
        self.assertEqual(resp["summary"]["red"], 1)
        self.assertIn("# 合规自查报告", resp["report_md"])
        self.assertTrue(resp["report_csv"].startswith("id,text_excerpt"))

    def test_legacy_verify_batch_anon(self):
        if not self.ctx.kb_available:
            self.skipTest("KB unavailable")
        body = {"text": "C1: 依据《公司法》第15条。\nC2: 依据《刑法》第9999条。",
                "as_of_date": "2025-01-01"}
        code, resp = self.call("POST", "/verify-batch", body)
        self.assertEqual(code, 200, resp)
        self.assertEqual(resp["summary"]["total"], 2)
        self.assertIn("report_md", resp)

    def test_empty_rejected(self):
        if not self.ctx.kb_available:
            self.skipTest("KB unavailable")
        token = self.register("batch2@example.com")
        code, resp = self.call("POST", "/api/verify-batch", {"items": []}, token=token)
        self.assertEqual(code, 400, resp)


if __name__ == "__main__":
    unittest.main()
