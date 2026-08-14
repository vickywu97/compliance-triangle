# 对外发布清单 · 合规三角 v1.0.0

> 目标：把"已发 GitHub Release 的合规三角"扩散到公众号 / 脉脉 / LinkedIn。
> 所有文案与脚本已在仓库里，**你只需复制 + 粘贴 + 点发布**，不用再写任何字。
> （演示录屏**非必需**——README 已嵌入 `dashboard_preview.png` 静态预览图，足够展示产品形态。）

## 前置（已就绪，确认即可）
- [x] GitHub Release `v1.0.0` 已发（compliance-triangle）
- [x] 三平台文案已写好并 push：`docs/LAUNCH_POSTS.md`（公众号 / LinkedIn / 脉脉三节）
- [x] VAT 覆盖声明已 push —— **已更正为 38/38**（原「38/41，缺 39–41 条」系误读公布令号，见 CHANGELOG Unreleased）
- [x] 预览图 `docs/dashboard_preview.png` 已生成（README 顶部嵌入，替代录屏）

---

## 动作一：发微信公众号（约 5 分钟）
1. 打开本仓库 `docs/LAUNCH_POSTS.md` → 复制 **「一、微信公众号」** 整节（含标题 + 正文）。
2. 登录 <https://mp.weixin.qq.com> → 新建图文 → 粘贴。
3. 封面图用 `legal-hallucination-bench/docs/wechat_cover.png`（960×408，已在 bench 仓库）。
4. 发布（或存草稿后群发）。
5. 发出后复制文章链接备用。

## 动作二：发脉脉（约 3 分钟）
1. 打开 `docs/LAUNCH_POSTS.md` → 复制 **「三、脉脉」** 整节。
2. 打开 <https://maimai.cn> → 发布动态 → 粘贴。
3. 点发布。复制动态链接备用。

## 动作三：发 LinkedIn（约 3 分钟）
1. 打开 `docs/LAUNCH_POSTS.md` → 复制 **「二、LinkedIn」** 整节（英文）。
2. 打开 <https://www.linkedin.com> → 首页 "Start a post" → 粘贴。
3. 自带 hashtag 已写好，直接发布。复制帖子链接备用。

## 动作四：演示视频（**可选，不做也完全可以**）
README 顶部已经嵌入 `dashboard_preview.png`（真实数据绘制的预览图），足以让访客一眼看懂产品形态，**本期不要求录屏**。
如果以后想录：脚本 `docs/SCREENCAST_SCRIPT.md` + 自动加字幕 `scripts/make_screencast.py` 已备好，随时可录——**但无需旁白**，录完交给我自动剪辑配字幕即可。

---

## 收尾：形成闭环
- 每发完一条，把链接贴回三个仓库 README 的「作品集联动」区。
  - 你只要把链接发给我，我帮你加区块并 push（compliance-triangle / legal-hallucination-bench / vickywu97-profile 三处）。

## 数据口径提醒（给复核用）
- 文案中的数字（最优模型最宽松尺度 **33%** 引注幻觉、严格逐字 **8 法域 0%**、KB **2327 条 / 8 部法**）
  与 `legal-hallucination-bench/README.md` 及 `CHANGELOG.md` 一致，源自真实评测报告，非杜撰。
- 增值税法口径已统一为 **38/38**（"主席令第四十一号" 是公布令号，非条文数），KB / 本仓库 README / config 三处一致，文案未夸大覆盖。
