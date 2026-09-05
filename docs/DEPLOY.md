# 部署指南 · 合规三角（多用户 SaaS）

本指南覆盖三种运行方式：**本地**、**Docker**、**Render 免费档**。
产品为纯标准库 Python（零第三方依赖），因此构建过程不需要联网装包。

---

## 一、本地运行

```bash
cd compliance-triangle
python3 -m compliance_triangle.web          # http://127.0.0.1:8000
PORT=9000 python3 -m compliance_triangle.web
```

- `/` —— 多用户单页应用（注册 / 登录 / 核验 / 历史 / 用量 / API Key）
- `/demo` —— 原有的预生成离线展示页
- `/healthz` —— 健康检查

> 本地模式（绑定 127.0.0.1）下，旧的 `/analyze` 端点允许匿名调用，方便演示。

---

## 二、Docker 本地验证

```bash
cd compliance-triangle
docker build -t compliance-triangle:local .
docker run --rm -p 8000:10000 \
  -e HOST=0.0.0.0 \
  -e COMPLIANCE_TRIANGLE_DB=/var/data/saas.db \
  compliance-triangle:local
```

打开 http://127.0.0.1:8000 ，确认：

- 页面右上角显示「法条库 8 部 / 2327 条」
- 能注册账号、粘贴文本、看到 🟢🟡🔴 核验结果
- `curl http://127.0.0.1:8000/healthz` 返回 `{"ok": true, ...}`

---

## 三、Render 部署（免费档）

仓库里已带 `render.yaml`，走 Blueprint 一键部署：

1. 把代码推到 GitHub（master 分支）
2. 打开 https://dashboard.render.com → **New** → **Blueprint**
3. 选择本仓库，Render 会读取 `render.yaml`
4. 若提示绑定 Disk，按引导创建；**若你的套餐不支持 Disk，删掉 `render.yaml` 里的 `disk:` 段再部署**
5. 部署完成后访问分配的 `https://<service>.onrender.com`
6. （可选）在 **Environment** 里添加模型密钥以启用实时分析：
   `DEEPSEEK_API_KEY` / `ZHIPU_API_KEY` / `DASHSCOPE_API_KEY` / `MOONSHOT_API_KEY`

> **密钥永远不要提交进仓库**，只在平台的环境变量面板里设置。

---

## 四、环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `HOST` | `127.0.0.1` | 部署时必须设 `0.0.0.0`，否则外部不可达 |
| `PORT` | `8000` | 监听端口（Render 常用 `10000`） |
| `COMPLIANCE_TRIANGLE_DB` | `~/.compliance_triangle/saas.db` | SQLite 路径 |
| `CT_ALLOW_ANON_ANALYZE` | 未设置 | 设为 `1` 可强行允许匿名调用付费模型（**不建议**） |
| `COMPLIANCE_TRIANGLE_PBKDF2_ITERS` | `200000` | 口令哈希迭代数（测试会调低以提速） |
| `CT_LOG` | 未设置 | 设为 `1` 打印访问日志 |
| `COMPLIANCE_TRIANGLE_BENCH` | 同级目录 | 指向 `legal-hallucination-bench` 以取最新法条库；未设置则用内嵌快照 |

---

## 五、数据持久化（重要，请如实理解）

数据存在**单个 SQLite 文件**里，包含：账号、会话、API Key、核验历史、用量计数。

| 场景 | 数据是否保留 |
|---|---|
| 本地运行 | ✅ 保留（落在 `~/.compliance_triangle/`） |
| Docker + 挂载卷 / Render Disk | ✅ 保留 |
| **Render 免费档（无 Disk）** | ❌ **容器重启或重新部署后清空** |

免费档若要保留数据，两条路：

1. 挂载 Render Disk（部分付费套餐才支持），并把 `COMPLIANCE_TRIANGLE_DB` 指到挂载点；
2. 接受重置——对作品集演示通常够用，因为核验本身是无状态的（粘贴→出报告），历史只是附加价值。

---

## 六、已知限制（诚实清单）

这些是**当前架构的真实边界**，不是待办清单里的遗漏：

- **冷启动**：免费档实例闲置后会休眠，首次访问需等待约 30–60 秒。
- **单实例**：SQLite + 进程内锁只适用于单实例；水平扩容需换成外部数据库（如 Postgres），届时要改 `server/store.py`。
- **限流是进程内的**：`RateLimiter` 存在内存里，多实例下不共享。
- **身份系统为作品集级**：没有邮箱验证、找回密码、MFA。口令用 PBKDF2-SHA256（per-user salt、20 万次迭代）存储，会话为服务端行、登出即失效，但请勿用于承载真实客户敏感数据。
- **海外节点**：Render 节点在境外，中国大陆访问可能偏慢。
- **`/analyze` 会花钱**：它调用付费大模型，因此在部署模式下强制要求登录；配额在调用前扣减。

---

## 七、核验

部署后按顺序检查：

```bash
BASE=https://<your-service>.onrender.com

curl $BASE/healthz                                   # {"ok":true,"kb_laws":8,...}
curl -X POST $BASE/api/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"abcd12345"}'   # 返回 token
```

拿到 token 后：

```bash
TOKEN=<粘贴上一步的 token>
curl -X POST $BASE/api/verify \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  -d '{"answer":"依据《中华人民共和国公司法》第142条，公司不得收购本公司股份。"}'
```

预期：`counts` 中 🟢 为 1，返回体含 `usage`（已用 1 次）。
