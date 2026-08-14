# 合规三角 v1.0.0 发布宣传稿（三平台）

> 用途：合规三角首个公开发布（GitHub Release `v1.0.0`）后，去三个平台发文扩散。
> 三版已按平台调性写好的，复制即用。数据口径与 `README.md` / `CHANGELOG.md` 一致。
> 仓库链接：
> - 产品：[github.com/vickywu97/compliance-triangle](https://github.com/vickywu97/compliance-triangle)
> - 地基：[github.com/vickywu97/legal-hallucination-bench（私有仓库 · 需授权访问）](https://github.com/vickywu97/legal-hallucination-bench)

---

## 一、微信公众号（故事感 + 钩子，约 600 字）

**标题**：我把"AI 引用法条会胡说"这件事，做成了一个能实时拦它的产品

做了十年法律 / 税务 / 知识产权，我现在在转 AI 法律产品。转的过程中我越来越确信一件事：
**大模型在"引用法条"这个最基础的动作上，可靠性堪忧。**

我先用一个离线基准量化了它——5 个国产模型、23 道带陷阱的题，在最宽松的尺度下，
表现最好的模型仍有 **33%** 的法条引注是幻觉；而在最严格的"逐字复述"尺度下，
**8 个法域全军覆没，正确率 0%**。连付费旗舰都没好到哪去。

光量化不够。所以我做了第二个东西——**合规三角**（Compliance Triangle），已经发布 v1.0.0。

它的想法很简单：既然 AI 会编造条文、引用已废止的法律、张冠李戴，那就给它的每一条引注
**实时盖个章**——

- 🟢 通过：条文真实、在有效期内
- 🟡 待复核：条文真实，但引述内容和官方有出入（概括 / 漏但书）
- 🔴 未通过：条文不存在，或引用了已废止的法律（比如 2024 新公司法施行后还引"旧公司法"）

你把你任何一个 LLM 生成的合规分析粘进去，它就用同一套引擎逐条核对 2327 条现行法条，
把错误标出来。也能反过来——你给个业务场景，它调国产模型生成分析，**生成完自动送进同一套校验层**。

整个产品离线、零依赖、可复现，32 个测试全绿。地基是我另一个仓库（专家逐条核验的法库），
合规三角是它上面的产品层。

这不是"会用 AI"，而是"知道 AI 哪里会出错，并设计了系统去防止"——
我觉得这正是 AI 法律产品岗最该具备的能力。

仓库在这 👉 [github.com/vickywu97/compliance-triangle](https://github.com/vickywu97/compliance-triangle)
（同名地基仓库 [legal-hallucination-bench（私有仓库 · 需授权访问）](https://github.com/vickywu97/legal-hallucination-bench)）

---

## 二、LinkedIn（英文、职场专业，面向外企 / 海外招聘）

**Headline**: Shipping Compliance Triangle v1.0.0 — turning "AI cites law incorrectly" from a metric into a real-time guardrail.

After a decade as a lawyer, tax agent, and patent attorney, I'm building AI legal products. My portfolio now has two linked repos:

1. **legal-hallucination-bench** — an offline, expert-verified benchmark proving how badly LLMs quote Chinese statutes. On the most forgiving metric, even the best domestic model still hallucinates on **33%** of citations; on verbatim accuracy across 8 law domains, the rate is **0%**.
2. **compliance-triangle** (v1.0.0, just released) — the product layer. It takes the *same* verification engine and turns "measuring hallucination" into "blocking it in real time."

Paste any LLM-generated compliance analysis, and every statute citation gets a 🟢 / 🟡 / 🔴 verdict:
- 🟢 verified (exists, in force)
- 🟡 needs human review (real article, but paraphrased / missing provisos)
- 🔴 failed (doesn't exist, or cites a repealed law like the pre-2024 Company Law)

It can also generate an analysis via a domestic model and auto-verify the output in one pipeline.

Fully offline, zero third-party dependencies, 32 unit tests green. Built on a 2,327-node verified statute KB.

Why this matters for an AI legal / compliance role: it's not "I can use AI" — it's "I can define the failure modes, quantify them, and ship a system that prevents them." That's the part pure-engineering or pure-legal teams can't replicate.

Repos:
- 🛡️ https://github.com/vickywu97/compliance-triangle
- 🧱 https://github.com/vickywu97/legal-hallucination-bench（私有仓库 · 需授权访问）

#AILaw #LegalTech #ProductManagement #Compliance #LLMEvaluation

---

## 三、脉脉（中文职场、简洁、强调作品集 + 数据）

**标题**：律师/税务师/专利代理师 在做 AI 法律产品，我发布了第二个作品

从法律实务转 AI 法律产品，我的作品集又往前走了一步：合规三角（Compliance Triangle）v1.0.0 已发布。

一句话定位：给 AI 生成的每条法条引注，实时盖 🟢🟡🔴 的章——
🟢通过 / 🟡待复核（概括漏但书）/ 🔴未通过（虚构条号或引用已废止法）。

三个数字说明它解决的痛点：
- 我另一个地基仓库测过：5 国产模型、23 道陷阱题，**最宽松尺度下最优模型仍有 33% 引注幻觉**；
- 最严格"逐字"尺度，**8 法域正确率全 0%**；
- 合规三角底层是 **2327 条专家核验的现行法条**，离线、零依赖、32 测试全绿。

三证合一（律师+税务师+专利代理师）是我做这件事的护城河：同一人定义陷阱、签每条 KB、设计校验规则。

产品仓 👉 github.com/vickywu97/compliance-triangle
地基仓 👉 github.com/vickywu97/legal-hallucination-bench（私有仓库 · 需授权访问）

欢迎 AI 法律 / 合规方向的团队交流 🙌

---

## 发文顺序建议
1. **知乎**（之前已发地基篇）→ 可补一篇"产品篇"呼应；
2. **公众号** → 长文沉淀，适合转发；
3. **脉脉** → 职场曝光， recruiting 向；
4. **LinkedIn** → 外企 / 海外机会。

每发完一条，把链接贴回三个 GitHub 仓库的 README「作品集联动 / 联系」区，形成闭环。
