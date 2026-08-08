"""Build the built-in demo dataset (scenario + answer + verification result).

Shared by the offline demo runner and the web app so the showcase data is
generated exactly once and identically.
"""
from __future__ import annotations

from typing import Dict, List, Optional


def build_demo_data(laws: Optional[Dict] = None) -> List[Dict]:
    """Return a list of ``{"scenario", "answer", "result"}`` for all built-in
    scenarios, each ``result`` produced by the Bench verify engine.
    """
    from compliance_triangle import kb
    from compliance_triangle.verify_integration import verify_answer
    from demo.scenarios import SCENARIOS

    laws = laws or kb.load_kb()
    out = []
    for s in SCENARIOS:
        res = verify_answer(s["id"], s["answer"], s["as_of_date"], laws)
        out.append({"scenario": s, "answer": s["answer"], "result": res})
    return out
