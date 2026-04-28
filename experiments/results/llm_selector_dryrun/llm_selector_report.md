# LLM Raw-Doc vs ASM Manifest Selector

Generated at: 2026-04-28T10:08:34Z
Tasks: 20
Provider/model: none / none
Ran LLM: False
Prompt selectors: raw_doc, manifest
Runs per task: 1
Max candidates per task: 5
Prompts generated: 40
Raw-source fetch events: 40

## Prompt Surface

| Selector | Prompts | Mean prompt chars | Max prompt chars | Est. mean prompt tokens |
|---|---:|---:|---:|---:|
| llm_manifest | 20 | 3981.5 | 4410 | 995.4 |
| llm_raw_doc | 20 | 7967.6 | 8657 | 1991.9 |

## Raw-Source Fetches

Unique sources: 24
Cache hit rate: 100.0%
Unavailable rate: 0.0%
Mean returned chars: 3675.9

## Selection Outcomes

| Selector | Utility mean | Regret mean | Constraint violations | Parse failures | Prompt chars | Cost mean | Latency mean | Quality mean |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| asm_topsis | 0.8972 | 0.0000 | 0.0% | 0.0% | 0.0 | 0.0035955130 | 7.0649 | 0.7143 |
| weighted_average | 0.8436 | 0.0536 | 0.0% | 0.0% | 0.0 | 0.0207955155 | 5.5574 | 0.7177 |
| fastest_first | 0.8355 | 0.0617 | 0.0% | 0.0% | 0.0 | 0.0208955130 | 5.5449 | 0.7185 |
| cheapest_first | 0.7472 | 0.1500 | 0.0% | 0.0% | 0.0 | 0.0035955130 | 7.0674 | 0.7143 |
| highest_quality_first | 0.5023 | 0.3949 | 0.0% | 0.0% | 0.0 | 0.0213172680 | 5.9524 | 0.7489 |
| most_expensive_first | 0.2025 | 0.6946 | 0.0% | 0.0% | 0.0 | 0.0218312680 | 6.0224 | 0.5559 |
