"""Tests for the live-analysis wiring (Batch C).

The model network call is mocked so these run offline; they prove the pipeline
(LLM answer -> citation extraction -> verify) is correctly wired and that the
availability gate fails clearly when no key is present.
"""
import os
import sys
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)


class TestLiveWiring(unittest.TestCase):
    SAMPLE_ANSWER = (
        "依据《公司法》第142条进行股份回购；"
        "《个人所得税法》第999条（虚构）作为示例；"
        "《旧公司法》第16条（已废止）。"
    )

    def test_analyze_pipeline(self):
        from compliance_triangle import live as live_mod
        with mock.patch.object(live_mod.llm_adapter, "call_model",
                               return_value=self.SAMPLE_ANSWER) as mk, \
             mock.patch.object(live_mod.llm_adapter, "available_models",
                               return_value=["DeepSeek-V3"]):
            answer, result = live_mod.analyze(
                "公司拟回购股份", "2025-01-01", "DeepSeek-V3")
        self.assertEqual(answer, self.SAMPLE_ANSWER)
        self.assertTrue(result["has_citations"])
        badges = [it["badge"] for it in result["items"]]
        # 1 green (real), 1 red (not found), 1 red (repealed)
        self.assertIn("🟢", badges)
        self.assertEqual(badges.count("🔴"), 2)
        mk.assert_called_once()

    def test_analyze_raises_without_key(self):
        from compliance_triangle import live as live_mod
        with mock.patch.object(live_mod.llm_adapter, "available_models",
                               return_value=[]):
            with self.assertRaises(RuntimeError):
                live_mod.analyze("场景", "2025-01-01", "DeepSeek-V3")


if __name__ == "__main__":
    unittest.main()
