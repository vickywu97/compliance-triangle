"""Prompt templates for the compliance-analysis LLM call.

Design goals (PRD §5.1): structured output, standard citation format
(《法律名》第X条), and a strict in-scope-law guardrail that converts any
out-of-scope / fictional citation into a clean hard hallucination.
"""
from __future__ import annotations

from .config import LAW_SCOPE

COMPLIANCE_SYSTEM_PROMPT = (
    "你是一位严谨的中国企业合规顾问，同时具备法律、税务、知识产权三重专业背景。"
    f"本次分析仅限以下八部现行有效法律：{LAW_SCOPE}。"
    "请仅引用这八部法律中的具体条文。\n\n"
    "输出要求（务必遵守，便于后续自动核验）：\n"
    "1. 结构化：先写「场景分析」，再按「法律合规 / 税务合规 / 知识产权合规」分域列出"
    "「涉及法条」「风险等级（高/中/低）」「建议措施」。\n"
    "2. 引注格式：每条法条使用标准格式 《法律名称》第X条 "
    "（例如 《公司法》第142条、《个人所得税法》第2条）。\n"
    "3. 如需引用条文原文，请在引注后紧接原文；如仅概括适用，也请明确说明。"
    "若问题无法由这八部法律回答，请明确说明「依据所给八部法律无法回答」，"
    "切勿引用其他法律、已废止法律（如旧公司法、合同法）或虚构法律/条号。"
)

USER_PROMPT_TEMPLATE = (
    "请就以下企业合规场景出具一份合规分析备忘录：\n\n"
    "【场景】{scenario}\n\n"
    "（分析基准日视为 {as_of_date}；请只引用该日期现行有效的法律条文。）"
)


def build_messages(scenario: str, as_of_date: str) -> list:
    return [
        {"role": "system", "content": COMPLIANCE_SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
            scenario=scenario, as_of_date=as_of_date)},
    ]
