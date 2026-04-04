# ASM (Agent Service Manifest) — 项目上下文文件

> **用途**：本文件是给新 AI 助手（没有历史对话记忆）的项目 Briefing。读完本文件后，你应该能像一个深度参与过项目全程的协作者一样继续推进工作。
> **更新日期**：2026-04-03

---

## 一、项目一句话定义

**Agent Service Manifest (ASM)** 是一个开放协议，让 AI Agent 能结构化地评估、比较和自动选择 AI 服务。

> "OpenAPI describes what a service *can do*. ASM describes what a service *is worth*."

---

## 二、问题定义

Agent 接到任务（如"帮我加字幕"），面前有多个可选服务，但：
- 定价方式不统一（按 token / 按次 / 按分钟 / 按结果）
- 质量没有标准度量
- SLA 信息不是机器可读的
- **结果：Agent 的"智能"在服务选择这一步归零，不管模型多强，面对非结构化信息它和随机选没有区别。**

ASM 让服务按统一维度暴露"价值"（成本、质量、SLA、支付方式），Agent 拿到结构化信息后用偏好函数自动选择。

---

## 三、ASM 在协议生态中的位置

```
MCP  → "这个工具能做什么"        ✅ 已解决（Anthropic）
A2A  → "agent 之间怎么通信"      ✅ 已解决（Google）
AP2  → "怎么安全地付钱"          ✅ 已解决（Google）
ASM  → "这个服务值多少、该不该买"  ❌ 无人做 ← 这是我们
```

**ASM 是 MCP 和 AP2 之间缺失的一层。**

---

## 四、当前进度

### 已完成 ✅
- ASM 协议 v0.2（JSON Schema，5 大模块：pricing/quality/sla/payment/extensions）
- 18 类 taxonomy（ai.llm.chat, ai.vision.image_generation 等）
- 3 个跨品类真实 Demo（Claude Sonnet 4 / FLUX 1.1 Pro / Veo 3.1）
- 最小决策函数 Demo（Python，加权平均，3 种偏好场景）
- SEP-ready Problem Statement（7 章，可直接用于 MCP 提案）
- MCP Discord 发帖 + 收到 IETF signed receipts 开发者积极回复
- MCP GitHub Discussion #69 跟帖（定位 ASM 为 service discovery 的 value metadata 层）
- 深度调研文档（16 章，~1800 行，覆盖协议空白分析、竞品、论文、博弈论、曝光策略）

### 待做 🔜（4/4 - 4/15 冲刺期）
- 导出正式 `schema.json`
- 写 14 个真实服务的 `.asm.json` manifest
- 实现 `scorer.py`（Filter + TOPSIS 两阶段）
- 搭建 `asm-registry` MCP Server
- 跑通 e2e demo
- 开源 GitHub repo
- 论文 Intro + Related Work 初稿
- X/Twitter thread 定稿

---

## 五、核心设计决策（你需要知道的）

### 5.1 Schema 设计原则
- MCP 兼容：可作为 `x-asm` 注解扩展嵌入 MCP ToolAnnotations
- 只有 3 个必填字段：`asm_version`, `service_id`, `taxonomy`
- 多计费维度并存：`billing_dimensions` 是数组（LLM 有 input_token + output_token）
- 品类特定字段放 `extensions` 命名空间，核心 schema 永远稳定

### 5.2 Scorer 设计
- **v0.2（demo 阶段）**：简单加权平均，够证明 concept
- **v1.0（论文阶段）**：Filter（硬约束过滤）→ TOPSIS（多准则排序）
- ASM Scorer 和 LLM Routing（如 RouteLLM）是互补关系：
  - RouteLLM：同品类内动态路由（"这个问题用 GPT-4 还是 Mixtral"）
  - ASM：跨品类静态选择（"这个任务用哪家的什么服务"）

### 5.3 MCP 集成路径
- Phase 1（现在）：独立的 `.well-known/asm` 端点
- Phase 2（SEP 通过后）：`x-asm` 嵌入 ToolAnnotations
- Phase 3（长期）：成为 MCP 核心字段

### 5.4 信任机制
- L1：`self_reported` 标记透明度
- L2：第三方 benchmark 引用
- L3：Signed Receipts 事后验证（与 Agent Receipts 团队合作中）

### 5.5 冷启动
- Registry 主动从公开定价页面抓取，不依赖 Provider opt-in
- 14 个服务（6 品类 × 2-3 个）就够做有说服力的 demo

---

## 六、关键竞品与差异化

| 竞品 | 做什么 | 不做什么 | ASM 的差异 |
|------|-------|---------|----------|
| MCP | 工具能做什么 | 工具值多少 | ASM 是 MCP 扩展层 |
| A2A | Agent 间通信 | 服务选择 | 互补 |
| AP2 | 安全付款 | 买哪个 | ASM 是 AP2 前置决策层 |
| AaaS-AN | Agent 组织协作 | 服务经济属性 | ASM 做经济决策，AaaS-AN 做协作编排 |
| OpenRouter | LLM 路由聚合 | 只覆盖 LLM、封闭平台 | ASM 跨品类、开放协议 |
| AWS Marketplace MCP | MCP 上做商品比较 | 封闭平台锁定 | ASM 是开放标准版 |
| RouteLLM | 同品类内动态路由 | 跨品类选择 | 互补：ASM 选品类+Provider，RouteLLM 选具体模型 |

---

## 七、学术规划

- **论文类型**：Systems / Demo paper
- **标题方向**：「Agent Service Manifest: A Standardized Value Description Protocol for Autonomous Service Selection in Multi-Agent Systems」
- **投稿目标**：arXiv 预印本（5月初）→ NeurIPS 2026（摘要 5/4）→ AAMAS 2027
- **黑客松**：Anthropic AI Hackathon（5/26）→ Global MCP Hackathon（8月）

---

## 八、关键论文（已调研）

| 论文 | 与 ASM 的关系 |
|------|-------------|
| [Agent Protocol Survey](https://arxiv.org/abs/2504.16736) | ASM 填补其"服务经济学"空白 |
| [AaaS-AN](https://arxiv.org/abs/2505.08446) | 最近竞品，做协作不做经济，互补 |
| [MCP Security](https://arxiv.org/abs/2503.23278) | 引用其 MCP 生态数据 |
| [RouteLLM](https://arxiv.org/abs/2406.18665) | 同品类路由，和 ASM 跨品类选择互补 |
| [Dynamic Routing Survey](https://arxiv.org/abs/2603.04445) | LLM 路由全景，定位 ASM 的学术位置 |
| [Pay for Second-Best](https://arxiv.org/abs/2511.00847) (WWW 2026) | 博弈论防 Provider 造假，ASM 信任机制的理论根基 |

---

## 九、社区互动状态

| 渠道 | 状态 | 下一步 |
|------|------|--------|
| MCP Discord | ✅ 已发帖，收到 Signed Receipts 开发者回复 | 等好友申请通过，推进 doc exchange |
| MCP GitHub Discussion #69 | ✅ 已跟帖 | 等回复 |
| GitHub repo | 🔜 待创建 | 4/11 开源 |
| X/Twitter | 🔜 待发 | 4/14 定稿 |
| arXiv | 🔜 待投 | 5 月初 |

---

## 十、项目文件结构

```
agent-service-manifest/
├── PROJECT-CONTEXT.md          ← 你正在读的这个文件
├── 调研文档.md                  ← 核心调研（16 章，~1800 行）
├── ASM曝光与学术规划.md          ← 时间线 + 执行计划
├── 黑客松选择建议.md             ← 比赛筛选
├── 论文阅读指南.md               ← 6 篇论文的定制阅读策略
├── 冲刺计划-4月.md               ← 4/4-4/15 每日安排
├── github-discussion-69-reply.md ← GitHub 跟帖内容存档
```

---

## 十一、Owner 信息

- **作者**：Caleb（yi guo）
- **背景**：腾讯广告 PM 实习（预算行业服务方向），同时做个人项目
- **GitHub 账号**：velmavalienteqejimu22-jpg（待更换为正式账号）
- **目标**：用 ASM 作为个人技术品牌的核心项目，通过黑客松、学术发表和开源社区建立影响力

---

## 十二、给 AI 助手的工作指引

### 你现在的角色
你是这个项目的技术协作者。Owner 会给你具体任务（写代码、写论文段落、调研某个问题），你需要：

1. **始终对齐 ASM 的核心定位**：开放的、跨品类的、MCP 兼容的服务价值描述协议
2. **代码风格**：TypeScript（MCP Server）或 Python（scorer、demo），代码要生产级质量
3. **学术写作风格**：Systems paper，简洁、有数据支撑、每个设计决策都有 rationale
4. **不要做的事**：
   - 不要偏离 MCP 兼容性（ASM 必须能嵌入 MCP 生态）
   - 不要过度工程化（v0.2 是 demo 级别，不是生产系统）
   - 不要改动已完成的调研文档结构（只追加，不重写）

### 关键上下文
- MCP 2026 Roadmap **不做** pricing/economics → ASM 窗口期存在
- AWS 已做封闭版（Marketplace MCP Server）→ ASM 的差异化是"开放标准"
- Agent Receipts（Signed Receipts）是最重要的合作方向 → ASM 声明 + Receipt 验证 = 完整信任链
- 论文最可能被问到的致命问题："为什么不让 LLM 直接读定价页面？" → 答案在调研文档第十五章

### 如果你不确定
读 `调研文档.md`。这个文件有 1800+ 行，覆盖了项目的所有思考。任何问题的答案大概率已经在里面了。
