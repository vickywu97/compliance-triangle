# Contributing / 贡献指南

欢迎法律科技同行、开源社区、以及律师 / 税务师 / 专利代理师贡献。本产品层的核心资产是**引注核验场景**、**解析边界用例**与**对地基仓库 KB 的同步**，三者都依赖领域专业性。

This product layer's core assets are the **citation-verification scenarios**, **parser edge-case fixtures**, and **KB sync from the foundation repo**. All benefit from domain expertise.

## 0. IP & accuracy guardrail (read first)

> ⚠️ 本仓库与地基仓库 `legal-hallucination-bench` 一样，**严禁引入任何第三方受著作权保护的内容**（教材、考试题、合同范本、商业数据库摘录、第三方 logo 等）。法条文本来自公开官方来源（flk.npc.gov.cn），属公开政府信息，可合法收录。所有评测数字必须**可复现、带版本号与日期**，不得夸大或编造。

- Do **not** commit any third-party copyrighted material (textbooks, exam questions, contract templates, commercial DB excerpts, third-party logos, etc.).
- Statute text comes from public official sources (flk.npc.gov.cn) and is permissible to include.
- All benchmark/evaluation numbers must be **reproducible, versioned, and dated** — never exaggerated or fabricated.

## 1. 同步地基 KB（vendor 快照）

本仓库内嵌一份 Bench KB 快照（`compliance_triangle/vendor/bench_kb/`）。若地基仓库法条有更新，用脚本刷新：

```bash
python scripts/sync_kb_from_bench.py
```

- 快照同步后必须跑测试确认计数仍为 **8 部法 / 2327 条**：`python -m unittest discover -s tests -v`。
- 不要手动编辑 `compliance_triangle/vendor/bench_kb/laws/statutes.jsonl`；它应由同步脚本生成。

## 2. 贡献引注核验场景（`demo/scenarios.py`）

- 每个场景是一个内置「含幻觉」的预置回答，用于演示校验层如何拦截虚构条号 / 已废止法名。
- 场景中的法条引注必须**真实可核验**（出自 8 部法之一），幻觉部分须明确标记为构造。
- 新增场景后跑 `python demo/run_demo.py` 确认 `demo/output/index.html` 正常生成。

## 3. 贡献引注解析边界用例（`tests/`）

- 覆盖常见与冷门写法：不含「条」字、英文法名、续列、嵌套书名号、引述冒号接原文等。
- 用 `unittest` 编写，仅标准库，**禁止引入第三方依赖**（保证离线可跑）。

## 4. 审核流程

- PR 经维护者审核（重点：是否引入第三方版权内容、数字是否可复现、场景构造是否诚实）。
- 涉及 KB 的变更须通过同步脚本 + 测试，不手动改快照。

## 5. 代码规范

- 纯 Python，禁止引入 C 扩展依赖（保证离线可跑）。
- 所有 KB 读取走 `compliance_triangle/kb.py` 的 `load_kb()`，勿硬编码路径。
- 模型密钥一律从环境变量读取，严禁硬编码。
