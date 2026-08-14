# Compliance Triangle · 合规三角

> Tri-domain enterprise compliance assistant (legal · tax · IP), backed by the **same person** — a lawyer / tax agent / patent attorney.
> Every AI-generated statute citation is checked through a three-layer gate (existence / timeliness / content match); citations that fail the gate are flagged with a red badge.

> 📦 **Two-repo portfolio · Product layer** — the foundation is [`legal-hallucination-bench` (private repo · access on request)](https://github.com/vickywu97/legal-hallucination-bench) (an offline benchmark that quantifies "AI legal-citation hallucination"). The full narrative / elevator pitch is in [`docs/PORTFOLIO.md` (private repo · access on request)](https://github.com/vickywu97/legal-hallucination-bench/blob/master/docs/PORTFOLIO.md).

> 🚀 **Live demo (self-contained static page)**: `docs/index.html` opens by double-click (no install / no network needed). It can also be deployed as a permanent public link:
> - **GitHub Pages**: repo Settings → Pages → Source = `Deploy from a branch` → `master` branch, `/docs` folder. Once enabled, the address is **https://vickywu97.github.io/compliance-triangle/** (note: must be enabled first to go live; this `github.io` address is also typically unreachable from mainland China — the offline `docs/index.html` is the reliable fallback).
> - Other static hosts (Vercel / Netlify / Cloudflare Pages): just upload `docs/index.html`.
> Local server: `python3 -m compliance_triangle.web` (prefers the sibling Bench KB; auto-falls-back to the built-in vendored snapshot when cloned standalone).

> 🌏 中文说明见 [README.md](./README.md).

---

## TL;DR (English)

I'm a lawyer + tax agent + patent attorney **building AI legal products**. This repo is the *product layer* of my portfolio: it turns the hallucination benchmark into a working tool that catches AI's bad statute citations in real time.

- I first **proved** (via [`legal-hallucination-bench` (private repo · access on request)](https://github.com/vickywu97/legal-hallucination-bench)) that AI cannot be trusted on legal citations: across **5 Chinese LLMs × 23 trap questions**, the Hallucination Vulnerability Index (HVI) ranged **33.3%–54.2%**, and the verbatim-EXACT compliance rate was **0% across all 8 law domains**.
- I then built **Compliance Triangle** on the *same verify engine*, so that every AI-generated statute citation is gated and bad ones are flagged 🟢🟡🔴 — *before* a human ever relies on them.
- The moat is the **triple qualification**: the same person who designs the verification rules, defines the traps, and signs off every KB entry is a licensed lawyer + tax agent + patent attorney. A pure-engineering or pure-ML team cannot replicate the domain grounding.

*(If I later pursue an AI legal PM / compliance role, this portfolio serves as backing evidence — it is not a claim that I have already transitioned.)*

---

## Product narrative (portfolio core)

I used the quantitative benchmark [`legal-hallucination-bench` (private repo · access on request)](https://github.com/vickywu97/legal-hallucination-bench)
to **prove AI is untrustworthy on legal citations** (5 models, HVI 33.3%–54.2%; verbatim-EXACT compliance = 0% across all 8 law domains);
then I built Compliance Triangle on the **same verify engine**, gating every AI-generated statute citation and
**flagging the failures with a red badge**. This is not "knowing how to use AI" — it is "knowing *where* AI fails, and having *designed a system* to prevent it."

## Three compliance pillars

| Pillar | Qualification | Covered laws (reused from Bench KB) |
| --- | --- | --- |
| Legal compliance | Lawyer | Company Law, Civil Code, Criminal Law |
| Tax compliance | Tax agent | EIT, IIT, VAT, Tax Administration |
| IP compliance | Patent attorney | Patent Law (trademark / copyright to follow) |

## Citation verification badges (🟢🟡🔴)

| Badge | Meaning |
| --- | --- |
| 🟢 Verified | The article exists and is in force |
| 🟡 Needs human review | The article is real, but the quoted text differs from the official text (paraphrase / summarized / missing a proviso) |
| 🔴 Failed | The article does not exist / is not yet in force, or it cites a **repealed** law (old Company Law, old Contract Law, etc.) |

## Architecture (maximizes reuse of Bench assets)

- **Statute KB**: read-only from `legal-hallucination-bench`'s `statutes.jsonl` (2327 nodes, full text of 8 laws). This repo stores **no** statute text of its own.
- **Verification engine**: directly reuses `benchmark/verify.py`'s `resolve_article` + `content_diff`, sharing the benchmark's "source-trust gate".
- **LLM integration**: `compliance_triangle/llm_adapter.py` (OpenAI-compatible layer for 5 Chinese models; keys via environment variables).

> **Runtime-dependency note (honest)**: at runtime this repo prefers the sibling `legal-hallucination-bench` statute KB (resolved via the `COMPLIANCE_TRIANGLE_BENCH` env var or a sibling directory) to get the latest data; it **also embeds a vendored snapshot** (`compliance_triangle/vendor/bench_kb/`, 2327 nodes / 8 laws), so it runs standalone even if `compliance-triangle` is cloned by itself. The strictly "offline, zero-dependency" claim applies to the **pre-generated static demo page** `docs/index.html` (opens by double-click, connects to no service).

> **Data-coverage note (honest)**: the Value-Added Tax Law (VAT_LAW) has **38 articles** (promulgated by Presidential Order No. 41, effective 2026-01-01 — "41" is the **promulgation order number**, not the article count). The KB has verified all 38 verbatim; nothing is missing. All 8 laws are complete official full texts.

> "Foundation → Product" relationship diagram:
> ![Portfolio architecture](./docs/portfolio_architecture.svg)

## Disclaimer

> ⚠️ This tool (Compliance Triangle) performs **automated** checks on AI-generated statute citations for *existence / timeliness / content match*. It **does not constitute legal advice, tax advice, or patent advice**, and cannot replace the professional judgment of a licensed lawyer, tax agent, or patent attorney. The verification results (🟢🟡🔴) only reflect how a citation matches the official statute text; they do **not** guarantee the correctness or applicability of any compliance conclusion. Users should consult a licensed professional for specific matters. The statute text referenced is from public official sources; the evaluation conclusions are automated scoring results that may deviate due to statute updates or extraction errors. Always rely on the latest official published text.

## Quick start

```bash
# 1) Clone the Bench repo as a sibling directory (or point an env var at it)
#    Note: Bench is a PRIVATE repo — you need access granted + Git credentials (SSH or token) to clone it.
git clone https://github.com/vickywu97/legal-hallucination-bench.git ../legal-hallucination-bench

# 2) Offline demo (no API key / no network): run 5 built-in scenarios,
#    generate a compliance memo + a static demo page
python demo/run_demo.py
# -> compliance memos: demo/output/S1..S5_*.md
# -> static demo page: docs/index.html  (double-click to open in a browser; zero-dep, offline)
```

The demo scenarios contain pre-built "hallucinated" answers, showing exactly how the verification layer intercepts fabricated article numbers and repealed law names.

### Phase 2 front-end · two ways to open

**A. Pure static demo page (recommended first look, double-click to use)**
`docs/index.html` is a **self-contained, zero-external-dependency, offline-capable** single-file page:
- Top "Verification overview": 🟢🟡🔴 count KPIs + ratio bars + breakdown by law;
- 5 demo scenarios as tabs; each citation rendered as a colored card (🟢 pass / 🟡 review / 🔴 fail),
  showing "AI quote vs. official text" side by side;
- Just double-click to open in a file manager — **no server needed**.

> Dashboard preview (a preview image generated from real demo data; open `docs/index.html` for the full interactive page):
> ![Compliance Triangle dashboard preview](docs/dashboard_preview.png)

**B. Local interactive server (paste your own AI answer for real-time verification)**
Zero third-party dependencies — only Python stdlib `http.server`:

```bash
python -m compliance_triangle.web            # default http://127.0.0.1:8000
PORT=8080 python -m compliance_triangle.web  # custom port
```

After opening in a browser, paste any LLM-generated compliance analysis (with `《Law》Article X` citations) into the "Real-time verification" area, click "Run verification", and the same verify engine checks each citation and returns 🟢🟡🔴.

### Live LLM call + automatic verification (wired up)

Beyond "paste-then-verify", this product chains `llm_adapter` + `prompt_template` into an end-to-end flow:
**fill scenario → call a Chinese model to generate analysis → same verify engine checks each citation**. Two options:

**① Command line (CLI)**

```bash
# configure the model key first (see env vars below)
python -m compliance_triangle.live \
    --scenario "Company plans to provide a large guarantee for an affiliate; confirm the resolution procedure and default remedies" \
    --as_of 2025-01-01 --model DeepSeek-V3 --out memo.md
```

If `--model` is omitted, it auto-picks the first model with a configured key; with no key it errors out explicitly (**never fails silently**).

**② Web endpoint `/analyze`**

After starting `python -m compliance_triangle.web`, choose a model and fill the scenario in the "Real-time verification" area, click "Call model and verify" — the service calls the model and feeds the result straight into the verification layer (front-end auto-renders 🟢🟡🔴).

Model keys are read from environment variables (never hardcoded; missing keys auto-degrade to "paste-only verification" mode with a banner at the top):
`DEEPSEEK_API_KEY` / `ZHIPU_API_KEY` / `DASHSCOPE_API_KEY` / `MOONSHOT_API_KEY`.
The 5 supported models are in `config.MODELS` (DeepSeek-V3 / DeepSeek-R1 / GLM-4-Flash / Qwen-Max / Kimi).

## Tests

Zero-dependency (`unittest`, stdlib only). KB-related cases need the sibling `legal-hallucination-bench`:

```bash
python -m unittest discover -s tests -v
```

Coverage: citation-parsing edge cases (no "条" character, English law names, continuations, nesting, quote-colon), the three-layer verify, KB counting (8 laws / 2327 articles), Web render fallback + live-model availability gate, and the live-call pipeline (mock model).

## Known limitations

- **Trust-tier gate not yet active**: In v1.3 Bench promoted all 2327 nodes to `verified`, so this product's "Tier A expert-signed / Tier B official-extract-unsigned" gate currently always passes and is not surfaced. The product verifies *existence / timeliness / verbatim content consistency*, not per-node provenance tiers.
- **VAT_LAW covers 38/38 articles** (current full text, verified verbatim, nothing missing; "Presidential Order No. 41" is the promulgation order number, not the article count).
- **Runtime depends on the Bench KB** (see "Runtime-dependency note" above).
- Citation parsing already covers common edge cases: no "条" character (第一百四十二条), English law names (`《Company Law》Article 142`), continuations (`《公司法》第15条、第142条`), nested book-title marks, quote-colon-then-original-text, etc. Very obscure phrasings may still slip through and be judged "not found" rather than falsely passed.

## Validated by (early user validation)

> Real trial feedback from practicing lawyers / tax advisors / patent attorneys (early validation, not a commercial endorsement).
> Collection template and backfill instructions: see `用户验证-合规三角.md` in repo.

<!-- TODO: paste 1–3 representative peer comments here, format:
> Name / role (e.g., practicing lawyer, X yrs corporate law) — one-line note (e.g., 🟡/🔴 flags on corporate-law citations were accurate, no false kills).
-->

## Roadmap

- Phase 1 (back-end skeleton): scenario input → LLM → verify → structured JSON ✅ demo-ready
- Phase 2 (front-end): compliance-memo UI + citation-verification visualization ✅
  - self-contained static demo page `docs/index.html` (offline, zero-dep, double-click)
  - zero-dep local server `python -m compliance_triangle.web` (real-time paste verification `/verify`)
- Phase 3 (portfolio-ize): standalone README / cross-links / architecture diagram / preview image / cross-repo wiring ✅
- Live LLM call + automatic verification (`compliance_triangle/live.py` + Web `/analyze` endpoint + CLI) ✅
- Citation-parsing edge-case hardening + zero-dep test suite (`tests/`) ✅
- Trust-reliability fixes (empty-answer false 🟢, graceful KB-missing degradation, VAT coverage labeling, hero counts) ✅

## License

MIT
