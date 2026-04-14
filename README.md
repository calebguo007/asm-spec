# Agent Service Manifest (ASM)

> **OpenAPI describes what a service *can do*. ASM describes what a service *is worth*.**

ASM is an open protocol that gives AI agents structured, machine-readable data to **evaluate, compare, and automatically select** AI services — covering pricing, quality, SLA, and payment.

```
MCP  → "what a tool can do"          ✅ Solved (Anthropic)
A2A  → "how agents communicate"      ✅ Solved (Google)
AP2  → "how to pay safely"           ✅ Solved (Google)
ASM  → "what a service is worth"     ❌ Nobody — until now
```

**ASM is the missing layer between MCP and AP2.**

---

## Why ASM?

When an agent faces multiple services that can fulfill the same task, it has **zero structured data** to choose:

| Without ASM | With ASM |
|---|---|
| Blind selection (pick cheapest or most famous) | Structured multi-criteria matching |
| 3-10x cost overrun or quality underrun | Optimal cost-quality tradeoff |
| Decisions are non-reproducible | Deterministic, auditable, explainable |
| Model intelligence = 0 at selection step | Full autonomous decision capability |

**This is not a model intelligence problem — it's a data problem.** No matter how smart the model, unstructured pricing pages are uncomputable.

---

## Quick Start

### Run the Demo

```bash
git clone https://github.com/asm-protocol/asm-spec.git
cd asm-spec

# End-to-end demo — pure Python, no dependencies
python3 demo/e2e_demo.py
```

The demo simulates 5 scenarios where an agent selects services across LLM, image generation, video generation, and TTS categories.

### Run the Scorer

```bash
python3 scorer/scorer.py
```

### Start the MCP Server

```bash
cd registry
npm install
npm run build
npm start
```

The MCP server exposes 5 tools: `asm_list`, `asm_get`, `asm_query`, `asm_compare`, `asm_score`.

---

## How It Works

### 1. A service publishes an ASM manifest

```json
{
  "asm_version": "0.2",
  "service_id": "anthropic/claude-sonnet-4@4.0",
  "taxonomy": "ai.llm.chat",
  "display_name": "Claude Sonnet 4",
  "pricing": {
    "billing_dimensions": [
      { "dimension": "input_token",  "unit": "per_1M", "cost_per_unit": 3.00,  "currency": "USD" },
      { "dimension": "output_token", "unit": "per_1M", "cost_per_unit": 15.00, "currency": "USD" }
    ],
    "batch_discount": 0.5
  },
  "quality": {
    "metrics": [{
      "name": "LMSYS_Elo", "score": 1290, "scale": "Elo",
      "benchmark": "LMSYS Chatbot Arena",
      "self_reported": false
    }]
  },
  "sla": {
    "latency_p50": "800ms", "uptime": 0.999,
    "rate_limit": "4000 req/min"
  }
}
```

### 2. An agent queries and scores

```python
from scorer import select_service, Constraints, Preferences

results = select_service(
    manifests,
    constraints=Constraints(min_quality=0.7, max_latency_s=5.0),
    preferences=Preferences(cost=0.5, quality=0.3, speed=0.15, reliability=0.05),
    method="topsis",
)

print(results[0].service.display_name)  # "GPT-4o"
print(results[0].reasoning)             # "GPT-4o scored 0.914 ..."
```

### 3. The full pipeline

```
Agent receives task
    │
    ▼
Task → Taxonomy mapping
    "subtitles" → ai.video.subtitle
    │
    ▼
ASM Registry Query
    GET .well-known/asm?taxonomy=ai.video.subtitle
    → Returns matching service manifests
    │
    ▼
ASM Scorer
    Filter (hard constraints) → TOPSIS (multi-criteria ranking)
    → Ranked list + reasoning
    │
    ▼
Selection + Execution
    Agent calls selected service via MCP
    AP2 handles payment
    Signed Receipt verifies delivery
```

---

## Schema (v0.3)

ASM manifests are JSON documents with **only 3 required fields**:

```json
{
  "asm_version": "0.2",
  "service_id": "anthropic/claude-sonnet-4@4.0",
  "taxonomy": "ai.llm.chat"
}
```

Everything else is optional — services expose what they can:

| Module | What it describes | Key fields |
|---|---|---|
| **pricing** | Cost structure | `billing_dimensions` (12 types), `tiers`, `conditions`, `batch_discount` |
| **quality** | Performance metrics | `metrics` (benchmark + `self_reported` flag), `leaderboard_rank` |
| **sla** | Reliability | `latency_p50/p99`, `uptime`, `rate_limit`, `cold_start`, `regions` |
| **payment** | How to pay | `methods`, `auth_type`, `ap2_endpoint` |
| **extensions** | Category-specific | Namespaced fields (e.g., `llm.supports_vision`, `image_gen.max_resolution`) |

Full schema: [`schema/asm-v0.2.schema.json`](schema/asm-v0.2.schema.json)

### Taxonomy (18 categories)

Hierarchical, prefix-queryable (e.g., `ai.llm.*` returns all LLM services):

```
ai.llm.chat                     ai.audio.tts
ai.llm.completion                ai.audio.stt
ai.llm.embedding                 ai.audio.music
ai.vision.image_generation       ai.code.generation
ai.vision.image_editing          ai.data.extraction
ai.vision.ocr                    ai.data.search
ai.video.generation              infra.compute.gpu
ai.video.subtitle                infra.storage.object
ai.video.editing                 infra.storage.vector
```

---

## What's Included

```
asm-spec/
├── schema/
│   ├── asm-v0.2.schema.json          # JSON Schema (v0.2)
│   └── asm-v0.3.schema.json          # JSON Schema (v0.3: +receipts, verification, ttl)
├── manifests/                         # 70 real-world service manifests
│   ├── anthropic-claude-sonnet-4.asm.json
│   ├── openai-gpt-4o.asm.json
│   ├── google-gemini-2.5-pro.asm.json
│   └── ... (70 services across 47 categories)
├── scorer/
│   ├── scorer.py                      # Filter + TOPSIS + Trust Delta scoring engine
│   └── test_scorer.py                 # Unit tests (golden, io_ratio, cross-language parity)
├── registry/
│   └── src/
│       ├── index.ts                   # MCP Server (5 tools, TOPSIS + Weighted Average)
│       ├── http.ts                    # HTTP API (REST endpoints)
│       ├── test_scorer.ts             # TypeScript unit tests
│       └── test_topsis.ts             # TOPSIS cross-validation
├── experiments/
│   ├── ab_test.py                     # Simulated A/B test (TOPSIS vs Random vs Expensive)
│   ├── real_ab_test.py                # Real API A/B test (live LLM calls)
│   ├── analyze.py                     # Analysis & report generation
│   └── results/                       # Test results (CSV + JSON + reports)
├── demo/
│   ├── e2e_demo.py                    # End-to-end demo (5 scenarios)
│   └── receipts_demo.py               # Signed Receipts trust pipeline demo
├── integrations/
│   └── langchain/                     # LangChain integration (callback + tools)
├── paper/
│   └── asm-paper-draft.md             # Academic paper draft
├── sep/
│   └── sep-asm-service-value.md       # SEP proposal for MCP specification
└── docs/
    └── internal/                      # Design notes, strategy docs, etc.
```

### 14 Services Across 6 Categories

| Category | Services |
|---|---|
| **LLM Chat** | Claude Sonnet 4, GPT-4o, Gemini 2.5 Pro |
| **Image Generation** | FLUX 1.1 Pro, DALL-E 3, Imagen 3 |
| **Video Generation** | Veo 3.1, Kling 3.0 |
| **Text-to-Speech** | ElevenLabs TTS v2, OpenAI TTS |
| **Embedding** | text-embedding-3-large, Voyage 3 Large |
| **GPU Compute** | Replicate Serverless, RunPod Serverless |

---

## Scorer

Two scoring methods, **fully aligned** between Python and TypeScript (verified by cross-language parity tests):

**Weighted Average** — simple, transparent, demo-ready.

**TOPSIS** — multi-criteria decision making that considers distance to both ideal and worst solutions. More robust against extreme values.

Both support:
- **Hard constraints** (filter): `quality >= 0.8 AND latency <= 5s`
- **Soft preferences** (rank): `cost=0.4, quality=0.35, speed=0.15, reliability=0.10`
- **Configurable io_ratio**: `0.3` (chat), `0.8` (RAG), `0.1` (creative writing) — controls input vs output token cost blending

### Run Tests

```bash
# Python unit tests (3 tests: golden, io_ratio regression, cross-language parity)
python3 scorer/test_scorer.py

# TypeScript unit tests
cd registry && npm test
```

### A/B Test Results (Real API Calls)

ASM TOPSIS selection vs Random vs Most-Expensive strategy, tested with real LLM API calls:

| Metric | ASM TOPSIS | Random | Expensive |
|---|---|---|---|
| TOPSIS Score | **0.8679** | 0.4571 | 0.3990 |
| Response Quality | **0.97** | 0.76 | 0.90 |
| Keyword Hit Rate | **100%** | 60% | 80% |

Statistical significance: **A vs B p=0.048 ✅ | A vs C p=0.001 ✅**

---

## MCP Server

The `asm-registry` MCP server provides 5 tools:

| Tool | Description |
|---|---|
| `asm_list` | List all services in the registry |
| `asm_get` | Get full manifest for a specific service |
| `asm_query` | Filter by taxonomy, cost, quality, latency, modality |
| `asm_compare` | Side-by-side comparison of 2-5 services |
| `asm_score` | Score and rank with custom preference weights |

### Configure in Claude Desktop

```json
{
  "mcpServers": {
    "asm-registry": {
      "command": "node",
      "args": ["/path/to/asm-spec/registry/dist/index.js"]
    }
  }
}
```

---

## Trust Model

ASM implements a 3-layer trust architecture:

```
L1: self_reported flag          → Agent knows "who says this"
L2: Third-party benchmarks      → Independently verifiable scores
L3: Signed Receipts (post-hoc)  → ASM declares → Receipt proves → Trust updates
```

### L1: Transparency at the Source

Every quality metric carries a `self_reported` boolean. An agent can distinguish a vendor's own claim (`self_reported: true`) from an independent benchmark result (`self_reported: false`).

### L2: External Verification

Quality metrics reference public benchmarks with URLs, evaluation dates, and leaderboard positions — all independently checkable.

### L3: Signed Receipts Integration

ASM manifests declare expected service quality *before* execution. [Signed Receipts](https://datatracker.ietf.org/doc/draft-farley-acta-signed-receipts/) (IETF ACTA) prove what *actually* happened after execution. The combination enables **computable trust**:

```
trust_delta(service, metric) = |declared_value - actual_value| / declared_value
```

If a manifest declares `latency_p50: 200ms` but receipts consistently record 450ms, the trust delta is 1.25 — a quantifiable, verifiable credibility signal. No other protocol stack provides this.

The `asm:` namespace is registered for receipt type fields:
- `asm:service_selection` — records which service was chosen, from which candidate pool, and why
- Receipt payloads carry `service_id` and `taxonomy` from the manifest for full traceability

Integration status: active collaboration with the [Agent Receipts](https://github.com/nicholasgriffintn/agent-receipts) team. Schema v0.3 will add `receipt_endpoint`, `verification.protocol`, and `verification.public_key` fields.

---

## Design Principles

1. **MCP-compatible** — can embed as `x-asm` annotations in ToolAnnotations
2. **Minimal required fields** — only `asm_version`, `service_id`, `taxonomy`
3. **Multi-dimensional pricing** — `billing_dimensions` array (LLM has input + output tokens)
4. **Trust transparency** — `self_reported` flag distinguishes self-assessed vs third-party verified
5. **Extensions don't pollute core** — category-specific fields in `extensions` namespace
6. **Declaration, not execution** — ASM declares value, AP2 executes payment

---

## Integration Path

| Phase | How | Status |
|---|---|---|
| Phase 1 | Independent `.well-known/asm` endpoint | Current |
| Phase 2 | `x-asm` embedded in MCP ToolAnnotations | After SEP |
| Phase 3 | Native MCP core fields | Long-term |

---

## Related Work

| Project | Solves | Doesn't Solve | ASM Relationship |
|---|---|---|---|
| MCP | What tools can do | What tools are worth | ASM extends MCP |
| A2A | Agent communication | Service selection | Complementary |
| AP2 | Secure payment | What to buy | ASM is AP2's pre-decision layer |
| Agent Receipts | Post-execution proof | Pre-selection data | ASM declares, Receipts verify |
| RouteLLM | Intra-category LLM routing | Cross-category selection | Complementary |
| AWS Marketplace MCP | Closed platform comparison | Open standard | ASM is the open version |

---

## Roadmap

- [x] Schema v0.2 (JSON Schema)
- [x] 18-category taxonomy
- [x] 70 real-world manifests (6 categories)
- [x] Scorer (Weighted Average + TOPSIS)
- [x] MCP Server (5 tools) + HTTP API
- [x] E2E demo (5 scenarios)
- [x] Schema v0.3 (`receipt_endpoint`, `verification`, `updated_at`, `ttl`)
- [x] Trust delta scoring with exponential decay
- [x] Signed Receipts integration demo
- [x] Configurable io_ratio (chat/RAG/creative cost blending)
- [x] Python ↔ TypeScript cross-language parity (verified)
- [x] Unit tests (golden, regression, cross-language)
- [x] **Real A/B test with live API calls** (TOPSIS vs Random: p<0.05 ✅)
- [x] arXiv preprint
- [x] SEP proposal to MCP specification
- [x] MCP community discussion ([#718](https://github.com/orgs/modelcontextprotocol/discussions/718))
- [ ] Automated manifest crawler pipeline
- [ ] LangChain PR / framework integration
- [ ] Conference submission (AAMAS / WWW)

---

## Contributing

ASM is an open protocol. Contributions welcome:

- **Add a manifest**: Create a `.asm.json` for any AI service
- **Improve the scorer**: Better normalization, new MCDM methods
- **Extend taxonomy**: Propose new categories via PR
- **Build integrations**: Embed ASM in your MCP server

---

## Citation

```bibtex
@misc{asm2026,
  title={Agent Service Manifest: A Standardized Value Description Protocol
         for Autonomous Service Selection in Multi-Agent Systems},
  author={Guo, Yi},
  year={2026},
  howpublished={\url{https://github.com/asm-protocol/asm-spec}}
}
```

---

## License

MIT — see [LICENSE](LICENSE).
