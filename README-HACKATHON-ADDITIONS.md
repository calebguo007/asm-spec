# README 补充内容（比赛用）

> 以下内容建议在提交前合并到 README.md 中。
> 位置：在 "Quick Start" section 之后，"How It Works" 之前。

---

## 🆕 Nanopayments Integration (Circle × Arc)

ASM integrates with [Circle Nanopayments](https://developers.circle.com/gateway/nanopayments) via the [x402 protocol](https://x402.org) to enable **per-API-call payments** for service scoring.

### Why Nanopayments?

| Traditional Gas Model | Circle Nanopayments on Arc |
|---|---|
| Gas per tx: $0.01 – $0.50 | Batched: ~$0.005 per tx |
| Gas > payment amount ❌ | Economically viable ✅ |
| Volatile gas token | Stable USDC |
| Human wallet confirmation | Fully autonomous agent flow |

### Quick Start (Nanopayments)

```bash
# 1. Start everything (Registry + Payment Server)
cd payments
npm install
npm run dev:all

# 2. Open the Dashboard
open http://localhost:4402/api/dashboard

# 3. Run the E2E Demo (6 agents, 50+ transactions)
npm run demo
```

### Payment Endpoints

| Endpoint | Price | Description |
|---|---|---|
| `POST /api/score` | $0.005 USDC | TOPSIS multi-criteria scoring |
| `POST /api/query` | $0.002 USDC | Filtered service query |
| `GET /api/services` | Free | Service discovery |
| `GET /api/dashboard` | Free | Real-time transaction dashboard |
| `GET /api/trust` | Free | Trust scores |

### Architecture

```
Agent receives task
    │
    ▼
ASM Registry Query (free)
    → Returns matching manifests
    │
    ▼
TOPSIS Scoring ($0.005 USDC via x402)
    → Circle Gateway → Arc settlement
    → Returns ranked list + payment receipt
    │
    ▼
Service Execution
    → Agent calls selected service
    │
    ▼
Signed Receipt + Trust Update
    → trust_delta = |declared - actual| / declared
    → Influences future rankings
```

---

> **Note**: This section documents the Circle Nanopayments integration built for the [Agentic Economy on Arc](https://lablab.ai/ai-hackathons/nano-payments-arc) hackathon (April 2026).
