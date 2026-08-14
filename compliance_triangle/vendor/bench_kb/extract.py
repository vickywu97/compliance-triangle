"""Vendored subset of benchmark.extract for offline fallback.

This module exists so compliance-triangle can run standalone (without the
legal-hallucination-bench repo as a sibling) while still recognizing repealed
law names as temporal hallucinations. The canonical source of this constant is
legal-hallucination-bench/benchmark/extract.py; refresh via
scripts/sync_kb_from_bench.py when that source changes.
"""

DEPRECATED_LAW_NAMES = {
    # Purged repealed-law names. They are kept OUT of laws_index.json so the KB
    # stays 100% current-law; the trap lives here at code level instead. Each
    # entry maps a repealed law name -> (surviving canonical law_code, repeal
    # date). Citing any of these post-repeal is flagged TEMPORAL_DEPRECATED and
    # is never scored against current-law text.
    #
    # Company Law family (repealed by the 2023-amended Company Law, eff. 2024-07-01):
    "旧公司法": ("COMPANY_LAW", "2024-07-01"),
    # Civil Code predecessors (all repealed when the Civil Code took effect on
    # 2021-01-01; their substance was absorbed into the Civil Code's编制/编):
    "合同法": ("CIVIL_CODE", "2021-01-01"),
    "民法总则": ("CIVIL_CODE", "2021-01-01"),
    "侵权责任法": ("CIVIL_CODE", "2021-01-01"),
    "物权法": ("CIVIL_CODE", "2021-01-01"),
    "担保法": ("CIVIL_CODE", "2021-01-01"),
    "婚姻法": ("CIVIL_CODE", "2021-01-01"),
    "继承法": ("CIVIL_CODE", "2021-01-01"),
    "收养法": ("CIVIL_CODE", "2021-01-01"),
    "民法通则": ("CIVIL_CODE", "2021-01-01"),
}
