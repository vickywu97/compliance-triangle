"""Integration tests for verify_answer against the real Bench KB.

These require the sibling ``legal-hallucination-bench`` repo (KB loader). They
prove the anti-hallucination gate behaves correctly end-to-end.
"""
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from compliance_triangle.verify_integration import verify_answer


@unittest.skipUnless(
    os.path.isdir(os.path.join(REPO_ROOT, "..", "legal-hallucination-bench",
                               "knowledge_base")),
    "legal-hallucination-bench sibling repo not found")
class TestVerifyAnswer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from compliance_triangle import config, kb
        config.ensure_bench_importable()
        cls.LAWS = kb.load_kb()

    def test_empty_answer_is_neutral_not_green(self):
        # P0-2: an answer with no citations must NOT get a false 🟢.
        r = verify_answer("T", "这是一段泛泛而谈、没有引用任何法条的回答。",
                          "2025-01-01", self.LAWS)
        self.assertEqual(r["items"], [])
        self.assertFalse(r["has_citations"])
        self.assertTrue(r["overall"].startswith("⚪"))

    def test_real_citation_passes(self):
        r = verify_answer("T", "依据《公司法》第142条。", "2025-01-01", self.LAWS)
        self.assertEqual(len(r["items"]), 1)
        self.assertEqual(r["items"][0]["badge"], "🟢")
        self.assertEqual(r["items"][0]["status"], "OK")

    def test_nonexistent_article_is_red(self):
        r = verify_answer("T", "依据《个人所得税法》第999条。", "2025-01-01", self.LAWS)
        self.assertEqual(r["items"][0]["badge"], "🔴")
        self.assertEqual(r["items"][0]["status"], "NOT_FOUND")

    def test_repealed_law_name_is_red(self):
        r = verify_answer("T", "依据《旧公司法》第16条。", "2025-01-01", self.LAWS)
        self.assertEqual(r["items"][0]["badge"], "🔴")
        self.assertEqual(r["items"][0]["status"], "TEMPORAL_DEPRECATED")

    def test_paraphrased_quote_is_yellow(self):
        # real article, but the quoted text diverges from the official wording
        ans = ("依据《公司法》第142条：股份有限公司在任意情形下都可以自由回购"
               "本公司股份，没有限制。")
        r = verify_answer("T", ans, "2025-01-01", self.LAWS)
        self.assertEqual(r["items"][0]["badge"], "🟡")
        self.assertIn(r["items"][0]["status"], ("PARTIAL", "FABRICATED"))

    def test_vat_coverage_gap_is_honest(self):
        # VAT_LAW holds 38/41; article 40 should resolve to NOT_FOUND (disclosed)
        r = verify_answer("T", "依据《增值税法》第40条。", "2026-08-01", self.LAWS)
        self.assertEqual(r["items"][0]["badge"], "🔴")

    def test_law_canonical_merges_name_forms(self):
        # 公司法 / 中华人民共和国公司法 / 旧公司法 must collapse to ONE row
        # in the "by law" distribution (law_canonical field).
        ans = ("依据《公司法》第15条、《中华人民共和国公司法》第142条、"
               "《旧公司法》第16条。")
        r = verify_answer("T", ans, "2025-01-01", self.LAWS)
        canon = {it["law_canonical"] for it in r["items"]}
        # 公司法 + 中华人民共和国公司法 -> 中华人民共和国公司法 (1 row);
        # 旧公司法 -> 中华人民共和国公司法 (groups under the current law)
        self.assertEqual(canon, {"中华人民共和国公司法"})


if __name__ == "__main__":
    unittest.main()
