# ASM Manifest 签名方案设计（v0.4 规划）

> 状态：设计草案，未实现
> 更新日期：2026-04-10
> 问题：manifest 数据目前没有防篡改机制。Receipt 有 Ed25519 签名，manifest 没有。

---

## 问题定义

当前 manifest 的信任链是断裂的：

```
服务商 → (未签名的 JSON) → registry → agent
              ↑
         任何人可以改这里
```

三种攻击场景：

1. **中间人篡改**：manifest 从服务商到 agent 的传输过程中被改了（比如降低竞争对手的 quality 分数）
2. **registry 篡改**：registry 运营者偷偷改 manifest 数据（利益冲突）
3. **冒充发布**：有人伪造一个 manifest 声称是 Anthropic 发布的

---

## 设计方案

### 核心思路

复用 Receipt 的签名机制——Ed25519 签名 + 64-char hex 公钥。

### manifest 新增字段（v0.4 schema）

```json
{
  "asm_version": "0.4",
  "service_id": "anthropic/claude-sonnet-4@4.0",
  "taxonomy": "ai.llm.chat",
  
  "...其他字段...",

  "manifest_signature": {
    "signed_at": "2026-04-10T12:00:00Z",
    "signed_by": "anthropic",
    "public_key": "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
    "signature": "7b2e4f...（对 manifest 内容的 Ed25519 签名）",
    "signed_fields": ["service_id", "taxonomy", "pricing", "quality", "sla"]
  }
}
```

### 签名流程

```
1. 服务商构建 manifest JSON（不含 manifest_signature 字段）
2. 将 JSON 序列化为 canonical form（key 排序 + 无空格）
3. 对序列化后的字节串做 Ed25519 签名
4. 将签名 + 公钥 + 元数据写入 manifest_signature 字段
```

### 验证流程

```
1. Agent 拿到 manifest
2. 提取 manifest_signature 字段并暂存
3. 删除 manifest_signature 字段
4. 将剩余 JSON 序列化为 canonical form
5. 用 public_key 验证 signature
6. VALID → manifest 确实由声明的 signed_by 签发
```

### signed_fields 的作用

不是所有字段都需要签名。`display_name` 改了无所谓，但 `pricing` 和 `quality` 改了就是欺诈。
`signed_fields` 声明了哪些字段被签名覆盖，agent 可以判断"关键字段是否可信"。

---

## 三种 manifest 的信任层级

| 层级 | 条件 | Agent 怎么对待 |
|------|------|---------------|
| **L0: 未签名** | 没有 `manifest_signature` | 数据仅供参考，权重最低 |
| **L1: 自签名** | 服务商自己签的（`signed_by` = 服务商自己） | 确认来源真实，但内容可能夸大 |
| **L2: 第三方签名** | 独立测评方签的（`signed_by` = 第三方测评机构） | 最高信任——来源真实 + 内容独立验证 |

这跟 HTTPS 证书的模型类似：
- L0 = HTTP（无保护）
- L1 = 自签名证书（加密但不可信）
- L2 = CA 签发的证书（加密 + 可信）

---

## 跟现有机制的关系

```
manifest_signature → 保证 manifest 没被篡改（事前）
self_reported flag → 透明度标记（声明时）
trust delta        → 检测 manifest 是否夸大（事后）

三者互补，不互相替代。
```

---

## 实现优先级

| 阶段 | 做什么 | 什么时候 |
|------|--------|---------|
| 1 | 在论文 Limitations 里写清楚"manifest 目前无签名" | 写论文时 |
| 2 | v0.4 schema 加 `manifest_signature` 字段定义 | Scopeblind 对接完成后 |
| 3 | 写一个 sign-manifest CLI 工具（Python，生成 Ed25519 签名） | v0.4 开发期 |
| 4 | MCP Server 加签名验证（有签名就验，没签名标记为 L0） | v0.4 开发期 |

---

## 开放问题

1. **canonical JSON 序列化**：用 JSON Canonicalization Scheme (RFC 8785) 还是简单的 key-sort + no-whitespace？
2. **公钥发现**：agent 怎么知道 Anthropic 的公钥是什么？需要 .well-known/asm-keys 端点？还是信任 registry 提供的公钥？
3. **密钥轮换**：服务商换密钥了，旧 manifest 的签名就失效了。需要 key rotation 机制。
4. **多签**：一个 manifest 可以同时有服务商签名和第三方测评签名吗？数组还是嵌套？
