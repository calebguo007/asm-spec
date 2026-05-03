# Live Execution: Chinese-LLM gateway

Generated: 2026-05-03T06:49:05Z
Tasks: 30
Gateway: https://tokendance.space/gateway/v1
Judge model: glm-4.7
LLM-picker model: qwen3-max

## Aggregate by selector (lower cost / latency / violation rates better; higher judge score better)

| Selector | n | Judge mean | Total cost (USD) | Mean latency (s) | Cost-viol | Latency-viol | Quality-viol |
|---|---:|---:|---:|---:|---:|---:|---:|
| llm_picker_raw_doc | 30 | 9.97 | $0.0068 | 5.74 | 0% | 7% | 0% |
| llm_picker_manifest | 30 | 9.60 | $0.0411 | 17.55 | 0% | 13% | 3% |
| cheapest_first | 30 | 9.50 | $0.0054 | 7.39 | 0% | 10% | 0% |
| random | 29 | 9.28 | $0.0392 | 18.45 | 0% | 17% | 0% |
| asm_topsis | 30 | 7.93 | $0.0149 | 13.46 | 0% | 10% | 0% |
| weighted_average | 30 | 7.40 | $0.0145 | 17.71 | 0% | 7% | 3% |
