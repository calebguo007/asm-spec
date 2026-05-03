**Table 4: Mean outcomes across 200 tasks, 3 selectors.**

| Selector | n | TOPSIS utility | Cost | Quality | Latency |
|---|---:|---:|---:|---:|---:|
| ASM-TOPSIS | 200 | 0.6700 | 0.004368 | 0.5184 | 3.1979 |
| Random | 200 | 0.5445 | 0.006211 | 0.5196 | 3.1808 |
| Most-expensive-first | 200 | 0.4010 | 0.010694 | 0.5227 | 2.9042 |

**Welch's t-tests, ASM vs baselines:**

| Metric | Comparison | t | p |
|---|---|---:|---:|
| topsis_score | A_vs_B | 4.999 | 8.80e-07 |
| topsis_score | A_vs_C | 11.063 | 6.56e-25 |
| cost_per_unit | A_vs_B | -1.082 | 2.80e-01 |
| cost_per_unit | A_vs_C | -2.317 | 2.14e-02 |
