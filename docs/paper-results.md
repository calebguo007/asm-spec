# Paper Results Snapshot

This page keeps the long-form empirical summary out of the README while preserving the key numbers behind the paper draft.

## Missing value layer

- 0/50 MCP-related GitHub repositories exposed ASM-style structured value metadata.
- 0/14,519 entries across MCP registries/directories exposed all four core value classes simultaneously: pricing, SLA/rate limit, quality/benchmark, and payment.

## Registry and manifests

- 75 source-linked ASM manifests.
- 47 taxonomies.
- All manifests validate against `schema/asm-v0.3.schema.json`.

## Offline selection

- 200-task A/B suite: ASM-TOPSIS improves preference-weighted utility by 23.1% over random.
- Cost reduction vs most-expensive baseline: 59.2%.
- Scoring overhead: under 5 ms per task.
- 7-policy regret analysis: ASM-TOPSIS has zero regret by construction; weighted average leaves 0.0720 mean regret.

## LLM-as-selector

Across DeepSeek-V4-flash, Qwen3-Max, and Kimi K2.5:

| Surface | Top-1 accuracy |
|---|---:|
| Raw provider HTML/snippets | 63.9-72.2% |
| ASM manifests | 100.0% |

Interpretation: the win is not that ASM makes an LLM smarter; it changes the task from brittle webpage reading to deterministic comparison over structured fields.

## Live execution

The 30-task Chinese-LLM live run is intentionally reported as a stress test:

- Naive 5-candidate run caused ASM-TOPSIS to over-select MiniMax because MiniMax reported MMLU while peers reported Artificial Analysis Intelligence.
- Same-benchmark 4-candidate run restored ASM-TOPSIS to 9.27 judge mean at $0.0064 execution cost.
- Conclusion: ASM inherits manifest semantics; registry-time benchmark compatibility is load-bearing.

## External preference signals

Section 6.8 is a stress test, not a validation claim:

- ASM quality vs LM Arena Elo: pooled heterogeneous metrics are uninformative.
- LMSYS_Elo subset vs Arena Elo: rho = 1.0 with n=3.
- ASM quality vs OpenRouter usage: weak correlation, as expected; usage is affected by price, availability, ecosystem fit, and traffic patterns.

## Reproduce

```bash
make reproduce
```

Live LLM experiments and external snapshots require credentials or external artifacts; see `ARTIFACT.md`.
