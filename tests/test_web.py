"""Tests for the web/HTML rendering layer and the live-model availability gate.

No network is touched: these verify the rendering logic and the graceful
degradation paths (KB-not-loaded notice, no-API-key notice).
"""
import os
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from compliance_triangle import llm_adapter
from compliance_triangle.memo import build_report_html


class TestRender(unittest.TestCase):
    def _data(self):
        return [{"scenario": {"title": "t", "scenario": "s", "id": "S"},
                 "answer": "依据《公司法》第142条。",
                 "result": {"as_of": "2025-01-01",
                            "counts": {"🟢": 1, "🟡": 0, "🔴": 0},
                            "items": [{"raw_law": "公司法", "article_no": "142",
                                       "badge": "🟢", "status": "OK", "note": "ok",
                                       "quoted": "", "ground_truth": ""}],
                            "has_citations": True,
                            "overall": "🟢 全部引注通过核验"}}]

    def test_notice_rendered(self):
        html = build_report_html(self._data(), with_live=False,
                                 notice="基准库未加载警告")
        self.assertIn("基准库未加载警告", html)
        self.assertIn('class="notice"', html)

    def test_live_models_render_picker(self):
        html = build_report_html(self._data(), with_live=True,
                                 live_models=["DeepSeek-V3", "Qwen-Max"])
        self.assertIn('<select id="model"', html)
        self.assertIn('id="runModelBtn"', html)
        self.assertIn("DeepSeek-V3", html)

    def test_no_live_models_renders_notice(self):
        html = build_report_html(self._data(), with_live=True, live_models=[])
        self.assertIn("未检测到任何模型 API key", html)
        self.assertNotIn('<select id="model"', html)

    def test_caveats_rendered(self):
        html = build_report_html(self._data(), with_live=False,
                                 caveats=["增值税法 38/41 条说明"])
        self.assertIn("增值税法 38/41 条说明", html)
        self.assertIn('class="caveats"', html)

    def test_hero_shows_counts(self):
        html = build_report_html(self._data(), with_live=False,
                                 kb_laws=8, kb_articles=2327)
        self.assertIn("2327", html)
        self.assertIn("8", html)


class TestLiveAvailability(unittest.TestCase):
    def test_no_keys_means_no_models(self):
        # in a clean environment no API keys are set -> degrade gracefully
        saved = {k: os.environ.pop(k, None) for k in
                 ("DEEPSEEK_API_KEY", "ZHIPU_API_KEY", "DASHSCOPE_API_KEY",
                  "MOONSHOT_API_KEY")}
        try:
            self.assertEqual(llm_adapter.available_models(), [])
        finally:
            for k, v in saved.items():
                if v is not None:
                    os.environ[k] = v


if __name__ == "__main__":
    unittest.main()
