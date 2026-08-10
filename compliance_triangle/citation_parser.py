"""Citation extraction from free-text LLM answers.

Pulls ``《法律名》第X条`` citations out of an LLM-generated compliance answer
and grabs the statute text the model quoted right after each citation (used for
the content-match check). Chinese numerals in article numbers are converted to
arabic so they line up with the KB's article keys.

Supported citation shapes (real-world LLM outputs vary a lot):
  * Standard:           《公司法》第142条
  * 之一 variant:        《刑法》第234条之一
  * No 条 marker:        《公司法》第一百四十二条
  * Continuation:        《公司法》第15条、第142条   (same law, multiple articles)
  * Parenthetical/nested:《证券法》第X条 inside （…） or after a comma
  * English:            《Company Law》Article 142   (mapped via EN_LAW_ALIASES)
"""
from __future__ import annotations

import re

from .config import EN_LAW_ALIASES

# Chinese-numeral citation. Three shapes:
#   alt1 标准:    《公司法》第142条  (第 required, 条 optional)
#   alt2 续列:    《公司法》第15条、第142条  (、第X条 reuses prior law)
#   alt3 无"第":  《公司法》第一百四十二条  (some models drop 第 entirely)
_CN_RE = re.compile(
    r"《(?P<law>[^》]+)》\s*第\s*"
    r"(?P<num>[0-9一二三四五六七八九十百千零两]+)\s*条?"
    r"(?P<zhi>(?:之[一二三四五六七八九])?)"
    r"|(?P<cont>(?:、|，|,|；|;|及|与|和|以及)\s*第\s*"
    r"(?P<cnum>[0-9一二三四五六七八九十百千零两]+)\s*条?)"
    r"|《(?P<law3>[^》]+)》\s*"
    r"(?P<num3>[0-9一二三四五六七八九十百千零两]+)\s*"
    r"(?P<zhi3>(?:之[一二三四五六七八九])?)"
)
# English-numeral citation: 《Company Law》Article 142
_EN_RE = re.compile(
    r"《(?P<elaw>[^》]+)》\s*Article\s*(?P<enum>[0-9]+)", re.IGNORECASE
)
# Any citation, used only to find where a quoted passage ends.
_ANY_CIT_RE = re.compile(
    r"《[^》]+》\s*第\s*[0-9一二三四五六七八九十百千零两]+\s*条?"
    r"|《[^》]+》\s*Article\s*[0-9]+",
    re.IGNORECASE,
)
# stop characters that end a quoted-statute span
_SPAN_END = re.compile(r"[。；;！？\n]")

# digits that may appear in a Chinese numeral (kept here so cn2int is testable)
_CN_DIGITS = {"零": 0, "0": 0, "一": 1, "两": 2, "二": 2, "三": 3, "四": 4, "五": 5,
              "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNITS = {"十": 10, "百": 100, "千": 1000}


def cn2int(s: str) -> int:
    """Convert a Chinese numeral (0-9999) to int. Digits pass through."""
    if s.isdigit():
        return int(s)
    total, cur = 0, 0
    for ch in s:
        if ch in _CN_DIGITS:
            cur = _CN_DIGITS[ch]
        elif ch in _CN_UNITS:
            u = _CN_UNITS[ch]
            if cur == 0:
                cur = 1
            total += cur * u
            cur = 0
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


def _extract_quote(text: str, start: int) -> str:
    """If the citation is followed by a colon (：/:), treat the span up to the
    next citation or sentence-ending punctuation as the quoted statute text."""
    rest = text[start:]
    stripped = rest.lstrip(" \t　")
    if stripped[:1] not in ("：", ":"):
        return ""
    body = stripped[1:]
    nxt = _ANY_CIT_RE.search(body)
    end = nxt.start() if nxt else len(body)
    span = body[:end]
    first_end = _SPAN_END.search(span)
    if first_end:
        span = span[:first_end.start()]
    return span.strip()


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
    if not text:
        return []
    matches = []
    for m in _CN_RE.finditer(text):
        matches.append((m.start(), "cn", m))
    for m in _EN_RE.finditer(text):
        matches.append((m.start(), "en", m))
    matches.sort(key=lambda x: x[0])

    out = []
    last_law = None
    for _, kind, m in matches:
        if kind == "cn":
            if m.group("law") is not None:
                law_name = m.group("law").strip()
                last_law = law_name
                num = m.group("num")
                zhi = m.group("zhi") or ""
                raw_num = f"{num}{zhi}"
            elif m.group("cont") is not None:
                # continuation (、第X条) — reuse the preceding law name
                if last_law is None:
                    continue  # orphan continuation with no anchor; skip
                law_name = last_law
                num = m.group("cnum")
                zhi = ""
                raw_num = num
            else:
                # alt3: no 第  (《公司法》第一百四十二条)
                law_name = m.group("law3").strip()
                last_law = law_name
                num = m.group("num3")
                zhi = m.group("zhi3") or ""
                raw_num = f"{num}{zhi}"
            try:
                article_no = _article_key(cn2int(num), zhi)
            except ValueError:
                continue
            raw = f"《{law_name}》第{raw_num}条"
            quoted = _extract_quote(text, m.end())
        else:  # english
            raw_law = m.group("elaw").strip()
            law_name = EN_LAW_ALIASES.get(raw_law.lower(), raw_law)
            last_law = law_name
            num = m.group("enum")
            try:
                article_no = str(int(num))
            except ValueError:
                continue
            raw = f"《{law_name}》第{num}条"
            quoted = _extract_quote(text, m.end())
        out.append({
            "raw": raw,
            "law_name": law_name,
            "article_no": article_no,
            "quoted": quoted,
        })
    return out
