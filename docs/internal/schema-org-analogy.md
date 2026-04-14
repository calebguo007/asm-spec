# ASM ↔ Schema.org 类比分析

> 更新日期：2026-04-10
> 用途：论文 Motivation、Show HN、投资人 pitch、社区讲故事

---

## 核心类比

```
Schema.org 之于搜索引擎 = ASM 之于 AI Agent

Schema.org：让网页内容对搜索引擎可计算
ASM：让 AI 服务的价值对 Agent 可计算
```

两者解决的是同一类问题：**信息存在但不可计算**。

| | Schema.org | ASM |
|---|---|---|
| **问题** | 网页有内容但搜索引擎读不懂结构 | AI 服务有定价/质量但 agent 无法比较 |
| **解法** | 在 HTML 里嵌入结构化标记 | 用 JSON manifest 描述服务价值 |
| **受益者** | 搜索引擎（更准的索引）+ 网站（更好的排名） | Agent（更优的选择）+ 服务商（更多曝光） |
| **数据格式** | JSON-LD / Microdata | .asm.json |
| **发布方式** | 嵌入网页 HTML | `.well-known/asm` 或独立文件 |
| **发现机制** | Google 爬虫抓取 | Registry 查询 / 爬虫索引 |

---

## Schema.org 成功的四个要素 → ASM 的对照

### 1. 不可拒绝的激励

**Schema.org**：加了结构化标记 → 搜索结果有 rich snippet（星级、价格、图片）→ 点击率提升 30-50%。不加 → 只有纯文本，被挤到视觉盲区。

**ASM 的等价激励**：有 manifest 的服务 → agent 能发现和选择。没有 manifest 的服务 → agent 不知道你存在。当足够多的 agent 依赖 ASM 做选择时，不发 manifest = 隐形。

**差距**：Schema.org 第一天就有 Google 这个"不可拒绝"的分发方。ASM 还没有等价的分发方。最接近的路径是 LangChain 集成——当 LangChain 默认用 ASM 选服务时，不发 manifest 的服务商就开始慌了。

### 2. 默认集成（零摩擦采用）

**Schema.org**：WordPress、Shopify、Wix 的模板默认生成 Schema.org 标记。站长不需要学 JSON-LD，CMS 自动处理。

**ASM 的等价路径**：
- 自动 manifest 生成工具（从定价页自动生成 .asm.json）
- Agent 框架内置（LangChain/CrewAI 默认读 ASM）
- AI 服务商的 dashboard 一键导出 manifest

**差距**：ASM 还没有任何"零摩擦"的生成和集成路径。这是 P1 优先级。

### 3. 多方参与的治理

**Schema.org**：由 Google、Microsoft、Yahoo、Yandex 联合发起。不是一家的标准，是行业共识。

**ASM 当前**：只有你一个人。Scopeblind 是第一个外部参与者，#general 的 enterprise registry 人是第二个。

**需要做的**：
- Scopeblind 的 field alignment doc = 第一个外部 spec 引用
- LangChain PR = 第一个框架认可
- MCP SEP #718 = 第一个标准化渠道
- 如果 working group 成立 = 第一个治理结构

### 4. 渐进式采用（最小可用）

**Schema.org**：可以只标记一个字段（比如只加 `name`），不需要全部标记完。

**ASM**：只需要 3 个必填字段 `asm_version`, `service_id`, `taxonomy`。这已经做到了。

**这是 ASM 的优势**——最小 manifest 只有 3 行，采用门槛极低。

---

## Schema.org 的时间线 → ASM 可以参考的节奏

| Schema.org | 时间 | ASM 等价事件 |
|---|---|---|
| Google 内部提案 | 2010 | Yi Guo 设计 ASM（2026-03） |
| 4 家搜索引擎联合发布 | 2011-06 | ❌ 还没有（目标：找到 1-2 个合作方） |
| WordPress 默认支持 | 2012 | ❌ 还没有（目标：LangChain 集成） |
| 50% 的网页使用 | 2015 | ❌ 远期目标 |
| 成为事实标准 | 2018+ | ❌ 远期目标 |

Schema.org 从提案到默认集成用了约 2 年。ASM 如果能在 2026 年内完成 LangChain 集成 + 1 个大厂背书，节奏就不慢。

---

## "谁是 ASM 的 Google"

不一定是一家公司。可能是：

| 候选 | 为什么 | 可能性 |
|------|--------|--------|
| **LangChain** | 最大的 agent 框架，内置 ASM = 几十万开发者直接用 | 中高 |
| **Anthropic** | MCP 的创建者，ASM 是 MCP 的经济层扩展 | 中 |
| **一个 AI marketplace**（Replicate/Together） | ASM 直接解决他们的服务发现问题 | 中 |
| **没有单一"Google"，而是社区驱动** | 类似 RSS、Markdown——没有一家公司推，但够简单所以自然传播 | 有可能 |

**最诚实的答案**：ASM 可能不需要一个"Google"。如果协议够简单（3 个必填字段）、工具够好（自动生成 + 框架集成）、激励够明确（没有 manifest = agent 找不到你），它可以像 Markdown 一样自然传播。

Markdown 没有 Google 推，但它赢了。因为它解决了一个真实问题，而且足够简单。

---

## 论文可用的一句话

> "ASM is to AI agent ecosystems what Schema.org is to search engine ecosystems: a structured, machine-readable metadata format that makes previously uncomputable information computable for autonomous decision-making."

放 Introduction 第一段或 Abstract 里。
