"""Compliance memo rendering (Markdown)."""

from __future__ import annotations

from typing import Dict

_STATUS_LABEL = {
    "OK": "已核验通过",
    "NOT_FOUND": "条文不存在/未生效",
    "TEMPORAL_DEPRECATED": "引用已废止法律",
    "PARTIAL": "引述差异(待复核)",
    "FABRICATED": "引述不符(待复核)",
    "UNVERIFIABLE": "未核验节点",
}


def build_memo_md(scenario: Dict, answer: str, result: Dict) -> str:
    """Render a compliance memo (Markdown) with the 🟢🟡🔴 verification matrix."""
    title = scenario.get("title", scenario.get("id", "场景"))
    as_of = result["as_of"]
    c = result["counts"]
    lines = []
    lines.append(f"# 合规备忘录 · {title}")
    lines.append("")
    lines.append(f"- **分析基准日**：{as_of}")
    lines.append(f"- **整体结论**：{result['overall']}")
    lines.append(f"- **引注核验统计**：🟢 {c['🟢']} · 🟡 {c['🟡']} · 🔴 {c['🔴']}")
    lines.append("")
    lines.append("## 一、场景")
    lines.append("")
    lines.append(scenario.get("scenario", ""))
    lines.append("")
    lines.append("## 二、AI 合规分析（原始输出）")
    lines.append("")
    lines.append("```text")
    lines.append(answer.strip())
    lines.append("```")
    lines.append("")
    lines.append("## 三、引注核验矩阵")
    lines.append("")
    lines.append("| 徽章 | 引注 | 核验状态 | 诊断说明 |")
    lines.append("| --- | --- | --- | --- |")
    for it in result["items"]:
        cit = f"《{it['raw_law']}》第{it['article_no']}条"
        status = _STATUS_LABEL.get(it["status"], it["status"])
        note = it["note"].replace("|", "／")
        lines.append(f"| {it['badge']} | {cit} | {status} | {note} |")
    lines.append("")
    lines.append("## 四、结论与建议")
    lines.append("")
    if c["🔴"]:
        lines.append("- 🔴 **存在未通过核验的引注**：上述标红条目要么条文不存在/未生效，"
                     "要么引用了已废止法律。相关合规结论**不可轻信**，须由人工核实真实条文后再采纳。")
    if c["🟡"]:
        lines.append("- 🟡 **存在引述差异**：标黄条目对应真实条文，但 AI 引述的措辞/但书与官方原文不一致，"
                     "建议人工比对官方文本后使用。")
    if not c["🔴"] and not c["🟡"]:
        lines.append("- 🟢 全部引注通过存在性与时效性核验，可作为进一步人工复核的基础。")
    lines.append("")
    lines.append("> 本备忘录的引注核验复用 `legal-hallucination-bench` 的 verify 引擎，"
                 "锚定 2327 条已核验法条全文。AI 可能编造法条，本系统负责拦截。")
    lines.append("")
    return "\n".join(lines)


def render(result: Dict, scenario: Dict, answer: str, fmt: str = "md") -> str:
    if fmt == "md":
        return build_memo_md(scenario, answer, result)
    raise ValueError(f"unsupported format: {fmt}")
