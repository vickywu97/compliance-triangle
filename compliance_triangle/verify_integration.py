"""Verification integration — maps a citation through the Bench verify engine
to a product-facing 🟢🟡🔴 badge.

Reuses ``benchmark.verify.content_diff`` directly (the same strict binary
content policy the benchmark uses) so the product's anti-hallucination gate is
byte-for-byte the same logic that produced the benchmark's leaderboard.
"""
from __future__ import annotations

from typing import Dict, Optional

from . import kb

# Product-facing badge taxonomy (see PRD §5.2)
GREEN = "🟢"   # citation real + in force (existence/temporal check passed)
YELLOW = "🟡"  # real article, but quoted text differs from official -> human review
RED = "🔴"     # does not exist / repealed / unverifiable


def verify_citation_item(law_name: str, article_no: str, quoted: str,
                         as_of_date: str, laws: Dict) -> Dict:
    """Verify one extracted citation and return a result dict::

        {"raw_law": ..., "article_no": ..., "badge": "🟢|🟡|🔴",
         "status": "OK|NOT_FOUND|TEMPORAL_DEPRECATED|PARTIAL|FABRICATED|UNVERIFIABLE",
         "note": ..., "ground_truth": ..., "as_of": as_of_date}
    """
    from benchmark.verify import content_diff

    res = kb.resolve(law_name, article_no, as_of_date, laws)

    # --- 🔴 temporal hallucination: cited a repealed law name ------------- #
    if res.used_deprecated_alias:
        return {
            "raw_law": law_name, "article_no": article_no, "quoted": quoted, "badge": RED,
            "status": "TEMPORAL_DEPRECATED",
            "note": f"引用了已废止法律「{law_name}」（{res.deprecated_repealed_date} 已废止），"
                    f"现行有效法律为 {res.law_name or '对应新法'}。",
            "ground_truth": "", "as_of": as_of_date,
        }

    # --- 🔴 does not exist / relocated / unknown law ---------------------- #
    if not res.found:
        note = "条文不存在或在该日期未生效（可能是虚构条号、已移序号或法律名无法识别）"
        if res.note == "UNKNOWN_LAW":
            note = f"无法识别的法律名「{law_name}」"
        return {
            "raw_law": law_name, "article_no": article_no, "quoted": quoted, "badge": RED,
            "status": "NOT_FOUND", "note": note,
            "ground_truth": "", "as_of": as_of_date,
        }

    # --- provenance gate (kept for safety; all 2327 nodes are verified) --- #
    if res.verification_status != "verified":
        return {
            "raw_law": res.law_name, "article_no": article_no, "quoted": quoted, "badge": RED,
            "status": "UNVERIFIABLE",
            "note": "该条文节点未经专家核验，暂不能作为判分基准（需人工核验）。",
            "ground_truth": "", "as_of": as_of_date,
        }

    # --- citation resolved to a real, current, verified article ----------- #
    gt = res.content or ""
    if not quoted:
        # No quoted text to compare -> existence check only -> 🟢
        return {
            "raw_law": res.law_name, "article_no": article_no, "quoted": quoted, "badge": GREEN,
            "status": "OK",
            "note": "法条存在且在有效期内（仅作存在性核验，未提供引述文本做逐字比对）。",
            "ground_truth": gt, "as_of": as_of_date,
        }

    d = content_diff(quoted, gt)
    if d.level == "EXACT":
        return {
            "raw_law": res.law_name, "article_no": article_no, "quoted": quoted, "badge": GREEN,
            "status": "OK",
            "note": "引述内容与官方条文逐字一致。",
            "ground_truth": gt, "as_of": as_of_date,
        }
    # non-exact: article is real, but the quoted wording diverges -> 🟡
    cov = d.cov
    return {
        "raw_law": res.law_name, "article_no": article_no, "quoted": quoted, "badge": YELLOW,
        "status": "PARTIAL" if cov >= 0.5 else "FABRICATED",
        "note": (f"法条真实存在，但引述内容与官方条文不一致"
                 f"（子句覆盖率 {cov:.0%}）。可能为概括/意译或遗漏但书，请人工复核。"),
        "ground_truth": gt, "as_of": as_of_date,
    }


def verify_answer(scenario_id: str, answer: str, as_of_date: str,
                  laws: Optional[Dict] = None) -> Dict:
    """Verify a full LLM compliance answer: extract all citations, verify each,
    and summarize the badge counts.
    """
    from .citation_parser import extract_citations

    laws = laws or kb.load_kb()
    items = []
    for c in extract_citations(answer):
        items.append(verify_citation_item(
            c["law_name"], c["article_no"], c["quoted"], as_of_date, laws))
    counts = {GREEN: 0, YELLOW: 0, RED: 0}
    for it in items:
        counts[it["badge"]] += 1
    if not items:
        # P0-2 fix: an answer with no 《法律》第X条 citations is NOT a pass.
        # Silently returning 🟢 here would let a vague, unverifiable answer
        # get a green light — the exact failure mode this product exists to
        # prevent. Report a neutral state instead.
        overall = ("⚪ 未检测到法条引注，无法核验——回答中未包含《法律名称》第X条"
                   "形式的引注。请确认 AI 输出是否标注了具体法条，否则本系统无从把关。")
    elif counts[RED]:
        overall = "🔴 存在未通过核验的引注，合规结论不可轻信"
    elif counts[YELLOW]:
        overall = "🟡 存在待人工复核的引述差异"
    else:
        overall = "🟢 全部引注通过核验"
    return {
        "scenario_id": scenario_id,
        "as_of": as_of_date,
        "items": items,
        "counts": counts,
        "has_citations": bool(items),
        "overall": overall,
    }
