# ASM 增长落地计划

> 基于 4/10 讨论的 5 个方向，结合现有代码和冲刺进度制定。
> 4/18 起可投入时间，优先级按可行性和影响力排序。

---

## 方向一：自动化 Manifest 生成工具（优先级 P0）

**目标**: 降低 manifest 创作门槛，让任何 API 提供商 5 分钟内生成 .asm.json

**为什么最优先**: 没有 manifest 就没有生态，手写 manifest 是最大的采纳障碍。

### 具体交付物

1. **`asm-gen` CLI 工具** (`tools/asm-gen/`)
   - 输入：API 文档 URL 或 OpenAPI spec
   - 输出：合规的 v0.3 .asm.json
   - 实现：解析 OpenAPI → 映射到 ASM schema → 补全 taxonomy/pricing
   - 技术栈：Python，用 LLM 辅助模糊字段推断（如 taxonomy 分类）

2. **Web 表单版**（可选，Phase 2）
   - 简单的 HTML 表单，填完直接下载 .asm.json
   - 可部署为 GitHub Pages

### 落地步骤

| 步骤 | 内容 | 预计时间 |
|------|------|---------|
| 1 | 设计 CLI 接口和映射规则（OpenAPI → ASM） | 2h |
| 2 | 实现 OpenAPI 解析 + ASM schema 填充 | 4h |
| 3 | 用现有 14 个 manifest 做回归测试 | 1h |
| 4 | README + 使用示例 | 1h |

**依赖**: 无，可独立启动

---

## 方向二：Agent 框架集成（优先级 P0）

**目标**: 让 LangChain / CrewAI 用户一行代码接入 ASM

**为什么优先**: 框架用户基数大，集成后 ASM 直接获得分发渠道。

### 具体交付物

1. **`asm-langchain` 适配器** (`integrations/langchain/`)
   - LangChain Tool wrapper：`ASMRegistryTool` — 查询 registry
   - LangChain Callback：`ASMScorerCallback` — 自动记录选择理由和 receipt
   - 示例 notebook：展示 agent 用 ASM 选服务的完整流程

2. **`asm-crewai` 适配器**（Phase 2）
   - CrewAI Tool 封装，逻辑类似

### 落地步骤

| 步骤 | 内容 | 预计时间 |
|------|------|---------|
| 1 | 研究 LangChain Tool 接口规范 | 1h |
| 2 | 实现 ASMRegistryTool（封装 MCP Server 的 HTTP 接口） | 3h |
| 3 | 实现 ASMScorerCallback | 2h |
| 4 | 写 demo notebook | 2h |
| 5 | 提 PR 到 langchain-community | 1h |

**依赖**: registry MCP Server 需要暴露 HTTP 端点（目前是 stdio，需加 express 层或独立 HTTP wrapper）

---

## 方向三：真实 A/B 测试（优先级 P1）

**目标**: 用真实数据证明 ASM + TOPSIS 比随机选择或单一提供商更优

**为什么重要**: 论文和推广都需要实证数据，光有框架没有数据说服力不够。

### 具体交付物

1. **测试脚本** (`experiments/ab_test.py`)
   - 场景：同一批 prompt，分别用 ASM 选择 vs 随机选择 vs 固定用最贵的
   - 指标：成本、延迟、质量评分（用另一个 LLM 打分）
   - 输出：对比表格 + 统计显著性

2. **测试报告** (`experiments/results/`)
   - Markdown 报告 + 可视化图表
   - 可直接嵌入论文 Section 5

### 落地步骤

| 步骤 | 内容 | 预计时间 |
|------|------|---------|
| 1 | 设计实验方案（场景、指标、样本量） | 1h |
| 2 | 准备测试 prompt 集（50-100 条，覆盖不同 taxonomy） | 2h |
| 3 | 实现测试框架（调用真实 API，记录结果） | 4h |
| 4 | 跑实验 + 收集数据 | 2h（+ API 费用） |
| 5 | 分析 + 写报告 | 2h |

**依赖**: 需要至少 2-3 个真实 API key（可用免费 tier），scorer.py 已就绪

---

## 方向四：争取大玩家背书（优先级 P1）

**目标**: 获得至少一个知名项目/公司的公开认可或集成

**为什么重要**: 开源协议的可信度严重依赖早期采纳者的身份。Schema.org 有 Google 背书才起飞。

### 具体行动

| 行动 | 目标 | 方式 | 时间 |
|------|------|------|------|
| 1 | MCP 社区 | 在 GitHub Discussion 持续参与，提 SEP（已提） | 持续 |
| 2 | Scopeblind/Agent Receipts | 深化合作，联合发文或 co-author | 已在进行 |
| 3 | LangChain 社区 | 提 PR + 写博客 "How ASM helps agents choose services" | 方向二完成后 |
| 4 | Anthropic | 如果 MCP SEP 被讨论，争取进入 official extensions | 被动等待 |
| 5 | 独立开发者 | 在 Reddit/HN 发帖，靠 demo 吸引 | 方向一完成后 |

**策略**: 不是去"求"背书，而是先做出可用的集成，让他们看到价值后主动采纳。

---

## 方向五：Registry 去中心化（优先级 P2）

**目标**: 从单一 MCP Server 演进为可联邦化的 manifest 发现网络

**为什么排后**: 当前阶段用户量不够，去中心化是规模化后的问题。但架构上要提前预留。

### 具体交付物

1. **Registry Federation 协议设计** (`sep/registry-federation.md`)
   - 定义 registry 间的同步协议
   - manifest 签名验证（v0.4 manifest signing）
   - 冲突解决策略

2. **DNS-based 发现**（概念验证）
   - `_asm._tcp.example.com` TXT 记录指向 manifest URL
   - 类似 Schema.org 的 sitemap 机制

### 落地步骤

| 步骤 | 内容 | 预计时间 |
|------|------|---------|
| 1 | 写 Federation 协议草案 | 3h |
| 2 | 实现 DNS 发现 PoC | 2h |
| 3 | 多 registry 同步 demo | 4h |

**依赖**: v0.4 manifest signing 完成后才能做安全的联邦化

---

## 阶段规划

### Phase 1（4/18 - 4/30）：基础工具 + 数据

| 周 | 重点 | 交付 |
|----|------|------|
| 4/18-4/20 | 方向一：asm-gen CLI | CLI 可用，能从 OpenAPI 生成 manifest |
| 4/21-4/25 | 方向二：LangChain 集成 | ASMRegistryTool + demo notebook |
| 4/26-4/30 | 方向三：A/B 测试设计 | 实验方案 + 测试框架骨架 |

### Phase 2（5月）：实证 + 传播

| 周 | 重点 | 交付 |
|----|------|------|
| 5/1-5/7 | A/B 测试执行 | 测试报告 + 图表 |
| 5/8-5/14 | 论文 Section 3-5 | 实证数据写入论文 |
| 5/15-5/21 | LangChain PR + 博客 | 提交社区 |
| 5/22-5/26 | Hackathon 打磨 | pitch deck + demo 优化 |

### Phase 3（6月）：规模化

- CrewAI 集成
- Registry Federation 草案
- arXiv 投稿
- 社区运营

---

## 与原冲刺计划对照

### 已完成（4/4 - 4/10）
- [x] schema.json v0.3 正式版
- [x] 14 个 .asm.json manifest（已升级到 v0.3）
- [x] scorer.py（Filter + TOPSIS + Trust Delta）
- [x] asm-registry MCP Server（v0.3 支持）
- [x] e2e demo + verify_demo
- [x] GitHub repo 已公开
- [x] Scopeblind 合作推进（3 轮 Discord 对话）

### 未完成（原计划 4/11-4/15，推迟到 4/18 起）
- [ ] 论文 Intro + Problem Formulation 初稿
- [ ] 论文 Related Work 初稿
- [ ] X/Twitter thread 定稿
- [ ] arXiv 排版
- [ ] 6 篇论文阅读笔记（部分完成）

### 新增任务（4/18 起）
- [ ] asm-gen CLI 工具
- [ ] LangChain 集成适配器
- [ ] A/B 测试框架
- [ ] 密码学基础课程学习（Ed25519, Hash, IETF）
- [ ] README 更新（reflect v0.3, verify_demo）
- [ ] .gitignore 更新 push 到公开仓库
