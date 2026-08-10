"""KB wrapper tests — count helpers must report the true law/article counts,
not the over-counted resolution-key dict length."""
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from compliance_triangle import kb


@unittest.skipUnless(
    os.path.isdir(os.path.join(REPO_ROOT, "..", "legal-hallucination-bench",
                               "knowledge_base")),
    "legal-hallucination-bench sibling repo not found")
class TestKbCounts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from compliance_triangle import config, kb
        config.ensure_bench_importable()
        cls.LAWS = kb.load_kb()

    def test_count_laws(self):
        # 8 in-scope laws, NOT the 29 resolution keys
        self.assertEqual(kb.count_laws(self.LAWS), 8)

    def test_count_articles(self):
        self.assertEqual(kb.count_articles(self.LAWS), 2327)

    def test_len_is_not_law_count(self):
        # guards against the old len(LAWS) == 29 bug
        self.assertNotEqual(len(self.LAWS), kb.count_laws(self.LAWS))


if __name__ == "__main__":
    unittest.main()
