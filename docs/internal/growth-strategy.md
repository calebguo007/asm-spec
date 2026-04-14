# ASM 增长策略 & 技术方向

> 更新日期：2026-04-10

---

## 一、五个方向 + 可行性分析

### 1. 自动化 Manifest 生成工具

**问题**：手动写 manifest 不 scale。14 个服务花了几小时，市场上有几千个。
**方案**：写一个爬虫/解析器，从定价页面 + API 文档 + 公开 benchmark 自动生成 .asm.json。

```
输入：服务商的 pricing page URL + API docs URL
输出：.asm.json 草稿（标记为 self_reported: false, auto_generated: true）
```

**实现路径**：
- Phase 1: Claude + 结构化 prompt → 给它一个定价页面，输出 manifest JSON
- Phase 2: 写一个 CLI 工具 `asm generate --url https://openai.com/pricing`
- Phase 3: 定时跑（cron），检测定价变化自动更新 manifest

**难点**：
- 定价页面格式各不相同，解析需要 LLM
- 需要人工 review（自动生成的可能有错）
- 价格变动频繁，需要 diff 检测

**优先级**：P1 — 直接解决冷启动，也是一个很好的 demo 项目

---

### 2. Agent 框架集成（LangChain / CrewAI / AutoGen）

**问题**：开发者不会主动去查 ASM manifest。需要在他们已经用的工具里内置。
**方案**：做插件/中间件，agent 调工具时自动经过 ASM 选择层。

```python
# 现在的 LangChain
llm = ChatOpenAI(model="gpt-4o")

# 接入 ASM 后
llm = ASMRouter(
    taxonomy="ai.llm.chat",
    preferences={"cost": 0.5, "quality": 0.3, "speed": 0.2},
    # 自动从 registry 选最优 LLM
)
```

**实现路径**：
- Phase 1: 写一个 Python 包 `asm-langchain`，wrap LangChain 的 LLM/Tool 选择
- Phase 2: 提 PR 到 LangChain 官方仓库（或作为 community integration）
- Phase 3: 同样做 CrewAI 和 AutoGen 的版本

**难点**：
- 每个框架的抽象层不一样，需要分别适配
- 需要框架维护者接受 PR（或者先做独立包）
- 实时选择 vs 启动时选择的 trade-off

**优先级**：P1 — 这是 ASM 被采用的核心路径。没有集成就没有用户。

---

### 3. 真实 A/B 测试

**问题**：现在所有数据都是模拟的。需要真实数据证明 ASM 的价值。
**方案**：找一个真实的 multi-agent 工作流，跑有/无 ASM 两个版本，对比。

**实验设计**：
```
工作流：100 篇文章 → 翻译 + 配图 + 生成摘要
对照组：固定用 GPT-4o + DALL-E 3（盲选）
实验组：用 ASM scorer 自动选择每一步的最优服务

测量指标：
- 总成本差异
- 总耗时差异
- 输出质量（人工评分或 LLM-as-judge）
- 决策可解释性
```

**产出**：一张表 + 一段话，放论文 Evaluation 章节。
> "在 100 个翻译+配图任务中，ASM 组总成本降低 47%，质量评分持平（4.2 vs 4.1/5），平均延迟增加 12%（因为选了更便宜但稍慢的服务）。"

**难点**：
- 需要真实 API key 和预算
- 需要设计公平的对比（对照组不能太蠢）
- 耗时可能几天

**优先级**：P1 — 论文和推广都需要这个数据。没有真实数据，一切都是空谈。

---

### 4. 争取大玩家背书

**问题**：ASM 目前只有你一个人在推。需要至少一个有影响力的参与者。
**方案**：让一个大厂或知名项目官方发布 .asm.json。

**潜在目标（按可行性排序）**：

| 目标 | 可行性 | 路径 |
|------|--------|------|
| **Scopeblind / Agent Receipts** | 高 | 已在合作，他们可以在自己的 repo 里引用 ASM |
| **Replicate** | 中 | 他们是 model marketplace，ASM 对他们有利（展示性价比） |
| **Anthropic Developer Relations** | 中 | 通过 MCP Discord + SEP #718 建立关系 |
| **LangChain** | 中 | 通过集成插件 PR 建立关系 |
| **OpenAI / Google** | 低 | 太大，不会主动参与早期标准 |

**最现实的路径**：
1. Scopeblind 在 field alignment doc 里正式引用 ASM → 第一个外部认可
2. 做 LangChain 集成，提 PR → 进入 LangChain 生态 = 几万开发者能看到
3. 找 Replicate 的 DevRel 聊 → 他们的模型全在 API 后面，ASM manifest 对他们是现成的产品页补充

**优先级**：P2 — 需要先有集成和真实数据，才有筹码去谈

---

### 5. Registry 去中心化

**问题**：中心化 registry 有单点故障和信任问题（谁控制 registry 谁就有权力）。
**方案**：让每个服务商在自己域名下发布 manifest。

**当前设计（已有）**：
```
GET https://api.anthropic.com/.well-known/asm
→ 返回 Anthropic 所有服务的 manifest 列表
```

**缺的是发现机制**——agent 怎么知道去哪些域名找 .well-known/asm？

| 方案 | 优点 | 缺点 |
|------|------|------|
| **DNS TXT 记录** | 标准、去中心化 | 更新慢，不适合动态数据 |
| **DNS-SD (Service Discovery)** | 专门为服务发现设计 | 复杂，需要 mDNS 支持 |
| **链上注册（ENS/IPNS）** | 不可篡改 | 太慢太贵，用户不熟悉 |
| **聚合 registry + .well-known 并存** | 简单实用 | 聚合 registry 还是中心化 |
| **HTTPS Well-Known URI + 爬虫索引** | 跟搜索引擎一样 | 需要爬虫基础设施 |

**推荐**：**聚合 registry + .well-known 并存**（类似 npm registry + GitHub 的关系）
- 服务商在自己域名发布 .well-known/asm（权威来源）
- 公共 registry 定期抓取 + 社区贡献（搜索入口）
- Agent 可以选择用公共 registry 或直接查 .well-known

**优先级**：P3 — 现阶段 14 个服务不需要去中心化。等用户量上来再说。

---

## 二、优先级总览

| 优先级 | 方向 | 为什么 |
|--------|------|--------|
| P1 | A/B 测试 | 论文必需，推广必需，没有真实数据一切免谈 |
| P1 | 自动化 manifest 生成 | 解决冷启动，也是一个好 demo |
| P1 | Agent 框架集成 | 没有集成就没有用户 |
| P2 | 大玩家背书 | 需要先有上面三个的成果才有筹码 |
| P3 | Registry 去中心化 | 现在太早，等有规模了再做 |

---

## 三、执行顺序建议

```
Phase 1（近期）：
  - A/B 测试设计 + 执行 → 产出论文 evaluation 数据
  - manifest 生成工具 MVP → 用 Claude API 实现

Phase 2（有数据后）：
  - LangChain 集成插件 → 提 PR
  - 带着数据和集成去找 Replicate / Anthropic DevRel

Phase 3（有用户后）：
  - .well-known/asm 标准化 → 写 spec
  - 公共 registry 服务上线
```
