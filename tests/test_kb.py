"""KB wrapper tests — count helpers and standalone (vendored) fallback."""
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from compliance_triangle import kb


class TestKbCounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # load_kb prefers the real Bench repo when available; otherwise falls
        # back to the vendored snapshot bundled in compliance_triangle/vendor.
        cls.LAWS = kb.load_kb()

    def test_count_laws(self):
        # 8 in-scope laws, NOT the ~29 resolution keys
        self.assertEqual(kb.count_laws(self.LAWS), 8)

    def test_count_articles(self):
        self.assertEqual(kb.count_articles(self.LAWS), 2327)

    def test_len_is_not_law_count(self):
        # guards against the old len(LAWS) == 29 bug
        self.assertNotEqual(len(self.LAWS), kb.count_laws(self.LAWS))


class TestKbStandaloneFallback(unittest.TestCase):
    """Verify compliance-triangle can run without the Bench repo as sibling."""

    def test_vendored_load(self):
        # Force the fallback path by making the Bench loader return None.
        original_cache = kb._laws_cache
        original_source = kb._kb_source
        original_loader = kb._load_bench_kb
        try:
            kb._laws_cache = None
            kb._kb_source = ""
            kb._load_bench_kb = lambda: None

            laws = kb.load_kb()
            self.assertEqual(kb.kb_source(), "vendored")
            self.assertEqual(kb.count_laws(laws), 8)
            self.assertEqual(kb.count_articles(laws), 2327)

            # Temporal trap still works with the vendored snapshot.
            result = kb.resolve("旧公司法", "16", "2025-06-01", laws)
            self.assertTrue(result.used_deprecated_alias)
            self.assertEqual(result.deprecated_repealed_date, "2024-07-01")

            # Current-law lookup still works.
            result = kb.resolve("公司法", "16", "2025-06-01", laws)
            self.assertTrue(result.found)
            self.assertEqual(result.verification_status, "verified")
        finally:
            kb._load_bench_kb = original_loader
            kb._laws_cache = original_cache
            kb._kb_source = original_source


if __name__ == "__main__":
    unittest.main()
