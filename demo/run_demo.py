#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Offline demo runner for compliance-triangle.

Runs the 5 built-in scenarios through the verify engine (reusing the Bench KB)
and writes a compliance memo per scenario. No API key, no network — proves the
anti-hallucination gate end-to-end.

Usage:
    python demo/run_demo.py
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from compliance_triangle import kb
from compliance_triangle.verify_integration import verify_answer
from compliance_triangle.memo import build_memo_md, write_report_html
from compliance_triangle.runner import build_demo_data
from demo.scenarios import SCENARIOS


def main() -> int:
    out_dir = os.path.join(REPO_ROOT, "demo", "output")
    os.makedirs(out_dir, exist_ok=True)
    html_dir = os.path.join(REPO_ROOT, "docs")
    os.makedirs(html_dir, exist_ok=True)

    laws = kb.load_kb()
    kb_law_count = kb.count_laws(laws)
    kb_article_count = kb.count_articles(laws)
    print(f"[kb ] loaded {kb_law_count} laws / {kb_article_count} articles "
          f"from legal-hallucination-bench")

    total = {"🟢": 0, "🟡": 0, "🔴": 0}
    print("\n=== 合规三角 · 离线演示（引注核验） ===\n")
    demo_data = build_demo_data(laws)
    for s, entry in zip(SCENARIOS, demo_data):
        result = entry["result"]
        for b, n in result["counts"].items():
            total[b] += n
        memo = build_memo_md(s, s["answer"], result)
        out_path = os.path.join(out_dir, f"{s['id']}_{s['title']}.md")
        with open(out_path, "w", encoding="utf-8") as f:
            f.write(memo)
        c = result["counts"]
        print(f"  [{s['id']}] {s['title']:<10} "
              f"🟢{c['🟢']} 🟡{c['🟡']} 🔴{c['🔴']}  -> {out_path}")

    # Self-contained static HTML showcase (double-click to open, no server).
    # Published under docs/ so GitHub Pages can serve it (Pages only allows / or /docs).
    html_path = os.path.join(html_dir, "index.html")
    write_report_html(demo_data, html_path, with_live=False,
                     kb_laws=kb_law_count, kb_articles=kb_article_count)
    print(f"\n[html] 静态展示页 -> {html_path}")

    print(f"\n[sum] 🟢{total['🟢']} 🟡{total['🟡']} 🔴{total['🔴']} "
          f"(共 {sum(total.values())} 条引注)")
    print("[done] 全部备忘录已写入 demo/output/")
    return 0


if __name__ == "__main__":
    sys.exit(main())
