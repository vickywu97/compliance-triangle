"""Batch compliance self-check: verify many clause texts at once and render a
consolidated 🟢🟡🔴 report as Markdown + CSV (for one-click download in the SPA).

One batch = ONE quota-consuming operation (it produces a single self-check
report). Stateless and offline — it reuses ``verify_integration.verify_answer``
so the per-citation gate is identical to the single-clause endpoint.
"""
from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Dict, List, Optional

from compliance_triangle.verify_integration import (
    GREEN, YELLOW, RED, verify_answer,
)

MAX_ITEMS = 100  # guard against a single batch exhausting the KB lookup loop


def _excerpt(text: str, n: int = 40) -> str:
    t = (text or "").replace("\r", "").replace("\n", " ").strip()
    return (t[:n] + "…") if len(t) > n else t


def _badge_css_class(badge: str) -> str:
    return {GREEN: "green", YELLOW: "yellow", RED: "red"}.get(badge, "neutral")


def verify_batch(items: List[Dict], as_of_date: str, laws: Dict) -> Dict:
    """Verify a list of ``{id, text}`` clauses. Returns the consolidated report.

    Each item is run through ``verify_answer``; the per-item ``result`` is kept
    intact so the SPA can drill down. A ``summary`` aggregates badge counts, and
    ``report_md`` / ``report_csv`` carry the downloadable artifacts.
    """
    out_items = []
    for i, it in enumerate(items[:MAX_ITEMS]):
        cid = it.get("id") or f"C{i + 1}"
        text = it.get("text") or ""
        res = verify_answer(cid, text, as_of_date, laws)
        out_items.append({"id": cid, "text": text, "result": res})

    total = len(out_items)
    green = yellow = red = neutral = 0
    red_ids, yellow_ids = [], []
    for it in out_items:
        c = it["result"]["counts"]
        green += c.get(GREEN, 0)
        yellow += c.get(YELLOW, 0)
        red += c.get(RED, 0)
        if not it["result"]["has_citations"]:
            neutral += 1
        if c.get(RED, 0):
            red_ids.append(it["id"])
        elif c.get(YELLOW, 0):
            yellow_ids.append(it["id"])

    summary = {
        "total": total,
        "green": green, "yellow": yellow, "red": red, "no_citation": neutral,
        "red_items": red_ids, "yellow_items": yellow_ids,
    }
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    report_md = _to_markdown(out_items, summary, as_of_date, ts)
    report_csv = _to_csv(out_items)
    return {
        "items": out_items,
        "summary": summary,
        "as_of": as_of_date,
        "generated_at": ts,
        "report_md": report_md,
        "report_csv": report_csv,
    }


def _row_for(item: Dict) -> Dict:
    """Flatten one verified item into the columns used by both MD + CSV."""
    res = item["result"]
    # A clause may cite several articles; show the first flagged one prominently,
    # but list all cited laws in the note column.
    first = res["items"][0] if res["items"] else {}
    laws_hit = "; ".join(
        f"{it.get('law_canonical') or it.get('raw_law')}第{it.get('article_no')}条"
        for it in res["items"]
    ) or "—"
    badge = RED if res["counts"].get(RED) else (YELLOW if res["counts"].get(YELLOW) else
             (GREEN if res["counts"].get(GREEN) else "⚪"))
    note = (res["overall"] if not res["items"]
            else " / ".join(i["note"] for i in res["items"]))
    return {
        "id": item["id"],
        "text": _excerpt(item["text"], 60),
        "badge": badge,
        "laws": laws_hit,
        "note": note,
    }


def _to_markdown(items: List[Dict], summary: Dict, as_of: str, ts: str) -> str:
    lines = [
        "# 合规自查报告（批量）",
        "",
        f"- 生成时间：{ts}",
        f"- 评估基准日：`{as_of}`",
        f"- 条款总数：**{summary['total']}**（🟢 {summary['green']} / "
        f"🟡 {summary['yellow']} / 🔴 {summary['red']} / ⚪ {summary['no_citation']}）",
        "",
        "| # | 条款标识 | 结论 | 命中法条 | 风险提示 |",
        "|---|---|---|---|---|",
    ]
    for it in items:
        r = _row_for(it)
        lines.append(
            f"| {r['id']} | {r['text']} | {r['badge']} | {r['laws']} | {r['note']} |")
    lines.append("")
    if summary["red_items"] or summary["yellow_items"]:
        lines.append("## 需关注（🔴/🟡）")
        for it in items:
            if it["id"] in summary["red_items"] or it["id"] in summary["yellow_items"]:
                r = _row_for(it)
                lines.append(f"- **{r['id']}** {r['badge']}：{r['note']}")
        lines.append("")
    lines.append("> 本报告由 compliance-triangle 离线生成，结论为可核验法条引注的 🟢🟡🔴 标注，"
                 "🔴/🟡 项需人工复核后方可作为正式合规意见。")
    return "\n".join(lines)


def _to_csv(items: List[Dict]) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, quoting=csv.QUOTE_MINIMAL)
    w.writerow(["id", "text_excerpt", "badge", "status", "laws", "note"])
    for it in items:
        r = _row_for(it)
        # status: collapse to a single overall verdict for the row
        res = it["result"]
        if not res["items"]:
            status = "NO_CITATION"
        elif res["counts"].get(RED):
            status = "RED"
        elif res["counts"].get(YELLOW):
            status = "YELLOW"
        else:
            status = "GREEN"
        w.writerow([r["id"], r["text"], r["badge"], status, r["laws"], r["note"]])
    return buf.getvalue()


def parse_lines(text: str) -> List[Dict]:
    """Split a newline-delimited textarea into batch items (id auto-assigned).

    Blank lines are skipped. Leading `C12:` / `12.` / `- ` prefixes on a line are
    treated as the clause id; otherwise the line index is used (C1, C2, …).
    """
    items = []
    idx = 0
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        idx += 1
        m = re.match(r"^(C?\d+)[:\.\s、]\s*(.*)$", line)
        if m and (m.group(1).startswith("C") or m.group(1).isdigit()):
            cid = m.group(1) if m.group(1).startswith("C") else f"C{m.group(1)}"
            body = m.group(2).strip()
        else:
            cid, body = f"C{idx}", line
        items.append({"id": cid, "text": body})
    return items
