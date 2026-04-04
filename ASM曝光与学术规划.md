# ASM 曝光 + 学术路线规划

> 更新日期：2026-04-02
> 原则：**纯线上参与，不出国**；学术和工程双线推进，互相喂养

---

## 一、时间线总览

```
4月 ████████████████████████████████
     第1周(3/30)  MCP Discord 发帖 + arXiv 预印本准备
     第2周(4/7)   ASM demo MVP 完成（schema + registry + scorer）
     第3周(4/14)  arXiv 投稿 + 黑客松报名确认
     第4周(4/20)  🏆 Agentic Commerce on Arc 黑客松（4/20-26）

5月 ████████████████████████████████
     第1周(5/4)   NeurIPS 2026 摘要截止（5/4）⚡
     第2周(5/6)   NeurIPS 2026 全文截止（5/6）⚡
     第3周(5/11)  AI & Big Data Expo 黑客松（5/11-19，可选）

6-8月 ██████████████████████████████
     6月          NeurIPS Workshop CFP 陆续开放
     8月          🏆 Global MCP Hackathon（~8/12）
     8/15-17      IJCAI 2026 Workshops（Bremen，投稿看具体 workshop CFP）
```

---

## 二、线上曝光渠道（按优先级排序）

### P0：MCP 社区 — 直接影响标准制定者

| 动作 | 内容 | 时间 |
|------|------|------|
| **MCP CWG Discord 发帖** | 在 `#working-group-ideation` 发起 "Service Economics / Agent Service Manifest" 讨论 | 本周 |
| **GitHub Discussion** | 在 modelcontextprotocol/specification 开一个 Discussion，附 ASM schema + 3个demo | 4月第2周 |
| **SEP PR** | demo 跑通后，正式提交 PR 到 `seps/` 目录 | 4月底–5月 |

关键链接：
- Discord: https://discord.com/invite/model-context-protocol-1312302100125843476
- CWG: https://github.com/modelcontextprotocol-community/working-groups
- MCP Spec: https://github.com/modelcontextprotocol/specification
- 2026 Roadmap: http://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/

### P1：黑客松 — 逼自己出 demo + 拿奖金

| 比赛 | 时间 | 奖金 | 适合度 |
|------|------|------|--------|
| **Agentic Commerce on Arc** | 4/20-26 | $20K USDC + $10K GCP | ⭐⭐⭐⭐⭐ Agent选服务+自动付费 |
| **Global MCP Hackathon** | ~8/12 | $25K+ | ⭐⭐⭐⭐⭐ 高级赛道=协议层创新 |
| AI & Big Data Expo | 5/11-19 | 企业曝光 | ⭐⭐⭐ 开放主题备选 |

持续关注：https://www.mcphackathon.com/ / https://huggingface.co/Agents-MCP-Hackathon

### P2：内容传播 — 让更多人知道 ASM

| 渠道 | 内容形式 | 目标 |
|------|---------|------|
| **arXiv 预印本** | 学术论文（见下方学术规划） | 被 survey 引用、建立学术信用 |
| **X/Twitter 英文 thread** | "The Missing Layer: MCP → ??? → AP2" + demo GIF | 触达 MCP 开发者社区 |
| **小红书** | "我设计了一个AI服务标准协议" 系列 | 中文圈传播 + 个人品牌 |
| **GitHub 开源** | asm-spec / asm-registry / asm-scorer 三个 repo | 让别人能用、能贡献 |
| **Dev.to / Medium** | 英文技术博客 "Why Your Agent Picks the Wrong Service" | SEO + 长尾流量 |

---

## 三、学术规划

### 3.1 学术定位

ASM 的学术贡献不是算法创新，而是**系统设计 + 标准化 + 实证验证**。最适合的论文类型：

| 类型 | 适合度 | 说明 |
|------|--------|------|
| **Systems / Demo paper** | ⭐⭐⭐⭐⭐ | "我们设计了一个系统，解决了真实问题" |
| **Position paper** | ⭐⭐⭐⭐ | "这个领域缺了什么，应该怎么补" |
| **Survey + Contribution** | ⭐⭐⭐⭐ | 在 survey 基础上提出 ASM 作为解决方案 |
| 纯理论 paper | ⭐ | ASM 不是算法，不适合 |

### 3.2 已有相关学术工作（ASM 需要引用 + 区分）

| 论文 | 关键词 | 与 ASM 的关系 |
|------|--------|-------------|
| [A Survey of AI Agent Protocols](https://arxiv.org/abs/2504.16736) | MCP/A2A/ACP/ANP 综述 | ASM 填补其中"服务经济学"空白 |
| [Agent-as-a-Service (AaaS-AN)](https://arxiv.org/abs/2505.08446) | RGPS 标准的服务化 agent | 最接近竞品，但侧重组织协作而非经济决策 |
| [MCP Landscape & Security](https://arxiv.org/abs/2503.23278) | MCP 安全分析，ACM TOSEM | 可引用其 MCP 生态数据 |
| [Context-Aware MCP Server Collaboration](https://arxiv.org/abs/2601.11595) | MCP server 协作 | 互补关系：它做协作，ASM 做选择 |
| [MCP Design Patterns](https://arxiv.org/html/2603.13417) | MCP 部署模式 | 可引用其架构分析 |
| CASTER / DyTopo / LLM Council | 多 agent 路由 | 算法层面的路由，ASM 是协议层面的信息标准 |

### 3.3 论文写作计划

**标题方向**：
> "Agent Service Manifest: A Standardized Value Description Protocol for Autonomous Service Selection in Multi-Agent Systems"

**结构**（Systems paper 模板）：

1. **Introduction** — Agent 经济体正在形成，但没有"商品标签"
2. **Background & Related Work** — MCP / A2A / AP2 / AaaS-AN / LLM 路由
3. **Problem Formulation** — 形式化定义：给定 agent 任务 T、用户偏好函数 P、候选服务集 S → 最优选择问题
4. **ASM Protocol Design** — Schema v0.2（已有）、设计原则、兼容性
5. **Reference Implementation** — registry + scorer + demo
6. **Evaluation** — 3 个跨品类案例（已有：Claude Sonnet / FLUX / Veo）+ 成本节约量化
7. **Discussion** — 局限性、隐私、博弈论问题（provider 会不会虚报质量？）
8. **Conclusion**

### 3.4 投稿目标（按截止时间排序）

| 目标 | 截止日期 | 类型 | 适合度 | 备注 |
|------|---------|------|--------|------|
| **arXiv 预印本** | 随时 | preprint | ⭐⭐⭐⭐⭐ | 先占坑，被 survey 引用 |
| **NeurIPS 2026 主会** | 摘要 5/4, 全文 5/6 | 顶会 | ⭐⭐⭐ | 难度高，但 systems 类 paper 有机会 |
| **NeurIPS 2026 Datasets & Benchmarks** | ~5月 | 数据集/基准 | ⭐⭐⭐ | 如果做了 ASM benchmark 数据集 |
| **NeurIPS 2026 Workshop** | ~6-8月 | workshop | ⭐⭐⭐⭐ | 门槛较低，很适合 position paper |
| **IJCAI 2026 Workshop** | 看具体 workshop | workshop | ⭐⭐⭐⭐ | 8/15-17 Bremen，"Agentic & Multi-Agent Systems" |
| **AAAI 2027** | ~8月 | 顶会 | ⭐⭐⭐ | 如果 NeurIPS 没中可以转投 |
| **AAMAS 2027** | ~10月 | 多 agent 顶会 | ⭐⭐⭐⭐⭐ | 最对口的顶会 |

### 3.5 学术 + 毕业论文的结合

你的毕业论文目前还在"结构确认"阶段。如果论文选题还有调整空间，ASM 方向可以直接作为毕业论文题目或其中一章：

- **选题角度 A**：多 Agent 系统中的服务选择优化（偏 CS）
- **选题角度 B**：AI Agent 经济体中的标准化协议设计（偏系统/工程）
- **选题角度 C**：基于结构化元数据的自动化服务推荐（偏信息检索/推荐系统）

> ⚠️ 这取决于你的导师方向和学位要求，需要你自己判断

---

## 四、详细执行计划（4月–8月）

### Phase 0: 社区首发 + 论文调研（4/2 – 4/13）

> 策略：先研究、边做边估时间，不急上工程。主线目标是 **5/26 Anthropic AI Hackathon 展示完全体**。

**周四 4/3（今天）✅**
- [x] MCP Discord `#working-group-ideation` 发帖（内容见附录 A）
- [x] 收到首条互动回复（signed receipts interop，见附录 A 互动记录）

**周五 4/4**
- [ ] lablab.ai 确认注册状态（已注册平台，确认 Anthropic AI Hackathon 可报名）
- [ ] 回复 Discord signed receipts 帖子（跟进 doc exchange）

**周末 4/5-6 — 调研日（半天深度块）**

上午（3h）：读 3 篇核心论文
- [ ] [A Survey of AI Agent Protocols](https://arxiv.org/abs/2504.16736)（30min，重点看 gap analysis）
- [ ] [Agent-as-a-Service / AaaS-AN](https://arxiv.org/abs/2505.08446)（30min，最近竞品，搞清区别）
- [ ] [MCP Landscape & Security](https://arxiv.org/abs/2503.23278)（30min，引用其 MCP 生态数据）
- [ ] 整理：ASM vs 已有工作的差异化表格（用于论文 Related Work + Discord 回复）
- [ ] 估算：完成 MVP demo 需要多少小时（schema 导出 / manifests / scorer / MCP Server）

下午（可选，看精力）：
- [ ] 从调研文档导出正式 `schema.json`
- [ ] 写 3 个 `.asm.json` manifest（Claude Sonnet 4 / FLUX 1.1 Pro / Veo 3.1，数据已有）

### Phase 1: 研究深化 + MVP 逐步推进（4/7 – 4/27，3周）

> 不赶，工作日每晚能做就做 30-60 分钟，周末集中半天。边做边评估节奏。

**工程线（按模块拆，不绑定具体日期）：**
- [ ] `schema.json` 正式版导出
- [ ] 3 个 `.asm.json` manifest
- [ ] `score()` 函数：输入偏好 → 归一化 → 加权排序 → 推荐 + 理由
- [ ] registry MCP Server 骨架（提供 ASM 数据查询接口）
- [ ] e2e demo 跑通（"我要最便宜图像生成" → 输出 FLUX + 理由）
- [ ] GitHub 开源 `asm-spec` repo

**学术线（并行）：**
- [ ] 论文 Introduction + Problem Formulation 初稿（~2页）
- [ ] Related Work 差异化表格完善
- [ ] 决定是否冲 NeurIPS 2026（摘要 5/4，全文 5/6）→ 如果时间不够就放弃顶会，走 arXiv + workshop

**社区线：**
- [ ] 持续回复 Discord 讨论
- [ ] 如果 signed receipts 合作推进，探索联合写 paper
- [ ] GitHub Discussion 发到 modelcontextprotocol/specification

### Phase 2: 黑客松冲刺（4/28 – 5/26）

> 目标：5/26 Anthropic AI Hackathon 开赛时，ASM 已有**完全体 demo** 可展示。

**5月第1周（5/4-5/6）：**
- [ ] NeurIPS 决策点：冲 or 放弃（如冲则摘要 5/4，全文 5/6）
- [ ] 无论是否冲顶会，arXiv 预印本此时应该能发

**5月第2-3周（5/7-5/18）：**
- [ ] demo 完善：edge case、UI/UX、演示流程打磨
- [ ] 录 demo 视频 / GIF
- [ ] 准备 pitch 文案（英文）
- [ ] X/Twitter thread + 小红书同步发布

**5月第4周（5/19-5/25）：赛前最终准备**
- [ ] Anthropic AI Hackathon 报名确认
- [ ] 提交材料 checklist
- [ ] 3 分钟 pitch 彩排

**5/26 – 6/2 🏆 Anthropic AI Hackathon**
- [ ] 参赛作品：**ASM** — MCP 扩展协议 + Registry MCP Server + 偏好函数 + e2e demo
- [ ] 赛后写复盘博客（中英双语）

### Phase 3: 长线（6月–8月）

- [ ] arXiv 预印本发布（如果还没发）
- [ ] SEP PR 正式提交到 MCP specification 仓库
- [ ] 关注 NeurIPS/IJCAI workshop CFP，投 workshop paper
- [ ] 8月参加 Global MCP Hackathon（$25K+）
- [ ] 持续维护 GitHub repo + 吸引社区贡献者

---

## 附录 A：MCP Discord 发帖内容

> 发布位置：MCP Discord → `#working-group-ideation`
> 发布前：先搜频道历史确认无重复话题
> 语气：请教 + 分享，不是"我要推标准"

```
🆕 Proposal: Service Economics Layer — Agent Service Manifest (ASM)

**Problem**

MCP tells agents what a tool *can do*. AP2 tells agents how to *pay safely*.
But nothing tells agents what a service *is worth* — pricing, quality, latency, reliability.

When an agent faces 3 subtitle services at different price/quality/speed tradeoffs, it has zero structured data to choose. It's blind selection regardless of model intelligence.

**Proposal**

Agent Service Manifest (ASM) — a lightweight JSON Schema extension to MCP ToolAnnotations (`x-asm` namespace) that lets providers declare:

- **Pricing** — 12 billing dimensions (per-token, per-image, per-second, tiered, conditional)
- **Quality** — third-party benchmark scores + self-reported metrics
- **SLA** — latency p50/p99, throughput, uptime, rate limits
- **Payment** — supported methods (api_key, stripe, ap2)

ASM is NOT a payment protocol. It's the **pre-payment decision layer** — making service value computable, comparable, and automatically actionable.

**Design principles**
- Composable, not category-specific (aligns with MCP design philosophy)
- All fields optional — providers expose what they can
- `extensions` namespace for category-specific data (no core schema pollution)
- Zero breaking changes — clients that don't support ASM simply ignore `x-asm`

**What I've built so far**
- Schema v0.2 (JSON Schema, 5 top-level modules)
- 18-category taxonomy covering LLM/vision/video/audio/code/data/infra
- 3 real-world demos: Claude Sonnet 4, FLUX 1.1 Pro, Google Veo 3.1
- Minimal scoring function: user preferences → ranked service list + reasoning

**One-liner**
> "OpenAPI describes what a service can do. ASM describes what a service is worth."

**Questions for the community**
1. Does this overlap with any existing WG work I should know about?
2. Would a working demo (MCP Server serving ASM data → agent auto-selecting) be useful for discussion?
3. Is `x-asm` the right namespace approach, or should this go deeper into the spec?

Happy to share the full schema, demo code, or a short writeup. Looking forward to feedback 🙏
```

### 发帖后实际互动记录

**2026-04-03 回复 #1** — 来自做 IETF signed receipts 的开发者

> 对方说："ASM for service economics and signed execution receipts for audit trails are complementary layers. I built an IETF draft for portable signed receipts (draft-farley-acta-signed-receipts-01) that could pair with ASM: the manifest declares service quality, the receipt proves what actually happened."

**互补关系**：
```
ASM = 事前声明（服务声称自己值多少）
Signed Receipts = 事后证明（服务实际交付了什么）
→ 对比两者 = 信任分数（provider 是否兑现承诺）
```

**已回复要点**：
1. 用 1-2-3-4 流程展示 ASM declare → agent select → service execute → receipt prove 的完整链路
2. 提出 3 个具体 interop 问题：ASM 加 `receipt_endpoint` 字段？receipt 引用 ASM manifest version？receipt 数据反哺质量指标？
3. 主动提供 schema + demo，提议 async doc exchange 或 call

**后续跟进**：
- [ ] 如果对方回复，优先推进 doc exchange（把 ASM schema 发给他看）
- [ ] 探索联合写 paper 的可能性（ASM + Receipts = 完整的 agent 服务信任体系）
- [ ] 在 ASM schema 中预埋 `receipt_endpoint` 和 `verification` 相关字段

**相关 IETF 工作**（调研补充）：
- [Agent Audit Trail (AAT)](https://datatracker.ietf.org/doc/draft-sharif-agent-audit-trail/) — IETF 标准化的 agent 审计日志格式
- [COSE Receipts](https://datatracker.ietf.org/doc/draft-ietf-cose-merkle-tree-proofs/) — 密码学签名收据，Merkle tree 验证
- 博客参考：[Receipts Are the New Reputation](https://jaxdunfee.com/blog/receipts-are-the-new-reputation-building-trust-infrastructure-for-ai-agents)

---

### 发帖后准备好的回复弹药

| 可能的质疑 | 回复要点 |
|-----------|---------|
| "这和 OpenRouter 有什么区别？" | OpenRouter 路由模型，ASM 描述任意服务；OpenRouter 是封闭平台，ASM 是开放协议 |
| "和 AaaS-AN 有什么区别？" | AaaS-AN 侧重 agent 组织协作（RGPS），ASM 侧重服务经济属性的标准化描述 |
| "provider 会虚报质量怎么办？" | ASM 区分 self_reported vs 第三方 benchmark，并预留 leaderboard_rank 字段引用公开排行 |
| "为什么不直接在 MCP ToolAnnotations 加字段？" | ToolAnnotations 设计为 hints（不可信），ASM 需要更丰富的结构；用 x-asm 命名空间零破坏 |
| "这需要 provider 额外工作" | 所有字段可选，最小版本只需 3 个必填字段（asm_version, service_id, taxonomy） |

---

## 五、核心资源链接

| 资源 | 链接 |
|------|------|
| MCP Discord | https://discord.com/invite/model-context-protocol-1312302100125843476 |
| MCP CWG Working Groups | https://github.com/modelcontextprotocol-community/working-groups |
| MCP Specification Repo | https://github.com/modelcontextprotocol/specification |
| MCP 2026 Roadmap | http://blog.modelcontextprotocol.io/posts/2026-mcp-roadmap/ |
| AAIF (Linux Foundation) | https://aaif.io/ |
| Agentic Commerce Hackathon | https://lablab.ai/event/agentic-commerce-on-arc |
| Global MCP Hackathon | https://globalmcphackathon.com |
| MCP Hackathon 目录 | https://www.mcphackathon.com/ |
| NeurIPS 2026 CFP | https://neurips.cc/Conferences/2026/CallForPapers |
| NeurIPS 2026 Dates | https://neurips.cc/Conferences/2026/Dates |
| IJCAI 2026 | https://2026.ijcai.org/ |
| Agent Protocol Survey | https://arxiv.org/abs/2504.16736 |
| AaaS-AN (最近竞品) | https://arxiv.org/abs/2505.08446 |
| AI Deadlines 汇总 | http://aideadlines.org/ |
