"""Live analysis wiring — call a domestic LLM, then run the verify engine.

This is the module that turns compliance-triangle from a *paste-and-check*
tool into a *generate-and-check* tool. It uses ``llm_adapter`` (urllib only,
zero third-party deps) so it stays in the project's offline-friendly spirit.

Requires an API key env var for the chosen model (e.g. ``DEEPSEEK_API_KEY``).
With no key, ``live_models()`` returns ``[]`` and ``analyze`` raises a clear
error rather than failing silently — the product degrades to paste-only mode.

CLI usage:
    python -m compliance_triangle.live --scenario "公司拟为关联方担保……" \
        --as_of 2025-01-01 --model DeepSeek-V3 --out memo.md
"""
from __future__ import annotations

import argparse
import sys
from typing import Dict, List, Optional, Tuple

from .prompt_template import build_messages
from .verify_integration import verify_answer
from . import llm_adapter
from compliance_triangle import kb as kb_mod
from compliance_triangle.memo import build_memo_md


def live_models() -> List[str]:
    """Labels whose API key is present in the environment (wired and callable)."""
    return llm_adapter.available_models()


def analyze(scenario: str, as_of_date: str, model_label: str,
            laws: Optional[Dict] = None) -> Tuple[str, Dict]:
    """Generate a compliance analysis with ``model_label`` and verify every
    citation it makes.

    Returns ``(answer, result)`` where ``answer`` is the raw model output and
    ``result`` is the verify result dict (same shape as ``verify_answer``).
    """
    if model_label not in llm_adapter.available_models():
        configured = ", ".join(llm_adapter.available_models()) or "(无)"
        raise RuntimeError(
            f"模型 {model_label} 未就绪：缺少对应 API key 环境变量。"
            f"当前可用模型：{configured}")
    answer = llm_adapter.call_model(model_label, build_messages(scenario, as_of_date))
    result = verify_answer(f"LIVE:{model_label}", answer, as_of_date, laws)
    return answer, result


def _cli() -> int:
    ap = argparse.ArgumentParser(
        description="调用国产大模型生成合规分析，并用 verify 引擎逐条核验引注。")
    ap.add_argument("--scenario", required=True, help="合规场景描述")
    ap.add_argument("--as_of", default="2025-01-01", help="分析基准日 YYYY-MM-DD")
    ap.add_argument("--model", default=None,
                    help="模型标签（见 config.MODELS）；缺省时取第一个已配置密钥的模型")
    ap.add_argument("--out", default=None, help="将合规备忘录写入该 .md 文件")
    args = ap.parse_args()

    available = llm_adapter.available_models()
    if not available:
        print("[error] 未检测到任何模型 API key 环境变量。请配置 DEEPSEEK_API_KEY 等后重试。",
              file=sys.stderr)
        return 2
    model = args.model or available[0]
    if model not in available:
        print(f"[error] 模型 {model} 未就绪，可用：{available}", file=sys.stderr)
        return 2

    laws = kb_mod.load_kb()
    answer, result = analyze(args.scenario, args.as_of, model, laws)
    c = result["counts"]
    print(f"\n[model] {model}  (as_of={args.as_of})")
    print(f"[verify] 🟢{c['🟢']} 🟡{c['🟡']} 🔴{c['🔴']}  -> {result['overall']}\n")
    print("===== AI 合规分析（原始输出）=====\n")
    print(answer)
    if args.out:
        memo = build_memo_md({"title": "实时分析", "scenario": args.scenario,
                              "id": f"LIVE:{model}"}, answer, result)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(memo)
        print(f"\n[out] 合规备忘录已写入 {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(_cli())
