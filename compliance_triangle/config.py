"""compliance-triangle — configuration & Bench reuse wiring.

This product does NOT store any statute text. It reads the verified
``statutes.jsonl`` (2327 nodes, 8 laws) and reuses the ``verify`` engine from
the sibling repo ``legal-hallucination-bench``. The Bench repo path is
configurable so the two repos stay decoupled (independent operation).
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Default: the Bench repo sits as a sibling directory. Override with the
# COMPLIANCE_TRIANGLE_BENCH env var if your layout differs.
BENCH_REPO_PATH = os.environ.get(
    "COMPLIANCE_TRIANGLE_BENCH",
    os.path.join(REPO_ROOT, "..", "legal-hallucination-bench"),
)


def ensure_bench_importable() -> str:
    """Insert the Bench repo root onto sys.path (front) so we can import
    ``knowledge_base.*`` and ``benchmark.*``. Returns the resolved path.

    Idempotent. Raises a clear error if the Bench repo is not found.
    """
    bench = os.path.abspath(BENCH_REPO_PATH)
    if not os.path.isdir(os.path.join(bench, "knowledge_base")):
        raise RuntimeError(
            f"legal-hallucination-bench not found at {bench}. "
            "Set COMPLIANCE_TRIANGLE_BENCH to its path, or clone it as a "
            "sibling of this repo."
        )
    if bench not in sys.path:
        sys.path.insert(0, bench)
    return bench


# --- Law-scope guardrail (mirrors Bench's 8-law system prompt) ------------- #
# The product only answers within these 8 in-scope laws; any out-of-scope or
# fictional citation becomes a clean hard hallucination (NOT_FOUND).
LAW_SCOPE = (
    "民法典、刑法、专利法、税收征收管理法、公司法（2023年修订，2024-07-01施行）、"
    "增值税法（2024年12月25日通过，2026-01-01施行）、"
    "企业所得税法（2018年修正，2018-12-29施行）、个人所得税法（2018年修正，2019-01-01施行）"
)

# --- Domestic model registry (mirrors scripts/generate_answers.py) --------- #
# All providers are OpenAI-compatible. API keys are read from the environment
# (never hardcoded). A model with no key is skipped rather than failing.
MODELS = [
    {"label": "DeepSeek-V3", "key": "DEEPSEEK_API_KEY", "kind": "openai",
     "url": "https://api.deepseek.com/chat/completions", "model": "deepseek-chat"},
    {"label": "DeepSeek-R1", "key": "DEEPSEEK_API_KEY", "kind": "openai",
     "url": "https://api.deepseek.com/chat/completions", "model": "deepseek-reasoner"},
    {"label": "GLM-4-Flash", "key": "ZHIPU_API_KEY", "kind": "openai",
     "url": "https://open.bigmodel.cn/api/paas/v4/chat/completions", "model": "glm-4-flash"},
    {"label": "Qwen-Max", "key": "DASHSCOPE_API_KEY", "kind": "openai",
     "url": "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions",
     "model": "qwen-max"},
    {"label": "Kimi", "key": "MOONSHOT_API_KEY", "kind": "openai",
     "url": "https://api.moonshot.cn/v1/chat/completions", "model": "kimi-k2.6",
     "minimal": True},
]
