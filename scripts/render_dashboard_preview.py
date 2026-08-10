#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Render an accurate, data-driven preview PNG of the compliance-triangle
dashboard (docs/dashboard_preview.png).

This is an *illustrative* rendering built from the real demo data
(build_demo_data), NOT a browser screenshot — but every number it shows is the
actual verify result, and the hero now reflects the true KB size (8 部法 /
2327 条). Run after demo/run_demo.py or on its own.

Usage:
    python scripts/render_dashboard_preview.py
"""
from __future__ import annotations

import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from PIL import Image, ImageDraw, ImageFont

from compliance_triangle import kb as kb_mod
from compliance_triangle.runner import build_demo_data

FONT_PATH = "/System/Library/Fonts/PingFang.ttc"
INDIGO = (79, 70, 229)
GREEN = (22, 163, 74)
YELLOW = (217, 119, 6)
RED = (220, 38, 38)
INK = (15, 23, 42)
MUTE = (100, 116, 139)
CARD = (248, 250, 252)
LINE = (226, 232, 240)
WHITE = (255, 255, 255)


def font(size, bold=False):
    try:
        return ImageFont.truetype(FONT_PATH, size)
    except Exception:
        return ImageFont.load_default()


def main() -> int:
    laws = kb_mod.load_kb()
    kb_laws = kb_mod.count_laws(laws)
    kb_articles = kb_mod.count_articles(laws)
    data = build_demo_data(laws)

    # aggregate
    g = y = r = 0
    per_law_raw = {}
    for d in data:
        c = d["result"]["counts"]
        g += c["🟢"]; y += c["🟡"]; r += c["🔴"]
        for it in d["result"]["items"]:
            # normalize to the KB's official short law name to avoid
            # duplicating "公司法" / "中华人民共和国公司法"
            code = kb_mod.normalize_law_name(laws, it["raw_law"])
            if code in laws:
                k = laws[code].name
            else:
                k = it["raw_law"]
            per_law_raw.setdefault(k, [0, 0, 0])
            if it["badge"] == "🟢":
                per_law_raw[k][0] += 1
            elif it["badge"] == "🟡":
                per_law_raw[k][1] += 1
            else:
                per_law_raw[k][2] += 1
    total = g + y + r

    W, H = 1280, 940
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)

    # header
    d.rectangle([0, 0, W, 132], fill=INDIGO)
    d.text((40, 26), "合规三角 · 引注核验仪表盘", font=font(30, True), fill=WHITE)
    d.text((40, 66), "法律合规 · 税务合规 · 知识产权合规 —— 同一套 verify 引擎为每条 AI 法条引注把关",
           font=font(15), fill=(226, 232, 240))
    d.text((40, 96), f"基准库：{kb_articles} 条已核验法条（{kb_laws} 部法，源自 legal-hallucination-bench）",
           font=font(15), fill=(226, 232, 240))

    # KPI cards
    cy, ch, cw = 156, 92, 290
    cards = [("🟢 通过", g, GREEN), ("🟡 待复核", y, YELLOW),
             ("🔴 未通过", r, RED), ("引注总数", total, INK)]
    for i, (label, val, col) in enumerate(cards):
        x = 40 + i * (cw + 16)
        d.rounded_rectangle([x, cy, x + cw, cy + ch], radius=12, fill=CARD,
                            outline=LINE, width=1)
        # colored dot
        d.ellipse([x + 18, cy + 36, x + 38, cy + 56], fill=col)
        d.text((x + 56, cy + 22), str(val), font=font(34, True), fill=col)
        d.text((x + 56, cy + 64), label, font=font(15), fill=MUTE)

    # per-law breakdown
    y0 = 280
    d.text((40, y0), "按法律分布", font=font(20, True), fill=INK)
    ry = y0 + 36
    d.text((40, ry), "法律", font=font(15, True), fill=MUTE)
    d.text((W - 260, ry), "🟢    🟡    🔴", font=font(15, True), fill=MUTE)
    ry += 26
    for law, (lg, ly, lr) in sorted(per_law_raw.items()):
        d.text((40, ry), law, font=font(15), fill=INK)
        for j, (v, col) in enumerate([(lg, GREEN), (ly, YELLOW), (lr, RED)]):
            d.ellipse([W - 250 + j * 78, ry + 4, W - 234 + j * 78, ry + 20], fill=col)
            d.text((W - 228 + j * 78, ry), str(v), font=font(15, True), fill=col)
        d.line([40, ry + 26, W - 40, ry + 26], fill=LINE, width=1)
        ry += 30

    # scenarios
    ry += 14
    d.text((40, ry), "演示场景（内置 5 个含幻觉样本）", font=font(20, True), fill=INK)
    ry += 36
    for d_ in data:
        s = d_["scenario"]
        c = d_["result"]["counts"]
        d.rounded_rectangle([40, ry, W - 40, ry + 40], radius=10, fill=CARD, outline=LINE, width=1)
        d.text((56, ry + 11), f"{s['id']}  {s['title']}", font=font(15, True), fill=INK)
        # badge dots + counts on the right
        vals = [c["🟢"], c["🟡"], c["🔴"]]
        cols = [GREEN, YELLOW, RED]
        bx = W - 220
        for v, col in zip(vals, cols):
            d.ellipse([bx, ry + 15, bx + 16, ry + 31], fill=col)
            d.text((bx + 20, ry + 12), str(v), font=font(16, True), fill=col)
            bx += 64
        ry += 50

    out = os.path.join(REPO_ROOT, "docs", "dashboard_preview.png")
    img.save(out)
    print(f"[png] 预览图已生成 -> {out}  ({W}x{H})")
    print(f"[data] 🟢{g} 🟡{y} 🔴{r}  总引注 {total} | KB {kb_laws} 部法 / {kb_articles} 条")
    return 0


if __name__ == "__main__":
    sys.exit(main())
