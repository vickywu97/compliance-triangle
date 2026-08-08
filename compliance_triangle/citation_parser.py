"""Citation extraction from free-text LLM answers.

Pulls ``《法律名》第X条`` citations out of an LLM-generated compliance answer
and grabs the statute text the model quoted right after each citation (used for
the content-match check). Chinese numerals in article numbers are converted to
arabic so they line up with the KB's article keys.
"""
from __future__ import annotations

import re

# 《法律名》第<数字>条  (+ optional 之一, which we keep as-is for the key)
_CIT_RE = re.compile(
    r"《([^》]+)》\s*第\s*([0-9一二三四五六七八九十百千零两]+)\s*条(?:(之[一二三四五六七八九]))?"
)
# stop characters that end a quoted-statute span
_SPAN_END = re.compile(r"[。；;！？\n]")


def cn2int(s: str) -> int:
    """Convert a Chinese numeral (0-9999) to int. Digits pass through."""
    if s.isdigit():
        return int(s)
    digits = {"零": 0, "0": 0, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
    units = {"十": 10, "百": 100, "千": 1000}
    total, cur, prev_unit = 0, 0, 1
    for ch in s:
        if ch in digits:
            cur = digits[ch]
        elif ch in units:
            u = units[ch]
            if cur == 0:
                cur = 1
            total += cur * u
            cur = 0
            prev_unit = u
        else:
            raise ValueError(f"unexpected char {ch!r} in {s!r}")
    # leftover cur (e.g. 十三 -> total=10, cur=3 -> 13)
    total += cur
    return total


def _article_key(num_arabic: int, zhi: str) -> str:
    """KB article key: integer string for plain articles, decimal for 之一."""
    if zhi:
        # 第234条之一 -> "234.001" (matches Bench sort_key convention)
        return f"{num_arabic}.001"
    return str(num_arabic)


def extract_citations(text: str) -> list:
    """Return a list of dicts::

        {"raw": "《公司法》第142条", "law_name": "公司法",
         "article_no": "142", "quoted": "<statute text the model quoted>"}

    ``quoted`` is only populated when the model explicitly quotes the statute
    text — i.e. the citation is immediately followed by a colon (：/:). This
    matches the prompt instruction ("如需引用条文原文，请在引注后紧接原文"):
    a bare citation is verified at the existence/temporal level only (🟢),
    while a colon-quoted passage is also content-checked (🟡/🟢). Any other
    trailing prose is NOT treated as a quote.
    """
    out = []
    for m in _CIT_RE.finditer(text):
        law_name = m.group(1).strip()
        try:
            num = cn2int(m.group(2))
        except ValueError:
            continue
        article_no = _article_key(num, m.group(3) or "")
        raw = m.group(0)
        quoted = ""
        start = m.end()
        # skip spaces; a colon means the model is quoting the statute text
        rest = text[start:]
        stripped = rest.lstrip(" 　")
        if stripped[:1] in ("：", ":"):
            body = stripped[1:]
            nxt = _CIT_RE.search(body)
            end = nxt.start() if nxt else len(body)
            span = body[:end]
            first_end = _SPAN_END.search(span)
            if first_end:
                span = span[: first_end.start()]
            quoted = span.strip()
        out.append({
            "raw": raw,
            "law_name": law_name,
            "article_no": article_no,
            "quoted": quoted,
        })
    return out
