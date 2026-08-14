# Changelog

本项目所有重要变更记录在案。格式参考 [Keep a Changelog](https://keepachangelog.com/)，
版本号遵循 [语义化版本](https://semver.org/lang/zh-CN/)。

---

## Unreleased — 数据口径修正

- **修正 VAT 法条文数误读**：此前 README / config 称「增值税法收录 38/41 条，第 39–41 条未入库」。
  实际《增值税法》共 **38 条**（主席令第四十一号公布，2026-01-01 施行）——"41" 是**公布令号**，
  并非条文数，故不存在第 39–41 条。KB 已全数逐字核验，8 部法均完整无缺漏。已同步更正
  README「数据覆盖说明」、Known Limitations、`config.COVERAGE_CAVEATS` 与相关测试注释。

## v1.0.0 (2026-08-11) — 三证合一的 AI 合规助手（首个公开发布）

> 版本映射：`v1.0.0` 标签落在首个公开发布 HEAD（`ba3a10b`），涵盖 Phase 1–3 全部工作 +
> 可信度修复（Batch A）+ 引注解析边界与测试套件（Batch B）+ LLM 实时调用（Batch C）。
> 复用地基仓库 `legal-hallucination-bench` 的 `statutes.jsonl` 与 `benchmark/verify.py`，
> 故本仓库首个版本即定位为产品层而非独立基准，版本号自 `v1.0.0` 起。

### 产品定位
- **地基 → 产品**：`legal-hallucination-bench` 量化了"AI 法律引注幻觉"（5 国产模型 × 23 陷阱题，
  HVI 33%–54%，8 法域逐字 EXACT 全 0%）；本仓库用**同一套 verify 引擎**把"量化"变为"实时拦截"——
  让 AI 生成的每条法条引注都盖上 🟢🟡🔴 章。
- **三证合一护城河**：作者具备**律师 + 税务师 + 专利代理师**三重资质，覆盖法律 / 税务 / 知识产权
  三域合规。同一人设计校验规则、定义陷阱、签署每一条 KB——纯工程 / 纯算法团队无法复制。

### 核心能力
- **三层校验**：存在性（条文是否存在）/ 时效性（是否引用已废止法）/ 内容匹配（是否逐字）。
- **🟢🟡🔴 徽章**：通过 / 待人工复核（概括·意译·漏但书）/ 未通过（不存在·已废止·张冠李戴）；
  新增 **⚪ 未检测到法条引注**（空回答不再误报 🟢）。
- **零依赖运行**（仅 Python 标准库 `http.server`）：
  - 自包含静态展示页 `demo/output/index.html`（离线、零外部依赖、双击即用）；
  - 本地交互服务 `python -m compliance_triangle.web`（粘贴 AI 回答实时校验 `/verify`）；
  - 端到端 LLM 调用 `python -m compliance_triangle.live` 或 Web `/analyze`（调国产模型生成并自动校验）。
- **测试套件**：32 个 `unittest` 全绿，覆盖引注解析边界、verify 三层校验、KB 计数（8 部法 / 2327 条）、
  Web 渲染降级与实时模型可用性门禁、实时调用流水线（mock 模型）。

### 引注解析边界（Batch B）
- 重写 `citation_parser.py`，覆盖：无「条」或省略「第」（《公司法》第一百四十二条）、
  英文法名（《Company Law》Article 142，经 `EN_LAW_ALIASES` 映射）、续列同法
  （《公司法》第15条、第142条）、嵌套书名号、引述冒号接原文、之一（《刑法》第234条之一）。
- 修复 `cn2int` 缺 `"一": 1` 的隐藏 bug（原仅阿拉伯数字用例未见，中文数字首例触发）。

### 可信度修复（Batch A）
- 空答案 → ⚪ 未检测到引注，不再误报 🟢；
- KB 缺失时优雅降级（服务不崩溃，离线结构展示 + `/verify` 返回 503 明确提示）；
- 增值税法 38/41 条诚实声明（`COVERAGE_CAVEATS`）；
- README 诚实化（运行时依赖 Bench KB、信任分级暂未启用、hero 计数修正为 8 部法 / 2327 条）。

### 已知限制（诚实声明）
- **运行时依赖 Bench KB**：`python -m compliance_triangle.web` 与 `demo/run_demo.py` 启动需加载同级
  `legal-hallucination-bench/statutes.jsonl`；KB 缺失时服务降级展示、不崩溃。真正"零依赖、双击即用"
  的是预生成的 `demo/output/index.html`。
- **增值税法覆盖 38/41 条**：第 39–41 条暂未入库，对这几条的引用会被判"未找到"。
- **信任分级暂未启用**：Bench v1.3 已将 2327 节点全升为 verified，本产品的 Tier A/B 门禁当前恒为真、
  不呈现；核验聚焦存在性 / 时效性 / 逐字一致性。

---

## 路线图（未发布，记录意图）
- Phase 1（后端骨架）：场景输入 → LLM → verify 校验 → 结构化 JSON ✅
- Phase 2（前端）：合规备忘录 UI + 引注核验可视化 ✅
  - 自包含静态展示页 `demo/output/index.html`（离线、零依赖、双击即用）
  - 零依赖本地服务 `python -m compliance_triangle.web`（实时粘贴校验 `/verify`）
- Phase 3（作品集化）：独立 README / 互链 / 架构图 / 预览图 / 跨仓库联动 ✅
- 实时调用 LLM 并自动校验（`live.py` + Web `/analyze` + CLI）✅
- 引注解析边界加固 + 零依赖测试套件（`tests/`）✅
- 可信度修复（空回答误报🟢、KB 缺失优雅降级、VAT 覆盖标注、hero 计数）✅
- **下一步**：商标 / 著作权支柱扩展；演示录屏与对外推广。（注：增值税法已于 KB 全数核验 38/38，无待补全条目——原「补全 39–41 条」系误读公布令号，已更正，见 Unreleased。）
