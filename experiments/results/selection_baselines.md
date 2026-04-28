# Selection Baseline and Regret Evaluation

Generated at: 2026-04-28T09:58:42Z
Tasks: 200
Seed: 2024

Regret is computed as `utility(best feasible service) - utility(selected service)` under the task's preference vector. Lower is better; zero means the strategy selected a utility-optimal service for that candidate set.

| Strategy | Utility mean | Regret mean | Zero-regret rate | Cost mean | Latency mean | Quality mean |
|---|---:|---:|---:|---:|---:|---:|
| asm_topsis | 0.9071 | 0.0000 | 100.0% | 0.0058011640 | 6.8914 | 0.6199 |
| fastest_first | 0.8369 | 0.0703 | 83.0% | 0.0212652890 | 5.4919 | 0.6289 |
| weighted_average | 0.8285 | 0.0787 | 79.0% | 0.0178044554 | 5.8205 | 0.6283 |
| cheapest_first | 0.6406 | 0.2665 | 68.5% | 0.0057811528 | 6.8900 | 0.6240 |
| random | 0.5329 | 0.3742 | 51.5% | 0.0154392470 | 6.3357 | 0.5892 |
| highest_quality_first | 0.4089 | 0.4982 | 31.0% | 0.0216596447 | 5.9288 | 0.6564 |
| most_expensive_first | 0.1980 | 0.7091 | 13.0% | 0.0220168655 | 6.0715 | 0.5780 |
