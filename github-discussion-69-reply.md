# GitHub Discussion #69 回复草稿

> 目标：在 MCP Service Discovery 讨论中引入 ASM，定位为 "value metadata layer"
> 链接：https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/69
> 语气：建设性参与，不是推销

---

## 回复内容（直接复制粘贴）

```
Great thread — service discovery is clearly a critical next step for MCP. I want to add a dimension that hasn't been discussed yet: **value metadata**.

### The gap

The proposals here focus on *capability discovery* — what a server can do, how to authenticate, what tools/resources it exposes. This is essential. But when an agent faces multiple servers that offer the same capability (e.g., three different image generation APIs), it still can't make an informed choice because there's no structured data about:

- **Pricing** — How much does it cost? Per-token? Per-image? Per-second? Tiered?
- **Quality** — How good is the output? What benchmark scores? Self-reported or third-party verified?
- **SLA** — What's the p50/p99 latency? Uptime? Rate limits?
- **Payment** — API key? Stripe? AP2?

Without this, discovery only answers "what exists" — not "what's worth using."

### What I've been working on

I've been designing **Agent Service Manifest (ASM)** — a lightweight JSON Schema extension that lets providers declare standardized value descriptors alongside their MCP tool definitions. Think of it as: `.well-known/mcp` tells you *what a server can do*, ASM tells you *what a server is worth*.

**Key design decisions (aligned with MCP principles):**
- **Composable, not category-specific** — one schema covers LLM, image gen, video gen, TTS, GPU compute, etc.
- **All fields optional** — providers expose what they can. Only 3 required fields: `asm_version`, `service_id`, `taxonomy`
- **`extensions` namespace** — category-specific data (like `max_resolution` for image gen) lives in extensions, keeping the core schema stable
- **Zero breaking changes** — can ship as `x-asm` annotations that non-supporting clients simply ignore

**What exists so far:**
- Schema v0.2 (JSON Schema, 5 top-level modules: pricing, quality, SLA, payment, extensions)
- 18-category taxonomy covering LLM/vision/video/audio/code/data/infra
- 3 real-world demos with actual pricing data: Claude Sonnet 4, FLUX 1.1 Pro, Google Veo 3.1
- Minimal scoring function: user preferences → normalized scores → ranked list + reasoning

**Real-world validation:** AWS recently shipped an [AWS Marketplace MCP Server](https://docs.aws.amazon.com/marketplace/latest/APIReference/marketplace-mcp-server.html) that does product comparison and recommendation through MCP. This proves the demand — but it's a closed, platform-locked implementation. ASM aims to provide the same capability as an open standard.

### How this connects to service discovery

I think the discovery flow should be:

```
1. .well-known/mcp → capability metadata (what the server can do)
2. x-asm annotations → value metadata (what the server is worth)
3. Agent preference function → ranked selection + reasoning
4. AP2 / payment → execute transaction
```

Step 1 is what this thread is designing. Step 2 is the gap ASM fills. Steps 3-4 complete the autonomous service selection loop.

### Questions for the community

1. Does adding value metadata (pricing/quality/SLA) feel like it belongs in the service discovery mechanism, or should it be a separate layer?
2. Would it make sense to define a standard `x-asm` namespace in ToolAnnotations, or is a separate metadata endpoint better?
3. I'm also in conversation with the [Agent Receipts](https://github.com/agent-receipts/ar) team about pairing ASM (pre-service declaration) with signed receipts (post-service verification) for a complete trust loop. Would this kind of interop be interesting to the MCP community?

Happy to share the full schema, demo code, or a detailed writeup. Here's the [schema overview and 3 cross-category demos](link-to-your-repo-or-doc) if anyone wants to dig in.
```

---

## 操作步骤

### 第一步：打开链接
浏览器打开：https://github.com/modelcontextprotocol/modelcontextprotocol/discussions/69

### 第二步：登录 GitHub
确保你用自己的 GitHub 账号登录（和你 Discord 同一个身份，保持一致性）。

### 第三步：滚动到底部评论框
页面最下面有一个 "Leave a comment" 的文本框。

### 第四步：粘贴内容
把上面 ``` 之间的内容完整复制粘贴进去。

### 第五步：检查并修改一个链接
回复最后一句有一个 `(link-to-your-repo-or-doc)` — 你需要替换成：
- 如果你已经有 GitHub repo：用 repo 链接
- 如果还没有：先不放链接，改成 "Happy to share the full schema and demo code — DM me or reply here."

### 第六步：预览
点击 "Preview" 标签，确认 Markdown 渲染正确（特别是代码块和列表）。

### 第七步：发布
点击 "Comment" 按钮发布。

### 第八步：后续跟进
- 发布后，在你的调研文档里记录链接和时间
- 关注是否有维护者（jspahrsummers）或其他人回复
- 如果有人问 schema 细节，准备好把 `调研文档.md` 第五章的 JSON Schema 贴出来

---

## 注意事项

1. **不要 @任何人** — 第一次发帖，先建设性参与，不要显得 pushy
2. **提到 AWS Marketplace MCP Server** — 这是最强的"需求验证"论据，比自己说"这很重要"有力 100 倍
3. **提到 Agent Receipts 合作** — 显示你不是孤立的，已经有跨项目合作在推进
4. **结尾问 3 个问题** — 邀请社区讨论，而不是单方面宣布
