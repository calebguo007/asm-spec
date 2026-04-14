# ASM 维度扩展 & 商业模式思考

> 更新日期：2026-04-10
> 触发：关于"维度是否够用"和"大厂激励问题"的讨论

---

## 一、当前维度（v0.3 scorer 使用的 4 个）

```
cost        → 多少钱
quality     → 多好（benchmark 分数）
speed       → 多快（延迟）
reliability → 多稳（uptime）
```

## 二、缺失的用户维度

### 体验类

| 维度 | 含义 | 例子 |
|------|------|------|
| **输出可控性** | 用户能多大程度控制输出 | system prompt、temperature、风格参数、seed 固定 |
| **容错友好度** | 出错时的体验 | 错误信息是否清晰、是否有 retry 建议、rate limit 是硬切还是降级 |
| **集成复杂度** | 接入需要多少工作量 | SDK 语言支持数、API 设计是否 RESTful、鉴权复杂度 |
| **文档质量** | 文档是否够用 | 有无 playground、示例代码完整度、更新频率 |
| **输出一致性** | 同样输入是否得到相似输出 | 对需要可复现结果的场景很重要（科研、合规） |
| **多模态灵活性** | 一个 API 能处理多少种输入输出组合 | Claude 能同时处理文本+图片，有些只能纯文本 |

### 经济类

| 维度 | 含义 | 例子 |
|------|------|------|
| **总拥有成本 (TCO)** | 不只是单价，还有隐性成本 | API key 管理、SDK 维护、错误重试的额外消耗 |
| **成本可预测性** | 账单波动大不大 | 固定价 vs 按量计费 vs GPU 时长（波动极大） |
| **阶梯优惠断点** | 用多少量才能触发下一档降价 | "月消费 $100 后单价降 30%" — 这影响长期选择 |
| **承诺折扣** | 预付/包年是否更便宜 | Reserved instance 模式 vs On-demand |
| **免费额度慷慨度** | 免费层能撑多久 | Gemini 免费层 vs OpenAI 无免费层 — 对小团队影响巨大 |
| **退出成本** | 切换到其他服务的代价 | API 兼容性、数据导出难度、fine-tune 模型是否可迁移 |
| **账单透明度** | 能否精确审计每笔消费 | 有些服务只给月度总额，有些给逐请求明细 |
| **退款/信用政策** | 服务故障时是否补偿 | SLA breach 时自动 credit vs 需要人工申请 |

## 三、哪些值得加到 schema

### v0.4 优先加（高频需求）

```json
"execution_modes": {
  "sync": { "latency_p50": "800ms", "cost_multiplier": 1.0 },
  "batch": { "latency_p50": "30min", "cost_multiplier": 0.5 }
},
"cost_predictability": "fixed | variable | estimated",
"exit_cost": "low | medium | high",
"free_tier_generosity": 0.8
```

### 放 extensions（行业特定）

```json
"extensions": {
  "developer_experience": {
    "sdk_languages": ["python", "typescript", "go"],
    "has_playground": true,
    "api_style": "REST",
    "doc_quality_score": 0.9
  },
  "privacy": {
    "data_retention": "none",
    "gdpr_compliant": true,
    "training_opt_out": true
  },
  "compliance": {
    "certifications": ["SOC2", "ISO27001"]
  },
  "economics": {
    "volume_discount_threshold": 100,
    "commitment_discount": 0.3,
    "refund_policy": "automatic_credit"
  }
}
```

### 不该加到 schema（太主观）

- 文档质量：因人而异
- 社区活跃度：变化太快，manifest 跟不上
- "好不好用"：不可量化

---

## 四、ASM 额外 Token 消耗的优化策略

### 问题
每次调 ASM 选服务消耗约 3000-5000 token。如果 agent 每个小任务都跑一遍，成本会叠加。

### 解决方案

**1. 本地缓存（ttl 机制，已有）**
```
manifest.ttl = 3600  → 1 小时内用缓存，不重新查
```

**2. 预计算 + 持久化**
```
agent 启动时跑一次全量打分 → 结果存本地 JSON
运行时直接查本地结果 → 0 token
ttl 到期后后台刷新 → 不阻塞主流程
```

**3. 决策阈值**
```
if estimated_task_cost < $0.01:
    skip ASM, use default service    # 不值得选
else:
    run ASM scorer                   # 值得选
```

**4. 分层缓存**
```
L1: 内存缓存（本次会话内有效）
L2: 本地文件缓存（跨会话，ttl 控制）
L3: Registry 查询（缓存失效时）
```

---

## 五、大厂激励问题 & 商业模式

### 核心矛盾

> "希望大厂买 ASM，让大厂定期跑测评。但大厂自己的服务拉了咋办？"

这是一个 **利益冲突问题**：

- 大厂作为 **服务提供商**：不希望自己的弱项被暴露
- 大厂作为 **服务消费者**（选择第三方工具时）：希望有准确的对比数据

### 谁会用 ASM？

| 角色 | 动机 | 会不会用 |
|------|------|---------|
| **Agent 框架开发者**（LangChain, CrewAI 等） | 让 agent 自动选最优服务，提升框架竞争力 | ✅ 会 |
| **中小 AI 服务商** | 跟大厂比不了品牌，但可以在 ASM 里展示性价比优势 | ✅ 会（对他们有利） |
| **企业采购** | 需要结构化对比来做采购决策 | ✅ 会 |
| **大厂作为消费者** | 选择第三方工具（如选 TTS 服务） | ✅ 会（在非竞争品类） |
| **大厂作为提供商** | 公开自己的弱项？ | ❌ 不会主动，但如果 ASM 成了标准，不参与 = 被边缘化 |

### 关键洞察

**大厂不需要"买" ASM。ASM 是开放协议，谁都可以用。**

真正的商业模式不是卖协议，是卖 **基于协议的增值服务**：

| 服务 | 收费模式 | 谁买 |
|------|---------|------|
| **托管 Registry**（高可用、全球分发） | SaaS 订阅 | Agent 框架公司 |
| **独立测评报告**（ASM Benchmark） | 按报告收费 | 企业采购部门 |
| **合规认证**（"ASM Verified" 标签） | 按服务收费 | 想证明自己不夸大的服务商 |
| **实时监控**（持续跑 receipt，更新 trust delta） | SaaS 订阅 | 需要持续监控 SLA 的企业 |

### 大厂博弈分析

大厂的算盘：
1. **如果 ASM 没人用** → 忽略它
2. **如果 ASM 成了标准** → 必须参与，否则 agent 选不到你的服务
3. **如果参与但自己拉了** → 两个选择：(a) 改善服务 (b) 试图影响 ASM 标准

**这正好是 ASM 的护城河：协议是开源的，数据是社区维护的，receipt 是数学验证的。** 大厂可以不写 manifest，但社区可以替他们写（基于公开数据）。大厂可以不喜欢 trust delta，但 receipt 签名不会骗人。

### 最好的结局

ASM 不需要大厂"买"。它需要：
1. Agent 框架内置 ASM（让 LangChain/CrewAI 默认读 ASM manifest）
2. 社区维护 manifest（像 Wikipedia 一样众包）
3. Receipt 自动积累 trust delta（用的人越多数据越准）

大厂的参与是结果，不是前提。

---

## 六、论文可用的素材

以上讨论直接对应论文的几个章节：

| 内容 | 论文章节 |
|------|---------|
| 4 维度 vs 扩展维度 | Section 3: Schema Design → 解释为什么选这 4 个 |
| extensions namespace | Section 3: 可扩展性设计 |
| token 消耗分析 | Section 6: Discussion → Overhead Analysis |
| 缓存策略 | Section 4: System Design → Caching |
| 大厂激励问题 | Section 7: Limitations → Incentive Alignment |
| 商业模式 | Section 8: Future Work |
